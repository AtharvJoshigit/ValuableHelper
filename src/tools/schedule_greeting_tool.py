import asyncio
import logging
from engine.registry.base_tool import BaseTool
from pydantic import Field

logger = logging.getLogger(__name__)

class DelayedGreetingTool(BaseTool):
    """
    Schedules a background task to print a greeting after a delay.
    """
    name: str = "schedule_greeting"
    description: str = "Schedules a 'Hi' message after a specified delay."
    delay_seconds: int = Field(180, description="Delay in seconds.")

    async def execute(self, **kwargs) -> str:
        delay = kwargs.get("delay_seconds", 180)
        async def delayed_hi():
            await asyncio.sleep(delay)
            # In a real scenario, we'd use the telegram bot to send this.
            # For this test, we log it and print it.
            print(f"\n--- [VALH] --- Hi Atharv! 3 minutes are up. \n")
            logger.info("Delayed greeting executed.")

        asyncio.create_task(delayed_hi())
        return f"Clock started. I'll drop a 'Hi' in the console in {delay} seconds."
