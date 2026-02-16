# agents/main_agent.py (UPDATED)

import asyncio
import logging
from typing import Dict, Optional

from app.app_context import get_app_context
from engine.core.agent_instance_manager import get_agent_manager
from engine.core.agent import Agent
from engine.core.agent_factory import get_global_database
from engine.registry.library.agent_management_tool import CreateAgentTool, SwitchAgentTool
from engine.registry.library.dynamic_tool_creator import DynamicToolCreatorTool
from engine.registry.library.filesystem_tools import ListDirectoryTool, ReadFileTool
from engine.registry.library.memory_retrieval_tool import MemoryRetrievalTool
from engine.registry.library.switch_model_tool import SwitchModelTool
from engine.registry.library.system_tools import RunCommandTool
from engine.registry.library.telegram_tools import SendTelegramMessageTool
from engine.registry.tool_registry import ToolRegistry
from engine.registry.tool_discovery import ToolDiscovery
from services.notification_service import get_notification_service
from infrastructure.websocket_manager import get_websocket_manager
from domain.event import Event, EventType

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class MainAgent(BaseAgent):
    """
    MainAgent is the SINGLE async orchestrator with database-backed memory.
    It consumes user events and streams responses back to UI layers.
    Each chat_id gets its own agent instance with persistent memory.
    """

    def __init__(self, bot_gateway, config: dict | None = None):
        default_config = {
            "model_id": "gemini-3-flash-preview",
            "provider": "google",
            "max_steps": 25,
            "temperature": 0.3,
            # Memory settings
            "enable_memory_summarization": True,
            "agent_name": "Main Agent",
            "memory_recent_k": 15,
            "memory_summarization_threshold": 30,
            "session_timeout_hours": 48,
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
        
        # Per-chat agent instances
        self._agents: Dict[int, Agent] = {}
        self._agent_ids: Dict[int, str] = {}  # Track agent IDs
        
        # Check database availability
        self.has_database = get_global_database() is not None
        if self.has_database:
            logger.info("✅ MainAgent initialized with database-backed memory")
        else:
            logger.warning("⚠️ MainAgent initialized without database (in-memory only)")

    def _get_registry(self) -> ToolRegistry:
        """
        Dynamically builds the 'God Mode' toolset using the Discovery Service.
        Main Agent gets everything, including the private 'tools/' folder.
        """
        registry = ToolRegistry()
        registry.register(ListDirectoryTool())
        registry.register(ReadFileTool())
        registry.register(SwitchModelTool())
        registry.register(RunCommandTool())
        registry.register(CreateAgentTool())
        registry.register(SwitchAgentTool())
        registry.register(SendTelegramMessageTool())
        registry.register(DynamicToolCreatorTool())
        registry.register(MemoryRetrievalTool())

        return registry

    def _get_or_create_agent(self, chat_id: int) -> Agent:
        """
        Get or create agent instance for a specific chat.
        Each chat gets its own agent with independent memory.
        """
        if chat_id not in self._agents:
            session_agent_id = f"main_agent_chat_{chat_id}"
            
            # Create agent using BaseAgent's create method
            agent = self.create(
                system_prompt_file=[
                    "identity.md",
                    "system.md",
                    "user.md",
                    "memory.md",
                    "tools_call.md",
                    "lessons.md"
                ],
                agent_id=session_agent_id,
                set_as_current=False  # Don't set as current, we manage multiple
            )
            
            self._agents[chat_id] = agent
            self._agent_ids[chat_id] = session_agent_id
            
            if self.has_database:
                logger.info(
                    f"✨ Created agent session with database: {session_agent_id} "
                    f"(chat_id: {chat_id})"
                )
            else:
                logger.info(
                    f"✨ Created in-memory agent session: {session_agent_id} "
                    f"(chat_id: {chat_id})"
                )
            
        return self._agents[chat_id]
    
    async def _ensure_agent_ready(self, chat_id: int):
        """Ensure agent is initialized and ready to use."""
        agent = self._get_or_create_agent(chat_id)
        
        # Ensure initialization if using database
        if self.has_database and hasattr(agent, 'ensure_initialized'):
            try:
                await agent.ensure_initialized()
            except Exception as e:
                logger.error(f"Failed to initialize agent for chat {chat_id}: {e}")
                # Continue anyway - agent will lazy-initialize on first use

    async def run(self):
        """Main orchestrator loop."""
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
        """Handle incoming user message."""
        chat_id = event.payload["chat_id"]
        text = event.payload["text"]
        source = getattr(event, "source", "telegram")
        
        await self.ws_manager.broadcast_status("thinking", details="Processing User Message")

        try:
            # Ensure agent is ready
            await self._ensure_agent_ready(chat_id)
            agent = self._agents[chat_id]
            
            full_response_text = ""
            current_status = "🤔 Thinking..."
            
            # Stream response
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

            # Send final message
            if source == "telegram":
                await self.bot.send_or_edit(
                    chat_id=chat_id, 
                    text=full_response_text + "\n ✔️", 
                    is_final=True
                )
            elif source == "web_ui":
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
            logger.error(f"Error handling message for chat {chat_id}: {e}", exc_info=True)
            error_msg = f"⚠️ Error: {str(e)}"
            
            if source == "web_ui":
                await self.ws_manager.broadcast({"type": "error", "message": str(e)})
            else:
                await self.bot.send_or_edit(
                    chat_id=chat_id, 
                    text=error_msg, 
                    is_final=True
                )
        finally:
            await self.ws_manager.broadcast_status("idle")

    async def _handle_user_approval(self, event: Event):
        """Handle user approval/denial of sensitive tool."""
        chat_id = event.payload["chat_id"]
        approved = event.payload["approved"]
        
        await self.ws_manager.broadcast_status("thinking", details="Processing Approval")

        try:
            # Ensure agent exists
            await self._ensure_agent_ready(chat_id)
            agent = self._agents[chat_id]
            
            reply = "User approved the action." if approved else "User denied the action."
            full_response_text = ""

            async for chunk in agent.stream(reply):
                if chunk.content:
                    full_response_text += chunk.content
                    await self.bot.send_or_edit(chat_id=chat_id, text=full_response_text)

            await self.bot.send_or_edit(
                chat_id=chat_id, 
                text=full_response_text, 
                is_final=True
            )
            
        except Exception as e:
            logger.error(f"Error handling approval for chat {chat_id}: {e}", exc_info=True)
        finally:
            await self.ws_manager.broadcast_status("idle")
    
    async def get_chat_stats(self, chat_id: int) -> Optional[dict]:
        """Get memory statistics for a specific chat."""
        if chat_id not in self._agents:
            return None
        
        agent = self._agents[chat_id]
        
        if hasattr(agent, 'get_memory_stats'):
            try:
                return await agent.get_memory_stats()
            except Exception as e:
                logger.error(f"Error getting stats for chat {chat_id}: {e}")
                return None
        
        return None
    
    async def clear_chat_memory(self, chat_id: int) -> bool:
        """Clear memory for a specific chat (start fresh conversation)."""
        if chat_id not in self._agents:
            return False
        
        agent = self._agents[chat_id]
        
        if hasattr(agent, 'start_fresh_conversation'):
            try:
                await agent.start_fresh_conversation()
                logger.info(f"✅ Cleared memory for chat {chat_id}")
                return True
            except Exception as e:
                logger.error(f"Error clearing memory for chat {chat_id}: {e}")
                return False
        
        return False
    
    def get_active_chats(self) -> list[int]:
        """Get list of active chat IDs."""
        return list(self._agents.keys())
    
    async def stop(self):
        """Stop the main agent and cleanup."""
        self.running = False
        
        # Cleanup all agent instances
        if self._agents:
            logger.info(f"Cleaning up {len(self._agents)} agent sessions...")
            cleanup_tasks = []
            
            for chat_id, agent in self._agents.items():
                if hasattr(agent, 'cleanup'):
                    cleanup_tasks.append(agent.cleanup())
            
            if cleanup_tasks:
                try:
                    await asyncio.gather(*cleanup_tasks, return_exceptions=True)
                except Exception as e:
                    logger.error(f"Error during agent cleanup: {e}")
        
        self._agents.clear()
        self._agent_ids.clear()
        
        logger.info("🛑 MainAgent stopped")