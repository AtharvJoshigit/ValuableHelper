"""
Main Agent - Complete Implementation with Google Support

This version properly integrates:
1. OpenAI SDK for OpenAI, Groq, and compatible providers
2. Native Google SDK for Google Gemini (with thought signature support)
3. Parallel agent/tool execution
4. Clean error handling
"""

from logging import Logger
from typing import Dict, Any, List, Optional
import json
from pathlib import Path
from dataclasses import dataclass
from src.main_agent.agent_tool_handler import AgentToolHandler, ExecutionResult


@dataclass
class MainAgentConfig:
    provider: str
    model: str
    api_key: Optional[str] = None
    system_prompt_file: str = "whoami.md"
    skills_prompt_file: str = "whatcanido.md"
    max_iterations: int = 10
    enable_parallel: bool = True


logger = Logger("MainAgentLogger")


class MainAgent:
    """
    Main orchestrator agent with support for all providers.
    
    Providers:
    - openai: Uses OpenAI SDK
    - groq: Uses OpenAI SDK  (OpenAI-compatible)
    - google: Uses Google native SDK (proper thought signature handling)
    - anthropic: Uses Anthropic SDK
    """
    
    def __init__(self, config: MainAgentConfig, handler: AgentToolHandler):
        self.config = config
        self.status_message = None
        self.handler = handler
        self.conversation_history: List[Dict[str, Any]] = []
        
        # Initialize provider-specific client
        self._init_client()
        
        # Load prompts
        self.system_prompt = self._load_system_prompt()
        self.skills_prompt = self._load_skills_prompt()
        
        # Initialize conversation with system prompt
        if self.system_prompt:
            self.conversation_history.append({
                "role": "system",
                "content": self.system_prompt
            })
    
    def _init_client(self):
        """Initialize the appropriate client based on provider."""
        
        if self.config.provider in ["openai", "groq"]:
            # Use OpenAI SDK
            from openai import OpenAI
            
            if self.config.provider == "groq":
                self.client = OpenAI(
                    api_key=self.config.api_key,
                    base_url="https://api.groq.com/openai/v1"
                )
            else:
                self.client = OpenAI(api_key=self.config.api_key)
        
        elif self.config.provider == "anthropic":
            # Use Anthropic SDK
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.config.api_key)
        
        elif self.config.provider == "google":
            # For Google, we don't initialize here
            # We'll use the google_handler_final module directly
            self.client = None
        
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")
    
    def _load_system_prompt(self) -> Optional[str]:
        """Load system prompt from file."""
        try:
            prompt_path = Path.cwd() / "me" / "whoami.md"
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            print(f"⚠️  Could not load system prompt: {e}")
        return None
    
    def _load_skills_prompt(self) -> Optional[str]:
        """Load skills prompt from file."""
        try:
            prompt_path = Path.cwd() / "whatMakesMe" / "whatcanido.md"
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            print(f"⚠️  Could not load skills prompt: {e}")
        return None
    
    def chat(
        self,
        user_message: str,
        enable_parallel: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Main chat method.
        
        Args:
            user_message: User's message
            enable_parallel: Override parallel execution setting
            
        Returns:
            Dict with status, response, and execution details
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Use config default if not specified
        if enable_parallel is None:
            enable_parallel = self.config.enable_parallel
        
        iteration = 0
        final_response = None
        all_executions: List[ExecutionResult] = []
        
        logger.info('=' * 60)
        logger.info('MAIN AGENT CALL START')
        logger.info('=' * 60)
        
        while iteration < self.config.max_iterations:
            iteration += 1
            logger.info(f"Iteration {iteration}/{self.config.max_iterations}")
            
            try:
                # Provider-specific handling
                if self.config.provider == "google":
                    # Use Google native handler
                    response = self._handle_google(all_executions, enable_parallel)
                
                elif self.config.provider == "anthropic":
                    # Use Anthropic handler
                    response = self._handle_anthropic(all_executions, enable_parallel)
                
                else:
                    # Use OpenAI SDK (works for OpenAI, Groq, etc.)
                    response = self._handle_openai_style(all_executions, enable_parallel)
                
                if response.get("finished"):
                    final_response = response.get("response")
                    all_executions = response.get("executions", [])
                    logger.info("✅ Conversation finished")
                    break
                
                all_executions = response.get("executions", [])
            
            except Exception as e:
                logger.error(f"❌ Error in iteration {iteration}: {e}")
                import traceback
                traceback.print_exc()
                
                return {
                    "status": "error",
                    "error": str(e),
                    "iteration": iteration,
                    "executions": [e.to_dict() for e in all_executions]
                }
        
        logger.info('=' * 60)
        logger.info(f'MAIN AGENT CALL END ({iteration} iterations)')
        logger.info('=' * 60)
        
        return {
            "status": "success",
            "response": final_response,
            "total_executions": len(all_executions),
            "iterations": iteration,
            "executions": [e.to_dict() for e in all_executions]
        }
    
    def _handle_openai_style(
        self,
        previous_executions: List[ExecutionResult],
        enable_parallel: bool
    ) -> Dict[str, Any]:
        """
        Handler for OpenAI SDK (works for OpenAI, Groq, compatible APIs).
        """
        # Get tools schema
        tools_schema = self.handler.get_tools_schema()
        
        # Make API call
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=self.conversation_history,
            tools=tools_schema,
            tool_choice="auto"
        )
        
        assistant_message = response.choices[0].message
        final_response = assistant_message.content if assistant_message.content else None
        
        # Check if there are tool calls
        if not assistant_message.tool_calls:
            # No tool calls - conversation finished
            if final_response:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": final_response
                })
            
            return {
                "finished": True,
                "response": final_response,
                "executions": previous_executions
            }
        
        # Add assistant message with tool calls to history
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
        
        # Prepare execution calls
        execution_calls = []
        for tool_call in assistant_message.tool_calls:
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}
            
            execution_calls.append({
                "name": tool_call.function.name,
                "arguments": arguments,
                "tool_call_id": tool_call.id
            })
        
        # Execute agents/tools
        executions = self.handler.execute_multiple(
            execution_calls,
            parallel=enable_parallel
        )
        
        # Update status message if available
        if self.status_message:
            for exec_result in executions:
                status_text = f"✅ {exec_result.name}" if exec_result.status == "success" else f"❌ {exec_result.name}"
                self.status_message.edit_text(status_text)
        
        # Add tool results to conversation history
        for i, tool_call in enumerate(assistant_message.tool_calls):
            exec_result = executions[i] if i < len(executions) else None
            
            if exec_result:
                result_content = {
                    "status": exec_result.status,
                    "result": exec_result.result
                }
                
                if exec_result.error:
                    result_content["error"] = exec_result.error
                
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result_content)
                })
        
        # Combine with previous executions
        all_executions = previous_executions + executions
        
        return {
            "finished": False,
            "executions": all_executions
        }
    
    def _handle_google(
        self,
        previous_executions: List[ExecutionResult],
        enable_parallel: bool
    ) -> Dict[str, Any]:
        """
        Handler for Google Gemini (native SDK with thought signature support).
        """
        from main_agent.provider.google_handler import handle_google_chat_unified, debug_conversation_history
        
        debug_conversation_history(self.conversation_history)
        return handle_google_chat_unified(
            client_api_key=self.config.api_key,
            model=self.config.model,
            conversation_history=self.conversation_history,
            tools_schema=self.handler.get_tools_schema(),
            handler=self.handler,
            previous_executions=previous_executions,
            enable_parallel=enable_parallel
        )
    
    def _handle_anthropic(
        self,
        previous_executions: List[ExecutionResult],
        enable_parallel: bool
    ) -> Dict[str, Any]:
        """
        Handler for Anthropic Claude.
        """
        # Format tools for Anthropic
        formatted_tools = []
        for tool in self.handler.get_tools_schema():
            formatted_tools.append({
                "name": tool["function"]["name"],
                "description": tool["function"]["description"],
                "input_schema": tool["function"]["parameters"]
            })
        
        # Get messages and system prompt
        messages = [msg for msg in self.conversation_history if msg["role"] != "system"]
        system = next((msg["content"] for msg in self.conversation_history if msg["role"] == "system"), None)
        
        # Make API call
        response = self.client.messages.create(
            model=self.config.model,
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
                "executions": previous_executions
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
            execution_calls = []
            for tool_use in tool_uses:
                execution_calls.append({
                    "name": tool_use.name,
                    "arguments": tool_use.input
                })
            
            executions = self.handler.execute_multiple(
                execution_calls,
                parallel=enable_parallel
            )
            
            # Add tool results
            tool_results_content = []
            for i, tool_use in enumerate(tool_uses):
                exec_result = executions[i]
                
                result_data = {
                    "status": exec_result.status,
                    "result": exec_result.result
                }
                
                if exec_result.error:
                    result_data["error"] = exec_result.error
                
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result_data)
                })
            
            self.conversation_history.append({
                "role": "user",
                "content": tool_results_content
            })
            
            all_executions = previous_executions + executions
            
            return {
                "finished": False,
                "executions": all_executions
            }
        
        return {
            "finished": True,
            "response": None,
            "executions": previous_executions
        }
    
    def reset_conversation(self):
        """Reset conversation history."""
        self.conversation_history = []
        if self.system_prompt:
            self.conversation_history.append({
                "role": "system",
                "content": self.system_prompt
            })
        logger.info("✅ Conversation reset")
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get conversation history."""
        return self.conversation_history.copy()
    
    def save_conversation(self, filepath: str):
        """Save conversation to file."""
        # Note: Can't save raw Content objects, so convert to strings
        saveable_history = []
        for msg in self.conversation_history:
            saved_msg = msg.copy()
            # Convert Content objects to strings for saving
            if hasattr(saved_msg.get("content"), "__class__") and "Content" in saved_msg["content"].__class__.__name__:
                saved_msg["content"] = "[Google Content object - not serializable]"
            saveable_history.append(saved_msg)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(saveable_history, f, indent=2)
        logger.info(f"✅ Conversation saved to {filepath}")
    
    def load_conversation(self, filepath: str):
        """Load conversation from file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            self.conversation_history = json.load(f)
        logger.info(f"✅ Conversation loaded from {filepath}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "provider": self.config.provider,
            "model": self.config.model,
            "conversation_length": len(self.conversation_history),
            "parallel_enabled": self.config.enable_parallel,
            "handler_stats": self.handler.get_stats()
        }


def create_main_agent(
    provider: str = "google",
    model: str = "gemini-2.0-flash-exp",
    api_key: Optional[str] = None,
    max_iterations: int = 20,
    enable_parallel: bool = True
) -> MainAgent:
    """
    Create a main agent with recommended settings.
    
    Args:
        provider: AI provider (openai, google, anthropic, groq)
        model: Model name
        api_key: API key (optional, reads from env)
        max_iterations: Max conversation iterations
        enable_parallel: Enable parallel agent/tool execution
        
    Returns:
        Configured MainAgent
    """
    from main_agent.agent_setup import setup_all_agents_and_tools
    
    config = MainAgentConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        max_iterations=max_iterations,
        enable_parallel=enable_parallel
    )
    
    # Setup handler with all agents and tools
    handler = setup_all_agents_and_tools(
        filesystem_provider=provider,
        filesystem_model=model
    )
    
    return MainAgent(config, handler)