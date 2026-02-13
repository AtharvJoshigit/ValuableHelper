# file: engine/core/agent_factory.py

from typing import Optional
import logging
from engine.core.agent import Agent
from engine.core.agent_instance_manager import AgentConfig
from engine.core.memory import Memory
from engine.registry.tool_registry import ToolRegistry
from engine.registry.tool_discovery import ToolDiscovery
from engine.core.provide import get_provider

logger = logging.getLogger(__name__)

def create_agent(
    agent_id : str,
    config: AgentConfig,
    registry: Optional[ToolRegistry] = None,
    memory: Optional[Memory] = None
) -> Agent:
    """
    Factory function to create an agent instance.
    Automatically populates the registry using the Discovery Service if no registry is provided.
    """
    if registry is None:
        registry = ToolRegistry()
        discovery = ToolDiscovery()
        # Default sub-agents do NOT get access to the private 'tools/' folder
        tools = discovery.discover_tools(include_tools_dir=False)
        for tool in tools:
            try:
                registry.register(tool)
            except Exception as e:
                logger.debug(f"Tool {tool.name} already registered or failed: {e}")
        logger.info(f"Created new ToolRegistry with {len(tools)} auto-discovered tools")
    
    if memory is None:
        memory = Memory()
    
    try:
        agent = Agent(
            agent_id=agent_id,
            config=config,
            registry=registry,
            memory=memory
        )
        return agent
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise

def get_default_config(
    model: str = "gemini-2.0-flash-thinking-exp-1219",
    provider: str = "google"
) -> AgentConfig:
    return AgentConfig(
        model=model,
        provider=provider,
        system_prompt="You are a helpful AI assistant.",
        max_steps=10,
        temperature=0.7
    )
