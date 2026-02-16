import logging
import asyncio
import time
from typing import Dict, Any, List, Optional

from app.app_context import get_app_context
from src.domain.task import Task, TaskStatus
from src.domain.event import EventType, Event
from src.infrastructure.singleton import Singleton
from src.engine.core.agent_instance_manager import get_agent_manager
from src.services.priority_queue import PriorityQueue
from src.services.notification_service import get_notification_service

logger = logging.getLogger(__name__)

class PlanDirectorConfig:
    MAX_CONCURRENT_TASKS = 3
    MAX_EXECUTION_TIME = 3600  # 1 Hour
    WATCHDOG_INTERVAL = 60

class PlanDirector:
    """
    Orchestrates the lifecycle of tasks.
    Manages concurrency, failure handling, and agent dispatch.
    """
    
    def __init__(self, config: PlanDirectorConfig = None):
        self.config = config or PlanDirectorConfig()
        self.event_bus = get_app_context().event_bus
        self.task_store = Singleton.get_task_store()
        self.priority_queue = PriorityQueue(self.task_store)
        self.notification_service = get_notification_service()
        
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._task_metadata: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Starts the main orchestration loop."""
        logger.info("PlanDirector: Starting...")
        self._shutdown_event.clear()
        
        # Subscribe to lifecycle events
        self.event_bus.subscribe(EventType.TASK_CREATED, self._on_task_event)
        self.event_bus.subscribe(EventType.TASK_COMPLETED, self._on_task_event)
        self.event_bus.subscribe(EventType.TASK_FAILED, self._on_task_event)
        self.event_bus.subscribe(EventType.TASK_STATUS_CHANGED, self._on_task_event)
        
        asyncio.create_task(self._watchdog())
        
        # Initial check
        await self._process_queue()

    async def stop(self):
        logger.info("PlanDirector: Stopping...")
        self._shutdown_event.set()
        for t in self._running_tasks.values():
            t.cancel()
        self._running_tasks.clear()

    async def _on_task_event(self, event: Event):
        # Trigger queue processing on any relevant change
        await self._process_queue()

    async def _process_queue(self):
        """Fills available execution slots with high-priority tasks."""
        async with self._lock:
            active_count = len(self._running_tasks)
            slots_available = self.config.MAX_CONCURRENT_TASKS - active_count
            
            if slots_available <= 0:
                return

            candidates = self.priority_queue.get_runnable_tasks()
            
            # Filter out tasks already running
            to_launch = []
            for task in candidates:
                if task.id not in self._running_tasks:
                    to_launch.append(task)
                    if len(to_launch) >= slots_available:
                        break
            
            for task in to_launch:
                await self._launch_task(task)

    async def _launch_task(self, task: Task):
        logger.info(f"🚀 Launching Task: {task.title} ({task.id})")
        
        # Mark as IN_PROGRESS immediately to prevent double-scheduling
        await self.task_store.update_status(task.id, TaskStatus.IN_PROGRESS)
        
        # Spawn the worker
        coro = asyncio.create_task(self._execute_agent(task))
        self._running_tasks[task.id] = coro
        self._task_metadata[task.id] = {"start_time": time.time()}

    async def _execute_agent(self, task: Task):
        """Worker coroutine that runs the agent."""
        try:
            agent = self._resolve_agent(task.assigned_to)
            
            # Contextualize agent (Optional: Load memories here)
            # await agent.load_context(task.id) 

            # Execute
            # We support both stream() and run() patterns
            result_text = ""
            if hasattr(agent, 'run'):
                result_text = await agent.run(task.description)
            elif hasattr(agent, 'stream'):
                async for chunk in agent.stream(task.description):
                    if hasattr(chunk, 'content') and chunk.content:
                        result_text += chunk.content
            else:
                # Fallback or Mock
                result_text = "Task executed (Agent had no standard run method)."

            # Task Success
            await self.task_store.update_task(task.id, updates={
                "status": TaskStatus.WAITING_REVIEW, # Needs approval
                "result_summary": str(result_text)
            })
            self.event_bus.publish(Event(EventType.TASK_COMPLETED, {"id": task.id, "parent_id": task.parent_id}))

        except asyncio.CancelledError:
            logger.warning(f"Task {task.id} cancelled.")
            await self.task_store.update_status(task.id, TaskStatus.CANCELLED)
            
        except Exception as e:
            logger.error(f"❌ Task {task.id} failed: {e}", exc_info=True)
            await self.task_store.update_task(task.id, updates={
                "status": TaskStatus.BLOCKED,
                "context": {"error": str(e)}
            })
            self.event_bus.publish(Event(EventType.TASK_FAILED, {"id": task.id, "parent_id": task.parent_id}))
            
        finally:
            self._cleanup_task(task.id)
            # Trigger queue again to fill the slot
            asyncio.create_task(self._process_queue())

    def _resolve_agent(self, agent_id: str):
        """Resolves the agent instance, initializing if necessary."""
        manager = get_agent_manager()
        agent = manager.get_agent(agent_id)
        
        if agent:
            return agent
            
        # Fallback Logic for Lazy Loading (if manager doesn't auto-load)
        # This matches your old logic but cleaner
        if agent_id == 'coder_agent':
            from src.agents.coder_agent import CoderAgent
            return CoderAgent() # Should use Singleton or Manager in real world
        elif agent_id == 'research_agent':
            from src.agents.research_agent import ResearchAgent
            return ResearchAgent()
        
        # Default
        from src.agents.plan_manager_agent import PlanManagerAgent
        return PlanManagerAgent()

    def _cleanup_task(self, task_id: str):
        self._running_tasks.pop(task_id, None)
        self._task_metadata.pop(task_id, None)

    async def _watchdog(self):
        """Prevents tasks from hanging forever."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(self.config.WATCHDOG_INTERVAL)
            now = time.time()
            
            for task_id, meta in list(self._task_metadata.items()):
                if (now - meta["start_time"]) > self.config.MAX_EXECUTION_TIME:
                    logger.error(f"Task {task_id} TIMED OUT. Cancelling.")
                    if task_id in self._running_tasks:
                        self._running_tasks[task_id].cancel()
