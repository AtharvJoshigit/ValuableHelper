import json
from typing import Dict, Any, List, Optional


def handle_openai_chat(self, previous_agent_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
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