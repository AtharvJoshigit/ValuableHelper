import asyncio
import os
import logging
from typing import List, Iterator, Optional, Any, Dict
from google import genai
from google.genai import types as genai_types

from engine.core.types import Message, AgentResponse, StreamChunk, ToolCall, UsageMetadata
from engine.registry.base_tool import BaseTool
from engine.providers.base_provider import BaseProvider
from engine.providers.google.adapter import GoogleAdapter

logger = logging.getLogger(__name__)

class GoogleProvider(BaseProvider):
    """
    Google Gemini provider implementation using the new google-genai SDK.
    """
    
    def __init__(self, model_id: str = "gemini-1.5-flash", api_key: Optional[str] = None):
        """
        Initialize the Google provider.
        
        Args:
            model_id: The model ID to use (e.g., "gemini-1.5-flash").
            api_key: Google API key. If None, looks for GOOGLE_API_KEY env var.
        """
        self.model_id = model_id
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key must be provided or set in GOOGLE_API_KEY environment variable.")
            
        self.client = genai.Client(api_key=self.api_key)

    def _create_function_declarations(self, tools: List[BaseTool]) -> List[genai_types.FunctionDeclaration]:
        """
        Create Google FunctionDeclaration objects from tools.
        """
        function_declarations = []
        
        for tool in tools:
            schema = tool.get_schema()
            
            # Extract properties and required fields
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            
            # Create FunctionDeclaration
            func_decl = genai_types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        key: self._convert_property_to_schema(prop)
                        for key, prop in properties.items()
                    },
                    required=required
                )
            )
            function_declarations.append(func_decl)
        
        return function_declarations
    
    def _convert_property_to_schema(self, prop: dict) -> genai_types.Schema:
        """
        Convert a property definition to Google genai Schema.
        Handles arrays properly with items.
        """
        prop_type = prop.get("type", "string")
        
        # Handle array types - CRITICAL for Google API
        if prop_type == "array":
            items_schema = prop.get("items", {})
            items_type = items_schema.get("type", "string")
            
            return genai_types.Schema(
                type=genai_types.Type.ARRAY,
                description=prop.get("description", ""),
                items=genai_types.Schema(
                    type=self._convert_type(items_type)
                )
            )
        
        # Handle object types
        elif prop_type == "object":
            nested_properties = prop.get("properties", {})
            
            return genai_types.Schema(
                type=genai_types.Type.OBJECT,
                description=prop.get("description", ""),
                properties={
                    key: self._convert_property_to_schema(nested_prop)
                    for key, nested_prop in nested_properties.items()
                }
            )
        
        # Handle simple types (string, number, integer, boolean)
        else:
            return genai_types.Schema(
                type=self._convert_type(prop_type),
                description=prop.get("description", "")
            )

    
    def _convert_type(self, json_type: str) -> genai_types.Type:
        """
        Convert JSON schema type to Google genai Type.
        """
        type_mapping = {
            "string": genai_types.Type.STRING,
            "number": genai_types.Type.NUMBER,
            "integer": genai_types.Type.INTEGER,
            "boolean": genai_types.Type.BOOLEAN,
            "array": genai_types.Type.ARRAY,
            "object": genai_types.Type.OBJECT,
        }
        return type_mapping.get(json_type, genai_types.Type.STRING)

    async def generate(self, history: List[Message], tools: List[BaseTool]) -> AgentResponse:
        """
        Generate a response from the model.
        
        Args:
            history: List of conversation messages
            tools: List of available tools
            
        Returns:
            AgentResponse object containing content and/or tool calls
        """
        # Convert history to Google format
        contents = GoogleAdapter.convert_history(history)
        
        # Create config with tools if provided
        config = None
        if tools:
            function_declarations = self._create_function_declarations(tools)
            
            # Create Tool object wrapping the function declarations
            tool = genai_types.Tool(
                function_declarations=function_declarations
            )
            
            config = genai_types.GenerateContentConfig(
                tools=[tool]
            )

        try:
            # Run sync SDK call in executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model=self.model_id,
                    contents=contents,
                    config=config
                )
            )
            return GoogleAdapter.convert_response(response)
            
        except Exception as e:
            logger.error(f"Google Provider Generate Error: {str(e)}")
            raise RuntimeError(f"Google Provider Generate Error: {str(e)}") from e

    async def stream(self, history: List[Message], tools: List[BaseTool]) -> Iterator[StreamChunk]:
        """
        Stream the response from the model.
        
        Args:
            history: List of conversation messages
            tools: List of available tools
            
        Returns:
            Iterator of StreamChunk objects
        """
        contents = GoogleAdapter.convert_history(history)
        
        config = None
        if tools:
            function_declarations = self._create_function_declarations(tools)
            
            tool = genai_types.Tool(
                function_declarations=function_declarations
            )
            
            config = genai_types.GenerateContentConfig(
                tools=[tool]
            )

        try:
            # Use generate_content_stream
            response_iterator = self.client.models.generate_content_stream(
                model=self.model_id,
                contents=contents,
                config=config
            )
            
            for chunk in response_iterator:
                # Safe extraction of text
                text = None
                try:
                    text = chunk.text
                except (AttributeError, ValueError):
                    pass
                
                # Check for tool calls in chunk
                tool_call = None
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if part.function_call:
                            # Convert args to dict safely
                            args = {}
                            if hasattr(part.function_call, 'args') and part.function_call.args:
                                try:
                                    args = dict(part.function_call.args)
                                except (AttributeError, TypeError, ValueError) as e:
                                    logger.warning(f"Failed to parse function args: {e}")
                                    args = {}

                            tool_call = ToolCall(
                                id=part.function_call.name,
                                name=part.function_call.name,
                                arguments=args
                            )
                
                # Usage extraction
                usage = None
                if chunk.usage_metadata:
                    usage = UsageMetadata(
                        input_tokens=getattr(chunk.usage_metadata, 'prompt_token_count', 0),
                        output_tokens=getattr(chunk.usage_metadata, 'candidates_token_count', 0),
                        total_tokens=getattr(chunk.usage_metadata, 'total_token_count', 0)
                    )

                yield StreamChunk(
                    content=text,
                    tool_call=tool_call,
                    usage=usage
                )
                    
        except Exception as e:
            logger.error(f"Google Provider Stream Error: {str(e)}")
            raise RuntimeError(f"Google Provider Stream Error: {str(e)}") from e