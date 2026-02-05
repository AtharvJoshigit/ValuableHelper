"""
Universal AI Client - IMPROVED VERSION
"""

from typing import Optional, List, Dict, Any, Union
import os
from enum import Enum


class OutputFormat(Enum):
    """Output format options."""
    TEXT = "text"
    JSON_OBJECT = "json_object"
    JSON_SCHEMA = "json_schema"


class UniversalAIClient:
    """Universal client with OpenAI SDK for all providers including Google."""
    
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        self.provider = provider.lower()
        self.model = model
        self.base_url = base_url
        self.kwargs = kwargs
        
        # Get API key
        self.api_key = api_key or self._get_api_key()
        
        # Initialize client
        self.client = self._init_client()
        
        # Conversation history
        self.conversation_history: List[Dict[str, str]] = []
        
        print(f"✓ Initialized {self.provider} client with model: {self.model}")
    
    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment."""
        env_var = f"{self.provider.upper()}_API_KEY"
        api_key = os.getenv(env_var)
        
        if not api_key:
            print(f"⚠️  Warning: {env_var} not found in environment")
        
        return api_key
    
    def _init_client(self):
        """Initialize the appropriate SDK client."""
        
        if self.provider == "openai":
            return self._init_openai()
        
        elif self.provider == "anthropic":
            return self._init_anthropic()
        
        elif self.provider == "google":
            # ✅ NEW: Use OpenAI SDK for Google Gemini
            return self._init_google_via_openai()
        
        elif self.provider == "groq":
            return self._init_groq()
        
        else:
            # Default: OpenAI SDK
            print(f"ℹ️  Using OpenAI SDK for {self.provider}")
            return self._init_openai()
    
    def _init_openai(self):
        """Initialize OpenAI SDK."""
        try:
            from openai import OpenAI
            
            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            
            return OpenAI(**client_kwargs)
        
        except ImportError:
            raise ImportError("OpenAI SDK not installed. Install with: pip install openai")
    
    def _init_anthropic(self):
        """Initialize Anthropic SDK."""
        try:
            from anthropic import Anthropic
            return Anthropic(api_key=self.api_key)
        
        except ImportError:
            raise ImportError("Anthropic SDK not installed. Install with: pip install anthropic")
    
    def _init_google_via_openai(self):
        """
        ✅ NEW: Initialize Google Gemini using OpenAI SDK.
        
        This avoids all the thought_signature issues by using Google's
        OpenAI-compatible API endpoint.
        """
        try:
            from openai import OpenAI
            
            # Google Gemini OpenAI-compatible endpoint
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            
            return OpenAI(
                api_key=self.api_key,
                base_url=base_url
            )
        
        except ImportError:
            raise ImportError("OpenAI SDK not installed. Install with: pip install openai")
    
    def _init_groq(self):
        """Initialize Groq using OpenAI SDK."""
        try:
            from openai import OpenAI
            
            return OpenAI(
                api_key=self.api_key,
                base_url="https://api.groq.com/openai/v1"
            )
        
        except ImportError:
            raise ImportError("OpenAI SDK not installed. Install with: pip install openai")
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        print("✓ Conversation history cleared")
    
    def set_model(self, model: str):
        """Change the model."""
        self.model = model
        print(f"✓ Model changed to: {self.model}")


# Recommended model mappings
RECOMMENDED_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "google": "gemini-2.0-flash-exp",  # Works with OpenAI SDK!
    "groq": "llama-3.3-70b-versatile"
}


def create_client(provider: str, api_key: Optional[str] = None) -> UniversalAIClient:
    """
    Create a client with recommended settings.
    
    Example:
        >>> client = create_client("google")
        >>> # Now works perfectly with function calling, no thought_signature issues!
    """
    model = RECOMMENDED_MODELS.get(provider.lower(), "gpt-4o-mini")
    
    return UniversalAIClient(
        provider=provider,
        model=model,
        api_key=api_key
    )