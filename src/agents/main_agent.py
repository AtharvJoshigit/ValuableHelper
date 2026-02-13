import asyncio
import logging
import uuid
from typing import Dict, Any

from agents.agent_id import AGENT_ID
from app.app_context import get_app_context
from engine.core.agent_instance_manager import get_agent_manager
from infrastructure.command_bus import CommandBus
from engine.core.agent import Agent
from engine.registry.tool_registry import ToolRegistry
from engine.registry.tool_discovery import ToolDiscovery
from services.notification_service import get_notification_service
import telegram
from infrastructure.command_bus import CommandBus
from infrastructure.websocket_manager import get_websocket_manager
from domain.event import Event, EventType
from services.telegram_bot.config import ADMIN_USER_IDS

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class MainAgent(BaseAgent):
    """
    MainAgent is the SINGLE async orchestrator.
    It consumes user events and streams responses back to UI layers.
    """

    def __init__(self, bot_gateway, config: dict | None = None):
        default_config = {
            "model_id": "gemini-3-flash-preview",
            "provider": "google",
            "max_steps": 25,
            "temperature": 0.3,
        }
        if config:
            default_config.update(config)

        super().__init__(default_config)

        self.command_bus = get_app_context().command_bus
        self.bot = bot_gateway
        self.notification_service = get_notification_service()
        self.running = True
        self.ws_manager = get_websocket_manager()
        self.agent_manager = get_agent_manager()
        self._agents: Dict[int, Agent] = {}

    def _get_registry(self) -> ToolRegistry:
        """
        Dynamically builds the 'God Mode' toolset using the Discovery Service.
        Main Agent gets everything, including the private 'tools/' folder.
        """
        registry = ToolRegistry()
        
        # Use the Discovery Service to find and register all tools
        discovery = ToolDiscovery()
        tools = discovery.discover_tools(include_tools_dir=True)
        
        for tool in tools:
            try:
                registry.register(tool)
            except Exception as e:
                logger.warning(f"Failed to register discovered tool {tool.name}: {e}")

        return registry

    def _get_or_create_agent(self, chat_id: int) -> Agent:
        if chat_id not in self._agents:
            session_agent_id = f"main_agent_{chat_id}"
            
            self._agents[chat_id] = self.create(
                system_prompt_file=[
                    "identity.md",
                    "system.md",
                    "user.md",
                    "memory.md",
                    "tools_call.md",
                    "lessons.md"
                ],
                agent_id=session_agent_id,
                set_as_current=True 
            )
            logger.info(f"✨ Created new agent session: {session_agent_id}")
            
        return self.agent_manager.get_agent()

    async def run(self):
        logger.info("🧠 MainAgent orchestrator loop started")
        while self.running:
            try:
                event: Event = await self.command_bus.receive()
                if event.type == EventType.USER_MESSAGE:
                    asyncio.create_task(self._handle_user_message(event))
                elif event.type == EventType.USER_APPROVAL:
                    asyncio.create_task(self._handle_user_approval(event))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in MainAgent loop: {e}", exc_info=True)

    async def _handle_user_message(self, event: Event):
        chat_id = event.payload["chat_id"]
        text = event.payload["text"]
        source = getattr(event, "source", "telegram")
        await self.ws_manager.broadcast_status("thinking", details="Processing User Message")

        try:
            agent = self._get_or_create_agent(chat_id)
            full_response_text = ""
            current_status = "🤔 Thinking..."
            
            async for chunk in agent.stream(text):
                if chunk.content:
                    full_response_text += chunk.content
                    
                    if source == "web_ui":
                        # Push to UI via WebSocket
                        await self.ws_manager.broadcast({
                            "type": "chat_message",
                            "payload": {
                                "role": "assistant",
                                "content": full_response_text
                            }
                        })
                    else:
                        await self.bot.send_or_edit(
                            chat_id=chat_id, 
                            text=f"{full_response_text}\n\n{current_status}"
                        )
                
                if chunk.tool_call:
                    tool_name = chunk.tool_call.name
                    current_status = f"🔧 Using {tool_name}..."
                    if source != "web_ui":
                        await self.bot.send_or_edit(
                            chat_id=chat_id, 
                            text=f"{full_response_text}\n\n{current_status}"
                        )
                    await self.ws_manager.broadcast_status("tool_use", details=tool_name)

                if chunk.tool_result:
                    current_status = "🤔 Thinking..."

            if source == "telegram":
                 await self.bot.send_or_edit(chat_id=chat_id, text=full_response_text + "\n ✔️", is_final=True)
            elif source == "web_ui":
                 # Final signal
                 await self.ws_manager.broadcast({
                    "type": "chat_message",
                    "payload": {
                        "role": "assistant",
                        "content": full_response_text,
                        "final": True
                    }
                })
            else:
                 await self.notification_service.send_custom_notification(full_response_text)

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            if source == "web_ui":
                 await self.ws_manager.broadcast({"type": "error", "message": str(e)})
            else:
                 await self.bot.send_or_edit(chat_id=chat_id, text=f"⚠️ Error: {str(e)}", is_final=True)
        finally:
            await self.ws_manager.broadcast_status("idle")

    async def _handle_user_approval(self, event: Event):
        chat_id = event.payload["chat_id"]
        approved = event.payload["approved"]
        await self.ws_manager.broadcast_status("thinking", details="Processing Approval")

        try:
            agent = self._get_or_create_agent(chat_id)
            reply = "User approved the action." if approved else "User denied the action."
            full_response_text = ""

            async for chunk in agent.stream(reply):
                if chunk.content:
                    full_response_text += chunk.content
                    await self.bot.send_or_edit(chat_id=chat_id, text=full_response_text)

            await self.bot.send_or_edit(chat_id=chat_id, text=full_response_text, is_final=True)
        except Exception as e:
             logger.error(f"Error handling approval: {e}")
        finally:
             await self.ws_manager.broadcast_status("idle")

    async def stop(self):
        self.running = False
        logger.info("🛑 MainAgent stopped")
