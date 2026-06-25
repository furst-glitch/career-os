"""
CostEngine — AI cost calculation.

Purpose: Calculate AI costs for pre-call budget estimation and post-call accounting.
Responsibility: Arithmetic calculation only. No side effects.
Dependencies: PricingRepositoryProtocol (injected).
Limitations:
  - estimate_cost() assumes linear token usage at output_utilization ratio.
  - Pricing accuracy depends on repository data freshness.
  - Does not account for provider discounts or volume pricing.

Performance: calculate_actual() completes in <100 microseconds (pure arithmetic).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.gateway.cost.repository import PricingRepositoryProtocol
from app.gateway.exceptions import GatewayConfigError
from app.gateway.schemas import ModelPricing

_MILLION = Decimal("1_000_000")
_QUANTIZE = Decimal("0.000001")  # 6 decimal places for USD


class CostEngine:
    """
    Calculates AI costs.

    Two modes:
    - calculate_actual(): post-call with exact token counts → for billing
    - estimate_cost(): pre-call with estimated tokens → for budget gate

    Thread-safe: yes (no mutable state).
    """

    def __init__(self, repository: PricingRepositoryProtocol) -> None:
        self._repository = repository

    def calculate_actual(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        pricing: ModelPricing,
    ) -> Decimal:
        """
        Calculate exact cost from actual token counts.

        Pure arithmetic — no I/O. Call this after a completed AI request.
        Result is rounded to 6 decimal places (sub-cent precision).
        """
        input_cost = Decimal(prompt_tokens) * pricing.input_per_1m_usd / _MILLION
        output_cost = Decimal(completion_tokens) * pricing.output_per_1m_usd / _MILLION
        return (input_cost + output_cost).quantize(_QUANTIZE, rounding=ROUND_HALF_UP)

    def estimate_cost(
        self,
        estimated_prompt_tokens: int,
        max_output_tokens: int,
        pricing: ModelPricing,
        output_utilization: float = 0.7,
    ) -> Decimal:
        """
        Estimate cost before a call for budget pre-check.

        Uses output_utilization (default 70%) to estimate likely completion length.
        Intentionally conservative: overestimates to avoid budget overrun.

        Pure arithmetic — no I/O.
        """
        if not (0.0 < output_utilization <= 1.0):
            raise ValueError(
                f"output_utilization must be in (0, 1], got {output_utilization}"
            )
        estimated_completion = int(max_output_tokens * output_utilization)
        return self.calculate_actual(estimated_prompt_tokens, estimated_completion, pricing)

    async def get_pricing(self, model: str, provider: str) -> ModelPricing:
        """
        Fetch pricing from the repository.

        Raises GatewayConfigError if no pricing entry exists for the model.
        Call this once per request; cache the result for estimate + actual calculations.
        """
        pricing = await self._repository.get_pricing(model, provider)
        if pricing is None:
            raise GatewayConfigError(
                f"No pricing found for model {model!r} (provider: {provider!r}). "
                "Add an entry to the model_pricing table.",
                code="pricing_not_found",
            )
        return pricing
