import asyncio
import logging
import inspect
from typing import List
from engine.core.types import ToolCall, ToolResult
from engine.registry.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

class ExecutionEngine:
    """
    Handles the execution of tool calls, supporting parallel execution.
    """
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

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
            
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                result=result
            )
        except asyncio.TimeoutError:
            logger.error(f"Tool {call.name} timed out after {timeout}s")
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                result=f"Tool {call.name} timed out after {timeout}s",
                error=f"Tool execution timed out after {timeout}s"
            )
        except Exception as e:
            logger.error(f"Error executing tool {call.name}: {e}")
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                result=f"Error executing tool {call.name}: {e}",
                error=str(e)
            )
