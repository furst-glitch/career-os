"""
Routing type definitions: CostClass, ModelSpec, RoutingConfig.
All types are immutable (frozen dataclasses or enums).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CostClass(str, Enum):
    """Relative cost tier for a model selection. Used for pre-call budget estimation."""
    LOW = "low"        # haiku-class: ~$0.001/1K tokens
    MEDIUM = "medium"  # sonnet-class: ~$0.003/1K tokens
    HIGH = "high"      # opus-class: ~$0.015/1K tokens


@dataclass(frozen=True)
class ModelSpec:
    """
    Complete specification for a routed model selection.
    Immutable — created once at config build time.
    """
    provider: str
    model: str
    max_tokens: int
    timeout_seconds: int
    cost_class: CostClass
    fallback_provider: str | None = None
    fallback_model: str | None = None


@dataclass(frozen=True)
class RoutingConfig:
    """
    Complete routing configuration.

    plan_matrix: plan → capability → ModelSpec
    The special key "_default" in capability map is used when the specific
    capability is not mapped for a given plan.

    plan_allowed_models: plan → frozenset of allowed model names.
    Used to validate user overrides.
    """
    plan_matrix: dict[str, dict[str, ModelSpec]]
    plan_allowed_models: dict[str, frozenset[str]]

    def get_spec(self, plan: str, capability: str) -> ModelSpec:
        """
        Look up the ModelSpec for a plan/capability pair.
        Falls back through: specific plan→capability, plan→_default, free→_default.
        Never raises — always returns a valid ModelSpec.
        """
        plan_config = self.plan_matrix.get(plan) or self.plan_matrix["free"]
        return plan_config.get(capability) or plan_config["_default"]

    def is_model_allowed(self, plan: str, model: str) -> bool:
        """Check if a model is within a plan's allowed set."""
        allowed = self.plan_allowed_models.get(plan, frozenset())
        return model in allowed
