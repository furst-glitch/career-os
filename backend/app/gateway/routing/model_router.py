"""
ModelRouter — pure decision engine for AI model selection.

Purpose: Route incoming requests to the optimal model given plan, capability, and constraints.
Responsibility: Decision-making only. No I/O, no side effects, no state mutation.
Dependencies: RoutingConfig (injected at construction time).
Limitations: Config must be injected externally. Not responsible for config freshness.

Performance: Designed for >100,000 decisions/second. All operations are dict lookups.
"""

from __future__ import annotations

from app.gateway.exceptions import GatewayConfigError
from app.gateway.routing.types import CostClass, ModelSpec, RoutingConfig
from app.gateway.schemas import ModelSelection


class ModelRouter:
    """
    Routes AI requests to the optimal model.

    Thread-safe: yes (immutable config, no state mutation).
    Instantiate once, share freely.
    """

    def __init__(self, config: RoutingConfig) -> None:
        self._config = config

    def route(
        self,
        plan: str,
        capability: str,
        agent_name: str,  # Reserved for future agent-specific overrides
        stream: bool = False,
        user_override: dict[str, str] | None = None,
    ) -> ModelSelection:
        """
        Determine the optimal model selection for a request.

        Args:
            plan: User's subscription plan (free/pro/professional/enterprise)
            capability: Task capability identifier (cv_parsing, chat, etc.)
            agent_name: Originating agent name (not used in routing yet — reserved)
            stream: Whether streaming is requested (passed through to output)
            user_override: Optional {"provider": ..., "model": ...} from user

        Returns:
            ModelSelection with provider, model, fallback, timeout, max_tokens, cost_class

        Raises:
            GatewayConfigError: If user_override requests a model outside their plan
        """
        spec = self._config.get_spec(plan, capability)

        # Validate and apply user override if present
        if user_override:
            override_model = user_override.get("model")
            override_provider = user_override.get("provider")
            if override_model and not self._config.is_model_allowed(plan, override_model):
                raise GatewayConfigError(
                    f"Model {override_model!r} is not available on plan {plan!r}",
                    code="model_not_in_plan",
                )
            if override_model:
                spec = ModelSpec(
                    provider=override_provider or spec.provider,
                    model=override_model,
                    max_tokens=spec.max_tokens,
                    timeout_seconds=spec.timeout_seconds,
                    cost_class=self._derive_cost_class(override_model),
                    fallback_provider=spec.fallback_provider,
                    fallback_model=spec.fallback_model,
                )

        return ModelSelection(
            provider=spec.provider,
            model=spec.model,
            fallback_provider=spec.fallback_provider,
            fallback_model=spec.fallback_model,
            was_degraded=False,  # Set by caller if fallback was used
        )

    def _derive_cost_class(self, model: str) -> CostClass:
        """Derive CostClass from model name. Used when user supplies an override model."""
        model_lower = model.lower()
        if any(t in model_lower for t in ("haiku", "mini", "flash", "nano")):
            return CostClass.LOW
        if any(t in model_lower for t in ("opus", "pro", "1.5-pro", "4-8", "4-7")):
            return CostClass.HIGH
        return CostClass.MEDIUM
