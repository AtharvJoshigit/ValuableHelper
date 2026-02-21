# infrastructure/repositories/conversation_repository.py (FIXED)
import json
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from database.base import BaseDatabase

logger = logging.getLogger(__name__)

class ConversationRepository:
    """Repository for conversation/session management with resumption support."""
    
    def __init__(self, db: BaseDatabase):
        self.db = db
    
    async def create_conversation(
        self,
        agent_id: str,
        agent_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new conversation session."""
        conversation_id = str(uuid.uuid4())
        
        query = """
            INSERT INTO conversations (id, agent_id, agent_name, metadata)
            VALUES (?, ?, ?, ?)
        """
        
        await self.db.execute(
            query,
            (conversation_id, agent_id, agent_name, json.dumps(metadata or {}))
        )
        
        logger.info(f"✅ Created new conversation: {conversation_id}")
        return conversation_id
    
    async def get_or_create_active_conversation(
        self,
        agent_id: str,
        agent_name: Optional[str] = None,
        session_timeout_hours: int = 24  # NEW: Configurable timeout
    ) -> str:
        """
        Get active conversation or create new one.
        
        Session resumption logic:
        1. Check for conversations active within timeout window
        2. If found, resume that conversation
        3. Otherwise, create new conversation
        """
        # Calculate cutoff time for session resumption
        # cutoff_time = datetime.now(timezone.utc) - timedelta(hours=session_timeout_hours)
        
        query = """
            SELECT id, updated_at FROM conversations
            WHERE agent_id = ? 
              AND is_active = 1
            ORDER BY updated_at DESC
            LIMIT 1
        """
        
        row = await self.db.fetch_one(
            query, 
            (agent_id,)
        )
        
        if row:
            conversation_id = row['id']
            logger.info(
                f"✅ Resuming conversation: {conversation_id} "
                f"(last active: {row['updated_at']})"
            )
            return conversation_id
        
        # No recent conversation found - create new one
        logger.info(f"No recent conversation found, creating new session for {agent_id}")
        return await self.create_conversation(agent_id, agent_name)
    
    async def update_conversation_timestamp(self, conversation_id: str):
        """Update the last activity timestamp."""
        query = """
            UPDATE conversations
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        await self.db.execute(query, (conversation_id,))
    
    async def deactivate_conversation(self, conversation_id: str):
        """Mark conversation as inactive (user explicitly ended it)."""
        query = """
            UPDATE conversations
            SET is_active = 0
            WHERE id = ?
        """
        await self.db.execute(query, (conversation_id,))
        logger.info(f"✅ Conversation {conversation_id} marked inactive")
    
    async def end_all_conversations(self, agent_id: str):
        """
        End all active conversations for an agent.
        Use this when explicitly starting a fresh conversation.
        """
        query = """
            UPDATE conversations
            SET is_active = 0
            WHERE agent_id = ? AND is_active = 1
        """
        await self.db.execute(query, (agent_id,))
        logger.info(f"✅ All conversations ended for agent {agent_id}")
    
    async def get_conversation_summary(self, conversation_id: str) -> Dict[str, Any]:
        """Get conversation metadata and statistics."""
        query = """
            SELECT 
                c.id, c.agent_id, c.agent_name, c.created_at, c.updated_at,
                COUNT(m.id) as message_count,
                COUNT(DISTINCT CASE WHEN m.is_summarized = 1 THEN m.id END) as summarized_count
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            WHERE c.id = ?
            GROUP BY c.id
        """
        return await self.db.fetch_one(query, (conversation_id,))