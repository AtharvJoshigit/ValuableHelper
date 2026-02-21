"""
Turn Result
=============

A clean serialisation boundary for a completed user turn.
After the agentic loop finishes processing one user message, the orchestrator produces a TurnResult that contains everything needed to:

1. **Send to the frontend** - > response_text", "is_final", etc.

2. **Persist to the DB** -- history_snapshot is a list of plain dicts 
    (provider-independent) that can be stored as JSON and later reloaded to reconstruct the conversation.

This keeps the in-RAM streaming / iteration state (StreamingJsonText Extractor raw provider objects, etc.) 
separate from the clean output that crosses the process boundary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.schemas.response import AgentResponse
from pydantic import BaseModel, Field



class TurnResult(BaseModel):
    """
    Immutable output of a single user turn through the agentic loop.

    This is the object you hand to your backend / WebSocket / DB layer.
    It contains no raw provider objects or in-flight streaming state.
    """

    # ------------------------------------------------------------------
    # User-facing payload
    # ------------------------------------------------------------------

    response: AgentResponse = Field(
        description="The final structured response from the model.",
    )

    exit_reason: str = Field(
        description="Why the loop stopped (completed | max_iterations | error | no_tool).",
    )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    iterations_used: int = Field(
        default=0,
        description="How many loop iterations were consumed.",
    )

    tool_calls_made: int = Field(
        default=0,
        description="Total number of tool calls executed in this turn.",
    )

    # ------------------------------------------------------------------
    # Serializable history snapshot
    # ------------------------------------------------------------------

    history_snapshot: List[Dict[str, Any]] = Field(
        description=(
            "Provider-independent serialisation of the full conversation "
            "history after this turn. Each entry is a Message.to_dict() "
            "output. Store this in DB; reload with Message.from_dict()."
        ),
    )

    # ------------------------------------------------------------------
    # Thought text (optional, for logging/debugging)
    # ------------------------------------------------------------------

    last_thought_text: Optional[str] = Field(
        default=None,
        description="The model's last thought summary (not user-facing).",
    )
