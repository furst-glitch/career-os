"""
AbstractProviderAdapter — base class for all AI provider adapters.

Purpose: Define the common interface all adapters must implement.
Responsibility: Interface contract only. No business logic.
Dependencies: None.
Limitations:
  - Subclasses are responsible for their own I/O and error normalization.
  - Streaming behavior is provider-specific; adapters must yield str chunks.

Design: Uses ABC (not Protocol) because adapters share implementation via mixin methods.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import AsyncGenerator

from app.gateway.exceptions import GatewayConfigError, GatewayError
from app.gateway.schemas import ProviderResponse


class AbstractProviderAdapter(ABC):
    """
    Base class for AI provider adapters.

    All adapters are stateless: API keys are injected per-call, not stored.
    Adapters may be shared across concurrent requests without locking.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical provider name: anthropic, openai, gemini, ollama."""
        ...

    @property
    @abstractmethod
    def supported_models(self) -> frozenset[str]:
        """Set of model identifiers this adapter can serve."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        stream: bool,
        temperature: float,
        max_tokens: int,
        timeout_seconds: int,
        api_key: str | None,
        api_base: str | None = None,
        **kwargs: object,
    ) -> ProviderResponse | AsyncGenerator[str, None]:
        """
        Execute a completion request.

        Returns ProviderResponse for non-streaming, AsyncGenerator[str, None] for streaming.
        All provider-specific exceptions MUST be caught and re-raised as GatewayError.
        """
        ...

    @abstractmethod
    async def count_tokens(
        self,
        messages: list[dict[str, str]],
        model: str,
    ) -> int:
        """
        Count tokens for a message list (pre-call estimation).
        Must not make network calls.
        """
        ...

    @abstractmethod
    def normalize_error(self, exc: Exception) -> GatewayError:
        """
        Normalize a provider-specific exception to a GatewayError.

        Must be a pure function — no I/O, no side effects.
        Called by complete() to wrap raw provider errors before re-raising.
        """
        ...

    async def embed(
        self,
        text: str,
        model: str,
        api_key: str | None,
    ) -> list[float]:
        """
        Generate an embedding vector.

        Default implementation raises GatewayConfigError.
        Override in adapters that support embeddings.
        """
        raise GatewayConfigError(
            f"Provider {self.name!r} does not support embeddings via this adapter.",
            code="embeddings_not_supported",
        )

    def _measure_latency(self, start_monotonic: float) -> int:
        """Calculate elapsed milliseconds from a monotonic start time."""
        return int((time.monotonic() - start_monotonic) * 1000)
