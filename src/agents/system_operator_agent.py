from pydantic import config
from engine.providers.base_provider import BaseProvider
from engine.providers.google.provider import GoogleProvider
from engine.registry.library.request_tools import RequestApprovalTool
from engine.registry.tool_registry import ToolRegistry
from engine.registry.library.filesystem_tools import ListDirectoryTool, ReadFileTool, CreateFileTool
from engine.registry.library.system_tools import RunCommandTool
from .base_agent import BaseAgent

class SystemOperatorAgent(BaseAgent):
    """
    A specialized agent for system operations, file management, and command execution.
    """
    def _get_provider(self) -> BaseProvider:
        return GoogleProvider(model_id="gemini-2.5-flash")
        
    def _get_registry(self) -> ToolRegistry:
        registry = ToolRegistry()

        # Register Filesystem Tools
        registry.register(ListDirectoryTool())
        registry.register(ReadFileTool())
        registry.register(CreateFileTool(file_path='.', content='..'))

        # Register System/Command Tools
        registry.register(RunCommandTool(command='ls'))

        #Approval tool 
        # registry.register(RequestApprovalTool(action_type="create_file", action_details={"summery": "Initializing the object"}))

        return registry

    def start(self):
        """Initializes the agent with its specialized system prompt."""
        return self.create(system_prompt_file=["my_agents/system_operator_agent.md", "tools_call.md"])