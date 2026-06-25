"""
Pricing repository interface and in-memory implementation.

The in-memory implementation serves two purposes:
1. Testing without database
2. Startup seed data before DB is available
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.gateway.schemas import ModelPricing


@runtime_checkable
class PricingRepositoryProtocol(Protocol):
    """
    Purpose: Abstract storage of model pricing data.
    Implementations: InMemoryPricingRepository (tests/dev), SupabasePricingRepository (prod).
    """

    async def get_pricing(self, model: str, provider: str) -> ModelPricing | None:
        """Return pricing for a model, or None if not found."""
        ...

    async def list_all(self) -> list[ModelPricing]:
        """Return all registered pricing entries."""
        ...


class InMemoryPricingRepository:
    """
    In-memory pricing repository.

    Thread-safe: yes (dict lookup, no mutation after init).
    Use for: tests, local development, application startup seed.
    """

    def __init__(self, entries: list[ModelPricing]) -> None:
        # Key: (model, provider) for O(1) lookup
        self._index: dict[tuple[str, str], ModelPricing] = {
            (p.model, p.provider): p for p in entries
        }

    async def get_pricing(self, model: str, provider: str) -> ModelPricing | None:
        return self._index.get((model, provider))

    async def list_all(self) -> list[ModelPricing]:
        return list(self._index.values())
