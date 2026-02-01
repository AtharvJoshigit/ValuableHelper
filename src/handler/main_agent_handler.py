# file: main_agent.py

from typing import Dict, Any, List, Optional
import json
from pathlib import Path
from dataclasses import dataclass
from src.client.universal_ai_client import UniversalAIClient
# from agent_handler import AgentHandler, AgentToolResult
from src.handler.agent_handler import AgentHandler

@dataclass
class MainAgentConfig:
    provider: str
    model: str
    api_key: Optional[str] = None
    system_prompt_file: str = "whoami.md"
    skills_prompt_file: str = "whatcanido.md"
    max_iterations: int = 10


class MainAgent:
    def __init__(self, config: MainAgentConfig, agent_handler: AgentHandler):
        self.config = config
        self.client = UniversalAIClient(
            provider=config.provider,
            model=config.model,
            api_key=config.api_key
        )
        self.agent_handler = agent_handler
        self.conversation_history: List[Dict[str, Any]] = []
        self.system_prompt = self._load_system_prompt()
        self.read_skills_prompt = self._load_skills_prompt()
        
        if self.system_prompt:
            self.conversation_history.append({
                "role": "system",
                "content": self.system_prompt
            })
    
    def _load_system_prompt(self) -> Optional[str]:
        try:
            prompt_path = Path(self.config.system_prompt_file)
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            print(f"Warning: Could not load system prompt from {self.config.system_prompt_file}: {e}")
        return None
    
    def _load_skills_prompt(self) -> Optional[str]:
        try:
            prompt_path = Path(self.config.skills_prompt_file)
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            print(f"Warning: Could not load system prompt from {self.config.system_prompt_file}: {e}")
        return None
    
    def chat(self, user_message: str) -> Dict[str, Any]:
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        iteration = 0
        final_response = None
        agent_calls = []
        
        while iteration < self.config.max_iterations:
            iteration += 1
            
            try:
                if self.config.provider == "openai" or self.config.provider == "groq":
                    response = self._handle_openai_chat(agent_calls)
                    if response.get("finished"):
                        final_response = response.get("response")
                        agent_calls = response.get("agent_calls", [])
                        break
                    agent_calls = response.get("agent_calls", [])
                
                elif self.config.provider == "anthropic":
                    response = self._handle_anthropic_chat(agent_calls)
                    if response.get("finished"):
                        final_response = response.get("response")
                        agent_calls = response.get("agent_calls", [])
                        break
                    agent_calls = response.get("agent_calls", [])
                
                elif self.config.provider == "google":
                    response = self._handle_google_chat(agent_calls)
                    if response.get("finished"):
                        final_response = response.get("response")
                        agent_calls = response.get("agent_calls", [])
                        break
                    agent_calls = response.get("agent_calls", [])
                
                else:
                    return {
                        "status": "error",
                        "error": f"Unsupported provider: {self.config.provider}"
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
            "agent_calls": len(agent_calls),
            "iterations": iteration,
            "details": agent_calls
        }
    
    def _handle_openai_chat(self, previous_agent_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        tools_schema = self.agent_handler.get_tools_schema()
        
        response = self.client.client.chat.completions.create(
            model=self.client.model,
            messages=self.conversation_history,
            tools=tools_schema,
            tool_choice="auto"
        )
        
        assistant_message = response.choices[0].message
        
        if assistant_message.content:
            final_response = assistant_message.content
        else:
            final_response = None
        
        if not assistant_message.tool_calls:
            if final_response:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": final_response
                })
            return {
                "finished": True,
                "response": final_response,
                "agent_calls": previous_agent_calls
            }
        
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
        
        agent_calls = previous_agent_calls.copy()
        
        for tool_call in assistant_message.tool_calls:
            agent_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            result = self.agent_handler.execute_agent(agent_name, arguments)
            
            agent_calls.append({
                "agent": agent_name,
                "arguments": arguments,
                "result": result.result,
                "status": result.status
            })
            
            self.conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps({
                    "status": result.status,
                    "result": result.result,
                    "error": result.error
                })
            })
        
        return {
            "finished": False,
            "agent_calls": agent_calls
        }
    
    def _handle_anthropic_chat(self, previous_agent_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        tools_schema = self.agent_handler.get_tools_schema()
        
        formatted_tools = []
        for tool in tools_schema:
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
            return {
                "finished": True,
                "response": final_response,
                "agent_calls": previous_agent_calls
            }
        
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
            
            agent_calls = previous_agent_calls.copy()
            tool_results_content = []
            
            for tool_use in tool_uses:
                agent_name = tool_use.name
                arguments = tool_use.input
                
                result = self.agent_handler.execute_agent(agent_name, arguments)
                
                agent_calls.append({
                    "agent": agent_name,
                    "arguments": arguments,
                    "result": result.result,
                    "status": result.status
                })
                
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps({
                        "status": result.status,
                        "result": result.result,
                        "error": result.error
                    })
                })
            
            self.conversation_history.append({
                "role": "user",
                "content": tool_results_content
            })
            
            return {
                "finished": False,
                "agent_calls": agent_calls
            }
        
        return {
            "finished": True,
            "response": None,
            "agent_calls": previous_agent_calls
        }
    
    def _handle_google_chat(self, previous_agent_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        from google import genai
        from google.genai import types
        
        tools_schema = self.agent_handler.get_tools_schema()
        
        formatted_tools = []
        for tool in tools_schema:
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
        
        messages = [msg for msg in self.conversation_history if msg["role"] != "system"]
        system_instruction = next((msg["content"] for msg in self.conversation_history if msg["role"] == "system"), None)
        
        client = genai.Client(api_key=self.client.api_key)
        
        contents = []
        for msg in messages:
            if msg["role"] == "user":
                if isinstance(msg["content"], str):
                    contents.append(
                        types.Content(
                            role="user",
                            parts=[types.Part(text=msg["content"])]
                        )
                    )
                elif isinstance(msg["content"], list):
                    parts = []
                    for item in msg["content"]:
                        if isinstance(item, dict) and item.get("type") == "function_response":
                            parts.append(
                                types.Part(
                                    function_response=types.FunctionResponse(
                                        name=item["name"],
                                        response=item["response"]
                                    )
                                )
                            )
                        else:
                            parts.append(types.Part(text=str(item)))
                    contents.append(types.Content(role="user", parts=parts))
            
            elif msg["role"] == "assistant":
                if isinstance(msg["content"], str):
                    contents.append(
                        types.Content(
                            role="model",
                            parts=[types.Part(text=msg["content"])]
                        )
                    )
                elif isinstance(msg["content"], list):
                    parts = []
                    for item in msg["content"]:
                        if isinstance(item, dict) and item.get("type") == "function_call":
                            parts.append(
                                types.Part(
                                    function_call=types.FunctionCall(
                                        name=item["name"],
                                        args=item["args"]
                                    )
                                )
                            )
                        elif isinstance(item, dict) and item.get("type") == "text":
                            parts.append(types.Part(text=item["text"]))
                        else:
                            parts.append(types.Part(text=str(item)))
                    contents.append(types.Content(role="model", parts=parts))
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=formatted_tools
        )
        
        response = client.models.generate_content(
            model=self.client.model,
            contents=contents,
            config=config
        )
        
        if not response.candidates:
            return {
                "finished": True,
                "response": None,
                "agent_calls": previous_agent_calls
            }
        
        candidate = response.candidates[0]
        
        if candidate.content.parts:
            has_function_calls = False
            assistant_content = []
            text_parts = []
            agent_calls = previous_agent_calls.copy()
            
            for part in candidate.content.parts:
                if part.function_call:
                    has_function_calls = True
                    function_call = part.function_call
                    
                    assistant_content.append({
                        "type": "function_call",
                        "name": function_call.name,
                        "args": dict(function_call.args)
                    })
                    
                    result = self.agent_handler.execute_agent(
                        function_call.name,
                        dict(function_call.args)
                    )
                    
                    agent_calls.append({
                        "agent": function_call.name,
                        "arguments": dict(function_call.args),
                        "result": result.result,
                        "status": result.status
                    })
                
                elif part.text:
                    text_parts.append(part.text)
                    assistant_content.append({
                        "type": "text",
                        "text": part.text
                    })
            
            final_response = "".join(text_parts) if text_parts else None
            
            if has_function_calls:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_content
                })
                
                function_responses = []
                for content_item in assistant_content:
                    if content_item.get("type") == "function_call":
                        matching_result = next(
                            (ac for ac in agent_calls if ac["agent"] == content_item["name"]),
                            None
                        )
                        if matching_result:
                            function_responses.append({
                                "type": "function_response",
                                "name": content_item["name"],
                                "response": {
                                    "status": matching_result["status"],
                                    "result": matching_result["result"]
                                }
                            })
                
                self.conversation_history.append({
                    "role": "user",
                    "content": function_responses
                })
                
                return {
                    "finished": False,
                    "agent_calls": agent_calls
                }
            else:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": final_response
                })
                return {
                    "finished": True,
                    "response": final_response,
                    "agent_calls": agent_calls
                }
        
        return {
            "finished": True,
            "response": None,
            "agent_calls": previous_agent_calls
        }
    
    def reset_conversation(self):
        self.conversation_history = []
        if self.system_prompt:
            self.conversation_history.append({
                "role": "system",
                "content": self.system_prompt
            })
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        return self.conversation_history.copy()
    
    def save_conversation(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.conversation_history, f, indent=2)
    
    def load_conversation(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            self.conversation_history = json.load(f)


def create_main_agent(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
    system_prompt_file: str = "valuableHelper\whatMakesMe\whoami.md",
    skills_prompt_File : str = "valuableHelper\whatMakesMe\whatcanido.md",
    max_iterations: int = 10
) -> MainAgent:
    from src.handler.agent_handler import create_agent_handler
    
    config = MainAgentConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        system_prompt_file=system_prompt_file,
        skills_prompt_file=skills_prompt_File,
        max_iterations=max_iterations
    )
    
    agent_handler = create_agent_handler()
    
    return MainAgent(config, agent_handler)