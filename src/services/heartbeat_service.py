import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from app.app_context import get_app_context
from domain.event import Event, EventType

logger = logging.getLogger(__name__)

class HeartbeatService:
    """
    The Pulse of ValH.
    Publishes HEARTBEAT events at a configurable interval.
    This allows the system to perform periodic self-maintenance or checks.
    """

    def __init__(self, interval_minutes: int = 30):
        self.interval_seconds = interval_minutes * 60
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self.command_bus = get_app_context().command_bus

    async def start(self):
        """Start the heartbeat loop."""
        if self.running:
            return
        
        self.running = True
        self._task = asyncio.create_task(self._loop(), name="heartbeat_service")
        logger.info(f"💓 Heartbeat Service started (Interval: {self.interval_seconds/60}m)")

    async def stop(self):
        """Stop the heartbeat loop."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("💔 Heartbeat Service stopped")

    async def _loop(self):
        """The main pulse loop."""
        while self.running:
            try:
                # Wait for the interval
                await asyncio.sleep(self.interval_seconds)
                
                # Publish Heartbeat Event
                event = Event(
                    type=EventType.HEARTBEAT,
                    payload={
                        "timestamp": datetime.now().isoformat(),
                        "source": "heartbeat_service",
                        "instruction": "Perform system health check and maintenance if needed."
                    },
                    source="system_heartbeat"
                )
                
                await self.command_bus.send(event)
                logger.debug("💓 Thump-thump (Heartbeat event published)")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Heartbeat loop: {e}", exc_info=True)
                # Wait a bit before retrying to avoid rapid error loops
                await asyncio.sleep(60)
