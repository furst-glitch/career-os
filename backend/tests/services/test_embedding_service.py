"""
Unit tests for EmbeddingService (app.services.embedding_service).

litellm is mocked — no real API calls.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.embedding_service import EMBEDDING_DIM, EMBEDDING_MODEL, EmbeddingService


# ── embed() ───────────────────────────────────────────────────────────────────


class TestEmbed:
    @pytest.mark.asyncio
    async def test_returns_none_without_api_key(self):
        svc = EmbeddingService(openai_api_key=None)
        result = await svc.embed("hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_litellm_error(self):
        svc = EmbeddingService(openai_api_key="sk-test")
        with patch("litellm.aembedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.side_effect = RuntimeError("quota exceeded")
            result = await svc.embed("hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_calls_litellm_with_correct_model_and_key(self):
        fake_embedding = [0.1] * EMBEDDING_DIM
        mock_response = SimpleNamespace(data=[{"embedding": fake_embedding}])
        svc = EmbeddingService(openai_api_key="sk-test")
        with patch("litellm.aembedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = mock_response
            result = await svc.embed("test text")

        mock_embed.assert_awaited_once()
        call_kwargs = mock_embed.call_args[1]
        assert call_kwargs["model"] == EMBEDDING_MODEL
        assert call_kwargs["api_key"] == "sk-test"
        assert result == fake_embedding

    @pytest.mark.asyncio
    async def test_long_text_truncated_to_max_chars(self):
        from app.services.embedding_service import MAX_CHARS
        fake_embedding = [0.0] * EMBEDDING_DIM
        mock_response = SimpleNamespace(data=[{"embedding": fake_embedding}])
        long_text = "x" * (MAX_CHARS + 5_000)
        svc = EmbeddingService(openai_api_key="sk-test")
        with patch("litellm.aembedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = mock_response
            await svc.embed(long_text)

        sent_input = mock_embed.call_args[1]["input"][0]
        assert len(sent_input) == MAX_CHARS

    @pytest.mark.asyncio
    async def test_returns_vector_of_correct_dimension(self):
        fake_embedding = [0.5] * EMBEDDING_DIM
        mock_response = SimpleNamespace(data=[{"embedding": fake_embedding}])
        svc = EmbeddingService(openai_api_key="sk-openai")
        with patch("litellm.aembedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = mock_response
            result = await svc.embed("short text")
        assert len(result) == EMBEDDING_DIM


# ── from_settings() ───────────────────────────────────────────────────────────


class TestFromSettings:
    def test_extracts_openai_api_key(self):
        settings = SimpleNamespace(openai_api_key="sk-from-settings")
        svc = EmbeddingService.from_settings(settings)
        assert svc._api_key == "sk-from-settings"

    def test_missing_key_returns_none(self):
        settings = SimpleNamespace()
        svc = EmbeddingService.from_settings(settings)
        assert svc._api_key is None

    def test_empty_string_key_treated_as_none(self):
        settings = SimpleNamespace(openai_api_key="")
        svc = EmbeddingService.from_settings(settings)
        assert svc._api_key is None
