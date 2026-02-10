# file: agent_instance_manager.py

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

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


@dataclass
class AgentInstance:
    """Container for agent instance with full configuration."""
    agent: Any
    config: AgentConfig
    memory: Any
    registry: Any
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentInstanceManager:
    """
    Manages agent instances and allows switching models/configs while preserving state.
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
        self._initialized = True
        logger.info("AgentInstanceManager initialized")
    
    def set_agent_factory(self, factory: Callable):
        """
        Set the factory function for creating agents.
        
        Args:
            factory: Function that creates an agent given config, registry, and memory
                     Signature: factory(config: AgentConfig, registry: ToolRegistry, memory: Memory) -> Agent
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
        set_as_current: bool = True
    ) -> str:
        """
        Create a new agent instance and register it.
        
        Args:
            agent_id: Unique identifier for the agent
            config: Agent configuration
            registry: Tool registry instance
            memory: Memory instance (if None, agent will create its own)
            metadata: Additional metadata
            set_as_current: Whether to set this as the current agent
            
        Returns:
            agent_id
        """
        if not self._agent_factory:
            raise ValueError("Agent factory not set. Call set_agent_factory() first.")
        
        agent = self._agent_factory(
            config=config,
            registry=registry,
            memory=memory
        )
        
        instance = AgentInstance(
            agent=agent,
            config=config,
            memory=agent.memory,
            registry=registry,
            metadata=metadata or {}
        )
        
        self._agents[agent_id] = instance
        
        if set_as_current or self._current_agent_id is None:
            self._current_agent_id = agent_id
        
        logger.info(
            f"Created and registered agent '{agent_id}' with model '{config.model}' "
            f"and provider '{config.provider}'"
        )
        return agent_id
    
    def register_agent(
        self,
        agent_id: str,
        agent: Any,
        config: AgentConfig,
        registry: Any,
        memory: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Register an existing agent instance.
        
        Args:
            agent_id: Unique identifier for the agent
            agent: Agent instance
            config: Agent configuration
            registry: Tool registry instance
            memory: Memory instance
            metadata: Additional metadata
            
        Returns:
            agent_id
        """
        instance = AgentInstance(
            agent=agent,
            config=config,
            memory=memory,
            registry=registry,
            metadata=metadata or {}
        )
        
        self._agents[agent_id] = instance
        
        if self._current_agent_id is None:
            self._current_agent_id = agent_id
        
        logger.info(
            f"Registered agent '{agent_id}' with model '{config.model}' "
            f"and provider '{config.provider}'"
        )
        return agent_id
    
    def get_agent(self, agent_id: Optional[str] = None) -> Optional[Any]:
        """
        Get agent instance by ID or current agent.
        
        Args:
            agent_id: Agent identifier (if None, returns current agent)
            
        Returns:
            Agent instance or None
        """
        if agent_id is None:
            agent_id = self._current_agent_id
        
        if agent_id and agent_id in self._agents:
            return self._agents[agent_id].agent
        
        return None
    
    def get_memory(self, agent_id: Optional[str] = None) -> Optional[Any]:
        """
        Get memory instance by agent ID or current agent.
        
        Args:
            agent_id: Agent identifier (if None, returns current agent memory)
            
        Returns:
            Memory instance or None
        """
        if agent_id is None:
            agent_id = self._current_agent_id
        
        if agent_id and agent_id in self._agents:
            return self._agents[agent_id].memory
        
        return None
    
    def get_config(self, agent_id: Optional[str] = None) -> Optional[AgentConfig]:
        """
        Get agent configuration by ID or current agent.
        
        Args:
            agent_id: Agent identifier (if None, returns current agent config)
            
        Returns:
            AgentConfig or None
        """
        if agent_id is None:
            agent_id = self._current_agent_id
        
        if agent_id and agent_id in self._agents:
            return self._agents[agent_id].config
        
        return None
    
    def get_registry(self, agent_id: Optional[str] = None) -> Optional[Any]:
        """
        Get tool registry by agent ID or current agent.
        
        Args:
            agent_id: Agent identifier (if None, returns current agent registry)
            
        Returns:
            Registry instance or None
        """
        if agent_id is None:
            agent_id = self._current_agent_id
        
        if agent_id and agent_id in self._agents:
            return self._agents[agent_id].registry
        
        return None
    
    def get_current_agent_id(self) -> Optional[str]:
        """Get current active agent ID."""
        return self._current_agent_id
    
    def set_current_agent(self, agent_id: str) -> bool:
        """
        Set the current active agent.
        
        Args:
            agent_id: Agent identifier to set as current
            
        Returns:
            True if successful, False otherwise
        """
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
        """
        Update agent configuration and recreate instance.
        Only updates parameters that are explicitly provided.
        
        Args:
            agent_id: Agent to update (if None, uses current agent)
            model: New model (if None, keeps existing)
            provider: New provider (if None, keeps existing)
            system_prompt: New system prompt (if None, keeps existing)
            max_steps: New max steps (if None, keeps existing)
            temperature: New temperature (if None, keeps existing)
            top_p: New top_p (if None, keeps existing)
            top_k: New top_k (if None, keeps existing)
            max_tokens: New max_tokens (if None, keeps existing)
            sensitive_tool_names: New sensitive tools (if None, keeps existing)
            preserve_memory: Whether to preserve existing memory
            preserve_registry: Whether to preserve existing registry
            **additional_params: Additional parameters to update
            
        Returns:
            agent_id of the updated agent
        """
        if not self._agent_factory:
            raise ValueError("Agent factory not set. Call set_agent_factory() first.")
        
        if agent_id is None:
            agent_id = self._current_agent_id
        
        if not agent_id or agent_id not in self._agents:
            logger.error(f"Agent '{agent_id}' not found for update")
            raise ValueError(f"Agent '{agent_id}' not found")
        
        old_instance = self._agents[agent_id]
        old_config = old_instance.config
        
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
            additional_params={**old_config.additional_params, **additional_params}
        )
        
        new_memory = old_instance.memory if preserve_memory else None
        new_registry = old_instance.registry if preserve_registry else None
        
        new_agent = self._agent_factory(
            config=new_config,
            registry=new_registry,
            memory=new_memory
        )
        
        new_instance = AgentInstance(
            agent=new_agent,
            config=new_config,
            memory=new_agent.memory,
            registry=new_registry,
            metadata=old_instance.metadata.copy()
        )
        
        new_instance.metadata['previous_config'] = {
            'model': old_config.model,
            'provider': old_config.provider,
            'temperature': old_config.temperature,
            'max_steps': old_config.max_steps
        }
        new_instance.metadata['updated_at'] = self._get_timestamp()
        
        changes = []
        if model and model != old_config.model:
            changes.append(f"model: {old_config.model} -> {model}")
        if provider and provider != old_config.provider:
            changes.append(f"provider: {old_config.provider} -> {provider}")
        if temperature is not None and temperature != old_config.temperature:
            changes.append(f"temperature: {old_config.temperature} -> {temperature}")
        if max_steps is not None and max_steps != old_config.max_steps:
            changes.append(f"max_steps: {old_config.max_steps} -> {max_steps}")
        
        self._agents[agent_id] = new_instance
        
        logger.info(f"Updated agent '{agent_id}': {', '.join(changes) if changes else 'no parameter changes'}")
        return agent_id
    
    def switch_model(
        self,
        new_model: str,
        agent_id: Optional[str] = None,
        preserve_memory: bool = True,
        preserve_registry: bool = True
    ) -> str:
        """
        Switch to a different model while preserving other configuration.
        
        Args:
            new_model: New model identifier
            agent_id: Agent to update (if None, uses current agent)
            preserve_memory: Whether to preserve existing memory
            preserve_registry: Whether to preserve existing registry
            
        Returns:
            agent_id of the updated agent
        """
        return self.update_agent(
            agent_id=agent_id,
            model=new_model,
            preserve_memory=preserve_memory,
            preserve_registry=preserve_registry
        )
    
    def transfer_memory(
        self,
        source_agent_id: str,
        target_agent_id: str
    ) -> bool:
        """
        Transfer memory from one agent to another.
        
        Args:
            source_agent_id: Source agent ID
            target_agent_id: Target agent ID
            
        Returns:
            True if successful, False otherwise
        """
        if source_agent_id not in self._agents or target_agent_id not in self._agents:
            logger.error("Source or target agent not found for memory transfer")
            return False
        
        source_memory = self._agents[source_agent_id].memory
        
        self._agents[target_agent_id].memory = source_memory
        self._agents[target_agent_id].agent.memory = source_memory
        
        logger.info(f"Transferred memory from '{source_agent_id}' to '{target_agent_id}'")
        return True
    
    def get_agent_info(self, agent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get information about an agent.
        
        Args:
            agent_id: Agent identifier (if None, returns current agent info)
            
        Returns:
            Dictionary with agent information
        """
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
                "top_p": config.top_p,
                "top_k": config.top_k,
                "max_tokens": config.max_tokens,
                "sensitive_tool_names": list(config.sensitive_tool_names),
                "has_memory": instance.memory is not None,
                "memory_length": len(instance.memory.get_history()) if instance.memory else 0,
                "has_registry": instance.registry is not None,
                "metadata": instance.metadata,
                "is_current": agent_id == self._current_agent_id,
                "additional_params": config.additional_params
            }
        
        return None
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents."""
        return [
            self.get_agent_info(agent_id)
            for agent_id in self._agents.keys()
        ]
    
    def remove_agent(self, agent_id: str) -> bool:
        """
        Remove an agent instance.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if successful, False otherwise
        """
        if agent_id not in self._agents:
            return False
        
        del self._agents[agent_id]
        
        if self._current_agent_id == agent_id:
            self._current_agent_id = next(iter(self._agents.keys())) if self._agents else None
        
        logger.info(f"Removed agent '{agent_id}'")
        return True
    
    def clear_all(self):
        """Clear all agent instances."""
        self._agents.clear()
        self._current_agent_id = None
        logger.info("Cleared all agent instances")
    
    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()


def get_agent_manager() -> AgentInstanceManager:
    """Get the global agent instance manager."""
    return AgentInstanceManager()