"""
Default routing configuration — the canonical plan→capability→model matrix.

These are constants, not loaded from the database. The DB version
(plan_capabilities table, Sprint 5) may override these at startup, but these
defaults must always work standalone so the Gateway can route without a DB.

Inner dicts are wrapped in MappingProxyType so the returned RoutingConfig is
effectively immutable (read-only views — mutation raises TypeError).
"""

from __future__ import annotations

from types import MappingProxyType

from app.gateway.routing.types import CostClass, ModelSpec, RoutingConfig

# Anthropic models
HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"
OPUS = "claude-opus-4-8"

# OpenAI models
GPT4O = "gpt-4o"
GPT4O_MINI = "gpt-4o-mini"

# Gemini models
GEMINI_FLASH = "gemini-2.0-flash"
GEMINI_PRO = "gemini-1.5-pro"

_ANTHROPIC = "anthropic"

# Capabilities considered "chat / quick" — routed to a cheaper, faster model on pro.
_QUICK_CAPABILITIES: frozenset[str] = frozenset({"chat", "interview_prep"})

# Capabilities considered "heavy analysis" — routed to opus on professional/enterprise.
_HEAVY_CAPABILITIES: frozenset[str] = frozenset(
    {"contract_analysis", "document_review", "multi_agent_review"}
)

# Full capability list (used to materialise enterprise's all-opus matrix).
_ALL_CAPABILITIES: tuple[str, ...] = (
    "chat",
    "cv_parsing",
    "cv_generation",
    "contract_analysis",
    "agreement_analysis",
    "payslip_extraction",
    "job_matching",
    "interview_prep",
    "salary_negotiation",
    "career_coaching",
    "document_review",
    "multi_agent_review",
)


def _haiku_spec() -> ModelSpec:
    return ModelSpec(
        provider=_ANTHROPIC,
        model=HAIKU,
        max_tokens=2048,
        timeout_seconds=30,
        cost_class=CostClass.LOW,
    )


def _sonnet_spec(max_tokens: int, timeout_seconds: int) -> ModelSpec:
    return ModelSpec(
        provider=_ANTHROPIC,
        model=SONNET,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        cost_class=CostClass.MEDIUM,
    )


def _opus_spec() -> ModelSpec:
    return ModelSpec(
        provider=_ANTHROPIC,
        model=OPUS,
        max_tokens=8192,
        timeout_seconds=120,
        cost_class=CostClass.HIGH,
    )


def _build_free() -> dict[str, ModelSpec]:
    """All capabilities → haiku."""
    return {"_default": _haiku_spec()}


def _build_pro() -> dict[str, ModelSpec]:
    """Standard → sonnet (4096/60s); chat & quick tasks → haiku (30s)."""
    matrix: dict[str, ModelSpec] = {"_default": _sonnet_spec(max_tokens=4096, timeout_seconds=60)}
    haiku = _haiku_spec()
    for cap in _QUICK_CAPABILITIES:
        matrix[cap] = haiku
    return matrix


def _build_professional() -> dict[str, ModelSpec]:
    """Default → sonnet (8192/90s); heavy analysis → opus (8192/120s)."""
    matrix: dict[str, ModelSpec] = {"_default": _sonnet_spec(max_tokens=8192, timeout_seconds=90)}
    opus = _opus_spec()
    for cap in _HEAVY_CAPABILITIES:
        matrix[cap] = opus
    return matrix


def _build_enterprise() -> dict[str, ModelSpec]:
    """Same shape as professional, but opus is available for every capability."""
    opus = _opus_spec()
    matrix: dict[str, ModelSpec] = {"_default": opus}
    for cap in _ALL_CAPABILITIES:
        matrix[cap] = opus
    return matrix


def build_default_routing_config() -> RoutingConfig:
    """
    Build the canonical default RoutingConfig.

    Inner capability maps are wrapped in MappingProxyType (read-only).
    Returns a fresh RoutingConfig on every call (no shared mutable state).
    """
    plan_matrix: dict[str, dict[str, ModelSpec]] = {
        "free": MappingProxyType(_build_free()),          # type: ignore[dict-item]
        "pro": MappingProxyType(_build_pro()),            # type: ignore[dict-item]
        "professional": MappingProxyType(_build_professional()),  # type: ignore[dict-item]
        "enterprise": MappingProxyType(_build_enterprise()),      # type: ignore[dict-item]
    }

    plan_allowed_models: dict[str, frozenset[str]] = {
        "free": frozenset({HAIKU}),
        "pro": frozenset({HAIKU, SONNET}),
        "professional": frozenset({HAIKU, SONNET, OPUS}),
        "enterprise": frozenset(
            {HAIKU, SONNET, OPUS, GPT4O, GPT4O_MINI, GEMINI_FLASH, GEMINI_PRO}
        ),
    }

    return RoutingConfig(
        plan_matrix=plan_matrix,
        plan_allowed_models=plan_allowed_models,
    )
