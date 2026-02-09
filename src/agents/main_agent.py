from turtle import update
from services.plan_director import PlanDirector
from .system_operator_agent import SystemOperatorAgent
from .coder_agent import CoderAgent
from engine.core.agent import Agent
from engine.registry.library.filesystem_tools import ListDirectoryTool, ReadFileTool
from engine.registry.library.telegram_tools import SendTelegramMessageTool
from tools.gmail_tool import GmailSearchTool, GmailReadTool, GmailSendTool
from tools.task_store_tool import AddTaskTool, DeleteTaskTool, GetTaskTool, ListSubtasksTool, ListTasksTool, UpdateTaskStatusTool, UpdateTaskTool
from src.infrastructure.singleton import Singleton
from engine.registry.tool_registry import ToolRegistry
from .base_agent import BaseAgent
from engine.registry.agent_wrapper import AgentWrapper

class MainAgent(BaseAgent):
    
    def _get_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        
        # --- Shared State ---
        # Use the singleton TaskStore so we share state with the PlanManager/Director
        task_store = Singleton.get_task_store()
        
        # --- Native Tools ---
        registry.register(ListDirectoryTool())
        registry.register(ReadFileTool())
        registry.register(SendTelegramMessageTool())
        registry.register(GmailSearchTool())
        registry.register(GmailReadTool())
        registry.register(GmailSendTool())
        
        # Register the TaskStoreTool
        # This is the PRIMARY way the Main Agent initiates complex work
        registry.register(AddTaskTool(task_store))
        registry.register(UpdateTaskStatusTool(task_store))
        registry.register(ListTasksTool(task_store))
        registry.register(ListSubtasksTool(task_store))
        registry.register(GetTaskTool(task_store))
        registry.register(DeleteTaskTool(task_store))
        registry.register(UpdateTaskTool(task_store))

        
        # --- Sub-Agents ---
        # Note: PlanManager is NOT here. We communicate via the TaskStore + Events.

        operator_agent = SystemOperatorAgent().start()
        registry.register(AgentWrapper(
            agent=operator_agent,
            name="system_operator",
            description="Delegate file operations and shell commands to this agent."
        ))

        # 3. The Brains: Coder Agent
        coder_agent = CoderAgent().start()
        registry.register(AgentWrapper(
            agent=coder_agent,
            name="coder_agent",
            description="Delegate code writing, refactoring, and testing to this agent."
        ))
        
        return registry


    def start(self) -> Agent:
        return self.create(system_prompt_file=["whoami.md", "user.md", "memory.md", "tools_call.md"])

def create_main_agent() -> Agent:
    #Initializing PlanDirector with Main Agent 
    PlanDirector().ensure_started()
    return MainAgent({
        'model_id': 'gemini-3-flash-preview', 
        'max_steps': 25,
        'sensitive_tool_names': {
            'gmail_send', 
        }
    }).start()