"""Tests for InMemoryPricingRepository and the PricingRepositoryProtocol contract."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.gateway.cost.defaults import build_default_pricing_repository
from app.gateway.cost.repository import (
    InMemoryPricingRepository,
    PricingRepositoryProtocol,
)
from app.gateway.schemas import ModelPricing

ENTRY_A = ModelPricing("model-a", "anthropic", Decimal("1.0"), Decimal("2.0"))
ENTRY_B = ModelPricing("model-b", "openai", Decimal("3.0"), Decimal("4.0"))


@pytest.fixture
def repo() -> InMemoryPricingRepository:
    return InMemoryPricingRepository([ENTRY_A, ENTRY_B])


async def test_get_pricing_found(repo: InMemoryPricingRepository) -> None:
    result = await repo.get_pricing("model-a", "anthropic")
    assert result is ENTRY_A


async def test_get_pricing_not_found_returns_none(repo: InMemoryPricingRepository) -> None:
    assert await repo.get_pricing("nope", "anthropic") is None


async def test_list_all_returns_all_entries(repo: InMemoryPricingRepository) -> None:
    entries = await repo.list_all()
    assert len(entries) == 2
    assert ENTRY_A in entries
    assert ENTRY_B in entries


async def test_empty_repository() -> None:
    repo = InMemoryPricingRepository([])
    assert await repo.get_pricing("anything", "anthropic") is None
    assert await repo.list_all() == []


async def test_lookup_is_case_sensitive(repo: InMemoryPricingRepository) -> None:
    assert await repo.get_pricing("MODEL-A", "anthropic") is None
    assert await repo.get_pricing("model-a", "Anthropic") is None


def test_is_valid_protocol_instance(repo: InMemoryPricingRepository) -> None:
    assert isinstance(repo, PricingRepositoryProtocol)


async def test_same_model_different_providers_are_distinct() -> None:
    a = ModelPricing("dup", "anthropic", Decimal("1"), Decimal("1"))
    b = ModelPricing("dup", "openai", Decimal("2"), Decimal("2"))
    repo = InMemoryPricingRepository([a, b])
    assert await repo.get_pricing("dup", "anthropic") is a
    assert await repo.get_pricing("dup", "openai") is b


async def test_default_pricing_repository_has_known_models() -> None:
    repo = build_default_pricing_repository()
    sonnet = await repo.get_pricing("claude-sonnet-4-6", "anthropic")
    assert sonnet is not None
    assert sonnet.input_per_1m_usd == Decimal("3.00")
    all_entries = await repo.list_all()
    assert len(all_entries) >= 9
