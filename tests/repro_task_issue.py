import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from services.task_store import TaskStore
from tools.task_store_tool import AddTaskTool
from domain.task import TaskPriority

async def test_add_task():
    print("Initializing TaskStore...")
    store = TaskStore()
    
    print("Initializing AddTaskTool...")
    tool = AddTaskTool(store)
    
    print("Executing tool with valid data...")
    result = await tool.execute(title="Test Task", priority="high", description="A test task")
    print(f"Result: {result}")
    
    if "Error" in str(result) and "NoneType" in str(result):
        print("FAIL: Caught NoneType error")
    elif "Error" in str(result):
        print("FAIL: Caught other error")
    else:
        print("SUCCESS: Task created")

    # Test with None dependencies passed explicitly (simulating LLM behavior)
    print("Executing tool with explicit None dependencies...")
    result = await tool.execute(title="Test Task 2", dependencies=None)
    print(f"Result: {result}")

    # Test with missing title
    print("Executing tool with missing title...")
    result = await tool.execute(priority="low")
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(test_add_task())