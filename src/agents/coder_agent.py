from engine.providers.base_provider import BaseProvider
from engine.providers.google.provider import GoogleProvider
from engine.registry.tool_registry import ToolRegistry
from engine.registry.library.filesystem_tools import ListDirectoryTool, ReadFileTool, CreateFileTool, SearchAndReplaceTool
from engine.registry.library.system_tools import RunCommandTool
from engine.registry.agent_wrapper import AgentWrapper
from .base_agent import BaseAgent
from .system_operator_agent import SystemOperatorAgent

class CoderAgent(BaseAgent):
    """
    A specialized agent for writing high-quality, efficient, and well-documented code.
    """
    def _get_provider(self) -> BaseProvider:
        # Using a high-performance model for coding tasks
        return GoogleProvider(model_id="gemini-2.5-pro")
        
    def _get_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        
        # Direct Filesystem Access for the Coder
        registry.register(ListDirectoryTool())
        registry.register(ReadFileTool())
        registry.register(CreateFileTool())
        registry.register(SearchAndReplaceTool())
        registry.register(RunCommandTool()) # Added for running tests/checks
        
        # Integration with System Operator for more complex tasks
        operator_agent = SystemOperatorAgent().start()
        registry.register(AgentWrapper(
            agent=operator_agent,
            name="system_operator",
            description="Delegate complex file operations, directory structure creation, or multi-step shell commands to this specialist."
        ))

        return registry

    def start(self):
        """Initializes the agent with its specialized system prompt."""
        return self.create(system_prompt_file=["my_agents/coder_agent.md", "tools_call.md"])