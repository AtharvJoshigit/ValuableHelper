import asyncio
import json
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
    
    def __init__(self, model_id: str = "gemini-1.5-flash", api_key: Optional[str] = None, **kwargs):
        """
        Initialize the Google provider.
        """
        self.model_id = model_id
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.config = kwargs
        if not self.api_key:
            raise ValueError("Google API key must be provided or set in GOOGLE_API_KEY environment variable.")
            
        self.client = genai.Client(api_key=self.api_key)

    def _create_function_declarations(self, tools: List[BaseTool]) -> List[genai_types.FunctionDeclaration]:
        """
        Create Google FunctionDeclaration objects from tools.
        """
        function_declarations = []
        
        for tool in tools:
            try:
                schema = tool.get_schema()
                
                # Extract properties and required fields
                properties = schema.get("properties", {})
                required = schema.get("required", [])
                
                # Create FunctionDeclaration
                func_decl = genai_types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description or f"Executes the {tool.name} command.",
                    parameters=genai_types.Schema(
                        type=genai_types.Type.OBJECT,
                        properties={
                            key: self._convert_property_to_schema(key, prop)
                            for key, prop in properties.items()
                        },
                        required=required
                    )
                )
                function_declarations.append(func_decl)
            except Exception as e:
                logger.error(f"Failed to convert tool '{tool.name}' to Google schema: {e}")
                continue
        
        return function_declarations
    
    def _convert_property_to_schema(self, name: str, prop: dict) -> genai_types.Schema:
        """
        Convert a property definition to Google genai Schema.
        Ensures a description is ALWAYS present to satisfy Gemini's strictness.
        """
        prop_type = prop.get("type", "string")
        description = prop.get("description") or f"The {name} parameter."
        
        # Handle array types
        if prop_type == "array":
            items_schema = prop.get("items", {})
            items_type = items_schema.get("type", "string")
            
            return genai_types.Schema(
                type=genai_types.Type.ARRAY,
                description=description,
                items=genai_types.Schema(
                    type=self._convert_type(items_type)
                )
            )
        
        # Handle object types
        elif prop_type == "object":
            nested_properties = prop.get("properties", {})
            
            return genai_types.Schema(
                type=genai_types.Type.OBJECT,
                description=description,
                properties={
                    key: self._convert_property_to_schema(key, nested_prop)
                    for key, nested_prop in nested_properties.items()
                }
            )
        
        # Handle simple types
        else:
            return genai_types.Schema(
                type=self._convert_type(prop_type),
                description=description
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
    
    def _get_config(self, tools: List[BaseTool]) -> genai_types.GenerateContentConfig :
        print(f"----------{self.config.get(
                "additional_params", {}).get("include_thoughts")}----------")
        if tools:
            function_declarations = self._create_function_declarations(tools)
            tool = genai_types.Tool(function_declarations=function_declarations)
            return genai_types.GenerateContentConfig(
                tools=[tool],
                temperature=self.config.get('temp'),
                top_k=self.config.get('top_k'),
                top_p=self.config.get('top_p'),
                max_output_tokens = self.config.get('max_tokens'),
                response_schema = self.config.get('response_schema'),
                automatic_function_calling = self.config.get('automatic_function_calling', {
                    'disable': True,
                    'maximum_remote_calls' : 0
                    }
                ),
                thinking_config = genai_types.ThinkingConfig(include_thoughts=self.config.get(
                "additional_params", {}).get("include_thoughts"))
            )
        return genai_types.GenerateContentConfig(
            temperature=self.config.get('temp'),
            top_k=self.config.get('top_k'),
            top_p=self.config.get('top_p'),
            max_output_tokens = self.config.get('max_tokens'),
            response_schema = self.config.get('response_schema'),
            automatic_function_calling = self.config.get('automatic_function_calling', {
                'disable': True,
                'maximum_remote_calls' : 0
                },
            ),
            thinking_config = genai_types.ThinkingConfig(include_thoughts=self.config.get(
                "additional_params", {}).get("include_thoughts"))
        )

    async def generate(self, history: List[Message], tools: List[BaseTool]) -> AgentResponse:
        """
        Generate a response from the model.
        """
        contents = GoogleAdapter.convert_history(history)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model=self.model_id,
                    contents=contents,
                    config= self._get_config(tools),
                )
            )
            return GoogleAdapter.convert_response(response)
            
        except Exception as e:
            logger.error(f"Google Provider Generate Error: {str(e)}")
            raise RuntimeError(f"Google Provider Generate Error: {str(e)}") from e

    async def stream(self, history: List[Message], tools: List[BaseTool]) -> Iterator[StreamChunk]:
        """
        Stream the response from the model with retry logic.
        """
        contents = GoogleAdapter.convert_history(history)
        

        max_retries = 3
        retry_delay = 1.5
        for attempt in range(max_retries):
            try:
                print(f"------------{self.model_id}--------------")
                response_iterator = self.client.models.generate_content_stream(
                    model=self.model_id,
                    contents=contents,
                    config= self._get_config(tools)
                )
                
                for chunk in response_iterator:
                    text = None
                    try:
                        text = chunk.text
                    except (AttributeError, ValueError):
                        pass
                    
                    tool_call = None
                    if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                        for part in chunk.candidates[0].content.parts:
                            if part.function_call:
                                args = {}
                                if hasattr(part.function_call, 'args') and part.function_call.args:
                                    try:
                                        args = dict(part.function_call.args)
                                    except (AttributeError, TypeError, ValueError) as e:
                                        logger.warning(f"Failed to parse function args: {e}")

                                tool_call = ToolCall(
                                    id=part.function_call.name,
                                    name=part.function_call.name,
                                    arguments=args
                                )
                    
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
                break

            except Exception as e:
                error_str = str(e)
                is_network_error = any(msg in error_str for msg in ["IncompleteRead", "Connection broken", "EOF occurred"])
                
                if is_network_error and attempt < max_retries - 1:
                    logger.warning(f"Stream interrupted ({error_str}). Retrying attempt {attempt + 2}/{max_retries}...")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"Google Provider Stream Error: {error_str}")
                    raise RuntimeError(f"Google Provider Stream Error: {error_str}") from e
