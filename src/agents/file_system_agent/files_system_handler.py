
from datetime import datetime
import json
from typing import Dict, Any, List, Optional, Callable
from src.client.universal_ai_client import UniversalAIClient
from src.agents.file_system_agent.tools.file_tools_executor import FILESYSTEM_TOOLS_SCHEMA, FileSystemToolExecutor
from src.agents.file_system_agent.prompts.file_system_prompt import system_prompt

def validate_tool_call(user_request: str, tool_called: str) -> tuple[bool, str]:
    """
    Validate that the agent called the expected tool based on user request.
    
    Returns:
        (is_valid, warning_message)
    """
    request_lower = user_request.lower()
    
    # Expected tool mappings
    expected_mappings = {
        "read": ["read_file"],
        "show": ["read_file"],  # "show contents" should use read_file
        "contents": ["read_file"],
        "what's in": ["read_file"],
        "list": ["list_directory"],
        "files in": ["list_directory"],
        "create": ["create_file", "create_directory"],
        "delete": ["delete_file", "delete_directory"],
        "move": ["move_file"],
        "copy": ["copy_file"],
    }
    
    for keyword, expected_tools in expected_mappings.items():
        if keyword in request_lower:
            if tool_called not in expected_tools:
                warning = f"User asked to '{keyword}' but agent called '{tool_called}' instead of {expected_tools}"
                return False, warning
    
    return True, ""

class LLMFileSystemAgent:
    def __init__(
        self,
        provider: str,
        model: str,
        filesystem_functions: Dict[str, Callable],
        api_key: Optional[str] = None,
        debug: bool = True  # Enable debug by default
    ):
        self.client = UniversalAIClient(provider=provider, model=model, api_key=api_key)
        self.executor = FileSystemToolExecutor(filesystem_functions, debug=debug)
        self.conversation_history = []
        self.debug = debug
    
    def _log(self, message: str, level: str = "INFO"):
        """Enhanced logging with timestamps."""
        if self.debug:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "SUCCESS": "✅"}.get(level, "📝")
            print(f"[{timestamp}] {emoji} [{level}] {message}")
    
    def chat(
        self,
        message: str,
        system_prompt: str = system_prompt,
        max_iterations: int = 10,
        force_tool: Optional[str] = None,
        preprocess: bool = True
    ) -> Dict[str, Any]:
        """
        Main chat method with tool calling support.
        
        Args:
            message: User message
            system_prompt: System prompt (uses improved default)
            max_iterations: Max number of iterations
            force_tool: Force agent to use specific tool (optional)
            preprocess: Whether to preprocess the message for clarity
        """
        self._log(f"User Request: {message}")
        print('I am here')
        if force_tool:
            self._log(f"Forcing tool: {force_tool}", level="WARNING")
            system_prompt = f"{system_prompt}\n\nCRITICAL OVERRIDE: You MUST use the {force_tool} function for this request. Use {force_tool} ONLY."
        
        # Initialize conversation with system prompt
        if not self.conversation_history and system_prompt:
            self.conversation_history.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Add user message
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        original_message = message
        iteration = 0
        final_response = None
        tool_results = []
        
        while iteration < max_iterations:
            iteration += 1
            self._log(f"Iteration {iteration}/{max_iterations}")
            
            try:
                if self.client.provider == "openai" or self.client.provider == "groq":
                    result = self._handle_openai_groq(tool_results)
                    
                elif self.client.provider == "anthropic":
                    result = self._handle_anthropic(tool_results)
                    
                elif self.client.provider == "google":
                    result = self._handle_google(system_prompt, original_message, tool_results)
                    
                else:
                    return {
                        "status": "error",
                        "error": f"Provider {self.client.provider} does not support tool calling"
                    }
                
                # Validate tool calls
                if result.get("tool_results"):
                    for tool_result in result["tool_results"]:
                        tool_name = tool_result.get("function")
                        is_valid, warning = validate_tool_call(original_message, tool_name)
                        
                        if not is_valid:
                            self._log(warning, level="WARNING")
                
                # Check if we're done
                if result.get("finished"):
                    final_response = result.get("response")
                    self._log("Conversation finished", level="SUCCESS")
                    break
                    
                # Update tool_results for next iteration
                if result.get("tool_results"):
                    tool_results = result["tool_results"]
            
            except Exception as e:
                import traceback
                self._log("Exception occurred", level="ERROR")
                self._log(traceback.format_exc(), level="ERROR")
                return {
                    "status": "error",
                    "error": str(e),
                    "iteration": iteration
                }
        
        # Log summary
        self._log(f"Completed in {iteration} iterations")
        self._log(f"Tool calls made: {len(tool_results)}")
        for i, tr in enumerate(tool_results, 1):
            self._log(f"  {i}. {tr['function']} -> {tr['result'].get('status')}")
        
        return {
            "status": "success",
            "response": final_response,
            "tool_calls": len(tool_results),
            "tool_results": tool_results,
            "iterations": iteration
        }
    
    def _handle_openai_groq(self, tool_results: List[Dict]) -> Dict[str, Any]:
        """Handle OpenAI and Groq providers."""
        
        response = self.client.client.chat.completions.create(
            model=self.client.model,
            messages=self.conversation_history,
            tools=FILESYSTEM_TOOLS_SCHEMA,
            tool_choice="auto"
        )
        
        assistant_message = response.choices[0].message
        
        # If there's content, add it to history
        if assistant_message.content:
            final_response = assistant_message.content
        else:
            final_response = None
        
        # If no tool calls, we're done
        if not assistant_message.tool_calls:
            if final_response:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": final_response
                })
            return {
                "finished": True,
                "response": final_response,
                "tool_results": tool_results
            }
        
        # Add assistant message with tool calls
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in assistant_message.tool_calls
            ]
        })
        
        # Execute tool calls
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            result = self.executor.execute_tool_call({
                "id": tool_call.id,
                "function": {
                    "name": function_name,
                    "arguments": function_args
                }
            })
            
            tool_results.append({
                "function": function_name,
                "arguments": function_args,
                "result": result
            })
            
            self.conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)
            })
        
        return {
            "finished": False,
            "tool_results": tool_results
        }
    
    def _handle_anthropic(self, tool_results: List[Dict]) -> Dict[str, Any]:
        """Handle Anthropic provider."""
        
        # Format tools for Anthropic
        formatted_tools = []
        for tool in FILESYSTEM_TOOLS_SCHEMA:
            formatted_tools.append({
                "name": tool["function"]["name"],
                "description": tool["function"]["description"],
                "input_schema": tool["function"]["parameters"]
            })
        
        # Get messages and system prompt
        messages = [msg for msg in self.conversation_history if msg["role"] != "system"]
        system = next((msg["content"] for msg in self.conversation_history if msg["role"] == "system"), None)
        
        response = self.client.client.messages.create(
            model=self.client.model,
            max_tokens=4096,
            system=system,
            messages=messages,
            tools=formatted_tools
        )
        
        # Check if done
        if response.stop_reason == "end_turn":
            final_response = response.content[0].text if response.content else None
            self.conversation_history.append({
                "role": "assistant",
                "content": final_response
            })
            return {
                "finished": True,
                "response": final_response,
                "tool_results": tool_results
            }
        
        # Handle tool use
        if response.stop_reason == "tool_use":
            assistant_content = []
            tool_uses = []
            
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })
                    tool_uses.append(block)
            
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_content
            })
            
            # Execute tools
            tool_results_content = []
            for tool_use in tool_uses:
                result = self.executor.execute_tool_call({
                    "id": tool_use.id,
                    "function": {
                        "name": tool_use.name,
                        "arguments": tool_use.input
                    }
                })
                
                tool_results.append({
                    "function": tool_use.name,
                    "arguments": tool_use.input,
                    "result": result
                })
                
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result)
                })
            
            self.conversation_history.append({
                "role": "user",
                "content": tool_results_content
            })
            
            return {
                "finished": False,
                "tool_results": tool_results
            }
        
        return {
            "finished": True,
            "response": None,
            "tool_results": tool_results
        }
    
    def _handle_google(
        self,
        system_prompt: str,
        original_message: str,
        tool_results: List[Dict]
    ) -> Dict[str, Any]:
        """
        SIMPLEST SOLUTION: Avoid the thought_signature issue entirely
        by not using structured function responses.
        """
        from google import genai
        from google.genai import types
        
        # Format tools (same as before)
        formatted_tools = []
        for tool in FILESYSTEM_TOOLS_SCHEMA:
            properties = {}
            required = tool["function"]["parameters"].get("required", [])
            
            for prop_name, prop_details in tool["function"]["parameters"].get("properties", {}).items():
                prop_type = prop_details["type"].upper()
                
                type_mapping = {
                    "STRING": types.Type.STRING,
                    "INTEGER": types.Type.INTEGER,
                    "NUMBER": types.Type.NUMBER,
                    "BOOLEAN": types.Type.BOOLEAN,
                    "ARRAY": types.Type.ARRAY,
                    "OBJECT": types.Type.OBJECT
                }
                
                if prop_type == "ARRAY":
                    item_type = prop_details.get("items", {}).get("type", "STRING").upper()
                    properties[prop_name] = types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(
                            type=type_mapping.get(item_type, types.Type.STRING)
                        ),
                        description=prop_details.get("description", "")
                    )
                else:
                    properties[prop_name] = types.Schema(
                        type=type_mapping.get(prop_type, types.Type.STRING),
                        description=prop_details.get("description", "")
                    )
            
            formatted_tools.append(
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=tool["function"]["name"],
                            description=tool["function"]["description"],
                            parameters=types.Schema(
                                type=types.Type.OBJECT,
                                properties=properties,
                                required=required
                            )
                        )
                    ]
                )
            )
        
        # SIMPLIFIED: Build contents differently
        messages = [msg for msg in self.conversation_history if msg["role"] != "system"]
        
        contents = []
        for msg in messages:
            parts = []
            
            if msg["role"] == "user":
                # SIMPLIFIED: Always convert to text
                if isinstance(msg["content"], str):
                    parts.append(types.Part(text=msg["content"]))
                elif isinstance(msg["content"], list):
                    # Convert list to text instead of structured parts
                    text_parts = []
                    for item in msg["content"]:
                        if isinstance(item, dict):
                            # Convert function responses to text
                            if item.get("type") == "function_response":
                                result_text = json.dumps(item["response"])
                                text_parts.append(f"Function {item['name']} result: {result_text}")
                            else:
                                text_parts.append(str(item))
                        else:
                            text_parts.append(str(item))
                    
                    if text_parts:
                        parts.append(types.Part(text="\n".join(text_parts)))
                else:
                    parts.append(types.Part(text=str(msg["content"])))
                
                if parts:
                    contents.append(types.Content(role="user", parts=parts))
            
            elif msg["role"] == "assistant":
                # SIMPLIFIED: Skip assistant messages with function calls
                # Only include text responses
                if isinstance(msg["content"], str):
                    parts.append(types.Part(text=msg["content"]))
                    contents.append(types.Content(role="model", parts=parts))
                # If it's a list with function calls, skip it entirely
        
        # Config
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=formatted_tools,
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode='AUTO')
            )
        )
        
        # Make API call
        response = self.client.client.models.generate_content(
            model=self.client.model,
            contents=contents,
            config=config
        )
        
        # Handle response
        if not response.candidates:
            return {
                "finished": True,
                "response": None,
                "tool_results": tool_results
            }
        
        candidate = response.candidates[0]
        
        if not candidate.content.parts:
            return {
                "finished": True,
                "response": None,
                "tool_results": tool_results
            }
        
        has_function_calls = False
        text_parts = []
        executed_functions = []
        
        for part in candidate.content.parts:
            if hasattr(part, 'function_call') and part.function_call:
                has_function_calls = True
                function_call = part.function_call
                
                print(f"📞 Calling function: {function_call.name}")
                
                # Execute the function
                result = self.executor.execute_tool_call({
                    "id": function_call.name,
                    "function": {
                        "name": function_call.name,
                        "arguments": dict(function_call.args)
                    }
                })
                
                tool_results.append({
                    "function": function_call.name,
                    "arguments": dict(function_call.args),
                    "result": result
                })
                
                executed_functions.append({
                    "name": function_call.name,
                    "result": result
                })
            
            elif hasattr(part, 'text') and part.text:
                text_parts.append(part.text)
        
        final_response = "".join(text_parts) if text_parts else None
        
        if has_function_calls:
            # SIMPLIFIED: Don't store structured function calls
            # Just send back the results as text
            
            results_text = "Tool execution results:\n"
            for func in executed_functions:
                result_json = json.dumps(func["result"])
                results_text += f"- {func['name']}: {result_json}\n"
            
            # Add as simple text message
            self.conversation_history.append({
                "role": "user",
                "content": results_text
            })
            
            print(f"✅ Executed {len(executed_functions)} functions, sending results back")
            
            return {
                "finished": False,
                "tool_results": tool_results
            }
        else:
            # No function calls, we're done
            self.conversation_history.append({
                "role": "assistant",
                "content": final_response
            })
            
            print(f'sub-agent: Final Response: {final_response}')
            
            return {
                "finished": True,
                "response": final_response,
                "tool_results": tool_results
            }
    
    def reset_conversation(self):
        """Reset conversation history."""
        self.conversation_history = []
        print("✓ Conversation history reset")