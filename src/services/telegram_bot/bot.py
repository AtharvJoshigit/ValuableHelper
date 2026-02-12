from functools import wraps
import os
import html
import logging
import asyncio
import time
from typing import Dict, Optional
from infrastructure.command_bus import CommandBus
from infrastructure.singleton import Singleton
from src.domain.event import Event, EventType
from telegram import InlineKeyboardMarkup, Update, constants
from telegram.error import BadRequest, TimedOut, NetworkError, RetryAfter
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.services.notification_service import notification_service
from src.services.telegram_bot.config import AUTHORIZED_USERS

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global State
_task_store = Singleton.get_task_store()

# Tracks the LAST message ID sent by the bot for a given chat.
_bot_messages: Dict[int, int] = {}
# Track typing tasks
_typing_tasks: Dict[int, asyncio.Task] = {}

# Rate limiting state
_last_update_time: Dict[int, float] = {}
UPDATE_INTERVAL = 1.0  # Seconds between edits

def authorized_only(func):
    @wraps(func)
    async def wrapped(self, *args, **kwargs):
        # Handle both (update, context) and (self, update, context)
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
    def __init__(self, token: str, bus: CommandBus):
        self.token = token
        self.application: Optional[Application] = None
        self.bus = bus

    async def start(self):
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN not found.")
            return

        self.application = ApplicationBuilder().token(self.token).build()

        # Command Handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("reset", self.reset_command))
        self.application.add_handler(CommandHandler("tasks", self.tasks_command))
        
        # Message Handler
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        # Callback Handler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        # Register with notification service
        notification_service.set_application(self.application)

        await self.application.initialize()
        await self.application.start()
        
        await self.application.updater.start_polling(
            poll_interval=1.0,
            timeout=10,
            read_timeout=20,
            write_timeout=20
        )
        logger.info("🤖 Telegram Polling Active")

    async def stop(self):
        if self.application:
            # Cancel all typing tasks
            for task in _typing_tasks.values():
                task.cancel()
            _typing_tasks.clear()
            
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

    async def _typing_loop(self, chat_id):
        """Sends the typing action every 4 seconds until cancelled."""
        try:
            while True:
                if self.application:
                    await self.application.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
                await asyncio.sleep(4) 
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Typing loop error: {e}")

    async def send_or_edit(
        self,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        is_final: bool = False
    ):
        if not self.application:
            return

        bot = self.application.bot
        safe_text = text.strip()
        
        # If text is empty and it's final, we might want to just stop typing
        if not safe_text and is_final:
            if chat_id in _typing_tasks:
                _typing_tasks[chat_id].cancel()
                del _typing_tasks[chat_id]
            return
            
        if not safe_text: return 

        # Cancel typing if we are sending a substantial update or finishing
        if is_final or len(safe_text) > 50:
            if chat_id in _typing_tasks:
                _typing_tasks[chat_id].cancel()
                del _typing_tasks[chat_id]

        # Truncate if too long
        if len(safe_text) > 4000:
            safe_text = safe_text[:4000] + "\n...(truncated)"

        # Rate Limiting Logic:
        # If this is NOT the final message, and we edited recently, SKIP this update.
        now = time.time()
        last_time = _last_update_time.get(chat_id, 0)
        
        if not is_final and (now - last_time) < UPDATE_INTERVAL:
            # Skip update to prevent flood limits
            return

        # Determine parse mode
        parse_mode = constants.ParseMode.HTML if is_final else None

        # Logic: If we haven't sent a message in this "turn", send a new one.
        # Otherwise, edit the existing one.
        if chat_id not in _bot_messages:
            try:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=safe_text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
                _bot_messages[chat_id] = msg.message_id
                _last_update_time[chat_id] = now
            except Exception as e:
                logger.error(f"Error sending new message: {e}")
            return

        # Edit existing message
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=_bot_messages[chat_id],
                text=safe_text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            _last_update_time[chat_id] = now
            
        except RetryAfter as e:
            logger.warning(f"Rate limited by Telegram. Sleeping {e.retry_after}s")
            if is_final:
                await asyncio.sleep(e.retry_after)
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=_bot_messages[chat_id],
                        text=safe_text,
                        parse_mode=parse_mode,
                        reply_markup=reply_markup,
                    )
                except Exception:
                    pass

        except BadRequest as e:
            if "message is not modified" in str(e):
                return
            if "can't parse entities" in str(e):
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=_bot_messages[chat_id],
                        text=safe_text,
                        parse_mode=None,
                        reply_markup=reply_markup,
                    )
                except Exception:
                    pass
        except (TimedOut, NetworkError):
            logger.warning("Telegram network issue during edit - ignoring.")

    @authorized_only
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if chat_id in _bot_messages: del _bot_messages[chat_id]
        await update.message.reply_text("Hi! I'm your engineering partner. Let's get to work.")

    @authorized_only
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        await self.bus.send(Event(
            type=EventType.USER_MESSAGE,
            payload={
                "chat_id": chat_id,
                "text": "System: Please reset my session memory."
            },
            source="telegram"
        ))
        
        if chat_id in _bot_messages: del _bot_messages[chat_id]
        await update.message.reply_text("🔄 Session reset request sent.")

    @authorized_only
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        text = update.message.text
        if chat_id in _bot_messages:
            del _bot_messages[chat_id]
            
        logger.info(f"Received message from {chat_id}")
        if chat_id not in _typing_tasks:
            _typing_tasks[chat_id] = asyncio.create_task(self._typing_loop(chat_id))
        
        await self.bus.send(Event(
            type=EventType.USER_MESSAGE,
            payload={
                "chat_id": chat_id,
                "text": text
            },
            source="telegram"
        ))

    @authorized_only
    async def tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if chat_id in _bot_messages: del _bot_messages[chat_id]

        try:
            pending = _task_store.list_tasks(status=["todo", "in_progress", "blocked", "waiting_approval", "waiting_review"])
            if not pending:
                await update.message.reply_text("✅ All clear!", parse_mode=constants.ParseMode.HTML)
                return
            
            response = "📋 <b>Current Tasks</b>\n\n"
            for task in pending:
                emoji = {"todo": "⏳", "in_progress": "🔄", "blocked": "⚠️", "waiting_approval": "👀", "waiting_review": "🔎"}.get(task.status, "•")
                response += f"{emoji} <b>{html.escape(task.title)}</b>\n   Status: {task.status}\n\n"
            
            await update.message.reply_text(response, parse_mode=constants.ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error fetching tasks: {e}")
            await update.message.reply_text("❌ Error fetching tasks.")

    @authorized_only
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        task_id = None
        approved = False
        
        if data.startswith("approve_task:"):
            task_id = data.split(":")[1]
            approved = True
        elif data.startswith("deny_task:"):
            task_id = data.split(":")[1]
            approved = False
        else:
            # Fallback for generic approval
            approved = (data == "approve")

        await self.bus.send(Event(
            type=EventType.USER_APPROVAL,
            payload={
                "chat_id": query.message.chat_id,
                "approved": approved,
                "task_id": task_id
            },
            source="telegram"
        ))
