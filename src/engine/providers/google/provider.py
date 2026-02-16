# engine/providers/google/provider.py (COMPLETE PRODUCTION-READY FIX)

import asyncio
import os
import logging
from typing import List, Optional, AsyncIterator

from google import genai
from google.genai import types as genai_types

from engine.core.types import Message, AgentResponse, StreamChunk
from engine.registry.base_tool import BaseTool
from engine.providers.base_provider import BaseProvider
from engine.providers.google.adapter import GoogleAdapter

logger = logging.getLogger(__name__)

class GoogleProvider(BaseProvider):
    """
    Production-ready Google Gemini provider implementation.
    Supports all Gemini models including thinking/reasoning models.
    """
    
    def __init__(
        self, 
        model_id: str = "gemini-2.5-flash",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None,
        **additional_params
    ):
        """
        Initialize the Google provider.
        
        Args:
            model_id: Gemini model identifier
            api_key: Google API key (or from GOOGLE_API_KEY env var)
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter
            max_tokens: Maximum output tokens
            **additional_params: Additional config (e.g., include_thoughts)
        """
        self.model_id = model_id
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Google API key must be provided or set in GOOGLE_API_KEY environment variable."
            )
        
        # Store generation parameters
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_tokens = max_tokens
        self.additional_params = additional_params
        
        # Initialize client
        self.client = genai.Client(api_key=self.api_key)
        
        logger.info(
            f"✅ Google Provider initialized: {model_id} "
            f"(temp={temperature}, max_tokens={max_tokens})"
        )

    def _build_config(self, tools: List[BaseTool]) -> genai_types.GenerateContentConfig:
        """
        Build generation config with proper parameter handling.
        
        Args:
            tools: List of tools to include in config
            
        Returns:
            GenerateContentConfig object
        """
        # Base config parameters
        config_kwargs = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
        }
        
        # Add optional parameters
        if self.top_p is not None:
            config_kwargs["top_p"] = self.top_p
        
        if self.top_k is not None:
            config_kwargs["top_k"] = self.top_k
        
        # Add tools if provided
        if tools:
            # Use adapter to convert tools properly
            tool_defs = []
            for tool in tools:
                tool_defs.append({
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.get_schema()
                })
            
            google_functions = GoogleAdapter.convert_tools(tool_defs)
            
            if google_functions:
                # Convert to FunctionDeclaration objects
                function_declarations = [
                    genai_types.FunctionDeclaration(
                        name=func["name"],
                        description=func["description"],
                        parameters=func["parameters"]
                    )
                    for func in google_functions
                ]
                
                config_kwargs["tools"] = [
                    genai_types.Tool(function_declarations=function_declarations)
                ]
                
                # Disable automatic function calling (we handle it ourselves)
                config_kwargs["automatic_function_calling"] = genai_types.AutomaticFunctionCallingConfig(
                    disable=True
                )
        
        # Handle thinking config (for thinking models)
        include_thoughts = self.additional_params.get("include_thoughts", False)
        
        if include_thoughts:
            config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
                include_thoughts=True
            )
            logger.debug(f"Thinking mode enabled for {self.model_id}")
        
        # Create and return config
        return genai_types.GenerateContentConfig(**config_kwargs)

    async def generate(
        self, 
        history: List[Message], 
        tools: List[BaseTool] = None
    ) -> AgentResponse:
        """
        Generate a non-streaming response from the model.
        
        Args:
            history: Conversation history
            tools: Available tools
            
        Returns:
            AgentResponse with content, tool_calls, and usage
        """
        if tools is None:
            tools = []
        
        # Convert history using adapter
        contents = GoogleAdapter.convert_history(history, self.model_id)
        
        # Build config
        config = self._build_config(tools)
        
        try:
            # Run sync API in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model=self.model_id,
                    contents=contents,
                    config=config
                )
            )
            
            # Convert response using adapter
            agent_response = GoogleAdapter.convert_response(response, self.model_id)
            
            logger.debug(
                f"Generated response: {len(agent_response.content or '')} chars, "
                f"{len(agent_response.tool_calls)} tool calls"
            )
            
            return agent_response
            
        except Exception as e:
            logger.error(f"Google Provider Generate Error: {e}", exc_info=True)
            raise RuntimeError(f"Google Provider Generate Error: {str(e)}") from e

    async def stream(
        self, 
        history: List[Message], 
        tools: List[BaseTool] = None
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream responses from the model with proper delta handling.
        
        CRITICAL: Properly filters thought parts and yields only deltas.
        
        Args:
            history: Conversation history
            tools: Available tools
            
        Yields:
            StreamChunk objects with content deltas and tool calls
        """
        if tools is None:
            tools = []
        
        # Convert history using adapter
        contents = GoogleAdapter.convert_history(history, self.model_id)
        
        logger.debug(f"Sending {len(contents)} messages to Google")
        
        # Build config
        config = self._build_config(tools)
        
        max_retries = 3
        retry_delay = 1.5
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Streaming with model: {self.model_id}")
                
                # Start streaming
                response_iterator = await self.client.aio.models.generate_content_stream(
                    model=self.model_id,
                    contents=contents,
                    config=config
                )
                
                # Process chunks
                chunk_count = 0
                async for chunk in response_iterator:
                    
                    chunk_count+=1
                    # Use adapter to convert chunk (handles thought filtering)
                    stream_chunk = GoogleAdapter.convert_stream_chunk(chunk, self.model_id)
                    
                    if stream_chunk:    
                        yield stream_chunk
                        
                logger.debug(f"Streamed {chunk_count} chunks successfully")
                # Successfully completed stream
                break
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a recoverable network error
                is_network_error = any(
                    msg in error_str 
                    for msg in [
                        "IncompleteRead", 
                        "Connection broken", 
                        "EOF occurred",
                        "Connection reset"
                    ]
                )
                
                if is_network_error and attempt < max_retries - 1:
                    logger.warning(
                        f"⚠️ Stream interrupted ({error_str}). "
                        f"Retrying attempt {attempt + 2}/{max_retries}..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                    continue
                else:
                    logger.error(f"Google Provider Stream Error: {error_str}", exc_info=True)
                    raise RuntimeError(f"Google Provider Stream Error: {error_str}") from e 