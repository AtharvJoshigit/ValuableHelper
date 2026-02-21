"""
Provider-Independent message model used in the conversation history.

Google GenAl enforces strict turn ordering:
    user -> model -> user -> model -> ...

Where a "model" turn may contain function_call parts, and the very next "user" turn must contain the matching function_response parts.
So the valid sequences are:

    user(text)
    model (text)   <-    plain answer
    model(function_call) -> user (function_response) -> model (text) <- tool use

This module models every possible turn as a Message with a "kind"" discriminator so the adapter can convert them into the exact Google Content objects with the right role.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from engine.core.types import ToolResult
from engine.schemas.tool_result import ToolCall
from pydantic import BaseModel, Field, PrivateAttr



class Role(str, Enum):
    USER = "user"
    MODEL = "model"
    SYSTEM = "system"


class MessageKind(str, Enum):
    """Discriminator for what a Message actually carries."""

    TEXT = "text"  # plain text (user or model)
    TOOL_CALL = "tool_call"  # model requesting tool execution
    TOOL_RESULT = "tool_result"  # results fed back (sent as role-user)
    STRUCTURED = "structured"  # model returned structured JSON


class Message(BaseModel):
    """
    A single turn in the conversation.

    The kind field determines which payload fields are populated:

    kind         | role   | populated fields
    ------------------------------------------------
    TEXT         | any    | text
    TOOL_CALL    | MODEL  | tool_calls
    TOOL_RESULT  | USER   | tool_results (Google needs role="user")
    STRUCTURED   | MODEL  | text (raw JSON), structured_response
    """

    model_config = {"arbitrary_types_allowed": True}

    role: Role
    kind: MessageKind = MessageKind.TEXT

    text: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    tool_results: List[ToolResult] = Field(default_factory=list)
    structured_response: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parsed structured JSON response from the model.",
    )
    thought_text: Optional[str] = Field(
        default=None,
        description="Thinking model's thought summary (not user-facing).",
    )
    agent_id: Optional[str] = Field(
        default="main",
        description="Name of the agent Making the call.",
    )

    # Private: raw provider content (not serialised)
    # Stores the original provider object (Google Content, OpenAI
    # ChatCompletionMessage, etc.) so it can be replayed verbatim in
    # future API calls preserving thought_signature, refusal fields,
    # logprobs, etc.
    _raw_provider_content: Any = PrivateAttr(default=None)

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def user(cls, text: str) -> "Message":
        return cls(role=Role.USER, kind=MessageKind.TEXT, text=text)

    @classmethod
    def system(cls, text: str) -> "Message":
        return cls(role=Role.SYSTEM, kind=MessageKind.TEXT, text=text)

    @classmethod
    def model_text(
        cls,
        text: str,
        *,
        thought: Optional[str] = None,
        raw_provider_content: Any = None,
    ) -> "Message":
        msg = cls(
            role=Role.MODEL,
            kind=MessageKind.TEXT,
            text=text,
            thought_text=thought,
        )
        msg._raw_provider_content = raw_provider_content
        return msg

    @classmethod
    def model_tool_calls(
        cls,
        calls: List[ToolCall],
        *,
        raw_provider_content: Any = None,
        thought: Optional[str] = None,
    ) -> "Message":
        """
        Create a model message with tool calls.

        Parameters
        ----------
        raw_provider_content:
            The original provider object (e.g. Google types.Content,
            or the ChatCompletionMessage from OpenAI). If provided it
            is replayed verbatim in history, preserving thought_signature
            (Google) or tool_call id fields (OpenAI).
        """
        msg = cls(
            role=Role.MODEL,
            kind=MessageKind.TOOL_CALL,
            tool_calls=calls,
            thought_text=thought,
        )
        msg._raw_provider_content = raw_provider_content
        return msg

    @classmethod
    def tool_results_msg(cls, results: List[ToolResult]) -> "Message":
        """
        Tool results are sent with role=USER in Google's format because
        Gemini expects function_response parts inside a user Content.

        OpenAI uses role="tool" with a tool_call_id correlation.
        """
        return cls(
            role=Role.USER,
            kind=MessageKind.TOOL_RESULT,
            tool_results=results,
        )

    @classmethod
    def model_structured(
        cls,
        model_response_txt: str,
        parsed: Dict[str, Any],
        *,
        thought: Optional[str] = None,
        raw_provider_content: Any = None,
    ) -> "Message":
        msg = cls(
            role=Role.MODEL,
            kind=MessageKind.STRUCTURED,
            text=model_response_txt,
            structured_response=parsed,
            thought_text=thought,
        )
        msg._raw_provider_content = raw_provider_content
        return msg

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (provider-independent)."""
        # Private attributes are excluded automatically by Pydantic.
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Deserialise from a plain dict."""
        return cls.model_validate(data)
