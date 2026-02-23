# engine/core/agent.py (PRODUCTION-GRADE)
"""
Production-ready Agent — updated for new schema layer.

Changes from previous version:
- Imports Message, Role, MessageKind from schemas.message (not engine.core.types)
- Imports ToolCall, ToolResult from schemas.tool_result with updated field names:
    tool_call.name  → tool_call.tool_name
    tool_call.id    → tool_call.call_id
    tool_result.error → tool_result.error_message + is_error=True
- Uses Message factory constructors throughout:
    Message.user(text)               instead of Message(role=Role.USER, content=...)
    Message.model_text(text, ...)    instead of Message(role=Role.ASSISTANT, content=...)
    Message.model_tool_calls(calls)  instead of Message(role=Role.ASSISTANT, tool_calls=...)
    Message.tool_results_msg(results) instead of Message(role=Role.TOOL, tool_results=...)
- provider.generate() now returns ProviderOutput; accesses
    output.agent_response.response_text  (was response.content)
    output.tool_calls                    (was response.tool_calls)
    output.raw_model_content             (new — raw Google Content for thought_signature)
- Role.ASSISTANT → Role.MODEL throughout
- Duplicate-user-message check uses msg.text and MessageKind.TEXT
"""

import logging
import asyncio
import uuid
from typing import Optional, List, AsyncIterator
from contextlib import asynccontextmanager

from app.app_context import get_app_context
from engine.core.builder import build_turn_prompt
from engine.core.orchstrator import AgentOrchestrator
from engine.core.turn_manager import complete_model_turn
from engine.core.types import StreamChunk, AgentError, TurnResultChunk
from engine.core.memory_manager import MemoryManager
from engine.providers.google.provider import GoogleProvider
from engine.providers.openai.provider import OpenAIProvider
from engine.registry.tool_registry import ToolRegistry
from engine.executors.execution_engine import ExecutionEngine
from engine.core.agent_instance_manager import AgentConfig
from database.base import BaseDatabase
from domain.event import Event, EventType
from engine.schemas.message import MessageKind, Role
from engine.schemas.tool_result import ToolCall
from engine.schemas.turn_result import LoopExitReason

logger = logging.getLogger(__name__)


class Agent:
    """
    Production Agent with proper coordination and error handling.

    Prevents common issues:
    1. Repetitive responses (deduplication in MemoryManager)
    2. 400 pattern errors (validation in google_adapter)
    3. Lost context (elastic window in MemoryManager)
    4. Tool execution failures (retry logic in ExecutionEngine)
    """

    def __init__(
        self,
        agent_id: str,
        config: AgentConfig,
        registry: ToolRegistry,
        db: BaseDatabase,
        memory_manager: Optional[MemoryManager] = None,
    ):
        self.config = config
        self.agent_id = agent_id
        self.db = db
        self._initialized = False
        self._initialization_lock = asyncio.Lock()
        
        # self.provider = OpenAIProvider(
        #     model_id='moonshotai/kimi-k2.5',
        #     temperature=config.temperature,
        #     system_instruction=config.system_prompt,
        #     top_p=config.top_p,
        #     top_k=config.top_k,
        #     max_tokens=config.max_tokens,
        #     api_key='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',
        #     base_url='https://integrate.api.nvidia.com/v1',
        #     **config.additional_params,
        # )

        self.provider = GoogleProvider(
            model_id=config.model,
            temperature=config.temperature,
            system_instruction=config.system_prompt,
            top_p=config.top_p,
            top_k=config.top_k,
            max_tokens=config.max_tokens,
            # api_key='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',
            # base_url='https://integrate.api.nvidia.com/v1',
            **config.additional_params,
        )
        if not self.provider:
            raise ValueError(f"Failed to initialize provider: {config.provider}")

        self.registry = registry
        self.system_prompt = config.system_prompt

        self.memory = memory_manager or MemoryManager(
            db=db,
            agent_id=agent_id,
            agent_name=config.agent_name,
            # ↓ system prompt held in MemoryManager RAM; never goes to DB
            system_prompt=config.system_prompt,
            recent_k_turns=config.memory_recent_k,
            summarization_threshold=config.memory_summarization_threshold,
            enable_summarization=config.enable_memory_summarization,
            auto_summarize=True,
        )

        self.execution_engine = ExecutionEngine(registry)
        self.max_steps = int(config.max_steps)
        self.sensitive_tool_names = config.sensitive_tool_names
        self.pending_tool_calls: Optional[List[ToolCall]] = None
        self.event_bus = get_app_context().event_bus

        self._current_step = 0
        self._last_assistant_message: Optional[str] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize agent and memory.  No system message is written to DB."""
        async with self._initialization_lock:
            if self._initialized:
                logger.warning("Agent %s already initialized", self.agent_id)
                return

            try:
                logger.info("🚀 Initializing agent %s", self.agent_id)
                await self.memory.initialize()
                # System prompt already set on MemoryManager at construction;
                # nothing to write to DB.
                self._initialized = True
                logger.info("✅ Agent %s ready", self.agent_id)

            except Exception as e:
                logger.error("❌ Initialization failed: %s", e, exc_info=True)
                raise AgentError(f"Failed to initialize agent: {e}") from e

    async def ensure_initialized(self) -> None:
        if not self._initialized:
            await self.initialize()
            
    # ------------------------------------------------------------------
    # Streaming run
    # ------------------------------------------------------------------

    async def stream(self, input_text: str) -> AsyncIterator[StreamChunk]:
        """
        Main streaming execution.

        Turn lifecycle:
        1. get_history()          — build context window, capture prev_len
        2. begin_turn()           — open OPEN turn in DB
        3. orchestrator.run()     — stream chunks; collect TurnResult
        4. commit_turn()          — persist snapshot delta, mark COMPLETED
        5. background summarize   — triggered inside commit_turn if needed

        If the orchestrator raises, cancel_current_turn() is called so the
        OPEN row is cleaned up and never pollutes future context.
        """
        try: 
            await self.ensure_initialized()

            if not input_text or not input_text.strip():
                yield StreamChunk(content="(Empty message ignored)")
                return

            # ── 1. Build context window ─────────────────────────────────────
            history, prev_history_length = await self.memory.get_history()

            # Duplicate-user check (still useful as a fast-path guard)
            last_user = next(
                (m for m in reversed(history)
                if m.role == Role.USER and m.kind == MessageKind.TEXT),
                None,
            )
            if last_user and last_user.text == input_text.strip():
                logger.warning("Duplicate user message detected — skipping")
                yield StreamChunk(
                    content="(Duplicate message detected — continuing from previous state...)\n"
                )
                return

            self.event_bus.publish(Event(
                type=EventType.USER_MESSAGE,
                payload={"content": input_text},
                source="agent",
            ))

            # ── 2. Open the turn ────────────────────────────────────────────
            await self.memory.begin_turn()

            # ── 3. Run orchestrator ─────────────────────────────────────────
            tools = self.registry.get_all_tools()
            logger.info(f"Tools count : {len(tools)}")
            turn_result: Optional[TurnResultChunk] = None
            system_prompt = build_turn_prompt(self.system_prompt)
            
            try:
                orchestrator = AgentOrchestrator(
                    provider=self.provider,
                    execution_engine=self.execution_engine,
                    history=history,
                    tools=tools,
                    max_iterations=self.max_steps,
                    system_prompt=system_prompt,
                )
                async for chunk in orchestrator.run(input_text):
                    if isinstance(chunk, StreamChunk):
                        yield chunk
                    elif isinstance(chunk, TurnResultChunk):
                        turn_result = chunk.turn_result
                        final_msg = f"Tools calls: {turn_result.tool_calls_made}"
                        yield StreamChunk(content=final_msg, is_final=True)
            except Exception as e:
                # Orchestrator crashed — cancel the open turn so it never
                # appears in history or summarization candidates.
                await self.memory.cancel_current_turn()
                logger.error("Orchestrator error: %s", e, exc_info=True)
                yield StreamChunk(content=f"\n\n❌ Error: {e}")
                raise AgentError(str(e)) from e

            # ── 4. Commit the turn ──────────────────────────────────────────
            if turn_result is None:
                await self.memory.cancel_current_turn()
                logger.error("No TurnResultChunk received — turn cancelled.")
                return

            t = turn_result
            # turn_metadata might be a dict or an object depending on your orchestrator
            turn_metadata = getattr(t, "turn_metadata", None) or {}

            # Safely get the TokenUsage object (class instance)
            # If missing, used_tokens will be None
            used_tokens = getattr(turn_metadata, "usage", None) 

            logger.info(f"Used Tokens for the Turn: {used_tokens}")

            # Common arguments for both commit_turn calls
            # getattr(used_tokens, "attr", 0) ensures you get a number, not None, for the DB
            commit_kwargs = {
                "prev_history_length": prev_history_length,
                "input_tokens": getattr(used_tokens, "input_tokens", 0),
                "output_tokens": getattr(used_tokens, "output_tokens", 0),
            }

            if t.exit_reason != LoopExitReason.COMPLETED:
                history = complete_model_turn(t, input_text)
                logger.info("histoyr: %s", history)
                logger.info(f"Committing Turn for {t.exit_reason}...")
                await self.memory.commit_turn(
                    history_snapshot=history,
                    delta=True,
                    **commit_kwargs
                )
                return

            await self.memory.commit_turn(
                history_snapshot=t.history_snapshot,
                **commit_kwargs
            )

                
        except AgentError:
            raise
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            yield StreamChunk(content=f"\n\n❌ Unexpected error: {e}")
            raise AgentError(str(e)) from e

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    async def start_fresh_conversation(self) -> None:
        await self.ensure_initialized()
        await self.memory.start_fresh_conversation()
        self._current_step = 0
        self._last_assistant_message = None
        self.pending_tool_calls = None
        logger.info("Started fresh conversation for agent %s", self.agent_id)

    async def get_memory_stats(self) -> dict:
        await self.ensure_initialized()
        stats = await self.memory.get_statistics()
        stats["current_step"] = self._current_step
        stats["last_message_length"] = len(self._last_assistant_message or "")
        return stats

    async def search_memory(self, query: str, limit: int = 5) -> List[dict]:
        await self.ensure_initialized()
        return await self.memory.search_memory(query, limit)

    async def cleanup(self) -> None:
        logger.info("🧹 Cleaning up agent %s", self.agent_id)
        self._initialized = False
        self._current_step = 0
        self._last_assistant_message = None
        self.pending_tool_calls = None


@asynccontextmanager
async def create_agent(
    agent_id: str,
    config: AgentConfig,
    registry: ToolRegistry,
    db: BaseDatabase,
):
    """
    Context manager for safe agent lifecycle management.

    Usage:
        async with create_agent(id, config, registry, db) as agent:
            async for chunk in agent.stream("Hello!"):
                print(chunk.content, end="")
    """
    agent = Agent(agent_id, config, registry, db)
    try:
        await agent.initialize()
        yield agent
    finally:
        await agent.cleanup()