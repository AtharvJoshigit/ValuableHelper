from typing import List, Optional, Dict, Set
from src.domain.task import Task, TaskPriority, TaskStatus

# Weights: Lower is more important
PRIORITY_WEIGHTS: Dict[TaskPriority, int] = {
    TaskPriority.CRITICAL: 0,
    TaskPriority.HIGH: 1,
    TaskPriority.MEDIUM: 2,
    TaskPriority.LOW: 3,
    TaskPriority.SCHEDULED: 4,
}

class PriorityQueue:
    """
    High-performance task scheduler.
    Optimized to only load active contexts rather than the entire history.
    """
    def __init__(self, task_store):
        self.task_store = task_store

    def _get_active_set(self) -> List[Task]:
        """
        Fetches only relevant tasks to reduce DB load.
        We need: TODO, APPROVED (to run), and IN_PROGRESS/WAITING (to check parents).
        """
        # In a real DB, this would be a filtered query. 
        # For the JSON store, we optimize by filtering in memory but only processing the result once.
        all_tasks = self.task_store.list_tasks()
        return [
            t for t in all_tasks 
            if t.status in {
                TaskStatus.TODO, 
                TaskStatus.APPROVED, 
                TaskStatus.IN_PROGRESS, 
                TaskStatus.WAITING_APPROVAL
            }
        ]

    def get_runnable_tasks(self) -> List[Task]:
        """
        Returns tasks ready for execution, sorted by effective priority.
        """
        all_tasks = self.task_store.list_tasks() # We still need full list for dependencies (completed tasks)
        task_map = {t.id: t for t in all_tasks}
        
        # We only care about running tasks that are TODO or APPROVED
        candidates = [t for t in all_tasks if t.status in {TaskStatus.TODO, TaskStatus.APPROVED}]
        
        runnable = []
        for task in candidates:
            # 1. Container Check: If it has children, it's a manager, not a worker.
            # (Assuming parent_id relationship is enough, but strictly we check if it IS a parent)
            # For now, we assume if it's a leaf node it's runnable. 
            # Ideally, we check if `task.id` is in anyone's `parent_id`. 
            # Optimized approach: The Planner Agent should mark containers as "WAITING" not "TODO".
            # So if it is TODO, we assume it is runnable.

            # 2. Parent Status Check
            if task.parent_id:
                parent = task_map.get(task.parent_id)
                # Parent must be Active (IN_PROGRESS) or Approved to allow children to run
                if parent and parent.status not in {TaskStatus.IN_PROGRESS, TaskStatus.APPROVED, TaskStatus.WAITING_REVIEW}:
                    continue

            # 3. Dependency Check
            if task.dependencies:
                deps_met = True
                for dep_id in task.dependencies:
                    dep = task_map.get(dep_id)
                    if not dep or dep.status != TaskStatus.DONE:
                        deps_met = False
                        break
                if not deps_met:
                    continue

            runnable.append(task)

        # Sort Logic:
        # 1. Priority (Critical first)
        # 2. Age (Older first - prevent starvation)
        runnable.sort(key=lambda t: (
            PRIORITY_WEIGHTS.get(t.priority, 99),
            t.created_at
        ))

        return runnable

    def get_next_task(self) -> Optional[Task]:
        queue = self.get_runnable_tasks()
        return queue[0] if queue else None
