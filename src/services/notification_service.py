
import asyncio
from threading import Lock
from typing import Any, Dict, Optional

from src.domain.event import Event, EventType
from src.infrastructure.event_bus import EventBus
from src.domain.task import Task
from src.services.telegram_bot.config import ADMIN_USER_IDS


class NotificationService:
    _instance: Optional["NotificationService"] = None
    _lock = Lock()

    def __new__(cls) -> "NotificationService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._application = None
            self._publisher = EventBus()
            self._subscribe_to_events()

    def set_application(self, app):
        """Sets the Telegram application instance."""
        self._application = app
    
    
    
    def _subscribe_to_events(self) -> None:
        """Subscribes to relevant task-related events."""
        self._publisher.subscribe(EventType.TASK_STATUS_CHANGED, self._handle_task_status_change)
        self._publisher.subscribe(EventType.TASK_CREATED, self._handle_task_created)
        self._publisher.subscribe(EventType.TASK_FAILED, self._handle_task_failed)
        self._publisher.subscribe(EventType.TASK_COMPLETED, self._handle_task_completed)

    async def _send_message_to_admins(self, message: str) -> None:
        """Sends a message to all configured admin user IDs."""
        app = self._application
        if not app:
            print("Warning: Telegram application not available. Cannot send notification.")
            return

        if not ADMIN_USER_IDS:
            print("Warning: No ADMIN_USER_IDS configured. Cannot send notification.")
            return

        for user_id in ADMIN_USER_IDS:
            try:
                await app.bot.send_message(chat_id=user_id, text=message)
            except Exception as e:
                print(f"Error sending notification to {user_id}: {e}")

    async def _handle_task_status_change(self, event: Event) -> None:
        payload = event.payload
        task_id = payload.get('description') or payload.get('title', 'N/A') 
        new_status = payload.get('new_status')
        message = f"🔄 Task status changed for task {task_id}: {event.type}"
        await self._send_message_to_admins(message)

    async def _handle_task_created(self, event: Event) -> None:
        payload = event.payload
        description = payload.get('description') or payload.get('title', 'N/A')
        message = f"🆕 New task created: '{description}'"
        await self._send_message_to_admins(message)

    async def _handle_task_failed(self, event: Event) -> None:
        payload = event.payload
        description = payload.get('description') or payload.get('title', 'N/A')
        message = f"❌ Task failed: '{description}'"
        result = payload.get('result')
        if result:
             message += f"\nReason: {result}"
        await self._send_message_to_admins(message)

    async def _handle_task_completed(self, event: Event) -> None:
        payload = event.payload
        description = payload.get('description') or payload.get('title', 'N/A')
        message = f"✅ Task completed: '{description}'"
        await self._send_message_to_admins(message)

    async def send_custom_notification(self, message: str) -> None:
        """Sends a custom message to all admins."""
        await self._send_message_to_admins(message)

# Singleton instance
notification_service = NotificationService()
