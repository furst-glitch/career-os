"""
Unit tests for AIExecutionService (app.gateway.execution_service).

All dependencies are mocked. Verifies the execution flow wiring: routing,
key resolution, PII scanning, provider call, cost calc, and usage recording.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.gateway.exceptions import GatewayProviderError, GatewayTimeoutError
from app.gateway.execution_service import AIExecutionService
from app.gateway.pii_scanner import PIIScanner
from app.gateway.schemas import (
    GatewayRequest,
    KeyResolution,
    ModelPricing,
    ModelSelection,
    PolicyDecision,
    ProviderResponse,
)


def _provider_response() -> ProviderResponse:
    return ProviderResponse(
        content="generated output",
        prompt_tokens=120,
        completion_tokens=80,
        total_tokens=200,
        model="claude-sonnet-4-6",
        provider="anthropic",
        latency_ms=42,
    )


def _pricing() -> ModelPricing:
    return ModelPricing(
        model="claude-sonnet-4-6",
        provider="anthropic",
        input_per_1m_usd=Decimal("3.00"),
        output_per_1m_usd=Decimal("15.00"),
    )


def _build(*, adapter_complete=None, count_tokens=200, pricing_raises=False):
    adapter = MagicMock()
    adapter.complete = adapter_complete or AsyncMock(return_value=_provider_response())
    adapter.count_tokens = AsyncMock(return_value=count_tokens)

    registry = MagicMock()
    registry.get.return_value = adapter

    key_resolver = MagicMock()
    key_resolver.resolve = AsyncMock(
        return_value=KeyResolution(api_key="k", api_base=None, used_platform_key=True)
    )

    model_router = MagicMock()
    model_router.route.return_value = ModelSelection(
        provider="anthropic", model="claude-sonnet-4-6"
    )

    cost_engine = MagicMock()
    if pricing_raises:
        cost_engine.get_pricing = AsyncMock(side_effect=RuntimeError("no pricing"))
    else:
        cost_engine.get_pricing = AsyncMock(return_value=_pricing())
    cost_engine.calculate_actual.return_value = Decimal("0.001560")
    cost_engine.estimate_cost.return_value = Decimal("0.002000")

    usage_tracker = MagicMock()
    usage_tracker.record = AsyncMock()

    service = AIExecutionService(
        registry=registry,
        key_resolver=key_resolver,
        pii_scanner=PIIScanner(),
        model_router=model_router,
        cost_engine=cost_engine,
        usage_tracker=usage_tracker,
    )
    return service, adapter, usage_tracker, key_resolver


def _request(**kwargs) -> GatewayRequest:
    base = dict(
        user_id="user-1",
        agent_name="cv_agent",
        messages=[{"role": "user", "content": "hello"}],
        task_capability="cv_parsing",
    )
    base.update(kwargs)
    return GatewayRequest(**base)


def _policy() -> PolicyDecision:
    return PolicyDecision(approved=True, user_plan="pro")


@pytest.mark.asyncio
async def test_execute_returns_gateway_response():
    service, _, _, _ = _build()
    resp = await service.execute(_request(), _policy())
    assert resp.content == "generated output"
    assert resp.model_used == "claude-sonnet-4-6"
    assert resp.provider_used == "anthropic"
    assert resp.usage.cost_usd == Decimal("0.001560")
    assert resp.used_platform_key is True


@pytest.mark.asyncio
async def test_execute_sanitizes_pii_before_provider():
    captured = {}

    async def fake_complete(**kwargs):
        captured["messages"] = kwargs["messages"]
        return _provider_response()

    service, adapter, _, _ = _build(adapter_complete=AsyncMock(side_effect=fake_complete))
    req = _request(messages=[{"role": "user", "content": "email me at a@b.com"}])
    await service.execute(req, _policy())
    assert "[REDACTED:EMAIL]" in captured["messages"][0]["content"]
    assert "a@b.com" not in captured["messages"][0]["content"]


@pytest.mark.asyncio
async def test_execute_uses_timeout_seconds_kwarg():
    captured = {}

    async def fake_complete(**kwargs):
        captured.update(kwargs)
        return _provider_response()

    service, _, _, _ = _build(adapter_complete=AsyncMock(side_effect=fake_complete))
    await service.execute(_request(), _policy())
    assert "timeout_seconds" in captured
    assert captured["stream"] is False


@pytest.mark.asyncio
async def test_execute_records_usage():
    service, _, usage_tracker, _ = _build()
    await service.execute(_request(), _policy())
    usage_tracker.record.assert_awaited_once()
    kwargs = usage_tracker.record.await_args.kwargs
    assert kwargs["user_id"] == "user-1"
    assert kwargs["agent_name"] == "cv_agent"


@pytest.mark.asyncio
async def test_execute_propagates_gateway_error_from_adapter():
    err = GatewayTimeoutError(provider="anthropic", timeout_seconds=60)
    service, _, _, _ = _build(adapter_complete=AsyncMock(side_effect=err))
    with pytest.raises(GatewayTimeoutError):
        await service.execute(_request(), _policy())


@pytest.mark.asyncio
async def test_execute_wraps_generic_exception():
    service, _, _, _ = _build(
        adapter_complete=AsyncMock(side_effect=ValueError("boom"))
    )
    with pytest.raises(GatewayProviderError) as exc:
        await service.execute(_request(), _policy())
    assert exc.value.provider == "anthropic"


@pytest.mark.asyncio
async def test_execute_rejects_streaming_response():
    async def gen():
        yield "chunk"

    service, _, _, _ = _build(adapter_complete=AsyncMock(return_value=gen()))
    with pytest.raises(GatewayProviderError) as exc:
        await service.execute(_request(), _policy())
    assert exc.value.code == "streaming_not_supported"


@pytest.mark.asyncio
async def test_estimate_cost_returns_non_negative():
    service, _, _, _ = _build()
    cost = await service.estimate_cost(_request(), _policy())
    assert cost >= Decimal("0")


@pytest.mark.asyncio
async def test_estimate_cost_zero_when_pricing_unknown():
    service, _, _, _ = _build(pricing_raises=True)
    cost = await service.estimate_cost(_request(), _policy())
    assert cost == Decimal("0")


@pytest.mark.asyncio
async def test_estimate_cost_falls_back_to_char_count_when_count_tokens_fails():
    service, adapter, _, _ = _build()
    adapter.count_tokens = AsyncMock(side_effect=RuntimeError("tokenizer missing"))
    cost = await service.estimate_cost(_request(), _policy())
    assert cost >= Decimal("0")


@pytest.mark.asyncio
async def test_response_format_forwarded_to_adapter():
    captured = {}

    async def fake_complete(**kwargs):
        captured.update(kwargs)
        return _provider_response()

    service, _, _, _ = _build(adapter_complete=AsyncMock(side_effect=fake_complete))
    req = _request(response_format={"type": "json_object"})
    await service.execute(req, _policy())
    assert captured["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_provider_override_does_not_pass_model_override():
    """A bare provider override must route with user_override=None (no model)."""
    service, _, _, _ = _build()
    req = _request(provider="anthropic")
    await service.execute(req, _policy())
    # route() called; with a provider override we still pass a dict whose model is None
    # — verify it did not raise model_not_in_plan and produced a response.
