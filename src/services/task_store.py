from typing import List, Optional
from src.domain.task import Task, TaskStatus, TaskPriority
from src.domain.event import Event, EventType
from src.infrastructure.event_bus import EventBus
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TaskStore:
    """
    Manages the storage and retrieval of tasks, ensuring data integrity
    and publishing events on state changes.
    """
    def __init__(self):
        self._tasks: List[Task] = []
        self._event_bus = EventBus()

    async def add_task(self, title: str, description: Optional[str] = None, 
                       priority: str = "medium", dependencies: Optional[List[str]] = None,
                       parent_id: Optional[str] = None) -> Task:
        """
        Adds a new task to the store.
        """
        try:
            task_priority = TaskPriority(priority)
        except ValueError:
            task_priority = TaskPriority.MEDIUM
            logger.warning(f"Invalid priority '{priority}' provided. Defaulting to MEDIUM.")

        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            priority=task_priority,
            dependencies=dependencies if dependencies is not None else [],
            parent_id=parent_id
        )
        self._tasks.append(task)
        logger.info(f"Task added: {task.title} (ID: {task.id})")
        self._event_bus.publish(Event(type=EventType.TASK_CREATED, payload=task.dict()))
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Retrieves a task by its ID.
        """
        return next((task for task in self._tasks if task.id == task_id), None)

    def list_tasks(self, status: Optional[TaskStatus] = None, priority: Optional[TaskPriority] = None) -> List[Task]:
        """
        Lists all tasks, optionally filtered by status and/or priority.
        """
        tasks = self._tasks
        if status:
            tasks = [t for t in tasks if t.status == status]
        if priority:
            tasks = [t for t in tasks if t.priority == priority]
        return list(tasks) # Return a copy

    async def update_status(self, task_id: str, new_status: TaskStatus) -> Optional[Task]:
        """
        Updates the status of a specific task.
        """
        task = self.get_task(task_id)
        if task:
            old_status = task.status
            task.status = new_status
            task.updated_at = datetime.now()
            
            logger.info(f"Task {task.id} status updated from {old_status} to {new_status}")
            self._event_bus.publish(Event(
                type=EventType.TASK_STATUS_CHANGED,
                payload={"task_id": task.id, "old_status": old_status.value, "new_status": new_status.value}
            ))
            
            if new_status == TaskStatus.DONE:
                self._event_bus.publish(Event(type=EventType.TASK_COMPLETED, payload=task.dict()))
            elif new_status == TaskStatus.FAILED:
                self._event_bus.publish(Event(type=EventType.TASK_FAILED, payload=task.dict()))
                
            return task
        return None

    async def update_task_description(self, task_id: str, new_description: str) -> Optional[Task]:
        task = self.get_task(task_id)
        if task:
            task.description = new_description
            task.updated_at = datetime.now()
            logger.info(f"Task {task.id} description updated.")
            self._event_bus.publish(Event(
                type=EventType.TASK_UPDATED,
                payload={"task_id": task.id, "field": "description", "new_value": new_description}
            ))
            return task
        return None

    async def update_task_priority(self, task_id: str, new_priority: TaskPriority) -> Optional[Task]:
        task = self.get_task(task_id)
        if task:
            task.priority = new_priority
            task.updated_at = datetime.now()
            logger.info(f"Task {task.id} priority updated to {new_priority.value}.")
            self._event_bus.publish(Event(
                type=EventType.TASK_UPDATED,
                payload={"task_id": task.id, "field": "priority", "new_value": new_priority.value}
            ))
            return task
        return None

    def get_dependencies(self, task_id: str) -> List[Task]:
        task = self.get_task(task_id)
        if not task or not task.dependencies:
            return []
        deps = []
        for dep_id in task.dependencies:
            t = self.get_task(dep_id)
            if t:
                deps.append(t)
        return deps

    def get_dependents(self, task_id: str) -> List[Task]:
        return [task for task in self._tasks if task_id in task.dependencies]

    async def add_dependency(self, task_id: str, dependency_id: str) -> Optional[Task]:
        task = self.get_task(task_id)
        if task and dependency_id not in task.dependencies:
            task.dependencies.append(dependency_id)
            task.updated_at = datetime.now()
            logger.info(f"Task {task.id} now depends on {dependency_id}.")
            self._event_bus.publish(Event(
                type=EventType.TASK_UPDATED,
                payload={"task_id": task.id, "field": "dependencies", "action": "added", "dependency_id": dependency_id}
            ))
            return task
        return None

    async def remove_dependency(self, task_id: str, dependency_id: str) -> Optional[Task]:
        task = self.get_task(task_id)
        if task and dependency_id in task.dependencies:
            task.dependencies.remove(dependency_id)
            task.updated_at = datetime.now()
            logger.info(f"Task {task.id} no longer depends on {dependency_id}.")
            self._event_bus.publish(Event(
                type=EventType.TASK_UPDATED,
                payload={"task_id": task.id, "field": "dependencies", "action": "removed", "dependency_id": dependency_id}
            ))
            return task
        return None