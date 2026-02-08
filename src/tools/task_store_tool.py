from typing import List, Optional, Any
from pydantic import Field, PrivateAttr
from engine.registry.base_tool import BaseTool
from src.services.task_store import TaskStore
from src.domain.task import TaskStatus, TaskPriority

class AddTaskTool(BaseTool):
    """
    Tool to create a new task in the TaskStore.
    """
    name: str = "add_task"
    description: str = "Create a new task with a title, optional description, priority, and dependencies."
    
    title: Optional[str] = Field("ignore?", description="The title of the task")
    description_text: Optional[str] = Field(None, alias="description", description="Detailed description of the task")
    priority: str = Field("medium", description="Task priority: low, medium, high, critical")
    dependencies: List[str] = Field(default_factory=list, description="List of dependency task IDs")
    parent_id: Optional[str] = Field(None, description="Parent task ID if this is a subtask")

    _store: TaskStore = PrivateAttr()

    def __init__(self, store: TaskStore, **data):
        super().__init__(**data)
        self._store = store

    async def execute(self, **kwargs) -> Any:
        title = kwargs.get("title")
        description = kwargs.get("description") # Alias maps to this key
        priority = kwargs.get("priority", "medium")
        dependencies = kwargs.get("dependencies", [])
        parent_id = kwargs.get("parent_id")

        if not title:
            return "❌ Error: 'title' is required for add_task"
        
        try:
            task = await self._store.add_task(title, description, priority, dependencies, parent_id)
            return f"✅ Task Created: {task.title} (ID: {task.id})"
        except Exception as e:
            return f"❌ Error: {e}"


class ListTasksTool(BaseTool):
    """
    Tool to list tasks, optionally filtering by status or priority.
    """
    name: str = "list_tasks"
    description: str = "List existing tasks. Can filter by status (todo, in_progress, done, blocked) or priority."
    
    status: Optional[str] = Field(None, description="Filter by status: todo, in_progress, done, blocked")
    priority: Optional[str] = Field(None, description="Filter by priority: low, medium, high, critical")

    _store: TaskStore = PrivateAttr()

    def __init__(self, store: TaskStore, **data):
        super().__init__(**data)
        self._store = store

    async def execute(self, **kwargs) -> Any:
        status = kwargs.get("status")
        priority = kwargs.get("priority")

        try:
            s_enum = TaskStatus(status) if status else None
            p_enum = TaskPriority(priority) if priority else None
            
            tasks = self._store.list_tasks(status=s_enum, priority=p_enum)
            
            if not tasks:
                return "No tasks found."
            
            output = "📋 **Task List**"
            for t in tasks:
                output += f"\n- {t.title} [{t.status.value}] (ID: {t.id})"
            return output
        except ValueError as e:
            return f"❌ Error: {e}"


class GetTaskTool(BaseTool):
    """
    Tool to retrieve a specific task by its ID.
    """
    name: str = "get_task"
    description: str = "Retrieve details of a specific task by its ID."
    
    task_id: Optional[str] = Field("ignore", description="The ID of the task to retrieve")

    _store: TaskStore = PrivateAttr()

    def __init__(self, store: TaskStore, **data):
        super().__init__(**data)
        self._store = store

    async def execute(self, **kwargs) -> Any:
        task_id = kwargs.get("task_id")

        if not task_id:
            return "❌ Error: 'task_id' is required for get_task"
        
        try:
            task = self._store.get_task(task_id)
            if task:
                dependencies_str = ", ".join(task.dependencies) if task.dependencies else "None"
                return (
                    f"📝 **Task Details: {task.title}** (ID: {task.id})\n"
                    f"  Status: {task.status.value}\n"
                    f"  Priority: {task.priority.value}\n"
                    f"  Description: {task.description or 'N/A'}\n"
                    f"  Dependencies: {dependencies_str}"
                )
            else:
                return f"❌ Task with ID '{task_id}' not found."
        except Exception as e:
            return f"❌ Error: {e}"


class UpdateTaskStatusTool(BaseTool):
    """
    Tool to update the status of a specific task.
    """
    name: str = "update_task_status"
    description: str = "Update the status of an existing task (e.g., move to 'in_progress' or 'done')."
    
    task_id: Optional[str] = Field("ignore", description="The ID of the task to update")
    status: Optional[str] = Field('igore', description="New status: todo, in_progress, done, blocked")

    _store: TaskStore = PrivateAttr()

    def __init__(self, store: TaskStore, **data):
        super().__init__(**data)
        self._store = store

    async def execute(self, **kwargs) -> Any:
        task_id = kwargs.get("task_id")
        status = kwargs.get("status")

        if not task_id or not status:
            return "❌ Error: 'task_id' and 'status' required"

        try:
            s_enum = TaskStatus(status)
            task = await self._store.update_status(task_id, s_enum)
            return f"🔄 Updated: {task.title} -> {task.status.value}" if task else "❌ Task not found"
        except ValueError:
            return f"❌ Invalid status: {status}"


class AddTaskDependencyTool(BaseTool):
    """
    Tool to add a dependency relationship between two tasks.
    """
    name: str = "add_task_dependency"
    description: str = "Mark a task as dependent on another task."
    
    task_id: Optional[str] = Field("ignore", description="The ID of the task that is blocked")
    dependency_id: Optional[str] = Field("ignore", description="The ID of the task that must be completed first")

    _store: TaskStore = PrivateAttr()

    def __init__(self, store: TaskStore, **data):
        super().__init__(**data)
        self._store = store

    async def execute(self, **kwargs) -> Any:
        task_id = kwargs.get("task_id")
        dependency_id = kwargs.get("dependency_id")

        if not task_id or not dependency_id:
            return "❌ Error: 'task_id' and 'dependency_id' required"

        res = await self._store.add_dependency(task_id, dependency_id)
        return f"🔗 Dependency added" if res else "❌ Failed to add dependency"


class RemoveTaskDependencyTool(BaseTool):
    """
    Tool to remove a dependency relationship between two tasks.
    """
    name: str = "remove_task_dependency"
    description: str = "Remove a dependency requirement from a task."
    
    task_id: Optional[str] = Field("ignore", description="The ID of the task to unblock")
    dependency_id: Optional[str] = Field("ignore", description="The ID of the dependency to remove")

    _store: TaskStore = PrivateAttr()

    def __init__(self, store: TaskStore, **data):
        super().__init__(**data)
        self._store = store

    async def execute(self, **kwargs) -> Any:
        task_id = kwargs.get("task_id")
        dependency_id = kwargs.get("dependency_id")

        if not task_id or not dependency_id:
            return "❌ Error: 'task_id' and 'dependency_id' required"

        res = await self._store.remove_dependency(task_id, dependency_id)
        return f"🔓 Dependency removed" if res else "❌ Failed to remove dependency"
