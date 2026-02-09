import logging
from src.infrastructure.event_bus import EventBus
from src.domain.event import EventType, Event
from src.infrastructure.singleton import Singleton
from src.agents.plan_manager_agent import PlanManagerAgent

logger = logging.getLogger(__name__)

class PlanDirector:
    """
    Orchestrates the PlanManagerAgent based on system events.
    Functions as a bridge between the EventBus and the PlanManager.
    """
    def __init__(self):
        self.event_bus = EventBus()
        self.task_store = Singleton.get_task_store()
        # Initialize the agent
        self.agent = PlanManagerAgent(self.task_store).start()

    def start(self):
        """Subscribes to relevant events."""
        logger.info("PlanDirector starting...")
        self.event_bus.subscribe(EventType.TASK_CREATED, self.handle_task_created)
        self.event_bus.subscribe(EventType.TASK_STATUS_CHANGED, self.handle_task_status_changed)

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
            logger.debug(f"PlanDirector ignoring sub-task creation: {title} ({task_id}) with parent {parent_id}")
            return

        logger.info(f"PlanDirector received TASK_CREATED: {title} ({task_id})")
        
        prompt = (
            f"A new task has been created: '{title}' (ID: {task_id})."
            f"Description: {task_data.get('description')}"

            "If it requires immediate action, assign it or execute it. "
            "Ensure you set the status to IN_PROGRESS if you are working on it."
        )
        
        try:
            logger.info(f"PlanManager activating for task {task_id}...")
            async for chunk in self.agent.stream(prompt):
                if hasattr(chunk, 'content') and chunk.content:
                    # Stream content as it arrives
                    print(chunk.content)
        except Exception as e:
            logger.error(f"Error in PlanManager execution for task {task_id}: {e}")
        finally:
            # After the stream ends, verify the task's state
            final_task_state = self.task_store.get_task(task_id)
            if final_task_state and final_task_state.status == "in_progress":
                logger.warning(
                    f"Task {task_id} is still IN_PROGRESS after PlanManager stream ended. "
                    "Agent may have crashed or reached a limit."
                )
                self.task_store.update_task(
                    task_id,
                    status="blocked",
                    reason="Agent stopped unexpectedly after initial processing."
                )

    async def handle_task_status_changed(self, event: Event):
        """
        Handle status changes (e.g. APPROVED).
        """
        payload = event.payload
        new_status = payload.get("new_status")
        task_id = payload.get("task_id")
        
        if new_status == "approved":
            logger.info(f"Task {task_id} APPROVED. Waking PlanManager...")
            prompt = f"Task {task_id} has been APPROVED. You may now proceed with execution."
            try:
                async for chunk in self.agent.stream(prompt):
                    pass
            except Exception as e:
                logger.error(f"Error in PlanManager execution: {e}")