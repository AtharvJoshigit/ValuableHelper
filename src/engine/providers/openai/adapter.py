# engine/providers/openai/adapter.py

from typing import List, Dict, Any, Optional
import json
import logging
import re
from copy import deepcopy

from engine.core.types import (
    Message, 
    Role, 
    ToolCall, 
    AgentResponse, 
    UsageMetadata,
    StreamChunk
)

logger = logging.getLogger(__name__)

class OpenAIAdapter:
    """
    Production-ready OpenAI adapter with robust error handling.
    
    Handles conversion between internal Message format and OpenAI's format.
    """

    @staticmethod
    def _sanitize_string(s: str) -> str:
        """Sanitize string to prevent JSON encoding issues."""
        if not isinstance(s, str):
            return str(s)
        
        # Remove null bytes and control characters
        s = s.replace('\x00', '')
        s = re.sub(r'[\x01-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', s)
        
        # Ensure proper UTF-8 encoding
        try:
            s = s.encode('utf-8', errors='ignore').decode('utf-8')
        except Exception:
            pass
        
        return s

    @staticmethod
    def _validate_json_serializable(obj: Any, max_depth: int = 10) -> Any:
        """Validate and fix object to be JSON-serializable."""
        if max_depth <= 0:
            return str(obj)
        
        if obj is None or isinstance(obj, (bool, int, float)):
            return obj
        
        if isinstance(obj, str):
            return OpenAIAdapter._sanitize_string(obj)
        
        if isinstance(obj, dict):
            sanitized = {}
            for k, v in obj.items():
                key = OpenAIAdapter._sanitize_string(str(k))
                sanitized[key] = OpenAIAdapter._validate_json_serializable(v, max_depth - 1)
            return sanitized
        
        if isinstance(obj, (list, tuple)):
            return [
                OpenAIAdapter._validate_json_serializable(item, max_depth - 1) 
                for item in obj
            ]
        
        return OpenAIAdapter._sanitize_string(str(obj))

    @staticmethod
    def convert_tools(tools_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert tool definitions to OpenAI function format.
        
        OpenAI expects:
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": {...}
            }
        }
        """
        openai_tools = []
        
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
                
                OpenAIAdapter._clean_schema(parameters)
                
                # Validate
                name = OpenAIAdapter._sanitize_string(tool["name"])
                description = OpenAIAdapter._sanitize_string(tool["description"])
                parameters = OpenAIAdapter._validate_json_serializable(parameters)
                
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": parameters
                    }
                }
                
                # Test serialization
                try:
                    json.dumps(tool_def)
                    openai_tools.append(tool_def)
                except Exception as e:
                    logger.error(f"Tool '{name}' not JSON-serializable: {e}")
                    continue
                
            except Exception as e:
                logger.error(f"Failed to convert tool '{tool.get('name', 'unknown')}': {e}")
                continue
        
        return openai_tools
    
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
                    OpenAIAdapter._clean_schema(prop_schema)
        
        if "items" in schema and isinstance(schema["items"], dict):
            OpenAIAdapter._clean_schema(schema["items"])

    @staticmethod
    def extract_system_message(history: List[Message]) -> Optional[str]:
        """Extract and combine all system messages."""
        system_msgs = [m.content for m in history if m.role == Role.SYSTEM and m.content]
        return "\n\n".join(system_msgs) if system_msgs else None

    @staticmethod
    def _consolidate_consecutive_roles(
        openai_history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge consecutive messages with the same role.
        OpenAI requires alternating user/assistant messages.
        """
        if not openai_history:
            return []
        
        consolidated = [openai_history[0]]
        
        for msg in openai_history[1:]:
            last_msg = consolidated[-1]
            
            # Same role? Merge the content
            if msg["role"] == last_msg["role"]:
                logger.warning(
                    f"Merging consecutive {msg['role']} messages"
                )
                
                # Merge content (both could be strings or lists)
                last_content = last_msg.get("content", "")
                new_content = msg.get("content", "")
                
                if isinstance(last_content, str) and isinstance(new_content, str):
                    last_msg["content"] = f"{last_content}\n\n{new_content}"
                else:
                    # Handle tool calls
                    if "tool_calls" in msg:
                        if "tool_calls" not in last_msg:
                            last_msg["tool_calls"] = []
                        last_msg["tool_calls"].extend(msg["tool_calls"])
            else:
                consolidated.append(msg)
        
        return consolidated

    @staticmethod
    def _validate_openai_pattern(
        openai_history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate OpenAI message pattern.
        
        Rules:
        - Messages must alternate between user and assistant
        - Tool calls must be followed by tool results
        - No dangling tool calls at the end
        """
        if not openai_history:
            return []
        
        validated = []
        
        for i, msg in enumerate(openai_history):
            role = msg["role"]
            
            # Check for dangling tool calls at the end
            is_last = (i == len(openai_history) - 1)
            if is_last and "tool_calls" in msg and msg["tool_calls"]:
                logger.warning("Removing dangling tool calls from history end")
                msg_copy = msg.copy()
                msg_copy.pop("tool_calls", None)
                if msg_copy.get("content"):
                    validated.append(msg_copy)
                else:
                    logger.warning("Skipping empty assistant message at end")
                    continue
            else:
                validated.append(msg)
        
        # Final check: ensure alternating pattern
        if len(validated) >= 2:
            for i in range(len(validated) - 1):
                current_role = validated[i]["role"]
                next_role = validated[i + 1]["role"]
                
                # Allow tool role to follow assistant
                if current_role == next_role and current_role != "tool":
                    logger.error(
                        f"PATTERN VIOLATION at index {i}: "
                        f"{current_role} → {next_role} (should alternate)"
                    )
        
        return validated

    @staticmethod
    def _safe_debug_print(openai_history: List[Dict[str, Any]]):
        """Debug print that's safe for logging."""
        safe_history = []
        
        for msg in openai_history:
            safe_msg = {"role": msg.get("role")}
            
            content = msg.get("content")
            if content:
                if isinstance(content, str):
                    safe_msg["content"] = content[:100] + "..." if len(content) > 100 else content
                else:
                    safe_msg["content"] = str(content)[:100]
            
            if "tool_calls" in msg:
                safe_msg["tool_calls"] = [
                    {
                        "id": tc.get("id", "unknown"),
                        "function": {
                            "name": tc.get("function", {}).get("name", "unknown")
                        }
                    }
                    for tc in msg["tool_calls"][:3]  # Show first 3
                ]
            
            if "tool_call_id" in msg:
                safe_msg["tool_call_id"] = msg["tool_call_id"]
            
            safe_history.append(safe_msg)
        
        logger.info(f"History being sent ({len(safe_history)} messages):")
        logger.info(json.dumps(safe_history, indent=2))

    @staticmethod
    def convert_history(
        history: List[Message]
    ) -> List[Dict[str, Any]]:
        """
        Convert Message history to OpenAI format.
        
        OpenAI format:
        - system: {"role": "system", "content": "..."}
        - user: {"role": "user", "content": "..."}
        - assistant: {"role": "assistant", "content": "...", "tool_calls": [...]}
        - tool: {"role": "tool", "tool_call_id": "...", "content": "..."}
        """
        logger.debug(f"Converting history: {len(history)} messages")
        
        openai_history = []
        
        for idx, msg in enumerate(history):
            try:
                # System messages
                if msg.role == Role.SYSTEM:
                    if msg.content and msg.content.strip():
                        openai_history.append({
                            "role": "system",
                            "content": OpenAIAdapter._sanitize_string(msg.content)
                        })
                    continue
                
                # User messages
                if msg.role == Role.USER:
                    if msg.content and msg.content.strip():
                        openai_history.append({
                            "role": "user",
                            "content": OpenAIAdapter._sanitize_string(msg.content)
                        })
                    continue
                
                # Assistant messages (with optional tool calls)
                if msg.role == Role.ASSISTANT:
                    assistant_msg = {"role": "assistant"}
                    
                    # Add content if present
                    if msg.content and msg.content.strip():
                        assistant_msg["content"] = OpenAIAdapter._sanitize_string(msg.content)
                    
                    # Add tool calls if present
                    if msg.tool_calls:
                        tool_calls = []
                        for tc in msg.tool_calls:
                            try:
                                args = OpenAIAdapter._prepare_arguments(tc.arguments)
                                args = OpenAIAdapter._validate_json_serializable(args)
                                
                                # Validate JSON serialization
                                args_str = json.dumps(args)
                                
                                tool_calls.append({
                                    "id": tc.id or f"call_{idx}",
                                    "type": "function",
                                    "function": {
                                        "name": tc.name,
                                        "arguments": args_str
                                    }
                                })
                            except Exception as e:
                                logger.error(f"Failed to convert tool call '{tc.name}': {e}")
                                continue
                        
                        if tool_calls:
                            assistant_msg["tool_calls"] = tool_calls
                    
                    # Only add if has content or tool calls
                    if "content" in assistant_msg or "tool_calls" in assistant_msg:
                        openai_history.append(assistant_msg)
                    else:
                        logger.warning(f"Skipping empty assistant message at index {idx}")
                    continue
                
                # Tool result messages
                if msg.role == Role.TOOL:
                    if msg.tool_results:
                        for tr in msg.tool_results:
                            try:
                                result_data = OpenAIAdapter._prepare_tool_result(tr.result)
                                result_data = OpenAIAdapter._validate_json_serializable(result_data)
                                
                                # OpenAI expects string content
                                result_str = json.dumps(result_data)
                                
                                openai_history.append({
                                    "role": "tool",
                                    "tool_call_id": tr.tool_call_id or tr.name,
                                    "content": result_str
                                })
                            except Exception as e:
                                logger.error(f"Failed to convert tool result '{tr.name}': {e}")
                                openai_history.append({
                                    "role": "tool",
                                    "tool_call_id": tr.tool_call_id or tr.name,
                                    "content": json.dumps({"error": f"Conversion failed: {str(e)}"})
                                })
                    continue
                
            except Exception as e:
                logger.error(f"Error processing message at index {idx}: {e}", exc_info=True)
                continue
        
        # Consolidate consecutive messages
        openai_history = OpenAIAdapter._consolidate_consecutive_roles(openai_history)
        
        # Validate pattern
        openai_history = OpenAIAdapter._validate_openai_pattern(openai_history)
        
        # Debug print
        OpenAIAdapter._safe_debug_print(openai_history)
        
        return openai_history

    @staticmethod
    def _prepare_arguments(arguments: Any) -> Dict[str, Any]:
        """Prepare and validate tool arguments."""
        if arguments is None:
            return {}
        
        if isinstance(arguments, dict):
            return arguments
        
        if isinstance(arguments, str):
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
            try:
                json.dumps(result)
                return result
            except (TypeError, ValueError) as e:
                logger.warning(f"Dict result not serializable: {e}")
                return {"result": str(result)}
        
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
                return {"result": parsed}
            except json.JSONDecodeError:
                return {"result": result}
        
        if isinstance(result, (int, float, bool)):
            return {"result": result}
        
        if isinstance(result, list):
            try:
                json.dumps(result)
                return {"result": result}
            except (TypeError, ValueError):
                return {"result": str(result)}
        
        return {"result": str(result)}

    @staticmethod
    def convert_response(response: Any) -> AgentResponse:
        """
        Convert OpenAI response to AgentResponse.
        
        OpenAI response structure:
        {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "...",
                    "tool_calls": [...]
                }
            }],
            "usage": {...}
        }
        """
        content = None
        tool_calls = []
        
        if not response.choices:
            return AgentResponse(content="Error: No choices returned.")
        
        choice = response.choices[0]
        message = choice.message
        
        # Extract content
        if hasattr(message, 'content') and message.content:
            content = message.content
        
        # Extract tool calls
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tc in message.tool_calls:
                try:
                    # Parse arguments
                    args = {}
                    if hasattr(tc.function, 'arguments'):
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse tool arguments: {tc.function.arguments}")
                            args = {"raw": tc.function.arguments}
                    
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args
                    ))
                except Exception as e:
                    logger.error(f"Error processing tool call: {e}")
        
        # Extract usage
        usage = None
        if hasattr(response, 'usage') and response.usage:
            usage = UsageMetadata(
                input_tokens=getattr(response.usage, 'prompt_tokens', 0) or 0,
                output_tokens=getattr(response.usage, 'completion_tokens', 0) or 0,
                total_tokens=getattr(response.usage, 'total_tokens', 0) or 0
            )
        
        return AgentResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage
        )
    
    @staticmethod
    def convert_stream_chunk(chunk: Any) -> Optional[StreamChunk]:
        """
        Convert OpenAI stream chunk to StreamChunk.
        
        OpenAI stream format:
        {
            "choices": [{
                "delta": {
                    "content": "...",
                    "tool_calls": [...]
                }
            }]
        }
        """
        if not chunk.choices:
            return None
        
        choice = chunk.choices[0]
        delta = choice.delta
        
        stream_chunk = StreamChunk()
        
        # Extract content delta
        if hasattr(delta, 'content') and delta.content:
            stream_chunk.content = delta.content
        
        # Extract tool call deltas
        if hasattr(delta, 'tool_calls') and delta.tool_calls:
            for tc in delta.tool_calls:
                try:
                    # OpenAI streams tool calls incrementally
                    if hasattr(tc, 'function') and tc.function:
                        # Parse arguments if present
                        args = {}
                        if hasattr(tc.function, 'arguments') and tc.function.arguments:
                            try:
                                args = json.loads(tc.function.arguments)
                            except json.JSONDecodeError:
                                # Partial JSON, skip for now
                                continue
                        
                        tool_call = ToolCall(
                            id=tc.id if hasattr(tc, 'id') else None,
                            name=tc.function.name if hasattr(tc.function, 'name') else None,
                            arguments=args
                        )
                        
                        stream_chunk.tool_call = tool_call
                except Exception as e:
                    logger.error(f"Error processing stream tool call: {e}")
        
        if stream_chunk.content or stream_chunk.tool_call:
            return stream_chunk
        
        return None