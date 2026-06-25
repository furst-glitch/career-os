"""
Unit tests for UsageTracker (app.gateway.usage_tracker).

Supabase is mocked. Verifies the INSERT payload maps to the actual ai_usage
schema and that failures are swallowed.
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
    def __init__(self, raise_on_insert=False):
        self.inserted: dict | None = None
        self._raise = raise_on_insert

    def table(self, name):
        assert name == "ai_usage"
        return self

    def insert(self, row):
        if self._raise:
            raise RuntimeError("db down")
        self.inserted = row
        return self

    def execute(self):
        return MagicMock(data=[self.inserted])


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
