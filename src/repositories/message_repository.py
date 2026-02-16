# infrastructure/repositories/message_repository.py
import json
import uuid
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from database.base import BaseDatabase
from engine.core.types import Message, Role

logger = logging.getLogger(__name__)

class MessageRepository:
    """Repository for message CRUD operations."""
    
    def __init__(self, db: BaseDatabase):
        self.db = db
    
    async def add_message(
        self,
        conversation_id: str,
        agent_id: str,
        message: Message,
        sequence_number: int
    ) -> str:
        """Store a single message in database."""
        message_id = str(uuid.uuid4())
        
        query = """
            INSERT INTO messages (
                id, conversation_id, agent_id, role, content,
                tool_calls, tool_results, sequence_number, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            message_id,
            conversation_id,
            agent_id,
            message.role.value,
            message.content,
            json.dumps([tc.dict() for tc in message.tool_calls]) if message.tool_calls else None,
            json.dumps([tr.dict() for tr in message.tool_results]) if message.tool_results else None,
            sequence_number,
            json.dumps({})
        )
        
        await self.db.execute(query, params)
        return message_id
    
    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int,
        exclude_system: bool = False
    ) -> List[Message]:
        """Fetch recent K messages efficiently."""
        query = """
            SELECT role, content, tool_calls, tool_results
            FROM messages
            WHERE conversation_id = ?
        """
        
        if exclude_system:
            query += " AND role != 'system'"
        
        query += " ORDER BY sequence_number DESC LIMIT ?"
        
        rows = await self.db.fetch_all(query, (conversation_id, limit))
        
        # Reverse to get chronological order
        messages = []
        for row in reversed(rows):
            messages.append(self._row_to_message(row))
        
        return messages
    
    async def get_messages_in_range(
        self,
        conversation_id: str,
        start_seq: int,
        end_seq: int
    ) -> List[Message]:
        """Fetch messages in a sequence range."""
        query = """
            SELECT role, content, tool_calls, tool_results, sequence_number
            FROM messages
            WHERE conversation_id = ?
              AND sequence_number BETWEEN ? AND ?
            ORDER BY sequence_number ASC
        """
        
        rows = await self.db.fetch_all(query, (conversation_id, start_seq, end_seq))
        return [self._row_to_message(row) for row in rows]
    
    async def get_unsummarized_messages(
        self,
        conversation_id: str,
        skip_recent_k: int
    ) -> Tuple[List[Message], int, int]:
        """
        Get messages that need summarization.
        Returns: (messages, start_seq, end_seq)
        """
        # Get total count
        count_query = """
            SELECT COUNT(*) as cnt, MIN(sequence_number) as min_seq, MAX(sequence_number) as max_seq
            FROM messages
            WHERE conversation_id = ?
              AND is_summarized = 0
              AND role != 'system'
        """
        
        count_row = await self.db.fetch_one(count_query, (conversation_id,))
        total_count = count_row['cnt']
        
        if total_count <= skip_recent_k:
            return [], 0, 0
        
        # Calculate range to summarize (exclude recent K)
        end_seq = count_row['max_seq'] - skip_recent_k
        start_seq = count_row['min_seq']
        
        # Fetch messages to summarize
        query = """
            SELECT role, content, tool_calls, tool_results, sequence_number
            FROM messages
            WHERE conversation_id = ?
              AND is_summarized = 0
              AND sequence_number BETWEEN ? AND ?
              AND role != 'system'
            ORDER BY sequence_number ASC
        """
        
        rows = await self.db.fetch_all(query, (conversation_id, start_seq, end_seq))
        messages = [self._row_to_message(row) for row in rows]
        
        return messages, start_seq, end_seq
    
    async def mark_as_summarized(
        self,
        conversation_id: str,
        start_seq: int,
        end_seq: int
    ):
        """Mark messages as summarized."""
        query = """
            UPDATE messages
            SET is_summarized = 1
            WHERE conversation_id = ?
              AND sequence_number BETWEEN ? AND ?
        """
        await self.db.execute(query, (conversation_id, start_seq, end_seq))
    
    async def get_message_count(
        self,
        conversation_id: str,
        unsummarized_only: bool = False
    ) -> int:
        """Get count of messages."""
        query = "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ?"
        
        if unsummarized_only:
            query += " AND is_summarized = 0 AND role != 'system'"
        
        row = await self.db.fetch_one(query, (conversation_id,))
        print(f"Count: {row['cnt']}, unsummarized_only: {unsummarized_only}")
        return row['cnt']
    
    async def get_system_message(self, conversation_id: str) -> Optional[Message]:
        """Get the system prompt message."""
        query = """
            SELECT role, content, tool_calls, tool_results
            FROM messages
            WHERE conversation_id = ? AND role = 'system'
            ORDER BY sequence_number ASC
            LIMIT 1
        """
        row = await self.db.fetch_one(query, (conversation_id,))
        return self._row_to_message(row) if row else None
    
    def _row_to_message(self, row: Dict[str, Any]) -> Message:
        """Convert database row to Message object."""
        tool_calls = None
        if row.get('tool_calls'):
            from engine.core.types import ToolCall
            tool_calls = [ToolCall(**tc) for tc in json.loads(row['tool_calls'])]
        
        tool_results = None
        if row.get('tool_results'):
            from engine.core.types import ToolResult
            tool_results = [ToolResult(**tr) for tr in json.loads(row['tool_results'])]
        
        return Message(
            role=Role(row['role']),
            content=row.get('content'),
            tool_calls=tool_calls or [],
            tool_results=tool_results or []
        )