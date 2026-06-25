"""
Integration tests for AIGateway (app.gateway.gateway).

Wires real PIIScanner, ModelRouter, CostEngine, KeyResolver, ProviderRegistry,
UsageTracker, AuditWriter and a real AIPolicyService — mocking only at the
provider (adapter) boundary and the Supabase/cache infrastructure.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.gateway.audit_writer import AuditWriter
from app.gateway.cost.cost_engine import CostEngine
from app.gateway.cost.defaults import build_default_pricing_repository
from app.gateway.exceptions import GatewayPolicyError
from app.gateway.execution_service import AIExecutionService
from app.gateway.gateway import AIGateway
from app.gateway.key_resolver import KeyResolver
from app.gateway.pii_scanner import PIIScanner
from app.gateway.policy_service import AIPolicyService
from app.gateway.providers.registry import ProviderRegistry
from app.gateway.routing.defaults import build_default_routing_config
from app.gateway.routing.model_router import ModelRouter
from app.gateway.schemas import GatewayRequest, ProviderResponse
from app.gateway.usage_tracker import UsageTracker

# ── Infrastructure mocks ──────────────────────────────────────────────────────


def _provider_response(content="Hello from Claude") -> ProviderResponse:
    return ProviderResponse(
        content=content,
        prompt_tokens=100,
        completion_tokens=40,
        total_tokens=140,
        model="claude-sonnet-4-6",
        provider="anthropic",
        latency_ms=33,
    )


def _make_adapter(complete_mock):
    adapter = MagicMock()
    adapter.name = "anthropic"
    adapter.complete = complete_mock
    adapter.count_tokens = AsyncMock(return_value=100)
    return adapter


class _Cache:
    """Minimal in-memory async cache implementing the methods PolicyService uses."""

    def __init__(self):
        self._store = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ttl=300):
        self._store[key] = value

    async def delete(self, key):
        self._store.pop(key, None)

    async def get_int(self, key):
        return int(self._store.get(key, 0))

    async def increment(self, key, expire_seconds=60):
        self._store[key] = int(self._store.get(key, 0)) + 1
        return self._store[key]

    async def increment_by(self, key, amount, expire_seconds=300):
        self._store[key] = int(self._store.get(key, 0)) + amount
        return self._store[key]


class _Supabase:
    """
    Routes table reads to canned data and records inserts/rpc calls.
    Used by PolicyService (subscriptions/plan_capabilities/ai_budgets) and the
    UsageTracker/AuditWriter inserts.
    """

    def __init__(self, plan="pro", budget=None, capability=None):
        self._plan = plan
        self._budget = budget
        self._capability = capability
        self.inserts: dict[str, list] = {}
        self.rpc_calls = []

    def table(self, name):
        return _Table(self, name)

    def rpc(self, fn, params):
        self.rpc_calls.append((fn, params))
        return MagicMock()


class _Table:
    def __init__(self, sb, name):
        self._sb = sb
        self._name = name

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def single(self):
        return self

    def insert(self, row):
        self._sb.inserts.setdefault(self._name, []).append(row)
        return self

    def execute(self):
        if self._name == "subscriptions":
            return SimpleNamespace(data={"plan": self._sb._plan} if self._sb._plan else None)
        if self._name == "plan_capabilities":
            return SimpleNamespace(data=self._sb._capability)
        if self._name == "ai_budgets":
            return SimpleNamespace(data=self._sb._budget)
        return SimpleNamespace(data=[])


def _settings():
    return SimpleNamespace(
        anthropic_api_key="sk-ant-platform",
        openai_api_key=None,
        gemini_api_key=None,
        ollama_base_url=None,
    )


def _build_gateway(supabase, cache, complete_mock):
    registry = ProviderRegistry().register(_make_adapter(complete_mock))
    execution = AIExecutionService(
        registry=registry,
        key_resolver=KeyResolver(supabase=supabase, settings=_settings()),
        pii_scanner=PIIScanner(),
        model_router=ModelRouter(config=build_default_routing_config()),
        cost_engine=CostEngine(repository=build_default_pricing_repository()),
        usage_tracker=UsageTracker(supabase=supabase),
    )
    return AIGateway(
        policy_service=AIPolicyService(supabase=supabase, cache=cache),
        execution_service=execution,
        audit_writer=AuditWriter(supabase=supabase),
    )


def _request(**kwargs) -> GatewayRequest:
    base = dict(
        user_id="11111111-1111-1111-1111-111111111111",
        agent_name="cv_agent",
        messages=[{"role": "user", "content": "Write my CV"}],
        task_capability="cv_parsing",
    )
    base.update(kwargs)
    return GatewayRequest(**base)


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_gateway_flow_success():
    complete = AsyncMock(return_value=_provider_response())
    supabase = _Supabase(plan="pro", budget=None)
    cache = _Cache()
    gateway = _build_gateway(supabase, cache, complete)

    resp = await gateway.complete(_request())

    assert resp.content == "Hello from Claude"
    assert resp.provider_used == "anthropic"
    assert resp.usage.total_tokens == 140
    # Usage recorded + audit written.
    assert "ai_usage" in supabase.inserts
    assert "audit_logs" in supabase.inserts
    assert supabase.inserts["audit_logs"][0]["action"] == "gateway.request.success"


@pytest.mark.asyncio
async def test_gateway_denies_on_policy_rejection():
    complete = AsyncMock(return_value=_provider_response())
    # Capability disabled for the plan → denial.
    supabase = _Supabase(
        plan="free", capability={"enabled": False, "requests_per_minute": None, "requests_per_day": None}
    )
    cache = _Cache()
    gateway = _build_gateway(supabase, cache, complete)

    with pytest.raises(GatewayPolicyError) as exc:
        await gateway.complete(_request())
    assert exc.value.code == "capability_not_in_plan"
    complete.assert_not_called()
    # Denial audited.
    assert supabase.inserts["audit_logs"][0]["action"] == "gateway.request.policy_denied"


@pytest.mark.asyncio
async def test_gateway_releases_reservation_on_provider_error():
    complete = AsyncMock(side_effect=ValueError("provider exploded"))
    supabase = _Supabase(plan="pro")
    cache = _Cache()
    gateway = _build_gateway(supabase, cache, complete)

    with pytest.raises(Exception):
        await gateway.complete(_request())

    # Reservation must be released back to ~0 (estimate added then subtracted).
    reservation = await cache.get_int(
        "gateway:budget:reservation:11111111-1111-1111-1111-111111111111"
    )
    assert reservation == 0


@pytest.mark.asyncio
async def test_gateway_pii_in_request_is_redacted_before_provider():
    captured = {}

    async def fake_complete(**kwargs):
        captured["messages"] = kwargs["messages"]
        return _provider_response()

    supabase = _Supabase(plan="pro")
    cache = _Cache()
    gateway = _build_gateway(supabase, cache, AsyncMock(side_effect=fake_complete))

    await gateway.complete(
        _request(messages=[{"role": "user", "content": "CPR 010190-1234 email a@b.com"}])
    )
    sent = captured["messages"][0]["content"]
    assert "010190-1234" not in sent
    assert "a@b.com" not in sent
    assert "[REDACTED:CPR]" in sent
    assert "[REDACTED:EMAIL]" in sent


def test_build_gateway_factory_wires_a_complete_gateway():
    """build_gateway() returns a usable AIGateway with all collaborators wired."""
    from app.gateway.factory import build_gateway

    mock_settings = SimpleNamespace(
        anthropic_api_key="sk-ant-test",
        openai_api_key=None,
        gemini_api_key=None,
        ollama_base_url=None,
    )
    gateway = build_gateway(_Supabase(plan="pro"), _Cache(), settings=mock_settings)
    assert isinstance(gateway, AIGateway)
    # Internals wired (smoke check on private attributes).
    assert gateway._policy is not None
    assert gateway._execution is not None
    assert gateway._audit is not None


@pytest.mark.asyncio
async def test_gateway_budget_warning_propagated_in_response_metadata():
    complete = AsyncMock(return_value=_provider_response())
    # Spend at 90% of a non-hard limit → warning, still approved.
    supabase = _Supabase(
        plan="pro",
        budget={"current_spend_usd": "9.0", "monthly_limit_usd": "10.0", "hard_limit": False},
    )
    cache = _Cache()
    gateway = _build_gateway(supabase, cache, complete)

    resp = await gateway.complete(_request())
    assert resp.metadata.get("budget_warning") is True
