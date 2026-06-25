"""
Unit tests for AIPolicyService (app.gateway.policy_service).

No network, no Redis, no database — Supabase and CacheService are mocked.
Target: 95%+ coverage of AIPolicyService.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.gateway.policy_service import AIPolicyService, _reservation_key
from app.gateway.schemas import PolicyDecision

# ── Supabase mock helpers ──────────────────────────────────────────────────


def _query_result(data):
    """
    Build a mock for a Supabase query chain:
        table().select().eq()[.eq()].single().execute().data == data
    Supports both single and chained .eq() calls.
    """
    execute_mock = MagicMock()
    execute_mock.data = data

    single_mock = MagicMock()
    single_mock.execute.return_value = execute_mock

    eq_mock = MagicMock()
    eq_mock.single.return_value = single_mock
    eq_mock.eq.return_value = eq_mock  # chained .eq()

    select_mock = MagicMock()
    select_mock.eq.return_value = eq_mock

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock
    return table_mock


class _SupabaseMock:
    """
    Routes .table(name) to a per-table query result, and records .rpc() calls.
    """

    def __init__(self, tables: dict[str, object], rpc_raises: bool = False):
        self._tables = tables
        self.rpc_calls: list[tuple[str, dict]] = []
        self._rpc_raises = rpc_raises

    def table(self, name: str):
        if name not in self._tables:
            raise KeyError(f"unexpected table {name!r}")
        return self._tables[name]

    def rpc(self, fn: str, params: dict):
        self.rpc_calls.append((fn, params))
        rpc_obj = MagicMock()
        if self._rpc_raises:
            rpc_obj.execute.side_effect = RuntimeError("db down")
        return rpc_obj


def make_supabase(
    *,
    plan="pro",
    plan_raises=False,
    capability=None,
    capability_raises=False,
    budget=None,
    budget_raises=False,
    rpc_raises=False,
):
    """Construct a Supabase mock with configurable per-table behaviour."""
    tables: dict[str, object] = {}

    # subscriptions
    sub_table = _query_result({"plan": plan} if plan is not None else None)
    if plan_raises:
        sub_table.select.return_value.eq.return_value.single.return_value.execute.side_effect = (
            RuntimeError("db down")
        )
    tables["subscriptions"] = sub_table

    # plan_capabilities
    cap_table = _query_result(capability)
    if capability_raises:
        cap_table.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.side_effect = (
            RuntimeError("db down")
        )
    tables["plan_capabilities"] = cap_table

    # ai_budgets
    budget_table = _query_result(budget)
    if budget_raises:
        budget_table.select.return_value.eq.return_value.single.return_value.execute.side_effect = (
            RuntimeError("db down")
        )
    tables["ai_budgets"] = budget_table

    return _SupabaseMock(tables, rpc_raises=rpc_raises)


@pytest.fixture
def mock_cache():
    """A cache mock that misses by default and allows all rate/budget ops."""
    cache = AsyncMock()
    cache.get.return_value = None       # cache miss
    cache.set.return_value = None
    cache.delete.return_value = None
    cache.increment.return_value = 1    # first request in window
    cache.increment_by.return_value = 0
    cache.get_int.return_value = 0      # no reservations
    return cache


def make_service(supabase, cache):
    return AIPolicyService(supabase=supabase, cache=cache)


# A capability row helper.
def cap_row(enabled=True, rpm=10, rpd=100):
    return {"enabled": enabled, "requests_per_minute": rpm, "requests_per_day": rpd}


# A budget row helper.
def budget_row(spend="0", limit="10", hard=True):
    return {
        "current_spend_usd": spend,
        "monthly_limit_usd": limit,
        "hard_limit": hard,
    }


# ── TestAIPolicyServiceEvaluate ─────────────────────────────────────────────


class TestAIPolicyServiceEvaluate:
    async def test_approved_pro_user_known_capability(self, mock_cache):
        supabase = make_supabase(
            plan="pro",
            capability=cap_row(enabled=True),
            budget=budget_row(spend="1", limit="10"),
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        assert isinstance(decision, PolicyDecision)
        assert decision.approved is True
        assert decision.user_plan == "pro"
        assert decision.denial_code is None

    async def test_denied_free_user_pro_capability(self, mock_cache):
        supabase = make_supabase(
            plan="free",
            capability=cap_row(enabled=False, rpm=None, rpd=None),
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "contract_analysis")
        assert decision.approved is False
        assert decision.denial_code == "capability_not_in_plan"
        assert decision.user_plan == "free"

    async def test_approved_free_user_free_capability(self, mock_cache):
        supabase = make_supabase(
            plan="free",
            capability=cap_row(enabled=True, rpm=5, rpd=100),
            budget=None,  # no budget row → unlimited
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "chat")
        assert decision.approved is True
        assert decision.user_plan == "free"

    async def test_denied_rate_limited_returns_correct_code(self, mock_cache):
        # increment returns above the per-minute limit.
        mock_cache.increment.return_value = 6
        supabase = make_supabase(
            plan="free",
            capability=cap_row(enabled=True, rpm=5, rpd=100),
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "chat")
        assert decision.approved is False
        assert decision.denial_code == "rate_limited"

    async def test_denied_budget_exceeded_hard_limit(self, mock_cache):
        supabase = make_supabase(
            plan="pro",
            capability=cap_row(enabled=True),
            budget=budget_row(spend="10", limit="10", hard=True),
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        assert decision.approved is False
        assert decision.denial_code == "budget_exceeded"

    async def test_budget_warning_at_80_percent(self, mock_cache):
        supabase = make_supabase(
            plan="pro",
            capability=cap_row(enabled=True),
            budget=budget_row(spend="8", limit="10", hard=True),
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        assert decision.approved is True
        assert decision.budget_warning is True

    async def test_budget_no_warning_below_80_percent(self, mock_cache):
        supabase = make_supabase(
            plan="pro",
            capability=cap_row(enabled=True),
            budget=budget_row(spend="5", limit="10", hard=True),
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        assert decision.approved is True
        assert decision.budget_warning is False

    async def test_soft_limit_over_budget_still_allowed(self, mock_cache):
        # hard_limit False → over budget is allowed but warns.
        supabase = make_supabase(
            plan="pro",
            capability=cap_row(enabled=True),
            budget=budget_row(spend="20", limit="10", hard=False),
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        assert decision.approved is True
        assert decision.budget_warning is True

    async def test_plan_lookup_failure_defaults_to_free(self, mock_cache):
        supabase = make_supabase(
            plan_raises=True,
            capability=cap_row(enabled=True),
            budget=None,
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "chat")
        assert decision.user_plan == "free"
        assert decision.approved is True

    async def test_budget_lookup_failure_allows_request(self, mock_cache):
        supabase = make_supabase(
            plan="pro",
            capability=cap_row(enabled=True),
            budget_raises=True,
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        assert decision.approved is True

    async def test_redis_unavailable_allows_request(self, mock_cache):
        # Both the cache reads and the rate-limit increment raise.
        mock_cache.get.side_effect = RuntimeError("redis down")
        mock_cache.set.side_effect = RuntimeError("redis down")
        mock_cache.increment.side_effect = RuntimeError("redis down")
        mock_cache.get_int.side_effect = RuntimeError("redis down")
        supabase = make_supabase(
            plan="pro",
            capability=cap_row(enabled=True, rpm=5),
            budget=budget_row(spend="1", limit="10"),
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        assert decision.approved is True

    async def test_no_budget_entry_allows_unlimited(self, mock_cache):
        supabase = make_supabase(
            plan="pro",
            capability=cap_row(enabled=True),
            budget=None,
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        assert decision.approved is True
        assert decision.budget_warning is False

    async def test_unknown_capability_denied_fail_closed(self, mock_cache):
        # Sprint 5: plan_capabilities has no row → deny with unknown_capability code.
        supabase = make_supabase(
            plan="pro",
            capability=None,  # DB returns no row
            budget=None,
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "some_new_capability")
        assert decision.approved is False
        assert decision.denial_code == "unknown_capability"

    async def test_capability_db_error_fails_open(self, mock_cache):
        # DB infrastructure failure → fail open (infra problem, not a policy decision).
        supabase = make_supabase(
            plan="pro",
            capability_raises=True,
            budget=None,
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        assert decision.approved is True

    async def test_enterprise_plan_allows_all_capabilities(self, mock_cache):
        supabase = make_supabase(
            plan="enterprise",
            capability=cap_row(enabled=True, rpm=None, rpd=None),
            budget=None,
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "multi_agent_review")
        assert decision.approved is True
        assert decision.user_plan == "enterprise"
        # Unlimited rpm → no rate-limit increment performed.
        mock_cache.increment.assert_not_called()

    async def test_cache_hit_avoids_db_call_for_plan(self, mock_cache):
        # Cached plan returned from cache.get for the plan key.
        async def get_side_effect(key):
            if key == "policy:plan:u1":
                return "professional"
            return None

        mock_cache.get.side_effect = get_side_effect
        supabase = make_supabase(
            plan="SHOULD_NOT_BE_USED",
            capability=cap_row(enabled=True),
            budget=None,
        )
        # Make the subscriptions lookup explode if called.
        supabase._tables["subscriptions"].select.return_value.eq.return_value.single.return_value.execute.side_effect = AssertionError(
            "subscriptions table should not be queried on cache hit"
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        assert decision.user_plan == "professional"

    async def test_capability_cache_hit_returns_entry(self, mock_cache):
        async def get_side_effect(key):
            if key == "policy:cap:pro:cv_generation":
                return {"enabled": True, "requests_per_minute": 7, "requests_per_day": 70}
            return None

        mock_cache.get.side_effect = get_side_effect
        supabase = make_supabase(plan="pro", budget=None)
        # plan_capabilities should not be queried on cache hit.
        supabase._tables["plan_capabilities"].select.return_value.eq.return_value.eq.return_value.single.return_value.execute.side_effect = AssertionError(
            "plan_capabilities should not be queried on cache hit"
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        assert decision.approved is True

    async def test_budget_cache_hit_avoids_db(self, mock_cache):
        # Budget served from cache (string-encoded Decimals + bool).
        async def get_side_effect(key):
            if key == "policy:budget:u1":
                return {"current_spend": "9", "monthly_limit": "10", "hard_limit": True}
            return None

        mock_cache.get.side_effect = get_side_effect
        supabase = make_supabase(plan="pro", capability=cap_row(enabled=True))
        # ai_budgets must NOT be queried when budget is cached.
        supabase._tables["ai_budgets"].select.return_value.eq.return_value.single.return_value.execute.side_effect = AssertionError(
            "ai_budgets should not be queried on cache hit"
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        # 9/10 → allowed with warning, no DB hit.
        assert decision.approved is True
        assert decision.budget_warning is True

    async def test_capability_disabled_cache_hit_denies(self, mock_cache):
        async def get_side_effect(key):
            if key == "policy:cap:free:contract_analysis":
                return {"enabled": False, "requests_per_minute": None, "requests_per_day": None}
            return None

        mock_cache.get.side_effect = get_side_effect
        supabase = make_supabase(plan="free")
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "contract_analysis")
        assert decision.approved is False
        assert decision.denial_code == "capability_not_in_plan"


# ── TestBudgetReservation ───────────────────────────────────────────────────


class TestBudgetReservation:
    async def test_reserve_budget_calls_increment(self, mock_cache):
        supabase = make_supabase()
        svc = make_service(supabase, mock_cache)
        await svc.reserve_budget("u1", Decimal("0.50"))
        mock_cache.increment_by.assert_awaited_once()
        args, kwargs = mock_cache.increment_by.call_args
        assert args[0] == _reservation_key("u1")
        assert args[1] == 500_000  # 0.50 USD in micro-cents

    async def test_reserve_budget_zero_cost_is_noop(self, mock_cache):
        supabase = make_supabase()
        svc = make_service(supabase, mock_cache)
        await svc.reserve_budget("u1", Decimal("0"))
        mock_cache.increment_by.assert_not_called()

    async def test_reserve_budget_negative_cost_is_noop(self, mock_cache):
        supabase = make_supabase()
        svc = make_service(supabase, mock_cache)
        await svc.reserve_budget("u1", Decimal("-1"))
        mock_cache.increment_by.assert_not_called()

    async def test_reserve_budget_redis_failure_does_not_raise(self, mock_cache):
        mock_cache.increment_by.side_effect = RuntimeError("redis down")
        supabase = make_supabase()
        svc = make_service(supabase, mock_cache)
        # Must not raise.
        await svc.reserve_budget("u1", Decimal("0.25"))

    async def test_release_reservation_decrements_and_updates_db(self, mock_cache):
        supabase = make_supabase()
        svc = make_service(supabase, mock_cache)
        await svc.release_budget_reservation("u1", Decimal("0.50"), Decimal("0.42"))

        # Reservation decremented by the estimate (negative amount).
        args, kwargs = mock_cache.increment_by.call_args
        assert args[0] == _reservation_key("u1")
        assert args[1] == -500_000

        # DB updated with the actual cost via RPC.
        assert supabase.rpc_calls
        fn, params = supabase.rpc_calls[0]
        assert fn == "increment_ai_spend"
        assert params["p_user_id"] == "u1"
        assert params["p_amount"] == pytest.approx(0.42)

        # Cached budget invalidated.
        mock_cache.delete.assert_awaited_with("policy:budget:u1")

    async def test_release_reservation_zero_cost_is_noop(self, mock_cache):
        supabase = make_supabase()
        svc = make_service(supabase, mock_cache)
        await svc.release_budget_reservation("u1", Decimal("0"), Decimal("0"))
        mock_cache.increment_by.assert_not_called()
        assert supabase.rpc_calls == []

    async def test_release_reservation_db_failure_does_not_raise(self, mock_cache):
        supabase = make_supabase(rpc_raises=True)
        svc = make_service(supabase, mock_cache)
        # Must swallow the DB error.
        await svc.release_budget_reservation("u1", Decimal("0.10"), Decimal("0.10"))

    async def test_release_reservation_redis_failure_does_not_raise(self, mock_cache):
        mock_cache.increment_by.side_effect = RuntimeError("redis down")
        supabase = make_supabase()
        svc = make_service(supabase, mock_cache)
        await svc.release_budget_reservation("u1", Decimal("0.10"), Decimal("0.10"))
        # DB still updated despite the redis failure.
        assert supabase.rpc_calls

    async def test_release_reservation_cache_invalidation_failure_does_not_raise(
        self, mock_cache
    ):
        mock_cache.delete.side_effect = RuntimeError("redis down")
        supabase = make_supabase()
        svc = make_service(supabase, mock_cache)
        # delete() raising during cache invalidation must be swallowed.
        await svc.release_budget_reservation("u1", Decimal("0.10"), Decimal("0.10"))
        assert supabase.rpc_calls


# ── Reservations folded into budget check ───────────────────────────────────


class TestBudgetWithReservations:
    async def test_reservation_pushes_over_hard_limit(self, mock_cache):
        # Spend 9 of 10, plus a 2.00 reservation → over the hard limit.
        mock_cache.get_int.return_value = 2_000_000  # 2.00 USD in micro-cents
        supabase = make_supabase(
            plan="pro",
            capability=cap_row(enabled=True),
            budget=budget_row(spend="9", limit="10", hard=True),
        )
        svc = make_service(supabase, mock_cache)
        decision = await svc.evaluate("u1", "cv_generation")
        assert decision.approved is False
        assert decision.denial_code == "budget_exceeded"


# ── Protocol conformance ────────────────────────────────────────────────────


def test_implements_policy_service_protocol():
    from app.gateway.interfaces import PolicyServiceProtocol

    svc = AIPolicyService(supabase=MagicMock(), cache=AsyncMock())
    assert isinstance(svc, PolicyServiceProtocol)
