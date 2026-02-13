
from engine.registry.base_tool import BaseTool
from src.infrastructure.event_bus import EventBus
from src.domain.event import Event, EventType
from src.services.proactive_observer import init_proactive_observer
import importlib
import src.domain.event
import logging

logger = logging.getLogger(__name__)

class PulseTriggerToolV2(BaseTool):
    def __init__(self):
        super().__init__(
            name="pulse_trigger",
            description="Manually fires a SYSTEM HEARTBEAT event to trigger proactive observers."
        )

    async def execute(self):
        try:
            # Force reload the event domain to catch the new HEARTBEAT member
            importlib.reload(src.domain.event)
            from src.domain.event import EventType, Event
            
            # Initialize Observer
            init_proactive_observer()
            
            # Publish
            bus = EventBus()
            # If HEARTBEAT still fails, we'll use the string directly if pydantic allows, 
            # but EventType(str) should work.
            try:
                e_type = EventType.HEARTBEAT
            except AttributeError:
                e_type = "heartbeat" # Fallback
                
            event = Event(type=e_type, payload={"manual": True})
            bus.publish(event)
            
            return f"💓 Heartbeat pulse fired using type: {e_type}. Check Telegram for the Gmail alert!"
        except Exception as e:
            return f"Failed to fire pulse: {str(e)}"
