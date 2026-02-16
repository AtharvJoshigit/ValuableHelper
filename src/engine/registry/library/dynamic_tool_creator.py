import importlib.util
import os
import sys
from typing import Optional, Type
from engine.registry.base_tool import BaseTool
from engine.registry.tool_registry import ToolRegistry
from engine.core.agent_instance_manager import get_agent_manager

class DynamicToolCreatorTool(BaseTool):
    """
    A God-Mode tool that allows ValH to build and inject new tools into its own brain
    on the fly, without restarting the server.
    """
    
    def __init__(self):
        super().__init__(
            name="dynamic_tool_creator",
            description="Builds and injects a new tool into ValH's active registry."
        )

    async def execute(self, code: str, class_name: str, tool_name: str) -> str:
        try:
            # 1. Ensure the library directory exists
            lib_path = "src/engine/registry/library"
            if not os.path.exists(lib_path):
                os.makedirs(lib_path, exist_ok=True)

            # 2. Save the tool code to the library with UTF-8 encoding
            file_path = f"{lib_path}/{tool_name}_tool.py"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            
            # 3. Dynamically import the new tool
            spec = importlib.util.spec_from_file_location(tool_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[tool_name] = module
            spec.loader.exec_module(module)
            
            # 4. Get the tool class
            tool_class = getattr(module, class_name)
            new_tool_instance = tool_class()
            
            # 5. Inject into the ACTIVE Agent Manager
            manager = get_agent_manager()
            current_agent_id = manager.get_current_agent_id()
            if not current_agent_id:
                return "Error: No active agent found to inject into."
            
            registry = manager.get_registry(current_agent_id)
            registry.register(new_tool_instance)
            
            return f"Successfully injected {tool_name} into the active neural registry. ValH now has a new ability."

        except Exception as e:
            return f"Injection failed: {str(e)}"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The complete Python code for the new tool class."},
                "class_name": {"type": "string", "description": "The name of the class to instantiate."},
                "tool_name": {"type": "string", "description": "A unique name for the new ability."}
            },
            "required": ["code", "class_name", "tool_name"]
        }
