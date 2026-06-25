"""
AI Gateway internal data schemas.
These are internal types — not API response models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class GatewayRequest:
    """Incoming request to the AI Gateway."""

    user_id: str
    agent_name: str
    messages: list[dict[str, str]]
    task_capability: str
    stream: bool = False
    provider: str | None = None          # Override provider selection
    temperature: float | None = None     # Override temperature
    max_tokens: int | None = None        # Override max tokens
    response_format: dict | None = None  # e.g. {"type": "json_object"}
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayUsage:
    """Token usage from a completed AI request."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: Decimal = field(default_factory=lambda: Decimal("0"))
    latency_ms: int = 0
    model: str = ""
    provider: str = ""


@dataclass
class GatewayResponse:
    """Response from the AI Gateway."""

    content: str
    usage: GatewayUsage
    request_id: str
    model_used: str
    provider_used: str
    latency_ms: int
    used_platform_key: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyDecision:
    """Result of policy engine evaluation."""

    approved: bool
    user_plan: str
    denial_reason: str | None = None    # Set if approved=False
    denial_code: str | None = None      # Machine-readable code
    budget_warning: bool = False        # True if >80% budget used


@dataclass
class ModelSelection:
    """Result of model routing."""

    provider: str
    model: str
    fallback_provider: str | None = None
    fallback_model: str | None = None
    was_degraded: bool = False          # True if plan forced downgrade


@dataclass
class KeyResolution:
    """Result of API key resolution."""

    api_key: str | None
    api_base: str | None                # For Ollama
    used_platform_key: bool             # False = BYOK


@dataclass
class PIIScanResult:
    """Result of PII scanning."""

    has_pii: bool
    scan_types_found: list[str]         # e.g. ["CPR", "IBAN"]
    sanitized_text: str                 # Text with PII redacted


@dataclass
class ProviderResponse:
    """Normalized response from a provider adapter."""

    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    provider: str
    latency_ms: int


@dataclass
class ModelPricing:
    """Pricing for a specific model."""

    model: str
    provider: str
    input_per_1m_usd: Decimal
    output_per_1m_usd: Decimal
