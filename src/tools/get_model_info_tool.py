from typing import Type, Any, Dict
from pydantic import BaseModel, Field
from engine.registry.base_tool import BaseTool
from app.app_context import get_app_context

class GetModelInfoInput(BaseModel):
    pass

class GetModelInfoTool(BaseTool):
    name = "get_model_info"
    description = "Returns information about the currently active AI model and agent configuration."
    args_schema: Type[BaseModel] = GetModelInfoInput

    async def _run(self, **kwargs: Any) -> Dict[str, Any]:
        # In a real app, we might fetch this from the Agent instance or Config
        # For now, we'll return static info or fetch from context if available
        
        # This is a placeholder as the Agent instance isn't easily accessible globally 
        # without a proper context provider for the *current* agent.
        # However, we can return the default config.
        
        return {
            "model": "gemini-2.5-flash", # Hardcoded based on provider.py default
            "provider": "google",
            "capabilities": ["tool_use", "structured_output", "thinking_stripping_fix_applied"],
            "note": "Thoughts are now stripped from Telegram output."
        }
