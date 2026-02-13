from agents.agent_id import AGENT_ID
from engine.providers.base_provider import BaseProvider
from engine.providers.google.provider import GoogleProvider
from engine.registry.library.filesystem_tools import ListDirectoryTool, ReadFileTool
from infrastructure.singleton import Singleton
from .base_agent import BaseAgent
from .coder_agent import CoderAgent
from .system_operator_agent import SystemOperatorAgent
from engine.registry.agent_wrapper import AgentWrapper
from tools.task_store_tool import AddTaskDependencyTool, AddTaskTool, DeleteTaskTool, GetTaskTool, ListSubtasksTool, ListTasksTool, RemoveTaskDependencyTool, UpdateTaskStatusTool, UpdateTaskTool
from services.task_store import TaskStore
from engine.registry.tool_registry import ToolRegistry

class PlanManagerAgent(BaseAgent):
    def __init__(self, config: dict = None):
        default_config = {
            "model_id": "gemini-2.5-pro",
            "provider": "google",
            "max_steps": 25,
            "temperature": 0.3,
            "sensitive_tool_names": {}
        }
        if config:
            default_config.update(config)
        super().__init__(default_config)
        self.task_store = Singleton.get_task_store()

    def _get_provider(self) -> BaseProvider:
        # Using a high-performance model for coding tasks
        return GoogleProvider(model_id="gemini-3-flash-preview")
        
    def _get_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        
        registry.register(ListDirectoryTool())
        registry.register(ReadFileTool())
        # 1. The Core Memory: Task Store
        # We pass the shared store instance so everyone sees the same tasks
        registry.register(AddTaskTool())
        registry.register(UpdateTaskStatusTool())
        registry.register(ListTasksTool())
        registry.register(AddTaskDependencyTool())
        registry.register(RemoveTaskDependencyTool())
        registry.register(UpdateTaskTool())
        registry.register(DeleteTaskTool())
        registry.register(ListSubtasksTool())
        registry.register(GetTaskTool())

    
        return registry

    def start(self):
        return self.create(
            system_prompt_file=["my_agents/plan_manager_prompt.md", "tools_call.md"],
            agent_id=AGENT_ID.FIXED_PLANER_AGENT.value,
            set_as_current=False
        )