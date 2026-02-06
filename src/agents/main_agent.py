from agents.system_operator_agent import SystemOperatorAgent
from engine.core.agent import Agent
from engine.registry.library.filesystem_tools import ListDirectoryTool, ReadFileTool
from engine.registry.tool_registry import ToolRegistry
from .base_agent import BaseAgent
from engine.registry.agent_wrapper import AgentWrapper

class MainAgent(BaseAgent):
    
    def _get_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(ListDirectoryTool())
        registry.register(ReadFileTool())
        
        operator_agent = SystemOperatorAgent().start()
        registry.register(AgentWrapper(
            agent=operator_agent,
            name="system_operator",
            description="Use this tool for file operations (create/list/read) or to run shell commands.",
            stream=True
        ))

        return registry


    def start(self) -> Agent:
        # We tell it which markdown file to use for its personality
        return self.create(system_prompt_file="whoami.md")

def create_main_agent() -> Agent:
    return MainAgent({'model_id': 'gemini-3-flash-preview'}).start()