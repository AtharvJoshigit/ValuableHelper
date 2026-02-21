"""
=============
Turn manager
=============

Provider-independent turn-ordering logic.
This module enforces the strict alternation rules that multi-turn LLM APIS require 
(user -> model -> user -> model) without importing anything from a specific provider (Google, OpenAI, etc.).
The adapter layer calls these helpers to validate / fix the abstract Message list "before" converting to provider-specific Content objects.

Responsibilities
1. Ensure roles alternate (merge consecutive same-role messages).
2. Ensure function_call messages are followed by function_response.
3. Ensure the first message is always a user message.
4. Provide a clean messages_to_history_dicts() for DB persistence.

This is intentionally kept separate from adapters so that:

- Any new provider adapter can reuse the same validation.

The orchestrator can validate the abstract history without coupling to a specific provider SDK.
"""


from __future__ import annotations

import logging
from typing import Any, Dict, List

from engine.schemas.message import Message, MessageKind, Role

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract history validation
# ---------------------------------------------------------------------------

def validate_message_ordering(messages: List[Message]) -> List[Message]:
    """
    Validate and fix the abstract Message list so that roles alternate correctly.

    Rules applied:
    1. First message must be role=USER.
    2. Consecutive messages with the same effective role are merged.
    3. A TOOL_CALL (model) must be followed by TOOL_RESULT (user).

    Returns a new list (the input is not mutated).
    """
    if not messages:
        return []

    result: List[Message] = []

    for msg in messages:
        effective_role = _effective_role(msg)

        if not result:
            # First message must be user
            if effective_role != Role.USER:
                result.append(Message.user("(start)"))
            result.append(msg)
            continue

        last_role = _effective_role(result[-1])

        if last_role == effective_role:
            # Same effective role → merge into the last message
            result[-1] = _merge_messages(result[-1], msg)
            logger.debug(
                "Merged consecutive %s messages (%s + %s)",
                effective_role.value,
                result[-1].kind.value,
                msg.kind.value,
            )
        else:
            result.append(msg)

    # Validate function_call → function_response pairing
    _validate_tool_call_pairing(result)

    return result


def _effective_role(msg: Message) -> Role:
    """
    Return the effective role for turn-ordering purposes.

    TOOL_RESULT messages are sent as role=USER in Google format,
    so their effective role is USER regardless of what msg.role says.
    """
    if msg.kind == MessageKind.TOOL_RESULT:
        return Role.USER

    return msg.role


def _merge_messages(existing: Message, incoming: Message) -> Message:
    """
    Merge two messages with the same effective role into one.

    For text messages, concatenate text.
    For tool calls, extend the lists.
    For tool results, extend the lists.

    Preserve raw_provider_content from the first message.
    """
    merged_text_parts: List[str] = []

    if existing.text:
        merged_text_parts.append(existing.text)

    if incoming.text:
        merged_text_parts.append(incoming.text)

    merged = Message(
        role=existing.role,
        kind=existing.kind,
        text="\n".join(merged_text_parts) if merged_text_parts else None,
        tool_calls=list(existing.tool_calls) + list(incoming.tool_calls),
        tool_results=list(existing.tool_results) + list(incoming.tool_results),
        structured_response=incoming.structured_response
        or existing.structured_response,
        thought_text=incoming.thought_text or existing.thought_text,
    )

    # Preserve raw provider content from existing
    merged._raw_provider_content = existing._raw_provider_content

    return merged


def _validate_tool_call_pairing(messages: List[Message]) -> None:
    """
    Verify that every TOOL_CALL message is immediately followed by a
    TOOL_RESULT message. Logs warnings but does not raise.
    """
    for i, msg in enumerate(messages):
        if msg.kind == MessageKind.TOOL_CALL:
            if i + 1 >= len(messages):
                logger.warning(
                    "History ends with a TOOL_CALL at index %d - "
                    "the next turn must provide TOOL_RESULT.",
                    i,
                )
                continue

            next_msg = messages[i + 1]

            if next_msg.kind != MessageKind.TOOL_RESULT:
                logger.warning(
                    "TOOL_CALL at index %d is not followed by TOOL_RESULT. "
                    "Got kind=%s",
                    i,
                    next_msg.kind.value,
                )


# ---------------------------------------------------------------------------
# History serialisation (for DB persistence)
# ---------------------------------------------------------------------------

def messages_to_history_dicts(
    messages: List[Message],
) -> List[Dict[str, Any]]:
    """
    Convert a list of Messages to plain dicts for DB storage.

    Strips provider-specific raw content.
    """
    return [msg.to_dict() for msg in messages]


def history_dicts_to_messages(
    dicts: List[Dict[str, Any]],
) -> List[Message]:
    """
    Reconstruct Messages from plain dicts loaded from the DB.
    """
    return [Message.from_dict(d) for d in dicts]