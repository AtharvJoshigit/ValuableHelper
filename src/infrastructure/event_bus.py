import asyncio
import logging
from typing import Callable, Dict, List, Awaitable
from src.domain.event import Event, EventType

logger = logging.getLogger(__name__)

# Type alias for event handlers: async function that takes an Event
EventHandler = Callable[[Event], Awaitable[None]]

class EventBus:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.subscribers: Dict[EventType, List[EventHandler]] = {}
        return cls._instance

    def subscribe(self, event_type: EventType, handler: EventHandler):
        """Register an async handler for a specific event type."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.info(f"Subscribed {handler.__name__} to {event_type}")

    def publish(self, event: Event):
        """
        Publish an event asynchronously.
        This method is non-blocking and schedules handlers as background tasks.
        """
        if event.type not in self.subscribers:
            return

        for handler in self.subscribers[event.type]:
            # Create a background task for each handler
            asyncio.create_task(self._run_handler(handler, event))

    async def _run_handler(self, handler: EventHandler, event: Event):
        """Wrapper to run handler and catch exceptions."""
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Error handling event {event.type} in {handler.__name__}: {e}", exc_info=True)