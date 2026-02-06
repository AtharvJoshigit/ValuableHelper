from typing import List, Optional
from universal_agent_framework.core.types import Message, Role

class Memory:
    """
    Simple list-based message history management.
    """

    def __init__(self, max_messages: Optional[int] = None):
        self._history: List[Message] = []
        self.max_messages = max_messages

    def add_message(self, message: Message):
        self._history.append(message)
        
        # Keep system message + last N messages
        if self.max_messages and len(self._history) > self.max_messages:
            # Preserve system message if it exists
            system_msgs = [m for m in self._history if m.role == Role.SYSTEM]
            other_msgs = [m for m in self._history if m.role != Role.SYSTEM]
            
            # Keep most recent messages
            keep_count = self.max_messages - len(system_msgs)
            self._history = system_msgs + other_msgs[-keep_count:]

    def add_user_message(self, content: str):
        """Shortcut to add a user message."""
        self.add_message(Message(role=Role.USER, content=content))

    def get_history(self) -> List[Message]:
        """Return the full conversation history."""
        return self._history

    def clear(self):
        """Clear the history."""
        self._history = []
