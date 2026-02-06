from typing import List, Dict, Any, Optional
from engine.core.types import (
    Message, 
    Role, 
    ToolCall, 
    AgentResponse, 
    UsageMetadata
)
from copy import deepcopy

from google.genai import types as genai_types

from engine.utils import utility

class GoogleAdapter:
    """
    Adapter to convert between Universal Framework types and Google Gemini types.
    """

    @staticmethod
    def convert_tools(tools_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert a list of tool definitions to Google FunctionDeclaration format.
        """
        google_functions = []
        for tool in tools_data:
            # Clean up the schema for Google
            parameters = deepcopy(tool.get("parameters", {}))
            fields_to_remove = ["title", "$schema", "additionalProperties", "$defs", "definitions"]
            for field in fields_to_remove:
                parameters.pop(field, None)
            
            func_decl = {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": parameters
            }
            google_functions.append(func_decl)
        return google_functions

    @staticmethod
    def convert_history(history: List[Message]) -> List[Dict[str, Any]]:
        """
        Convert framework Message history to Google Content objects (as dicts).
        """
        google_history = []
        
        for msg in history:
            parts = []
            
            # 1. Handle Text Content
            # Gemini doesn't like empty strings or None content if other parts are present, 
            # but usually text part should only be added if it has value.
            if msg.content:
                parts.append({"text": msg.content})

            # 2. Handle Tool Calls (Model -> User)
            if msg.tool_calls:
                for tc in msg.tool_calls:

                    func_call = genai_types.FunctionCall(
                        name=tc.name,
                        args=tc.arguments or {}
                    )
                    
                    # Add thought signature to the part
                    parts.append(genai_types.Part(
                        function_call=func_call,
                        thought=True  # Add thought flag to the part
                    ))

            # 3. Handle Tool Results (User -> Model)
            if msg.tool_results:
                for tr in msg.tool_results:
                    # Gemini expects the response to be wrapped in a dict
                    # and the 'name' must match the function name.
                    parts.append({
                        "function_response": {
                            "name": tr.name, 
                            "response": {"result": tr.result}
                        }
                    })
            
            # Determine Role
            role = "user"
            if msg.role == Role.ASSISTANT:
                role = "model"
            elif msg.role == Role.TOOL:
                # Function responses are provided by the "user" (the environment)
                role = "user" 
            elif msg.role == Role.SYSTEM:
                # System instructions are handled separately in some APIs, 
                # but Gemini often accepts them as 'system' role or converts them.
                # Here we map to 'system' and the provider handles it.
                role = "system"
            
            if parts:
                google_history.append({"role": utility.to_gemini_role(role), "parts": parts})

        return google_history

    @staticmethod
    def convert_response(response: Any) -> AgentResponse:
        """
        Convert Google GenerateContentResponse to AgentResponse.
        """
        content = None
        tool_calls = []
        
        if not response.candidates:
            return AgentResponse(content="Error: No candidates returned.")

        candidate = response.candidates[0]
        
        if candidate.content and candidate.content.parts:

            # has_thought = None

            for part in candidate.content.parts:

                 # Capture thought signatures
                # if hasattr(part, 'thought') and part.thought:
                #     has_thought = part.thought

                if part.text:
                    content = (content or "") + part.text
                
                if part.function_call:
                    # Convert args to dict safely
                    args = {}
                    if part.function_call.args:
                        args = dict(part.function_call.args)

                    tool_calls.append(ToolCall(
                        id=part.function_call.name, # Use function name as ID for Gemini
                        name=part.function_call.name,
                        arguments=args
                    ))
                 # Reset thought after capturing
                has_thought = False

        usage = None
        if response.usage_metadata:
            usage = UsageMetadata(
                input_tokens=response.usage_metadata.prompt_token_count or 0,
                output_tokens=response.usage_metadata.candidates_token_count or 0,
                total_tokens=response.usage_metadata.total_token_count or 0
            )

        return AgentResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage
        )
