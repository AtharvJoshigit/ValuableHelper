# engine/core/agent_instance_manager.py (UPDATED)

from datetime import timezone, datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import logging
import asyncio

from database.base import BaseDatabase

logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
    """Configuration for creating an agent."""
    model: str
    provider: str
    system_prompt: Optional[str] = None
    max_steps: int = 10
    temperature: float = 0.7
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    max_tokens: Optional[int] = None
    sensitive_tool_names: set = field(default_factory=set)
    additional_params: Dict[str, Any] = field(default_factory=dict)

    # Memory settings (database-backed)
    enable_memory_summarization: bool = False
    memory_recent_k: int = 10
    memory_summarization_threshold: int = 20
    agent_name: Optional[str] = None
    
    # Advanced memory settings
    memory_importance_threshold: int = 5
    memory_auto_summarize: bool = True
    session_timeout_hours: int = 24
    retention_policy: str = "90days"

    class Config:
        arbitrary_types_allowed = True

    def __post_init__(self):
        if self.max_steps is not None: 
            self.max_steps = int(self.max_steps)
        if self.temperature is not None: 
            self.temperature = float(self.temperature)
        # Ensure sensitive_tool_names is a set
        if not isinstance(self.sensitive_tool_names, set):
            self.sensitive_tool_names = set(self.sensitive_tool_names)


@dataclass
class AgentInstance:
    """Container for agent instance with full configuration."""
    agent: Any
    config: AgentConfig
    memory: Any
    registry: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    initialized: bool = False  # Track initialization status


class AgentInstanceManager:
    """
    Manages agent instances with database-backed memory support.
    Singleton pattern to ensure single instance across application.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentInstanceManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._agents: Dict[str, AgentInstance] = {}
        self._current_agent_id: Optional[str] = None
        self._agent_factory: Optional[Callable] = None
        self._database: Optional[BaseDatabase] = None
        self._initialization_tasks: Dict[str, asyncio.Task] = {}
        self._initialized = True
        logger.info("AgentInstanceManager initialized")
    
    def set_database(self, db: BaseDatabase):
        """
        Set the database connection for all agents.
        Should be called during application startup.
        
        Args:
            db: Database instance
        """
        self._database = db
        
        # Also set global database for factory
        from engine.core.agent_factory import set_global_database
        set_global_database(db)
        
        logger.info("✅ Database set for AgentInstanceManager")
    
    def get_database(self) -> Optional[BaseDatabase]:
        """Get the database connection."""
        return self._database
    
    def set_agent_factory(self, factory: Callable):
        """
        Set the factory function for creating agents.
        
        Args:
            factory: Function that creates an agent
                     Signature: factory(agent_id, config, registry, memory) -> Agent
        """
        self._agent_factory = factory
        logger.info("Agent factory set")
    
    def create_and_register_agent(
        self,
        agent_id: str,
        config: AgentConfig,
        registry: Any,
        memory: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        set_as_current: bool = True,
        wait_for_init: bool = False
    ) -> str:
        """
        Create a new agent instance and register it.
        
        Args:
            agent_id: Unique identifier for the agent
            config: Agent configuration
            registry: Tool registry instance
            memory: Memory instance (ignored if using database-backed memory)
            metadata: Additional metadata
            set_as_current: Whether to set this as the current agent
            wait_for_init: If True, blocks until agent is initialized (async contexts only)
            
        Returns:
            agent_id
        """
        if not self._agent_factory:
            raise ValueError("Agent factory not set. Call set_agent_factory() first.")
        
        # Create agent using factory
        agent = self._agent_factory(
            agent_id=agent_id,
            config=config,
            registry=registry,
            memory=memory
        )
        
        instance = AgentInstance(
            agent=agent,
            config=config,
            memory=agent.memory,
            registry=registry,
            metadata=metadata or {},
            initialized=False
        )
        
        self._agents[agent_id] = instance
        
        if set_as_current or self._current_agent_id is None:
            self._current_agent_id = agent_id
        
        # Check if agent needs async initialization
        if hasattr(agent, '_initialized') and not agent._initialized:
            # Agent has database-backed memory, needs initialization
            if wait_for_init:
                # Block and wait (only works in async context)
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        logger.warning(
                            f"Cannot wait for initialization in running loop. "
                            f"Agent '{agent_id}' will initialize in background."
                        )
                    else:
                        loop.run_until_complete(agent.initialize())
                        instance.initialized = True
                except RuntimeError:
                    logger.warning(f"No event loop, agent '{agent_id}' will initialize lazily")
            else:
                # Schedule background initialization
                self._schedule_initialization(agent_id, agent)
        else:
            # Old-style agent, already ready
            instance.initialized = True
        
        logger.info(
            f"Created and registered agent '{agent_id}' with model '{config.model}' "
            f"(initialized: {instance.initialized})"
        )
        return agent_id
    
    def _schedule_initialization(self, agent_id: str, agent: Any):
        """Schedule agent initialization in background."""
        async def init():
            try:
                await agent.initialize()
                if agent_id in self._agents:
                    self._agents[agent_id].initialized = True
                logger.info(f"✅ Agent '{agent_id}' initialized in background")
            except Exception as e:
                logger.error(f"❌ Failed to initialize agent '{agent_id}': {e}")
        
        try:
            task = asyncio.create_task(init())
            self._initialization_tasks[agent_id] = task
        except RuntimeError:
            # No event loop running, initialization will happen on first use
            logger.info(f"No event loop, agent '{agent_id}' will initialize on first use")
    
    async def ensure_agent_initialized(self, agent_id: Optional[str] = None):
        """
        Ensure agent is initialized before use.
        Call this before using agent in async contexts.
        
        Args:
            agent_id: Agent identifier (if None, uses current agent)
        """
        if agent_id is None:
            agent_id = self._current_agent_id
        
        if not agent_id or agent_id not in self._agents:
            return
        
        instance = self._agents[agent_id]
        
        if instance.initialized:
            return
        
        # Wait for initialization task if exists
        if agent_id in self._initialization_tasks:
            await self._initialization_tasks[agent_id]
            return
        
        # Initialize now if not yet done
        if hasattr(instance.agent, 'initialize'):
            await instance.agent.initialize()
            instance.initialized = True
    
    def register_agent(
        self,
        agent_id: str,
        agent: Any,
        config: AgentConfig,
        registry: Any,
        memory: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Register an existing agent instance."""
        instance = AgentInstance(
            agent=agent,
            config=config,
            memory=memory,
            registry=registry,
            metadata=metadata or {},
            initialized=getattr(agent, '_initialized', True)
        )
        
        self._agents[agent_id] = instance
        
        if self._current_agent_id is None:
            self._current_agent_id = agent_id
        
        logger.info(f"Registered agent '{agent_id}'")
        return agent_id
    
    def get_agent(self, agent_id: Optional[str] = None) -> Optional[Any]:
        """Get agent instance by ID or current agent."""
        if agent_id is None:
            agent_id = self._current_agent_id
        
        if agent_id and agent_id in self._agents:
            return self._agents[agent_id].agent
        
        return None
    
    def get_memory(self, agent_id: Optional[str] = None) -> Optional[Any]:
        """Get memory instance by agent ID or current agent."""
        if agent_id is None:
            agent_id = self._current_agent_id
        
        if agent_id and agent_id in self._agents:
            return self._agents[agent_id].memory
        
        return None
    
    def get_config(self, agent_id: Optional[str] = None) -> Optional[AgentConfig]:
        """Get agent configuration by ID or current agent."""
        if agent_id is None:
            agent_id = self._current_agent_id
        
        if agent_id and agent_id in self._agents:
            return self._agents[agent_id].config
        
        return None
    
    def get_registry(self, agent_id: Optional[str] = None) -> Optional[Any]:
        """Get tool registry by agent ID or current agent."""
        if agent_id is None:
            agent_id = self._current_agent_id
        
        if agent_id and agent_id in self._agents:
            return self._agents[agent_id].registry
        
        return None
    
    def get_current_agent_id(self) -> Optional[str]:
        """Get current active agent ID."""
        return self._current_agent_id
    
    def set_current_agent(self, agent_id: str) -> bool:
        """Set the current active agent."""
        if agent_id in self._agents:
            self._current_agent_id = agent_id
            logger.info(f"Current agent set to '{agent_id}'")
            return True
        
        logger.warning(f"Agent '{agent_id}' not found")
        return False
    
    def update_agent(
        self,
        agent_id: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_steps: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None,
        sensitive_tool_names: Optional[set] = None,
        preserve_memory: bool = True,
        preserve_registry: bool = True,
        **additional_params
    ) -> str:
        """Update agent configuration and recreate instance."""
        if not self._agent_factory:
            raise ValueError("Agent factory not set.")
        
        if agent_id is None:
            agent_id = self._current_agent_id
        
        if not agent_id or agent_id not in self._agents:
            raise ValueError(f"Agent '{agent_id}' not found")
        
        old_instance = self._agents[agent_id]
        old_config = old_instance.config
        
        # Build new config
        new_config = AgentConfig(
            model=model if model is not None else old_config.model,
            provider=provider if provider is not None else old_config.provider,
            system_prompt=system_prompt if system_prompt is not None else old_config.system_prompt,
            max_steps=max_steps if max_steps is not None else old_config.max_steps,
            temperature=temperature if temperature is not None else old_config.temperature,
            top_p=top_p if top_p is not None else old_config.top_p,
            top_k=top_k if top_k is not None else old_config.top_k,
            max_tokens=max_tokens if max_tokens is not None else old_config.max_tokens,
            sensitive_tool_names=sensitive_tool_names if sensitive_tool_names is not None else old_config.sensitive_tool_names,
            additional_params={**old_config.additional_params, **additional_params},
            
            # Preserve memory settings
            enable_memory_summarization=old_config.enable_memory_summarization,
            memory_recent_k=old_config.memory_recent_k,
            memory_summarization_threshold=old_config.memory_summarization_threshold,
            agent_name=old_config.agent_name,
            session_timeout_hours=old_config.session_timeout_hours
        )
        
        new_memory = old_instance.memory if preserve_memory else None
        new_registry = old_instance.registry if preserve_registry else None
        
        # Create new agent
        new_agent = self._agent_factory(
            agent_id=agent_id,
            config=new_config,
            registry=new_registry,
            memory=new_memory
        )
        
        # Update instance
        new_instance = AgentInstance(
            agent=new_agent,
            config=new_config,
            memory=new_agent.memory,
            registry=new_registry,
            metadata=old_instance.metadata.copy(),
            initialized=False
        )
        
        new_instance.metadata['updated_at'] = self._get_timestamp()
        
        self._agents[agent_id] = new_instance
        
        # Schedule initialization
        if hasattr(new_agent, 'initialize'):
            self._schedule_initialization(agent_id, new_agent)
        
        logger.info(f"Updated agent '{agent_id}'")
        return agent_id
    
    def switch_model(
        self,
        new_model: str,
        agent_id: Optional[str] = None,
        preserve_memory: bool = True,
        preserve_registry: bool = True
    ) -> str:
        """Switch to a different model while preserving configuration."""
        return self.update_agent(
            agent_id=agent_id,
            model=new_model,
            preserve_memory=preserve_memory,
            preserve_registry=preserve_registry
        )
    
    def get_agent_info(self, agent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get information about an agent."""
        if agent_id is None:
            agent_id = self._current_agent_id
        
        if agent_id and agent_id in self._agents:
            instance = self._agents[agent_id]
            config = instance.config
            
            return {
                "agent_id": agent_id,
                "model": config.model,
                "provider": config.provider,
                "system_prompt": config.system_prompt,
                "max_steps": config.max_steps,
                "temperature": config.temperature,
                "has_memory": instance.memory is not None,
                "memory_type": type(instance.memory).__name__,
                "initialized": instance.initialized,
                "is_current": agent_id == self._current_agent_id,
                "enable_memory_summarization": config.enable_memory_summarization,
                "metadata": instance.metadata
            }
        
        return None
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents."""
        return [
            self.get_agent_info(agent_id)
            for agent_id in self._agents.keys()
        ]
    
    def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent instance."""
        if agent_id not in self._agents:
            return False
        
        # Cancel initialization task if exists
        if agent_id in self._initialization_tasks:
            self._initialization_tasks[agent_id].cancel()
            del self._initialization_tasks[agent_id]
        
        del self._agents[agent_id]
        
        if self._current_agent_id == agent_id:
            self._current_agent_id = next(iter(self._agents.keys())) if self._agents else None
        
        logger.info(f"Removed agent '{agent_id}'")
        return True
    
    def clear_all(self):
        """Clear all agent instances."""
        # Cancel all initialization tasks
        for task in self._initialization_tasks.values():
            task.cancel()
        
        self._initialization_tasks.clear()
        self._agents.clear()
        self._current_agent_id = None
        logger.info("Cleared all agent instances")
    
    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp."""
        return datetime.now(timezone.utc)


def get_agent_manager() -> AgentInstanceManager:
    """Get the global agent instance manager."""
    return AgentInstanceManager()