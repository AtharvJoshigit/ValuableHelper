from typing import List, Optional, Dict
from enum import Enum

from ..domain.task import Task, TaskPriority, TaskStatus


PRIORITY_WEIGHTS: Dict[TaskPriority, int] = {
    TaskPriority.CRITICAL: 0,
    TaskPriority.HIGH: 1,
    TaskPriority.MEDIUM: 2,
    TaskPriority.LOW: 3,
    TaskPriority.SCHEDULED: 4,
}

class PriorityQueue:
    def __init__(self, task_store):
        self.task_store = task_store

    def get_runnable_tasks(self) -> List[Task]:
        all_tasks = self.task_store.list_tasks()
        task_map = {task.id: task for task in all_tasks}

        todo_tasks = [task for task in all_tasks if task.status in [TaskStatus.TODO, TaskStatus.APPROVED]]

        runnable_tasks = []
        for task in todo_tasks:
            if not task.dependencies:
                runnable_tasks.append(task)
                continue

            dependencies_satisfied = True
            for dep_id in task.dependencies:
                if dep_id not in task_map or task_map[dep_id].status != TaskStatus.DONE:
                    dependencies_satisfied = False
                    break
            
            if dependencies_satisfied:
                runnable_tasks.append(task)

        runnable_tasks.sort(key=lambda t: (PRIORITY_WEIGHTS[t.priority], t.created_at))

        return runnable_tasks

    def get_next_task(self) -> Optional[Task]:
        runnable_tasks = self.get_runnable_tasks()
        return runnable_tasks[0] if runnable_tasks else None
