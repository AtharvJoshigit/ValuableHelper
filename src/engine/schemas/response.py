"""
Core response schema the structured JSON format that the LLM must return.
This is provider-Independent. The Google adapter converts it into the response schema parameter that Gemini expects, 
and parses Gemini's structured output back into these Pydantic models.

"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------
# Tool categories the LLM can request
# ----------------------------------------------------------------------

class ToolCategory(str, Enum):
    """
    Predefined capability buckets. Extend this enum whenever a new
    domain of tools is onboarded into the tool-router.
    """

    MESSAGE = "message"
    FINANCE = "finance"
    CALENDAR = "calendar"
    SEARCH = "search"
    CODE_EXECUTION = "code_execution"
    DATABASE = "database"
    FILE_MANAGEMENT = "file_management"
    NOTIFICATION = "notification"
    ANALYTICS = "analytics"
    EXTERNAL_API = "external_api"


class ToolSuggestion(BaseModel):
    """
    A single tool the LLM believes it will need in the next iteration.
    The orchestrator uses these suggestions to pre-fetch tools from
    the tool-router before the next LLM call.
    """

    category: ToolCategory = Field(
        description="High-level capability bucket (e.g. 'finance', 'message').",
    )

    tool_name: Optional[str] = Field(
        default=None,
        description=(
            "Specific tool name if the model knows it, e.g. "
            "'get_stock_price'. None means 'give me all tools in this category'."
        ),
    )

    reason: str = Field(
        description="Why the model thinks this tool is needed next.",
    )

    priority: int = Field(
        default=1,
        ge=1,
        le=5,
        description="1 highest priority, 5 lowest.",
    )


# ----------------------------------------------------------------------
# Metadata
# ----------------------------------------------------------------------

class ResponseMetadata(BaseModel):
    """
    Optional metadata the model can attach to its response.
    """

    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Model's self-assessed confidence (0-1).",
    )

    reasoning_summary: Optional[str] = Field(
        default=None,
        description="Brief internal chain-of-thought summary.",
    )

    follow_up_questions: List[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions for the user.",
    )


# ----------------------------------------------------------------------
# Top-level structured response
# ----------------------------------------------------------------------

class AgentResponse(BaseModel):
    """
    The canonical response schema sent to the LLM as `response_schema`.

    Fields
    ------
    response_text: str
        The human-readable answer for the end-user.
        This is the only field surfaced in the streaming user channel.

    needs_tool_call: bool
        True when the model wants to invoke a tool right now
        (current iteration). The orchestrator should inspect the
        function-call part of the LLM reply for details.

    suggested_tools: List[ToolSuggestion]
        Tools the model anticipates needing in future iterations.
        The orchestrator pre-loads these from the tool-router.

    is_final: bool
        True when the model considers the task complete.

    metadata: Optional[ResponseMetadata]
        Optional quality / debugging metadata.
    """

    response_text: str = Field(
        description="The complete user-facing answer text.",
    )

    needs_tool_call: bool = Field(
        default=False,
        description="Whether the model wants to invoke a tool in this turn.",
    )

    suggested_tools: List[ToolSuggestion] = Field(
        default_factory=list,
        description=(
            "Tools the model predicts it will need in the next iteration. "
            "The orchestrator pre-fetches them from the tool-router."
        ),
    )

    is_final: bool = Field(
        default=True,
        description="True if the model considers the conversation turn complete.",
    )

    metadata: Optional[ResponseMetadata] = Field(
        default=None,
        description="Optional reasoning/confidence metadata.",
    )
