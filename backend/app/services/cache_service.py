"""
Redis Cache Service — Sprint 9

Wraps redis.asyncio with a transparent in-memory fallback so the app keeps
working when REDIS_URL is not configured (e.g. local dev without Redis).

Usage:
    cache = get_cache()
    await cache.get("key")
    await cache.set("key", value, ttl=300)
    await cache.delete("key")
    await cache.delete_pattern("snapshot:*")

Key namespaces:
    snapshot:{user_id}                 TTL 300s
    match:{user_id}:{job_id}           TTL 3600s
    discovery:{user_id}:{query_hash}   TTL 300s
    coach:{user_id}:{analysis_type}    TTL 1800s
    mcv:{user_id}                      TTL 3600s
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# TTL constants (seconds)
TTL_SNAPSHOT = 300      # 5 min — refreshed on CV upload
TTL_MATCH = 3_600       # 1 h
TTL_DISCOVERY = 300     # 5 min
TTL_COACH = 1_800       # 30 min
TTL_MCV = 3_600         # 1 h


# ── In-memory fallback ────────────────────────────────────────────────────────

class _MemoryCache:
    """Simple TTL-aware dict used when Redis is unavailable."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float]] = {}  # key → (json_value, expires_at)
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        value, exp = entry
        if time.monotonic() > exp:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return json.loads(value)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        self._store[key] = (json.dumps(value, default=str), time.monotonic() + ttl)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def delete_pattern(self, pattern: str) -> int:
        prefix = pattern.rstrip("*")
        keys = [k for k in list(self._store) if k.startswith(prefix)]
        for k in keys:
            del self._store[k]
        return len(keys)

    # ── Atomic integer counters (Redis INCR/INCRBY parity) ─────────────────
    # Used by AIPolicyService for rate limiting and budget reservations.
    # In-memory parity is best-effort (single-process); Redis is authoritative.

    async def get_int(self, key: str) -> int:
        value = await self.get(key)
        try:
            return int(value) if value is not None else 0
        except (TypeError, ValueError):
            return 0

    async def increment(self, key: str, expire_seconds: int = 60) -> int:
        current = await self.get_int(key)
        new_value = current + 1
        await self.set(key, new_value, ttl=expire_seconds)
        return new_value

    async def increment_by(self, key: str, amount: int, expire_seconds: int = 300) -> int:
        current = await self.get_int(key)
        new_value = current + amount
        await self.set(key, new_value, ttl=expire_seconds)
        return new_value

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "backend": "memory",
            "keys": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(self._hits / total * 100, 1) if total else 0,
        }

    async def ping(self) -> bool:
        return True


# ── Redis wrapper ─────────────────────────────────────────────────────────────

class _RedisCache:
    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis  # type: ignore[import-untyped]
        self._client = aioredis.from_url(url, decode_responses=True)
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Any | None:
        try:
            raw = await self._client.get(key)
            if raw is None:
                self._misses += 1
                return None
            self._hits += 1
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis GET error for %s: %s", key, exc)
            self._misses += 1
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        try:
            await self._client.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception as exc:
            logger.warning("Redis SET error for %s: %s", key, exc)

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(key)
        except Exception as exc:
            logger.warning("Redis DELETE error for %s: %s", key, exc)

    async def delete_pattern(self, pattern: str) -> int:
        try:
            keys = await self._client.keys(pattern)
            if keys:
                await self._client.delete(*keys)
            return len(keys)
        except Exception as exc:
            logger.warning("Redis DELETE_PATTERN error for %s: %s", pattern, exc)
            return 0

    # ── Atomic integer counters ────────────────────────────────────────────
    # Native Redis INCR/INCRBY — atomic across processes. These store the value
    # as a plain integer string (NOT JSON), so use get_int() to read them back,
    # never get(). Used by AIPolicyService for rate limits and budget reservations.

    async def get_int(self, key: str) -> int:
        try:
            raw = await self._client.get(key)
            return int(raw) if raw is not None else 0
        except Exception as exc:
            logger.warning("Redis GET_INT error for %s: %s", key, exc)
            return 0

    async def increment(self, key: str, expire_seconds: int = 60) -> int:
        # INCR is atomic and creates the key at 0 if absent. Set TTL only on the
        # first increment (NX) so an active window isn't extended on every hit.
        new_value = await self._client.incr(key)
        if new_value == 1:
            await self._client.expire(key, expire_seconds)
        return int(new_value)

    async def increment_by(self, key: str, amount: int, expire_seconds: int = 300) -> int:
        new_value = await self._client.incrby(key, amount)
        # (Re)arm the TTL so reservations don't linger indefinitely.
        await self._client.expire(key, expire_seconds)
        return int(new_value)

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "backend": "redis",
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(self._hits / total * 100, 1) if total else 0,
        }

    async def ping(self) -> bool:
        try:
            return await self._client.ping()
        except Exception:
            return False


# ── Sync wrapper (for use in sync code like MemorySnapshotService) ────────────

class _SyncRedisCache:
    """Thin sync Redis client — used from synchronous service methods."""

    def __init__(self, url: str) -> None:
        import redis  # type: ignore[import-untyped]
        self._client = redis.from_url(url, decode_responses=True)
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        try:
            raw = self._client.get(key)
            if raw is None:
                self._misses += 1
                return None
            self._hits += 1
            return json.loads(raw)
        except Exception as exc:
            logger.warning("SyncRedis GET %s: %s", key, exc)
            self._misses += 1
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        try:
            self._client.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception as exc:
            logger.warning("SyncRedis SET %s: %s", key, exc)

    def delete_pattern(self, pattern: str) -> int:
        try:
            keys = self._client.keys(pattern)
            if keys:
                self._client.delete(*keys)
            return len(keys)
        except Exception as exc:
            logger.warning("SyncRedis DEL_PAT %s: %s", pattern, exc)
            return 0

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "backend": "redis-sync",
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(self._hits / total * 100, 1) if total else 0,
        }


_sync_cache: _SyncRedisCache | None = None


def get_sync_cache() -> _SyncRedisCache | None:
    """Returns a sync Redis client, or None if Redis not configured."""
    global _sync_cache
    if _sync_cache is None:
        url = getattr(settings, "redis_url", None)
        if url:
            try:
                _sync_cache = _SyncRedisCache(url)
            except Exception as exc:
                logger.warning("SyncRedis init failed: %s", exc)
    return _sync_cache


# ── Singleton (async) ─────────────────────────────────────────────────────────

_cache: _MemoryCache | _RedisCache | None = None


def get_cache() -> _MemoryCache | _RedisCache:
    global _cache
    if _cache is None:
        url = getattr(settings, "redis_url", None)
        if url:
            try:
                _cache = _RedisCache(url)
                logger.info("Cache: Redis at %s", url.split("@")[-1])
            except Exception as exc:
                logger.warning("Redis unavailable (%s) — falling back to in-memory cache", exc)
                _cache = _MemoryCache()
        else:
            logger.info("Cache: in-memory (set REDIS_URL for Redis)")
            _cache = _MemoryCache()
    return _cache


# ── Key builders ──────────────────────────────────────────────────────────────

def key_snapshot(user_id: str) -> str:
    return f"snapshot:{user_id}"

def key_match(user_id: str, job_id: str) -> str:
    return f"match:{user_id}:{job_id}"

def key_discovery(user_id: str, query: str, location: str | None) -> str:
    h = hashlib.md5(f"{query}|{location or ''}".encode()).hexdigest()[:12]
    return f"discovery:{user_id}:{h}"

def key_coach(user_id: str, analysis_type: str, question: str | None = None) -> str:
    h = hashlib.md5(f"{analysis_type}|{question or ''}".encode()).hexdigest()[:12]
    return f"coach:{user_id}:{h}"

def key_mcv(user_id: str) -> str:
    return f"mcv:{user_id}"


# ── Invalidation helpers ──────────────────────────────────────────────────────

async def invalidate_user(user_id: str) -> None:
    """Purge all cached data for a user (call after CV upload or profile change)."""
    cache = get_cache()
    await cache.delete_pattern(f"snapshot:{user_id}*")
    await cache.delete_pattern(f"match:{user_id}*")
    await cache.delete_pattern(f"coach:{user_id}*")
    await cache.delete_pattern(f"mcv:{user_id}*")
    logger.info("Cache invalidated for user %s", user_id[:8])
