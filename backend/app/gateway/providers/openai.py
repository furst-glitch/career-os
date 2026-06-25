"""
OpenAIAdapter — wraps LiteLLM for OpenAI API calls.
"""

from __future__ import annotations

import time
from typing import AsyncGenerator, AsyncIterator, cast

from app.gateway.exceptions import GatewayConfigError, GatewayError
from app.gateway.providers._litellm_errors import normalize_litellm_error
from app.gateway.providers.base import AbstractProviderAdapter
from app.gateway.schemas import ProviderResponse

_PROVIDER = "openai"
_EMBEDDING_MODELS = frozenset({"text-embedding-3-small", "text-embedding-3-large"})


class OpenAIAdapter(AbstractProviderAdapter):
    """
    Adapter for OpenAI GPT models via LiteLLM.

    Supports: GPT-4o, GPT-4o-mini, GPT-4-turbo, o1 series.
    Embeddings: text-embedding-3-small, text-embedding-3-large.
    """

    @property
    def name(self) -> str:
        return _PROVIDER

    @property
    def supported_models(self) -> frozenset[str]:
        return frozenset({
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "o1",
            "o1-mini",
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

        call_kwargs: dict[str, object] = {
            "model": model,  # OpenAI: no prefix needed
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
        async for chunk in response:
            delta = chunk.choices[0].delta  # type: ignore[attr-defined]
            content = getattr(delta, "content", None)
            if content:
                yield content

    async def embed(
        self,
        text: str,
        model: str,
        api_key: str | None,
    ) -> list[float]:
        if model not in _EMBEDDING_MODELS:
            raise GatewayConfigError(
                f"Embedding model {model!r} not supported. Use: {sorted(_EMBEDDING_MODELS)}",
                code="unsupported_embedding_model",
            )
        import litellm

        try:
            response = await litellm.aembedding(
                model=f"openai/{model}",
                input=text,
                **({"api_key": api_key} if api_key else {}),
            )
            return cast("list[float]", response.data[0]["embedding"])
        except GatewayError:
            raise
        except Exception as exc:
            raise self.normalize_error(exc) from exc

    async def count_tokens(
        self,
        messages: list[dict[str, str]],
        model: str,
    ) -> int:
        try:
            import litellm
            return int(litellm.token_counter(model=model, messages=messages))
        except Exception:
            total_chars = sum(len(m.get("content", "")) for m in messages)
            return max(1, total_chars // 4)

    def normalize_error(self, exc: Exception) -> GatewayError:
        return normalize_litellm_error(exc, _PROVIDER)
