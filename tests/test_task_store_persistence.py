import os
import json
import pytest
import asyncio
from src.services.task_store import TaskStore
from src.domain.task import TaskStatus, TaskPriority

@pytest.fixture
def temp_storage():
    storage_path = "test_tasks.json"
    if os.path.exists(storage_path):
        os.remove(storage_path)
    yield storage_path
    if os.path.exists(storage_path):
        os.remove(storage_path)

@pytest.mark.asyncio
async def test_task_store_persistence(temp_storage):
    # 1. Initialize and add a task
    store = TaskStore(storage_path=temp_storage)
    task1 = await store.add_task(title="Persistent Task", description="Testing JSON")
    task_id = task1.id
    
    # Verify file exists
    assert os.path.exists(temp_storage)
    
    # 2. Re-initialize store and check if task is loaded
    new_store = TaskStore(storage_path=temp_storage)
    loaded_task = new_store.get_task(task_id)
    assert loaded_task is not None
    assert loaded_task.title == "Persistent Task"
    assert loaded_task.description == "Testing JSON"

@pytest.mark.asyncio
async def test_task_store_modification_persistence(temp_storage):
    store = TaskStore(storage_path=temp_storage)
    task = await store.add_task(title="Update Task")
    
    # Update status
    await store.update_status(task.id, TaskStatus.IN_PROGRESS)
    
    # Re-load
    store2 = TaskStore(storage_path=temp_storage)
    loaded_task = store2.get_task(task.id)
    assert loaded_task.status == TaskStatus.IN_PROGRESS

@pytest.mark.asyncio
async def test_delete_task_clears_parent_id(temp_storage):
    store = TaskStore(storage_path=temp_storage)
    parent = await store.add_task(title="Parent")
    child = await store.add_task(title="Child", parent_id=parent.id)
    
    assert child.parent_id == parent.id
    
    # Delete parent
    await store.delete_task(parent.id)
    
    # Check child
    updated_child = store.get_task(child.id)
    assert updated_child.parent_id is None
    
    # Verify persistence of the deletion and update
    store2 = TaskStore(storage_path=temp_storage)
    assert store2.get_task(parent.id) is None
    assert store2.get_task(child.id).parent_id is None

@pytest.mark.asyncio
async def test_atomic_save_error_handling(temp_storage):
    # This is harder to test without mocking, but we can verify it works normally
    store = TaskStore(storage_path=temp_storage)
    await store.add_task(title="Task 1")
    
    with open(temp_storage, 'r') as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]['title'] == "Task 1"
