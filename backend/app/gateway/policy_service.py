"""
AIPolicyService — fast, cached gateway policy evaluation.

Purpose: Evaluate all policy gates before an AI request is allowed.
Responsibility: Plan gate, capability gate, rate-limit gate, budget gate.
Dependencies: Supabase (plan/capability/budget lookup), CacheService
              (rate limiting + budget reservation; Redis with in-memory fallback).

Limitations:
  - Budget check is eventually consistent — reservations prevent overrun but
    are not 100% atomic against concurrent multi-instance writes.
  - Rate limit degrades to per-process in-memory counters when Redis is down.
  - Capability/plan caches mean changes propagate within their TTL window.

Fail-safe philosophy:
  - Plan lookup failure   → assume "free" (least privilege).
  - Capability lookup fail → fail OPEN (allow) for better UX; log warning.
  - Budget lookup failure  → fail OPEN (allow); log warning.
  - Redis unavailable      → rate limit & reservation degrade to allow; log.
  Never crash the request path on a policy-infrastructure error.

Performance target: <10ms cached paths, <50ms uncached paths.

Implements PolicyServiceProtocol (app.gateway.interfaces).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from app.gateway.schemas import PolicyDecision

if TYPE_CHECKING:
    from supabase import Client

    from app.services.cache_service import _MemoryCache, _RedisCache

    CacheLike = _MemoryCache | _RedisCache

logger = logging.getLogger("app.gateway.policy")

# Cache TTLs (seconds)
_TTL_PLAN = 60
_TTL_CAPABILITIES = 300
_TTL_BUDGET = 30

# Budget reservation precision: micro-cents (1 USD = 1,000,000 micro-cents).
# Stored as an integer in Redis so reservations use atomic INCRBY.
_MICRO_CENTS_PER_USD = Decimal("1000000")

# Budget warning fires at this fraction of the monthly limit.
_BUDGET_WARNING_FRACTION = Decimal("0.8")

# Reservation key TTL — a reservation auto-expires if never released.
_RESERVATION_TTL = 300


@dataclass
class _CapabilityEntry:
    enabled: bool
    requests_per_minute: int | None
    requests_per_day: int | None


def _reservation_key(user_id: str) -> str:
    return f"gateway:budget:reservation:{user_id}"


class AIPolicyService:
    """Fast, cached gateway policy evaluation. No AI I/O."""

    def __init__(self, supabase: "Client", cache: "CacheLike") -> None:
        self._supabase = supabase
        self._cache = cache

    # ── Public API ─────────────────────────────────────────────────────────

    async def evaluate(
        self,
        user_id: str,
        task_capability: str,
    ) -> PolicyDecision:
        """
        Evaluate all policy gates for a user and capability.

        Order: plan → capability → rate limit → budget.
        Short-circuits on the first denial.
        """
        # 1. Resolve the user's plan.
        plan = await self._get_user_plan(user_id)

        # 2. Capability gate. Unknown capability → permissive (None entry).
        capability_entry = await self._get_capability_entry(plan, task_capability)
        if capability_entry is not None and not capability_entry.enabled:
            return PolicyDecision(
                approved=False,
                user_plan=plan,
                denial_reason=(
                    f"Capability '{task_capability}' is not available on the "
                    f"'{plan}' plan. Upgrade to unlock it."
                ),
                denial_code="capability_not_in_plan",
            )

        # 3. Rate-limit gate (per-minute window).
        rpm_limit = capability_entry.requests_per_minute if capability_entry else None
        rate_ok, retry_after = await self._check_rate_limit(user_id, rpm_limit)
        if not rate_ok:
            return PolicyDecision(
                approved=False,
                user_plan=plan,
                denial_reason=(
                    f"Request rate limit exceeded. Retry in {retry_after}s."
                ),
                denial_code="rate_limited",
            )

        # 4. Budget gate.
        budget_ok, budget_warning = await self._check_budget(user_id)
        if not budget_ok:
            return PolicyDecision(
                approved=False,
                user_plan=plan,
                denial_reason="Monthly AI budget exceeded.",
                denial_code="budget_exceeded",
            )

        return PolicyDecision(
            approved=True,
            user_plan=plan,
            budget_warning=budget_warning,
        )

    async def reserve_budget(
        self,
        user_id: str,
        estimated_cost_usd: Decimal,
    ) -> None:
        """
        Pre-deduct an estimated cost into the Redis budget reservation.

        Called AFTER evaluate() approves a request and BEFORE the AI call, to
        guard against the budget race condition between concurrent requests.
        The reservation auto-expires after _RESERVATION_TTL seconds and is
        reconciled by release_budget_reservation().
        """
        if estimated_cost_usd <= Decimal("0"):
            return

        micro_cents = int(estimated_cost_usd * _MICRO_CENTS_PER_USD)
        try:
            await self._cache.increment_by(
                _reservation_key(user_id), micro_cents, expire_seconds=_RESERVATION_TTL
            )
        except Exception:
            logger.warning(
                "budget_reservation_failed user=%s cost=%s",
                user_id,
                estimated_cost_usd,
            )

    async def release_budget_reservation(
        self,
        user_id: str,
        estimated_cost_usd: Decimal,
        actual_cost_usd: Decimal,
    ) -> None:
        """
        Release a reservation and persist the actual cost to ai_budgets.

        Called AFTER the AI call completes. The reserved estimate is given back
        (decrement) and the actual spend is committed to the DB via the
        increment_ai_spend RPC.
        """
        # Give back the estimated reservation.
        if estimated_cost_usd > Decimal("0"):
            micro_cents = int(estimated_cost_usd * _MICRO_CENTS_PER_USD)
            try:
                await self._cache.increment_by(
                    _reservation_key(user_id),
                    -micro_cents,
                    expire_seconds=_RESERVATION_TTL,
                )
            except Exception:
                logger.warning("budget_reservation_release_failed user=%s", user_id)

        # Commit the actual cost to the DB.
        if actual_cost_usd > Decimal("0"):
            try:
                self._supabase.rpc(
                    "increment_ai_spend",
                    {"p_user_id": user_id, "p_amount": float(actual_cost_usd)},
                ).execute()
            except Exception:
                logger.error(
                    "budget_db_update_failed user=%s actual=%s",
                    user_id,
                    actual_cost_usd,
                )

        # Invalidate the cached budget snapshot so the next read reflects the spend.
        try:
            await self._cache.delete(f"policy:budget:{user_id}")
        except Exception:
            pass

    # ── Private helpers ────────────────────────────────────────────────────

    async def _get_user_plan(self, user_id: str) -> str:
        """Get the user's subscription plan. Cached _TTL_PLAN seconds."""
        cache_key = f"policy:plan:{user_id}"

        try:
            cached = await self._cache.get(cache_key)
            if cached:
                return str(cached)
        except Exception:
            pass

        try:
            result = (
                self._supabase.table("subscriptions")
                .select("plan")
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            plan = result.data["plan"] if result.data else "free"
        except Exception:
            logger.warning("plan_lookup_failed_defaulting_to_free user=%s", user_id)
            plan = "free"

        try:
            await self._cache.set(cache_key, plan, ttl=_TTL_PLAN)
        except Exception:
            pass

        return plan

    async def _get_capability_entry(
        self,
        plan: str,
        capability: str,
    ) -> _CapabilityEntry | None:
        """
        Get the capability config for a plan. Cached _TTL_CAPABILITIES seconds.

        Returns None when the capability is not configured for the plan, which
        the caller treats as permissive (allow unknown capabilities).
        """
        cache_key = f"policy:cap:{plan}:{capability}"

        try:
            cached = await self._cache.get(cache_key)
            if isinstance(cached, dict):
                return _CapabilityEntry(
                    enabled=cached["enabled"],
                    requests_per_minute=cached.get("requests_per_minute"),
                    requests_per_day=cached.get("requests_per_day"),
                )
        except Exception:
            pass

        try:
            result = (
                self._supabase.table("plan_capabilities")
                .select("enabled, requests_per_minute, requests_per_day")
                .eq("plan", plan)
                .eq("capability", capability)
                .single()
                .execute()
            )
            if not result.data:
                return None
            entry = _CapabilityEntry(
                enabled=result.data["enabled"],
                requests_per_minute=result.data.get("requests_per_minute"),
                requests_per_day=result.data.get("requests_per_day"),
            )
        except Exception:
            # Table missing or DB error — fail open.
            logger.warning(
                "capability_lookup_failed_allowing plan=%s cap=%s", plan, capability
            )
            return None

        try:
            await self._cache.set(
                cache_key,
                {
                    "enabled": entry.enabled,
                    "requests_per_minute": entry.requests_per_minute,
                    "requests_per_day": entry.requests_per_day,
                },
                ttl=_TTL_CAPABILITIES,
            )
        except Exception:
            pass

        return entry

    async def _check_rate_limit(
        self,
        user_id: str,
        rpm_limit: int | None,
    ) -> tuple[bool, int]:
        """
        Per-minute fixed-window rate limit using an atomic counter.

        Returns (allowed, retry_after_seconds). Fails open (allow) if the cache
        backend errors.
        """
        if rpm_limit is None:
            return True, 0

        window = int(time.time() // 60)
        key = f"rate:req:{user_id}:min:{window}"

        try:
            current = await self._cache.increment(key, expire_seconds=120)
        except Exception:
            logger.warning("rate_limit_cache_unavailable user=%s", user_id)
            return True, 0

        if current > rpm_limit:
            retry_after = 60 - (int(time.time()) % 60)
            return False, retry_after
        return True, 0

    async def _check_budget(self, user_id: str) -> tuple[bool, bool]:
        """
        Check the user's budget, including outstanding Redis reservations.

        Returns (allowed, budget_warning). Fails open (allow) if the DB errors.
        A missing budget row means the user is treated as unlimited.
        """
        cache_key = f"policy:budget:{user_id}"
        current_spend: Decimal
        monthly_limit: Decimal
        hard_limit: bool

        cached_loaded = False
        try:
            cached = await self._cache.get(cache_key)
            if isinstance(cached, dict):
                current_spend = Decimal(str(cached["current_spend"]))
                monthly_limit = Decimal(str(cached["monthly_limit"]))
                hard_limit = bool(cached["hard_limit"])
                cached_loaded = True
        except Exception:
            pass

        if not cached_loaded:
            try:
                result = (
                    self._supabase.table("ai_budgets")
                    .select("current_spend_usd, monthly_limit_usd, hard_limit")
                    .eq("user_id", user_id)
                    .single()
                    .execute()
                )
                if not result.data:
                    return True, False  # No budget row → unlimited.

                current_spend = Decimal(str(result.data["current_spend_usd"]))
                monthly_limit = Decimal(str(result.data["monthly_limit_usd"]))
                hard_limit = bool(result.data["hard_limit"])

                try:
                    await self._cache.set(
                        cache_key,
                        {
                            "current_spend": str(current_spend),
                            "monthly_limit": str(monthly_limit),
                            "hard_limit": hard_limit,
                        },
                        ttl=_TTL_BUDGET,
                    )
                except Exception:
                    pass
            except Exception:
                logger.warning("budget_lookup_failed_allowing user=%s", user_id)
                return True, False

        # Fold in outstanding reservations.
        try:
            reservation_micro_cents = await self._cache.get_int(_reservation_key(user_id))
            reservation_usd = Decimal(reservation_micro_cents) / _MICRO_CENTS_PER_USD
        except Exception:
            reservation_usd = Decimal("0")

        total_committed = current_spend + reservation_usd

        if hard_limit and monthly_limit > Decimal("0") and total_committed >= monthly_limit:
            return False, False

        warning = (
            monthly_limit > Decimal("0")
            and total_committed >= monthly_limit * _BUDGET_WARNING_FRACTION
        )
        return True, warning
