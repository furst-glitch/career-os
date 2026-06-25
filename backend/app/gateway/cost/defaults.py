"""
Default model pricing data.
Prices are per 1M tokens in USD.
Source: Published provider pricing pages (2026-06).
Update: When providers change pricing, update the model_pricing DB table — not this file.
This file is a development/test fallback only.
"""

from decimal import Decimal

from app.gateway.cost.repository import InMemoryPricingRepository
from app.gateway.schemas import ModelPricing

PRICING_TABLE: list[ModelPricing] = [
    # Anthropic
    ModelPricing(
        model="claude-haiku-4-5-20251001",
        provider="anthropic",
        input_per_1m_usd=Decimal("0.80"),
        output_per_1m_usd=Decimal("4.00"),
    ),
    ModelPricing(
        model="claude-sonnet-4-6",
        provider="anthropic",
        input_per_1m_usd=Decimal("3.00"),
        output_per_1m_usd=Decimal("15.00"),
    ),
    ModelPricing(
        model="claude-opus-4-8",
        provider="anthropic",
        input_per_1m_usd=Decimal("15.00"),
        output_per_1m_usd=Decimal("75.00"),
    ),
    ModelPricing(
        model="claude-fable-5",
        provider="anthropic",
        input_per_1m_usd=Decimal("3.00"),
        output_per_1m_usd=Decimal("15.00"),
    ),
    # OpenAI
    ModelPricing(
        model="gpt-4o",
        provider="openai",
        input_per_1m_usd=Decimal("2.50"),
        output_per_1m_usd=Decimal("10.00"),
    ),
    ModelPricing(
        model="gpt-4o-mini",
        provider="openai",
        input_per_1m_usd=Decimal("0.15"),
        output_per_1m_usd=Decimal("0.60"),
    ),
    # Google Gemini
    ModelPricing(
        model="gemini-2.0-flash",
        provider="gemini",
        input_per_1m_usd=Decimal("0.10"),
        output_per_1m_usd=Decimal("0.40"),
    ),
    ModelPricing(
        model="gemini-1.5-pro",
        provider="gemini",
        input_per_1m_usd=Decimal("3.50"),
        output_per_1m_usd=Decimal("10.50"),
    ),
    # Ollama — no cost (self-hosted)
    ModelPricing(
        model="llama3.2",
        provider="ollama",
        input_per_1m_usd=Decimal("0.00"),
        output_per_1m_usd=Decimal("0.00"),
    ),
]


def build_default_pricing_repository() -> InMemoryPricingRepository:
    """Build the default in-memory pricing repository from PRICING_TABLE."""
    return InMemoryPricingRepository(PRICING_TABLE)
