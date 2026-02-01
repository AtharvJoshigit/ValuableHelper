"""
Universal AI Client - Using Official SDKs
Supports: OpenAI, Anthropic, Google, Groq with their official SDKs
Falls back to OpenAI SDK for compatible providers
"""

from typing import Optional, List, Dict, Any, Union, Literal
import os
from enum import Enum


class OutputFormat(Enum):
    """Output format options."""
    TEXT = "text"
    JSON_OBJECT = "json_object"
    JSON_SCHEMA = "json_schema"


class UniversalAIClient:
    """
    Universal client using official SDKs for each provider.
    Thread-safe and supports multiple simultaneous instances.
    """
    
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the universal AI client.
        
        Args:
            provider: Provider name (openai, anthropic, google, groq, etc.)
            model: Model name to use
            api_key: API key (if None, reads from {PROVIDER}_API_KEY env var)
            base_url: Custom base URL (optional)
            **kwargs: Additional provider-specific arguments
        """
        self.provider = provider.lower()
        self.model = model
        self.base_url = base_url
        self.kwargs = kwargs
        
        # Get API key dynamically: {PROVIDER}_API_KEY
        self.api_key = api_key or self._get_api_key()
        
        # Initialize the appropriate client
        self.client = self._init_client()
        
        # Conversation history (per instance)
        self.conversation_history: List[Dict[str, str]] = []
        
        print(f"✓ Initialized {self.provider} client with model: {self.model}")
    
    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment variable {PROVIDER}_API_KEY."""
        env_var = f"{self.provider.upper()}_API_KEY"
        api_key = os.getenv(env_var)
        
        if not api_key:
            print(f"⚠️  Warning: {env_var} not found in environment")
        
        return api_key
    
    def _init_client(self):
        """Initialize the appropriate SDK client based on provider."""
        
        if self.provider == "openai":
            return self._init_openai()
        
        elif self.provider == "anthropic":
            return self._init_anthropic()
        
        elif self.provider == "google":
            return self._init_google()
        
        elif self.provider == "groq":
            return self._init_groq()
        
        else:
            # Default: Use OpenAI SDK for OpenAI-compatible APIs
            print(f"ℹ️  Using OpenAI SDK for {self.provider} (OpenAI-compatible)")
            return self._init_openai()
    
    def _init_openai(self):
        """Initialize OpenAI SDK client."""
        try:
            from openai import OpenAI
            
            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            
            return OpenAI(**client_kwargs)
        
        except ImportError:
            raise ImportError(
                "OpenAI SDK not installed. Install with: pip install openai"
            )
    
    def _init_anthropic(self):
        """Initialize Anthropic SDK client."""
        try:
            from anthropic import Anthropic
            
            return Anthropic(api_key=self.api_key)
        
        except ImportError:
            raise ImportError(
                "Anthropic SDK not installed. Install with: pip install anthropic"
            )
    
    def _init_google(self):
        """Initialize Google Generative AI SDK client."""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key)
            
            # Return the genai module itself (it has the generate_content method)
            return genai
        
        except ImportError:
            raise ImportError(
                "Google Generative AI SDK not installed. Install with: pip install google-generativeai"
            )
    
    def _init_groq(self):
        """Initialize Groq SDK client (uses OpenAI SDK)."""
        try:
            from openai import OpenAI
            
            # Groq uses OpenAI-compatible API
            return OpenAI(
                api_key=self.api_key,
                base_url="https://api.groq.com/openai/v1"
            )
        
        except ImportError:
            raise ImportError(
                "OpenAI SDK not installed (needed for Groq). Install with: pip install openai"
            )
    
    def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        output_format: Optional[Union[OutputFormat, str]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        use_history: bool = False,
        **kwargs
    ) -> Union[str, Dict[str, Any], Any]:
        """
        Send a chat completion request.
        
        Args:
            message: User message
            system_prompt: System message for behavior control
            temperature: Randomness (0-2)
            max_tokens: Max response length
            output_format: Output format (text, json_object, json_schema)
            response_schema: JSON schema for structured output
            tools: List of tool definitions (for future use)
            stream: Whether to stream the response
            use_history: Whether to include conversation history
            **kwargs: Additional provider-specific arguments
            
        Returns:
            Model response
        """
        # Convert output_format to enum if string
        if isinstance(output_format, str):
            output_format = OutputFormat(output_format.lower())
        
        # Route to appropriate provider method
        if self.provider == "anthropic":
            return self._chat_anthropic(
                message, system_prompt, temperature, max_tokens,
                output_format, tools, stream, use_history, **kwargs
            )
        
        elif self.provider == "google":
            return self._chat_google(
                message, system_prompt, temperature, max_tokens,
                output_format, tools, stream, use_history, **kwargs
            )
        
        else:
            # OpenAI and OpenAI-compatible (Groq, custom, etc.)
            return self._chat_openai(
                message, system_prompt, temperature, max_tokens,
                output_format, response_schema, tools, stream, use_history, **kwargs
            )
    
    def _chat_openai(
        self,
        message: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        output_format: Optional[OutputFormat],
        response_schema: Optional[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        stream: bool,
        use_history: bool,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """Handle OpenAI SDK requests."""
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        if use_history:
            messages.extend(self.conversation_history)
        
        messages.append({"role": "user", "content": message})
        
        # Build request parameters
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        
        if max_tokens:
            params["max_tokens"] = max_tokens
        
        # Handle output format
        if output_format == OutputFormat.JSON_OBJECT:
            params["response_format"] = {"type": "json_object"}
        elif output_format == OutputFormat.JSON_SCHEMA and response_schema:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": response_schema
            }
        
        # Add tools if provided (for future use)
        if tools:
            params["tools"] = tools
        
        # Merge additional kwargs
        params.update(kwargs)
        
        try:
            response = self.client.chat.completions.create(**params)
            
            if stream:
                # Handle streaming
                full_response = ""
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        print(content, end="", flush=True)
                        full_response += content
                print()  # New line
                result = full_response
            else:
                result = response.choices[0].message.content
            
            # Update conversation history
            if use_history:
                self.conversation_history.append({"role": "user", "content": message})
                self.conversation_history.append({"role": "assistant", "content": result})
            
            # Parse JSON if needed
            if output_format in [OutputFormat.JSON_OBJECT, OutputFormat.JSON_SCHEMA]:
                import json
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    print("⚠️ Warning: Response is not valid JSON")
                    return result
            
            return result
        
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _chat_anthropic(
        self,
        message: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        output_format: Optional[OutputFormat],
        tools: Optional[List[Dict[str, Any]]],
        stream: bool,
        use_history: bool,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """Handle Anthropic SDK requests."""
        
        # Build messages
        messages = []
        if use_history:
            messages.extend(self.conversation_history)
        
        messages.append({"role": "user", "content": message})
        
        # Build request parameters
        params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or 1024,
            "temperature": temperature,
            "stream": stream,
        }
        
        if system_prompt:
            params["system"] = system_prompt
        
        # Add tools if provided (for future use)
        if tools:
            params["tools"] = tools
        
        # Merge additional kwargs
        params.update(kwargs)
        
        try:
            if stream:
                # Handle streaming
                full_response = ""
                with self.client.messages.stream(**params) as stream:
                    for text in stream.text_stream:
                        print(text, end="", flush=True)
                        full_response += text
                print()  # New line
                result = full_response
            else:
                response = self.client.messages.create(**params)
                result = response.content[0].text
            
            # Update conversation history
            if use_history:
                self.conversation_history.append({"role": "user", "content": message})
                self.conversation_history.append({"role": "assistant", "content": result})
            
            # Parse JSON if needed
            if output_format in [OutputFormat.JSON_OBJECT, OutputFormat.JSON_SCHEMA]:
                import json
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    print("⚠️ Warning: Response is not valid JSON")
                    return result
            
            return result
        
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _chat_google(
        self,
        message: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        output_format: Optional[OutputFormat],
        tools: Optional[List[Dict[str, Any]]],
        stream: bool,
        use_history: bool,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """Handle Google Generative AI SDK requests."""
        
        # Get the model
        model = self.client.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt
        )
        
        # Build generation config
        generation_config = {
            "temperature": temperature,
        }
        
        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens
        
        # Merge additional kwargs
        generation_config.update(kwargs)
        
        # Build contents
        contents = []
        if use_history:
            for msg in self.conversation_history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [msg["content"]]})
        
        contents.append({"role": "user", "parts": [message]})
        
        try:
            if stream:
                # Handle streaming
                full_response = ""
                response = model.generate_content(
                    contents,
                    generation_config=generation_config,
                    stream=True
                )
                for chunk in response:
                    if chunk.text:
                        print(chunk.text, end="", flush=True)
                        full_response += chunk.text
                print()  # New line
                result = full_response
            else:
                response = model.generate_content(
                    contents,
                    generation_config=generation_config
                )
                result = response.text
            
            # Update conversation history
            if use_history:
                self.conversation_history.append({"role": "user", "content": message})
                self.conversation_history.append({"role": "assistant", "content": result})
            
            # Parse JSON if needed
            if output_format in [OutputFormat.JSON_OBJECT, OutputFormat.JSON_SCHEMA]:
                import json
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    print("⚠️ Warning: Response is not valid JSON")
                    return result
            
            return result
        
        except Exception as e:
            return f"Error: {str(e)}"
    
    def clear_history(self):
        """Clear conversation history for this instance."""
        self.conversation_history = []
        print("✓ Conversation history cleared")
    
    def save_history(self, filepath: str):
        """Save conversation history to file."""
        import json
        with open(filepath, 'w') as f:
            json.dump(self.conversation_history, f, indent=2)
        print(f"✓ History saved to: {filepath}")
    
    def load_history(self, filepath: str):
        """Load conversation history from file."""
        import json
        with open(filepath, 'r') as f:
            self.conversation_history = json.load(f)
        print(f"✓ History loaded from: {filepath}")
    
    def set_model(self, model: str):
        """Change the model for this instance."""
        self.model = model
        print(f"✓ Model changed to: {self.model}")


# Example usage demonstrating multiple simultaneous instances
# if __name__ == "__main__":
#     print("=" * 70)
#     print("Universal AI Client - Multi-Instance Demo")
#     print("=" * 70)
    
#     # Create multiple clients simultaneously
#     clients = {
#         "openai": UniversalAIClient(provider="openai", model="gpt-4o-mini"),
#         "groq": UniversalAIClient(provider="groq", model="llama-3.3-70b-versatile"),
#         # "anthropic": UniversalAIClient(provider="anthropic", model="claude-3-haiku-20240307"),
#         # "google": UniversalAIClient(provider="google", model="gemini-1.5-flash-latest"),
#     }
    
#     question = "What is artificial intelligence in one sentence?"
    
#     print(f"\nQuestion: {question}\n")
    
#     # All clients can be used simultaneously
#     for name, client in clients.items():
#         print(f"{name.upper()}:")
#         response = client.chat(question)
#         print(f"  {response}\n")
    
#     # Example: JSON output
#     print("\n" + "=" * 70)
#     print("JSON Output Example")
#     print("=" * 70)
    
#     client = clients["openai"]
#     response = client.chat(
#         "Generate a JSON object with fields: name, age, city for a fictional person",
#         output_format=OutputFormat.JSON_OBJECT,
#         system_prompt="Return only valid JSON, no other text."
#     )
    
#     print(f"\nJSON Response: {response}")
    
#     # Example: Conversation history (per instance)
#     print("\n" + "=" * 70)
#     print("Conversation History Example")
#     print("=" * 70)
    
#     client = clients["groq"]
#     client.clear_history()
    
#     print("\nTurn 1:")
#     response = client.chat("My name is Alice", use_history=True)
#     print(f"Assistant: {response}")
    
#     print("\nTurn 2:")
#     response = client.chat("What's my name?", use_history=True)
#     print(f"Assistant: {response}")