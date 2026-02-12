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
    """
    Manages task scheduling based on priority and dependencies.
    Enforces the rule: "Container tasks (with subtasks) are not runnable; only leaves are."
    """
    def __init__(self, task_store):
        self.task_store = task_store

    def _get_effective_priority_weight(self, task: Task, task_map: Dict[str, Task]) -> int:
        """
        Calculates the effective priority weight by traversing the parent chain.
        The effective priority is the highest priority (lowest weight) found in the chain.
        """
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
        Returns a list of tasks that are ready to run.
        
        Criteria:
        1. Status is TODO or APPROVED.
        2. Task is NOT a container (has no children).
        3. All dependencies are DONE.
        4. If it has a parent, the parent must NOT be WAITING_APPROVAL or TODO (unless the subtask itself is what's being approved).
           Actually, the simplest rule: A subtask can only run if its parent is IN_PROGRESS or APPROVED.
        """
        all_tasks = self.task_store.list_tasks()
        task_map = {task.id: task for task in all_tasks}

        # Identification of parent tasks (containers)
        parent_ids = set()
        for task in all_tasks:
            if task.parent_id:
                parent_ids.add(task.parent_id)

        # Candidates for execution
        candidates = [
            t for t in all_tasks 
            if t.status in [TaskStatus.TODO, TaskStatus.APPROVED]
        ]

        runnable_tasks = []
        for task in candidates:
            # Rule: If a task has children, it's a manager/container. 
            if task.id in parent_ids:
                continue

            # Rule: If it has a parent, the parent must be in a state that allows execution.
            if task.parent_id:
                parent = task_map.get(task.parent_id)
                if parent and parent.status in [TaskStatus.WAITING_APPROVAL, TaskStatus.TODO, TaskStatus.PAUSED]:
                    # Parent is not ready yet
                    continue

            # Rule: Dependencies must be satisfied
            if task.dependencies:
                dependencies_satisfied = True
                for dep_id in task.dependencies:
                    if dep_id not in task_map:
                        dependencies_satisfied = False
                        break
                    if task_map[dep_id].status != TaskStatus.DONE:
                        dependencies_satisfied = False
                        break
                
                if not dependencies_satisfied:
                    continue

            runnable_tasks.append(task)

        # Sort by effective priority (CRITICAL first), then creation time (FIFO)
        runnable_tasks.sort(key=lambda t: (
            self._get_effective_priority_weight(t, task_map),
            t.created_at
        ))

        return runnable_tasks

    def get_next_task(self) -> Optional[Task]:
        runnable_tasks = self.get_runnable_tasks()
        return runnable_tasks[0] if runnable_tasks else None
