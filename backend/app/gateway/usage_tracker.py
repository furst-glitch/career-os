"""
UsageTracker — records AI usage to the database after each Gateway request.

Purpose: Persist usage data for billing, analytics, and budget enforcement.
Responsibility: INSERT to ai_usage. Non-critical path — errors are logged, not raised.
Dependencies: Supabase (ai_usage table, agent_registry table).
Limitations: Async fire-and-forget. Not guaranteed delivery if process crashes mid-write.

Schema notes (from 00012_ai_cost_management.sql):
  - `agent_id` (uuid FK to agent_registry, nullable) — resolved from agent name
    via _resolve_agent_id(). Cached at class level (agent registry is stable).
  - `operation` (text NOT NULL) — always set to agent_name for traceability.
  - `provider` is the `ai_provider` enum: ('openai','anthropic','ollama','custom').
    Any provider outside that set (e.g. 'gemini') is coerced to 'custom'.
  - `cost_usd` is numeric(10,6); we pass a float.

TD-008 (Sprint 5): agent_id is now resolved from the agent_registry table and
stored in ai_usage, enabling per-agent cost aggregation in dashboards.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client

    from app.gateway.schemas import GatewayResponse

logger = logging.getLogger("app.gateway.usage")

# Valid values for the ai_provider enum. Anything else is mapped to 'custom'.
_KNOWN_PROVIDERS = frozenset({"openai", "anthropic", "ollama", "custom"})


class UsageTracker:
    """Records AI usage to ai_usage. Errors are logged, never raised."""

    # Class-level cache: agent name → registry uuid (or None if not found).
    # agent_registry is only modified on deploy; a process-lifetime cache is safe.
    _agent_id_cache: dict[str, str | None] = {}

    def __init__(self, supabase: "Client") -> None:
        self._supabase = supabase

    async def _resolve_agent_id(self, agent_name: str) -> str | None:
        """
        Look up the agent_registry uuid for an agent name.

        Result is cached at class level. A DB error returns None (non-blocking).
        """
        if agent_name in self._agent_id_cache:
            return self._agent_id_cache[agent_name]

        try:
            result = (
                self._supabase.table("agent_registry")
                .select("id")
                .eq("name", agent_name)
                .limit(1)
                .execute()
            )
            agent_id: str | None = result.data[0]["id"] if result.data else None
        except Exception as exc:
            logger.warning("agent_id_lookup_failed agent=%s error=%s", agent_name, exc)
            agent_id = None

        self._agent_id_cache[agent_name] = agent_id
        return agent_id

    async def record(
        self,
        request_id: str,
        response: "GatewayResponse",
        user_id: str,
        agent_name: str | None = None,
    ) -> None:
        """Record AI usage. Errors are logged but never raised."""
        try:
            provider = response.provider_used
            if provider not in _KNOWN_PROVIDERS:
                provider = "custom"

            agent_id = await self._resolve_agent_id(agent_name) if agent_name else None

            row = {
                "id": request_id,
                "user_id": user_id,
                "agent_id": agent_id,
                "operation": agent_name or "gateway",
                "model": response.model_used,
                "provider": provider,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "cost_usd": float(response.usage.cost_usd),
                "latency_ms": response.latency_ms,
                "used_user_key": not response.used_platform_key,
            }
            self._supabase.table("ai_usage").insert(row).execute()
        except Exception as exc:
            logger.error("usage_tracking_failed request_id=%s error=%s", request_id, exc)
