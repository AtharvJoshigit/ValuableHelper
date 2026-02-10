# file: engine/core/provide.py

from typing import Type, Dict, Any, Optional
import logging
from engine.providers.base_provider import BaseProvider

logger = logging.getLogger(__name__)

PROVIDER_REGISTRY: Dict[str, Type[BaseProvider]] = {}

def register_provider(name: str, provider_class: Type[BaseProvider]):
    """Register a provider class."""
    PROVIDER_REGISTRY[name] = provider_class
    logger.info(f"Registered provider: {name}")

def get_provider(name: str, **kwargs) -> Optional[BaseProvider]:
    """Get provider instance by name with configuration."""
    try:
        provider_class = PROVIDER_REGISTRY[name]
        return provider_class(model_id = kwargs.get('model'))
    except KeyError:
        logger.error(f"Unsupported provider: {name}")
        return None
    except Exception as e:
        logger.error(f"Error creating provider {name}: {e}")
        return None

def list_providers() -> list[str]:
    """List all registered providers."""
    return list(PROVIDER_REGISTRY.keys())

def auto_register_providers():
    """Auto-register all available providers."""
    try:
        from engine.providers.google.provider import GoogleProvider
        register_provider("google", GoogleProvider)
    except ImportError:
        logger.warning("Google provider not available")
    
    try:
        from engine.providers.openai.provider import OpenAIProvider
        register_provider("openai", OpenAIProvider)
    except ImportError:
        logger.warning("OpenAI provider not available")
    
    try:
        from engine.providers.anthropic.provider import AnthropicProvider
        register_provider("anthropic", AnthropicProvider)
    except ImportError:
        logger.warning("Anthropic provider not available")