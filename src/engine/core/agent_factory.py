# engine/core/agent_factory.py (UPDATED for AgentInstanceManager integration)

from typing import Optional
import logging
import asyncio

from engine.core.agent import Agent
from engine.core.agent_instance_manager import AgentConfig
from engine.core.memory_manager import MemoryManager
from engine.core.memory import Memory  # Keep for backward compatibility
from engine.registry.tool_registry import ToolRegistry
from engine.registry.tool_discovery import ToolDiscovery
from database.base import BaseDatabase

logger = logging.getLogger(__name__)

# Global database instance for factory
_global_db: Optional[BaseDatabase] = None

def set_global_database(db: BaseDatabase):
    """
    Set global database for agent factory.
    Must be called during application startup.
    
    Usage:
        from infrastructure.database.db_manager import DatabaseManager
        
        db = await DatabaseManager.initialize()
        set_global_database(db)
    """
    global _global_db
    _global_db = db
    logger.info("✅ Global database set for agent factory")

def get_global_database() -> Optional[BaseDatabase]:
    """Get the global database instance."""
    return _global_db


def create_agent(
    agent_id: str,
    config: AgentConfig,
    registry: Optional[ToolRegistry] = None,
    memory: Optional[Memory] = None  # Old-style memory for backward compatibility
) -> Agent:
    """
    Factory function compatible with AgentInstanceManager.
    
    Behavior:
    - If database available: Creates agent with MemoryManager (database-backed)
    - If no database: Falls back to old Memory class
    
    Args:
        agent_id: Unique identifier
        config: Agent configuration
        registry: Tool registry (auto-discovered if None)
        memory: Legacy memory instance (ignored if using database)
    
    Returns:
        Agent instance (not yet initialized if using database)
    """
    # Auto-discover tools if no registry provided
    if registry is None:
        registry = ToolRegistry()
        discovery = ToolDiscovery()
        tools = discovery.discover_tools(["tools"])
        
        registered_count = 0
        for tool in tools:
            try:
                registry.register(tool)
                registered_count += 1
            except Exception as e:
                logger.debug(f"Tool {tool.name} registration failed: {e}")
        
        logger.info(f"✅ Auto-discovered {registered_count} tools")
    
    # Check if database is available
    db = get_global_database()
    
    if db and config.enable_memory_summarization:
        # NEW: Database-backed memory
        logger.info(f"Creating agent '{agent_id}' with database-backed memory")
        
        logger.info(f"Memory Threshold {config.memory_summarization_threshold}")
        memory_manager = MemoryManager(
            db=db,
            agent_id=agent_id,
            agent_name=config.agent_name or agent_id,
            # recent_k=config.memory_recent_k,
            summarization_threshold=config.memory_summarization_threshold,
            enable_summarization=config.enable_memory_summarization,
            auto_summarize=config.memory_auto_summarize,
            recent_k_turns=config.memory_recent_k,
            # session_timeout_hours=getattr(config, 'session_timeout_hours', 24)
        )
        
        agent = Agent(
            agent_id=agent_id,
            config=config,
            registry=registry,
            db=db,
            memory_manager=memory_manager
        )
        
        # Schedule async initialization (non-blocking)
        asyncio.create_task(_initialize_agent_async(agent))
        
        return agent
    
    else:
        # OLD: In-memory fallback
        if db is None:
            logger.warning(
                f"⚠️ Creating agent '{agent_id}' without database. "
                "Call set_global_database() during startup for persistence."
            )
        
        if memory is None:
            memory = Memory()
        
        # Create agent with old-style memory (no database required)
        # This maintains backward compatibility
        try:
            # Try new Agent signature with db parameter
            agent = Agent(
                agent_id=agent_id,
                config=config,
                registry=registry,
                db=db or _create_mock_db(),  # Mock DB for compatibility
                memory_manager=None
            )
            # Inject old-style memory
            agent.memory = memory
            return agent
        except TypeError:
            # Fallback to old Agent signature (if not yet updated)
            logger.warning("Using legacy Agent initialization")
            from engine.core.agent_legacy import Agent as LegacyAgent
            return LegacyAgent(
                agent_id=agent_id,
                config=config,
                registry=registry,
                memory=memory
            )


async def _initialize_agent_async(agent: Agent):
    """Initialize agent asynchronously in the background."""
    try:
        await agent.initialize()
        logger.info(f"✅ Agent '{agent.agent_id}' initialized asynchronously")
    except Exception as e:
        logger.error(f"❌ Failed to initialize agent '{agent.agent_id}': {e}")


def _create_mock_db():
    """Create a mock database for backward compatibility."""
    class MockDB:
        async def connect(self): pass
        async def disconnect(self): pass
        async def execute(self, *args, **kwargs): pass
        async def fetch_one(self, *args, **kwargs): return None
        async def fetch_all(self, *args, **kwargs): return []
    
    return MockDB()


async def create_agent_async(
    agent_id: str,
    config: AgentConfig,
    db: BaseDatabase,
    registry: Optional[ToolRegistry] = None,
    auto_initialize: bool = True
) -> Agent:
    """
    Async version for creating agents with guaranteed initialization.
    Use this when you need the agent to be ready immediately.
    
    Args:
        agent_id: Unique identifier
        config: Agent configuration
        db: Database connection
        registry: Optional tool registry
        auto_initialize: Initialize before returning
    
    Returns:
        Initialized Agent instance
    """
    if registry is None:
        registry = ToolRegistry()
        discovery = ToolDiscovery()
        tools = discovery.discover_tools(["tools"])
        
        for tool in tools:
            try:
                registry.register(tool)
            except:
                pass
    
    memory_manager = MemoryManager(
        db=db,
        agent_id=agent_id,
        agent_name=config.agent_name or agent_id,
        recent_k=config.memory_recent_k,
        summarization_threshold=config.memory_summarization_threshold,
        enable_summarization=config.enable_memory_summarization,
        auto_summarize=config.memory_auto_summarize,
        session_timeout_hours=getattr(config, 'session_timeout_hours', 24)
    )
    
    agent = Agent(
        agent_id=agent_id,
        config=config,
        registry=registry,
        db=db,
        memory_manager=memory_manager
    )
    
    if auto_initialize:
        await agent.initialize()
    
    return agent


def get_default_config(
    model: str = "claude-sonnet-4-20250514",
    provider: str = "anthropic",
    enable_memory: bool = False,  # Default False for backward compatibility
    agent_name: Optional[str] = None
) -> AgentConfig:
    """Get default agent configuration."""
    return AgentConfig(
        model=model,
        provider=provider,
        system_prompt="You are a helpful AI assistant.",
        max_steps=10,
        temperature=0.7,
        
        # Memory settings
        enable_memory_summarization=enable_memory,
        agent_name=agent_name,
        memory_recent_k=10,
        memory_summarization_threshold=20,
        session_timeout_hours=24,
        
        sensitive_tool_names=set()
    )


# Export for backward compatibility
__all__ = [
    'create_agent',
    'create_agent_async',
    'get_default_config',
    'set_global_database',
    'get_global_database'
]