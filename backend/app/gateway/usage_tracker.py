"""
UsageTracker — records AI usage to the database after each Gateway request.

Purpose: Persist usage data for billing, analytics, and budget enforcement.
Responsibility: INSERT to ai_usage. Non-critical path — errors are logged, not raised.
Dependencies: Supabase (ai_usage table).
Limitations: Async fire-and-forget. Not guaranteed delivery if process crashes mid-write.

Schema notes (from 00012_ai_cost_management.sql):
  - ai_usage has NO `agent_name` column. It has `agent_id` (uuid FK to
    agent_registry, nullable) and `operation` (text NOT NULL). The Gateway only
    knows the agent's *name* string, not its registry uuid, so we store the name
    in `operation` and leave `agent_id` NULL.
  - `provider` is the `ai_provider` enum: ('openai','anthropic','ollama','custom').
    Any provider outside that set (e.g. 'gemini') is coerced to 'custom' so the
    INSERT does not violate the enum constraint.
  - `cost_usd` is numeric(10,6); we pass a float.
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

    def __init__(self, supabase: "Client") -> None:
        self._supabase = supabase

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

            row = {
                "id": request_id,
                "user_id": user_id,
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
