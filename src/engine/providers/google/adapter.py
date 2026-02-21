"""
Google Adapter

Converts between the provider-agnostic Pydantic layer and the Gemini API
wire format (google.genai types).

thought_signature reconstruction fix
--------------------------------------
thought_signature is a field on types.Part, NOT on types.FunctionCall.
types.FunctionCall has extra_forbidden — setting thought_signature on it
raises a Pydantic validation error and the bytes are silently dropped,
causing Gemini to return:

    400 Function call is missing a thought_signature in functionCall parts.

Correct reconstruction pattern:
    types.Part(
        function_call=types.FunctionCall(name=..., args=...),
        thought_signature=tc.thought_signature,   ← on Part, not FunctionCall
    )

Schema handling
---------------
pydantic_to_google_schema() inlines all $defs/$ref entries before sending to
Gemini. Gemini does not support JSON Schema $ref — it causes silent mismatches
or 400 errors.

anyOf with null (Pydantic's Optional encoding) is unwrapped to the non-null
branch in _json_schema_to_gemini_schema().
"""

from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any, Dict, List, Optional, Type

from google.genai import types

from engine.registry.base_tool import BaseTool
from engine.schemas.message import Message, MessageKind, Role
from engine.schemas.response import AgentResponse
from engine.schemas.tool_result import ToolCall, ToolResult

logger = logging.getLogger(__name__)

_MARKDOWN_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


# ---------------------------------------------------------------------------
# Pydantic schema → Gemini response_schema
# ---------------------------------------------------------------------------

def pydantic_to_google_schema(model: Type[Any]) -> Dict[str, Any]:
    """
    Convert a Pydantic model class to a Gemini-compatible response_schema.

    Gemini does not support $ref / $defs — inlines all references first.
    Strips fields Gemini's validator rejects (title, default, examples, etc.).
    """
    raw_schema = model.model_json_schema()
    defs = raw_schema.pop("$defs", {})
    inlined = _inline_refs(raw_schema, defs)
    _clean_for_gemini(inlined)
    return inlined


def _inline_refs(schema: Any, defs: Dict[str, Any]) -> Any:
    """Recursively replace all $ref pointers with inlined copies."""
    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_name = schema["$ref"].split("/")[-1]
            if ref_name in defs:
                return _inline_refs(copy.deepcopy(defs[ref_name]), defs)
            logger.warning("Unknown $ref: %s", schema["$ref"])
            return schema
        return {k: _inline_refs(v, defs) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_inline_refs(item, defs) for item in schema]
    return schema


def _clean_for_gemini(schema: Any) -> None:
    """Recursively remove fields Gemini's schema parser does not accept."""
    if not isinstance(schema, dict):
        return
    for key in ("title", "default", "examples", "additionalProperties"):
        schema.pop(key, None)
    for v in schema.get("properties", {}).values():
        _clean_for_gemini(v)
    if "items" in schema:
        _clean_for_gemini(schema["items"])
    for combiner in ("anyOf", "oneOf", "allOf"):
        for sub in schema.get(combiner, []):
            _clean_for_gemini(sub)


# ---------------------------------------------------------------------------
# AgentResponse parser
# ---------------------------------------------------------------------------

def parse_agent_response(text: str) -> Optional[AgentResponse]:
    """
    Parse Gemini free-text output into an AgentResponse.

    Handles pure JSON, JSON in markdown fences, and JSON embedded in prose.
    """
    raw = text.strip()
    if not raw:
        return None

    # Try markdown fence first.
    match = _MARKDOWN_JSON_RE.search(raw)
    candidate = match.group(1) if match else None

    # Fall back to first {...} block.
    if not candidate:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end > start:
            candidate = raw[start:end + 1]

    if not candidate:
        return None

    try:
        data = json.loads(candidate)
        return AgentResponse.model_validate(data)
    except json.JSONDecodeError as exc:
        logger.warning("parse_agent_response: JSON parse failed — %s", exc)
    except Exception as exc:
        logger.warning("parse_agent_response: Pydantic validation failed — %s", exc)

    return None


# ---------------------------------------------------------------------------
# Tool definition → Gemini tools format
# ---------------------------------------------------------------------------

def build_google_tools(tools: List[BaseTool]) -> List[types.Tool]:
    declarations = []
    for tool in tools:
        schema = tool.get_schema()
        properties = schema.get("properties", {})
        required = schema.get("required", list(properties.keys()))

        declarations.append(
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description or f"Executes {tool.name}",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        k: _json_schema_to_gemini_schema(v)
                        for k, v in properties.items()
                    },
                    required=required,
                ),
            )
        )

    return [types.Tool(function_declarations=declarations)]


def _json_schema_to_gemini_schema(schema: Dict[str, Any]) -> types.Schema:
    """Convert a JSON Schema property dict to types.Schema."""
    type_map = {
        "string":  types.Type.STRING,
        "integer": types.Type.INTEGER,
        "number":  types.Type.NUMBER,
        "boolean": types.Type.BOOLEAN,
        "array":   types.Type.ARRAY,
        "object":  types.Type.OBJECT,
    }

    # Unwrap Optional (anyOf with a null branch).
    if "anyOf" in schema:
        non_null = [s for s in schema["anyOf"] if s.get("type") != "null"]
        if non_null:
            return _json_schema_to_gemini_schema(non_null[0])

    schema_type = type_map.get(schema.get("type", "string"), types.Type.STRING)
    kwargs: dict = {"type": schema_type}

    if "description" in schema:
        kwargs["description"] = schema["description"]
    if "enum" in schema:
        kwargs["enum"] = schema["enum"]
    if schema_type == types.Type.ARRAY and "items" in schema:
        kwargs["items"] = _json_schema_to_gemini_schema(schema["items"])
    if schema_type == types.Type.OBJECT and "properties" in schema:
        kwargs["properties"] = {
            k: _json_schema_to_gemini_schema(v)
            for k, v in schema["properties"].items()
        }
        if "required" in schema:
            kwargs["required"] = schema["required"]

    return types.Schema(**kwargs)


# ---------------------------------------------------------------------------
# History builder: Pydantic Messages → Gemini contents list
# ---------------------------------------------------------------------------

def validate_and_fix_history(messages: List[Message]) -> List[types.Content]:
    """
    Convert Pydantic Messages to Gemini types.Content objects.

    Reconstruction rules
    --------------------
    MODEL + TOOL_CALL  → role="model", parts=[Part(function_call=..., thought_signature=...)]
                         thought_signature set on Part (NOT on FunctionCall).
    USER + TOOL_RESULT → role="user",  parts=[Part(function_response=...)]
    MODEL text         → role="model", parts=[Part(text=...)]
    USER text          → role="user",  parts=[Part(text=...)]
    """
    contents: List[types.Content] = []

    for msg in messages:
        
        logger.info(f"Message Kind: {msg.kind}")
        # ── Model tool-call turn ────────────────────────────────────────
        if msg.role == Role.MODEL and msg.kind == MessageKind.TOOL_CALL:
            parts: List[types.Part] = []
            if msg._raw_provider_content:
                contents.append(msg._raw_provider_content)
                continue
            if hasattr(msg, ' thought_text') and msg.thought_text:
                parts.append(types.Part(thought=True, text=msg.thought_text))

            for tc in (msg.tool_calls or []):
                # Reconstruct the Part.
                # CRITICAL: thought_signature goes on types.Part, not on
                # types.FunctionCall. FunctionCall has extra_forbidden —
                # setting thought_signature there raises a silent error and
                # Gemini never receives the signature, causing the 400.
                part_kwargs: dict = {
                    "function_call": types.FunctionCall(
                        name=tc.name,
                        args=tc.arguments,
                    ),
                }

                if tc.thought_signature is not None:
                    part_kwargs["thought_signature"] = tc.thought_signature
                    logger.debug(
                        "Replaying thought_signature for '%s' (%d bytes)",
                        tc.name, len(tc.thought_signature),
                    )
                else:
                    logger.debug(
                        "No thought_signature to replay for '%s' "
                        "(non-thinking model or first call)",
                        tc.name,
                    )

                parts.append(types.Part(**part_kwargs))

            if parts:
                contents.append(types.Content(role="model", parts=parts))
            continue

        # ── Tool result turn ────────────────────────────────────────────
        if msg.kind == MessageKind.TOOL_RESULT:
            parts = []
            for tr in (msg.tool_results or []):
                parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=tr.name,
                            response={
                                "result": tr.result,
                                "is_error": tr.is_error,
                            },
                        )
                    )
                )
            if parts:
                contents.append(types.Content(role="user", parts=parts))
            continue

        # ── Plain model text ────────────────────────────────────────────
        if msg.role == Role.MODEL:
            if msg._raw_provider_content:
                contents.append(msg._raw_provider_content)
                continue
            text = msg.text or ""
            if text:
                contents.append(
                    types.Content(role="model", parts=[types.Part(text=text)])
                )
            continue

        # ── User text ───────────────────────────────────────────────────
        text = msg.text or ""
        if text:
            contents.append(
                types.Content(role="user", parts=[types.Part(text=text)])
            )

    return contents