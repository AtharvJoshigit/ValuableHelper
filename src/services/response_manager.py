import logging
import random
from typing import Any, Dict
from telegram import constants
from infrastructure.websocket_manager import get_websocket_manager

logger = logging.getLogger(__name__)

class ResponseManager:
    """
    Unified Output Gateway.
    Routes agent chunks to the correct interface (Telegram, WebUI, etc.) 
    based on the 'source' provided by the MainAgent.
    """
    
    def __init__(self, telegram_bot_service):
        self.bot_service = telegram_bot_service
        self.ws_manager = get_websocket_manager()
        self._last_message_ids: Dict[int, int] = {} # chat_id -> last_content_msg_id

    async def handle_chunk(self, chat_id: int, chunk: Any, source: str):
        """
        Directly routes chunks to the appropriate interface.
        """
        is_final = getattr(chunk, 'is_final', False)
        
        # 1. Handle Conversational Content
        if chunk.content:
            await self.stream_text(chat_id, chunk.content, source, is_final)

        # 2. Handle Tool Calls (Status Updates)
        if chunk.tool_call:
            status_text = f"🔧 Using {chunk.tool_call.name}..."
            await self.update_status(chat_id, status_text, source)

        # 3. Handle Tool Results
        if chunk.tool_result:
            await self.update_status(chat_id, "🤔 Thinking...", source)

    async def stream_text(self, chat_id: int, text: str, source: str, is_final: bool = False):
        """Sends text to the correct destination."""
        if source == "web_ui":
            await self.ws_manager.broadcast({
                "type": "chat_message",
                "payload": {"role": "assistant", "content": text, "final": is_final}
            })
        elif source == "telegram":
            if is_final:
                markers = ["⚡", "✔️", "🚀", "✅", "✨", "🦾"]
                text = f"{random.choice(markers)} {text}"
            
            msg_id = await self.bot_service.send_message(chat_id, text)
            if msg_id:
                self._last_message_ids[chat_id] = msg_id

    async def update_status(self, chat_id: int, status_text: str, source: str):
        """Updates the system status on the correct interface."""
        if source == "web_ui":
            await self.ws_manager.broadcast_status("tool_use", details=status_text)
        elif source == "telegram":
            await self.bot_service.update_status(chat_id, status_text)

    async def finalize_response(self, chat_id: int, source: str):
        """Cleanup and add a creative 'done' marker."""
        if source == "telegram":
            await self.bot_service.cleanup(chat_id)
        elif source == "web_ui":
            await self.ws_manager.broadcast_status("idle")

    async def send_error(self, chat_id: int, error_text: str, source: str):
        if source == "web_ui":
            await self.ws_manager.broadcast({"type": "error", "message": error_text})
        elif source == "telegram":
            await self.bot_service.send_message(chat_id, f"⚠️ {error_text}")
            await self.bot_service.cleanup(chat_id)
