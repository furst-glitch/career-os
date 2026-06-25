"""Tests for CostEngine — all branches plus performance."""

from __future__ import annotations

import time
from decimal import Decimal

import pytest

from app.gateway.cost.cost_engine import CostEngine
from app.gateway.cost.repository import InMemoryPricingRepository
from app.gateway.exceptions import GatewayConfigError
from app.gateway.schemas import ModelPricing

SONNET_PRICING = ModelPricing(
    model="claude-sonnet-4-6",
    provider="anthropic",
    input_per_1m_usd=Decimal("3.00"),
    output_per_1m_usd=Decimal("15.00"),
)


@pytest.fixture
def engine() -> CostEngine:
    return CostEngine(InMemoryPricingRepository([SONNET_PRICING]))


# --------------------------------------------------------------------------- #
# calculate_actual
# --------------------------------------------------------------------------- #

def test_calculate_actual_known_values(engine: CostEngine) -> None:
    # 1000 input * 3/1M + 500 output * 15/1M = 0.003 + 0.0075 = 0.0105
    result = engine.calculate_actual(1000, 500, SONNET_PRICING)
    assert result == Decimal("0.010500")


def test_calculate_actual_zero_prompt_tokens(engine: CostEngine) -> None:
    result = engine.calculate_actual(0, 500, SONNET_PRICING)
    assert result == Decimal("0.007500")


def test_calculate_actual_zero_completion_tokens(engine: CostEngine) -> None:
    result = engine.calculate_actual(1000, 0, SONNET_PRICING)
    assert result == Decimal("0.003000")


def test_calculate_actual_both_zero(engine: CostEngine) -> None:
    result = engine.calculate_actual(0, 0, SONNET_PRICING)
    assert result == Decimal("0.000000")


def test_calculate_actual_returns_decimal(engine: CostEngine) -> None:
    result = engine.calculate_actual(123, 456, SONNET_PRICING)
    assert isinstance(result, Decimal)


def test_calculate_actual_rounded_to_six_places(engine: CostEngine) -> None:
    # 1 token input → 3/1M = 0.000003 exactly; check exponent is -6.
    result = engine.calculate_actual(1, 1, SONNET_PRICING)
    assert result.as_tuple().exponent == -6


# --------------------------------------------------------------------------- #
# estimate_cost
# --------------------------------------------------------------------------- #

def test_estimate_cost_default_utilization(engine: CostEngine) -> None:
    # 1000 prompt, max 1000 output, 0.7 util → 700 output
    # 0.003 + 700*15/1M = 0.003 + 0.0105 = 0.0135
    result = engine.estimate_cost(1000, 1000, SONNET_PRICING)
    assert result == Decimal("0.013500")


def test_estimate_cost_custom_utilization(engine: CostEngine) -> None:
    # 0.5 util → 500 output → 0.003 + 0.0075 = 0.0105
    result = engine.estimate_cost(1000, 1000, SONNET_PRICING, output_utilization=0.5)
    assert result == Decimal("0.010500")


def test_estimate_cost_utilization_one(engine: CostEngine) -> None:
    # 1.0 util → full 1000 output → 0.003 + 0.015 = 0.018
    result = engine.estimate_cost(1000, 1000, SONNET_PRICING, output_utilization=1.0)
    assert result == Decimal("0.018000")


def test_estimate_cost_invalid_utilization_above_one(engine: CostEngine) -> None:
    with pytest.raises(ValueError, match="output_utilization"):
        engine.estimate_cost(1000, 1000, SONNET_PRICING, output_utilization=1.5)


def test_estimate_cost_invalid_utilization_zero(engine: CostEngine) -> None:
    with pytest.raises(ValueError, match="output_utilization"):
        engine.estimate_cost(1000, 1000, SONNET_PRICING, output_utilization=0.0)


def test_estimate_cost_invalid_utilization_negative(engine: CostEngine) -> None:
    with pytest.raises(ValueError, match="output_utilization"):
        engine.estimate_cost(1000, 1000, SONNET_PRICING, output_utilization=-0.1)


# --------------------------------------------------------------------------- #
# get_pricing
# --------------------------------------------------------------------------- #

async def test_get_pricing_delegates_to_repository(engine: CostEngine) -> None:
    pricing = await engine.get_pricing("claude-sonnet-4-6", "anthropic")
    assert pricing is SONNET_PRICING


async def test_get_pricing_raises_when_not_found(engine: CostEngine) -> None:
    with pytest.raises(GatewayConfigError) as exc_info:
        await engine.get_pricing("unknown-model", "anthropic")
    assert exc_info.value.code == "pricing_not_found"


async def test_get_pricing_wrong_provider_raises(engine: CostEngine) -> None:
    with pytest.raises(GatewayConfigError):
        await engine.get_pricing("claude-sonnet-4-6", "openai")


# --------------------------------------------------------------------------- #
# Performance
# --------------------------------------------------------------------------- #

def test_calculate_actual_under_100_microseconds() -> None:
    engine = CostEngine(InMemoryPricingRepository([]))
    pricing = ModelPricing(
        "claude-sonnet-4-6", "anthropic", Decimal("3.00"), Decimal("15.00")
    )
    iterations = 10_000
    start = time.perf_counter()
    for _ in range(iterations):
        engine.calculate_actual(1000, 500, pricing)
    avg_us = (time.perf_counter() - start) / iterations * 1_000_000
    assert avg_us < 100, f"Expected <100us, got {avg_us:.1f}us"
