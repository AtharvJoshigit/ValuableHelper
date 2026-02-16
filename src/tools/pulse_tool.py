
import psutil
import os
import platform
from engine.registry.base_tool import BaseTool

class SystemPulseTool(BaseTool):
    """
    Retrieves live system health metrics (CPU, RAM, Disk, Uptime).
    """
    name : str = "system_pulse_tool"
    description : str = "Get real-time system performance metrics (CPU, RAM, Disk, Uptime)."

    async def execute(self, **kwargs) -> dict:
        try:
            return {
                "os": platform.system(),
                "release": platform.release(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "ram_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "process_id": os.getpid()
            }
        except Exception as e:
            return {"error": f"Failed to get pulse: {str(e)}"}
