import asyncio
from src.services.task_store import TaskStore
from src.domain.task import TaskStatus, TaskPriority
from src.domain.event import EventType

async def test_task_store_new_methods():
    store = TaskStore()
    
    # Setup: Create tasks
    task1 = await store.add_task(title="Task 1", dependencies=[])
    task2 = await store.add_task(title="Task 2", dependencies=[task1.id])
    
    # 1. Test get_subtasks
    task3 = await store.add_task(title="Subtask", parent_id=task1.id)
    subtasks = store.get_subtasks(task1.id)
    assert len(subtasks) == 1
    assert subtasks[0].id == task3.id
    print("✓ get_subtasks passed")

    # 2. Test update_task
    updates = {
        "title": "Updated Task 1",
        "status": "in_progress",
        "priority": "high",
        "description": "New description",
        "parent_id": "some_parent"
    }
    updated_task = await store.update_task(task1.id, updates)
    assert updated_task.title == "Updated Task 1"
    assert updated_task.status == TaskStatus.IN_PROGRESS
    assert updated_task.priority == TaskPriority.HIGH
    assert updated_task.description == "New description"
    assert updated_task.parent_id == "some_parent"
    assert updated_task.updated_at > task1.created_at
    print("✓ update_task basic fields passed")

    # Test status change events
    await store.update_task(task1.id, {"status": "done"})
    assert updated_task.status == TaskStatus.DONE
    assert updated_task.completed_at is not None
    print("✓ update_task status DONE passed")

    # 3. Test delete_task
    # Before deletion, task2 depends on task1
    assert task1.id in store.get_task(task2.id).dependencies
    
    deleted = await store.delete_task(task1.id)
    assert deleted is True
    assert store.get_task(task1.id) is None
    
    # Check if dependency was removed from task2
    assert task1.id not in store.get_task(task2.id).dependencies
    print("✓ delete_task passed")

if __name__ == "__main__":
    asyncio.run(test_task_store_new_methods())
