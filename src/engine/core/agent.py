# engine/core/agent.py (PRODUCTION-READY VERSION)
import json
import logging
import asyncio
import uuid
from typing import Optional, List, Any, AsyncIterator
from contextlib import asynccontextmanager

from app.app_context import get_app_context
from engine.core.provide import get_provider
from engine.core.types import (
    Message, Role, ToolResult, StreamChunk, ToolCall,
    MaxStepsExceededError, AgentError
)
from engine.core.memory_manager import MemoryManager
from engine.registry import tool_manager
from engine.registry.tool_registry import ToolRegistry
from engine.executors.execution_engine import ExecutionEngine
from engine.core.agent_instance_manager import AgentConfig
from infrastructure.event_bus import EventBus
from database.base import BaseDatabase
from domain.event import Event, EventType

logger = logging.getLogger(__name__)

STREAM_WATCHDOG_TIMEOUT = 30.0
STREAM_RETRY_LIMIT = 1

class AgentInitializationError(Exception):
    """Raised when agent initialization fails."""
    pass

class Agent:
    """
    Production-ready Agent Orchestrator with database-backed memory.
    
    Key improvements:
    - Proper async initialization
    - Error recovery
    - Cleanup/shutdown
    - Session resumption
    """

    def __init__(
        self,
        agent_id: str,
        config: AgentConfig,
        registry: ToolRegistry,
        db: BaseDatabase,
        memory_manager: Optional[MemoryManager] = None
    ):
        self.config = config
        self.agent_id = agent_id
        self.db = db
        self._initialized = False
        self._initialization_lock = asyncio.Lock()
        
        # Initialize provider
        self.provider = get_provider(
            config.provider,
            model_id=config.model,
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
        
        # Database-backed memory manager
        self.memory = memory_manager or MemoryManager(
            db=db,
            agent_id=agent_id,
            agent_name=config.agent_name,
            recent_k=config.memory_recent_k,
            summarization_threshold=config.memory_summarization_threshold,
            enable_summarization=config.enable_memory_summarization,
            auto_summarize=True,
            session_timeout_hours=config.session_timeout_hours
        )
        
        self.execution_engine = ExecutionEngine(registry)
        self.max_steps = int(config.max_steps)
        self.sensitive_tool_names = config.sensitive_tool_names
        self.pending_tool_calls: Optional[List[ToolCall]] = None
        self.event_bus = get_app_context().event_bus
        self.tool_manager = tool_manager.ToolManager()
        self.tool_search_semantic = ""
        self.last_model_message = ""
    
    async def initialize(self) -> None:
        """
        Initialize agent and memory.
        MUST be called before using the agent!
        
        Usage:
            agent = Agent(...)
            await agent.initialize()
            # Now safe to use agent
        """
        async with self._initialization_lock:
            if self._initialized:
                logger.warning(f"Agent {self.agent_id} already initialized")
                return
            
            try:
                logger.info(f"🚀 Initializing agent {self.agent_id}...")
                
                # Initialize memory (will resume conversation if exists)
                await self.memory.initialize()
                
                # Add system prompt if needed
                if self.system_prompt:
                    system_msg = await self.memory.message_repo.get_system_message(
                        self.memory.conversation_id
                    )
                    
                    if not system_msg:
                        print("I should not be here")
                        await self.memory.add_message(
                            Message(role=Role.SYSTEM, content=self.system_prompt)
                        )
                        logger.info("✅ System prompt added")
                
                self._initialized = True
                logger.info(f"✅ Agent {self.agent_id} initialized successfully")
                
            except Exception as e:
                logger.error(f"❌ Agent initialization failed: {e}", exc_info=True)
                raise AgentInitializationError(
                    f"Failed to initialize agent {self.agent_id}: {e}"
                ) from e
    
    async def ensure_initialized(self):
        """Ensure agent is initialized before use."""
        if not self._initialized:
            await self.initialize()
    
    def _is_sensitive(self, tool_call: ToolCall) -> bool:
        """Check if a tool call involves sensitive operations."""
        return tool_call.name in self.sensitive_tool_names

    async def _execute_and_stream_tools(
        self, 
        tool_calls: List[ToolCall]
    ) -> AsyncIterator[StreamChunk]:
        """Execute tool calls and stream results."""
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
        
        # Store in database
        await self.memory.add_message(
            Message(role=Role.TOOL, tool_results=tool_results)
        )

    async def run(self, input_text: str) -> str:
        """Non-streaming execution."""
        await self.ensure_initialized()
        
        await self.memory.add_user_message(input_text)
        
        self.event_bus.publish(Event(
            type=EventType.USER_MESSAGE,
            payload={"content": input_text},
            source="agent"
        ))

        step_count = 0
        while step_count < self.max_steps:
            step_count += 1
            
            history = await self.memory.get_history()
            tools = self.registry.get_all_tools()
            response = await self.provider.generate(history, tools)
            
            await self.memory.add_message(Message(
                role=Role.ASSISTANT,
                content=response.content,
                tool_calls=response.tool_calls
            ))

            if not response.tool_calls:
                return response.content or ""
            
            tool_results = await self.execution_engine.execute_tool_calls(
                response.tool_calls
            )
            await self.memory.add_message(
                Message(role=Role.TOOL, tool_results=tool_results)
            )

        raise MaxStepsExceededError(
            f"Max steps ({self.max_steps}) reached without final answer."
        )

    async def _stream_with_watchdog(
        self,
        history: List[Message],
        tools: List[Any]
    ) -> AsyncIterator[StreamChunk]:
        """Stream with timeout protection."""
        stream = self.provider.stream(history, tools)
        last_chunk_time = asyncio.get_running_loop().time()

        async for chunk in stream:
            last_chunk_time = asyncio.get_running_loop().time()
            yield chunk

            if (
                asyncio.get_running_loop().time() - last_chunk_time
                > STREAM_WATCHDOG_TIMEOUT
            ):
                raise asyncio.TimeoutError("LLM stream stalled")
    
    def _fetch_tools(self): 
        """Fetch tools including dynamic RAG tools."""
        # dynamic_tools = self.tool_manager.retrieve_tools(
        #     self.tool_search_semantic, 3
        # )
        # self.registry.register_rag_tools(dynamic_tools)
        return self.registry.get_all_tools()

    async def stream(self, input_text: str) -> AsyncIterator[StreamChunk]:
        """
        Main streaming execution method.
        Automatically initializes if needed.
        """
        try:
            # Ensure initialized
            await self.ensure_initialized()
            
            # Handle pending tool approval
            if self.pending_tool_calls:
                is_approved = input_text.strip().lower() in [
                    "yes", "y", "approve", "confirm"
                ]
                
                self.event_bus.publish(Event(
                    type=EventType.USER_APPROVAL,
                    payload={"approved": is_approved, "input": input_text},
                    source="agent"
                ))

                if is_approved:
                    yield StreamChunk(
                        content="✅ Permission granted. Resuming execution...\n"
                    )
                    async for chunk in self._execute_and_stream_tools(
                        self.pending_tool_calls
                    ):
                        yield chunk
                else:
                    yield StreamChunk(
                        content="❌ Permission denied. Cancelling tool execution.\n"
                    )
                    tool_results = []
                    for call in self.pending_tool_calls:
                        tool_results.append(ToolResult(
                            tool_call_id=call.id,
                            name=call.name,
                            agent_id=self.agent_id,
                            result=None,
                            error=f"User denied permission. Input: {input_text}"
                        ))
                    await self.memory.add_message(
                        Message(role=Role.TOOL, tool_results=tool_results)
                    )
                
                self.pending_tool_calls = None
                
            else: 
                await self.memory.add_user_message(input_text)
                
                self.event_bus.publish(Event(
                    type=EventType.USER_MESSAGE,
                    payload={"content": input_text},
                    source="agent"
                ))

            self.tool_search_semantic = f"""
            user intentions: {input_text}
            model last reply: {self.last_model_message}
            """
            self.last_model_message = ""
            
            step_count = 0
            while step_count < self.max_steps:
                step_count += 1
                
                history = await self.memory.get_history()
                tools = self._fetch_tools()

                full_content = ""
                tool_calls = []
                retry_count = 0

                while True:
                    try:
                        async for chunk in self._stream_with_watchdog(history, tools):
                            if chunk.content:
                                full_content += chunk.content

                                yield StreamChunk(content=chunk.content)

                            if chunk.tool_call:
                                if not chunk.tool_call.id:
                                    chunk.tool_call.id = f"call_{uuid.uuid4().hex[:8]}"
                                    chunk.tool_call.agent = self.agent_id
                                tool_calls.append(chunk.tool_call)
                                yield StreamChunk(tool_call=chunk.tool_call)

                        break

                    except asyncio.TimeoutError:
                        logger.warning("⚠️ LLM stream stalled, retrying...")
                        retry_count += 1

                        if retry_count > STREAM_RETRY_LIMIT:
                            raise AgentError("LLM stream repeatedly stalled")

                        yield StreamChunk(
                            content="\n\n⚠️ Model stalled. Retrying...\n"
                        )
                        continue

                assistant_msg = Message(
                    role=Role.ASSISTANT,
                    content=full_content if full_content else None,
                    tool_calls=tool_calls
                )
                await self.memory.add_message(assistant_msg)
        
                if not tool_calls:
                    self.last_model_message = full_content
                    return
                
                sensitive_calls = [c for c in tool_calls if self._is_sensitive(c)]
                if sensitive_calls:
                    self.pending_tool_calls = tool_calls
                    yield StreamChunk(permission_request=sensitive_calls)
                    return

                async for chunk in self._execute_and_stream_tools(tool_calls):
                    yield chunk

                print(f"----------TOOL CALL : {tool_calls}")
            yield StreamChunk(content="\n\nMax steps reached.")
            raise MaxStepsExceededError(
                f"Max steps ({self.max_steps}) reached."
            )
            
        except AgentError as e:
            logger.error(f"Agent Error: {e}")
            yield StreamChunk(content=f"\n\n❌ {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected Error: {e}", exc_info=True)
            yield StreamChunk(content=f'\n\n❌ Error: {e}')
            raise AgentError(str(e)) from e
    
    async def start_fresh_conversation(self):
        """Start a completely new conversation (don't resume)."""
        await self.ensure_initialized()
        await self.memory.start_fresh_conversation()
    
    async def get_memory_stats(self) -> dict:
        """Get memory statistics."""
        await self.ensure_initialized()
        return await self.memory.get_statistics()
    
    async def search_memory(self, query: str, limit: int = 5) -> List[dict]:
        """Search agent's memory."""
        await self.ensure_initialized()
        return await self.memory.search_memory(query, limit)
    
    async def cleanup(self):
        """Cleanup resources."""
        logger.info(f"🧹 Cleaning up agent {self.agent_id}")
        # Cancel pending tasks, close connections, etc.
        # Add specific cleanup logic as needed

# Context manager for agent lifecycle
@asynccontextmanager
async def create_agent(
    agent_id: str,
    config: AgentConfig,
    registry: ToolRegistry,
    db: BaseDatabase
):
    """
    Context manager for safe agent creation and cleanup.
    
    Usage:
        async with create_agent(...) as agent:
            response = await agent.stream("Hello!")
    """
    agent = Agent(agent_id, config, registry, db)
    try:
        await agent.initialize()
        yield agent
    finally:
        await agent.cleanup()