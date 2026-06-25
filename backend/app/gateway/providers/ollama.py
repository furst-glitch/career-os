"""
OllamaAdapter — wraps LiteLLM for self-hosted Ollama API calls.

Ollama differs from cloud providers:
  - No authentication (api_key is ignored).
  - api_base is REQUIRED (the Ollama server URL, e.g. http://localhost:11434).
  - Open-ended model set: any model the operator has pulled. supported_models is
    therefore empty — validation is by api_base presence, not model membership.
  - No local tokenizer API: count_tokens always uses character approximation.
  - Errors are typically httpx connection errors, not litellm auth errors; the
    shared normalizer maps unknown exceptions to GatewayProviderError.
"""

from __future__ import annotations

import time
from typing import AsyncGenerator, AsyncIterator, cast

from app.gateway.exceptions import GatewayConfigError, GatewayError
from app.gateway.providers._litellm_errors import normalize_litellm_error
from app.gateway.providers.base import AbstractProviderAdapter
from app.gateway.schemas import ProviderResponse

_PROVIDER = "ollama"
_MODEL_PREFIX = "ollama/"


class OllamaAdapter(AbstractProviderAdapter):
    """
    Adapter for self-hosted Ollama models via LiteLLM.

    Models are open-ended; supported_models is intentionally empty.
    Embeddings: not supported via this adapter (inherits the base raise).
    """

    @property
    def name(self) -> str:
        return _PROVIDER

    @property
    def supported_models(self) -> frozenset[str]:
        # Open-ended: any pulled model is valid. Validation is by api_base presence.
        return frozenset()

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
        if not api_base:
            raise GatewayConfigError(
                "Ollama requires api_base (e.g., http://localhost:11434)",
                code="missing_api_base",
            )

        import litellm

        litellm_model = f"{_MODEL_PREFIX}{model}"
        call_kwargs: dict[str, object] = {
            "model": litellm_model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout_seconds,
            "api_base": api_base,  # api_key intentionally ignored — Ollama has no auth
            **kwargs,
        }

        try:
            start = time.monotonic()
            response = await litellm.acompletion(**call_kwargs)
        except Exception as exc:
            raise self.normalize_error(exc) from exc

        if stream:
            return self._stream_chunks(cast("AsyncIterator[object]", response))

        return ProviderResponse(
            content=response.choices[0].message.content or "",
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            model=model,
            provider=_PROVIDER,
            latency_ms=self._measure_latency(start),
        )

    async def _stream_chunks(
        self, response: AsyncIterator[object]
    ) -> AsyncGenerator[str, None]:
        """Yield string content chunks from a litellm streaming response."""
        async for chunk in response:
            delta = chunk.choices[0].delta  # type: ignore[attr-defined]
            content = getattr(delta, "content", None)
            if content:
                yield content

    async def count_tokens(
        self,
        messages: list[dict[str, str]],
        model: str,
    ) -> int:
        """
        Ollama exposes no tokenizer API, so always use a character approximation
        (4 characters per token on average). Never makes a network call.
        """
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return max(1, total_chars // 4)

    def normalize_error(self, exc: Exception) -> GatewayError:
        """Map litellm/httpx exceptions to GatewayError hierarchy."""
        return normalize_litellm_error(exc, _PROVIDER)
