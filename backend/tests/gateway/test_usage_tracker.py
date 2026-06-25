"""
Unit tests for UsageTracker (app.gateway.usage_tracker).

Supabase is mocked. Verifies the INSERT payload maps to the actual ai_usage
schema and that failures are swallowed.

TD-008 (Sprint 5): agent_id is now resolved from agent_registry and stored
in the ai_usage row. Tests verify the lookup, class-level caching, and
graceful degradation on DB errors.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.gateway.schemas import GatewayResponse, GatewayUsage
from app.gateway.usage_tracker import UsageTracker


def _response(provider="anthropic", used_platform_key=True) -> GatewayResponse:
    usage = GatewayUsage(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd=Decimal("0.001234"),
        latency_ms=321,
        model="claude-sonnet-4-6",
        provider=provider,
    )
    return GatewayResponse(
        content="hi",
        usage=usage,
        request_id="11111111-1111-1111-1111-111111111111",
        model_used="claude-sonnet-4-6",
        provider_used=provider,
        latency_ms=321,
        used_platform_key=used_platform_key,
    )


class _SupabaseSpy:
    """
    Minimal Supabase mock for UsageTracker tests.

    Routes table("ai_usage") to insert capture.
    Routes table("agent_registry") to a configurable lookup result.
    """

    def __init__(
        self,
        raise_on_insert: bool = False,
        agent_registry_data: list | None = None,
        raise_on_registry_lookup: bool = False,
    ):
        self.inserted: dict | None = None
        self._raise_on_insert = raise_on_insert
        self._registry_data = agent_registry_data if agent_registry_data is not None else []
        self._raise_on_registry = raise_on_registry_lookup
        self._registry_lookup_count = 0

    def table(self, name: str):
        if name == "agent_registry":
            return _RegistryTable(self)
        assert name == "ai_usage", f"unexpected table: {name!r}"
        return _UsageTable(self)


class _RegistryTable:
    def __init__(self, spy: _SupabaseSpy):
        self._spy = spy

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        self._spy._registry_lookup_count += 1
        if self._spy._raise_on_registry:
            raise RuntimeError("registry db down")
        return MagicMock(data=self._spy._registry_data)


class _UsageTable:
    def __init__(self, spy: _SupabaseSpy):
        self._spy = spy

    def insert(self, row):
        if self._spy._raise_on_insert:
            raise RuntimeError("db down")
        self._spy.inserted = row
        return self

    def execute(self):
        return MagicMock(data=[self._spy.inserted])


@pytest.fixture(autouse=True)
def clear_agent_id_cache():
    """Clear the class-level agent_id cache before each test to prevent cross-contamination."""
    UsageTracker._agent_id_cache.clear()
    yield
    UsageTracker._agent_id_cache.clear()


@pytest.mark.asyncio
async def test_record_inserts_correct_fields():
    spy = _SupabaseSpy()
    tracker = UsageTracker(spy)
    await tracker.record(
        request_id="11111111-1111-1111-1111-111111111111",
        response=_response(),
        user_id="user-1",
        agent_name="cv_agent",
    )
    row = spy.inserted
    assert row["id"] == "11111111-1111-1111-1111-111111111111"
    assert row["user_id"] == "user-1"
    assert row["operation"] == "cv_agent"
    assert row["model"] == "claude-sonnet-4-6"
    assert row["provider"] == "anthropic"
    assert row["prompt_tokens"] == 100
    assert row["completion_tokens"] == 50
    assert row["total_tokens"] == 150
    assert row["latency_ms"] == 321


@pytest.mark.asyncio
async def test_record_cost_is_float():
    spy = _SupabaseSpy()
    tracker = UsageTracker(spy)
    await tracker.record("11111111-1111-1111-1111-111111111111", _response(), "u")
    assert isinstance(spy.inserted["cost_usd"], float)
    assert spy.inserted["cost_usd"] == pytest.approx(0.001234)


@pytest.mark.asyncio
async def test_used_user_key_is_inverse_of_platform_key():
    spy = _SupabaseSpy()
    tracker = UsageTracker(spy)
    await tracker.record(
        "11111111-1111-1111-1111-111111111111",
        _response(used_platform_key=False),
        "u",
    )
    assert spy.inserted["used_user_key"] is True

    spy2 = _SupabaseSpy()
    tracker2 = UsageTracker(spy2)
    await tracker2.record(
        "11111111-1111-1111-1111-111111111111",
        _response(used_platform_key=True),
        "u",
    )
    assert spy2.inserted["used_user_key"] is False


@pytest.mark.asyncio
async def test_unknown_provider_coerced_to_custom():
    spy = _SupabaseSpy()
    tracker = UsageTracker(spy)
    await tracker.record(
        "11111111-1111-1111-1111-111111111111",
        _response(provider="gemini"),
        "u",
    )
    assert spy.inserted["provider"] == "custom"


@pytest.mark.asyncio
async def test_record_does_not_raise_on_db_error():
    spy = _SupabaseSpy(raise_on_insert=True)
    tracker = UsageTracker(spy)
    # Must not raise.
    await tracker.record("11111111-1111-1111-1111-111111111111", _response(), "u")


@pytest.mark.asyncio
async def test_agent_name_defaults_to_gateway():
    spy = _SupabaseSpy()
    tracker = UsageTracker(spy)
    await tracker.record(
        "11111111-1111-1111-1111-111111111111", _response(), "u", agent_name=None
    )
    assert spy.inserted["operation"] == "gateway"
    assert spy.inserted["agent_id"] is None


# ── TD-008: agent_id resolution ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_id_resolved_from_registry():
    """agent_id in the INSERT row matches the uuid from agent_registry."""
    registry_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    spy = _SupabaseSpy(agent_registry_data=[{"id": registry_uuid}])
    tracker = UsageTracker(spy)
    await tracker.record(
        "11111111-1111-1111-1111-111111111111",
        _response(),
        "user-1",
        agent_name="cv_agent",
    )
    assert spy.inserted["agent_id"] == registry_uuid


@pytest.mark.asyncio
async def test_agent_id_is_none_when_not_in_registry():
    """agent_id is NULL if the agent name has no entry in agent_registry."""
    spy = _SupabaseSpy(agent_registry_data=[])  # empty → not found
    tracker = UsageTracker(spy)
    await tracker.record(
        "11111111-1111-1111-1111-111111111111",
        _response(),
        "user-1",
        agent_name="unknown_agent",
    )
    assert spy.inserted["agent_id"] is None


@pytest.mark.asyncio
async def test_agent_id_is_none_on_registry_db_error():
    """agent_id is NULL if the agent_registry lookup raises — does not propagate."""
    spy = _SupabaseSpy(raise_on_registry_lookup=True)
    tracker = UsageTracker(spy)
    # Must not raise.
    await tracker.record(
        "11111111-1111-1111-1111-111111111111",
        _response(),
        "user-1",
        agent_name="cv_agent",
    )
    assert spy.inserted["agent_id"] is None


@pytest.mark.asyncio
async def test_agent_id_cache_prevents_redundant_lookups():
    """Second call with same agent name uses the class-level cache, not the DB."""
    registry_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    spy = _SupabaseSpy(agent_registry_data=[{"id": registry_uuid}])
    tracker = UsageTracker(spy)

    await tracker.record("rid-1", _response(), "u1", agent_name="cv_agent")
    await tracker.record("rid-2", _response(), "u2", agent_name="cv_agent")

    # registry was only queried once (second call hits cache).
    assert spy._registry_lookup_count == 1
    assert spy.inserted["agent_id"] == registry_uuid
