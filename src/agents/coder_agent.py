from agents.agent_id import AGENT_ID
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
    
    def __init__(self, config: dict = None):
        default_config = {
            "model_id": "gemini-3-flash-prevew",
            "provider": "google",
            "max_steps": 25,
            "temperature": 0.3,
            "sensitive_tool_names": {}
        }
        if config:
            default_config.update(config)
        super().__init__(default_config)
    
    def _get_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        
        # Direct Filesystem Access for the Coder
        registry.register(ListDirectoryTool())
        registry.register(ReadFileTool())
        registry.register(CreateFileTool())
        registry.register(SearchAndReplaceTool())
        registry.register(RunCommandTool()) # Added for running tests/checks
        

        return registry

    def start(self):
        """Initializes the agent with its specialized system prompt."""
        return self.create(
            system_prompt_file=["my_agents/coder_agent.md", "tools_call.md"],
            agent_id=AGENT_ID.FIXED_CODER_AGENT.value,
            set_as_current=False
        )