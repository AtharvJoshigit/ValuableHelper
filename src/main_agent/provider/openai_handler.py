# from logging import Logger
# from typing import Dict, Any, List
# import json
# from main_agent.agent_tool_handler import AgentToolHandler, ExecutionResult


# def handle_openai_unified(
#         previous_executions: List[ExecutionResult],
#         enable_parallel: bool
#     ) -> Dict[str, Any]:
#         """
#         Unified chat handler using OpenAI SDK for ALL providers.
        
#         This eliminates the need for separate handlers for each provider!
#         """
#         # Get tools schema
#         tools_schema = self.handler.get_tools_schema()
        
#         # Make API call using OpenAI SDK
#         # (This works for OpenAI, Groq, Google Gemini, and any OpenAI-compatible API)
#         response = self.client.client.chat.completions.create(
#             model=self.client.model,
#             messages=self.conversation_history,
#             tools=tools_schema,
#             tool_choice="auto"
#         )
        
#         assistant_message = response.choices[0].message
        
#         # Extract text response
#         final_response = assistant_message.content if assistant_message.content else None
        
#         # Check if there are tool calls
#         if not assistant_message.tool_calls:
#             # No tool calls - conversation finished
#             if final_response:
#                 self.conversation_history.append({
#                     "role": "assistant",
#                     "content": final_response
#                 })
            
#             return {
#                 "finished": True,
#                 "response": final_response,
#                 "executions": previous_executions
#             }
        
#         # Add assistant message with tool calls to history
#         self.conversation_history.append({
#             "role": "assistant",
#             "content": assistant_message.content,
#             "tool_calls": [
#                 {
#                     "id": tc.id,
#                     "type": "function",
#                     "function": {
#                         "name": tc.function.name,
#                         "arguments": tc.function.arguments
#                     }
#                 }
#                 for tc in assistant_message.tool_calls
#             ]
#         })
        
#         # Prepare execution calls
#         execution_calls = []
#         for tool_call in assistant_message.tool_calls:
#             try:
#                 arguments = json.loads(tool_call.function.arguments)
#             except json.JSONDecodeError:
#                 arguments = {}
            
#             execution_calls.append({
#                 "name": tool_call.function.name,
#                 "arguments": arguments,
#                 "tool_call_id": tool_call.id
#             })
        
#         # Execute agents/tools (parallel if enabled)
#         executions = self.handler.execute_multiple(
#             execution_calls,
#             parallel=enable_parallel
#         )
        
#         # Update status message if available
#         if self.status_message:
#             for exec_result in executions:
#                 status_text = f"✅ {exec_result.name}" if exec_result.status == "success" else f"❌ {exec_result.name}"
#                 self.status_message.edit_text(status_text)
        
#         # Add tool results to conversation history
#         for i, tool_call in enumerate(assistant_message.tool_calls):
#             exec_result = executions[i] if i < len(executions) else None
            
#             if exec_result:
#                 # Format the result for the conversation
#                 result_content = {
#                     "status": exec_result.status,
#                     "result": exec_result.result
#                 }
                
#                 if exec_result.error:
#                     result_content["error"] = exec_result.error
                
#                 self.conversation_history.append({
#                     "role": "tool",
#                     "tool_call_id": tool_call.id,
#                     "content": json.dumps(result_content)
#                 })
        
#         # Combine with previous executions
#         all_executions = previous_executions + executions
        
#         return {
#             "finished": False,
#             "executions": all_executions
#         }