
import asyncio
import logging
import html
from typing import List, Dict, Any
from src.domain.event import Event, EventType
from src.infrastructure.event_bus import EventBus
from src.tools.gmail_tool import GmailSearchTool

logger = logging.getLogger(__name__)

class ProactiveObserver:
    """
    The Autonomous Eye of ValH.
    Listens for Heartbeat events and executes proactive checks.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProactiveObserver, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.event_bus = EventBus()
        self.gmail_tool = GmailSearchTool()
        self.last_check_results = {}
        self._initialized = True
        
        # Subscribe to the heartbeat
        self.event_bus.subscribe(EventType.HEARTBEAT, self.on_heartbeat)
        logger.info("ProactiveObserver initialized and subscribed to HEARTBEAT.")

    async def on_heartbeat(self, event: Event):
        """Triggered every time the pulse fires."""
        logger.info("💓 Observer received heartbeat. Running proactive checks...")
        
        # We run these in background tasks so they don't block the bus
        asyncio.create_task(self.check_gmail())

    async def check_gmail(self):
        """Check for unread emails and notify if new ones arrive."""
        try:
            # GmailSearchTool.execute is synchronous in the current codebase
            # We wrap it in run_in_executor or just call it if we're in a task
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self.gmail_tool.execute(query="is:unread", limit=5))
            
            if isinstance(result, dict) and result.get("status") == "success":
                emails = result.get("results", [])
                if emails:
                    count = len(emails)
                    logger.info(f"📬 Proactive Check: Found {count} unread emails.")
                    
                    from src.services.notification_service import get_notification_service
                    notifier = get_notification_service()
                    
                    msg = f"📬 <b>Proactive Gmail Alert</b>\nYou have {count} unread emails.\n"
                    for em in emails[:3]:
                        # Escape HTML characters to prevent Telegram parse errors
                        safe_from = html.escape(em['from'])
                        safe_subject = html.escape(em['subject'])
                        msg += f"\n• From: {safe_from}\n  Subj: {safe_subject}"
                    
                    await notifier.send_custom_notification(msg)
            
        except Exception as e:
            logger.error(f"Error in Proactive Gmail check: {e}")

# Global instance initialization
def init_proactive_observer():
    return ProactiveObserver()
