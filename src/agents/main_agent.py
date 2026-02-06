from .system_operator_agent import SystemOperatorAgent
from .coder_agent import CoderAgent
from engine.core.agent import Agent
from engine.registry.library.filesystem_tools import ListDirectoryTool, ReadFileTool
from engine.registry.library.telegram_tools import SendTelegramMessageTool
from engine.registry.tool_registry import ToolRegistry
from .base_agent import BaseAgent
from engine.registry.agent_wrapper import AgentWrapper

class MainAgent(BaseAgent):
    
    def _get_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(ListDirectoryTool())
        registry.register(ReadFileTool())
        registry.register(SendTelegramMessageTool())
        
        # System Operator for low-level file/shell ops
        operator_agent = SystemOperatorAgent().start()
        registry.register(AgentWrapper(
            agent=operator_agent,
            name="system_operator",
            description="Use this tool for file operations (create/list/read) or to run shell commands."
        ))

        # Coder Agent for high-level code generation and review
        coder_agent = CoderAgent().start()
        registry.register(AgentWrapper(
            agent=coder_agent,
            name="coder_agent",
            description="Use this tool for writing high-quality code, designing software architecture, or performing code reviews. Always prefer this over writing code yourself."
        ))

        return registry


    def start(self) -> Agent:
        # We tell it which markdown file to use for its personality
        return self.create(system_prompt_file="whoami.md")

def create_main_agent() -> Agent:
    return MainAgent({'model_id': 'gemini-2.5-pro', 'max_steps': 25}).start()