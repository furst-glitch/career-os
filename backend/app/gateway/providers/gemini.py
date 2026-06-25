"""
GeminiAdapter — wraps LiteLLM for Google Gemini API calls.

All litellm imports are deferred to method bodies so the module can be imported
without litellm installed (test environments that mock it).
"""

from __future__ import annotations

import time
from typing import AsyncGenerator, AsyncIterator, cast

from app.gateway.exceptions import GatewayError
from app.gateway.providers._litellm_errors import normalize_litellm_error
from app.gateway.providers.base import AbstractProviderAdapter
from app.gateway.schemas import ProviderResponse

_PROVIDER = "gemini"
_MODEL_PREFIX = "gemini/"


class GeminiAdapter(AbstractProviderAdapter):
    """
    Adapter for Google Gemini models via LiteLLM.

    Supported models: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash.
    Embeddings: not supported via this adapter (inherits the base raise).
    """

    @property
    def name(self) -> str:
        return _PROVIDER

    @property
    def supported_models(self) -> frozenset[str]:
        return frozenset({
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        })

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
        import litellm

        litellm_model = f"{_MODEL_PREFIX}{model}"
        call_kwargs: dict[str, object] = {
            "model": litellm_model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout_seconds,
            **kwargs,
        }
        if api_key:
            call_kwargs["api_key"] = api_key
        if api_base:
            call_kwargs["api_base"] = api_base

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
        Count tokens using litellm's local tokenizer (no network call).
        Falls back to approximate count if tokenizer is unavailable.
        """
        try:
            import litellm
            return int(
                litellm.token_counter(
                    model=f"{_MODEL_PREFIX}{model}",
                    messages=messages,
                )
            )
        except Exception:
            total_chars = sum(len(m.get("content", "")) for m in messages)
            return max(1, total_chars // 4)

    def normalize_error(self, exc: Exception) -> GatewayError:
        """Map litellm/httpx exceptions to GatewayError hierarchy."""
        return normalize_litellm_error(exc, _PROVIDER)
