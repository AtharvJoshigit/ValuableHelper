import json
import os
import logging
import uuid
from typing import List, Optional
from datetime import datetime
from tempfile import NamedTemporaryFile

from app.app_context import get_app_context
from src.domain.task import Task, TaskStatus, TaskPriority
from src.domain.event import Event, EventType

logger = logging.getLogger(__name__)

class TaskStore:
    """
    Manages the storage and retrieval of tasks, ensuring data integrity,
    persisting to JSON, and publishing events on state changes.
    """
    def __init__(self, storage_path: str = "tasks.json"):
        self.storage_path = storage_path
        self._tasks: List[Task] = []
        self._event_bus = get_app_context().event_bus
        self._load()

    def _load(self):
        """Loads tasks from the JSON file without firing events."""
        if not os.path.exists(self.storage_path):
            logger.info(f"Storage file {self.storage_path} not found. Starting with empty store.")
            return

        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                self._tasks = [Task(**task_data) for task_data in data]
            logger.info(f"Loaded {len(self._tasks)} tasks from {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to load tasks from {self.storage_path}: {e}")
            self._tasks = []

    def _save(self):
        """Saves tasks to the JSON file using an atomic write pattern."""
        try:
            # model_dump() is the Pydantic v2 way. 
            # If v1, use .dict(). Based on src/domain/task.py using pydantic.BaseModel, 
            # we check for model_dump.
            tasks_data = [task.model_dump() for task in self._tasks]
            
            dir_name = os.path.dirname(os.path.abspath(self.storage_path))
            with NamedTemporaryFile('w', dir=dir_name, delete=False, suffix='.tmp') as tf:
                json.dump(tasks_data, tf, indent=2, default=str)
                temp_name = tf.name
            
            os.replace(temp_name, self.storage_path)
        except Exception as e:
            logger.error(f"Failed to save tasks to {self.storage_path}: {e}")
            if 'temp_name' in locals() and os.path.exists(temp_name):
                os.remove(temp_name)

    async def add_task(self, title: str, description: Optional[str] = None, 
                       priority: str = "medium", dependencies: Optional[List[str]] = None,
                       parent_id: Optional[str] = None) -> Task:
        """
        Adds a new task to the store and saves.
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
        
        self._save()
       
        self._event_bus.publish(Event(type=EventType.TASK_CREATED, payload=task.model_dump()))
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
        Updates the status of a specific task and saves.
        """
        task = self.get_task(task_id)
        if task:
            old_status = task.status
            task.status = new_status
            task.updated_at = datetime.now()
            
            logger.info(f"Task {task.title} status updated from {old_status.value} to {new_status.value}")
            
            self._save()
            
            self._event_bus.publish(Event(
                type=EventType.TASK_STATUS_CHANGED,
                payload={"task_id": task.id, "old_status": old_status.value, "new_status": new_status.value}
            ))
            
            if new_status == TaskStatus.DONE:
                self._event_bus.publish(Event(type=EventType.TASK_COMPLETED, payload=task.model_dump()))
            elif new_status == TaskStatus.FAILED:
                self._event_bus.publish(Event(type=EventType.TASK_FAILED, payload=task.model_dump()))
                
            return task
        return None

    async def update_task_description(self, task_id: str, new_description: str) -> Optional[Task]:
        task = self.get_task(task_id)
        if task:
            task.description = new_description
            task.updated_at = datetime.now()
            logger.info(f"Task {task.id} description updated.")
            
            self._save()
            
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
            
            self._save()
            
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
            
            self._save()
            
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
            
            self._save()
            
            self._event_bus.publish(Event(
                type=EventType.TASK_UPDATED,
                payload={"task_id": task.id, "field": "dependencies", "action": "removed", "dependency_id": dependency_id}
            ))
            return task
        return None

    async def delete_task(self, task_id: str) -> bool:
        """
        Removes a task, updates subtasks to clear their parent_id, 
        and removes references in other tasks' dependencies.
        """
        task = self.get_task(task_id)
        if not task:
            return False
        
        # Remove references from other tasks' dependencies and clear parent_id for subtasks
        for t in self._tasks:
            if task_id in t.dependencies:
                t.dependencies.remove(task_id)
            if t.parent_id == task_id:
                t.parent_id = None
                
        self._tasks.remove(task)
        logger.info(f"Task deleted: {task.id}")
        
        self._save()
        
        self._event_bus.publish(Event(type=EventType.TASK_DELETED, payload={"task_id": task_id}))
        return True

    def get_subtasks(self, parent_id: str) -> List[Task]:
        """
        Returns all tasks that have the given parent_id.
        """
        return [task for task in self._tasks if task.parent_id == parent_id]

    async def update_task(self, task_id: str, updates: dict) -> Optional[Task]:
        """
        Updates multiple fields of a task at once, saves, and publishes a single update event.
        """
        task = self.get_task(task_id)
        if not task:
            return None
        
        allowed_fields = {'title', 'description', 'priority', 'status', 'parent_id', 'assigned_to', 'result_summary', 'context'}
        changes = {}
        
        for field, value in updates.items():
            if field in allowed_fields:
                old_value = getattr(task, field)
                if old_value != value:
                    # Handle enum conversion
                    if field == 'priority' and isinstance(value, str):
                        try:
                            value = TaskPriority(value)
                        except ValueError:
                            logger.warning(f"Invalid priority '{value}' for task {task_id}. Skipping.")
                            continue
                    if field == 'status' and isinstance(value, str):
                        try:
                            value = TaskStatus(value)
                        except ValueError:
                            logger.warning(f"Invalid status '{value}' for task {task_id}. Skipping.")
                            continue
                    
                    setattr(task, field, value)
                    changes[field] = {"old": str(old_value), "new": str(value)}
        
        if changes:
            task.updated_at = datetime.now()
            logger.info(f"Task {task.id} updated: {list(changes.keys())}")
            
            self._save()
            
            self._event_bus.publish(Event(
                type=EventType.TASK_UPDATED,
                payload={"task_id": task.id, "changes": changes}
            ))
            
            # Specific events for status changes
            if 'status' in changes:
                if task.status == TaskStatus.DONE:
                    task.completed_at = datetime.now()
                    self._event_bus.publish(Event(type=EventType.TASK_COMPLETED, payload=task.model_dump()))
                elif task.status == TaskStatus.FAILED:
                    self._event_bus.publish(Event(type=EventType.TASK_FAILED, payload=task.model_dump()))
                    
        return task
