import json
import logging
import os
from datetime import datetime
from typing import Any, Dict

from src.domain.event import Event, EventType
from src.infrastructure.event_bus import EventBus

logger = logging.getLogger(__name__)

class FileEventLogger:
    """
    Subscribes to all events and writes them to a JSONL file.
    """
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, "events.jsonl")
        self.bus = EventBus()
        self._subscribe_to_all()
        logger.info(f"📝 FileEventLogger initialized. Writing to {self.log_file}")

    def _subscribe_to_all(self):
        """Subscribe to all defined EventTypes."""
        for event_type in EventType:
            self.bus.subscribe(event_type, self.log_event)

    async def log_event(self, event: Event):
        """
        Handler that writes the event to the file.
        """
        try:
            # Convert to dict and handle datetime serialization
            event_dict = event.model_dump()
            event_dict['timestamp'] = event.timestamp.isoformat()
            
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_dict) + "\n")
        except Exception as e:
            logger.error(f"Failed to log event to file: {e}")
