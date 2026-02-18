# engine/providers/google/adapter.py
"""
Production-hardened Google Gemini adapter.
Enforces strict sequence: (user) -> (model: thought? + call?) -> (user: response) -> (model)
"""

import json
import logging
from typing import List, Dict, Any, Optional, Union
from copy import deepcopy

from google.genai import types as genai_types
from engine.core.types import (
    Message, Role, ToolCall, AgentResponse, UsageMetadata, StreamChunk
)

logger = logging.getLogger(__name__)

class ConversationPatternError(Exception):
    """Raised when conversation pattern violates Gemini's finite state machine."""
    pass

class GoogleAdapter:
    """Production adapter with strict Gemini conversation pattern validation."""

    THINKING_MODELS = {
        'gemini-2.0-flash-thinking-exp',
        'gemini-2.0-flash-thinking-exp-1219',
        'gemini-exp-1206',
        'gemini-3-flash-preview',
        'gemini-3-pro-preview'
    }

    @staticmethod
    def is_thinking_model(model_id: str) -> bool:
        return (
            model_id in GoogleAdapter.THINKING_MODELS or
            'thinking' in model_id.lower() or
            model_id.startswith('gemini-exp-')
        )

    @staticmethod
    def convert_tools(tools_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        google_functions = []
        for tool in tools_data:
            try:
                params = deepcopy(tool.get("parameters", {}))
                GoogleAdapter._clean_schema_recursive(params)
                google_functions.append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": params
                })
            except Exception as e:
                logger.error(f"Failed to convert tool '{tool.get('name')}': {e}")
        return google_functions

    @staticmethod
    def _clean_schema_recursive(schema: Dict[str, Any]) -> None:
        if not isinstance(schema, dict):
            return
        # Gemini's JSON schema subset is strict
        for field in ["title", "$schema", "additionalProperties", "$defs", "definitions", "allOf", "anyOf", "oneOf"]:
            schema.pop(field, None)
        
        for key, value in list(schema.items()):
            if isinstance(value, dict):
                GoogleAdapter._clean_schema_recursive(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        GoogleAdapter._clean_schema_recursive(item)

    @staticmethod
    def extract_system_instruction(history: List[Message]) -> Optional[str]:
        system_msgs = [m.content for m in history if m.role == Role.SYSTEM and m.content]
        return "\n\n".join(system_msgs) if system_msgs else None

    @staticmethod
    def convert_history(history: List[Message], model_id: str) -> List[Dict[str, Any]]:
        is_thinking = GoogleAdapter.is_thinking_model(model_id)
        
        # 1. Initial conversion
        google_history = GoogleAdapter._convert_messages_to_parts(history, is_thinking)
        
        # 2. Pattern Enforcement (Merging, Placeholders, Call/Response alignment)
        google_history = GoogleAdapter._enforce_gemini_pattern(google_history, is_thinking)
        
        # 3. Final safety validation
        GoogleAdapter._validate_final_pattern(google_history)
        
        return google_history

    @staticmethod
    def _convert_messages_to_parts(history: List[Message], is_thinking: bool) -> List[Dict[str, Any]]:
        google_history = []
        for msg in history:
            if msg.role == Role.SYSTEM:
                continue
            
            parts = []
            
            # Text content
            if msg.content and msg.content.strip():
                parts.append(genai_types.Part(
                    text=msg.content.strip(),
                    thought=is_thinking if msg.role == Role.ASSISTANT else False
                ))
            
            # Tool calls (Assistant)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    args = GoogleAdapter._prepare_args(tc.arguments)
                    parts.append(genai_types.Part(
                        function_call=genai_types.FunctionCall(name=tc.name, args=args),
                        thought=is_thinking
                    ))
            
            # Tool results (User)
            if msg.tool_results:
                for tr in msg.tool_results:
                    result_data = GoogleAdapter._prepare_result(tr.result)
                    parts.append(genai_types.Part(
                        function_response={"name": tr.name, "response": result_data}
                    ))

            if not parts:
                continue
            
            role = "model" if msg.role == Role.ASSISTANT else "user"
            google_history.append({"role": role, "parts": parts})
        
        return google_history

    @staticmethod
    def _enforce_gemini_pattern(history: List[Dict[str, Any]], is_thinking: bool) -> List[Dict[str, Any]]:
        if not history:
            return []

        # Step A: Merge consecutive same-role messages
        merged = []
        for msg in history:
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["parts"].extend(msg["parts"])
            else:
                merged.append(msg)

        # Step B: Handle "Orphaned" tool responses (Truncation safety)
        # If the first message is a User message containing function_responses, 
        # it MUST be preceded by a Model message with function_calls. 
        # If history was truncated, we drop these responses to prevent 400 errors.
        if merged and merged[0]["role"] == "user":
            merged[0]["parts"] = [
                p for p in merged[0]["parts"] 
                if getattr(p, 'function_response', None) is None
            ]
            if not merged[0]["parts"]:
                merged.pop(0)

        # Step C: Alternating Roles & Start/End Constraints
        if not merged: return []
        
        # Must start with User
        if merged[0]["role"] != "user":
            merged.insert(0, {"role": "user", "parts": [genai_types.Part(text="Continuing conversation...")]})

        fixed = [merged[0]]
        for i in range(1, len(merged)):
            prev = fixed[-1]
            curr = merged[i]
            
            if curr["role"] == prev["role"]:
                placeholder_role = "model" if prev["role"] == "user" else "user"
                placeholder_text = "[System: flow correction]"
                part = genai_types.Part(text=placeholder_text)
                if placeholder_role == "model" and is_thinking:
                    part.thought = True
                
                fixed.append({"role": placeholder_role, "parts": [part]})
            
            fixed.append(curr)

        # Step D: Cannot end with a function call (must wait for user response)
        if fixed and GoogleAdapter._has_function_calls(fixed[-1]["parts"]):
            logger.warning("Dangling function call detected at tail; removing to prevent API error.")
            fixed[-1]["parts"] = [p for p in fixed[-1]["parts"] if getattr(p, 'function_call', None) is None]
            if not fixed[-1]["parts"]:
                fixed.pop()

        return fixed

    @staticmethod
    def _has_function_calls(parts: List[Any]) -> bool:
        return any(getattr(p, "function_call", None) is not None for p in parts)

    @staticmethod
    def _validate_final_pattern(history: List[Dict[str, Any]]) -> None:
        if not history: return
        if history[0]["role"] != "user":
            raise ConversationPatternError("Must start with user")
        for i in range(len(history) - 1):
            if history[i]["role"] == history[i+1]["role"]:
                raise ConversationPatternError(f"Consecutive {history[i]['role']} at {i}")
        if GoogleAdapter._has_function_calls(history[-1]["parts"]):
            raise ConversationPatternError("Cannot end with function_call")

    @staticmethod
    def _prepare_args(arguments: Any) -> Dict[str, Any]:
        if isinstance(arguments, dict): return arguments
        try:
            parsed = json.loads(arguments)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except:
            return {"raw_input": str(arguments)}

    @staticmethod
    def _prepare_result(result: Any) -> Dict[str, Any]:
        if isinstance(result, dict): return result
        return {"result": result}

    @staticmethod
    def convert_response(response: Any, model_id: str) -> AgentResponse:
        is_thinking = GoogleAdapter.is_thinking_model(model_id)
        content_parts, tool_calls = [], []
        
        if not response.candidates:
            return AgentResponse(content="Error: No response candidates")
        
        candidate = response.candidates[0]
        if hasattr(candidate, 'finish_reason') and 'SAFETY' in str(candidate.finish_reason):
            return AgentResponse(content="⚠️ Blocked by safety filters.")

        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                # Log/Process thoughts but don't return as final content
                if is_thinking and getattr(part, 'thought', False):
                    continue
                if hasattr(part, 'text') and part.text:
                    content_parts.append(part.text)
                if hasattr(part, 'function_call') and part.function_call:
                    fc = part.function_call
                    tool_calls.append(ToolCall(id=fc.name, name=fc.name, arguments=dict(fc.args or {})))

        usage = None
        if hasattr(response, 'usage_metadata'):
            um = response.usage_metadata
            usage = UsageMetadata(
                input_tokens=getattr(um, 'prompt_token_count', 0),
                output_tokens=getattr(um, 'candidates_token_count', 0),
                total_tokens=getattr(um, 'total_token_count', 0)
            )

        return AgentResponse(
            content="".join(content_parts).strip() or None,
            tool_calls=tool_calls,
            usage=usage
        )
    
    @staticmethod
    def convert_stream_chunk(chunk: Any, model_id: str) -> Optional[StreamChunk]:
        """Convert stream chunk - filters thoughts for thinking models."""
        is_thinking = GoogleAdapter.is_thinking_model(model_id)
        
        if not chunk.candidates or not chunk.candidates[0].content:
            return None
        
        parts = chunk.candidates[0].content.parts
        if not parts:
            return None
        
        stream_chunk = StreamChunk()
        
        for part in parts:
            # Skip thought parts
            if is_thinking and hasattr(part, 'thought') and part.thought:
                continue
            
            # Extract text delta
            if hasattr(part, 'text') and part.text:
                stream_chunk.content = part.text
            
            # Extract function call
            if hasattr(part, 'function_call') and part.function_call:
                fc = part.function_call
                stream_chunk.tool_call = ToolCall(
                    id=fc.name,
                    name=fc.name,
                    arguments=dict(fc.args) if fc.args else {}
                )
        
        return stream_chunk if (stream_chunk.content or stream_chunk.tool_call) else None