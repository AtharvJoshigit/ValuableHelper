import json
from typing import Dict, Any, List, Optional, Callable
from src.client.universal_ai_client import UniversalAIClient
# from src.agent.file_sy    tools.file_tools_executor import FILESYSTEM_TOOLS_SCHEMA, FileSystemToolExecutor
from src.agents.file_system_agent.tools.file_tools_executor import FILESYSTEM_TOOLS_SCHEMA, FileSystemToolExecutor


class LLMFileSystemAgent:
    def __init__(
        self,
        provider: str,
        model: str,
        filesystem_functions: Dict[str, Callable],
        api_key: Optional[str] = None
    ):
        self.client = UniversalAIClient(provider=provider, model=model, api_key=api_key)
        self.executor = FileSystemToolExecutor(filesystem_functions)
        self.conversation_history = []
    
    def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        max_iterations: int = 10
    ) -> Dict[str, Any]:
        if not self.conversation_history and system_prompt:
            self.conversation_history.append({
                "role": "system",
                "content": system_prompt
            })
        
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        system_prompt = system_prompt or "You are a helpful assistant that can perform file system operations using the provided tools."
        original_message = message
        iteration = 0
        final_response = None
        tool_results = []
        
        while iteration < max_iterations:
            iteration += 1
            print(f"🔄 Iteration {iteration}...")
            try:
                if self.client.provider == "openai" or self.client.provider == "groq":
                    response = self.client.client.chat.completions.create(
                        model=self.client.model,
                        messages=self.conversation_history,
                        tools=FILESYSTEM_TOOLS_SCHEMA,
                        tool_choice="auto"
                    )
                    
                    assistant_message = response.choices[0].message
                    
                    if assistant_message.content:
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": assistant_message.content
                        })
                        final_response = assistant_message.content
                    
                    if not assistant_message.tool_calls:
                        break
                    
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
                
                elif self.client.provider == "anthropic":
                    formatted_tools = []
                    for tool in FILESYSTEM_TOOLS_SCHEMA:
                        formatted_tools.append({
                            "name": tool["function"]["name"],
                            "description": tool["function"]["description"],
                            "input_schema": tool["function"]["parameters"]
                        })
                    
                    messages = [msg for msg in self.conversation_history if msg["role"] != "system"]
                    system = next((msg["content"] for msg in self.conversation_history if msg["role"] == "system"), None)
                    
                    response = self.client.client.messages.create(
                        model=self.client.model,
                        max_tokens=4096,
                        system=system,
                        messages=messages,
                        tools=formatted_tools
                    )
                    
                    if response.stop_reason == "end_turn":
                        final_response = response.content[0].text if response.content else None
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": final_response
                        })
                        break
                    
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
                elif self.client.provider == "google":
                    formatted_tools = []
                    print("here I am - google tool calling")
                    for tool in FILESYSTEM_TOOLS_SCHEMA:
                        properties = {}
                        required = tool["function"]["parameters"].get("required", [])
                        
                        for prop_name, prop_details in tool["function"]["parameters"].get("properties", {}).items():
                            prop_schema = {
                                "type": prop_details["type"].upper(),
                                "description": prop_details.get("description", "")
                            }
                            # if "default" in prop_details:
                            #     prop_schema["default"] = prop_details["default"]
                            properties[prop_name] = prop_schema
                        
                        formatted_tools.append({
                            "name": tool["function"]["name"],
                            "description": tool["function"]["description"],
                            "parameters": {
                                "type": "OBJECT",
                                "properties": properties,
                                "required": required
                            }
                        })
                    
                    messages = [msg for msg in self.conversation_history if msg["role"] != "system"]
                    # system_instruction = next((msg["content"] for msg in self.conversation_history if msg["role"] == "system"), None)
                    # print(f'before model init with tools: {json.dumps(formatted_tools, indent=2)}')
                    model = self.client.client.GenerativeModel(
                        model_name=self.client.model,
                        system_instruction=system_prompt,
                        tools=[{"function_declarations": formatted_tools}]
                    )
                    print("Model initialized for Google AI tool calling.")
                    chat_history = []
                    for msg in messages[:-1]:
                        role = "user" if msg["role"] == "user" else "model"
                        parts = []
                        
                        # Standardize content to a list for unified processing
                        raw = msg.get("content") or msg.get("parts") or []
                        raw_content = raw_content = raw if isinstance(raw, list) else [raw]
                        
                        for item in raw_content:
                            if isinstance(item, str):
                                # WRAP STRINGS IN TEXT DICT (Required by API)
                                parts.append({"text": item})
                            
                            elif isinstance(item, dict):
                                item_type = item.get("type")
                                
                                if item_type == "function_response":
                                    parts.append({
                                        "function_response": {
                                            "name": item["name"],
                                            "response": item["response"]
                                        }
                                    })
                                elif item_type == "function_call":
                                    parts.append({
                                        "function_call": {
                                            "name": item["name"],
                                            "args": item["args"]
                                        }
                                    })
                                elif item_type == "text":
                                    parts.append({"text": item["text"]})
                                else:
                                    # Fallback for unknown dict types
                                    parts.append({"text": str(item)})

                        if parts:
                            chat_history.append({
                                "role": role,
                                "parts": parts
                            })

                    chat = model.start_chat(history=chat_history)
                    print(f'Messages : {json.dumps(messages, indent=2)}')
                    # print(f'I think failing here {messages[-1]["content"]}')
                    response = chat.send_message(original_message)
                    print(f"Received response from Google AI. {response}")
                    if not response.candidates:
                        return {
                            "status": "error",
                            "error": "No response candidates from Google AI"
                        }
                    
                    candidate = response.candidates[0]
                    
                    if candidate.content.parts:
                        has_function_calls = False
                        assistant_content = []
                        text_parts = []
                        
                        for part in candidate.content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                has_function_calls = True
                                function_call = part.function_call
                                
                                assistant_content.append({
                                    "type": "function_call",
                                    "name": function_call.name,
                                    "args": dict(function_call.args)
                                })
                                
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
                            
                            elif hasattr(part, 'text') and part.text:
                                text_parts.append(part.text)
                                assistant_content.append({
                                    "type": "text",
                                    "text": part.text
                                })
                        
                        if text_parts:
                            final_response = "".join(text_parts)
                        
                        if has_function_calls:
                            self.conversation_history.append({
                                "role": "assistant",
                                "content": assistant_content
                            })
                            
                            function_responses = []
                            for content_item in assistant_content:
                                if content_item.get("type") == "function_call":
                                    matching_result = next(
                                        (tr for tr in tool_results if tr["function"] == content_item["name"]),
                                        None
                                    )
                                    if matching_result:
                                        function_responses.append({
                                            "name": content_item["name"],
                                            "response": matching_result["result"]
                                        })
                            
                            self.conversation_history.append({
                                "role": "user",
                                "parts": function_responses
                            })
                        else:
                            self.conversation_history.append({
                                "role": "assistant",
                                "content": final_response
                            })
                            break
                
                else:
                    return {
                        "status": "error",
                        "error": f"Provider {self.client.provider} does not support tool calling"
                    }
            
            except Exception as e:
                return {
                    "status": "error",
                    "error": str(e),
                    "iteration": iteration
                }
        
        return {
            "status": "success",
            "response": final_response,
            "tool_calls": len(tool_results),
            "tool_results": tool_results,
            "iterations": iteration
        }
    
    def reset_conversation(self):
        self.conversation_history = []
