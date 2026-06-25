"""
AIExecutionService — executes AI requests through the provider stack.

Purpose: Bind KeyResolver, PIIScanner, ModelRouter, ProviderRegistry, CostEngine,
         and UsageTracker into a single execution flow.
Responsibility: Execute one AI request. No policy decisions (those are PolicyService's job).
Dependencies: All above components (injected).
Limitations:
  - Streaming responses: this implementation handles non-streaming only for Sprint 4.
    Streaming is contracted in the interface but raises if the adapter returns a
    streaming response (future work tracked in technical debt).
"""

from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from app.gateway.exceptions import GatewayError, GatewayProviderError
from app.gateway.schemas import GatewayResponse, GatewayUsage

if TYPE_CHECKING:
    from app.gateway.cost.cost_engine import CostEngine
    from app.gateway.key_resolver import KeyResolver
    from app.gateway.pii_scanner import PIIScanner
    from app.gateway.providers.registry import ProviderRegistry
    from app.gateway.routing.model_router import ModelRouter
    from app.gateway.schemas import GatewayRequest, PolicyDecision
    from app.gateway.usage_tracker import UsageTracker

logger = logging.getLogger("app.gateway.execution")


class AIExecutionService:
    """
    Executes an AI request through the full provider stack.
    Thread-safe: yes (all dependencies are stateless or thread-safe).
    """

    def __init__(
        self,
        registry: "ProviderRegistry",
        key_resolver: "KeyResolver",
        pii_scanner: "PIIScanner",
        model_router: "ModelRouter",
        cost_engine: "CostEngine",
        usage_tracker: "UsageTracker",
    ) -> None:
        self._registry = registry
        self._key_resolver = key_resolver
        self._pii_scanner = pii_scanner
        self._model_router = model_router
        self._cost_engine = cost_engine
        self._usage_tracker = usage_tracker

    def _route(self, request: "GatewayRequest", policy: "PolicyDecision"):
        """
        Route the request to a model.

        Only pass a user_override when a concrete model override exists. A bare
        provider override (no model) must NOT trigger ModelRouter's
        model-not-in-plan validation, so we leave user_override=None in that case.
        """
        user_override = None
        if request.provider:
            user_override = {"provider": request.provider, "model": None}
        return self._model_router.route(
            plan=policy.user_plan,
            capability=request.task_capability,
            agent_name=request.agent_name,
            stream=request.stream,
            user_override=user_override,
        )

    async def execute(
        self,
        request: "GatewayRequest",
        policy: "PolicyDecision",
    ) -> GatewayResponse:
        """
        Execute a gateway request through the full provider stack.

        Flow:
        1. Route to model (determines provider).
        2. Resolve API key for that provider.
        3. Scan messages for PII (sanitize).
        4. Get pricing + adapter.
        5. Call provider adapter.
        6. Calculate actual cost.
        7. Record usage (fire-and-forget).
        8. Return GatewayResponse.

        Budget reservation/release is handled by AIGateway (the caller).
        """
        request_id = str(uuid.uuid4())
        start = time.monotonic()

        # 1. Route first, so we know which provider's key to resolve.
        model_selection = self._route(request, policy)

        # 2. Resolve API key (platform-first) for the routed provider.
        key = await self._key_resolver.resolve(model_selection.provider, request.user_id)

        # 3. PII scan — sanitize before anything reaches the provider.
        sanitized_messages, pii_result = self._pii_scanner.scan_messages(
            request.messages, agent_name=request.agent_name
        )
        if pii_result.has_pii:
            logger.info(
                "pii_redacted request_id=%s types=%s agent=%s",
                request_id,
                pii_result.scan_types_found,
                request.agent_name,
            )

        # 4. Adapter + pricing.
        adapter = self._registry.get(model_selection.provider)
        pricing = await self._cost_engine.get_pricing(
            model_selection.model, model_selection.provider
        )

        # 5. Call provider.
        extra_kwargs: dict = {}
        if request.response_format:
            extra_kwargs["response_format"] = request.response_format
        try:
            provider_response = await adapter.complete(
                messages=sanitized_messages,
                model=model_selection.model,
                stream=False,  # Sprint 4: streaming deferred
                temperature=request.temperature if request.temperature is not None else 0.5,
                max_tokens=request.max_tokens or 2048,
                timeout_seconds=60,
                api_key=key.api_key,
                api_base=key.api_base,
                **extra_kwargs,
            )
        except GatewayError:
            raise  # Already normalized by adapter
        except Exception as exc:
            raise GatewayProviderError(str(exc), provider=model_selection.provider) from exc

        # Streaming responses are AsyncGenerators (no .content) — unsupported here.
        if not hasattr(provider_response, "content"):
            raise GatewayProviderError(
                "Streaming not yet supported in Gateway (Sprint 4)",
                provider=model_selection.provider,
                code="streaming_not_supported",
            )

        # 6. Calculate actual cost.
        actual_cost = self._cost_engine.calculate_actual(
            prompt_tokens=provider_response.prompt_tokens,
            completion_tokens=provider_response.completion_tokens,
            pricing=pricing,
        )

        latency_ms = int((time.monotonic() - start) * 1000)

        usage = GatewayUsage(
            prompt_tokens=provider_response.prompt_tokens,
            completion_tokens=provider_response.completion_tokens,
            total_tokens=provider_response.total_tokens,
            cost_usd=actual_cost,
            latency_ms=latency_ms,
            model=provider_response.model,
            provider=provider_response.provider,
        )

        response = GatewayResponse(
            content=provider_response.content,
            usage=usage,
            request_id=request_id,
            model_used=provider_response.model,
            provider_used=provider_response.provider,
            latency_ms=latency_ms,
            used_platform_key=key.used_platform_key,
        )

        # 7. Record usage (non-critical path — errors logged, not raised).
        await self._usage_tracker.record(
            request_id=request_id,
            response=response,
            user_id=request.user_id,
            agent_name=request.agent_name,
        )

        return response

    async def estimate_cost(
        self,
        request: "GatewayRequest",
        policy: "PolicyDecision",
    ) -> Decimal:
        """
        Estimate request cost before execution, for budget reservation.
        Uses a token-count estimate and the request's max_tokens.
        """
        model_selection = self._route(request, policy)

        try:
            adapter = self._registry.get(model_selection.provider)
            estimated_tokens = await adapter.count_tokens(
                request.messages, model_selection.model
            )
        except Exception:
            # Fallback: estimate from character count (~4 chars per token).
            total_chars = sum(len(m.get("content", "")) for m in request.messages)
            estimated_tokens = max(1, total_chars // 4)

        try:
            pricing = await self._cost_engine.get_pricing(
                model_selection.model, model_selection.provider
            )
            return self._cost_engine.estimate_cost(
                estimated_prompt_tokens=estimated_tokens,
                max_output_tokens=request.max_tokens or 2048,
                pricing=pricing,
            )
        except Exception:
            return Decimal("0")  # If pricing unknown, don't block.
