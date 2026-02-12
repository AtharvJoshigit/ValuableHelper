import asyncio
import logging
from engine.registry.tool_registry import tool

logger = logging.getLogger(__name__)

class DelayedGreetingTool:
    @tool
    async def schedule_greeting(self, delay_seconds: int = 180):
        \"\"\"
        Schedules a background task to print a greeting after a delay.
        \"\"\"
        async def delayed_hi():
            await asyncio.sleep(delay_seconds)
            # This will appear in the logs/console since we don't have a 
            # direct "push" to the user message history without a bot session
            logger.info(f"--- [CRON GREETING] --- Hi Boss! It has been {delay_seconds} seconds.")
            print(f"\\n--- [CRON GREETING] --- Hi Boss! It has been {delay_seconds} seconds.\\n")

        asyncio.create_task(delayed_hi())
        return f"Greeting scheduled in {delay_seconds} seconds. Keep an eye on the logs or console."
