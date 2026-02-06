import logging
import asyncio
from typing import Optional, List, Any, AsyncIterator

from engine.core.types import Message, Role, ToolResult, StreamChunk
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
        max_steps: int = 10
    ):
        self.provider = provider
        self.registry = registry
        self.system_prompt = system_prompt
        self.memory = memory or Memory()
        self.execution_engine = ExecutionEngine(registry)
        self.max_steps = max_steps

        # Initialize memory with system prompt if provided and empty
        if self.system_prompt and not self.memory.get_history():
            self.memory.add_message(Message(role=Role.SYSTEM, content=self.system_prompt))

    async def run(self, input_text: str) -> str:
        """
        Run the agent with the given input text.
        
        Args:
            input_text: The user's input message.
            
        Returns:
            The final response content from the assistant.
        """

        try : 
            # Add user message to memory
            self.memory.add_user_message(input_text)

            step_count = 0
            while step_count < self.max_steps:
                step_count += 1
                
                # 1. Get current history and tools
                history = self.memory.get_history()
                tools = self.registry.get_all_tools()
                
                # 2. Generate response from LLM
                loop = asyncio.get_running_loop()
                response = await self.provider.generate(history, tools)
                
                # 3. Add assistant response to memory
                assistant_msg = Message(
                    role=Role.ASSISTANT,
                    content=response.content,
                    tool_calls=response.tool_calls
                )
                self.memory.add_message(assistant_msg)

                # 4. Check for tool calls
                if not response.tool_calls:
                    # No tool calls, we are done
                    return response.content or ""
                
                # 5. Execute tool calls
                logger.info(f"Executing {len(response.tool_calls)} tool calls")
                tool_results = await self.execution_engine.execute_tool_calls(response.tool_calls)
                
                # 6. Add results to memory
                self.memory.add_message(Message(role=Role.TOOL, tool_results=tool_results))
                
                # Loop continues...

            return "Max steps reached without final answer."
        except Exception as e: 
            return f"Encountred error: {e}"


    async def stream(self, input_text: str) -> AsyncIterator[StreamChunk]:
            
        try :     
            self.memory.add_user_message(input_text)

            step_count = 0
            while step_count < self.max_steps:
                step_count += 1
                

                # Yield step indicator
                yield StreamChunk(content=f"\n{'='*50}\n📍 Step {step_count}\n{'='*50}\n")

                history = self.memory.get_history()
                tools = self.registry.get_all_tools()
                
                full_content = ""
                tool_calls = []
                
                # Now provider.stream is async
                async for chunk in self.provider.stream(history, tools):
                    if chunk.content:
                        full_content += chunk.content
                    
                    if chunk.tool_call:
                        tool_calls.append(chunk.tool_call)
                        
                    yield chunk

                # Add to memory...
                assistant_msg = Message(
                    role=Role.ASSISTANT,
                    content=full_content if full_content else None,
                    tool_calls=tool_calls
                )
                self.memory.add_message(assistant_msg)
        
                if not tool_calls:
                    yield StreamChunk(content="\n\n✅ Task completed!\n")
                    return
                # Execute tools and stream results
                yield StreamChunk(content=f"\n\n🔧 Executing {len(tool_calls)} tool(s) in parallel...\n")

                task_to_info = {}
                for i, call in enumerate(tool_calls):
                    task = asyncio.create_task(
                        self.execution_engine._execute_single_tool(call)
                    )
                    task_to_info[task] = (i, call.name, call.arguments)
                
                tool_results = [None] * len(tool_calls)
                completed_count = 0
                pending = set(task_to_info.keys())
                # Stream results as they complete
                while pending:
                    done, pending = await asyncio.wait(
                        pending, 
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    for task in done:
                        result = task.result()
                        idx, name, args = task_to_info[task]
                        tool_results[idx] = result
                        completed_count += 1
                        
                        # Show progress
                        if result.error:
                            yield StreamChunk(
                                content=f"  [{completed_count}/{len(tool_calls)}] ❌ {name}: {result.error}\n"
                            )
                        else:
                            result_str = str(result.result)
                            if len(result_str) > 150:
                                result_str = result_str[:150] + "..."
                            yield StreamChunk(
                                content=f"  [{completed_count}/{len(tool_calls)}] ✅ {name}: {result_str}\n"
                            )
                
                self.memory.add_message(Message(role=Role.TOOL, tool_results=tool_results))

            yield StreamChunk(content="\nMax steps reached without final answer.")
        except Exception as e: 
            print("Encounter Error")
            yield StreamChunk(contents=f'\n Encountered Error : {e}')