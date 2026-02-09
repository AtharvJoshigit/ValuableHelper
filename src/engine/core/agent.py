import logging
import asyncio
import uuid
from typing import Optional, List, Any, AsyncIterator, Set

from engine.core.types import (
    Message, Role, ToolResult, StreamChunk, ToolCall, 
    MaxStepsExceededError, AgentError
)
from engine.core.memory import Memory
from engine.registry.tool_registry import ToolRegistry
from engine.executors.execution_engine import ExecutionEngine
from engine.providers.base_provider import BaseProvider

logger = logging.getLogger(__name__)

class Agent:
    """
    The main Agent Orchestrator.
    Manages the loop of: User Input -> LLM -> Tool Execution -> LLM -> Response.
    """

    def __init__(
        self,
        provider: BaseProvider,
        registry: ToolRegistry,
        system_prompt: Optional[str] = None,
        memory: Optional[Memory] = None,
        max_steps: int = 10,
        sensitive_tool_names: Set[str] = set()
    ):
        self.provider = provider
        self.registry = registry
        self.system_prompt = system_prompt
        self.memory = memory or Memory()
        self.execution_engine = ExecutionEngine(registry)
        self.max_steps = max_steps
        self.sensitive_tool_names = sensitive_tool_names
        self.pending_tool_calls: Optional[List[ToolCall]] = None

        # Initialize memory with system prompt if provided and empty
        if self.system_prompt and not self.memory.get_history():
            self.memory.add_message(Message(role=Role.SYSTEM, content=self.system_prompt))

    def _is_sensitive(self, tool_call: ToolCall) -> bool:
        """
        Check if a tool call involves sensitive operations requiring approval.
        """
        return tool_call.name in self.sensitive_tool_names

    async def _execute_and_stream_tools(self, tool_calls: List[ToolCall]) -> AsyncIterator[StreamChunk]:
        """
        Execute a list of tool calls and stream the results.
        """
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
        # Legacy synchronous run method (kept for compatibility but not updated with HITL)
        self.memory.add_user_message(input_text)
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

    async def stream(self, input_text: str) -> AsyncIterator[StreamChunk]:
        try:
            # 1. Handle Pending HITL Requests (Resumption)
            if self.pending_tool_calls:
                # Check if user approved
                is_approved = input_text.strip().lower() in ["yes", "y", "approve", "confirm"]
                
                if is_approved:
                    yield StreamChunk(content="✅ Permission granted. Resuming execution...\n")
                    # Execute pending tools
                    async for chunk in self._execute_and_stream_tools(self.pending_tool_calls):
                        yield chunk
                else:
                    yield StreamChunk(content="❌ Permission denied. Cancelling tool execution.\n")
                    # Generate error results for pending tools
                    tool_results = []
                    for call in self.pending_tool_calls:
                        tool_results.append(ToolResult(
                            tool_call_id=call.id,
                            name=call.name,
                            result=None,
                            error=f"User denied permission. Input: {input_text}"
                        ))
                    self.memory.add_message(Message(role=Role.TOOL, tool_results=tool_results))
                
                # Clear pending state
                self.pending_tool_calls = None
                
            else:
                # Normal flow: Add user message
                self.memory.add_user_message(input_text)

            step_count = 0
            while step_count < self.max_steps:
                step_count += 1
                
                # Separator removed as requested
                
                history = self.memory.get_history()
                tools = self.registry.get_all_tools()
                
                full_content = ""
                tool_calls = []
                
                async for chunk in self.provider.stream(history, tools):
                    if chunk.content:
                        full_content += chunk.content
                    if chunk.tool_call:
                        # Robustness: Ensure ID exists
                        if not chunk.tool_call.id:
                            chunk.tool_call.id = f"call_{uuid.uuid4().hex[:8]}"
                        tool_calls.append(chunk.tool_call)  
                    yield chunk

                assistant_msg = Message(
                    role=Role.ASSISTANT,
                    content=full_content if full_content else None,
                    tool_calls=tool_calls
                )
                self.memory.add_message(assistant_msg)
        
                if not tool_calls:
                    yield StreamChunk(content="\n\n-----------\n")
                    return
                
                # 2. Check for Sensitive Tools (HITL)
                sensitive_calls = [c for c in tool_calls if self._is_sensitive(c)]
                if sensitive_calls:
                    self.pending_tool_calls = tool_calls
                    # Yield permission request chunk instead of text warning
                    yield StreamChunk(permission_request=sensitive_calls)
                    return # Exit stream to wait for user input

                # 3. Execute Tools (if no permission needed)
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
