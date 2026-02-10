# file: switch_model_tool.py

from typing import Any, Optional
from engine.core.agent_instance_manager import get_agent_manager
from engine.providers.google.models import GeminiModel
from pydantic import Field
from engine.registry.base_tool import BaseTool
import logging

logger = logging.getLogger(__name__)


class SwitchModelTool(BaseTool):
    """
    Switches the current agent to a different model while preserving conversation memory.
    """
    name: str = "switch_model"
    description: str = (
        "Switches the AI model being used while preserving the conversation history. "
        "Use this when you need different model capabilities (e.g., faster responses, "
        "better reasoning, vision support). Available models: gemini-3-pro-preview, "
        "gemini-3-flash-preview, gemini-2.5-pro, gemini-2.5-flash, gemini-2.0-flash, etc."
    )
    
    model: str = Field(
        description=(
            "The model to switch to. Choose from: "
            "gemini-3-pro-preview (latest, most capable), "
            "gemini-3-flash-preview (fast, experimental), "
            "gemini-2.5-pro (stable, high quality), "
            "gemini-2.5-flash (balanced speed/quality), "
            "gemini-2.0-flash (fast responses), "
            "gemini-1.5-pro (long context support)"
        )
    )
    
    preserve_memory: bool = Field(
        default=True,
        description="Whether to preserve conversation history when switching models"
    )
    
    agent_id: Optional[str] = Field(
        default=None,
        description="Specific agent ID to switch (if None, switches current agent)"
    )

    def execute(self, **kwargs: Any) -> Any:
        """
        Execute model switch.
        
        Args:
            **kwargs: Override parameters (model, preserve_memory, agent_id)
            
        Returns:
            Result dictionary with status and details
        """
        model = kwargs.get("model", self.model)
        preserve_memory = kwargs.get("preserve_memory", self.preserve_memory)
        agent_id = kwargs.get("agent_id", self.agent_id)
        
        try:
            if isinstance(model, str):
                try:
                    model_enum = GeminiModel(model)
                    model = model_enum.value
                except ValueError:
                    logger.warning(f"Model '{model}' not in GeminiModel enum, using as-is")
            
            manager = get_agent_manager()
            
            current_info = manager.get_agent_info(agent_id)
            if not current_info:
                return {
                    "status": "error",
                    "error": f"Agent '{agent_id or 'current'}' not found"
                }
            
            current_model = current_info["model"]
            
            if current_model == model:
                return {
                    "status": "success",
                    "message": f"Already using model '{model}'",
                    "model": model,
                    "agent_id": current_info["agent_id"]
                }
            
            updated_agent_id = manager.switch_model(
                new_model=model,
                agent_id=agent_id,
                preserve_memory=preserve_memory
            )
            
            new_info = manager.get_agent_info(updated_agent_id)
            
            memory_status = "preserved" if preserve_memory else "reset"
            
            return {
                "status": "success",
                "message": f"Successfully switched from '{current_model}' to '{model}'",
                "previous_model": current_model,
                "new_model": model,
                "memory_status": memory_status,
                "conversation_length": new_info["memory_length"],
                "agent_id": updated_agent_id
            }
        
        except Exception as e:
            logger.error(f"Error switching model: {e}")
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


class ListModelsTools(BaseTool):
    """Lists all available models that can be switched to."""
    name: str = "list_available_models"
    description: str = "Lists all available AI models that can be switched to."

    def execute(self, **kwargs: Any) -> Any:
        """List all available models."""
        models = []
        
        for model in GeminiModel:
            category = "Unknown"
            if "3-" in model.value:
                category = "Gemini 3 (Latest/Experimental)"
            elif "2.5-" in model.value:
                category = "Gemini 2.5 (Stable)"
            elif "2.0-" in model.value or "2-" in model.value:
                category = "Gemini 2.0 (Current)"
            elif "1.5-" in model.value:
                category = "Gemini 1.5 (Legacy)"
            
            models.append({
                "model": model.value,
                "category": category,
                "name": model.name
            })
        
        return {
            "status": "success",
            "total_models": len(models),
            "models": models
        }


class GetCurrentModelTool(BaseTool):
    """Gets information about the currently active model."""
    name: str = "get_current_model"
    description: str = "Gets information about the currently active AI model and conversation state."

    def execute(self, **kwargs: Any) -> Any:
        """Get current model information."""
        try:
            manager = get_agent_manager()
            info = manager.get_agent_info()
            
            if not info:
                return {
                    "status": "error",
                    "error": "No active agent found"
                }
            
            return {
                "status": "success",
                "current_model": info["model"],
                "provider": info["provider"],
                "agent_id": info["agent_id"],
                "temperature": info["temperature"],
                "max_steps": info["max_steps"],
                "conversation_length": info["memory_length"],
                "metadata": info["metadata"]
            }
        
        except Exception as e:
            logger.error(f"Error getting current model: {e}")
            return {
                "status": "error",
                "error": str(e)
            }