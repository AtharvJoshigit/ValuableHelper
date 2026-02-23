from functools import wraps
import os
import html
import logging
import asyncio
import time
from typing import Dict, Optional
from app.app_context import get_app_context
from infrastructure.command_bus import CommandBus
from infrastructure.singleton import Singleton
from domain.event import Event, EventType
from telegram import InlineKeyboardMarkup, Update, constants
from telegram.request import HTTPXRequest
from telegram.error import BadRequest, TimedOut, NetworkError, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

from services.notification_service import get_notification_service
from services.telegram_bot.config import AUTHORIZED_USERS

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global State
_bot_messages: Dict[int, int] = {}
_typing_tasks: Dict[int, asyncio.Task] = {}
_status_messages: Dict[int, int] = {} # chat_id -> status_message_id
_last_update_time: Dict[int, float] = {}
UPDATE_INTERVAL = 1.0  # Seconds between edits

MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5  # seconds


def authorized_only(func):
    @wraps(func)
    async def wrapped(self, *args, **kwargs):
        update = next((arg for arg in args if isinstance(arg, Update)), None)
        if not update or not update.effective_user:
            return await func(self, *args, **kwargs)

        user_id = update.effective_user.id
        if user_id not in AUTHORIZED_USERS:
            logger.warning(f"Unauthorized access attempt: {user_id}")
            if update.message:
                await update.message.reply_text("🚫 Access Denied.")
            return
        return await func(self, *args, **kwargs)
    return wrapped


class TelegramBotService:
    def __init__(self, token: str):
        self.token = token
        self.application: Optional[Application] = None
        self.bus = get_app_context().command_bus
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start the telegram bot service"""
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN not found.")
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        if self._running:
            return

        self._running = True
        attempt = 0

        while self._running and attempt < MAX_RECONNECT_ATTEMPTS:
            try:
                await self._initialize_bot()
                await self._start_polling()
                logger.info("🤖 Telegram Bot Started Successfully")
                await self._shutdown_event.wait()
                break
            except Exception as e:
                attempt += 1
                logger.error(f"Error starting bot (attempt {attempt}/{MAX_RECONNECT_ATTEMPTS}): {e}")
                if attempt < MAX_RECONNECT_ATTEMPTS and self._running:
                    await asyncio.sleep(RECONNECT_DELAY)
                else:
                    raise

    async def _initialize_bot(self):
        request = HTTPXRequest(connection_pool_size=20, read_timeout=30.0, write_timeout=30.0)
        self.application = ApplicationBuilder().token(self.token).request(request).build()

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("reset", self.reset_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        notification_service = get_notification_service()
        notification_service.set_application(self.application)

        await self.application.initialize()
        await self.application.start()

    async def _start_polling(self):
        await self.application.updater.start_polling(drop_pending_updates=False)

    async def stop(self):
        if not self._running: return
        self._running = False
        self._shutdown_event.set()
        
        for chat_id in list(_typing_tasks.keys()):
            self._cancel_typing(chat_id)
        
        if self.application:
            await self.application.stop()
            await self.application.shutdown()

    # --- Core Messaging API ---
    def safe_text(self, text: str) -> str: 
        if len(text) > 4000:
            return text[:3950] + "\n\n...(message truncated)"
        return text
        
        
    async def send_message(self, chat_id: int, text: str, parse_mode=None, reply_markup=None) -> Optional[int]:
        """Send a new message and return its ID"""
        if not self.application: return None
        try:
            msg = await self.application.bot.send_message(
                chat_id=chat_id,
                text=self.safe_text(text),
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            _bot_messages[chat_id] = msg.message_id
            return msg.message_id
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None

    async def edit_message(self, chat_id: int, message_id: int, text: str, parse_mode=None, reply_markup=None) -> bool:
        """Edit an existing message with rate limit handling"""
        if not self.application: return False
        
        now = time.time()
        if (now - _last_update_time.get(message_id, 0)) < UPDATE_INTERVAL:
            return False # Skip too-frequent edits

        try:
            await self.application.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=self.safe_text(text),
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            _last_update_time[message_id] = now
            return True
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            return await self.edit_message(chat_id, message_id, text, parse_mode, reply_markup)
        except BadRequest as e:
            if "message is not modified" in str(e).lower(): return True
            logger.warning(f"Edit failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected edit error: {e}")
            return False

    async def delete_message(self, chat_id: int, message_id: int):
        """Delete a message"""
        if not self.application: return
        try:
            await self.application.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass

    # --- Dashboard & Status API ---

    async def update_status(self, chat_id: int, status_text: str):
        """Updates or creates the system status dashboard message."""
        if not self.application: return
        
        formatted_text = f"⚙️ <b>System:</b> {status_text}"
        
        if chat_id in _status_messages:
            msg_id = _status_messages[chat_id]
            success = await self.edit_message(chat_id, msg_id, formatted_text, parse_mode=constants.ParseMode.HTML)
            if success: return

        msg_id = await self.send_message(chat_id, formatted_text, parse_mode=constants.ParseMode.HTML)
        if msg_id:
            _status_messages[chat_id] = msg_id

    async def cleanup(self, chat_id: int):
        """Stops typing and removes the status dashboard."""
        self._cancel_typing(chat_id)
        if chat_id in _status_messages:
            await self.delete_message(chat_id, _status_messages[chat_id])
            del _status_messages[chat_id]

    # --- Handlers ---

    async def _typing_loop(self, chat_id: int):
        try:
            while True:
                if self.application and self._running:
                    await self.application.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
                await asyncio.sleep(4)
        except asyncio.CancelledError: pass

    def _cancel_typing(self, chat_id: int):
        if chat_id in _typing_tasks:
            if not _typing_tasks[chat_id].done(): _typing_tasks[chat_id].cancel()
            del _typing_tasks[chat_id]

    @authorized_only
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Hi! I'm ValH. Let's build something.")

    @authorized_only
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.bus.send(Event(EventType.USER_MESSAGE, {"chat_id": update.effective_chat.id, "text": "System: Reset session."}, "telegram"))
        await update.message.reply_text("🔄 Resetting...")

    @authorized_only
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if chat_id not in _typing_tasks or _typing_tasks[chat_id].done():
            _typing_tasks[chat_id] = asyncio.create_task(self._typing_loop(chat_id))
        
        await self.bus.send(
            Event(
                type=EventType.USER_MESSAGE, 
                payload={"chat_id": chat_id, "text": update.message.text}, 
                source="telegram"
            )
        )

    @authorized_only
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        approved = "approve" in data
        task_id = data.split(":", 1)[1] if ":" in data else None
        await self.bus.send(
            Event(
                type=EventType.USER_APPROVAL, 
                payload={"chat_id": query.message.chat_id, "approved": approved, "task_id": task_id},
                source="telegram"
            )
        )

    def is_running(self) -> bool: return self._running
