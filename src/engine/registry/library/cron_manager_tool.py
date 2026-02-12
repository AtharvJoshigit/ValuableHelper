import os
import logging
from typing import Any, Optional
from pydantic import Field
from engine.registry.base_tool import BaseTool
from services.cron_service import cron_service
from infrastructure.command_bus import CommandBus
from src.domain.event import Event, EventType

logger = logging.getLogger(__name__)

class CronManagerTool(BaseTool):
    """
    God-mode tool to manage recurring automated tasks.
    """
    name: str = "cron_manager"
    description: str = "Add, list, or stop recurring automated tasks. Cron Scheduler"
    action: str = Field(..., description="Action to perform: 'add', 'list', or 'stop'.")
    job_name: Optional[str] = Field(None, description="Unique name for the job.")
    interval: Optional[int] = Field(None, description="Interval in seconds (for 'add').")
    instruction: Optional[str] = Field(None, description="The text instruction to run (for 'add').")

    async def execute(self, **kwargs) -> Any:
        action = kwargs.get("action")
        job_name = kwargs.get("job_name")
        interval = kwargs.get("interval")
        instruction = kwargs.get("instruction")

        if action == "add":
            if not all([job_name, interval, instruction]):
                return {"status": "error", "message": "Missing job_name, interval, or instruction for 'add'."}
            
            # Callback logic: Send a System Message event to the Main Agent
            async def cron_callback(instr):
                bus = CommandBus() # Global singleton instance
                await bus.send(Event(
                    type=EventType.USER_MESSAGE,
                    payload={
                        "chat_id": 0, # System chat ID
                        "text": f"System Cron ({job_name}): {instr}"
                    },
                    source="system"
                ))

            cron_service.add_job(job_name, interval, cron_callback, instruction)
            return {"status": "success", "message": f"Scheduled '{job_name}' every {interval}s."}

        elif action == "list":
            return {"status": "success", "jobs": cron_service.list_jobs()}

        elif action == "stop":
            if not job_name:
                return {"status": "error", "message": "job_name required to stop."}
            cron_service.stop_job(job_name)
            return {"status": "success", "message": f"Stopped job '{job_name}'."}

        return {"status": "error", "message": f"Unknown action: {action}"}
