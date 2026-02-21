"""
OpenAI Provider

Provider contract (shared with all providers):
    call_model() → (agent_response, reasoning_text, tool_calls)

    agent_response — Parsed AgentResponse, or None when model called a tool,
                     or None on error (orchestrator gets an error description
                     via the tool_calls list in that case).
    reasoning_text — Accumulated reasoning tokens (o-series), or None.
    tool_calls     — List[ToolCall] parsed into provider-agnostic Pydantic
                     objects. Carries ToolCall.id for OpenAI history replay.
                     May contain synthetic error entries if argument parsing
                     failed — the orchestrator returns these to the model.

Design notes
------------
* raw_provider_content is NOT used. Tool call ids are stored on ToolCall.id
  and the adapter reconstructs assistant messages from pure Pydantic models.

* Structured Outputs (response_format=json_schema) are toggleable via
  supports_structured_output. Disable this when pointing at Gemini via the
  OpenAI-compatible endpoint — Gemini does not support strict=True and will
  return a 400.

* o-series parameters (reasoning_effort) are only forwarded when the model
  id starts with "o" — other models reject them.

* Stream tool call buffers use lists rather than string concatenation so
  "".join() is used at the end (more memory-efficient in tight async loops).

* Malformed tool call arguments are NOT silently dropped. A synthetic error
  ToolResult is returned to the orchestrator which feeds it back to the model
  so it can self-correct.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Callable, List, Optional, Tuple

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessage
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)

from engine.registry.base_tool import BaseTool
from engine.schemas.message import Message
from engine.schemas.response import AgentResponse
from engine.schemas.tool_result import ToolCall
from engine.providers.openai.adapter import (
    build_openai_tools,
    validate_and_fix_history,
    StreamingJsonTextExtractor,
    AgentResponseParseError,
    pydantic_to_openai_response_format,
)

logger = logging.getLogger(__name__)

# Parameters safe to forward to the completions endpoint.
# Constructor-level keys (base_url) and model-specific keys are handled
# separately — see _build_call_kwargs.
_SAFE_COMPLETION_PARAMS = frozenset({
    "frequency_penalty",
    "logit_bias",
    "logprobs",
    "n",
    "presence_penalty",
    "seed",
    "stop",
    "stream_options",
    "top_logprobs",
    "user",
})

# o-series models accept reasoning_effort; standard models reject it.
_O_SERIES_PARAMS = frozenset({"reasoning_effort"})

# Provider contract return type.
ProviderResult = Tuple[
    Optional[AgentResponse],   # parsed structured response (or None)
    Optional[str],             # reasoning text (or None)
    List[ToolCall],            # pre-parsed provider-agnostic tool calls
]


class OpenAIProvider:
    """
    Production OpenAI provider.

    Parameters
    ----------
    model_id:
        Any OpenAI model string, or a Gemini model string when base_url
        points at the Gemini OpenAI-compatible endpoint.
    supports_structured_output:
        Set False for models that do not support OpenAI Structured Outputs
        (e.g. Gemini via OpenAI-compatible endpoint, older GPT models).
        When False, response_format is omitted entirely.
    """

    def __init__(
        self,
        model_id: str = "gpt-4o",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        system_instruction: str = "You are a Helpful Assistant",
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        on_text_chunk: Optional[Callable[[str], None]] = None,
        supports_structured_output: bool = True,
        **additional_params,
    ) -> None:
        self.model_id = model_id
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.on_text_chunk = on_text_chunk
        self.system_instruction = system_instruction
        self.supports_structured_output = supports_structured_output

        # Determine whether this looks like an o-series model so we know
        # whether to forward reasoning_effort.
        self._is_o_series = model_id.startswith("o")

        # Filter to params safe for the completions endpoint.
        safe_keys = _SAFE_COMPLETION_PARAMS | (_O_SERIES_PARAMS if self._is_o_series else set())
        self.additional_params = {
            k: v for k, v in additional_params.items() if k in safe_keys
        }

        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY or pass api_key=."
            )

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=additional_params.get("base_url"),
        )

        logger.info(
            "OpenAI Provider initialised: model=%s temperature=%s "
            "max_tokens=%s structured_output=%s o_series=%s",
            model_id, temperature,
            max_tokens or "default",
            supports_structured_output,
            self._is_o_series,
        )

    # ------------------------------------------------------------------
    # Config builder
    # ------------------------------------------------------------------

    def _build_call_kwargs(self, tools: List[BaseTool]) -> dict:
        kwargs: dict = {
            "model": self.model_id,
            "temperature": self.temperature,
        }

        if self.top_p is not None:
            kwargs["top_p"] = self.top_p
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens

        # Only add response_format if the model supports it.
        if self.supports_structured_output:
            kwargs["response_format"] = pydantic_to_openai_response_format(AgentResponse)

        if tools:
            kwargs["tools"] = build_openai_tools(tools)
            kwargs["tool_choice"] = "auto"

        kwargs.update(self.additional_params)
        return kwargs

    # ------------------------------------------------------------------
    # Public: model call
    # ------------------------------------------------------------------

    async def call_model(
        self,
        history: List[Message],
        tools: Optional[List[BaseTool]] = None,
    ) -> ProviderResult:
        """
        Stream one model turn and return the provider-contract 3-tuple:
            (agent_response, reasoning_text, tool_calls)

        tool_calls are fully parsed ToolCall objects with .id set so the
        adapter can round-trip them through history without raw content.

        On unrecoverable error returns (None, None, []).
        """
        if tools is None:
            tools = []

        extractor = StreamingJsonTextExtractor()
        accumulated_content: list[str] = []
        accumulated_reasoning: list[str] = []

        # Use lists everywhere in the stream buffer — joined at the end.
        # Maps stream index → {"id": [...], "name": [...], "arguments": [...]}
        tool_calls_buffer: dict[int, dict[str, list[str]]] = {}

        try:
            messages = validate_and_fix_history(
                history, system_instruction=self.system_instruction
            )
            call_kwargs = self._build_call_kwargs(tools)

            stream = await self.client.chat.completions.create(
                messages=messages,
                stream=True,
                **call_kwargs,
            )

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # Reasoning tokens (o-series).
                reasoning_fragment = getattr(delta, "reasoning_content", None)
                if reasoning_fragment:
                    accumulated_reasoning.append(reasoning_fragment)

                # Text content.
                if delta.content:
                    accumulated_content.append(delta.content)
                    for fragment in extractor.feed(delta.content):
                        if self.on_text_chunk:
                            self.on_text_chunk(fragment)

                # Tool call stream deltas — list-based accumulation.
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx: int = tc_delta.index if tc_delta.index is not None else 0
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": [],
                                "name": [],
                                "arguments": [],
                            }
                        slot = tool_calls_buffer[idx]
                        if tc_delta.id:
                            slot["id"].append(tc_delta.id)
                        if tc_delta.function:
                            if tc_delta.function.name:
                                slot["name"].append(tc_delta.function.name)
                            if tc_delta.function.arguments:
                                slot["arguments"].append(tc_delta.function.arguments)

        except Exception as exc:
            logger.error("OpenAI stream error: %s", exc, exc_info=True)
            return None, None, []

        # ------------------------------------------------------------------
        # Assemble tool calls from buffers.
        # Malformed JSON arguments produce a synthetic error ToolCall that
        # the orchestrator returns to the model as a ToolResult so it can
        # self-correct rather than silently getting empty arguments.
        # ------------------------------------------------------------------
        parsed_tool_calls: List[ToolCall] = []

        for idx in sorted(tool_calls_buffer):
            slot = tool_calls_buffer[idx]
            fn_name = "".join(slot["name"]).strip()
            fn_args_raw = "".join(slot["arguments"])
            call_id = "".join(slot["id"]) or f"call_synthetic_{idx}"

            if not fn_name:
                logger.warning(
                    "Skipping tool call at index %d: name is empty. Buffer: %s",
                    idx, slot,
                )
                continue

            try:
                parsed_args = json.loads(fn_args_raw) if fn_args_raw.strip() else {}
            except json.JSONDecodeError as exc:
                logger.warning(
                    "Malformed JSON arguments for tool '%s' (id=%s): %s",
                    fn_name, call_id, exc,
                )
                # Return a sentinel ToolCall that the orchestrator will convert
                # to an error ToolResult and feed back to the model.
                parsed_tool_calls.append(
                    ToolCall(
                        name=fn_name,
                        arguments={
                            "__parse_error__": (
                                f"Invalid JSON arguments: {exc}. "
                                "Fix the syntax and try again."
                            )
                        },
                        id=call_id,
                    )
                )
                continue

            parsed_tool_calls.append(
                ToolCall(name=fn_name, arguments=parsed_args, id=call_id)
            )

        # ------------------------------------------------------------------
        # Parse structured response (only when model did not call tools).
        # AgentResponseParseError propagates so the orchestrator can feed
        # the validation failure back to the model.
        # ------------------------------------------------------------------
        reasoning_text: Optional[str] = (
            "".join(accumulated_reasoning) or None
        )
        agent_response: Optional[AgentResponse] = None

        if not parsed_tool_calls:
            try:
                agent_response = extractor.finalize()
            except AgentResponseParseError:
                raise  # orchestrator handles this
            if agent_response is None and accumulated_content:
                logger.warning(
                    "Non-empty content could not be parsed as AgentResponse "
                    "(first 200 chars): %.200s",
                    "".join(accumulated_content),
                )

        logger.debug(
            "call_model — tool_calls=%d agent_response=%s reasoning=%s",
            len(parsed_tool_calls),
            agent_response is not None,
            reasoning_text is not None,
        )
        return agent_response, reasoning_text, parsed_tool_calls