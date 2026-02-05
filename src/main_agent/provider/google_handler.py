"""
ACTUAL FIX - The Content Object is Missing the Text Part!

PROBLEM IDENTIFIED:
From your debug output, position [2] shows:
  Content: <types.Content object with 1 parts>
    Part 0: function_call = filesystem_operations

MISSING: Part 0 should be TEXT (with thought), Part 1 should be function_call!

The Content object from Google's response DOES have both parts, but you're
not preserving it correctly OR Google isn't generating it with text.

FIX: ALWAYS ensure text part exists before function calls when storing.
"""

import uuid
import json
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from google import genai
from google.genai import types


@dataclass
class GoogleToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments)
            }
        }


@dataclass
class GoogleChatResponse:
    content: Optional[str]
    tool_calls: Optional[List[GoogleToolCall]]
    raw_content: Optional[types.Content]


class GoogleChatHandler:
    
    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model
    
    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto"
    ) -> GoogleChatResponse:
        
        system_instruction = None
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                user_messages.append(msg)
        
        contents = self._convert_messages_to_contents(user_messages)
        
        config_kwargs = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        
        if tools:
            config_kwargs["tools"] = self._convert_tools_to_google_format(tools)
        
        config = types.GenerateContentConfig(**config_kwargs)
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config
        )
        
        return self._convert_response_to_openai_style(response)
    
    def _convert_messages_to_contents(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[types.Content]:
        """Convert messages to Google Content objects."""
        contents: List[types.Content] = []
        
        for msg in messages:
            role = msg["role"]
            content = msg.get("content")
            
            # ✅ CRITICAL: Use raw Content if available
            if isinstance(content, types.Content):
                # ✅ ADDITIONAL FIX: Verify it has text before function calls
                # If it doesn't, we need to fix it
                fixed_content = self._ensure_text_before_function_calls(content)
                contents.append(fixed_content)
                continue
            
            parts: List[types.Part] = []
            
            # Handle assistant/model messages
            if role in ("assistant", "model"):
                tool_calls = msg.get("tool_calls", [])
                
                if not tool_calls:
                    # Simple text response
                    if isinstance(content, str) and content:
                        parts.append(types.Part(text=content))
                else:
                    # ✅ CRITICAL: ALWAYS add text before function calls
                    thought_text = content if isinstance(content, str) and content else "Processing request..."
                    parts.append(types.Part(text=thought_text))
                    
                    # Then add function calls
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            args = fn.get("arguments", "{}")
                            parts.append(
                                types.Part(
                                    function_call=types.FunctionCall(
                                        name=fn["name"],
                                        args=json.loads(args) if isinstance(args, str) else args
                                    )
                                )
                            )
                
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
                continue
            
            # Handle tool responses
            if role == "tool":
                try:
                    data = json.loads(content) if isinstance(content, str) else content
                except Exception:
                    data = {"result": content}
                
                function_name = msg.get("name") or msg.get("tool_call_id", "unknown")
                
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=function_name,
                                response=data
                            )
                        ]
                    )
                )
                continue
            
            # Handle user messages
            if role == "user":
                if isinstance(content, str) and content:
                    parts.append(types.Part(text=content))
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text" and item.get("text"):
                                parts.append(types.Part(text=item["text"]))
                
                if parts:
                    contents.append(types.Content(role="user", parts=parts))
        
        return contents
    
    def _ensure_text_before_function_calls(
        self,
        content: types.Content
    ) -> types.Content:
        """
        ✅ NEW FIX: Ensure Content has text part before any function calls.
        
        Google REQUIRES text before function calls for thought signatures.
        If the Content object doesn't have this, we fix it.
        """
        parts = list(content.parts)
        
        # Check if first part is a function call (missing text!)
        if parts and hasattr(parts[0], 'function_call') and parts[0].function_call:
            # Missing text part - add one!
            print("⚠️  Warning: Content missing text before function call - adding it")
            parts.insert(0, types.Part(text="Executing tool..."))
            return types.Content(role=content.role, parts=parts)
        
        return content
    
    def _convert_tools_to_google_format(
        self,
        tools: List[Dict[str, Any]]
    ) -> List[types.Tool]:
        """Convert OpenAI tools to Google format."""
        google_tools = []
        
        for tool in tools:
            if tool.get("type") != "function":
                continue
            
            fn = tool["function"]
            params = fn.get("parameters", {})
            required = params.get("required", [])
            properties = {}
            
            type_map = {
                "STRING": types.Type.STRING,
                "INTEGER": types.Type.INTEGER,
                "NUMBER": types.Type.NUMBER,
                "BOOLEAN": types.Type.BOOLEAN,
                "ARRAY": types.Type.ARRAY,
                "OBJECT": types.Type.OBJECT,
            }
            
            for name, spec in params.get("properties", {}).items():
                t = spec.get("type", "STRING").upper()
                
                if t == "ARRAY":
                    item_t = spec.get("items", {}).get("type", "STRING").upper()
                    properties[name] = types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=type_map.get(item_t, types.Type.STRING)),
                        description=spec.get("description", "")
                    )
                else:
                    properties[name] = types.Schema(
                        type=type_map.get(t, types.Type.STRING),
                        description=spec.get("description", "")
                    )
            
            google_tools.append(
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=fn["name"],
                            description=fn.get("description", ""),
                            parameters=types.Schema(
                                type=types.Type.OBJECT,
                                properties=properties,
                                required=required
                            )
                        )
                    ]
                )
            )
        
        return google_tools
    
    def _convert_response_to_openai_style(self, response) -> GoogleChatResponse:
        """
        Convert Google response to OpenAI style.
        
        ✅ CRITICAL FIX: If response has function calls but no text,
        we need to add text to the raw_content before storing it!
        """
        if not response.candidates:
            return GoogleChatResponse(None, None, None)
        
        candidate = response.candidates[0]
        raw_content = candidate.content
        
        text_chunks: List[str] = []
        tool_calls: List[GoogleToolCall] = []
        
        for part in candidate.content.parts:
            if hasattr(part, 'text') and part.text:
                text_chunks.append(part.text)
            
            if hasattr(part, 'function_call') and part.function_call:
                tool_calls.append(
                    GoogleToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name=part.function_call.name,
                        arguments=dict(part.function_call.args),
                    )
                )
        
        content_str = "".join(text_chunks) if text_chunks else None
        
        # ✅ CRITICAL FIX: If there are tool calls but no text, fix the Content object!
        if tool_calls and not text_chunks:
            print("⚠️  Warning: Response has function calls but no text - fixing Content object")
            raw_content = self._ensure_text_before_function_calls(raw_content)
            content_str = None  # OpenAI compat: no text when tool calls present
        elif tool_calls:
            content_str = None  # OpenAI compat: ignore text when tool calls present
        
        return GoogleChatResponse(
            content=content_str,
            tool_calls=tool_calls or None,
            raw_content=raw_content  # ← Fixed Content with text part
        )


def handle_google_chat_unified(
    client_api_key: str,
    model: str,
    conversation_history: List[Dict[str, Any]],
    tools_schema: List[Dict[str, Any]],
    handler,
    previous_executions: List,
    enable_parallel: bool
) -> Dict[str, Any]:
    """
    Complete fix for thought signature issues.
    """
    
    google = GoogleChatHandler(client_api_key, model)
    response = google.chat_completion(conversation_history, tools_schema)
    
    # No tool calls - finished
    if not response.tool_calls:
        if response.content:
            conversation_history.append({
                "role": "assistant",
                "content": response.content
            })
        return {
            "finished": True,
            "response": response.content,
            "executions": previous_executions
        }
    
    # ✅ Store raw Content (now guaranteed to have text before function calls)
    conversation_history.append({
        "role": "assistant",
        "content": response.raw_content,  # ← Fixed Content object
        "tool_calls": [tc.to_dict() for tc in response.tool_calls]
    })
    
    # Prepare execution calls
    calls = [
        {
            "name": tc.name,
            "arguments": tc.arguments,
            "tool_call_id": tc.id
        }
        for tc in response.tool_calls
    ]
    
    # Execute
    executions = handler.execute_multiple(calls, parallel=enable_parallel)
    
    # Add tool responses
    for tc, exec_result in zip(response.tool_calls, executions):
        payload = {
            "status": exec_result.status,
            "result": exec_result.result
        }
        if exec_result.error:
            payload["error"] = exec_result.error
        
        conversation_history.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "name": tc.name,
            "content": json.dumps(payload)
        })
    
    return {
        "finished": False,
        "executions": previous_executions + executions
    }


def debug_conversation_history(conversation_history: List[Dict[str, Any]]):
    """Debug helper."""
    print("\n" + "=" * 60)
    print("CONVERSATION HISTORY DEBUG")
    print("=" * 60)
    
    for i, msg in enumerate(conversation_history):
        role = msg.get("role")
        content = msg.get("content")
        
        print(f"\n[{i}] Role: {role}")
        
        if isinstance(content, types.Content):
            print(f"    Content: <types.Content object with {len(content.parts)} parts>")
            for j, part in enumerate(content.parts):
                if hasattr(part, 'text') and part.text:
                    print(f"      Part {j}: text = '{part.text[:50]}...'")
                if hasattr(part, 'function_call') and part.function_call:
                    print(f"      Part {j}: function_call = {part.function_call.name}")
                if hasattr(part, 'function_response') and part.function_response:
                    print(f"      Part {j}: function_response = {part.function_response.name}")
            
            # ✅ VALIDATION CHECK
            has_function_call = any(
                hasattr(p, 'function_call') and p.function_call
                for p in content.parts
            )
            has_text_before_fc = (
                len(content.parts) > 0 and
                hasattr(content.parts[0], 'text') and
                content.parts[0].text
            )
            
            if has_function_call and not has_text_before_fc:
                print("      ❌ ERROR: Function call without preceding text!")
            elif has_function_call and has_text_before_fc:
                print("      ✅ OK: Text before function call")
        
        elif isinstance(content, str):
            print(f"    Content: '{content[:100]}...'")
        
        if msg.get("tool_calls"):
            print(f"    Tool calls: {len(msg['tool_calls'])}")
    
    print("=" * 60 + "\n")
