"""
Factory for building a fully-configured ProviderRegistry.
"""

from app.gateway.providers.anthropic import AnthropicAdapter
from app.gateway.providers.gemini import GeminiAdapter
from app.gateway.providers.ollama import OllamaAdapter
from app.gateway.providers.openai import OpenAIAdapter
from app.gateway.providers.registry import ProviderRegistry


def build_default_provider_registry() -> ProviderRegistry:
    """
    Build and return a ProviderRegistry with all supported adapters registered.

    Call once at application startup. Pass the resulting registry to all Gateway components.
    Do NOT store the result in module-level scope — inject it via dependency injection.
    """
    return (
        ProviderRegistry()
        .register(AnthropicAdapter())
        .register(OpenAIAdapter())
        .register(GeminiAdapter())
        .register(OllamaAdapter())
    )
