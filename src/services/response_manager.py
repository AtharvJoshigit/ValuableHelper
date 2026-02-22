import logging
import asyncio
import time
from typing import Dict, Optional, Any
from telegram import InlineKeyboardMarkup, constants
from telegram.error import BadRequest, RetryAfter, TelegramError
from infrastructure.websocket_manager import get_websocket_manager

logger = logging.getLogger(__name__)

class ResponseManager:
    """
    Centralized manager for handling agent output and directing it to the appropriate
    interface (Telegram, WebUI, etc.).
    
    It manages:
    1. Chat History (New Messages)
    2. System Status (Dashboard/Edit Messages)
    3. WebUI Broadcasting
    """
    
    def __init__(self, telegram_bot_service):
        self.bot_service = telegram_bot_service
        self.ws_manager = get_websocket_manager()
        
        # State tracking
        self._status_messages: Dict[int, int] = {}  # chat_id -> message_id
        self._last_update_time: Dict[int, float] = {}
        self._update_interval = 1.5  # Seconds between edits to prevent rate limits

    async def stream_text(self, chat_id: int, text: str, source: str = "telegram", is_final: bool = False):
        """
        Handle streaming text content.
        - WebUI: Broadcasts chunks.
        - Telegram: Buffers and sends/edits message.
        """
        if source == "web_ui":
            await self.ws_manager.broadcast({
                "type": "chat_message",
                "payload": {
                    "role": "assistant",
                    "content": text,
                    "final": is_final
                }
            })
        else:
            # For Telegram, we want to simulate a "typing" stream or just send chunks?
            # Based on user preference: "whenever I get content from it would be a full phrase"
            # So we might just want to send the final message or update a "thinking" message?
            
            # Current implementation in MainAgent accumulates text.
            # If we want "streaming" feel in Telegram without spam, we edit the last message.
            # If we want "distinct messages", we wait for significant chunks.
            
            # Let's stick to the "Edit" strategy for the current response, 
            # and "New Message" for the next turn.
            await self.bot_service.send_or_edit(chat_id, text, is_final=is_final)

    async def update_status(self, chat_id: int, status_text: str, source: str = "telegram"):
        """
        Update the system status (e.g., "🔧 Using Tool...", "🤔 Thinking...").
        - WebUI: Broadcasts status event.
        - Telegram: Edits a dedicated status message (or appends to current if preferred).
        """
        # WebUI always gets real-time status
        await self.ws_manager.broadcast_status("tool_use", details=status_text)

        if source == "telegram":
            # For now, we assume MainAgent combines them, so this might be unused 
            # unless we refactor MainAgent to stop combining them.
            pass

    async def send_error(self, chat_id: int, error_text: str, source: str = "telegram"):
        """Handle error reporting."""
        if source == "web_ui":
            await self.ws_manager.broadcast({"type": "error", "message": error_text})
        else:
            await self.bot_service.send_or_edit(chat_id, f"⚠️ {error_text}", is_final=True)
