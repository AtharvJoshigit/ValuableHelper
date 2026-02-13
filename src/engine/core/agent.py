# file: engine/core/agent.py (updated)

import json
import logging
import asyncio
import uuid
from typing import Optional, List, Any, AsyncIterator, Set

from app.app_context import get_app_context
from engine.core.provide import get_provider
from engine.core.types import (
    Message, Role, ToolResult, StreamChunk, ToolCall,
    MaxStepsExceededError, AgentError
)
from engine.core.memory import Memory
from engine.registry.tool_registry import ToolRegistry
from engine.executors.execution_engine import ExecutionEngine
from engine.core.agent_instance_manager import AgentConfig
from infrastructure.event_bus import EventBus
from domain.event import Event, EventType

logger = logging.getLogger(__name__)

STREAM_WATCHDOG_TIMEOUT = 30.0  # seconds
STREAM_RETRY_LIMIT = 1

class Agent:
    """
    The main Agent Orchestrator.
    Manages the loop of: User Input -> LLM -> Tool Execution -> LLM -> Response.
    """

    def __init__(
        self,
        agent_id: str,
        config: AgentConfig,
        registry: ToolRegistry,
        memory: Optional[Memory] = None
    ):
        self.config = config
        self.agent_id = agent_id
        self.provider = get_provider(
            config.provider,
            model=config.model,
            temperature=config.temperature,
            top_p=config.top_p,
            top_k=config.top_k,
            max_tokens=config.max_tokens,
            **config.additional_params
        )
        
        if self.provider is None:
            raise ValueError(f"Failed to initialize provider: {config.provider}")
        
        self.registry = registry
        self.system_prompt = config.system_prompt
        self.memory = memory or Memory()
        self.execution_engine = ExecutionEngine(registry)
        self.max_steps = config.max_steps
        self.sensitive_tool_names = config.sensitive_tool_names
        self.pending_tool_calls: Optional[List[ToolCall]] = None
        self.event_bus = get_app_context().event_bus

        if self.system_prompt and not self.memory.get_history():
            self.memory.add_message(Message(role=Role.SYSTEM, content=self.system_prompt))

    def _is_sensitive(self, tool_call: ToolCall) -> bool:
        """Check if a tool call involves sensitive operations requiring approval."""
        return tool_call.name in self.sensitive_tool_names

    async def _execute_and_stream_tools(self, tool_calls: List[ToolCall]) -> AsyncIterator[StreamChunk]:
        """Execute a list of tool calls and stream the results."""
        task_to_info = {}
        for i, call in enumerate(tool_calls):
            task = asyncio.create_task(
                self.execution_engine._execute_single_tool(call)
            )
            task_to_info[task] = (i, call.name, call.arguments)
        
        tool_results = [None] * len(tool_calls)
        pending = set(task_to_info.keys())
        
        while pending:
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in done:
                result = task.result()
                idx, name, args = task_to_info[task]
                tool_results[idx] = result
                
                yield StreamChunk(tool_result=result)
        
        self.memory.add_message(Message(role=Role.TOOL, tool_results=tool_results))

    async def run(self, input_text: str) -> str:
        self.memory.add_user_message(input_text)
        
        # Emit User Message Event
        self.event_bus.publish(Event(
            type=EventType.USER_MESSAGE,
            payload={"content": input_text},
            source="agent"
        ))

        step_count = 0
        while step_count < self.max_steps:
            step_count += 1
            history = self.memory.get_history()
            tools = self.registry.get_all_tools()
            response = await self.provider.generate(history, tools)
            
            self.memory.add_message(Message(
                role=Role.ASSISTANT,
                content=response.content,
                tool_calls=response.tool_calls
            ))

            if not response.tool_calls:
                return response.content or ""
            
            tool_results = await self.execution_engine.execute_tool_calls(response.tool_calls)
            self.memory.add_message(Message(role=Role.TOOL, tool_results=tool_results))

        raise MaxStepsExceededError(f"Max steps ({self.max_steps}) reached without final answer.")

    async def _stream_with_watchdog(
        self,
        history,
        tools
    ) -> AsyncIterator[StreamChunk]:
        """
        Streams from provider with a watchdog.
        Aborts if no chunk is received within STREAM_WATCHDOG_TIMEOUT.
        """
        stream = self.provider.stream(history, tools)
        last_chunk_time = asyncio.get_running_loop().time()

        async for chunk in stream:
            last_chunk_time = asyncio.get_running_loop().time()
            yield chunk

            # cooperative check (cheap, non-blocking)
            if (
                asyncio.get_running_loop().time() - last_chunk_time
                > STREAM_WATCHDOG_TIMEOUT
            ):
                raise asyncio.TimeoutError("LLM stream stalled")
    
    
    async def stream(self, input_text: str) -> AsyncIterator[StreamChunk]:
        try:
            if self.pending_tool_calls:
                is_approved = input_text.strip().lower() in ["yes", "y", "approve", "confirm"]
                
                self.event_bus.publish(Event(
                    type=EventType.USER_APPROVAL,
                    payload={"approved": is_approved, "input": input_text},
                    source="agent"
                ))

                if is_approved:
                    yield StreamChunk(content="✅ Permission granted. Resuming execution...\n")
                    async for chunk in self._execute_and_stream_tools(self.pending_tool_calls):
                        yield chunk
                else:
                    yield StreamChunk(content="❌ Permission denied. Cancelling tool execution.\n")
                    tool_results = []
                    for call in self.pending_tool_calls:
                        tool_results.append(ToolResult(
                            tool_call_id=call.id,
                            name=call.name,
                            agent_id = self.agent_id,
                            result=None,
                            error=f"User denied permission. Input: {input_text}"
                        ))
                    self.memory.add_message(Message(role=Role.TOOL, tool_results=tool_results))
                
                self.pending_tool_calls = None
                
            else:
                self.memory.add_user_message(input_text)
                self.event_bus.publish(Event(
                    type=EventType.USER_MESSAGE,
                    payload={"content": input_text},
                    source="agent"
                ))

            step_count = 0
            while step_count < self.max_steps:
                step_count += 1
                
                history = self.memory.get_history()
                tools = self.registry.get_all_tools()
                
                full_content = ""
                tool_calls = []
                
                retry_count = 0

                while True:
                    try:
                        async for chunk in self._stream_with_watchdog(history, tools):
                            if chunk.content:
                                full_content += chunk.content

                            if chunk.tool_call:
                                if not chunk.tool_call.id:
                                    chunk.tool_call.id = f"call_{uuid.uuid4().hex[:8]}"
                                    chunk.tool_call.agent = self.agent_id
                                tool_calls.append(chunk.tool_call)

                            yield chunk

                        break  # stream completed successfully

                    except asyncio.TimeoutError:
                        logger.warning("⚠️ LLM stream stalled >30s, retrying...")
                        retry_count += 1

                        if retry_count > STREAM_RETRY_LIMIT:
                            raise AgentError("LLM stream repeatedly stalled")

                        # Inform user (non-breaking UX)
                        yield StreamChunk(
                            content="\n\n⚠️ Model stalled. Retrying response...\n"
                        )

                        # IMPORTANT: do NOT mutate memory again
                        continue

                assistant_msg = Message(
                    role=Role.ASSISTANT,
                    content=full_content if full_content else None,
                    tool_calls=tool_calls
                )
                self.memory.add_message(assistant_msg)
        
                if not tool_calls:
                    return
                
                sensitive_calls = [c for c in tool_calls if self._is_sensitive(c)]
                if sensitive_calls:
                    self.pending_tool_calls = tool_calls
                    yield StreamChunk(permission_request=sensitive_calls)
                    return

                async for chunk in self._execute_and_stream_tools(tool_calls):
                    yield chunk
            
            yield StreamChunk(content="\n\nMax steps reached without final answer.")
            raise MaxStepsExceededError(f"Max steps ({self.max_steps}) reached without final answer.")
        except AgentError as e:
            logger.error(f"Agent Error: {e}")
            yield StreamChunk(content=f"\n\n❌ {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected Agent Error: {e}")
            yield StreamChunk(content=f'\n\n❌ Encountered Error: {e}')
            raise AgentError(str(e)) from e
        