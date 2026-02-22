# engine/core/memory_manager.py
"""
Turn-based, state-aware memory engine.

System-prompt policy
--------------------
The system prompt is NEVER stored in the database.
It is held exclusively in self._original_system_prompt (in-memory).
get_history() fuses it with the short summary at call-time.
This keeps the messages table free of system rows and eliminates the
summary-accumulation bug entirely.

Turn lifecycle (called from Agent)
-----------------------------------
  begin_turn()   – open an OPEN turn row; returns turn_id
  commit_turn()  – persist turn messages from TurnResult.history_snapshot,
                   mark the turn COMPLETED, fire background summarization
  cancel_current_turn() – explicit cancel (e.g. user disconnected)

Context retrieval
-----------------
  get_history() → [fused system msg] + [msgs from last N COMPLETED turns]
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from database.base import BaseDatabase
from engine.core.summarizer import MemorySummarizer
from engine.schemas.message import Message, MessageKind, Role
from rag.stores.memory import MemoryVectorStore
from repositories.conversation_repository import ConversationRepository
from repositories.message_repository import MessageRepository
from repositories.summary_repository import HybridSummaryRepository
from repositories.turn_repository import TurnRepository

logger = logging.getLogger(__name__)

_SUMMARY_MARKER = "\n\n### PREVIOUS CONVERSATION CONTEXT\n"


class MemoryManager:
    def __init__(
        self,
        db: BaseDatabase,
        agent_id: str,
        agent_name: Optional[str] = None,
        system_prompt: Optional[str] = None,   # passed in; never stored to DB
        recent_k_turns: int = 10,
        summarization_threshold: int = 15,
        token_threshold_pct: float = 0.70,
        model_context_tokens: int = 100_000,
        enable_summarization: bool = True,
        auto_summarize: bool = True,
    ):
        self.db = db
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.recent_k_turns = recent_k_turns
        self.summarization_threshold = summarization_threshold
        self.token_threshold = int(model_context_tokens * token_threshold_pct)
        self.enable_summarization = enable_summarization
        self.auto_summarize = auto_summarize

        # System prompt lives HERE ONLY — never in the DB.
        self._original_system_prompt: Optional[str] = system_prompt

        self.message_repo      = MessageRepository(db)
        self.turn_repo         = TurnRepository(db)
        self.conversation_repo = ConversationRepository(db)
        self.summary_repo      = HybridSummaryRepository(
            db=db,
            vector_store=MemoryVectorStore() if enable_summarization else None,
        )

        self.conversation_id: Optional[str] = None
        self._sequence_counter: int = 0
        self._current_turn_id: Optional[str] = None
        self._summarization_lock = asyncio.Lock()

        self._summarizer: Optional[MemorySummarizer] = None
        if enable_summarization:
            self._summarizer = MemorySummarizer(agent_id=agent_id)

    # ------------------------------------------------------------------ #
    # Initialization                                                       #
    # ------------------------------------------------------------------ #

    async def initialize(self) -> None:
        """
        Resume or create a conversation session.

        On resume: cancel any OPEN turns left by a prior crash so
        history is always built from fully-completed turns only.

        Note: We do NOT read any system message from the DB.
              _original_system_prompt is set at construction time.
        """
        self.conversation_id = await self.conversation_repo.get_or_create_active_conversation(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
        )

        cancelled = await self.turn_repo.cancel_open_turns(self.conversation_id)
        if cancelled:
            logger.warning(
                "Session resume: cancelled %d stale OPEN turn(s) in conversation %s",
                cancelled, self.conversation_id[:8],
            )

        self._sequence_counter = await self.message_repo.get_message_count(
            self.conversation_id
        )
        self._current_turn_id = None

    def set_system_prompt(self, prompt: str) -> None:
        """
        Update the in-memory system prompt at runtime (e.g. after tool-augmented
        prompt injection).  Never touches the DB.
        """
        self._original_system_prompt = self._strip_summary_injection(prompt)

    # ------------------------------------------------------------------ #
    # Turn lifecycle — called from Agent                                   #
    # ------------------------------------------------------------------ #

    async def begin_turn(self) -> str:
        """
        Open a new OPEN turn immediately before the orchestrator runs.

        If a prior turn is somehow still OPEN (e.g. agent reused without
        commit after an error), cancel it first.

        Returns the new turn_id so the caller can pass it to commit_turn.
        """
        if not self.conversation_id:
            await self.initialize()

        if self._current_turn_id:
            logger.warning(
                "begin_turn called while turn %s was still OPEN — cancelling it.",
                self._current_turn_id[:8],
            )
            await self.turn_repo.cancel_turn(self._current_turn_id)
            self._current_turn_id = None

        # Placeholder sequence; real user-message seq is filled in commit_turn.
        turn_id = await self.turn_repo.open_turn(
            conversation_id=self.conversation_id,
            agent_id=self.agent_id,
            user_message_seq=self._sequence_counter + 1,  # optimistic
        )
        self._current_turn_id = turn_id
        logger.debug("Opened turn %s", turn_id[:8])
        return turn_id

    async def commit_turn(
        self,
        history_snapshot: List[Dict[str, Any]],
        prev_history_length: int,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        delta: bool = False,
    ) -> None:
        """
        Persist the new messages produced during this turn and mark it COMPLETED.

        Parameters
        ----------
        history_snapshot
            The full ordered history after this turn (TurnResult.history_snapshot).
            Each element is either a Message or a Message.to_dict() dict.
        prev_history_length
            Number of non-system messages that were in the context window BEFORE
            this turn ran.  New messages = snapshot[prev_history_length:].
        input_tokens / output_tokens
            Optional token counts from the provider response.
        """
        if not self._current_turn_id:
            logger.error("commit_turn called with no open turn — snapshot discarded.")
            return

        # --- Reconstruct Message objects from snapshot -----------------
        raw_messages: List[Message] = []
        for item in history_snapshot:
            if isinstance(item, Message):
                raw_messages.append(item)
            elif isinstance(item, dict):
                raw_messages.append(Message.from_dict(item))
            else:
                logger.warning("Unexpected item type in history_snapshot: %s", type(item))

        # --- Extract only the NEW messages produced this turn ----------
        # Slice off everything the orchestrator already had in context.
        new_messages = raw_messages[prev_history_length:] if not delta else raw_messages

        if not new_messages:
            logger.warning("commit_turn: no new messages in snapshot delta — cancelling turn.")
            await self.turn_repo.cancel_turn(self._current_turn_id)
            self._current_turn_id = None
            return

        # --- Filter and persist ----------------------------------------
        user_seq: Optional[int] = None
        assistant_seq: Optional[int] = None

        for msg in new_messages:
            clean = self._clean_message(msg)
            if clean is None:
                continue  # system or fully-empty after cleaning

            self._sequence_counter += 1
            seq = self._sequence_counter

            await self.message_repo.add_message(
                conversation_id=self.conversation_id,
                agent_id=self.agent_id,
                message=clean,
                sequence_number=seq,
                turn_id=self._current_turn_id,
            )

            if clean.role == Role.USER and user_seq is None:
                user_seq = seq
            elif clean.role == Role.MODEL:
                assistant_seq = seq  # keep updating; last MODEL msg is the final response

        # Back-fill the user_message_seq that was optimistic in begin_turn
        if user_seq is not None:
            await self.db.execute(
                "UPDATE turns SET user_message_seq = ? WHERE id = ?",
                (user_seq, self._current_turn_id),
            )

        if assistant_seq is None:
            logger.warning(
                "commit_turn: no MODEL message found in delta — cancelling turn %s.",
                self._current_turn_id[:8],
            )
            await self.turn_repo.cancel_turn(self._current_turn_id)
            self._current_turn_id = None
            return

        # --- Complete the turn -----------------------------------------

        await self.turn_repo.complete_turn(
            turn_id=self._current_turn_id,
            assistant_message_seq=assistant_seq,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        await self.conversation_repo.update_conversation_timestamp(self.conversation_id)

        completed_turn_id = self._current_turn_id
        self._current_turn_id = None

        logger.info(
            "Turn %s committed (user_seq=%s, assistant_seq=%s, new_msgs=%d)",
            completed_turn_id[:8], user_seq, assistant_seq, len(new_messages),
        )

        # --- Optional background summarization -------------------------
        if self.enable_summarization and self.auto_summarize:
            total_tokens = (input_tokens or 0) + (output_tokens or 0)
            logger.info("I am here in enable_summarization")
            await self._maybe_summarize(total_tokens=total_tokens)

    async def cancel_current_turn(self) -> None:
        """Explicitly cancel the current OPEN turn (e.g. user disconnected)."""
        if self._current_turn_id:
            await self.turn_repo.cancel_turn(self._current_turn_id)
            logger.info("Turn %s cancelled by caller.", self._current_turn_id[:8])
            self._current_turn_id = None

    # ------------------------------------------------------------------ #
    # Context retrieval                                                    #
    # ------------------------------------------------------------------ #

    async def get_history(self) -> List[Message]:
        """
        Build the prompt window for the next LLM call.

        Structure:
          [Fused system message]  ← _original_system_prompt + short summary block
          [Messages from last N COMPLETED turns, excluding summarized coverage]

        Returns a (message_list, non_system_count) tuple so Agent can pass
        non_system_count as prev_history_length to commit_turn.
        """
        if not self.conversation_id:
            await self.initialize()

        history: List[Message] = []

        # ── Fused system message ────────────────────────────────────────
        system_parts: List[str] = []

        # if self._original_system_prompt:
        #     system_parts.append(self._original_system_prompt)

        short_summary_row: Optional[Dict[str, Any]] = None
        if self.enable_summarization:
            short_summary_row = await self.summary_repo.get_short_summary(
                self.conversation_id
            )
            if short_summary_row:
                block = (
                    f"{_SUMMARY_MARKER}"
                    f"The following is a compressed summary of the conversation so far. "
                    f"Use it to maintain context without repetition:\n"
                    f"{short_summary_row['content']}"
                )
                system_parts.append(block)

        if system_parts:
            history.append(Message(role=Role.SYSTEM, text="\n".join(system_parts)))

        # ── Recent completed turns ──────────────────────────────────────
        turns = await self.turn_repo.get_recent_completed_turns(
            conversation_id=self.conversation_id,
            limit=self.recent_k_turns,
        )

        # Exclude turns already covered by the short summary to avoid
        # double-injecting content that is already in the system block.
        if short_summary_row and turns:
            covered_end = short_summary_row.get("turn_end_id")
            if covered_end:
                turn_ids = [t["id"] for t in turns]
                if covered_end in turn_ids:
                    cutoff = turn_ids.index(covered_end) + 1
                    turns = turns[cutoff:]

        non_system_count = 0
        if turns:
            turn_ids = [t["id"] for t in turns]
            messages = await self.message_repo.get_messages_for_turns(turn_ids)
            sanitized = self._sanitize(messages)
            history.extend(sanitized)
            non_system_count = len(sanitized)

        return history, non_system_count

    # ------------------------------------------------------------------ #
    # Summarization                                                        #
    # ------------------------------------------------------------------ #

    async def _maybe_summarize(self, total_tokens: int = 0) -> None:
        count= await self.turn_repo.get_completed_turn_count(self.conversation_id)
        logger.info("count: %s", count)
        archivable = max(0, count - self.recent_k_turns)
        logger.info("Archivable: %s \n Summarization Threshold: %s \n Total Token : %s \n Token Threshold : %s", archivable, self.summarization_threshold, total_tokens, self.token_threshold)
        token_pressure = total_tokens > 0 and total_tokens >= self.token_threshold
        turn_pressure  = archivable >= self.summarization_threshold
        
        logger.info("Token Pressure: %s, Turn Pressure: %s", token_pressure, turn_pressure)
        if token_pressure or turn_pressure:
            task = asyncio.create_task(self._perform_summarization())
            task.add_done_callback(_log_task_exception)

    async def _perform_summarization(self) -> None:
        async with self._summarization_lock:
            candidate_turns = await self.turn_repo.get_unsummarized_completed_turns(
                conversation_id=self.conversation_id,
                exclude_recent=self.recent_k_turns,
            )
            if not candidate_turns:
                return

            turn_ids = [t["id"] for t in candidate_turns]
            messages = await self.message_repo.get_messages_for_turns(turn_ids)
            if not messages:
                return

            seqs = [
                s for t in candidate_turns
                for s in (t["user_message_seq"], t["assistant_message_seq"])
                if s is not None
            ]
            start_seq, end_seq = min(seqs), max(seqs)

            prev_row = await self.summary_repo.get_short_summary(self.conversation_id)
            prev_text: Optional[str] = prev_row["content"] if prev_row else None

            summary_data = await self._summarizer.summarize_conversations(
                messages=messages,
                agent_name=self.agent_name,
                previous_summary=prev_text,
            )

            if not summary_data.get("short"):
                logger.warning("Summarizer returned no short summary — skipping upsert.")
                return

            await self.summary_repo.upsert_short_summary(
                conversation_id=self.conversation_id,
                agent_id=self.agent_id,
                content=summary_data["short"],
                message_start_seq=start_seq,
                message_end_seq=end_seq,
                turn_start_id=candidate_turns[0]["id"],
                turn_end_id=candidate_turns[-1]["id"],
                metadata=summary_data.get("metadata", {}),
                agent_name=self.agent_name,
            )

            if summary_data.get("long"):
                await self.summary_repo.add_long_summary(
                    conversation_id=self.conversation_id,
                    agent_id=self.agent_id,
                    content=summary_data["long"],
                    importance=summary_data.get("importance", 5),
                    message_start_seq=start_seq,
                    message_end_seq=end_seq,
                    message_count=len(messages),
                    turn_start_id=candidate_turns[0]["id"],
                    turn_end_id=candidate_turns[-1]["id"],
                    tags=summary_data.get("metadata", {}).get("key_topics", []),
                    metadata=summary_data.get("metadata", {}),
                    agent_name=self.agent_name,
                )

            await self.turn_repo.mark_turns_summarized(turn_ids)
            logger.info(
                "Summarized %d turns (seqs %d→%d), conversation %s",
                len(candidate_turns), start_seq, end_seq, self.conversation_id[:8],
            )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _clean_message(msg: Message) -> Optional[Message]:
        """
        Return a DB-safe copy of the message:
          - Drop system messages entirely (never stored).
          - Strip thought_text and reasoning_text (debug artifacts, not persisted).
          - Return None if the result would be empty/useless.
        """
        if msg.role == Role.SYSTEM:
            return None

        return Message(
            role=msg.role,
            kind=msg.kind,
            text=msg.text,
            tool_calls=msg.tool_calls or [],
            tool_results=msg.tool_results or [],
            structured_response=msg.structured_response,
            thought_text=None,       # intentionally dropped
            agent_id=msg.agent_id,
        )

    @staticmethod
    def _strip_summary_injection(content: Optional[str]) -> Optional[str]:
        if not content:
            return content
        idx = content.find(_SUMMARY_MARKER)
        return content[:idx] if idx != -1 else content

    @staticmethod
    def _sanitize(messages: List[Message]) -> List[Message]:
        """
        Merge consecutive same-role messages; drop orphaned leading non-USER rows.
        """
        merged: List[Message] = []
        for msg in messages:
            if merged and merged[-1].role == msg.role:
                prev = merged[-1]
                prev.text = (
                    ((prev.text or "") + "\n\n" + (msg.text or "")).strip() or None
                )
                prev.tool_calls   = (prev.tool_calls   or []) + (msg.tool_calls   or [])
                prev.tool_results = (prev.tool_results or []) + (msg.tool_results or [])
                continue
            merged.append(msg)

        while merged and merged[0].role != Role.USER:
            logger.warning("Dropping orphaned %s at context-window start.", merged[0].role)
            merged.pop(0)

        return merged

    # ------------------------------------------------------------------ #
    # Misc public helpers                                                  #
    # ------------------------------------------------------------------ #

    async def start_fresh_conversation(self) -> None:
        await self.conversation_repo.end_all_conversations(self.agent_id)
        self.conversation_id = None
        self._sequence_counter = 0
        self._current_turn_id = None
        await self.initialize()

    async def get_statistics(self) -> Dict[str, Any]:
        if not self.conversation_id:
            return {}
        count = await self.message_repo.get_message_count(self.conversation_id)
        turn_count = await self.turn_repo.get_completed_turn_count(self.conversation_id)
        return {
            "conversation_id": self.conversation_id,
            "total_messages": count,
            "completed_turns": turn_count,
        }


def _log_task_exception(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Background summarization task raised an unhandled exception")