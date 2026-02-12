import logging
import asyncio
import time
from typing import Dict, Any, List, Optional

from src.domain.task import Task, TaskStatus
from src.infrastructure.event_bus import EventBus
from src.domain.event import EventType, Event
from src.infrastructure.singleton import Singleton
from src.engine.core.agent_instance_manager import get_agent_manager
from src.engine.core.types import Message, Role
from src.services.priority_queue import PriorityQueue
from src.services.notification_service import notification_service

logger = logging.getLogger(__name__)


class PlanDirectorConfig:
    """Configuration for PlanDirector watchdog timeouts and limits"""
    MAX_CONCURRENT_TASKS = 1
    INACTIVITY_TIMEOUT_INITIAL = 120 
    INACTIVITY_TIMEOUT_ACTIVE = 240   
    MAX_TOTAL_TIME = 1200              
    MAX_TOOL_CALLS = 100              
    WATCHDOG_CHECK_INTERVAL = 45     
    VERIFY_TASK_COMPLETION = True


class PlanDirector:
    """
    Orchestrates the Specialist Swarm.
    Ensures tasks flow: TODO -> IN_PROGRESS -> WAITING_REVIEW -> DONE.
    Handles Parent/Child gating and Plan Approvals.
    """
    
    def __init__(self, config: PlanDirectorConfig = None):
        self.config = config or PlanDirectorConfig()
        self.event_bus = EventBus()
        self.task_store = Singleton.get_task_store()
        self.priority_queue = PriorityQueue(self.task_store)
        self._started = False
        self._start_lock = asyncio.Lock()    
        
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
            self._started = True
        
        logger.info("PlanDirector starting...")
        self.event_bus.subscribe(EventType.TASK_CREATED, self.handle_task_created)
        self.event_bus.subscribe(EventType.TASK_STATUS_CHANGED, self.handle_task_status_changed)
        self.event_bus.subscribe(EventType.TASK_COMPLETED, self.handle_task_completed)
        self.event_bus.subscribe(EventType.TASK_FAILED, self.handle_task_failed)
        self.event_bus.subscribe(EventType.USER_APPROVAL, self.handle_user_approval)

        if not self._watchdog_running:
            asyncio.create_task(self._watchdog_loop())
            self._watchdog_running = True
            
        await self._cleanup_zombie_tasks()
        logger.info("PlanDirector started successfully")

    # --- Event Handlers ---

    async def handle_user_approval(self, event: Event):
        """Handles task approvals from the user (via Telegram)."""
        payload = event.payload
        task_id = payload.get('task_id')
        approved = payload.get('approved')
        
        if task_id:
            task = self.task_store.get_task(task_id)
            if task and task.status == TaskStatus.WAITING_APPROVAL:
                new_status = TaskStatus.APPROVED if approved else TaskStatus.CANCELLED
                await self.task_store.update_status(task_id, new_status)
                logger.info(f"Task {task_id} approved: {approved}. Status set to {new_status}")

    async def handle_task_created(self, event: Event):
        task_data = event.payload
        parent_id = task_data.get('parent_id')
        if parent_id:
            await self._handle_subtask_addition(parent_id)
        await self._process_queue()

    async def handle_task_status_changed(self, event: Event):
        task_data = event.payload
        new_status = task_data.get('new_status')
        task_id = task_data.get('task_id')

        if new_status == TaskStatus.DONE:
            task = self.task_store.get_task(task_id)
            if task and task.parent_id:
                await self._check_parent_completion(task.parent_id)

        await self._process_queue()

    async def handle_task_completed(self, event: Event):
        await self._process_queue()

    async def handle_task_failed(self, event: Event):
        task_data = event.payload
        if task_data.get('parent_id'):
            await self._notify_parent_failure(task_data['parent_id'], task_data.get('id'))
        await self._process_queue()

    # --- Core Logic ---

    async def _handle_subtask_addition(self, parent_id: str):
        parent = self.task_store.get_task(parent_id)
        if parent and parent.status not in [TaskStatus.APPROVED, TaskStatus.WAITING_APPROVAL, TaskStatus.BLOCKED, TaskStatus.DONE]:
            subtasks = self.task_store.get_subtasks(parent_id)
            await self.task_store.update_task(
                parent_id,
                updates={
                    "status": TaskStatus.WAITING_APPROVAL,
                    "context": {"auto_update": f"Plan generated with {len(subtasks)} subtasks."}
                }
            )
            await notification_service.send_plan_approval_request(parent_id, parent.title, len(subtasks))

    async def _check_parent_completion(self, parent_id: str):
        parent = self.task_store.get_task(parent_id)
        if not parent or parent.status == TaskStatus.DONE:
            return

        subtasks = self.task_store.get_subtasks(parent_id)
        if not subtasks: return

        total = len(subtasks)
        done = [t for t in subtasks if t.status == TaskStatus.DONE]
        
        if len(done) == total:
            summary = "### Consolidated Execution Summary\n\n"
            for t in subtasks:
                summary += f"**Task:** {t.title}\n**Result:** {t.result_summary or 'Completed.'}\n\n"
            
            await self.task_store.update_task(
                parent_id,
                updates={
                    "status": TaskStatus.DONE,
                    "result_summary": summary
                }
            )
            await notification_service.send_custom_notification(f"🏁 **Project Completed**: {parent.title}\n{summary}")

    async def _notify_parent_failure(self, parent_id: str, child_id: str):
        parent = self.task_store.get_task(parent_id)
        if parent and parent.status != TaskStatus.BLOCKED:
            await self.task_store.update_task(
                parent_id,
                updates={
                    "status": TaskStatus.BLOCKED,
                    "context": {"blocked_reason": f"Subtask {child_id} failed."}
                }
            )

    async def _process_queue(self):
        if len(self.processing_tasks) >= self.config.MAX_CONCURRENT_TASKS:
            return

        next_task = self.priority_queue.get_next_task()
        if next_task and next_task.id not in self.processing_tasks:
            await self._run_agent_for_task(next_task)

    def _get_or_create_agent(self, agent_id: str):
        manager = get_agent_manager()
        agent = manager.get_agent(agent_id)
        if not agent:
            if agent_id == 'coder_agent':
                from src.agents.coder_agent import CoderAgent
                return CoderAgent().start()
            elif agent_id == 'research_agent':
                from src.agents.research_agent import ResearchAgent
                return ResearchAgent().start()
            elif agent_id == 'system_operator_agent':
                from src.agents.system_operator_agent import SystemOperatorAgent
                return SystemOperatorAgent().start()
            else:
                from src.agents.plan_manager_agent import PlanManagerAgent
                return PlanManagerAgent().start()
        return agent

    async def _run_agent_for_task(self, task: Task):
        task_id = task.id
        self.processing_tasks[task_id] = {
            'start_time': time.time(),
            'last_activity': time.time(),
            'tool_calls': 0,
            'title': task.title
        }
        
        sibling_context = ""
        if task.parent_id:
            siblings = self.task_store.get_subtasks(task.parent_id)
            done_siblings = [s for s in siblings if s.status == TaskStatus.DONE and s.id != task_id]
            if done_siblings:
                sibling_context = "### Context from Previous Steps:\n"
                for s in done_siblings:
                    sibling_context += f"- {s.title}: {s.result_summary}\n"

        prompt = (
            f"Objective: '{task.title}'\n"
            f"Description: {task.description or 'None'}\n"
            f"{sibling_context}\n"
            "Execution: Perform the task. At the end, provide a 'RESULT SUMMARY' "
            "detailing exactly what you achieved and any evidence (paths, success codes). "
            "Then stop. Do not mark as DONE yourself; the Planner will review your work."
        )
        
        try:
            agent_id = task.assigned_to or 'plan_manager'
            agent = self._get_or_create_agent(agent_id)
            manager = get_agent_manager()
            memory = manager.get_memory(agent_id)
            if memory: memory.clear()
            
            logger.info(f"Task {task_id} running with {agent_id}")
            full_response = ""
            async for chunk in agent.stream(prompt):
                if hasattr(chunk, 'content') and chunk.content:
                    full_response += chunk.content
                    if task_id in self.processing_tasks:
                        self.processing_tasks[task_id]['last_activity'] = time.time()
                if hasattr(chunk, 'tool_call') and chunk.tool_call:
                    if task_id in self.processing_tasks:
                        self.processing_tasks[task_id]['tool_calls'] += 1

            await self.task_store.update_task(
                task_id, 
                updates={
                    "status": TaskStatus.WAITING_REVIEW,
                    "result_summary": full_response.strip()
                }
            )
        except Exception as e:
            await self._handle_processing_failure(task_id, f"Agent crashed: {str(e)}")
        finally:
            self.processing_tasks.pop(task_id, None)
            await self._process_queue()

    async def _handle_processing_failure(self, task_id: str, reason: str, details: dict = None):
        task = self.task_store.get_task(task_id)
        if not task: return
        await self.task_store.update_task(task_id, updates={
            "status": TaskStatus.BLOCKED,
            "context": {"blocked_reason": reason, **(details or {})}
        })
        await notification_service.send_custom_notification(f"❌ **Task Failure**: {task.title}\n{reason}")

    async def _watchdog_loop(self):
        while True:
            await asyncio.sleep(self.config.WATCHDOG_CHECK_INTERVAL)
            current_time = time.time()
            for task_id, tracking in list(self.processing_tasks.items()):
                if (current_time - tracking['last_activity']) > self.config.INACTIVITY_TIMEOUT_ACTIVE or (current_time - tracking['start_time']) > self.config.MAX_TOTAL_TIME:
                    await self._handle_processing_failure(task_id, "Watchdog: Task Timeout")
                    self.processing_tasks.pop(task_id, None)

    def stop(self):
        self._watchdog_running = False
