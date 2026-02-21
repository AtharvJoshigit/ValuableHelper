"""
Pydantic models for tool calls and tool results.
These are provider-independent adapters handle conversion to/from
provider-specific formats (Google FunctionCall/ FunctionResponse" OpenAI tool calls"/tool messages, etc.).
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class ToolCall(BaseModel):
    """
    Represents a function/tool call the model wants to make.
    """

    name: str = Field(
        ...,
        description="Name of the tool to invoke.",
    )
    
    agent_id: Optional[str] = Field(
        default="main",
        description="Name of the agent Making the call.",
    )

    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value arguments for the tool.",
    )

    id: Optional[str] = Field(
        None,
        description=(
            "Unique ID for correlating call result. "
            "Auto-generated if not supplied (required by OpenAI)."
        ),
    )
    thought_signature: Optional[bytes] = Field(
        default=None,
        description=(
            "Gemini thought_signature blob. Opaque — do not inspect or modify. "
            "The Google adapter writes it back to types.FunctionCall verbatim."
        ),
    )
    

    @model_validator(mode="after")
    def _ensure_call_id(self) -> "ToolCall":
        """Guarantee a call_id exists for providers that require it."""
        if self.id is None:
            self.id = f"call_{uuid.uuid4().hex[:24]}"
        return self


class ToolResult(BaseModel):
    """
    Result returned by an executed tool, fed back to the LLM.
    """

    name: str = Field(
        ...,
        description="Name of the tool that ran.",
    )

    id: Optional[str] = Field(
        None,
        description="Correlates with the originating ToolCall.",
    )
    
    agent_id: Optional[str] = Field(
        default="main",
        description="Name of the agent Making the call.",
    )

    result: Any = Field(
        ...,
        description="The tool's return value (must be JSON-serialisable).",
    )

    is_error: bool = Field(
        default=False,
        description="True if the tool raised an error.",
    )

    error_message: Optional[str] = Field(
        None,
        description="Human-readable error description.",
    )

    def result_as_str(self) -> str:
        """
        Serialise result to a JSON string for providers that expect
        tool output as a plain string (e.g. OpenAI).
        """
        import json

        if isinstance(self.result, str):
            return self.result

        try:
            return json.dumps(self.result, default=str)
        except (TypeError, ValueError):
            return str(self.result)
