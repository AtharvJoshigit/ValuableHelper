from typing import Any, Dict, Optional
from engine.core.types import ToolCall, ToolResult

class Guardrails:
    """
    Guardrails for validating tool calls and results.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize guardrails with configuration.
        
        Args:
            config: Dictionary containing configuration options like:
                    - allowed_tools: List[str]
                    - max_result_length: int
        """
        self.config = config or {}

    def validate_pre_execution(self, tool_call: ToolCall) -> None:
        """
        Validate a tool call before execution.
        
        Args:
            tool_call: The tool call to validate.
            
        Raises:
            ValueError: If validation fails.
        """
        # Check allowed tools
        allowed_tools = self.config.get("allowed_tools")
        if allowed_tools is not None and tool_call.name not in allowed_tools:
            raise ValueError(f"Security Alert: Tool '{tool_call.name}' is not allowed by current policy.")

        # Future: Add argument validation logic here
        pass

    def validate_post_execution(self, result: ToolResult) -> None:
        """
        Validate and potentially modify a tool result after execution.
        
        Args:
            result: The tool result to validate.
        """
        # Check result size limit
        max_length = self.config.get("max_result_length")
        if max_length and isinstance(result.result, str):
            if len(result.result) > max_length:
                # Truncate the result to prevent context window overflows
                result.result = result.result[:max_length] + f"\n... (truncated to {max_length} chars)"
