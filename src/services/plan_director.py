import logging
import asyncio
import time
from typing import Dict, Any, List, Tuple

from src.domain.task import Task, TaskStatus
from src.infrastructure.event_bus import EventBus
from src.domain.event import EventType, Event
from src.infrastructure.singleton import Singleton
from src.agents.plan_manager_agent import PlanManagerAgent
from src.agents.coder_agent import CoderAgent
from src.agents.research_agent import ResearchAgent
from src.services.priority_queue import PriorityQueue
from src.services.notification_service import notification_service

logger = logging.getLogger(__name__)


class PlanDirectorConfig:
    """Configuration for PlanDirector watchdog timeouts and limits"""
    
    # Concurrency
    MAX_CONCURRENT_TASKS = 1
    
    # Inactivity timeouts
    INACTIVITY_TIMEOUT_INITIAL = 120  # 2 min
    INACTIVITY_TIMEOUT_ACTIVE = 240   # 4 min
    
    # Absolute limits
    MAX_TOTAL_TIME = 900              # 15 min
    MAX_TOOL_CALLS = 100              # 100 tool calls
    
    # Watchdog
    WATCHDOG_CHECK_INTERVAL = 45     # 45 seconds
    
    # Verification
    VERIFY_TASK_COMPLETION = True
    CLEANUP_ORPHANED_TASKS = False


class PlanDirector:
    """
    Orchestrates the PlanManagerAgent based on system events.
    """
    
    def __init__(self, config: PlanDirectorConfig = None):
        self.config = config or PlanDirectorConfig()
        self.event_bus = EventBus()
        self.task_store = Singleton.get_task_store()
        self.priority_queue = PriorityQueue(self.task_store)
        self._started = False
        self._start_lock = asyncio.Lock()    
        
        # Track tasks currently being processed
        self.processing_tasks: Dict[str, Dict[str, Any]] = {}
        self._watchdog_running = False
    
    def ensure_started(self):
        if self._started:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.start())
        except RuntimeError:
            logger.debug("PlanDirector start deferred (no event loop yet)")

    async def _cleanup_zombie_tasks(self):
        """Standardizes orphaned IN_PROGRESS tasks to PAUSED on startup."""
        for task in self.task_store.list_tasks():
            if task.status == TaskStatus.IN_PROGRESS:
                await self.task_store.update_task(
                    task.id,
                    updates={
                        "status": TaskStatus.PAUSED,
                        "context": {"pause_reason": "System restart cleanup"}
                    }
                )

    async def start(self):
        if self._started:
            return
        async with self._start_lock:
            if self._started:
                return
        
        logger.info("PlanDirector starting...")
        self.event_bus.subscribe(EventType.TASK_CREATED, self.handle_task_created)
        self.event_bus.subscribe(EventType.TASK_STATUS_CHANGED, self.handle_task_status_changed)
        self.event_bus.subscribe(EventType.TASK_COMPLETED, self.handle_task_completed)
        self.event_bus.subscribe(EventType.TASK_FAILED, self.handle_task_failed)

        if not self._watchdog_running:
            asyncio.create_task(self._watchdog_loop())
            self._watchdog_running = True
            
        await self._cleanup_zombie_tasks()
        self._started = True
        logger.info("PlanDirector started successfully")

    async def handle_task_created(self, event: Event):
        await self._process_queue()

    async def handle_task_status_changed(self, event: Event):
        await self._process_queue()

    async def handle_task_completed(self, event: Event):
        await self._process_queue()

    async def handle_task_failed(self, event: Event):
        await self._process_queue()

    async def _process_queue(self):
        if len(self.processing_tasks) >= self.config.MAX_CONCURRENT_TASKS:
            return

        next_task = self.priority_queue.get_next_task()
        if next_task and next_task.id not in self.processing_tasks:
            logger.info(f"Processing next task: {next_task.title} ({next_task.id})")
            await self._run_agent_for_task(next_task)

    async def _run_agent_for_task(self, task: Task):
        task_id = task.id
        self.processing_tasks[task_id] = {
            'start_time': time.time(),
            'last_activity': time.time(),
            'tool_calls': 0,
            'title': task.title
        }
        
        prompt = (
            f"Task: '{task.title}' (ID: {task_id})\\n"
            f"Description: {task.description or 'None'}\\n"
            f"Status: {task.status}\\n\\n"
            "Analyze and act. Move task out of 'todo' to 'in_progress', 'waiting_approval', or 'blocked'."
        )
        
        try:
            # Create a fresh agent instance based on assignment
            if task.assigned_to == 'coder_agent':
                agent = CoderAgent().start()
            elif task.assigned_to == 'research_agent':
                agent = ResearchAgent().start()
            else:
                # Default to PlanManager for orchestration
                agent = PlanManagerAgent(self.task_store).start()

            logger.info(f"Task {task_id} assigned to {agent.__class__.__name__}")

            async for chunk in agent.stream(prompt):\
                # Check for permission requests
                if hasattr(chunk, 'permission_request') and chunk.permission_request:
                    tool_names = []
                    for req in chunk.permission_request:
                        if isinstance(req, dict):
                            tool_names.append(req.get('name', 'unknown'))
                        elif hasattr(req, 'name'):
                            tool_names.append(req.name)
                        else:
                            tool_names.append(str(req))
                    
                    logger.info(f"Task {task.id} requesting permission for: {tool_names}")
                    
                    await self.task_store.update_task(
                        task_id, 
                        updates={
                            "status": TaskStatus.WAITING_APPROVAL,
                            "context": {"pending_permissions": tool_names}
                        }
                    )
                    
                    await notification_service.send_approval_request(task_id, task.title, tool_names)
                    break

                if hasattr(chunk, 'content') and chunk.content:
                    if task_id in self.processing_tasks:
                        self.processing_tasks[task_id]['last_activity'] = time.time()
                
                if hasattr(chunk, 'tool_call') and chunk.tool_call:
                    if task_id in self.processing_tasks:
                        self.processing_tasks[task_id]['tool_calls'] += 1
        except Exception as e:
            await self._handle_processing_failure(task_id, f"Agent crashed: {str(e)}")
        finally:
            self.processing_tasks.pop(task_id, None)
            if self.config.VERIFY_TASK_COMPLETION:
                await self._verify_and_cleanup_task(task_id)
            await self._process_queue()

    async def _verify_and_cleanup_task(self, task_id: str):
        task = self.task_store.get_task(task_id)
        if not task: 
            return

        # Check 2: IN_PROGRESS validation
        if task.status == TaskStatus.IN_PROGRESS:
            subtasks = self.task_store.get_subtasks(task_id)
            if not subtasks:
                if not task.assigned_to:
                    msg = f"🟡 **Safety Net**: Paused '{task.title}'. No subtasks or agent assigned."
                    await notification_service.send_custom_notification(msg)
                    await self.task_store.update_task(task_id, updates={
                        "status": TaskStatus.PAUSED,
                        "context": {"pause_reason": "No subtasks/agent assigned"}
                    })
            else:
                active = [st for st in subtasks if st.status in [TaskStatus.IN_PROGRESS, TaskStatus.WAITING_APPROVAL]]
                if not active:
                    done = [st for st in subtasks if st.status == TaskStatus.DONE]
                    if len(done) == len(subtasks):
                        await self.task_store.update_task(task_id, updates={
                            "status": TaskStatus.DONE,
                            "result_summary": "System Auto-Complete: All subtasks finished."
                        })
                    elif any(st.status == TaskStatus.BLOCKED for st in subtasks):
                        await self.task_store.update_task(task_id, updates={"status": TaskStatus.BLOCKED})

    async def _handle_processing_failure(self, task_id: str, reason: str, details: dict = None):
        task = self.task_store.get_task(task_id)
        if not task: return
        
        await self.task_store.update_task(task_id, updates={
            "status": TaskStatus.BLOCKED,
            "context": {"blocked_reason": reason, **(details or {})}
        })
        
        msg = f"❌ **Task Failure**: '{task.title}'\\nReason: {reason}"
        notification_service.send_custom_notification(msg)

    async def _watchdog_loop(self):
        while True:
            await asyncio.sleep(self.config.WATCHDOG_CHECK_INTERVAL)
            current_time = time.time()
            for task_id, tracking in list(self.processing_tasks.items()):
                elapsed = current_time - tracking['start_time']
                inactive = current_time - tracking['last_activity']
                
                reason = None
                if inactive > self.config.INACTIVITY_TIMEOUT_ACTIVE:
                    reason = "Inactivity Timeout"
                elif elapsed > self.config.MAX_TOTAL_TIME:
                    reason = "Absolute Timeout"
                
                if reason:
                    await self._handle_processing_failure(task_id, f"Watchdog: {reason}", {"elapsed": elapsed})
                    self.processing_tasks.pop(task_id, None)

    def stop(self):
        self._watchdog_running = False