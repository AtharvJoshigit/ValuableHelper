# file: engine/tools/agent_management_tools.py

from typing import Any, Optional, Dict
from engine.core.models import LLModel
from pydantic import Field
from engine.registry.base_tool import BaseTool
from engine.core.agent_instance_manager import get_agent_manager, AgentConfig
from engine.core.agent_factory import create_agent
from engine.registry.tool_registry import ToolRegistry
import logging

logger = logging.getLogger(__name__)


class CreateAgentTool(BaseTool):
    """
    Dynamically creates and registers a new agent instance with custom configuration.
    """
    name: str = "create_agent"
    description: str = (
        "Creates a new agent instance with specified model and configuration. "
        "Allows dynamic agent creation for different purposes (research, coding, creative writing, etc). "
        "The agent is registered and can be switched to later."
    )
    
    agent_id: str = Field('main_agent_child',
        description="Unique identifier for the new agent (e.g., 'research_agent', 'code_assistant')"
    )
    
    model: str = Field('gemini-2.5-pro',
        description=(
            "Model to use for this agent. Options: "
            "gemini-3-pro-preview, gemini-3-flash-preview, "
            "gemini-2.5-pro, gemini-2.5-flash, gemini-2.0-flash"
        )
    )
    
    provider: str = Field(
        default="google",
        description="Provider name (google, openai, anthropic)"
    )
    
    system_prompt: Optional[str] = Field(
        default=None,
        description="System prompt defining agent behavior and personality"
    )
    
    max_steps: Optional[int] = Field(
        default=10,
        description="Maximum reasoning steps for this agent"
    )
    
    temperature: Optional[float] = Field(
        default=0.7,
        description="Temperature for response randomness (0.0-2.0)"
    )
    
    set_as_current: bool = Field(
        default=False,
        description="Whether to set this as the active agent immediately"
    )

    def execute(self, **kwargs: Any) -> Any:
        """Create and register a new agent."""
        agent_id = kwargs.get("agent_id", self.agent_id)
        model = kwargs.get("model", self.model)
        provider = kwargs.get("provider", self.provider)
        system_prompt = kwargs.get("system_prompt", self.system_prompt)
        max_steps = kwargs.get("max_steps", self.max_steps)
        temperature = kwargs.get("temperature", self.temperature)
        set_as_current = kwargs.get("set_as_current", self.set_as_current)
        
        try:
            if isinstance(model, str):
                try:
                    model_enum = LLModel(model)
                    model = model_enum.value
                except ValueError:
                    logger.info(f"Model '{model}' not in LLModel enum, using as-is")
            
            manager = get_agent_manager()
            
            if manager.get_agent(agent_id):
                return {
                    "status": "error",
                    "error": f"Agent with ID '{agent_id}' already exists. Use a different ID or update existing agent."
                }
            
            config = AgentConfig(
                model=model,
                provider=provider,
                system_prompt=system_prompt or "You are a helpful AI assistant.",
                max_steps=max_steps or 10,
                temperature=temperature or 0.7,
                **{k: v for k, v in kwargs.items() if k not in [
                    'agent_id', 'model', 'provider', 'system_prompt',
                    'max_steps', 'temperature', 'set_as_current'
                ]}
            )
            
            registry = ToolRegistry()
            
            created_id = manager.create_and_register_agent(
                agent_id=agent_id,
                config=config,
                registry=registry,
                metadata={
                    "created_by_tool": True,
                    "purpose": kwargs.get("purpose", "general")
                },
                set_as_current=set_as_current
            )
            
            return {
                "status": "success",
                "message": f"Successfully created agent '{created_id}'",
                "agent_id": created_id,
                "config": {
                    "model": config.model,
                    "provider": config.provider,
                    "system_prompt": config.system_prompt,
                    "max_steps": config.max_steps,
                    "temperature": config.temperature
                },
                "is_current": set_as_current
            }
        
        except Exception as e:
            logger.error(f"Error creating agent: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


class SwitchAgentTool(BaseTool):
    """
    Switches between different registered agent instances.
    """
    name: str = "switch_agent"
    description: str = (
        "Switches to a different registered agent instance. "
        "Use this to switch between specialized agents (e.g., from general assistant to code assistant)."
    )
    
    agent_id: str = Field('n/a',
        description="ID of the agent to switch to"
    )

    def execute(self, **kwargs: Any) -> Any:
        """Switch to a different agent."""
        agent_id = kwargs.get("agent_id", self.agent_id)
        
        try:
            manager = get_agent_manager()
            
            if not manager.get_agent(agent_id):
                available = manager.list_agents()
                agent_list = [a["agent_id"] for a in available]
                return {
                    "status": "error",
                    "error": f"Agent '{agent_id}' not found",
                    "available_agents": agent_list
                }
            
            success = manager.set_current_agent(agent_id)
            
            if success:
                info = manager.get_agent_info(agent_id)
                return {
                    "status": "success",
                    "message": f"Switched to agent '{agent_id}'",
                    "agent_info": {
                        "agent_id": info["agent_id"],
                        "model": info["model"],
                        "provider": info["provider"],
                        "conversation_length": info["memory_length"]
                    }
                }
            else:
                return {
                    "status": "error",
                    "error": "Failed to switch agent"
                }
        
        except Exception as e:
            logger.error(f"Error switching agent: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


class ListAgentsTool(BaseTool):
    """
    Lists all registered agent instances.
    """
    name: str = "list_agents"
    description: str = "Lists all registered agent instances with their configurations."

    def execute(self, **kwargs: Any) -> Any:
        """List all agents."""
        try:
            manager = get_agent_manager()
            agents = manager.list_agents()
            
            return {
                "status": "success",
                "total_agents": len(agents),
                "current_agent": manager.get_current_agent_id(),
                "agents": [
                    {
                        "agent_id": agent["agent_id"],
                        "model": agent["model"],
                        "provider": agent["provider"],
                        "conversation_length": agent["memory_length"],
                        "is_current": agent["is_current"]
                    }
                    for agent in agents
                ]
            }
        
        except Exception as e:
            logger.error(f"Error listing agents: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


class UpdateAgentConfigTool(BaseTool):
    """
    Updates agent configuration parameters like temperature, max_steps, etc.
    """
    name: str = "update_agent_config"
    description: str = (
        "Updates the agent's configuration parameters such as temperature, max_steps, "
        "or system prompt while preserving memory and conversation history."
    )
    
    temperature: Optional[float] = Field(
        default=None,
        description="Temperature for response randomness (0.0-2.0)"
    )
    
    max_steps: Optional[int] = Field(
        default=None,
        description="Maximum number of reasoning steps"
    )
    
    system_prompt: Optional[str] = Field(
        default=None,
        description="New system prompt to set agent behavior"
    )
    
    model: Optional[str] = Field(
        default=None,
        description="Model to switch to"
    )
    
    agent_id: Optional[str] = Field(
        default=None,
        description="Specific agent ID to update (if None, updates current agent)"
    )

    def execute(self, **kwargs: Any) -> Any:
        """Execute configuration update."""
        try:
            manager = get_agent_manager()
            
            update_params = {}
            if kwargs.get("temperature") is not None:
                update_params["temperature"] = kwargs["temperature"]
            if kwargs.get("max_steps") is not None:
                update_params["max_steps"] = kwargs["max_steps"]
            if kwargs.get("system_prompt") is not None:
                update_params["system_prompt"] = kwargs["system_prompt"]
            if kwargs.get("model") is not None:
                update_params["model"] = kwargs["model"]
            
            if not update_params:
                return {
                    "status": "error",
                    "error": "No parameters provided for update"
                }
            
            agent_id = kwargs.get("agent_id", self.agent_id)
            
            updated_agent_id = manager.update_agent(
                agent_id=agent_id,
                **update_params
            )
            
            new_info = manager.get_agent_info(updated_agent_id)
            
            return {
                "status": "success",
                "message": "Agent configuration updated successfully",
                "agent_id": updated_agent_id,
                "updated_parameters": update_params,
                "current_config": {
                    "model": new_info["model"],
                    "temperature": new_info["temperature"],
                    "max_steps": new_info["max_steps"],
                    "system_prompt": new_info["system_prompt"]
                }
            }
        
        except Exception as e:
            logger.error(f"Error updating agent config: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
        
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return {
                "status": "error",
                "error": str(e)
            }