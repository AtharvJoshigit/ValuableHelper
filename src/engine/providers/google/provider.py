"""
Google (Gemini) Provider

Implements the shared provider contract:
    call_model() → (agent_response, reasoning_text, tool_calls)

thought_signature fix
---------------------
thought_signature is a field on types.Part, NOT on types.FunctionCall.
types.FunctionCall has extra_forbidden — passing thought_signature to its
constructor raises a Pydantic validation error and the bytes are silently
dropped, which is why the 400 persists even after adding the field to ToolCall.

Correct extraction:
    part.thought_signature          ← RIGHT  (types.Part field)
    part.function_call.thought_signature  ← WRONG (field doesn't exist)

Correct reconstruction (in adapter):
    types.Part(function_call=..., thought_signature=bytes)   ← RIGHT
    types.FunctionCall(..., thought_signature=bytes)          ← WRONG

Gemini mutual-exclusion constraint
------------------------------------
response_schema/response_mime_type and tools cannot be active in the same
request. Two-mode config strategy:

  TOOL MODE   (tools are loaded):
      Omit response_schema + response_mime_type.
      Parse AgentResponse from free text via parse_agent_response().

  STRUCTURED MODE   (no tools):
      Set response_schema + response_mime_type="application/json".
      Model is API-enforced to return valid AgentResponse JSON.
"""

from __future__ import annotations

import logging
import os
from typing import Callable, List, Optional, Tuple

from engine.core.turn_manager import validate_message_ordering
from google import genai
from google.genai import types

from engine.registry.base_tool import BaseTool
from engine.schemas.message import Message
from engine.schemas.response import AgentResponse
from engine.schemas.tool_result import ToolCall
from engine.providers.google.adapter import (
    build_google_tools,
    validate_and_fix_history,
    parse_agent_response,
    pydantic_to_google_schema,
)

logger = logging.getLogger(__name__)

ProviderResult = Tuple[
    Optional[AgentResponse],
    Optional[str],
    List[ToolCall],
]


class GoogleProvider:
    """
    Production Google Gemini provider.

    Two-mode config strategy avoids the structured-output + tools mutual-
    exclusion 400 error. thought_signature is extracted from the correct
    object (types.Part) and stored on ToolCall for verbatim replay.
    """

    def __init__(
        self,
        model_id: str = "gemini-2.5-flash",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        system_instruction: str = "You are a Helpful Assistant",
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        on_text_chunk: Optional[Callable[[str], None]] = None,
        **additional_params,
    ) -> None:
        self.model_id = model_id
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.on_text_chunk = on_text_chunk
        self.system_instruction = system_instruction

        api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "Google API key required. Set GOOGLE_API_KEY or pass api_key=."
            )

        self.client = genai.Client(api_key=api_key)
        logger.info("Google Provider initialised: model=%s", model_id)

    # ------------------------------------------------------------------
    # Config builder — two-mode strategy
    # ------------------------------------------------------------------

    def _build_config(
        self,
        tools: List[BaseTool],
        *,
        tool_mode: bool,
    ) -> types.GenerateContentConfig:
        """
        Build config that avoids the structured-output + tools mutual-
        exclusion error.

        tool_mode=True  → include tools, omit response_schema.
        tool_mode=False → include response_schema, omit tools.
        """
        config_kwargs: dict = {
            "temperature": self.temperature,
            "system_instruction": self.system_instruction,
        }
        if self.top_p is not None:
            config_kwargs["top_p"] = self.top_p
        if self.max_tokens is not None:
            config_kwargs["max_output_tokens"] = self.max_tokens

        if tool_mode:
            config_kwargs["tools"] = build_google_tools(tools)
            # Do NOT set response_schema — mutual exclusion with tools.
        else:
            config_kwargs["response_schema"] = pydantic_to_google_schema(AgentResponse)
            config_kwargs["response_mime_type"] = "application/json"
            # Do NOT set tools — mutual exclusion with response_schema.

        return types.GenerateContentConfig(**config_kwargs)

    # ------------------------------------------------------------------
    # Public: model call
    # ------------------------------------------------------------------

    async def call_model(
        self,
        history: List[Message],
        tools: Optional[List[BaseTool]] = None,
    ) -> ProviderResult:
        """
        Call Gemini and return (agent_response, reasoning_text, tool_calls).

        thought_signature extraction
        ----------------------------
        Read from part.thought_signature (types.Part field).
        Do NOT read from part.function_call.thought_signature — that field
        does not exist. types.FunctionCall has extra_forbidden so passing
        thought_signature to its constructor raises a silent validation error.
        """
        if tools is None:
            tools = []

        tool_mode = bool(tools)
        print(f"tool Mode : {tool_mode}")
        try:
            history = validate_message_ordering(history)
            contents = validate_and_fix_history(history)
            config = self._build_config(tools, tool_mode=tool_mode)

            logger.info(f"Build config {config.response_schema}")
            logger.info(f'Google Contents : {contents}') 
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            logger.error("Google API error: %s", exc, exc_info=True)
            return None, None, []

        # ------------------------------------------------------------------
        # Parse response parts
        # ------------------------------------------------------------------
        tool_calls: List[ToolCall] = []
        reasoning_text: Optional[str] = None
        text_parts: list[str] = []

        try:
            candidate = response.candidates[0]
            content = candidate.content

            for part in (content.parts or []):

                # ── Thinking / reasoning part ───────────────────────────
                if getattr(part, "thought", False) and part.text:
                    reasoning_text = part.text
                    if self.on_text_chunk:
                        self.on_text_chunk(part.text)
                    continue

                # ── Regular text part ───────────────────────────────────
                if part.text and not getattr(part, "thought", False):
                    text_parts.append(part.text)
                    if self.on_text_chunk:
                        self.on_text_chunk(part.text)
                    continue

                # ── Function call part ──────────────────────────────────
                fc = getattr(part, "function_call", None)
                if fc is None:
                    continue

                fn_name = getattr(fc, "name", "") or ""
                if not fn_name:
                    logger.warning("Skipping function_call with empty name: %s", part)
                    continue

                # ── thought_signature extraction ────────────────────────
                # CORRECT: read from part.thought_signature (types.Part field).
                # WRONG:   part.function_call.thought_signature does not exist.
                #          types.FunctionCall has extra_forbidden — bytes
                #          passed to its constructor are silently dropped.
                thought_signature: Optional[bytes] = getattr(
                    part, "thought_signature", None
                )

                if thought_signature:
                    logger.debug(
                        "Captured thought_signature for tool '%s' (%d bytes)",
                        fn_name, len(thought_signature),
                    )
                else:
                    logger.debug(
                        "No thought_signature for tool '%s' "
                        "(non-thinking model or thinking disabled)",
                        fn_name,
                    )

                tool_calls.append(
                    ToolCall(
                        name=fn_name,
                        arguments=dict(fc.args) if fc.args else {},
                        thought_signature=thought_signature,
                        # id not used by Gemini, defaults to None.
                    )
                )

        except (IndexError, AttributeError) as exc:
            logger.error("Failed to parse Gemini response: %s", exc, exc_info=True)
            return None, None, []

        # ------------------------------------------------------------------
        # Parse AgentResponse from text
        # ------------------------------------------------------------------
        agent_response: Optional[AgentResponse] = None

        if not tool_calls and text_parts:
            raw_text = "".join(text_parts)
            agent_response = parse_agent_response(raw_text)

            if agent_response is None:
                logger.warning(
                    "Could not parse AgentResponse from Gemini text "
                    "(tool_mode=%s, first 200 chars): %.200s",
                    tool_mode, raw_text,
                )
                # In tool_mode the model sometimes returns prose instead of
                # JSON. Wrap it so the orchestrator has something to yield.
                if tool_mode:
                    agent_response = AgentResponse(
                        response_text=raw_text,
                        is_final=True,
                    )

        logger.debug(
            "call_model — tool_mode=%s tool_calls=%d agent_response=%s reasoning=%s",
            tool_mode, len(tool_calls),
            agent_response is not None,
            reasoning_text is not None,
        )
        if agent_response is None and text_parts: 
            agent_response = AgentResponse(
                response_text="".join(text_parts),
                is_final=False
            )
        return agent_response, reasoning_text, tool_calls, response