# engine/core/memory_manager.py
import logging
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

from engine.core.summerizer import MemorySummarizer
from engine.core.types import Message, Role
from database.base import BaseDatabase
from rag.stores.memory import MemoryVectorStore
from repositories.message_repository import MessageRepository
from repositories.conversation_repository import ConversationRepository
from repositories.summary_repository import HybridSummaryRepository

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(
        self,
        db: BaseDatabase,
        agent_id: str,
        agent_name: Optional[str] = None,
        recent_k: int = 15,
        summarization_threshold: int = 20,
        enable_summarization: bool = True,
        auto_summarize: bool = True,
        session_timeout_hours: int  = 24
    ):
        self.db = db
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.recent_k = recent_k
        self.summarization_threshold = summarization_threshold
        self.enable_summarization = enable_summarization
        self.auto_summarize = auto_summarize
        
        self.message_repo = MessageRepository(db)
        self.summary_repo = HybridSummaryRepository(
            db=db,
            vector_store=MemoryVectorStore() if enable_summarization else None
        )
        self.conversation_repo = ConversationRepository(db)
        
        self.conversation_id: Optional[str] = None
        self._sequence_counter: int = 0
        self._original_system_prompt: Optional[str] = None
        self._summarization_lock = asyncio.Lock()
        
        self._summarizer: Optional[MemorySummarizer] = None
        if enable_summarization:
            self._summarizer = MemorySummarizer(agent_id=agent_id)

    async def initialize(self):
        """Initialize conversation session."""
        self.conversation_id = await self.conversation_repo.get_or_create_active_conversation(
            agent_id=self.agent_id,
            agent_name=self.agent_name
        )
        
        self._sequence_counter = await self.message_repo.get_message_count(self.conversation_id)
        
        # Cache original system prompt
        system_msg = await self.message_repo.get_system_message(self.conversation_id)
        if system_msg:
            self._original_system_prompt = system_msg.content

    async def add_message(self, message: Message):
        """Add message with strict consecutive deduplication."""
        if not self.conversation_id:
            await self.initialize()

        # 1. Handle System Prompt Updates
        if message.role == Role.SYSTEM:
            # Strip any injected summary block before comparison or storage.
            # get_history() fuses the original prompt with a summary block and returns
            # it as the system message.  If the agent framework naively feeds that
            # fused message back through add_message(), we must not let the injected
            # block pollute _original_system_prompt — otherwise each cycle appends
            # another summary on top of the previous one (the accumulation bug).
            clean_content = self._strip_summary_injection(message.content)

            # Identical clean content → nothing has changed, skip entirely.
            if self._original_system_prompt and clean_content == self._original_system_prompt:
                return

            # Genuinely new system prompt — update cache with the CLEAN version only.
            self._original_system_prompt = clean_content

            # Persist the clean version so session resume via initialize() also loads
            # a prompt that has no baked-in summary.
            message = Message(role=Role.SYSTEM, content=clean_content)

        # 2. Strict Consecutive Deduplication
        # Only compare against the very last message to prevent "stuttering".
        # Tool results are excluded from dedup — identical polling results are valid.
        last_msg = await self.message_repo.get_last_message(self.conversation_id)
        if last_msg:
            is_dup_content = (last_msg.content == message.content) and (message.content is not None)
            is_dup_role    = last_msg.role == message.role
            if is_dup_role and is_dup_content and message.role != Role.TOOL:
                logger.warning(f"Skipping consecutive duplicate message: {message.content[:50]}...")
                return

        self._sequence_counter += 1
        
        await self.message_repo.add_message(
            conversation_id=self.conversation_id,
            agent_id=self.agent_id,
            message=message,
            sequence_number=self._sequence_counter
        )
        
        await self.conversation_repo.update_conversation_timestamp(self.conversation_id)

        # 3. Trigger Summarization Check
        # Only trigger on a completed assistant turn (no pending tool calls) so we
        # always summarize full user→assistant cycles, never mid-chain fragments.
        if self.enable_summarization and self.auto_summarize:
            if message.role == Role.ASSISTANT and not message.tool_calls:
                await self._check_and_summarize()

    # Sentinel that marks the start of the injected summary block inside the fused
    # system prompt. Must match the string used in get_history() exactly.
    # Single source of truth — change it here and both methods stay in sync.
    _SUMMARY_INJECTION_MARKER = "\n\n### PREVIOUS CONVERSATION CONTEXT\n"

    @classmethod
    def _strip_summary_injection(cls, content: Optional[str]) -> Optional[str]:
        """
        Remove the injected summary block from a (potentially fused) system prompt.

        get_history() builds:
            "<original_prompt>\\n\\n### PREVIOUS CONVERSATION CONTEXT\\n..."

        If the agent framework passes that fused string back through add_message(),
        this method returns only the clean original portion so _original_system_prompt
        is never contaminated with summary content.

        If the marker is absent the content is returned unchanged — meaning it really
        is a fresh/new system prompt and should be stored as-is.
        """
        if not content:
            return content
        marker_pos = content.find(cls._SUMMARY_INJECTION_MARKER)
        if marker_pos == -1:
            return content  # No injection present — nothing to strip
        return content[:marker_pos]

    async def get_history(self) -> List[Message]:
        """
        Constructs the optimized prompt window.
        Structure: [Fused System Prompt] + [Elastic Window of Recent Messages]
        """
        if not self.conversation_id:
            await self.initialize()

        final_history = []

        # --- Step 1: Construct the Fused System Prompt ---
        system_content_parts = []
        
        if self._original_system_prompt:
            system_content_parts.append(self._original_system_prompt)
            
        if self.enable_summarization:
            # get_latest_short_summary always returns at most ONE row because
            # upsert_short_summary atomically replaces on every summarization cycle.
            summary = await self.summary_repo.get_latest_short_summary(self.conversation_id)
            if summary:
                # _SUMMARY_INJECTION_MARKER is the prefix _strip_summary_injection
                # uses to detect and remove this block if the fused message is ever
                # fed back through add_message(). Keep these two in sync.
                summary_block = (
                    f"{self._SUMMARY_INJECTION_MARKER}"
                    f"The following is a compressed summary of the conversation so far. "
                    f"Use this to maintain context without repetition:\n{summary}"
                )
                system_content_parts.append(summary_block)
        
        if system_content_parts:
            final_history.append(Message(
                role=Role.SYSTEM,
                content="\n".join(system_content_parts)
            ))

        # --- Step 2: Retrieve Elastic Context Window ---
        # Fetch slightly more than recent_k to give the elastic backward-scan room.
        buffer_limit = self.recent_k + 15
        raw_messages = await self.message_repo.get_recent_messages(
            conversation_id=self.conversation_id,
            limit=buffer_limit,
            exclude_system=True
        )

        if raw_messages:
            valid_messages    = self._get_context_window(raw_messages, self.recent_k)
            sanitized_messages = self._validate_conversation_pattern(valid_messages)
            final_history.extend(sanitized_messages)

        return final_history

    def _get_context_window(self, messages: List[Message], target_k: int) -> List[Message]:
        """
        Returns a slice of messages ending at the most recent.
        Ensures the slice always starts at a clean USER entry point — never in the
        middle of a tool-call chain.

        Strategy (in order):
          1. Ideal cut: messages[-target_k:]
          2. Backward expansion: if the cut lands inside a tool chain, walk back up
             to 10 steps to find the USER turn that opened the chain.
          3. Forward fallback: if backward scan couldn't find a clean start, advance
             from the ideal cut to the first USER message we find.
          4. Last resort: return the ideal target_k slice as-is so the caller always
             gets *something* valid rather than an empty list.
        """
        total = len(messages)
        if total <= target_k:
            return messages

        cutoff_index = total - target_k

        # --- Backward expansion (elastic window) ---
        scan_limit  = max(0, cutoff_index - 10)
        current_idx = cutoff_index

        while current_idx > scan_limit:
            msg = messages[current_idx]
            if msg.role == Role.USER and not msg.tool_results:
                # Clean entry point found.
                return messages[current_idx:]
            current_idx -= 1

        # --- Forward fallback ---
        # Backward scan couldn't find a clean USER start.  Advance from the ideal
        # cutoff until we hit the next USER message.  This may return fewer than
        # target_k messages, but it guarantees a coherent chain.
        for i in range(cutoff_index, total):
            if messages[i].role == Role.USER:
                return messages[i:]

        # --- Last resort ---
        # No USER message anywhere in the window (e.g. first few turns are all
        # assistant/system).  Return the ideal slice; _validate_conversation_pattern
        # will strip any orphaned leading messages.
        logger.warning(
            "_get_context_window: no clean USER start found; "
            "falling back to raw target_k slice."
        )
        return messages[cutoff_index:]

    def _validate_conversation_pattern(self, messages: List[Message]) -> List[Message]:
        """
        Sanitizes the message list for LLM consumption:
          1. Merges consecutive same-role messages into one.
          2. Drops orphaned leading messages until the first USER turn.
        """
        validated = []
        
        for msg in messages:
            # 1. Merge consecutive same-role messages
            if validated and validated[-1].role == msg.role:
                prev = validated[-1]
                
                if msg.content:
                    prev.content = (prev.content or "") + "\n\n" + msg.content
                if msg.tool_calls:
                    prev.tool_calls = (prev.tool_calls or []) + msg.tool_calls
                if msg.tool_results:
                    prev.tool_results = (prev.tool_results or []) + msg.tool_results
                
                continue
            
            validated.append(msg)

        # 2. Drop leading non-USER messages
        while validated and validated[0].role != Role.USER:
            logger.warning(f"Dropping orphaned {validated[0].role} at start of context window.")
            validated.pop(0)

        # Note on dangling tool calls (validated[-1] is ASSISTANT with tool_calls):
        # We intentionally leave this alone.  In a streaming / agentic setup the
        # executor layer is responsible for completing the tool loop before calling
        # get_history() again.  Silently dropping or rewriting that message would
        # mask a real orchestration bug.

        return validated

    async def _check_and_summarize(self):
        """
        Checks if enough messages have accumulated outside the active window to
        warrant a summarization job.

        safe_threshold = recent_k + summarization_threshold ensures we never try
        to summarize messages that are still inside the active context window.
        """
        count = await self.message_repo.get_unsummarized_count(self.conversation_id)
        safe_threshold = self.recent_k + self.summarization_threshold
        
        if count >= safe_threshold:
            task = asyncio.create_task(self._perform_summarization())
            # Attach a callback so unhandled exceptions are logged rather than
            # silently discarded.  Without this, asyncio only prints them at GC time.
            task.add_done_callback(self._on_summarization_done)

    @staticmethod
    def _on_summarization_done(task: asyncio.Task):
        """Log any exception raised by the background summarization task."""
        try:
            task.result()
        except asyncio.CancelledError:
            pass  # Graceful shutdown — not an error
        except Exception:
            logger.exception("Background summarization task failed")

    async def _perform_summarization(self):
        async with self._summarization_lock:
            messages, start_seq, end_seq = await self.message_repo.get_archivable_messages(
                conversation_id=self.conversation_id,
                keep_recent=self.recent_k + 5  # Safety buffer inside the lock
            )
            
            if not messages:
                return

            summary_data = await self._summarizer.summarize_conversations(
                messages, self.agent_name
            )

            if summary_data["short"]:
                # Atomic replace: HybridSummaryRepository.upsert_short_summary deletes
                # the old 'short' row and inserts a new one in a single transaction.
                # This is what prevents summary accumulation in the system prompt.
                await self.summary_repo.upsert_short_summary(
                    conversation_id=self.conversation_id,
                    content=summary_data["short"],
                    metadata=summary_data["metadata"],
                    agent_id=self.agent_id,
                    agent_name=self.agent_name
                )

            # Persist the detailed long-form summary for RAG recall separately.
            if summary_data["long"]:
                await self.summary_repo.add_summary(
                    conversation_id=self.conversation_id,
                    agent_id=self.agent_id,
                    summary_type="long",
                    content=summary_data["long"],
                    importance=summary_data["importance"],
                    message_start_seq=start_seq,
                    message_end_seq=end_seq,
                    message_count=len(messages),
                    tags=summary_data["metadata"].get("key_topics", []),
                    metadata=summary_data["metadata"],
                    agent_name=self.agent_name
                )
                
            # Mark processed messages so they are excluded from future jobs.
            await self.message_repo.mark_as_summarized(
                conversation_id=self.conversation_id,
                start_seq=start_seq,
                end_seq=end_seq
            )