"""
Agent Orchestrator

Orchestrates multi-turn agent interactions.  Completely provider-agnostic.

Provider contract
-----------------
Every provider must implement:

    call_model(history, tools) → (agent_response, reasoning_text, tool_calls)

    agent_response — Parsed AgentResponse or None (None when model called a tool).
    reasoning_text — Thinking/reasoning text or None.
    tool_calls     — List[ToolCall] in provider-agnostic Pydantic form.
                     ToolCall.id carries OpenAI's tool_call_id.
                     ToolCall.thought_signature carries Gemini's signature.
                     Both are replayed by the respective adapter when building
                     the next history entry — the orchestrator never reads them.
    raw_response  - to preserve the thoughts 
The orchestrator never inspects provider-specific objects.  It only works
with the three types above plus Message / TurnResult Pydantic models.

History safety
--------------
self.history is a defensive copy of the list passed to __init__ so the
caller's list is never mutated.  Concurrent requests each get their own
AgentOrchestrator instance with their own isolated history copy.
"""

from __future__ import annotations

import copy
import logging
from enum import Enum
from typing import AsyncGenerator, Callable, List, Optional, Union

from engine.core.turn_manager import messages_to_history_dicts
from engine.core.types import StreamChunk, TurnResultChunk
from engine.executors.execution_engine import ExecutionEngine
from engine.providers.base_provider import BaseProvider
from engine.registry.base_tool import BaseTool
from engine.schemas.message import Message
from engine.schemas.response import AgentResponse
from engine.schemas.tool_result import ToolCall, ToolResult
from engine.schemas.turn_result import TurnResult
from engine.providers.openai.adapter import AgentResponseParseError

logger = logging.getLogger(__name__)


class LoopExitReason(str, Enum):
    COMPLETED = "completed"
    MAX_ITERATIONS = "max_iterations"
    ERROR = "error"
    NO_TOOL_EXECUTOR = "no_tool_executor"


StreamEvent = Union[StreamChunk, TurnResultChunk]


class AgentOrchestrator:
    """
    Orchestrates multi-turn agent interactions with structured output and
    tool calling.

    Parameters
    ----------
    provider:
        Any provider implementing the 4-tuple call_model() contract.
    execution_engine:
        Tool executor.  Pass None if this agent never calls tools.
    history:
        Initial message history.  A defensive copy is made — the caller's
        list is never mutated, making this safe for concurrent requests.
    tools:
        Initial tool set.  May be updated per-turn via tool_router.
    max_iterations:
        Hard cap on agentic loop iterations.
    on_text_chunk:
        Optional UI streaming callback.
    tool_router:
        Optional — resolves AgentResponse.suggested_tools into BaseTool
        instances for the next iteration.
    """

    def __init__(
        self,
        provider: BaseProvider,
        execution_engine: Optional[ExecutionEngine],
        history: List[Message],
        tools: List[BaseTool],
        max_iterations: int = 10,
        on_text_chunk: Optional[Callable[[str], None]] = None,
        tool_router=None,
    ) -> None:
        self.provider = provider
        self.max_iterations = max_iterations
        self.history: List[Message] = copy.copy(history)
        self.current_tools = tools
        self.on_text_chunk = on_text_chunk
        self.tool_executor = execution_engine
        self.tool_router = tool_router
        self.last_exit_reason: Optional[LoopExitReason] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, user_input: str) -> AsyncGenerator[StreamEvent, None]:
        """
        Execute a full agentic loop for one user turn.

        Yields StreamChunk for each model text response, then exactly one
        TurnResultChunk when the loop exits (any reason).
        """
        self.history.append(Message.user(user_input))

        last_response: Optional[AgentResponse] = None
        total_tool_calls = 0
        last_thought: Optional[str] = None

        for iteration in range(self.max_iterations):
            logger.info(
                "Agentic loop — iteration %d / %d",
                iteration + 1, self.max_iterations,
            )

            # ----------------------------------------------------------
            # Provider call — 3-tuple contract.
            # The orchestrator only unpacks these three values.
            # Provider-specific concerns (thought_signature, tool_call_id
            # round-tripping) are handled entirely within the provider and
            # its adapter.
            # ----------------------------------------------------------
            try:
                agent_response, thought_text, tool_calls, raw_response = (
                    await self.provider.call_model(
                        history=self.history,
                        tools=self.current_tools,
                    )
                )
                logger.info(f"\n\n\n\n {agent_response} \n\n\n\n")
                # logger.info(f"{self.history[-1]} \n\n")
            except AgentResponseParseError as exc:
                # Model returned valid JSON that did not match AgentResponse.
                # Feed the validation error back so the model can self-correct.
                logger.warning(
                    "AgentResponse validation failed — feeding error back to model: %s",
                    exc,
                )
                self.history.append(
                    Message.user(
                        f"Your previous response failed schema validation:\n{exc}\n"
                        "Please respond again following the required JSON schema exactly."
                    )
                )
                continue
            except Exception as exc:
                logger.error("Unexpected provider error: %s", exc, exc_info=True)
                self.last_exit_reason = LoopExitReason.ERROR
                yield TurnResultChunk(
                    turn_result=self._build_turn_result(
                        AgentResponse(
                            response_text="I encountered an unexpected error.",
                            is_final=True,
                        ),
                        LoopExitReason.ERROR,
                        iteration + 1,
                        total_tool_calls,
                        last_thought,
                    )
                )
                return

            if thought_text:
                last_thought = thought_text

            # Unrecoverable: provider returned nothing at all.
            if agent_response is None and not tool_calls:
                logger.error("Provider returned empty result — exiting loop.")
                self.last_exit_reason = LoopExitReason.ERROR
                yield TurnResultChunk(
                    turn_result=self._build_turn_result(
                        AgentResponse(
                            response_text=(
                                "I encountered an issue processing your request."
                            ),
                            is_final=True,
                        ),
                        LoopExitReason.ERROR,
                        iteration + 1,
                        total_tool_calls,
                        last_thought,
                    )
                )
                return
            
            # ----------------------------------------------------------
            # Structured response
            # ----------------------------------------------------------
            if agent_response is not None:
                last_response = agent_response

                self.history.append(
                    Message.model_structured(
                        model_response_txt=agent_response.response_text,
                        parsed=agent_response.model_dump(),
                        thought=thought_text,
                        raw_provider_content=raw_response,
                    )
                )

                yield StreamChunk(content=agent_response.response_text)

                # Update active tool set from model suggestions.
                if agent_response.suggested_tools and self.tool_router is not None:
                    self.current_tools = self.tool_router.resolve_suggestions(
                        agent_response.suggested_tools
                    )

                # Task complete.
                if agent_response.is_final and not agent_response.needs_tool_call:
                    self.last_exit_reason = LoopExitReason.COMPLETED
                    yield TurnResultChunk(
                        turn_result=self._build_turn_result(
                            agent_response,
                            LoopExitReason.COMPLETED,
                            iteration + 1,
                            total_tool_calls,
                            last_thought,
                        )
                    )
                    return

                # Model wants tools but none loaded.
                if agent_response.needs_tool_call and not self.current_tools:
                    self.history.append(
                        Message.user(
                            "The tools you requested are not available. "
                            "Please answer with the information you have, "
                            "or suggest alternative tools."
                        )
                    )
                    continue

                # Model is not done yet.
                if not agent_response.is_final and not tool_calls:
                    self.history.append(
                        Message.user("Continue. Complete your objective.")
                    )
                    continue
            # ----------------------------------------------------------
            # Tool calls
            # tool_calls is List[ToolCall] — provider-agnostic Pydantic.
            # ToolCall.id / ToolCall.thought_signature are carried here and
            # read only by the respective provider's adapter.
            # ----------------------------------------------------------
            if tool_calls:
                logger.info("Tool calls: %s", [tc.name for tc in tool_calls])

                # Pass the thought/reasoning text into the message 
                # so the adapter can reconstruct the 'thought' part later.
                self.history.append(
                    Message.model_tool_calls(
                        calls=tool_calls,
                        thought=thought_text,
                        raw_provider_content=raw_response,
                    )
                )

                if self.tool_executor is None:
                    logger.error("Model requested tools but no executor provided.")
                    self.last_exit_reason = LoopExitReason.NO_TOOL_EXECUTOR
                    yield TurnResultChunk(
                        turn_result=self._build_turn_result(
                            AgentResponse(
                                response_text="Tool execution is not available.",
                                is_final=True,
                            ),
                            LoopExitReason.NO_TOOL_EXECUTOR,
                            iteration + 1,
                            total_tool_calls,
                            last_thought,
                        )
                    )
                    return

                # Detect argument-parse errors and convert them to error
                # ToolResults so the model can self-correct.
                results = await self._execute_with_error_passthrough(tool_calls)
                total_tool_calls += len(tool_calls)
                self.history.append(Message.tool_results_msg(results))


        # ------------------------------------------------------------------
        # Max iterations — emit exactly one TurnResultChunk.
        # ------------------------------------------------------------------
        logger.warning("Max iterations (%d) reached.", self.max_iterations)
        self.last_exit_reason = LoopExitReason.MAX_ITERATIONS
        logger.info(f"\n\n History \n\n{self.history}\n\n")
        final_response = last_response or AgentResponse(
            response_text="Reached maximum iterations without completing the task.",
            is_final=True,
        )
        if last_response:
            last_response.is_final = True

        yield TurnResultChunk(
            turn_result=self._build_turn_result(
                final_response,
                LoopExitReason.MAX_ITERATIONS,
                self.max_iterations,
                total_tool_calls,
                last_thought,
            )
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _execute_with_error_passthrough(
        self, tool_calls: List[ToolCall]
    ) -> List[ToolResult]:
        """
        Execute tool calls, converting argument-parse-error sentinels into
        error ToolResult messages the model can read and self-correct from.
        """
        results: List[ToolResult] = []
        calls_for_executor: List[ToolCall] = []
        error_results: dict[str, ToolResult] = {}

        for tc in tool_calls:
            if "__parse_error__" in tc.arguments:
                error_msg = tc.arguments["__parse_error__"]
                error_results[tc.id or tc.name] = ToolResult(
                    name=tc.name,
                    result={"error": error_msg},
                    is_error=True,
                    id=tc.id,
                )
            else:
                calls_for_executor.append(tc)

        if calls_for_executor:
            executed = await self.tool_executor.execute_tool_calls(calls_for_executor)
            results.extend(executed)

        results.extend(error_results.values())
        return results

    def _build_turn_result(
        self,
        response: AgentResponse,
        exit_reason: LoopExitReason,
        iterations_used: int,
        tool_calls_made: int,
        last_thought: Optional[str],
    ) -> TurnResult:
        self.last_exit_reason = exit_reason
        return TurnResult(
            response=response,
            exit_reason=exit_reason.value,
            iterations_used=iterations_used,
            tool_calls_made=tool_calls_made,
            history_snapshot=messages_to_history_dicts(self.history),
            last_thought_text=last_thought,
        )