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
from src.domain.event import Event, EventType
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

from src.services.notification_service import get_notification_service
from src.services.telegram_bot.config import AUTHORIZED_USERS

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global State
# _task_store = Singleton.get_task_store()

# Tracks the LAST message ID sent by the bot for a given chat.
_bot_messages: Dict[int, int] = {}
# Track typing tasks
_typing_tasks: Dict[int, asyncio.Task] = {}

# Rate limiting state
_last_update_time: Dict[int, float] = {}
UPDATE_INTERVAL = 1.0  # Seconds between edits

# Reconnection settings
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5  # seconds


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
    def __init__(self, token: str):
        self.token = token
        self.application: Optional[Application] = None
        self.bus = get_app_context().command_bus
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._polling_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the telegram bot service with error handling and reconnection logic"""
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN not found.")
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        if self._running:
            logger.warning("Bot service already running")
            return

        self._running = True
        attempt = 0

        while self._running and attempt < MAX_RECONNECT_ATTEMPTS:
            try:
                await self._initialize_bot()
                await self._start_polling()
                logger.info("🤖 Telegram Bot Started Successfully")
                
                # Wait for shutdown signal
                await self._shutdown_event.wait()
                break
                
            except Exception as e:
                attempt += 1
                logger.error(f"Error starting bot (attempt {attempt}/{MAX_RECONNECT_ATTEMPTS}): {e}", exc_info=True)
                
                if attempt < MAX_RECONNECT_ATTEMPTS and self._running:
                    logger.info(f"Retrying in {RECONNECT_DELAY} seconds...")
                    await asyncio.sleep(RECONNECT_DELAY)
                else:
                    logger.critical("Max reconnection attempts reached. Bot service failed to start.")
                    raise

    async def _initialize_bot(self):
        """Initialize the telegram application and handlers"""
        request = HTTPXRequest(
            connection_pool_size=20,
            read_timeout=30.0,
            write_timeout=30.0,
            connect_timeout=30.0,
            pool_timeout=30.0
        )

        self.application = (
            ApplicationBuilder()
            .token(self.token)
            .request(request)
            .build()
        )

        # Command Handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("reset", self.reset_command))
        # self.application.add_handler(CommandHandler("tasks", self.tasks_command))
        
        # Message Handler
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        # Callback Handler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        # Register with notification service
        notification_service = get_notification_service()
        notification_service.set_application(self.application)

        # Initialize the application
        await self.application.initialize()
        await self.application.start()
        
        logger.info("✅ Telegram application initialized")

    async def _start_polling(self):
        """Start polling with proper error handling"""
        try:
            await self.application.updater.start_polling(
                poll_interval=1.0,
                timeout=10,
                read_timeout=20,
                write_timeout=20,
                drop_pending_updates=False,
                allowed_updates=Update.ALL_TYPES,
            )
            logger.info("🔄 Telegram Polling Active")
        except Exception as e:
            logger.error(f"Error starting polling: {e}", exc_info=True)
            raise

    async def stop(self):
        """Gracefully stop the bot service"""
        if not self._running:
            return
            
        logger.info("🛑 Stopping Telegram Bot Service...")
        self._running = False
        
        # Signal shutdown event
        self._shutdown_event.set()
        
        # Cancel all typing tasks
        for chat_id, task in list(_typing_tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        _typing_tasks.clear()
        
        # Stop the application
        if self.application:
            try:
                if self.application.updater.running:
                    await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                logger.info("✅ Telegram application stopped")
            except Exception as e:
                logger.error(f"Error during shutdown: {e}", exc_info=True)
        
        # Clear message tracking
        _bot_messages.clear()
        _last_update_time.clear()

    async def _typing_loop(self, chat_id: int):
        """Sends the typing action every 4 seconds until cancelled."""
        try:
            while True:
                if self.application and self._running:
                    try:
                        await self.application.bot.send_chat_action(
                            chat_id=chat_id, 
                            action=constants.ChatAction.TYPING
                        )
                    except TelegramError as e:
                        logger.debug(f"Typing action failed for chat {chat_id}: {e}")
                        break
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            logger.debug(f"Typing loop cancelled for chat {chat_id}")
        except Exception as e:
            logger.error(f"Typing loop error for chat {chat_id}: {e}", exc_info=True)
        finally:
            # Clean up the task reference
            if chat_id in _typing_tasks:
                del _typing_tasks[chat_id]

    def _cancel_typing(self, chat_id: int):
        """Cancel typing indicator for a specific chat"""
        if chat_id in _typing_tasks:
            task = _typing_tasks[chat_id]
            if not task.done():
                task.cancel()
            del _typing_tasks[chat_id]

    async def send_or_edit(
        self,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        is_final: bool = False
    ):
        """Send or edit a message with rate limiting and error handling"""
        if not self.application or not self._running:
            logger.warning("Cannot send message: bot not running")
            return

        bot = self.application.bot
        safe_text = text.strip()
        
        # If text is empty and it's final, stop typing
        if not safe_text and is_final:
            self._cancel_typing(chat_id)
            return
            
        if not safe_text:
            return

        # Cancel typing if we are sending a substantial update or finishing
        if is_final or len(safe_text) > 50:
            self._cancel_typing(chat_id)

        # Truncate if too long
        if len(safe_text) > 4000:
            safe_text = safe_text[:3950] + "\n\n...(message truncated)"

        # Rate Limiting Logic
        now = time.time()
        last_time = _last_update_time.get(chat_id, 0)
        
        if not is_final and (now - last_time) < UPDATE_INTERVAL:
            # Skip update to prevent flood limits
            return

        # Determine parse mode
        parse_mode = constants.ParseMode.HTML if is_final else None

        # Send new message or edit existing
        if chat_id not in _bot_messages:
            await self._send_new_message(chat_id, safe_text, parse_mode, reply_markup, now)
        else:
            await self._edit_existing_message(chat_id, safe_text, parse_mode, reply_markup, now, is_final)

    async def _send_new_message(
        self, 
        chat_id: int, 
        text: str, 
        parse_mode, 
        reply_markup, 
        timestamp: float
    ):
        """Send a new message"""
        try:
            msg = await self.application.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            _bot_messages[chat_id] = msg.message_id
            _last_update_time[chat_id] = timestamp
        except TelegramError as e:
            logger.error(f"Error sending new message to {chat_id}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error sending message to {chat_id}: {e}", exc_info=True)

    async def _edit_existing_message(
        self, 
        chat_id: int, 
        text: str, 
        parse_mode, 
        reply_markup, 
        timestamp: float,
        is_final: bool
    ):
        """Edit an existing message with retry logic"""
        try:
            await self.application.bot.edit_message_text(
                chat_id=chat_id,
                message_id=_bot_messages[chat_id],
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            _last_update_time[chat_id] = timestamp
            
        except RetryAfter as e:
            logger.warning(f"Rate limited by Telegram. Retry after {e.retry_after}s")
            if is_final:
                await asyncio.sleep(e.retry_after)
                try:
                    await self.application.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=_bot_messages[chat_id],
                        text=text,
                        parse_mode=parse_mode,
                        reply_markup=reply_markup,
                    )
                except Exception as retry_error:
                    logger.error(f"Retry edit failed: {retry_error}")

        except BadRequest as e:
            error_msg = str(e).lower()
            if "message is not modified" in error_msg:
                # Message content is identical, this is fine
                return
            elif "can't parse entities" in error_msg:
                # Retry without HTML parsing
                try:
                    await self.application.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=_bot_messages[chat_id],
                        text=text,
                        parse_mode=None,
                        reply_markup=reply_markup,
                    )
                except Exception as parse_error:
                    logger.error(f"Edit without parse mode failed: {parse_error}")
            elif "message to edit not found" in error_msg:
                # Message was deleted, send a new one
                logger.warning(f"Message {_bot_messages[chat_id]} not found, sending new message")
                del _bot_messages[chat_id]
                await self._send_new_message(chat_id, text, parse_mode, reply_markup, timestamp)
            else:
                logger.error(f"BadRequest editing message: {e}")
                
        except (TimedOut, NetworkError) as e:
            logger.warning(f"Telegram network issue during edit: {e}")
        except TelegramError as e:
            logger.error(f"Telegram error editing message: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error editing message: {e}", exc_info=True)

    @authorized_only
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            chat_id = update.effective_chat.id
            if chat_id in _bot_messages:
                del _bot_messages[chat_id]
            
            self._cancel_typing(chat_id)
            await update.message.reply_text("Hi! I'm your engineering partner. Let's get to work.")
        except Exception as e:
            logger.error(f"Error in start_command: {e}", exc_info=True)

    @authorized_only
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reset command"""
        try:
            chat_id = update.effective_chat.id
            
            await self.bus.send(Event(
                type=EventType.USER_MESSAGE,
                payload={
                    "chat_id": chat_id,
                    "text": "System: Please reset my session memory."
                },
                source="telegram"
            ))
            
            if chat_id in _bot_messages:
                del _bot_messages[chat_id]
            
            self._cancel_typing(chat_id)
            await update.message.reply_text("🔄 Session reset request sent.")
        except Exception as e:
            logger.error(f"Error in reset_command: {e}", exc_info=True)
            await update.message.reply_text("❌ Error resetting session. Please try again.")

    @authorized_only
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming user messages"""
        try:
            chat_id = update.effective_chat.id
            text = update.message.text
            
            if chat_id in _bot_messages:
                del _bot_messages[chat_id]
            
            logger.info(f"Received message from {chat_id}: {text[:50]}...")
            
            # Start typing indicator
            if chat_id not in _typing_tasks or _typing_tasks[chat_id].done():
                _typing_tasks[chat_id] = asyncio.create_task(self._typing_loop(chat_id))
            
            # Send message to command bus for main agent processing
            await self.bus.send(Event(
                type=EventType.USER_MESSAGE,
                payload={
                    "chat_id": chat_id,
                    "text": text
                },
                source="telegram"
            ))
            
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            self._cancel_typing(update.effective_chat.id)
            await update.message.reply_text("❌ Sorry, an error occurred processing your message.")

    # @authorized_only
    # async def tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     """Handle /tasks command"""
    #     chat_id = update.effective_chat.id
    #     if chat_id in _bot_messages:
    #         del _bot_messages[chat_id]
    #
    #     try:
    #         pending = _task_store.list_tasks(status=["todo", "in_progress", "blocked", "waiting_approval", "waiting_review"])
    #         if not pending:
    #             await update.message.reply_text("✅ All clear!", parse_mode=constants.ParseMode.HTML)
    #             return
    #         
    #         response = "📋 <b>Current Tasks</b>\n\n"
    #         for task in pending:
    #             emoji = {"todo": "⏳", "in_progress": "🔄", "blocked": "⚠️", "waiting_approval": "👀", "waiting_review": "🔎"}.get(task.status, "•")
    #             response += f"{emoji} <b>{html.escape(task.title)}</b>\n   Status: {task.status}\n\n"
    #         
    #         await update.message.reply_text(response, parse_mode=constants.ParseMode.HTML)
    #     except Exception as e:
    #         logger.error(f"Error fetching tasks: {e}", exc_info=True)
    #         await update.message.reply_text("❌ Error fetching tasks.")

    @authorized_only
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callback queries"""
        try:
            query = update.callback_query
            await query.answer()
            
            data = query.data
            task_id = None
            approved = False
            
            if data.startswith("approve_task:"):
                task_id = data.split(":", 1)[1]
                approved = True
            elif data.startswith("deny_task:"):
                task_id = data.split(":", 1)[1]
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
            
        except Exception as e:
            logger.error(f"Error in button_callback: {e}", exc_info=True)
            if query:
                await query.answer("❌ Error processing your response")

    def is_running(self) -> bool:
        """Check if the bot service is running"""
        return self._running and self.application is not None

    async def health_check(self) -> bool:
        """Perform a health check on the bot service"""
        try:
            if not self.application or not self._running:
                return False
            
            # Try to get bot info
            me = await self.application.bot.get_me()
            return me is not None
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False