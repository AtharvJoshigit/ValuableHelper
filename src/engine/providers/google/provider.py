# engine/providers/google/provider.py (PRODUCTION-GRADE)
"""
Production-ready Google Gemini provider with robust error handling.

Features:
1. Proper retry logic for transient errors
2. Rate limit handling
3. Model-specific configuration
4. Comprehensive error messages
"""

import asyncio
import os
import logging
from typing import List, Optional, AsyncIterator
import time

from google import genai
from google.genai import types as genai_types

from engine.core.types import Message, AgentResponse, StreamChunk
from engine.registry.base_tool import BaseTool
from engine.providers.base_provider import BaseProvider
from engine.providers.google.adapter import GoogleAdapter, ConversationPatternError

logger = logging.getLogger(__name__)

class GoogleProviderError(Exception):
    """Base exception for Google Provider errors."""
    pass

class GoogleRateLimitError(GoogleProviderError):
    """Raised when rate limit is hit."""
    pass

class GoogleProvider(BaseProvider):
    """
    Production Google Gemini provider with robust error handling.
    
    Handles:
    - Rate limiting with exponential backoff
    - Transient network errors
    - Invalid conversation patterns
    - Model-specific quirks
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
        self.model_id = model_id
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Google API key required. Set GOOGLE_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_tokens = max_tokens
        self.additional_params = additional_params
        
        # Initialize client
        self.client = genai.Client(
            api_key=self.api_key,
            http_options={'api_version': 'v1beta'}
        )
        
        # Rate limiting
        self._last_request_time = 0.0
        self._min_request_interval = 0.1  # 100ms between requests
        
        logger.info(
            f"✅ Google Provider initialized: {model_id} "
            f"(temp={temperature}, max_tokens={max_tokens or 'default'})"
        )

    def _build_config(
        self, 
        tools: List[BaseTool], 
        system_instruction: Optional[str]
    ) -> genai_types.GenerateContentConfig:
        """Build generation config with all parameters."""
        config = {
            "temperature": self.temperature,
            "system_instruction": system_instruction,
        }
        
        # Optional parameters
        if self.max_tokens:
            config["max_output_tokens"] = self.max_tokens
        if self.top_p is not None:
            config["top_p"] = self.top_p
        if self.top_k is not None:
            config["top_k"] = self.top_k
        
        # Convert and add tools
        if tools:
            tool_defs = [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.get_schema()
                }
                for t in tools
            ]
            
            google_funcs = GoogleAdapter.convert_tools(tool_defs)
            
            if google_funcs:
                func_declarations = [
                    genai_types.FunctionDeclaration(
                        name=f["name"],
                        description=f["description"],
                        parameters=f["parameters"]
                    )
                    for f in google_funcs
                ]
                
                config["tools"] = [
                    genai_types.Tool(function_declarations=func_declarations)
                ]
                
                config["automatic_function_calling"] = genai_types.AutomaticFunctionCallingConfig(
                    disable=True
                )
        
        # Thinking config for thinking models
        if self.additional_params.get("include_thoughts", False):
            config["thinking_config"] = genai_types.ThinkingConfig(
                include_thoughts=True
            )
            logger.debug(f"Thinking mode enabled for {self.model_id}")
        
        return genai_types.GenerateContentConfig(**config)

    async def _rate_limit_wait(self):
        """Implement simple rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    async def generate(
        self, 
        history: List[Message], 
        tools: List[BaseTool] = None
    ) -> AgentResponse:
        """
        Generate non-streaming response with retry logic.
        
        Handles:
        - Conversation pattern errors (400)
        - Rate limiting (429)
        - Transient network errors (500)
        """
        tools = tools or []
        
        # Extract system instruction
        system_instruction = GoogleAdapter.extract_system_instruction(history)
        
        # Convert history with strict validation
        try:
            contents = GoogleAdapter.convert_history(history, self.model_id)
        except ConversationPatternError as e:
            logger.error(f"Invalid conversation pattern: {e}")
            raise GoogleProviderError(
                f"Invalid conversation pattern: {e}. "
                "This usually means tool calls are not properly paired with responses."
            ) from e
        
        # Build config
        config = self._build_config(tools, system_instruction)
        
        # Retry logic for transient errors
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Rate limiting
                await self._rate_limit_wait()
                
                # Make request
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model=self.model_id,
                        contents=contents,
                        config=config
                    )
                )
                
                # Convert and return
                return GoogleAdapter.convert_response(response, self.model_id)
                
            except Exception as e:
                error_str = str(e)
                
                # Check error type
                is_rate_limit = "429" in error_str or "RATE_LIMIT" in error_str
                is_transient = any(
                    msg in error_str for msg in [
                        "500", "502", "503", "504",
                        "INTERNAL", "UNAVAILABLE", "DEADLINE_EXCEEDED"
                    ]
                )
                is_invalid_argument = "400" in error_str or "INVALID_ARGUMENT" in error_str
                
                # Don't retry on client errors (400)
                if is_invalid_argument:
                    logger.error(f"Invalid request (400): {error_str}")
                    raise GoogleProviderError(
                        f"Invalid request to Gemini API: {error_str}\n\n"
                        "This usually indicates:\n"
                        "1. Function call not followed by function response\n"
                        "2. Consecutive messages from same role\n"
                        "3. Missing thought signature for thinking models\n"
                        "4. Invalid conversation pattern"
                    ) from e
                
                # Retry on rate limits and transient errors
                if (is_rate_limit or is_transient) and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"⚠️ Transient error (attempt {attempt + 1}/{max_retries}): {error_str}\n"
                        f"   Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    continue
                
                # All retries exhausted or non-retryable error
                logger.error(f"Google API error: {error_str}", exc_info=True)
                raise GoogleProviderError(f"Google API error: {error_str}") from e
        
        raise GoogleProviderError("Max retries exceeded")

    async def stream(
        self, 
        history: List[Message], 
        tools: List[BaseTool] = None
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream responses with proper error handling.
        
        Handles:
        - Connection interruptions
        - Rate limiting
        - Pattern validation errors
        """
        tools = tools or []
        
        # Extract system instruction
        system_instruction = GoogleAdapter.extract_system_instruction(history)
        
        # Convert history with strict validation
        try:
            contents = GoogleAdapter.convert_history(history, self.model_id)
        except ConversationPatternError as e:
            logger.error(f"Invalid conversation pattern: {e}")
            yield StreamChunk(
                content=f"\n\n❌ Error: Invalid conversation pattern: {e}"
            )
            raise GoogleProviderError(
                f"Invalid conversation pattern: {e}"
            ) from e
        
        # Build config
        config = self._build_config(tools, system_instruction)
        
        # Retry logic for stream interruptions
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                # Rate limiting
                await self._rate_limit_wait()
                
                # Start streaming
                logger.debug(f"Starting stream (attempt {attempt + 1})")
                response_iterator = await self.client.aio.models.generate_content_stream(
                    model=self.model_id,
                    contents=contents,
                    config=config
                )
                
                chunk_count = 0
                
                # Stream chunks
                async for chunk in response_iterator:
                    chunk_count += 1
                    
                    # Convert chunk
                    stream_chunk = GoogleAdapter.convert_stream_chunk(
                        chunk, 
                        self.model_id
                    )
                    
                    if stream_chunk:
                        yield stream_chunk
                
                logger.debug(f"Stream completed: {chunk_count} chunks")
                return  # Success
                
            except Exception as e:
                error_str = str(e)
                
                # Check error type
                is_network = any(
                    msg in error_str for msg in [
                        "Connection", "EOF", "IncompleteRead",
                        "Timeout", "reset"
                    ]
                )
                
                is_invalid_argument = "400" in error_str or "INVALID_ARGUMENT" in error_str
                
                # Don't retry on client errors
                if is_invalid_argument:
                    logger.error(f"Invalid request (400): {error_str}")
                    yield StreamChunk(
                        content=f"\n\n❌ Error: Invalid request: {error_str}"
                    )
                    raise GoogleProviderError(
                        f"Invalid request: {error_str}"
                    ) from e
                
                # Retry on network errors
                if is_network and attempt < max_retries - 1:
                    logger.warning(
                        f"⚠️ Stream interrupted (attempt {attempt + 1}/{max_retries}): {error_str}\n"
                        f"   Retrying..."
                    )
                    await asyncio.sleep(1.0)
                    continue
                
                # All retries exhausted
                logger.error(f"Stream error: {error_str}", exc_info=True)
                yield StreamChunk(
                    content=f"\n\n❌ Error: {error_str}"
                )
                raise GoogleProviderError(f"Stream error: {error_str}") from e
        
        raise GoogleProviderError("Max stream retries exceeded")