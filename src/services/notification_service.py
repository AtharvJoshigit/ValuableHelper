
import asyncio
from threading import Lock
from typing import Any, Dict, Optional, List

from app.app_context import get_app_context

from src.domain.event import Event, EventType
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
            self._publisher = get_app_context().event_bus
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

    async def _send_message_to_admins(self, message: str, reply_markup=None) -> None:
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
                await app.bot.send_message(
                    chat_id=user_id, 
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Error sending notification to {user_id}: {e}")

    async def _handle_task_status_change(self, event: Event) -> None:
        payload = event.payload
        task_id = payload.get('task_id', 'N/A')
        new_status = payload.get('new_status')
        message = f"🔄 <b>Task Status Update</b>\nID: <code>{task_id}</code>\nStatus: {new_status}"
        await self._send_message_to_admins(message)

    async def _handle_task_created(self, event: Event) -> None:
        payload = event.payload
        title = payload.get('title', 'N/A')
        message = f"🆕 <b>New Task</b>\n{title}"
        await self._send_message_to_admins(message)

    async def _handle_task_failed(self, event: Event) -> None:
        payload = event.payload
        title = payload.get('title', 'N/A')
        message = f"❌ <b>Task Failed</b>\n{title}"
        result = payload.get('result_summary')
        if result:
             message += f"\nReason: {result}"
        await self._send_message_to_admins(message)

    async def _handle_task_completed(self, event: Event) -> None:
        payload = event.payload
        title = payload.get('title', 'N/A')
        message = f"✅ <b>Task Completed</b>\n{title}"
        await self._send_message_to_admins(message)

    async def send_custom_notification(self, message: str) -> None:
        """Sends a custom message to all admins."""
        await self._send_message_to_admins(message)

    async def send_approval_request(self, task_id: str, title: str, tools: List[str]) -> None:
        """Sends a message with Approve/Deny buttons to admins."""
        if not self._application: return
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        tools_str = ", ".join(tools)
        text = (
            f"⚠️ <b>Approval Needed</b>\n"
            f"Task: {title}\n"
            f"Action: Agent wants to use <b>{tools_str}</b>.\n\n"
            f"Allow this?"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_task:{task_id}"),
                InlineKeyboardButton("❌ Deny", callback_data=f"deny_task:{task_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self._send_message_to_admins(text, reply_markup=reply_markup)

    async def send_plan_approval_request(self, parent_id: str, title: str, subtasks_count: int) -> None:
        """Sends a specific notification for plan approval."""
        if not self._application: return
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        text = (
            f"📋 <b>Plan Review Needed</b>\n"
            f"Parent: {title}\n"
            f"Structure: {subtasks_count} subtasks generated.\n\n"
            f"Approve this execution plan?"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve Plan", callback_data=f"approve_task:{parent_id}"),
                InlineKeyboardButton("❌ Reject Plan", callback_data=f"deny_task:{parent_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self._send_message_to_admins(text, reply_markup=reply_markup)

# Singleton instance
def get_notification_service() : 
    return NotificationService()
