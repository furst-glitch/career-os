"""
EmbeddingService — generate text embeddings for semantic search.

Wraps litellm's async embedding API to produce 1536-dim vectors for
career_memories (text-embedding-3-small, OpenAI).

Design decisions:
- Returns None on any failure (no API key, quota, network) — callers
  treat missing embeddings as degraded search, not fatal errors.
- Accepts the OpenAI key directly so it can be injected in tests without
  touching Settings or environment variables.
- from_settings() is the production constructor.
- MAX_CHARS is a conservative character limit (~2× the typical 8191-token
  limit) to avoid truncation errors without counting tokens.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("app.services.embedding")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
MAX_CHARS = 20_000  # conservative limit; text-embedding-3-small supports ~8191 tokens


class EmbeddingService:
    """Generate 1536-dim embeddings via litellm (OpenAI text-embedding-3-small)."""

    def __init__(self, openai_api_key: str | None = None) -> None:
        self._api_key = openai_api_key

    async def embed(self, text: str) -> list[float] | None:
        """
        Generate a 1536-dim embedding vector.

        Returns None if no API key is available or the provider raises.
        Callers should handle None gracefully (skip vector search, not crash).
        """
        if not self._api_key:
            logger.debug("embedding_skipped reason=no_api_key")
            return None

        try:
            import litellm
            response = await litellm.aembedding(
                model=EMBEDDING_MODEL,
                input=[text[:MAX_CHARS]],
                api_key=self._api_key,
            )
            return response.data[0]["embedding"]
        except Exception as exc:
            logger.warning("embedding_failed model=%s error=%s", EMBEDDING_MODEL, exc)
            return None

    @classmethod
    def from_settings(cls, settings: object) -> "EmbeddingService":
        """Build from application settings. Production constructor."""
        key = getattr(settings, "openai_api_key", None) or None
        return cls(openai_api_key=key)
