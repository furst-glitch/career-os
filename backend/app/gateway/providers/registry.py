"""
ProviderRegistry — dynamic registry mapping provider names to adapter instances.

Purpose: Central lookup for provider adapters. Eliminates if/else chains in routing logic.
Responsibility: Adapter registration and retrieval.
Dependencies: None.
Limitations:
  - Register at application startup only (not thread-safe for concurrent registration).
  - One adapter instance per provider name; adapters must be stateless.

Usage:
    registry = ProviderRegistry()
    registry.register(AnthropicAdapter())
    registry.register(OpenAIAdapter())
    adapter = registry.get("anthropic")
"""

from __future__ import annotations

from app.gateway.exceptions import GatewayConfigError
from app.gateway.providers.base import AbstractProviderAdapter


class ProviderRegistry:
    """
    Registry of provider adapters.

    Thread-safe for reads after initialization (no locking needed for concurrent gets).
    Not safe for concurrent registration — register all adapters at startup before serving requests.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, AbstractProviderAdapter] = {}

    def register(self, adapter: AbstractProviderAdapter) -> "ProviderRegistry":
        """
        Register an adapter. Returns self to enable chaining.

        Overwrites existing registration for the same provider name.
        """
        self._adapters[adapter.name] = adapter
        return self

    def get(self, provider_name: str) -> AbstractProviderAdapter:
        """
        Retrieve adapter for a provider.

        Raises GatewayConfigError if provider is not registered.
        """
        adapter = self._adapters.get(provider_name)
        if adapter is None:
            available = sorted(self._adapters)
            raise GatewayConfigError(
                f"Provider {provider_name!r} is not registered. "
                f"Available providers: {available}",
                code="provider_not_registered",
            )
        return adapter

    def is_registered(self, provider_name: str) -> bool:
        """Check if a provider is registered without raising."""
        return provider_name in self._adapters

    def list_providers(self) -> list[str]:
        """Return sorted list of registered provider names."""
        return sorted(self._adapters)

    def __len__(self) -> int:
        return len(self._adapters)
