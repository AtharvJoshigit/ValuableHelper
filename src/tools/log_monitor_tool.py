import os
import logging
from typing import Any, Optional
from pydantic import Field
from engine.registry.base_tool import BaseTool

logger = logging.getLogger(__name__)

class LogMonitorTool(BaseTool):
    """
    Reads the last N lines of the application log file.
    """
    name: str = "log_monitor"
    description: str = "Read the latest entries from the application log file for debugging."
    lines: int = Field(default=50, description="Number of recent log lines to retrieve.")
    log_file: str = Field(default="valh.log", description="Path to the log file.")

    async def execute(self, **kwargs) -> Any:
        num_lines = kwargs.get("lines", self.lines)
        log_path = kwargs.get("log_file", self.log_file)
        
        if not os.path.exists(log_path):
            return {
                "status": "error", 
                "message": f"Log file not found at {log_path}. Ensure logging is configured to write to a file."
            }
            
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                # Efficiently get last N lines
                all_lines = f.readlines()
                last_lines = all_lines[-num_lines:]
                return {
                    "status": "success",
                    "log_path": os.path.abspath(log_path),
                    "entries": "".join(last_lines),
                    "count": len(last_lines)
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}
