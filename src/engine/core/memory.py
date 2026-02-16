# engine/core/memory.py (DEPRECATED - Use MemoryManager instead)
"""
DEPRECATED: This simple in-memory version is replaced by MemoryManager.
Kept for backward compatibility only.
Use engine.core.memory_manager.MemoryManager for production.
"""
from typing import List, Optional
from engine.core.types import Message, Role
import logging

logger = logging.getLogger(__name__)

class Memory:
    """
    DEPRECATED: Simple list-based message history management.
    Use MemoryManager for production with database backing.
    """

    def __init__(self, max_messages: Optional[int] = None):
        logger.warning(
            "⚠️ Using deprecated Memory class. "
            "Please migrate to MemoryManager for database-backed memory."
        )
        self._history: List[Message] = []
        self.max_messages = max_messages

    def add_message(self, message: Message):
        self._history.append(message)
        
        if self.max_messages and len(self._history) > self.max_messages:
            system_msgs = [m for m in self._history if m.role == Role.SYSTEM]
            other_msgs = [m for m in self._history if m.role != Role.SYSTEM]
            keep_count = self.max_messages - len(system_msgs)
            self._history = system_msgs + other_msgs[-keep_count:]

    def add_user_message(self, content: str):
        self.add_message(Message(role=Role.USER, content=content))

    def get_history(self) -> List[Message]:
        return self._history

    def clear(self):
        self._history = []