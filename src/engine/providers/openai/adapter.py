"""
OpenAI Adapter

Converts between the provider-agnostic Pydantic layer and the OpenAI API wire
format.  All reconstruction is done from pure Pydantic models — there is no
dependency on cached raw provider objects.

Tool call ids (ToolCall.id) and any other round-trip fields are carried on
the Pydantic models themselves, so history replay is accurate without needing
to cache ChatCompletionMessage instances.

Turn ordering rules enforced here:
  system (optional, first only)
  user
  assistant                     ← plain response
  assistant (tool_calls=[…])   ← model requesting tools
  tool (tool_call_id=…) ×N    ← one per tool call
  user / assistant / …          ← conversation continues
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Type

from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
    ChatCompletionSystemMessageParam,
)

from engine.core.turn_manager import validate_message_ordering
from engine.registry.base_tool import BaseTool
from engine.schemas.message import Message, MessageKind, Role
from engine.schemas.response import AgentResponse
from engine.schemas.tool_result import ToolCall

logger = logging.getLogger(__name__)

# Matches ```json ... ``` or ``` ... ``` with optional surrounding whitespace.
_MARKDOWN_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


# ---------------------------------------------------------------------------
# Streaming JSON extractor
# ---------------------------------------------------------------------------

class StreamingJsonTextExtractor:
    """
    Accumulates streamed text fragments and parses the final AgentResponse
    once streaming is complete.

    Handles markdown code fences robustly via regex rather than brittle
    line-splitting (trailing whitespace/newlines after the fence would break
    a line-based approach).
    """

    def __init__(self) -> None:
        self._buffer: list[str] = []

    def feed(self, fragment: str) -> list[str]:
        self._buffer.append(fragment)
        return [fragment]

    def finalize(self) -> Optional[AgentResponse]:
        raw = "".join(self._buffer).strip()
        if not raw:
            return None

        # Strip markdown fences if present.
        match = _MARKDOWN_JSON_RE.search(raw)
        if match:
            raw = match.group(1)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("StreamingJsonTextExtractor: invalid JSON — %s", exc)
            return None

        try:
            return AgentResponse.model_validate(data)
        except Exception as exc:
            # Surface the validation error so the orchestrator can feed it
            # back to the model rather than silently retrying.
            logger.warning(
                "StreamingJsonTextExtractor: AgentResponse validation failed — %s", exc
            )
            # Re-raise as a domain exception the orchestrator can catch.
            raise AgentResponseParseError(str(exc), raw_json=raw) from exc


class AgentResponseParseError(Exception):
    """Raised when the model's JSON is syntactically valid but fails Pydantic validation."""

    def __init__(self, detail: str, raw_json: str = "") -> None:
        super().__init__(detail)
        self.raw_json = raw_json


# ---------------------------------------------------------------------------
# Pydantic schema → OpenAI response_format (Structured Outputs)
# ---------------------------------------------------------------------------

def pydantic_to_openai_response_format(model: Type[Any]) -> Dict[str, Any]:
    """
    Convert a Pydantic model class to the OpenAI ``response_format`` dict.

    Uses ``strict=True`` which requires every property in ``required`` and
    no ``additionalProperties``.  ``_make_strict`` patches the schema to
    comply while skipping bare ``{"type": "null"}`` stubs emitted by Pydantic
    for Optional fields (patching those produces invalid schemas that fail
    OpenAI's validation).
    """
    schema = model.model_json_schema()
    _make_strict(schema)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": model.__name__,
            "schema": schema,
            "strict": True,
        },
    }


def _make_strict(schema: Dict[str, Any]) -> None:
    """
    Recursively patch a JSON schema for OpenAI strict mode.

    Only applies additionalProperties/required to actual object nodes.
    Bare ``{"type": "null"}`` entries in anyOf are skipped.
    """
    if schema.get("type") == "object" or "properties" in schema:
        props = schema.get("properties", {})
        schema["additionalProperties"] = False
        schema["required"] = list(props.keys())
        for prop_schema in props.values():
            _make_strict(prop_schema)

    if "items" in schema:
        _make_strict(schema["items"])

    for combiner in ("anyOf", "oneOf", "allOf"):
        for sub in schema.get(combiner, []):
            if sub.get("type") == "null" and len(sub) == 1:
                continue
            _make_strict(sub)

    for def_schema in schema.get("$defs", {}).values():
        _make_strict(def_schema)


# ---------------------------------------------------------------------------
# Tool definition → OpenAI tools[] format
# ---------------------------------------------------------------------------

def build_openai_tools(tools: List[BaseTool]) -> List[Dict[str, Any]]:
    result = []
    for tool in tools:
        schema = tool.get_schema()
        properties = schema.get("properties", {})
        required = schema.get("required", list(properties.keys()))
        result.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or f"Executes {tool.name}",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
            },
        })
    return result


# ---------------------------------------------------------------------------
# Message conversion: Pydantic Message → OpenAI ChatCompletionMessageParam
# ---------------------------------------------------------------------------

def message_to_openai_param(msg: Message) -> List[ChatCompletionMessageParam]:
    """
    Convert a single Pydantic Message to one *or more* OpenAI message dicts.

    Reconstruction is done entirely from the Pydantic model fields:
      - ToolCall.id carries the tool_call_id for exact round-trip matching.
      - No raw provider objects are read here.

    TOOL_RESULT messages expand into one dict per result (one tool_call_id each).
    """

    # ── Model turns ────────────────────────────────────────────────────────
    if msg.role == Role.MODEL:

        if msg.kind == MessageKind.TOOL_CALL:
            if not msg.tool_calls:
                logger.warning("TOOL_CALL message has no tool_calls — skipping.")
                return []
            return [
                ChatCompletionAssistantMessageParam(
                    role="assistant",
                    # content must be None when tool_calls are present (OpenAI spec).
                    content=None,
                    tool_calls=[
                        {
                            "id": tc.id or f"call_{i}_{tc.name}",
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for i, tc in enumerate(msg.tool_calls)
                    ],
                )
            ]

        # Plain text / structured model message.
        return [
            ChatCompletionAssistantMessageParam(
                role="assistant",
                content=msg.text or "",
            )
        ]

    # ── Tool results ────────────────────────────────────────────────────────
    # OpenAI tool message spec: role, tool_call_id, content only.
    # The `name` field is NOT in the spec and causes API errors if included.
    if msg.kind == MessageKind.TOOL_RESULT:
        params: List[ChatCompletionMessageParam] = []
        for tr in msg.tool_results:
            params.append(
                ChatCompletionToolMessageParam(
                    role="tool",
                    tool_call_id=tr.id or f"call_{tr.name}",
                    content=json.dumps({"result": tr.result, "is_error": tr.is_error}),
                )
            )
        return params

    # ── User text ──────────────────────────────────────────────────────────
    return [
        ChatCompletionUserMessageParam(
            role="user",
            content=msg.text or "",
        )
    ]


# ---------------------------------------------------------------------------
# History validation
# ---------------------------------------------------------------------------

def validate_and_fix_history(
    messages: List[Message],
    *,
    system_instruction: Optional[str] = None,
) -> List[ChatCompletionMessageParam]:
    """
    Convert Pydantic Messages to OpenAI params, enforcing ordering rules.

    1. Inject system message first if provided.
    2. Provider-independent ordering validation.
    3. Convert each Message via message_to_openai_param().
    4. Validate tool_call / tool message pairing.
    """
    params: List[ChatCompletionMessageParam] = []

    if system_instruction:
        params.append(
            ChatCompletionSystemMessageParam(role="system", content=system_instruction)
        )

    if not messages:
        return params

    validated = validate_message_ordering(messages)
    for msg in validated:
        params.extend(message_to_openai_param(msg))

    _validate_tool_call_pairing(params)
    return params


def _validate_tool_call_pairing(params: List[ChatCompletionMessageParam]) -> None:
    for i, param in enumerate(params):
        if param.get("role") != "assistant":
            continue
        tool_calls = param.get("tool_calls")
        if not tool_calls:
            continue

        expected_ids = {tc["id"] for tc in tool_calls}
        found_ids: set[str] = set()
        j = i + 1
        while j < len(params) and params[j].get("role") == "tool":
            found_ids.add(params[j]["tool_call_id"])
            j += 1

        missing = expected_ids - found_ids
        if missing:
            logger.error(
                "History: tool_calls at index %d missing responses for ids: %s "
                "— API call will likely be rejected.",
                i, missing,
            )