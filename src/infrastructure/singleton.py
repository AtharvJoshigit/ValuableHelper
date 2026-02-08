from src.services.task_store import TaskStore

class Singleton:
    _task_store = None

    @classmethod
    def get_task_store(cls) -> TaskStore:
        if cls._task_store is None:
            cls._task_store = TaskStore()
        return cls._task_store