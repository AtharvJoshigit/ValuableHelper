# file: engine/core/agent_factory.py

from typing import Optional
import logging
from engine.core.agent import Agent
from engine.core.agent_instance_manager import AgentConfig
from engine.core.memory import Memory
from engine.registry.tool_registry import ToolRegistry
from engine.core.provide import get_provider

logger = logging.getLogger(__name__)

def create_agent(
    config: AgentConfig,
    registry: Optional[ToolRegistry] = None,
    memory: Optional[Memory] = None
) -> Agent:
    """
    Factory function to create an agent instance.
    
    Args:
        config: Agent configuration
        registry: Tool registry (creates new if None)
        memory: Memory instance (creates new if None)
        
    Returns:
        Configured Agent instance
    """
    if registry is None:
        registry = ToolRegistry()
        logger.info("Created new ToolRegistry for agent")
    
    if memory is None:
        memory = Memory()
        logger.info("Created new Memory for agent")
    
    try:
        agent = Agent(
            config=config,
            registry=registry,
            memory=memory
        )
        logger.info(
            f"Created agent with model={config.model}, "
            f"provider={config.provider}, max_steps={config.max_steps}"
        )
        return agent
    
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise

def get_default_config(
    model: str = "gemini-2.5-flash",
    provider: str = "google"
) -> AgentConfig:
    """Get a default agent configuration."""
    return AgentConfig(
        model=model,
        provider=provider,
        system_prompt="You are a helpful AI assistant.",
        max_steps=10,
        temperature=0.7
    )