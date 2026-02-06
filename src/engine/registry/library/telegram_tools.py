import requests
from typing import Any, Optional
from pydantic import Field
from engine.registry.base_tool import BaseTool
from services.telegram_bot.config import TELEGRAM_BOT_TOKEN, AUTHORIZED_USERS

class SendTelegramMessageTool(BaseTool):
    """
    Tool to send a message via Telegram.
    """
    name: str = "send_telegram_message"
    description: str = "Send a text message to a specific Telegram chat or user."
    text: Optional[str] = Field(default=None, description="The message content to send.")
    chat_id: Optional[int] = Field(default=None, description="The Chat ID to send to. If not provided, sends to the first authorized user.")

    def execute(self, **kwargs) -> Any:
        text = kwargs.get("text")
        chat_id = kwargs.get("chat_id")

        if not text:
            return {"status": "error", "error": "Message text is required."}

        # Default to first authorized user if no specific chat_id is given
        if not chat_id:
            if AUTHORIZED_USERS:
                chat_id = AUTHORIZED_USERS[0]
            else:
                return {"status": "error", "error": "No chat_id provided and no authorized users found to default to."}

        if not TELEGRAM_BOT_TOKEN:
            return {"status": "error", "error": "TELEGRAM_BOT_TOKEN not configured."}

        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": text}
            # Timeout set to 10s to prevent hanging
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return {"status": "success", "recipient": chat_id, "api_response": response.json()}
            else:
                return {"status": "error", "error": f"Telegram API Error {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {"status": "error", "error": str(e)}
