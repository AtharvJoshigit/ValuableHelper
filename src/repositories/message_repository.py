# repositories/message_repository.py
import json
import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from database.base import BaseDatabase
from engine.schemas.message import Message, Role

logger = logging.getLogger(__name__)


class MessageRepository:

    def __init__(self, db: BaseDatabase):
        self.db = db

    # ------------------------------------------------------------------ #
    # Writes                                                               #
    # ------------------------------------------------------------------ #

    async def add_message(
        self,
        conversation_id: str,
        agent_id: str,
        message: Message,
        sequence_number: int,
        turn_id: Optional[str] = None,
    ) -> str:
        msg_id = str(uuid.uuid4())
        await self.db.execute(
            """
            INSERT INTO messages (
                id, conversation_id, agent_id, turn_id, role, kind,
                content, tool_calls, tool_results, sequence_number, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg_id,
                conversation_id,
                agent_id,
                turn_id,
                message.role.value,
                message.kind.value,
                message.text,
                json.dumps([tc.dict() for tc in message.tool_calls]) if message.tool_calls else None,
                json.dumps([tr.dict() for tr in message.tool_results]) if message.tool_results else None,
                sequence_number,
                json.dumps({}),
            ),
        )
        return msg_id

    # ------------------------------------------------------------------ #
    # Reads                                                                #
    # ------------------------------------------------------------------ #

    async def get_messages_for_turns(
        self,
        turn_ids: List[str],
    ) -> List[Message]:
        """
        Fetch all messages belonging to a set of turns, in sequence order.
        Used by context-window construction and summarization.
        """
        if not turn_ids:
            return []
        placeholders = ",".join("?" * len(turn_ids))
        rows = await self.db.fetch_all(
            f"""
            SELECT * FROM messages
            WHERE turn_id IN ({placeholders})
            ORDER BY sequence_number ASC
            """,
            tuple(turn_ids),
        )
        return [self._row_to_message(r) for r in rows]

    async def get_system_message(self, conversation_id: str) -> Optional[Message]:
        row = await self.db.fetch_one(
            """
            SELECT * FROM messages
            WHERE conversation_id = ? AND role = 'system'
            ORDER BY sequence_number DESC
            LIMIT 1
            """,
            (conversation_id,),
        )
        return self._row_to_message(row) if row else None

    async def get_last_message(self, conversation_id: str) -> Optional[Message]:
        row = await self.db.fetch_one(
            """
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY sequence_number DESC
            LIMIT 1
            """,
            (conversation_id,),
        )
        return self._row_to_message(row) if row else None

    async def get_message_count(self, conversation_id: str) -> int:
        row = await self.db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        return row["cnt"] if row else 0

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _row_to_message(self, row: Dict[str, Any]) -> Message:
        tool_calls = json.loads(row["tool_calls"]) if row.get("tool_calls") else []
        tool_results = json.loads(row["tool_results"]) if row.get("tool_results") else []
        return Message(
            role=Role(row["role"]),
            text=row.get("content"),
            kind=row.get("kind"),
            tool_calls=tool_calls,
            tool_results=tool_results,
        )