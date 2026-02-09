from engine.providers.base_provider import BaseProvider
from engine.providers.google.provider import GoogleProvider
from engine.registry.library.filesystem_tools import ListDirectoryTool, ReadFileTool
from .base_agent import BaseAgent
from .coder_agent import CoderAgent
from .system_operator_agent import SystemOperatorAgent
from engine.registry.agent_wrapper import AgentWrapper
from tools.task_store_tool import AddTaskDependencyTool, AddTaskTool, DeleteTaskTool, GetTaskTool, ListSubtasksTool, ListTasksTool, RemoveTaskDependencyTool, UpdateTaskStatusTool, UpdateTaskTool
from services.task_store import TaskStore
from engine.registry.tool_registry import ToolRegistry

class PlanManagerAgent(BaseAgent):
    def __init__(self, task_store: TaskStore, config: dict = None):
        super().__init__(config)
        self.task_store = task_store

    def _get_provider(self) -> BaseProvider:
        # Using a high-performance model for coding tasks
        return GoogleProvider(model_id="gemini-2.5-pro")
        
    def _get_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        
        registry.register(ListDirectoryTool())
        registry.register(ReadFileTool())
        # 1. The Core Memory: Task Store
        # We pass the shared store instance so everyone sees the same tasks
        registry.register(AddTaskTool(self.task_store))
        registry.register(UpdateTaskStatusTool(self.task_store))
        registry.register(ListTasksTool(self.task_store))
        registry.register(AddTaskDependencyTool(self.task_store))
        registry.register(RemoveTaskDependencyTool(self.task_store))
        registry.register(UpdateTaskTool(self.task_store))
        registry.register(DeleteTaskTool(self.task_store))
        registry.register(ListSubtasksTool(self.task_store))
        registry.register(GetTaskTool(self.task_store))

        
        # 2. The Hands: System Operator
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

    def start(self):
        return self.create(
            system_prompt_file="my_agents/plan_manager_prompt.md",
        )