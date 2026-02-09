import logging
import asyncio
import time
from typing import Dict, Any, List, Tuple

from domain.task import TaskStatus
from src.infrastructure.event_bus import EventBus
from src.domain.event import EventType, Event
from src.infrastructure.singleton import Singleton
from src.agents.plan_manager_agent import PlanManagerAgent

logger = logging.getLogger(__name__)


class PlanDirectorConfig:
    """Configuration for PlanDirector watchdog timeouts and limits"""
    
    # Inactivity timeouts (time since last output from agent)
    INACTIVITY_TIMEOUT_INITIAL = 120  # 2 min: Initial analysis phase (no tools yet)
    INACTIVITY_TIMEOUT_ACTIVE = 240   # 4 min: Active tool usage phase
    
    # Absolute limits
    MAX_TOTAL_TIME = 900              # 15 min: Absolute maximum processing time
    MAX_TOOL_CALLS = 100              # 100 tool calls: Likely infinite loop
    
    # Watchdog
    WATCHDOG_CHECK_INTERVAL = 45     # Check every 30 seconds
    
    # Stream completion verification
    VERIFY_TASK_COMPLETION = True     # Check task states after stream ends
    CLEANUP_ORPHANED_TASKS = False     # Auto-cleanup tasks left in progress


class PlanDirector:
    """
    Orchestrates the PlanManagerAgent based on system events.
    Functions as a bridge between the EventBus and the PlanManager.
    
    Features:
    - Event-driven task processing
    - Watchdog monitoring for hung processes
    - Inactivity-based timeout detection
    - Automatic cleanup of orphaned tasks
    - Progressive timeout strategy
    """
    
    def __init__(self, config: PlanDirectorConfig = None):
        self.config = config or PlanDirectorConfig()
        self.event_bus = EventBus()
        self.task_store = Singleton.get_task_store()
        self._started = False
        self._start_lock = asyncio.Lock()    
        
        # Initialize the PlanManager agent
        self.agent = PlanManagerAgent(self.task_store).start()
        
        # Track tasks currently being processed
        # Format: task_id -> {start_time, last_activity, tool_calls, context}
        self.processing_tasks: Dict[str, Dict[str, Any]] = {}
        
        # Flag to control watchdog
        self._watchdog_running = False
    
    def ensure_started(self):
        """
        Safe to call from sync or async code.
        Starts PlanDirector when an event loop exists.
        """
        if self._started:
            return

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.start())
        except RuntimeError:
            # No event loop yet → defer startup
            logger.debug("PlanDirector start deferred (no event loop yet)")

    async def start(self):
        """Start the PlanDirector and subscribe to events."""

        if self._started:
            return

        async with self._start_lock:
            if self._started:
                return

        logger.info("PlanDirector starting...")
        
        # Subscribe to relevant events
        self.event_bus.subscribe(EventType.TASK_CREATED, self.handle_task_created)
        self.event_bus.subscribe(EventType.TASK_STATUS_CHANGED, self.handle_task_status_changed)
        
        # Start watchdog for stuck tasks
        if not self._watchdog_running:
            asyncio.create_task(self._watchdog_loop())
            self._watchdog_running = True
        self._pause_all_active_tasks()
        logger.info("PlanDirector started successfully")

    def _pause_all_active_tasks(self): 
        for task in self.task_store.list_tasks(): 
            if task.status == TaskStatus.IN_PROGRESS: 
                task.status = TaskStatus.WAITING_REVIEW


    async def handle_task_created(self, event: Event):
        """
        When a new task is created (likely by MainAgent), 
        wake up the Plan Manager to analyze it.
        
        To prevent recursive loops, we ignore sub-tasks created by the Plan Manager.
        """
        task_data = event.payload
        task_id = task_data.get("id")
        title = task_data.get("title")
        parent_id = task_data.get("parent_id")
        
        # FIX: Ignore sub-tasks to prevent loops
        if parent_id:
            logger.debug(
                f"PlanDirector ignoring sub-task creation: {title} ({task_id}) "
                f"with parent {parent_id}"
            )
            return

        logger.info(f"PlanDirector received TASK_CREATED: {title} ({task_id})")
        
        # Track that we're processing this task
        self.processing_tasks[task_id] = {
            'start_time': time.time(),
            'last_activity': time.time(),
            'tool_calls': 0,
            'context': 'task_created',
            'title': title
        }
        
        prompt = (
            f"A new task has been created: '{title}' (ID: {task_id}).\n"
            f"Description: {task_data.get('description', 'No description provided')}\n"
            f"Current status: {task_data.get('status', 'todo')}\n"
            f"Priority: {task_data.get('priority', 'medium')}\n\n"
            "Analyze this task, create a plan if needed, and set appropriate status.\n"
            "Ensure you move the task out of 'todo' status to either 'in_progress', "
            "'waiting_approval', or 'blocked'.\n\n"
            "For complex tasks requiring many tool calls (>10), periodically output progress markers:\n"
            "Example: [PROGRESS] Created 3 of 8 subtasks...\n\n"
            "CRITICAL: Before you finish, verify the task is in a valid state that will "
            "trigger future events. Never leave tasks orphaned in 'todo' or 'in_progress' "
            "without assignment."
        )
        
        try:
            logger.info(f"PlanManager activating for task {task_id}...")
            
            # Stream agent responses (no hard timeout - watchdog handles it)
            async for chunk in self.agent.stream(prompt):
                if hasattr(chunk, 'content') and chunk.content:
                    # Stream content as it arrives
                    content = chunk.content
                    print(content, end='', flush=True)
                    
                    # Update last activity time on any output
                    if task_id in self.processing_tasks:
                        self.processing_tasks[task_id]['last_activity'] = time.time()
                        
                        # Check for progress markers
                        if '[PROGRESS]' in content:
                            logger.debug(f"Task {task_id} progress: {content.strip()}")
                
                # Track tool usage
                if hasattr(chunk, 'type') and chunk.type == 'tool_use':
                    if task_id in self.processing_tasks:
                        self.processing_tasks[task_id]['tool_calls'] += 1
                        logger.debug(
                            f"Task {task_id} tool call #{self.processing_tasks[task_id]['tool_calls']}: "
                            f"{getattr(chunk, 'name', 'unknown')}"
                        )
            
            logger.info(f"PlanManager completed processing task {task_id}")
            
        except Exception as e:
            logger.error(
                f"PlanManager ERROR processing task {task_id}: {e}", 
                exc_info=True
            )
            await self._handle_processing_failure(
                task_id,
                f"PlanManager crashed with exception: {str(e)}"
            )
        finally:
            # Remove from processing tracker
            tracking_info = self.processing_tasks.pop(task_id, None)
            
            if tracking_info:
                elapsed = time.time() - tracking_info['start_time']
                tool_calls = tracking_info['tool_calls']
                logger.info(
                    f"Task {task_id} processing complete: "
                    f"{elapsed:.1f}s elapsed, {tool_calls} tool calls"
                )
            
            # Verify the task is in a valid state
            if self.config.VERIFY_TASK_COMPLETION:
                await self._verify_and_cleanup_task(task_id)

    async def handle_task_status_changed(self, event: Event):
        """
        Handle status changes (e.g. APPROVED).
        Only processes transitions to 'approved' status.
        """
        payload = event.payload
        new_status = payload.get("new_status")
        task_id = payload.get("task_id")
        old_status = payload.get("old_status", "unknown")
        
        # Only process approved tasks
        if new_status not in ["approved", "todo", "cleanup"]:
            logger.debug(
                f"PlanDirector ignoring status change: {task_id} "
                f"{old_status} -> {new_status}"
            )
            return
            
        logger.info(
            f"Task {task_id} is moved to {new_status} (was {old_status}). Waking PlanManager..."
        )
        
        # Track processing
        self.processing_tasks[task_id] = {
            'start_time': time.time(),
            'last_activity': time.time(),
            'tool_calls': 0,
            'context': 'approved',
            'title': payload.get('title', 'Unknown')
        }
        
        prompt = (
            f"Task {task_id} has been moved to {new_status} by the user.\n"
            f"Previous status: {old_status}\n"
            f"Current status: {new_status}\n\n"
            "Your actions:\n"
            "1. Transition task to 'in_progress'\n"
            "2. Assign to appropriate agent (coder_agent or system_operator)\n"
            "3. Ensure execution begins immediately\n\n"
            "Exit cleanly once the task is properly assigned and in progress."
        )
        
        try:
            async for chunk in self.agent.stream(prompt):
                if hasattr(chunk, 'content') and chunk.content:
                    print(chunk.content, end='', flush=True)
                    
                    if task_id in self.processing_tasks:
                        self.processing_tasks[task_id]['last_activity'] = time.time()
                
                if hasattr(chunk, 'type') and chunk.type == 'tool_use':
                    if task_id in self.processing_tasks:
                        self.processing_tasks[task_id]['tool_calls'] += 1
            
            logger.info(f"PlanManager completed approval processing for task {task_id}")
            
        except Exception as e:
            logger.error(
                f"PlanManager ERROR processing approval for {task_id}: {e}", 
                exc_info=True
            )
            await self._handle_processing_failure(
                task_id,
                f"PlanManager crashed during approval processing: {str(e)}"
            )
        finally:
            self.processing_tasks.pop(task_id, None)
            
            if self.config.VERIFY_TASK_COMPLETION:
                await self._verify_and_cleanup_task(task_id)

    async def _verify_and_cleanup_task(self, task_id: str):
        """
        Verify task is in a valid state after PlanManager processing.
        Handle orphaned tasks and cleanup incomplete work.
        
        This runs after the agent stream completes to catch cases where:
        - Task left in 'todo' without dependencies
        - Task left in 'in_progress' without assignment
        - Subtasks created but not properly managed
        """
        task = self.task_store.get_task(task_id)
        if not task:
            logger.warning(
                f"Task {task_id} not found after processing - may have been deleted"
            )
            return
        
        logger.debug(f"Verifying task {task_id} state: {task.status}")
        
        # Check 1: Task still in 'todo' without valid reason
        if task.status == "todo":
            # Check if it has dependencies (valid reason to be in todo)
            if task.dependencies and len(task.dependencies) > 0:
                logger.info(
                    f"Task {task_id} in 'todo' with {len(task.dependencies)} "
                    "dependencies - valid state"
                )
                return
            
            # No dependencies but still in 'todo' - this is a failure
            logger.error(
                f"Task {task_id} left in 'todo' without dependencies after processing. "
                "PlanManager failed to plan this task. Marking as blocked."
            )
            await self.task_store.update_task(
                task_id,
                updates={
                    "status": "waiting_review",
                    "context": {
                        "waiting_review_reason": (
                            "PlanManager failed to transition task out of 'todo' status. "
                            "Task may be unclear or too complex."
                        ),
                        "original_title": task.title,
                        "requires_manual_review": True,
                        "auto_blocked_by": "plan_director_cleanup",
                        "blocked_at": time.time()
                    }
                }
            )
            logger.info(f"Task {task_id} is in waiting_review due to orphaned 'todo' status")
            return
        
        # Check 2: Task in 'in_progress' - verify it has subtasks or assignment
        if task.status == "in_progress":
            # Get subtasks
            subtasks = self.task_store.get_subtasks(task_id)
            
            # If no subtasks, this should be a simple task assigned to an agent
            if not subtasks or len(subtasks) == 0:
                # This might be OK if it's assigned directly to an agent
                # We can't verify assignment here, but log it
                logger.info(
                    f"Task {task_id} in 'in_progress' with no subtasks - "
                    "assuming direct agent assignment"
                )
                return
            
            # Has subtasks - verify at least one is active
            active_subtasks = [
                st for st in subtasks 
                if st.status in ['in_progress', 'waiting_approval']
            ]
            
            if not active_subtasks:
                # All subtasks are blocked/done/paused - parent shouldn't be in_progress
                logger.warning(
                    f"Task {task_id} in 'in_progress' but all {len(subtasks)} "
                    "subtasks are inactive. Checking completion status..."
                )
                
                # Check if all subtasks are done
                done_subtasks = [st for st in subtasks if st.status == 'done']
                if len(done_subtasks) == len(subtasks):
                    logger.info(
                        f"Task {task_id} - all subtasks complete, marking parent as done"
                    )
                    await self.task_store.update_task(task_id, updates={"status": "done"})
                    return
                
                # Check if any are blocked
                blocked_subtasks = [st for st in subtasks if st.status == 'blocked']
                if blocked_subtasks:
                    logger.warning(
                        f"Task {task_id} - {len(blocked_subtasks)} subtasks blocked, "
                        "marking parent as blocked"
                    )
                    await self.task_store.update_task(
                        task_id,
                        updates={
                            "status": "blocked",
                            "context": {
                                "blocked_reason": f"{len(blocked_subtasks)} subtasks are blocked",
                                "blocked_subtasks": [st.id for st in blocked_subtasks],
                                "auto_blocked_by": "plan_director_cleanup"
                            }
                        }
                    )
                    return
                
                # Otherwise, pause the parent
                logger.info(
                    f"Task {task_id} - no active subtasks, pausing parent until work resumes"
                )
                await self.task_store.update_task(
                    task_id,
                    updates={
                        "status": "paused",
                        "context": {
                            "paused_reason": "All subtasks are inactive (waiting_approval, todo, or paused)",
                            "auto_paused_by": "plan_director_cleanup"
                        }
                    }
                )
        
        # Check 3: Cleanup orphaned subtasks if enabled
        if self.config.CLEANUP_ORPHANED_TASKS:
            await self._cleanup_orphaned_subtasks(task_id)

    async def _cleanup_orphaned_subtasks(self, parent_task_id: str):
        """
        Find and cleanup subtasks that are stuck in 'in_progress' 
        without proper assignment or context.
        """
        subtasks = self.task_store.get_subtasks(parent_task_id)
        
        for subtask in subtasks:
            # Only check subtasks that are supposedly active
            if subtask.status != "in_progress":
                continue
            
            # If a subtask is in_progress but hasn't been updated recently,
            # it might be orphaned (agent crashed, etc.)
            # We can't check timestamps here without that field, so just log
            logger.debug(
                f"Subtask {subtask.id} of {parent_task_id} is in_progress - "
                "assuming agent is handling it"
            )
            
            # TODO: If task_store has 'updated_at' timestamp, we could check:
            # if subtask.updated_at < (now - 5 minutes):
            #     logger.warning(f"Subtask {subtask.id} stale, marking as paused")
            #     self.task_store.update_task(subtask.id, status="paused")

    def _verify_task_state(self, task_id: str):
        """
        DEPRECATED: Use _verify_and_cleanup_task instead.
        Kept for backward compatibility.
        """
        # This is now handled by _verify_and_cleanup_task
        # which is called in the finally block
        pass

    async def _handle_processing_failure(self, task_id: str, reason: str):
        """
        Handle failures during PlanManager processing.
        Ensures task is marked as blocked with clear reason.
        
        Args:
            task_id: ID of the task that failed
            reason: Human-readable explanation of the failure
        """
        logger.error(f"Processing failure for task {task_id}: {reason}")
        
        try:
            task = self.task_store.get_task(task_id)
            if not task:
                logger.error(
                    f"Cannot mark task {task_id} as blocked - task not found"
                )
                return
            
            await self.task_store.update_task(
                task_id,
                updates={
                    "status": "blocked",
                    "context": {
                        "blocked_reason": reason,
                        "failed_at": time.time(),
                        "requires_manual_review": True,
                        "auto_blocked_by": "plan_director_failure_handler",
                        "original_status": task.status
                    }
                }
            )
            logger.info(
                f"Task {task_id} marked as blocked due to processing failure"
            )
            
        except Exception as e:
            logger.critical(
                f"CRITICAL: Failed to mark task {task_id} as blocked after "
                f"processing failure. Error: {e}. Original reason: {reason}",
                exc_info=True
            )

    async def _watchdog_loop(self):
        """
        Periodically check for tasks that have been processing too long.
        Uses an INACTIVITY timeout rather than absolute timeout.
        
        Detection strategies:
        1. Inactivity timeout (no output from agent)
        2. Absolute time limit (prevent infinite loops)
        3. Excessive tool calls (detect runaway recursion)
        """
        logger.info("PlanDirector watchdog started")
        
        while True:
            try:
                await asyncio.sleep(self.config.WATCHDOG_CHECK_INTERVAL)
                
                current_time = time.time()
                stuck_tasks: List[Tuple[str, str]] = []

                
                for task_id, tracking in list(self.processing_tasks.items()):
                    # task are only stuck if they are in_progress and no child task in waiting for approval 
                    start_time = tracking['start_time']
                    last_activity = tracking['last_activity']
                    tool_calls = tracking['tool_calls']
                    context = tracking.get('context', 'unknown')
                    title = tracking.get('title', 'Unknown')
                    
                    elapsed_total = current_time - start_time
                    inactive_duration = current_time - last_activity

                    subtasks = self.task_store.get_subtasks(task_id)
                
                    # Has subtasks - verify at least one is active
                    active_subtasks = [
                        st for st in subtasks 
                        if st.status in ['waiting_approval']
                    ]

                    if active_subtasks : 
                        continue
                    
                    # Strategy 1: No tool calls yet and inactive for too long
                    # (Stuck in initial analysis/thinking)
                    if (tool_calls == 0 and 
                        inactive_duration > self.config.INACTIVITY_TIMEOUT_INITIAL):
                        stuck_tasks.append((
                            task_id,
                            f"No activity for {inactive_duration:.0f}s, "
                            f"no tool calls made (stuck in analysis). "
                            f"Context: {context}, Task: '{title}'"
                        ))
                    
                    # Strategy 2: Making tool calls but inactive for too long
                    # (Hung on a tool call or waiting for response)
                    elif (tool_calls > 0 and 
                          inactive_duration > self.config.INACTIVITY_TIMEOUT_ACTIVE):
                        stuck_tasks.append((
                            task_id,
                            f"No activity for {inactive_duration:.0f}s after "
                            f"{tool_calls} tool calls (hung on operation). "
                            f"Context: {context}, Task: '{title}'"
                        ))
                    
                    # Strategy 3: Total time exceeds absolute limit
                    # (Safety net for any scenario)
                    elif elapsed_total > self.config.MAX_TOTAL_TIME:
                        stuck_tasks.append((
                            task_id,
                            f"Total processing time {elapsed_total:.0f}s exceeds "
                            f"{self.config.MAX_TOTAL_TIME}s limit "
                            f"({tool_calls} tool calls). "
                            f"Infinite loop suspected. Context: {context}, Task: '{title}'"
                        ))
                    
                    # Strategy 4: Excessive tool calls
                    # (Possible infinite loop or runaway recursion)
                    elif tool_calls > self.config.MAX_TOOL_CALLS:
                        stuck_tasks.append((
                            task_id,
                            f"Excessive tool calls ({tool_calls} > "
                            f"{self.config.MAX_TOOL_CALLS}) detected. "
                            f"Infinite loop suspected. Elapsed: {elapsed_total:.0f}s, "
                            f"Context: {context}, Task: '{title}'"
                        ))
                
                # Handle stuck tasks
                for task_id, reason in stuck_tasks:
                    logger.error(f"Watchdog detected stuck task {task_id}: {reason}")
                    await self._handle_processing_failure(
                        task_id, 
                        f"Watchdog intervention: {reason}"
                    )
                    self.processing_tasks.pop(task_id, None)
                
                # Log watchdog health
                if self.processing_tasks:
                    logger.info(
                        f"Watchdog check: {len(self.processing_tasks)} tasks in progress, "
                        f"{len(stuck_tasks)} stuck tasks detected"
                    )
                    
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}", exc_info=True)
                # Don't let watchdog crash - keep monitoring

    def stop(self):
        """Shutdown the PlanDirector gracefully."""
        logger.info("PlanDirector stopping...")
        self._watchdog_running = False
        
        # Report any tasks still in progress
        if self.processing_tasks:
            logger.warning(
                f"PlanDirector stopping with {len(self.processing_tasks)} "
                "tasks still in progress"
            )
            for task_id, tracking in self.processing_tasks.items():
                logger.warning(
                    f"  - Task {task_id}: {tracking['context']}, "
                    f"{tracking['tool_calls']} tool calls, "
                    f"{time.time() - tracking['start_time']:.1f}s elapsed"
                )
        
        logger.info("PlanDirector stopped")
