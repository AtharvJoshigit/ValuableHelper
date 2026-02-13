import asyncio
import logging
import inspect
from typing import List, Optional
from app.app_context import get_app_context
from engine.core.types import ToolCall, ToolResult
from engine.registry.tool_registry import ToolRegistry
from infrastructure.event_bus import EventBus
from domain.event import Event, EventType

logger = logging.getLogger(__name__)

class ExecutionEngine:
    """
    Handles the execution of tool calls, supporting parallel execution.
    """
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.event_bus = get_app_context().event_bus
        if not self.event_bus:
            logger.warning("EventBus not provided to ExecutionEngine. Events will not be published.")

    async def execute_tool_calls(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """
        Execute a list of tool calls in parallel.
        
        Args:
            tool_calls: List of ToolCall objects to execute.
            
        Returns:
            List of ToolResult objects corresponding to the calls.
        """

        tasks = []
        for call in tool_calls:
            tasks.append(self._execute_single_tool(call))
            
        return await asyncio.gather(*tasks)

    async def _execute_single_tool(self, call: ToolCall, timeout: float = 300.0) -> ToolResult:
        """
        Execute a single tool call safely, supporting both sync and async tools.
        """
        logger.info(f"⚡ ExecutionEngine: About to execute {call.name}")
        
        if self.event_bus:
            logger.info(f"⚡ ExecutionEngine: Publishing START event for {call.name}")
            try:
                self.event_bus.publish(Event(
                    type=EventType.TOOL_EXECUTION_STARTED,
                    payload={
                        "agent_id": call.agent_id,
                        "tool_call_id": call.id,
                        "tool_name": call.name,
                        "arguments": call.arguments
                    }
                ))
            except Exception as e:
                logger.error(f"⚡ ExecutionEngine: Failed to publish START event: {e}")
        else:
            logger.error("⚡ ExecutionEngine: EventBus is None!")

        try:
            tool = self.registry.get_tool(call.name)
            
            # 1. Check if the tool has an explicit execute_async method
            if hasattr(tool, "execute_async") and inspect.iscoroutinefunction(tool.execute_async):
                result = await asyncio.wait_for(
                    tool.execute_async(**call.arguments),
                    timeout=timeout
                )
            # 2. Check if the standard execute method is a coroutine
            elif inspect.iscoroutinefunction(tool.execute):
                result = await asyncio.wait_for(
                    tool.execute(**call.arguments),
                    timeout=timeout
                )
            # 3. Fallback to synchronous execution in an executor
            else:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool.execute(**call.arguments)),
                    timeout=timeout
                )
            
            if self.event_bus:
                self.event_bus.publish(Event(
                    type=EventType.TOOL_EXECUTION_COMPLETED,
                    payload={
                        "agent_id": call.agent_id,
                        "tool_call_id": call.id,
                        "tool_name": call.name,
                        "result": str(result)[:1000] # Truncate for log safety
                    }
                ))

            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                result=result
            )

        except asyncio.TimeoutError:
            error_msg = f"Tool {call.name} timed out after {timeout}s"
            logger.error(error_msg)
            
            if self.event_bus:
                self.event_bus.publish(Event(
                    type=EventType.TOOL_EXECUTION_FAILED,
                    payload={
                        "agent_id": call.agent_id,
                        "tool_call_id": call.id,
                        "tool_name": call.name,
                        "error": error_msg
                    }
                ))

            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                result=error_msg,
                error=error_msg
            )

        except Exception as e:
            error_msg = f"Error executing tool {call.name}: {e}"
            logger.error(error_msg)

            if self.event_bus:
                self.event_bus.publish(Event(
                    type=EventType.TOOL_EXECUTION_FAILED,
                    payload={
                        "tool_call_id": call.id,
                        "tool_name": call.name,
                        "error": str(e)
                    }
                ))

            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                result=error_msg,
                error=str(e)
            )
