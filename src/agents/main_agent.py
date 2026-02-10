import asyncio
import logging
from typing import Dict

from agents.agent_id import AGENT_ID
from engine.core.agent import Agent
from src.infrastructure.command_bus import CommandBus
from engine.core.types import StreamChunk
from engine.registry.tool_registry import ToolRegistry
from src.domain.event import Event, EventType
from src.infrastructure.singleton import Singleton
from services.plan_director import PlanDirector

from engine.registry.library.system_tools import RunCommandTool
from engine.registry.library.filesystem_tools import (
    CreateFileTool,
    ListDirectoryTool,
    ReadFileTool,
)
from engine.registry.library.telegram_tools import SendTelegramMessageTool
from tools.gmail_tool import GmailSearchTool, GmailReadTool, GmailSendTool

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class MainAgent(BaseAgent):
    """
    MainAgent is the SINGLE async orchestrator.
    It consumes user events and streams responses back to UI layers.
    """

    def __init__(self, bot_gateway, bus, config: dict | None = None):
        default_config = {
            "model_id": "gemini-3-pro-preview",
            "provider": "google",
            "max_steps": 25,
            "temperature": 0.3,
            "sensitive_tool_names": {},  # can be extended
        }
        if config:
            default_config.update(config)

        super().__init__(default_config)

        self.command_bus = bus
        self.bot = bot_gateway  # Telegram / Console adapter
        self.running = True

        # One agent instance per chat
        self._agents: Dict[int, Agent] = {}

        

    # ------------------------------------------------------------------
    # Registry (UNCHANGED from your design)
    # ------------------------------------------------------------------

    def _get_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        task_store = Singleton.get_task_store()

        registry.register(ListDirectoryTool())
        registry.register(ReadFileTool())
        registry.register(CreateFileTool(file_path=".", content=".."))
        registry.register(RunCommandTool(command="ls"))

        registry.register(SendTelegramMessageTool())

        registry.register(GmailSearchTool())
        registry.register(GmailReadTool())
        registry.register(GmailSendTool())

        return registry

    # ------------------------------------------------------------------
    # Agent factory (per chat)
    # ------------------------------------------------------------------

    def _get_or_create_agent(self, chat_id: int) -> Agent:
        if chat_id not in self._agents:
            self._agents[chat_id] = self.create(
                system_prompt_file=[
                    "whoami.md",
                    "user.md",
                    "memory.md",
                    "tools_call.md",
                ],
                agent_id=AGENT_ID.MAIN_AGENT.value,
            )
        return self._agents[chat_id]

    # ------------------------------------------------------------------
    # MAIN LOOP (this is what you were missing)
    # ------------------------------------------------------------------

    async def run(self):
        """
        Single async loop that drives the entire system.
        """
        logger.info("🧠 MainAgent loop started")

        while self.running:
            event: Event = await self.command_bus.receive()

            if event.type == EventType.USER_MESSAGE:
                await self._handle_user_message(event)

            elif event.type == EventType.USER_APPROVAL:
                await self._handle_user_approval(event)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _handle_user_message(self, event: Event):
        chat_id = event.payload["chat_id"]
        text = event.payload["text"]

        agent = self._get_or_create_agent(chat_id)

        async for chunk in agent.stream(text):
            await self._handle_stream_chunk(chat_id, chunk)

    async def _handle_user_approval(self, event: Event):
        chat_id = event.payload["chat_id"]
        approved = event.payload["approved"]

        agent = self._get_or_create_agent(chat_id)
        reply = "approve" if approved else "deny"

        async for chunk in agent.stream(reply):
            await self._handle_stream_chunk(chat_id, chunk)

    # ------------------------------------------------------------------
    # Stream handling
    # ------------------------------------------------------------------

    async def _handle_stream_chunk(self, chat_id: int, chunk: StreamChunk):
        """
        Converts Agent stream output into UI updates.
        """

        # if chunk.permission_request:
        #     await self.bot.request_approval(
        #         chat_id=chat_id,
        #         tools=chunk.permission_request,
        #     )
        #     return

        if chunk.content:
            await self.bot.send_or_edit(
                chat_id=chat_id,
                text=chunk.content,
            )

        if chunk.tool_result:
            logger.info(
                f"Tool completed: {chunk.tool_result.name} ({chat_id})"
            )

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def stop(self):
        self.running = False
        logger.info("🛑 MainAgent stopped")
