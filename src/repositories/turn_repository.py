# repositories/turn_repository.py
import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from database.base import BaseDatabase

logger = logging.getLogger(__name__)

TurnState = str  # "OPEN" | "COMPLETED" | "CANCELLED"


class TurnRepository:
    """
    Manages the lifecycle of turns.

    A turn = one (user-message, assistant-response) pair.
    The turn row is the authoritative source for state and archival status.
    Messages reference it via turn_id.
    """

    def __init__(self, db: BaseDatabase):
        self.db = db

    # ------------------------------------------------------------------ #
    # Creation                                                             #
    # ------------------------------------------------------------------ #

    async def open_turn(
        self,
        conversation_id: str,
        agent_id: str,
        user_message_seq: int,
    ) -> str:
        """
        Create a new OPEN turn.  Returns the new turn_id.
        """
        turn_id = str(uuid.uuid4())
        await self.db.execute(
            """
            INSERT INTO turns (id, conversation_id, agent_id, state, user_message_seq)
            VALUES (?, ?, ?, 'OPEN', ?)
            """,
            (turn_id, conversation_id, agent_id, user_message_seq),
        )
        logger.debug("Opened turn %s (seq=%d)", turn_id[:8], user_message_seq)
        return turn_id

    # ------------------------------------------------------------------ #
    # State transitions                                                    #
    # ------------------------------------------------------------------ #

    async def complete_turn(
        self,
        turn_id: str,
        assistant_message_seq: int,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ) -> None:
        """
        Transition OPEN → COMPLETED.
        Idempotent: if the turn is already COMPLETED this is a no-op.
        """
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            """
            UPDATE turns
            SET state = 'COMPLETED',
                assistant_message_seq = ?,
                input_tokens  = COALESCE(?, input_tokens),
                output_tokens = COALESCE(?, output_tokens),
                completed_at  = ?
            WHERE id = ? AND state = 'OPEN'
            """,
            (assistant_message_seq, input_tokens, output_tokens, now, turn_id),
        )
        logger.debug("Completed turn %s", turn_id[:8])

    async def cancel_turn(self, turn_id: str) -> None:
        """
        Transition OPEN → CANCELLED.
        Called when a new user message arrives while a prior turn is still OPEN.
        """
        await self.db.execute(
            "UPDATE turns SET state = 'CANCELLED' WHERE id = ? AND state = 'OPEN'",
            (turn_id,),
        )
        logger.warning("Cancelled turn %s (superseded by new user message)", turn_id[:8])

    async def cancel_open_turns(self, conversation_id: str) -> int:
        """
        Cancel all OPEN turns in a conversation.
        Returns the number of rows affected.
        Used on session resume and before opening a new turn.
        """
        cursur = await self.db.execute(
            """
            UPDATE turns
            SET state = 'CANCELLED'
            WHERE conversation_id = ? AND state = 'OPEN'
            """,
            (conversation_id,),
        )
        rows = cursur.rowcount
        if rows:
            logger.warning(
                "Cancelled %d stale OPEN turn(s) in conversation %s",
                rows, conversation_id[:8],
            )
        return rows or 0

    async def mark_turns_summarized(
        self,
        turn_ids: List[str],
    ) -> None:
        """Mark a batch of completed turns as summarized."""
        if not turn_ids:
            return
        placeholders = ",".join("?" * len(turn_ids))
        await self.db.execute(
            f"UPDATE turns SET is_summarized = 1 WHERE id IN ({placeholders})",
            tuple(turn_ids),
        )

    # ------------------------------------------------------------------ #
    # Queries                                                              #
    # ------------------------------------------------------------------ #

    async def get_open_turn(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Return the single OPEN turn for this conversation, if any."""
        return await self.db.fetch_one(
            "SELECT * FROM turns WHERE conversation_id = ? AND state = 'OPEN' LIMIT 1",
            (conversation_id,),
        )

    async def get_recent_completed_turns(
        self,
        conversation_id: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Return the last `limit` COMPLETED turns, oldest-first so callers can
        build an ordered history without reversing.
        """
        rows = await self.db.fetch_all(
            """
            SELECT * FROM turns
            WHERE conversation_id = ? AND state = 'COMPLETED'
            ORDER BY completed_at DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        )
        # Reverse so history is chronological (oldest → newest)
        return list(reversed(rows))

    async def get_unsummarized_completed_turns(
        self,
        conversation_id: str,
        exclude_recent: int,
    ) -> List[Dict[str, Any]]:
        """
        Return COMPLETED, not-yet-summarized turns that are outside the active
        context window (i.e., not in the last `exclude_recent` turns).

        Only these turns are candidates for archival summarization.
        """
        rows = await self.db.fetch_all(
            """
            WITH ranked AS (
                SELECT *,
                       ROW_NUMBER() OVER (ORDER BY completed_at DESC) AS rn
                FROM turns
                WHERE conversation_id = ? AND state = 'COMPLETED'
            )
            SELECT * FROM ranked
            WHERE is_summarized = 0 AND rn > ?
            ORDER BY completed_at ASC
            """,
            (conversation_id, exclude_recent),
        )
        return rows

    async def get_completed_turn_count(self, conversation_id: str) -> int:
        row = await self.db.fetch_one(
            """
            SELECT COUNT(*) AS cnt FROM turns
            WHERE conversation_id = ? AND state = 'COMPLETED' AND is_summarized = 0
            """,
            (conversation_id,),
        )
        logger.info(row)
        return row["cnt"] if row else 0
    
    # repositories/turn_repository.py

    async def get_recent_turns_output_tokens(
    self,
    conversation_id: str,
    limit: int,
) -> List[int]:
        """
        Return output_tokens for the last `limit` COMPLETED turns,
        ordered newest → oldest.

        We return a list so the caller can do a backward walk to
        dynamically shrink the protected window without extra DB calls.
        NULLs are coerced to 0 to keep arithmetic safe.
        """
        rows = await self.db.fetch_all(
            """
            SELECT COALESCE(output_tokens, 0) AS output_tokens
            FROM   turns
            WHERE  conversation_id = ? AND state = 'COMPLETED'
            ORDER  BY completed_at DESC
            LIMIT  ?
            """,
            (conversation_id, limit),
        )
        return [int(r["output_tokens"]) for r in rows]