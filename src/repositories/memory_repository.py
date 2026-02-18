# file: engine/core/memory_repository.py

import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime

from engine.core.types import Message, Role

logger = logging.getLogger(__name__)


class MessageRepository(ABC):
    """Abstract repository for message persistence."""
    
    @abstractmethod
    async def save_message(
        self,
        conversation_id: str,
        message: Message,
        sequence: int
    ) -> str:
        """Save a message and return its ID."""
        pass
    
    @abstractmethod
    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Message]:
        """Get messages for a conversation."""
        pass
    
    @abstractmethod
    async def get_system_message(
        self,
        conversation_id: str
    ) -> Optional[Message]:
        """Get the system message for a conversation."""
        pass
    
    @abstractmethod
    async def get_message_count(self, conversation_id: str) -> int:
        """Get total message count for conversation."""
        pass
    
    @abstractmethod
    async def delete_messages(
        self,
        conversation_id: str,
        keep_system: bool = True
    ) -> int:
        """Delete messages, optionally keeping system message."""
        pass
    
    @abstractmethod
    async def search_messages(
        self,
        conversation_id: str,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search messages by content."""
        pass
    
    @abstractmethod
    async def save_summary(
        self,
        conversation_id: str,
        summary: str,
        message_range: Dict[str, int]
    ) -> str:
        """Save a conversation summary."""
        pass
    
    @abstractmethod
    async def get_latest_summary(
        self,
        conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent summary."""
        pass


class InMemoryMessageRepository(MessageRepository):
    """
    In-memory message repository for development/testing.
    Replace with database-backed implementation for production.
    """
    
    def __init__(self):
        self._messages: Dict[str, List[Dict[str, Any]]] = {}
        self._summaries: Dict[str, List[Dict[str, Any]]] = {}
        self._counters: Dict[str, int] = {}
        self._message_id_counter = 0
    
    def _next_id(self) -> str:
        self._message_id_counter += 1
        return f"msg_{self._message_id_counter}"
    
    async def save_message(
        self,
        conversation_id: str,
        message: Message,
        sequence: int
    ) -> str:
        if conversation_id not in self._messages:
            self._messages[conversation_id] = []
        
        msg_id = self._next_id()
        
        self._messages[conversation_id].append({
            "id": msg_id,
            "sequence": sequence,
            "role": message.role,
            "content": message.content,
            "tool_calls": message.tool_calls,
            "tool_results": message.tool_results,
            "created_at": datetime.utcnow()
        })
        
        return msg_id
    
    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Message]:
        raw = self._messages.get(conversation_id, [])
        raw_sorted = sorted(raw, key=lambda x: x["sequence"])
        
        if offset:
            raw_sorted = raw_sorted[offset:]
        if limit:
            raw_sorted = raw_sorted[-limit:]
        
        return [
            Message(
                role=r["role"],
                content=r["content"],
                tool_calls=r["tool_calls"],
                tool_results=r["tool_results"]
            )
            for r in raw_sorted
        ]
    
    async def get_system_message(
        self,
        conversation_id: str
    ) -> Optional[Message]:
        raw = self._messages.get(conversation_id, [])
        for r in raw:
            if r["role"] == Role.SYSTEM:
                return Message(
                    role=r["role"],
                    content=r["content"]
                )
        return None
    
    async def get_message_count(self, conversation_id: str) -> int:
        return len(self._messages.get(conversation_id, []))
    
    async def delete_messages(
        self,
        conversation_id: str,
        keep_system: bool = True
    ) -> int:
        existing = self._messages.get(conversation_id, [])
        
        if keep_system:
            system_msgs = [m for m in existing if m["role"] == Role.SYSTEM]
            deleted = len(existing) - len(system_msgs)
            self._messages[conversation_id] = system_msgs
        else:
            deleted = len(existing)
            self._messages[conversation_id] = []
        
        return deleted
    
    async def search_messages(
        self,
        conversation_id: str,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        raw = self._messages.get(conversation_id, [])
        query_lower = query.lower()
        
        matches = []
        for msg in raw:
            content = msg.get("content") or ""
            if query_lower in content.lower():
                matches.append({
                    "id": msg["id"],
                    "role": msg["role"],
                    "content": content,
                    "created_at": msg["created_at"]
                })
        
        return matches[-limit:]
    
    async def save_summary(
        self,
        conversation_id: str,
        summary: str,
        message_range: Dict[str, int]
    ) -> str:
        if conversation_id not in self._summaries:
            self._summaries[conversation_id] = []
        
        summary_id = self._next_id()
        self._summaries[conversation_id].append({
            "id": summary_id,
            "summary": summary,
            "message_range": message_range,
            "created_at": datetime.utcnow()
        })
        
        return summary_id
    
    async def get_latest_summary(
        self,
        conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        summaries = self._summaries.get(conversation_id, [])
        if not summaries:
            return None
        return sorted(summaries, key=lambda x: x["created_at"])[-1]