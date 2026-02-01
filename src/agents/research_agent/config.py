"""
Configuration Manager for AI Handler
Manages provider and model settings for different research methods
"""

from typing import Optional, Dict, Literal
import json
import os


class AIConfig:
    """
    Configuration manager for AI research handlers.
    Allows setting different providers and models for different research types.
    """
    
    # Default configurations for each research method
    DEFAULT_CONFIG = {
        "handle_research": {
            "provider": "groq",
            "model": "groq/compound",
            "temperature": 0.7,
            "max_tokens": 2000,
        },
        "handle_research_on_trend": {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.8,
            "max_tokens": 3000,
        },
        "todays_research": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.9,
            "max_tokens": 4000,
        },
        "image_generation": {
            "provider": "openai",
            "model": "dall-e-3",
            "size": "1024x1024",
            "quality": "standard",
        }
    }
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to JSON config file (optional)
        """
        self.config_file = config_file or "ai_config.json"
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from file or use defaults."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                print(f"✓ Loaded config from {self.config_file}")
                return loaded_config
            except Exception as e:
                print(f"⚠️  Error loading config: {e}")
                print("Using default configuration")
                return self.DEFAULT_CONFIG.copy()
        else:
            print("ℹ️  No config file found, using defaults")
            return self.DEFAULT_CONFIG.copy()
    
    def _save_config(self):
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"✓ Config saved to {self.config_file}")
        except Exception as e:
            print(f"⚠️  Error saving config: {e}")
    
    def get(
        self,
        method: Literal["handle_research", "handle_research_on_trend", "todays_research", "image_generation"]
    ) -> Dict:
        """
        Get configuration for a specific method.
        
        Args:
            method: Method name (handle_research, handle_research_on_trend, todays_research, image_generation)
            
        Returns:
            Configuration dictionary for the method
        """
        return self.config.get(method, self.DEFAULT_CONFIG.get(method, {}))
    
    def set(
        self,
        method: Literal["handle_research", "handle_research_on_trend", "todays_research", "image_generation"],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ):
        """
        Set configuration for a specific method.
        
        Args:
            method: Method name
            provider: Provider name (openai, anthropic, google, groq)
            model: Model name
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
        """
        if method not in self.config:
            self.config[method] = {}
        
        if provider:
            self.config[method]["provider"] = provider
        
        if model:
            self.config[method]["model"] = model
        
        # Update additional parameters
        self.config[method].update(kwargs)
        
        self._save_config()
        print(f"✓ Updated config for {method}")
        print(f"  Provider: {self.config[method].get('provider')}")
        print(f"  Model: {self.config[method].get('model')}")
    
    def get_provider(self, method: str) -> str:
        """Get provider for a specific method."""
        return self.get(method).get("provider", "openai")
    
    def get_model(self, method: str) -> str:
        """Get model for a specific method."""
        return self.get(method).get("model", "gpt-4o-mini")
    
    def get_temperature(self, method: str) -> float:
        """Get temperature for a specific method."""
        return self.get(method).get("temperature", 0.7)
    
    def get_max_tokens(self, method: str) -> int:
        """Get max_tokens for a specific method."""
        return self.get(method).get("max_tokens", 2000)
    
    def reset(self, method: Optional[str] = None):
        """
        Reset configuration to defaults.
        
        Args:
            method: Specific method to reset, or None to reset all
        """
        if method:
            self.config[method] = self.DEFAULT_CONFIG.get(method, {}).copy()
            print(f"✓ Reset config for {method} to defaults")
        else:
            self.config = self.DEFAULT_CONFIG.copy()
            print("✓ Reset all config to defaults")
        
        self._save_config()
    
    def print_config(self):
        """Print current configuration."""
        print("\n" + "=" * 70)
        print("CURRENT AI CONFIGURATION")
        print("=" * 70)
        
        for method, settings in self.config.items():
            print(f"\n📌 {method}:")
            for key, value in settings.items():
                print(f"   {key}: {value}")
        
        print("\n" + "=" * 70)
    
    def set_all(
        self,
        provider: str,
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        """
        Set the same provider and model for all methods.
        
        Args:
            provider: Provider name
            model: Model name
            temperature: Temperature (optional)
            max_tokens: Max tokens (optional)
        """
        methods = ["handle_research", "handle_research_on_trend", "todays_research"]
        
        for method in methods:
            kwargs = {}
            if temperature is not None:
                kwargs["temperature"] = temperature
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            
            self.set(method, provider=provider, model=model, **kwargs)
        
        print(f"\n✓ Set all methods to use {provider}/{model}")


# Singleton instance
_config_instance = None


def get_config() -> AIConfig:
    """Get the global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = AIConfig()
    return _config_instance


# Example usage and testing
if __name__ == "__main__":
    print("=" * 70)
    print("AI Configuration Manager - Demo")
    print("=" * 70)
    
    # Create config instance
    config = AIConfig()
    
    # Print default config
    print("\n1. Default Configuration:")
    config.print_config()
    
    # Set specific method config
    print("\n2. Setting custom config for handle_research:")
    config.set(
        "handle_research",
        provider="anthropic",
        model="claude-3-haiku-20240307",
        temperature=0.5,
        max_tokens=1500
    )
    
    # Set another method
    print("\n3. Setting custom config for todays_research:")
    config.set(
        "todays_research",
        provider="groq",
        model="llama-3.3-70b-versatile",
        temperature=0.9
    )
    
    # Print updated config
    print("\n4. Updated Configuration:")
    config.print_config()
    
    # Get specific config
    print("\n5. Getting config for handle_research:")
    research_config = config.get("handle_research")
    print(f"   Provider: {research_config['provider']}")
    print(f"   Model: {research_config['model']}")
    print(f"   Temperature: {research_config['temperature']}")
    
    # Reset specific method
    print("\n6. Resetting handle_research to defaults:")
    config.reset("handle_research")
    config.print_config()
    
    # Set all methods to same config
    print("\n7. Setting all methods to use Groq:")
    config.set_all(
        provider="groq",
        model="llama-3.3-70b-versatile",
        temperature=0.8
    )
    config.print_config()