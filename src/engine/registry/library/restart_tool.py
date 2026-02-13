import os
import sys
import logging
from engine.registry.base_tool import BaseTool

logger = logging.getLogger(__name__)

class ValHRestartTool(BaseTool):
    """
    Triggers a graceful shutdown of ValH. 
    When combined with the Resurrector script, this effectively restarts the agent
    to apply updates or refresh the tool registry.
    """
    name: str = "restart_valh"
    description: str = "Restarts the ValH system to apply new tools or updates."

    async def execute(self, **kwargs) -> str:
        logger.info("🚀 Restart command received. Shutting down for resurrection...")
        
        # We use a slight delay to allow the response to reach the user before the process dies
        def trigger_restart():
            import time
            time.sleep(1)
            # Exit with 0 so the Resurrector knows it was a graceful update request
            os._exit(0)

        import threading
        threading.Thread(target=trigger_restart).start()

        return "Initiating restart... I'll be back in a few seconds with my new abilities active. 🦾"
