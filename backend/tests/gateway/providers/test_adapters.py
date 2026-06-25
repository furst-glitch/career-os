"""
Tests for all provider adapters (Anthropic, OpenAI, Gemini, Ollama).

No network calls — litellm functions are patched. Error normalization uses real
litellm exception classes so the isinstance mapping is exercised faithfully.
"""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest

from app.gateway.exceptions import (
    GatewayAuthError,
    GatewayConfigError,
    GatewayPolicyError,
    GatewayProviderError,
    GatewayTimeoutError,
    GatewayUnavailableError,
)
from app.gateway.providers.anthropic import AnthropicAdapter
from app.gateway.providers.gemini import GeminiAdapter
from app.gateway.providers.ollama import OllamaAdapter
from app.gateway.providers.openai import OpenAIAdapter
from app.gateway.schemas import ProviderResponse

# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #


@pytest.fixture
def mock_litellm_response() -> MagicMock:
    """A mock litellm ModelResponse (non-streaming)."""
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message.content = "test response"
    mock.usage.prompt_tokens = 10
    mock.usage.completion_tokens = 5
    mock.usage.total_tokens = 15
    mock.model = "claude-sonnet-4-6"
    return mock


def _make_stream_chunk(content: str | None) -> MagicMock:
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = content
    return chunk


def _async_stream(chunks: list) -> AsyncIterator:
    """Return an async iterator over the given chunks."""

    async def gen() -> AsyncIterator:
        for c in chunks:
            yield c

    return gen()


def _auth_error() -> litellm.AuthenticationError:
    return litellm.AuthenticationError(
        message="invalid key", llm_provider="anthropic", model="m"
    )


def _rate_limit_error() -> litellm.RateLimitError:
    return litellm.RateLimitError(
        message="slow down", llm_provider="anthropic", model="m"
    )


def _context_window_error() -> litellm.ContextWindowExceededError:
    return litellm.ContextWindowExceededError(
        message="too big", model="m", llm_provider="anthropic"
    )


def _timeout_error() -> litellm.Timeout:
    return litellm.Timeout(message="timed out", model="m", llm_provider="anthropic")


def _unavailable_error() -> litellm.ServiceUnavailableError:
    return litellm.ServiceUnavailableError(
        message="down", llm_provider="anthropic", model="m"
    )


def _bad_request_error() -> litellm.BadRequestError:
    return litellm.BadRequestError(
        message="bad", model="m", llm_provider="anthropic"
    )


ADAPTERS = {
    "anthropic": (AnthropicAdapter, "claude-sonnet-4-6"),
    "openai": (OpenAIAdapter, "gpt-4o"),
    "gemini": (GeminiAdapter, "gemini-2.0-flash"),
}


async def _call_complete(adapter, model, stream=False, api_base=None):
    return await adapter.complete(
        messages=[{"role": "user", "content": "hello"}],
        model=model,
        stream=stream,
        temperature=0.5,
        max_tokens=1000,
        timeout_seconds=30,
        api_key="sk-test",
        api_base=api_base,
    )


# --------------------------------------------------------------------------- #
# Non-streaming complete (all cloud adapters)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
async def test_complete_non_streaming(
    provider: str, mock_litellm_response: MagicMock
) -> None:
    adapter_cls, model = ADAPTERS[provider]
    adapter = adapter_cls()
    with patch("litellm.acompletion", new=AsyncMock(return_value=mock_litellm_response)):
        result = await _call_complete(adapter, model)
    assert isinstance(result, ProviderResponse)
    assert result.provider == provider
    assert result.model == model
    assert result.content == "test response"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert result.total_tokens == 15
    assert result.latency_ms >= 0


@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
async def test_complete_handles_none_content(
    provider: str, mock_litellm_response: MagicMock
) -> None:
    mock_litellm_response.choices[0].message.content = None
    adapter_cls, model = ADAPTERS[provider]
    adapter = adapter_cls()
    with patch("litellm.acompletion", new=AsyncMock(return_value=mock_litellm_response)):
        result = await _call_complete(adapter, model)
    assert result.content == ""


# --------------------------------------------------------------------------- #
# Streaming complete
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
async def test_complete_streaming_yields_chunks(provider: str) -> None:
    adapter_cls, model = ADAPTERS[provider]
    adapter = adapter_cls()
    chunks = [
        _make_stream_chunk("Hello"),
        _make_stream_chunk(None),  # empty delta — skipped
        _make_stream_chunk(" world"),
    ]
    with patch("litellm.acompletion", new=AsyncMock(return_value=_async_stream(chunks))):
        gen = await _call_complete(adapter, model, stream=True)
        collected = [piece async for piece in gen]
    assert collected == ["Hello", " world"]


# --------------------------------------------------------------------------- #
# Error normalization (parametrized across cloud adapters)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
@pytest.mark.parametrize(
    "make_error, expected",
    [
        (_auth_error, GatewayAuthError),
        (_rate_limit_error, GatewayPolicyError),
        (_context_window_error, GatewayConfigError),
        (_timeout_error, GatewayTimeoutError),
        (_unavailable_error, GatewayUnavailableError),
        (_bad_request_error, GatewayProviderError),
        (lambda: RuntimeError("boom"), GatewayProviderError),
    ],
)
async def test_complete_normalizes_errors(
    provider: str, make_error, expected
) -> None:
    adapter_cls, model = ADAPTERS[provider]
    adapter = adapter_cls()
    with patch("litellm.acompletion", new=AsyncMock(side_effect=make_error())):
        with pytest.raises(expected):
            await _call_complete(adapter, model)


@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
def test_normalize_error_sets_provider(provider: str) -> None:
    adapter_cls, _ = ADAPTERS[provider]
    adapter = adapter_cls()
    err = adapter.normalize_error(RuntimeError("x"))
    assert isinstance(err, GatewayProviderError)
    assert err.provider == provider


def test_normalize_error_without_litellm_installed() -> None:
    """If litellm import fails, normalization falls back to GatewayProviderError."""
    adapter = AnthropicAdapter()
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "litellm":
            raise ImportError("no litellm")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        err = adapter.normalize_error(RuntimeError("x"))
    assert isinstance(err, GatewayProviderError)
    assert err.provider == "anthropic"


# --------------------------------------------------------------------------- #
# Token counting
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
async def test_count_tokens_returns_positive_integer(provider: str) -> None:
    adapter_cls, model = ADAPTERS[provider]
    adapter = adapter_cls()
    with patch("litellm.token_counter", return_value=42):
        count = await adapter.count_tokens(
            [{"role": "user", "content": "hi"}], model
        )
    assert count == 42


@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
async def test_count_tokens_falls_back_on_exception(provider: str) -> None:
    adapter_cls, model = ADAPTERS[provider]
    adapter = adapter_cls()
    with patch("litellm.token_counter", side_effect=Exception("tokenizer unavailable")):
        count = await adapter.count_tokens(
            [{"role": "user", "content": "hello world"}], model
        )
    assert count > 0


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #


async def test_anthropic_embed_raises_not_supported() -> None:
    adapter = AnthropicAdapter()
    with pytest.raises(GatewayConfigError, match="not support"):
        await adapter.embed("text", "some-model", api_key=None)


async def test_gemini_embed_raises_not_supported() -> None:
    adapter = GeminiAdapter()
    with pytest.raises(GatewayConfigError, match="not support"):
        await adapter.embed("text", "some-model", api_key=None)


async def test_ollama_embed_raises_not_supported() -> None:
    adapter = OllamaAdapter()
    with pytest.raises(GatewayConfigError, match="not support"):
        await adapter.embed("text", "some-model", api_key=None)


async def test_openai_embed_supported() -> None:
    mock_resp = MagicMock()
    mock_resp.data = [{"embedding": [0.1, 0.2, 0.3]}]
    adapter = OpenAIAdapter()
    with patch("litellm.aembedding", new=AsyncMock(return_value=mock_resp)):
        result = await adapter.embed("hello", "text-embedding-3-small", api_key="sk-test")
    assert result == [0.1, 0.2, 0.3]


async def test_openai_embed_without_api_key() -> None:
    mock_resp = MagicMock()
    mock_resp.data = [{"embedding": [0.5]}]
    adapter = OpenAIAdapter()
    with patch("litellm.aembedding", new=AsyncMock(return_value=mock_resp)) as m:
        result = await adapter.embed("hello", "text-embedding-3-large", api_key=None)
    assert result == [0.5]
    # api_key omitted from call kwargs when None
    assert "api_key" not in m.await_args.kwargs


async def test_openai_embed_unsupported_model_raises() -> None:
    adapter = OpenAIAdapter()
    with pytest.raises(GatewayConfigError, match="not supported"):
        await adapter.embed("hello", "gpt-4o", api_key="sk-test")


async def test_openai_embed_normalizes_provider_error() -> None:
    adapter = OpenAIAdapter()
    with patch("litellm.aembedding", new=AsyncMock(side_effect=_auth_error())):
        with pytest.raises(GatewayAuthError):
            await adapter.embed("hello", "text-embedding-3-small", api_key="sk-test")


# --------------------------------------------------------------------------- #
# Ollama-specific
# --------------------------------------------------------------------------- #


async def test_ollama_requires_api_base() -> None:
    adapter = OllamaAdapter()
    with pytest.raises(GatewayConfigError, match="api_base"):
        await _call_complete(adapter, "llama3.2", api_base=None)


async def test_ollama_complete_with_api_base(mock_litellm_response: MagicMock) -> None:
    adapter = OllamaAdapter()
    with patch(
        "litellm.acompletion", new=AsyncMock(return_value=mock_litellm_response)
    ) as m:
        result = await _call_complete(
            adapter, "llama3.2", api_base="http://localhost:11434"
        )
    assert isinstance(result, ProviderResponse)
    assert result.provider == "ollama"
    # Model is prefixed and api_base passed; api_key NOT passed (Ollama has no auth).
    assert m.await_args.kwargs["model"] == "ollama/llama3.2"
    assert m.await_args.kwargs["api_base"] == "http://localhost:11434"
    assert "api_key" not in m.await_args.kwargs


async def test_ollama_count_tokens_uses_approximation() -> None:
    adapter = OllamaAdapter()
    # Never calls litellm.token_counter — approximation only.
    count = await adapter.count_tokens(
        [{"role": "user", "content": "x" * 40}], "llama3.2"
    )
    assert count == 10  # 40 chars // 4


async def test_ollama_count_tokens_minimum_one() -> None:
    adapter = OllamaAdapter()
    count = await adapter.count_tokens([{"role": "user", "content": ""}], "llama3.2")
    assert count == 1


async def test_ollama_normalizes_connection_error() -> None:
    adapter = OllamaAdapter()
    with patch(
        "litellm.acompletion",
        new=AsyncMock(side_effect=ConnectionError("refused")),
    ):
        with pytest.raises(GatewayProviderError):
            await _call_complete(
                adapter, "llama3.2", api_base="http://localhost:11434"
            )


def test_ollama_supported_models_empty() -> None:
    assert OllamaAdapter().supported_models == frozenset()


# --------------------------------------------------------------------------- #
# Adapter metadata
# --------------------------------------------------------------------------- #


def test_adapter_names_and_models() -> None:
    assert AnthropicAdapter().name == "anthropic"
    assert OpenAIAdapter().name == "openai"
    assert GeminiAdapter().name == "gemini"
    assert OllamaAdapter().name == "ollama"
    assert "claude-sonnet-4-6" in AnthropicAdapter().supported_models
    assert "gpt-4o" in OpenAIAdapter().supported_models
    assert "gemini-2.0-flash" in GeminiAdapter().supported_models


@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
async def test_complete_passes_api_base_when_provided(
    provider: str, mock_litellm_response: MagicMock
) -> None:
    adapter_cls, model = ADAPTERS[provider]
    adapter = adapter_cls()
    with patch(
        "litellm.acompletion", new=AsyncMock(return_value=mock_litellm_response)
    ) as m:
        await adapter.complete(
            messages=[{"role": "user", "content": "hi"}],
            model=model,
            stream=False,
            temperature=0.0,
            max_tokens=100,
            timeout_seconds=10,
            api_key="sk-test",
            api_base="http://proxy.local",
        )
    assert m.await_args.kwargs["api_base"] == "http://proxy.local"


async def test_ollama_streaming_yields_chunks() -> None:
    adapter = OllamaAdapter()
    chunks = [_make_stream_chunk("a"), _make_stream_chunk("b")]
    with patch("litellm.acompletion", new=AsyncMock(return_value=_async_stream(chunks))):
        gen = await _call_complete(
            adapter, "llama3.2", stream=True, api_base="http://localhost:11434"
        )
        collected = [piece async for piece in gen]
    assert collected == ["a", "b"]


async def test_openai_embed_reraises_gateway_error() -> None:
    """A GatewayError raised by the underlying call propagates unchanged (not re-wrapped)."""
    adapter = OpenAIAdapter()
    gateway_err = GatewayConfigError("boom", code="some_code")
    with patch("litellm.aembedding", new=AsyncMock(side_effect=gateway_err)):
        with pytest.raises(GatewayConfigError) as exc_info:
            await adapter.embed("hi", "text-embedding-3-small", api_key="sk-test")
    assert exc_info.value is gateway_err


async def test_anthropic_count_tokens_uses_prefixed_model() -> None:
    adapter = AnthropicAdapter()
    with patch("litellm.token_counter", return_value=7) as m:
        await adapter.count_tokens([{"role": "user", "content": "hi"}], "claude-sonnet-4-6")
    assert m.call_args.kwargs["model"] == "anthropic/claude-sonnet-4-6"
