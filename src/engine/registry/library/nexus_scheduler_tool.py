from engine.registry.base_tool import BaseTool
from services.cron_service import cron_service
from app.app_context import get_app_context
from src.domain.event import Event, EventType
import logging

logger = logging.getLogger(__name__)

class NexusSchedulerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="nexus_scheduler",
            description="Manages system-level recurring tasks and heartbeats."
        )

    async def execute(self, action: str, job_name: str = None, interval: int = 1800, event_type: str = None):
        if action == "add_heartbeat":
            bus = get_app_context().event_bus
            
            def pulse():
                logger.info(f"💓 [Nexus Pulse] Firing HEARTBEAT")
                bus.publish(Event(type=EventType.HEARTBEAT, payload={"job": job_name}))
            
            cron_service.add_job(job_name or "nexus_heartbeat", interval, pulse)
            return f"✅ Heartbeat '{job_name or 'nexus_heartbeat'}' established. Pulse every {interval}s."
        
        elif action == "list":
            return {"active_jobs": cron_service.list_jobs()}
        
        elif action == "stop":
            if not job_name:
                return "Error: job_name required for stop action."
            cron_service.stop_job(job_name)
            return f"🛑 Stopped job: {job_name}"
            
        return "Invalid action. Use 'add_heartbeat', 'list', or 'stop'."
