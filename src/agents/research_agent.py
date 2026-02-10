from .base_agent import BaseAgent
from src.tools.web_search_tool import WebSearchTool
from engine.registry.library.filesystem_tools import ReadFileTool, CreateFileTool, ListDirectoryTool
from engine.registry.tool_registry import ToolRegistry

class ResearchAgent(BaseAgent):
    def _get_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(WebSearchTool())
        registry.register(ReadFileTool())
        registry.register(CreateFileTool())
        registry.register(ListDirectoryTool())
        return registry

    def start(self):
        return self.create(system_prompt_file=["my_agents/research_agent.md", "tools_call.md"])
