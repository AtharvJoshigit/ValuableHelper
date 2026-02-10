from functools import wraps
import os
import html
import logging
import asyncio
import time
import json
from typing import Dict, List, Optional
from agents.agent_id import AGENT_ID
from domain.event import Event, EventType
from engine.core import agent_instance_manager
from infrastructure.command_bus import CommandBus
from infrastructure.singleton import Singleton
from services.task_store import EventBus
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.error import BadRequest, TimedOut, NetworkError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

from engine.core.types import StreamChunk
from src.services.notification_service import notification_service
from src.services.telegram_bot.config import AUTHORIZED_USERS

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global State (In-Memory)
user_sessions: Dict[int, object] = {} # ChatID -> Agent Instance
user_locks: Dict[int, asyncio.Lock] = {} # ChatID -> Lock
_task_store = Singleton.get_task_store()
command_bus = CommandBus()

# Tracks the LAST message ID sent by the bot for a given chat.
# Used to determine if we should edit the existing message (streaming) or send a new one.
_bot_messages: Dict[int, int] = {}

def authorized_only(func):
    @wraps(func)
    async def wrapped(*args, **kwargs):
        update = next((arg for arg in args if isinstance(arg, Update)), None)

        if not update or not update.effective_user:
            return await func(*args, **kwargs)

        user_id = update.effective_user.id

        if user_id not in AUTHORIZED_USERS:
            logger.warning(f"Unauthorized access attempt: {user_id}")
            if update.message:
                await update.message.reply_text("🚫 Access Denied.")
            return

        return await func(*args, **kwargs)
    return wrapped

class TelegramBotService:
    def __init__(self, token: str, bus):
        self.token = token
        self.application: Optional[Application] = None
        self._is_running = False
        self.bus = bus

    async def start(self):
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN not found.")
            return

        # Increase connection pool limits/timeouts if needed via request=... 
        # For now, we'll stick to default builder but tweak polling.
        self.application = ApplicationBuilder().token(self.token).build()

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("reset", self.reset_command))
        self.application.add_handler(CommandHandler("tasks", self.tasks_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        notification_service.set_application(self.application)

        # ✅ NON-blocking polling with increased robustness
        await self.application.initialize()
        await self.application.start()
        
        # Explicit timeouts to help with "Connection Timed Out" logs
        await self.application.updater.start_polling(
            poll_interval=1.0,     # Check for updates every 1s
            timeout=10,            # Long-polling timeout
            read_timeout=20,       # Socket read timeout (must be > timeout)
            write_timeout=20       # Socket write timeout
        )
        logger.info("🤖 Telegram Polling Active")

    async def stop(self):
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

    async def send_or_edit(
        self,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ):
        if not self.application:
            return

        bot = self.application.bot
        
        safe_text = text.strip()
        if not safe_text: return 

        if len(safe_text) > 4000:
             safe_text = safe_text[:4000] + "\n...(truncated)"

        # New message logic
        # If we don't have a tracked message for this chat, OR if the tracked message is invalid, send NEW.
        if chat_id not in _bot_messages:
            try:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=safe_text,
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=reply_markup,
                )
                _bot_messages[chat_id] = msg.message_id
            except Exception as e:
                logger.error(f"Error sending message: {e}")
            return

        # Edit logic
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=_bot_messages[chat_id],
                text=safe_text,
                parse_mode=constants.ParseMode.HTML,
                reply_markup=reply_markup,
            )
        except BadRequest as e:
            if "message is not modified" in str(e):
                return
            
            # If edit fails (e.g. message too old, or deleted by user), send NEW and update tracker
            logger.warning(f"Edit failed ({e}), sending new message.")
            try:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=safe_text,
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=reply_markup,
                )
                _bot_messages[chat_id] = msg.message_id
            except Exception as send_e:
                logger.error(f"Error sending fallback message: {send_e}")
        except TimedOut:
            logger.warning("Telegram TimedOut during edit - ignoring.")
        except NetworkError:
            logger.warning("Telegram NetworkError during edit - ignoring.")

    @authorized_only
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Reset tracker on start
        chat_id = update.effective_chat.id
        if chat_id in _bot_messages: del _bot_messages[chat_id]
        await update.message.reply_text("Hi! I'm your engineering partner. Let's get to work.")

    @authorized_only
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if chat_id in user_sessions:
            del user_sessions[chat_id]
        if 'chunks' in context.user_data:
            del context.user_data['chunks']
        
        # Clear message tracker so next msg is new
        if chat_id in _bot_messages: del _bot_messages[chat_id]
            
        await update.message.reply_text("Memory wiped. Starting fresh.")

    @authorized_only
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        text = update.message.text
        
        # CRITICAL FIX: User sent a NEW message. 
        # We must forget the previous bot response so we reply with a NEW message.
        if chat_id in _bot_messages:
            del _bot_messages[chat_id]
            
        logger.info(f"Received message from {chat_id}")
        
        await self.bus.send(Event(
            type=EventType.USER_MESSAGE,
            payload={
                "chat_id": chat_id,
                "text": text
            },
            source="telegram"
        ))
        
        await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)

    @authorized_only
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        # Force new message for stats
        if chat_id in _bot_messages: del _bot_messages[chat_id]
            
        if chat_id not in user_sessions:
            await update.message.reply_text("No active session.", parse_mode=constants.ParseMode.HTML)
            return
        
        agent = self.get_or_create_agent(chat_id)
        msg_count = getattr(agent, 'message_count', 'N/A')
        tool_count = getattr(agent, 'tool_call_count', 'N/A')
        
        stats_text = f"""📊 <b>Session Stats</b>\n\n💬 Messages: {msg_count}\n🛠️ Tools: {tool_count}"""
        await update.message.reply_text(stats_text, parse_mode=constants.ParseMode.HTML)

    @authorized_only
    async def tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        # Force new message for tasks
        if chat_id in _bot_messages: del _bot_messages[chat_id]

        try:
            pending = _task_store.list_tasks(status=["todo", "in_progress", "blocked", "waiting_approval"])
            if not pending:
                await update.message.reply_text("✅ All clear!", parse_mode=constants.ParseMode.HTML)
                return
            
            response = "📋 <b>Current Tasks</b>\n\n"
            for task in pending:
                emoji = {"todo": "⏳", "in_progress": "🔄", "blocked": "⚠️", "waiting_approval": "👀"}.get(task.status, "•")
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

        if query.data in ["approve", "deny"]:
            await self.bus.send(Event(
                type=EventType.USER_APPROVAL,
                payload={
                    "chat_id": query.message.chat_id,
                    "approved": query.data == "approve"
                },
                source="telegram"
            ))
