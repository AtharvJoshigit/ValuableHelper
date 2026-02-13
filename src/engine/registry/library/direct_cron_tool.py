from engine.registry.base_tool import BaseTool
from services.cron_service import cron_service
import logging

logger = logging.getLogger(__name__)

class DirectCronTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="direct_cron",
            description="Directly interface with the CronService to manage background tasks."
        )

    async def execute(self, action: str, job_name: str = None, interval: int = 60, message: str = "Hi"):
        if action == "add":
            if not job_name:
                return "Error: job_name is required for 'add' action."
            # Direct callback to print to console/log
            def callback():
                print(f"\n[CRON] {job_name}: {message}")
                logger.info(f"CRON EXEC: {job_name} - {message}")
            
            cron_service.add_job(job_name, interval, callback)
            return f"✅ Job '{job_name}' scheduled every {interval}s."
        
        elif action == "list":
            jobs = cron_service.list_jobs()
            return str({"active_jobs": jobs})
        
        elif action == "stop":
            if not job_name:
                return "Error: job_name is required for 'stop' action."
            cron_service.stop_job(job_name)
            return f"🛑 Stopped Job '{job_name}'."
        
        return "Invalid action."

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "list", "stop"], "description": "The action to perform."},
                "job_name": {"type": "string", "description": "Unique name for the job."},
                "interval": {"type": "integer", "description": "Interval in seconds."},
                "message": {"type": "string", "description": "The message to log/print."}
            },
            "required": ["action"]
        }
