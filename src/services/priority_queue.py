from typing import List, Optional, Dict, Set
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

    def _get_effective_priority_weight(self, task: Task, task_map: Dict[str, Task]) -> int:
        """
        Calculates the effective priority weight by traversing the parent chain.
        The effective priority is the highest priority (lowest weight) found in the chain.
        """
        # Default to lowest priority (highest weight) if unknown
        min_weight = PRIORITY_WEIGHTS.get(task.priority, 999)
        
        current_task = task
        visited: Set[str] = set()
        
        while current_task.parent_id:
            if current_task.id in visited:
                break # Cycle detected
            visited.add(current_task.id)
            
            parent = task_map.get(current_task.parent_id)
            if not parent:
                break
                
            parent_weight = PRIORITY_WEIGHTS.get(parent.priority, 999)
            if parent_weight < min_weight:
                min_weight = parent_weight
            
            current_task = parent
            
        return min_weight

    def get_runnable_tasks(self) -> List[Task]:
        """
        Returns a list of tasks that are ready to run (TODO/APPROVED and dependencies met),
        sorted by effective priority (inheriting from parents) and then creation time.
        """
        all_tasks = self.task_store.list_tasks()
        task_map = {task.id: task for task in all_tasks}

        todo_tasks = [task for task in all_tasks if task.status in [TaskStatus.TODO, TaskStatus.APPROVED]]

        runnable_tasks = []
        for task in todo_tasks:
            # Check dependencies
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

        # Sort by effective priority, then creation time
        runnable_tasks.sort(key=lambda t: (
            self._get_effective_priority_weight(t, task_map),
            t.created_at
        ))

        return runnable_tasks

    def get_next_task(self) -> Optional[Task]:
        runnable_tasks = self.get_runnable_tasks()
        return runnable_tasks[0] if runnable_tasks else None
