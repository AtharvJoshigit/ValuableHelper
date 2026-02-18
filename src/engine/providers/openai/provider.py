# engine/providers/openai/provider.py

import asyncio
import json
import os
import logging
from typing import List, Optional, AsyncIterator

from openai import AsyncOpenAI

from engine.core.types import Message, AgentResponse, StreamChunk, ToolCall
from engine.registry.base_tool import BaseTool
from engine.providers.base_provider import BaseProvider
from engine.providers.openai.adapter import OpenAIAdapter

logger = logging.getLogger(__name__)

class OpenAIProvider(BaseProvider):
    """
    Production-ready OpenAI provider implementation.
    Supports all OpenAI models with streaming and tool calls.
    """
    
    def __init__(
        self, 
        model_id: str = "gpt-4-turbo-preview",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        **additional_params
    ):
        """
        Initialize the OpenAI provider.
        
        Args:
            model_id: OpenAI model identifier (gpt-4, gpt-3.5-turbo, etc.)
            api_key: OpenAI API key (or from OPENAI_API_KEY env var)
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling parameter
            max_tokens: Maximum output tokens
            frequency_penalty: Penalize frequent tokens (-2.0 to 2.0)
            presence_penalty: Penalize new tokens (-2.0 to 2.0)
        """
        self.model_id = model_id
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "OpenAI API key must be provided or set in OPENAI_API_KEY environment variable."
            )
        
        # Store generation parameters
        self.temperature = max(temperature, 0.3)  # Minimum 0.3 to avoid repetition
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.frequency_penalty = frequency_penalty or 0.0
        self.presence_penalty = presence_penalty or 0.0
        self.additional_params = additional_params
        
        # Initialize client
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://integrate.api.nvidia.com/v1"
            )
        
        logger.info(
            f"✅ OpenAI Provider initialized: {model_id} "
            f"(temp={self.temperature}, max_tokens={max_tokens})"
        )

    def _build_request_params(
        self, 
        messages: List[dict],
        tools: List[BaseTool]
    ) -> dict:
        """Build request parameters for OpenAI API."""
        params = {
            "model": self.model_id,
            "messages": messages,
            "temperature": self.temperature,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
        }
        
        # Add optional parameters
        if self.top_p is not None:
            params["top_p"] = self.top_p
        
        if self.max_tokens is not None:
            params["max_tokens"] = min(self.max_tokens, 4096)  # Cap at reasonable limit
        
        # Add tools if provided
        if tools:
            tool_defs = []
            for tool in tools:
                tool_defs.append({
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.get_schema()
                })
            
            openai_tools = OpenAIAdapter.convert_tools(tool_defs)
            
            if openai_tools:
                params["tools"] = openai_tools
                params["tool_choice"] = "auto"  # Let model decide when to use tools
        
        return params

    async def generate(
        self, 
        history: List[Message], 
        tools: List[BaseTool] = None
    ) -> AgentResponse:
        """
        Generate a non-streaming response from OpenAI.
        
        Args:
            history: Conversation history
            tools: Available tools
            
        Returns:
            AgentResponse with content, tool_calls, and usage
        """
        if tools is None:
            tools = []
        
        # Convert history
        messages = OpenAIAdapter.convert_history(history)
        
        # Build request params
        params = self._build_request_params(messages, tools)
        
        try:
            response = await self.client.chat.completions.create(**params)
            
            # Convert response
            agent_response = OpenAIAdapter.convert_response(response)
            
            logger.debug(
                f"Generated response: {len(agent_response.content or '')} chars, "
                f"{len(agent_response.tool_calls)} tool calls"
            )
            
            return agent_response
            
        except Exception as e:
            logger.error(f"OpenAI Provider Generate Error: {e}", exc_info=True)
            raise RuntimeError(f"OpenAI Provider Generate Error: {str(e)}") from e

    async def stream(
        self, 
        history: List[Message], 
        tools: List[BaseTool] = None
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream responses from OpenAI with repetition detection.
        
        Args:
            history: Conversation history
            tools: Available tools
            
        Yields:
            StreamChunk objects with content deltas and tool calls
        """
        if tools is None:
            tools = []
        
        # Convert history
        messages = OpenAIAdapter.convert_history(history)
        
        logger.debug(f"Sending {len(messages)} messages to OpenAI")
        
        # Build request params
        params = self._build_request_params(messages, tools)
        params["stream"] = True
        
        # Repetition detection
        recent_chunks = []
        max_repetition_check = 10
        repetition_threshold = 0.7
        total_chunks = 0
        max_chunks = 500  # Emergency brake
        
        def is_repetitive(recent: List[str], new: str) -> bool:
            """Check if new chunk is repetitive."""
            if len(recent) < 5:
                return False
            
            matches = sum(1 for c in recent[-max_repetition_check:] if c.strip() == new.strip())
            similarity = matches / min(len(recent), max_repetition_check)
            
            return similarity > repetition_threshold
        
        max_retries = 3
        retry_delay = 1.5
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Streaming with model: {self.model_id}")
                
                # Start streaming
                stream = await self.client.chat.completions.create(**params)
                
                # Accumulate tool call data across chunks
                tool_call_accumulator = {}
                
                chunk_count = 0
                async for chunk in stream:
                    chunk_count += 1
                    total_chunks += 1
                    
                    # Emergency brake
                    if total_chunks > max_chunks:
                        logger.error(f"🚨 EMERGENCY STOP: {total_chunks} chunks (repetition loop?)")
                        yield StreamChunk(content="\n\n[Model output truncated - repetition detected]")
                        return
                    
                    # Convert chunk
                    stream_chunk = OpenAIAdapter.convert_stream_chunk(chunk)
                    
                    if stream_chunk and stream_chunk.content:
                        # Check for repetition
                        if is_repetitive(recent_chunks, stream_chunk.content):
                            logger.warning(
                                f"🚨 REPETITION DETECTED after {total_chunks} chunks. "
                                f"Last content: {stream_chunk.content[:50]}"
                            )
                            yield StreamChunk(content="\n\n[Output stopped - repetitive pattern detected]")
                            return
                        
                        # Track recent chunks
                        recent_chunks.append(stream_chunk.content)
                        if len(recent_chunks) > max_repetition_check:
                            recent_chunks.pop(0)
                        
                        yield stream_chunk
                    
                    elif stream_chunk and stream_chunk.tool_call:
                        # OpenAI streams tool calls incrementally
                        tc = stream_chunk.tool_call
                        
                        if tc.id:
                            if tc.id not in tool_call_accumulator:
                                tool_call_accumulator[tc.id] = {
                                    "id": tc.id,
                                    "name": tc.name,
                                    "arguments": ""
                                }
                            
                            # Accumulate arguments
                            if tc.arguments:
                                # Arguments come as string chunks
                                args_str = json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments)
                                tool_call_accumulator[tc.id]["arguments"] += args_str
                        
                        yield stream_chunk

                logger.debug(f"Streamed {chunk_count} chunks successfully")
                
                # Yield complete tool calls if any
                if tool_call_accumulator:
                    for tc_data in tool_call_accumulator.values():
                        try:
                            args = json.loads(tc_data["arguments"])
                            complete_tc = ToolCall(
                                id=tc_data["id"],
                                name=tc_data["name"],
                                arguments=args
                            )
                            yield StreamChunk(tool_call=complete_tc)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse accumulated tool call arguments: {tc_data}")
                
                # Successfully completed stream
                break
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a recoverable error
                is_recoverable = any(
                    msg in error_str.lower()
                    for msg in [
                        "timeout",
                        "connection",
                        "network",
                        "rate limit"
                    ]
                )
                
                if is_recoverable and attempt < max_retries - 1:
                    logger.warning(
                        f"⚠️ Stream interrupted ({error_str}). "
                        f"Retrying attempt {attempt + 2}/{max_retries}..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5
                    continue
                else:
                    logger.error(f"OpenAI Provider Stream Error: {error_str}", exc_info=True)
                    raise RuntimeError(f"OpenAI Provider Stream Error: {error_str}") from e