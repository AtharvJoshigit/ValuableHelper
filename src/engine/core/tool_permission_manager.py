from typing import Set

from engine.core.types import ToolCall

class ToolPermissionManager:
    """
    Manages permissions and sensitivity checks for tool calls.
    """

    def __init__(self, sensitive_tools: Set[str] = None):
        """
        Initializes the ToolPermissionManager.

        Args:
            sensitive_tools: A set of tool names considered sensitive.
                             If None, a default set of sensitive tools will be used.
        """
        self._sensitive_tools = sensitive_tools or {
            'system_operator',
            'coder_agent',
            'gmail_send',
            'send_telegram_message',
            'run_command',
            'create_file',
            'str_replace'
        }

    def is_sensitive(self, tool_call: ToolCall) -> bool:
        """
        Check if a tool call involves sensitive operations requiring approval.

        Args:
            tool_call: The tool call to check.

        Returns:
            True if the tool is in the sensitive list, False otherwise.
        """
        return tool_call.name in self._sensitive_tools
