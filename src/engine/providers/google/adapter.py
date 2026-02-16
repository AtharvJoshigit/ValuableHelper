# engine/providers/google/adapter.py (ROBUST VERSION)

from typing import List, Dict, Any, Optional
import json
import logging
import re
from copy import deepcopy

from google.genai import types as genai_types

from engine.core.types import (
    Message, 
    Role, 
    ToolCall, 
    AgentResponse, 
    UsageMetadata,
    StreamChunk
)
from engine.utils import utility

logger = logging.getLogger(__name__)

class GoogleAdapter:
    """
    Production-ready adapter with robust error handling and data validation.
    """

    THINKING_MODELS = {
        'gemini-2.0-flash-thinking-exp',
        'gemini-2.0-flash-thinking-exp-1219',
        'gemini-exp-1206',
        'gemini-3-flash-preview'
    }

    @staticmethod
    def is_thinking_model(model_id: str) -> bool:
        """Check if model requires thought signatures."""
        if model_id in GoogleAdapter.THINKING_MODELS:
            return True
        model_lower = model_id.lower()
        return 'thinking' in model_lower or model_id.startswith('gemini-exp-')

    @staticmethod
    def _sanitize_string(s: str) -> str:
        """
        Sanitize string to prevent JSON encoding issues.
        Removes problematic characters that break JSON.
        """
        if not isinstance(s, str):
            return str(s)
        
        # Remove null bytes and other control characters
        s = s.replace('\x00', '')
        
        # Remove other problematic control characters (except newline, tab, carriage return)
        s = re.sub(r'[\x01-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', s)
        
        # Ensure proper UTF-8 encoding
        try:
            s = s.encode('utf-8', errors='ignore').decode('utf-8')
        except Exception:
            pass
        
        return s

    @staticmethod
    def _validate_json_serializable(obj: Any, max_depth: int = 10) -> Any:
        """
        Validate and fix object to be JSON-serializable.
        Returns sanitized version of object.
        """
        if max_depth <= 0:
            return str(obj)
        
        if obj is None or isinstance(obj, (bool, int, float)):
            return obj
        
        if isinstance(obj, str):
            return GoogleAdapter._sanitize_string(obj)
        
        if isinstance(obj, dict):
            sanitized = {}
            for k, v in obj.items():
                # Sanitize key
                key = GoogleAdapter._sanitize_string(str(k))
                # Recursively validate value
                sanitized[key] = GoogleAdapter._validate_json_serializable(v, max_depth - 1)
            return sanitized
        
        if isinstance(obj, (list, tuple)):
            return [
                GoogleAdapter._validate_json_serializable(item, max_depth - 1) 
                for item in obj
            ]
        
        # Fallback: convert to string
        return GoogleAdapter._sanitize_string(str(obj))

    @staticmethod
    def convert_tools(tools_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert tool definitions with validation."""
        google_functions = []
        
        for tool in tools_data:
            try:
                parameters = deepcopy(tool.get("parameters", {}))
                
                # Remove incompatible fields
                fields_to_remove = [
                    "title", "$schema", "additionalProperties", 
                    "$defs", "definitions", "allOf", "anyOf", "oneOf"
                ]
                
                for field in fields_to_remove:
                    parameters.pop(field, None)
                
                GoogleAdapter._clean_schema(parameters)
                
                # Validate tool name and description
                name = GoogleAdapter._sanitize_string(tool["name"])
                description = GoogleAdapter._sanitize_string(tool["description"])
                
                # Validate parameters schema is JSON-serializable
                parameters = GoogleAdapter._validate_json_serializable(parameters)
                
                func_decl = {
                    "name": name,
                    "description": description,
                    "parameters": parameters
                }
                
                # Test serialization before adding
                try:
                    json.dumps(func_decl)
                    google_functions.append(func_decl)
                except Exception as e:
                    logger.error(f"Tool '{name}' not JSON-serializable: {e}")
                    continue
                
            except Exception as e:
                logger.error(f"Failed to convert tool '{tool.get('name', 'unknown')}': {e}")
                continue
        
        return google_functions
    
    @staticmethod
    def _clean_schema(schema: Dict[str, Any]) -> None:
        """Recursively clean schema."""
        if not isinstance(schema, dict):
            return
        
        for field in ["title", "additionalProperties", "$defs", "definitions"]:
            schema.pop(field, None)
        
        if "properties" in schema:
            for prop_schema in schema["properties"].values():
                if isinstance(prop_schema, dict):
                    GoogleAdapter._clean_schema(prop_schema)
        
        if "items" in schema and isinstance(schema["items"], dict):
            GoogleAdapter._clean_schema(schema["items"])

    @staticmethod
    def convert_history(
        history: List[Message], 
        model_id: str
    ) -> List[Dict[str, Any]]:
        """
        Convert Message history with robust validation.
        """
        is_thinking_model = GoogleAdapter.is_thinking_model(model_id)
        google_history = []
        
        for idx, msg in enumerate(history):
            try:
                parts = []
                
                # 1. Text Content - sanitize
                if msg.content and msg.content.strip():
                    sanitized_content = GoogleAdapter._sanitize_string(msg.content)
                    parts.append({"text": sanitized_content})

                # 2. Tool Calls - validate and sanitize
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        try:
                            # Prepare and validate arguments
                            args = GoogleAdapter._prepare_arguments(tc.arguments)
                            
                            # Validate args are JSON-serializable
                            args = GoogleAdapter._validate_json_serializable(args)
                            
                            # Test serialization
                            try:
                                json.dumps(args)
                            except Exception as e:
                                logger.error(f"Tool call args not serializable: {e}")
                                args = {"error": "Arguments could not be serialized"}
                            
                            func_call = genai_types.FunctionCall(
                                name=tc.name,
                                args=args
                            )
                            
                            part = genai_types.Part(function_call=func_call)
                            
                            # Add thought signature for thinking models
                            if is_thinking_model:
                                part.thought = True
                            
                            parts.append(part)
                            
                        except Exception as e:
                            logger.error(f"Failed to convert tool call '{tc.name}': {e}", exc_info=True)
                            parts.append({"text": f"[Tool call conversion error: {tc.name}]"})

                # 3. Tool Results - validate and sanitize
                if msg.tool_results:
                    for tr in msg.tool_results:
                        try:
                            # Prepare and validate result
                            result_data = GoogleAdapter._prepare_tool_result(tr.result)
                            
                            # Double validation
                            result_data = GoogleAdapter._validate_json_serializable(result_data)
                            
                            # Test serialization
                            try:
                                json.dumps(result_data)
                            except Exception as e:
                                logger.error(f"Tool result not serializable: {e}")
                                result_data = {"result": "Result could not be serialized", "error": str(e)}
                            
                            parts.append({
                                "function_response": {
                                    "name": tr.name,
                                    "response": result_data
                                }
                            })
                            
                        except Exception as e:
                            logger.error(f"Failed to convert tool result '{tr.name}': {e}", exc_info=True)
                            parts.append({
                                "function_response": {
                                    "name": tr.name,
                                    "response": {"error": f"Conversion failed: {str(e)}"}
                                }
                            })
                
                if not parts:
                    logger.warning(f"Skipping empty message at index {idx}")
                    continue
                
                # Map role
                if msg.role == Role.ASSISTANT:
                    role = "model"
                elif msg.role == Role.TOOL:
                    role = "user"
                elif msg.role == Role.SYSTEM:
                    role = "system"
                else:
                    role = "user"
                
                content_dict = {
                    "role": utility.to_gemini_role(role),
                    "parts": parts
                }
                
                # Final validation - test entire message serialization
                try:
                    json.dumps(content_dict, default=str)
                    google_history.append(content_dict)
                except Exception as e:
                    logger.error(f"Message at index {idx} not serializable: {e}")
                    # Add error message instead
                    google_history.append({
                        "role": "user",
                        "parts": [{"text": "[Previous message could not be processed]"}]
                    })
                
            except Exception as e:
                logger.error(f"Error processing message at index {idx}: {e}", exc_info=True)
                continue

        return google_history

    @staticmethod
    def _prepare_arguments(arguments: Any) -> Dict[str, Any]:
        """Prepare and validate tool arguments."""
        if arguments is None:
            return {}
        
        if isinstance(arguments, dict):
            return arguments
        
        if isinstance(arguments, str):
            # Try parsing as JSON
            try:
                parsed = json.loads(arguments)
                return parsed if isinstance(parsed, dict) else {"value": parsed}
            except json.JSONDecodeError:
                logger.warning(f"Could not parse arguments as JSON: {arguments[:100]}")
                return {"raw_input": arguments}
        
        return {"value": str(arguments)}

    @staticmethod
    def _prepare_tool_result(result: Any) -> Dict[str, Any]:
        """Prepare and validate tool result."""
        if result is None:
            return {"result": None}
        
        if isinstance(result, dict):
            # Validate it's JSON-serializable
            try:
                json.dumps(result)
                return result
            except (TypeError, ValueError) as e:
                logger.warning(f"Dict result not serializable: {e}")
                return {"result": str(result)}
        
        if isinstance(result, str):
            # Check if it's JSON
            try:
                parsed = json.loads(result)
                # Wrap parsed result
                return {"result": parsed}
            except json.JSONDecodeError:
                # Plain string
                return {"result": result}
        
        if isinstance(result, (int, float, bool)):
            return {"result": result}
        
        if isinstance(result, list):
            try:
                json.dumps(result)
                return {"result": result}
            except (TypeError, ValueError):
                return {"result": str(result)}
        
        # Fallback
        return {"result": str(result)}

    @staticmethod
    def convert_response(response: Any, model_id: str) -> AgentResponse:
        """Convert response with error handling."""
        is_thinking_model = GoogleAdapter.is_thinking_model(model_id)
        content = None
        tool_calls = []
        
        if not response.candidates:
            return AgentResponse(content="Error: No candidates returned.")

        candidate = response.candidates[0]
        
        # Check finish reason
        if hasattr(candidate, 'finish_reason'):
            finish_reason = str(candidate.finish_reason)
            if 'SAFETY' in finish_reason:
                return AgentResponse(
                    content=f"⚠️ Response blocked by safety filters: {finish_reason}"
                )
        
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                try:
                    # Skip thought parts for thinking models
                    if is_thinking_model and hasattr(part, 'thought') and part.thought:
                        if hasattr(part, 'text') and part.text:
                            logger.debug(f"Thought: {part.text[:100]}")
                        continue
                    
                    # Extract text
                    if hasattr(part, 'text') and part.text:
                        content = (content or "") + part.text
                    
                    # Extract function calls
                    if hasattr(part, 'function_call') and part.function_call:
                        args = GoogleAdapter._extract_function_args(part.function_call)
                        
                        tool_calls.append(ToolCall(
                            id=part.function_call.name,
                            name=part.function_call.name,
                            arguments=args
                        ))
                        
                except Exception as e:
                    logger.error(f"Error processing part: {e}")

        # Usage metadata
        usage = None
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = UsageMetadata(
                input_tokens=getattr(response.usage_metadata, 'prompt_token_count', 0) or 0,
                output_tokens=getattr(response.usage_metadata, 'candidates_token_count', 0) or 0,
                total_tokens=getattr(response.usage_metadata, 'total_token_count', 0) or 0
            )

        return AgentResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage
        )
    
    @staticmethod
    def convert_stream_chunk(chunk: Any, model_id: str) -> Optional[StreamChunk]:
        """Convert stream chunk with validation."""
        is_thinking_model = GoogleAdapter.is_thinking_model(model_id)
        
        if not chunk.candidates:
            return None
        
        candidate = chunk.candidates[0]
        
        if not candidate.content or not candidate.content.parts:
            return None
        
        stream_chunk = StreamChunk()
        
        for part in candidate.content.parts:
            try:
                # Skip thoughts
                if is_thinking_model and hasattr(part, 'thought') and part.thought:
                    continue
                
                # Extract text delta
                if hasattr(part, 'text') and part.text:
                    stream_chunk.content = part.text
                
                # Extract function calls
                if hasattr(part, 'function_call') and part.function_call:
                    args = GoogleAdapter._extract_function_args(part.function_call)
                    
                    stream_chunk.tool_call = ToolCall(
                        id=part.function_call.name,
                        name=part.function_call.name,
                        arguments=args
                    )
                    
            except Exception as e:
                logger.error(f"Error processing stream chunk: {e}")
        
        if stream_chunk.content or stream_chunk.tool_call:
            return stream_chunk
        
        return None
    
    @staticmethod
    def _extract_function_args(function_call: Any) -> Dict[str, Any]:
        """Extract function arguments safely."""
        if not hasattr(function_call, 'args'):
            return {}
        
        args = function_call.args
        
        if args is None:
            return {}
        
        if isinstance(args, dict):
            return args
        
        try:
            return dict(args)
        except Exception:
            return {}