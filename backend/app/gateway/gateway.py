"""
AIGateway — minimal facade that orchestrates the complete request flow.

Purpose: Single entry point for all AI requests. Ties policy, execution, and audit together.
Responsibility: Orchestration only. No business logic.
Dependencies: AIPolicyService, AIExecutionService, AuditWriter.
Limitations: Sprint 4 — non-streaming only. Streaming support deferred to Sprint 7.

Usage:
    gateway = build_gateway(supabase, cache)
    response = await gateway.complete(GatewayRequest(...))
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from app.gateway.exceptions import GatewayPolicyError
from app.gateway.schemas import GatewayResponse

if TYPE_CHECKING:
    from app.gateway.audit_writer import AuditWriter
    from app.gateway.execution_service import AIExecutionService
    from app.gateway.policy_service import AIPolicyService
    from app.gateway.schemas import GatewayRequest

logger = logging.getLogger("app.gateway")


class AIGateway:
    """
    AI Gateway facade. Thin orchestrator — no business logic.
    Thread-safe: yes.
    """

    def __init__(
        self,
        policy_service: "AIPolicyService",
        execution_service: "AIExecutionService",
        audit_writer: "AuditWriter",
    ) -> None:
        self._policy = policy_service
        self._execution = execution_service
        self._audit = audit_writer

    async def complete(self, request: "GatewayRequest") -> GatewayResponse:
        """
        Process a complete AI request through the Gateway pipeline.

        Flow: policy → estimate → reserve → execute → release → audit → return

        Raises GatewayPolicyError if policy denies the request.
        Raises GatewayError subclasses on provider or auth failures.
        """
        # 1. Policy evaluation (plan, rate limit, budget).
        policy = await self._policy.evaluate(request.user_id, request.task_capability)
        if not policy.approved:
            await self._audit.write(
                request_id=f"denied-{request.user_id}",
                outcome="policy_denied",
                metadata={
                    "user_id": request.user_id,
                    "capability": request.task_capability,
                    "denial_code": policy.denial_code,
                    "plan": policy.user_plan,
                },
            )
            raise GatewayPolicyError(
                policy.denial_reason or "Request denied by policy",
                code=policy.denial_code or "policy_denied",
            )

        # 2. Pre-execution cost estimate + budget reservation.
        estimated_cost = await self._execution.estimate_cost(request, policy)
        await self._policy.reserve_budget(request.user_id, estimated_cost)

        # 3. Execute.
        try:
            response = await self._execution.execute(request, policy)
        except Exception:
            # Release reservation on failure (actual cost = 0).
            await self._policy.release_budget_reservation(
                request.user_id, estimated_cost, Decimal("0")
            )
            raise

        # 4. Release reservation with actual cost.
        await self._policy.release_budget_reservation(
            request.user_id, estimated_cost, response.usage.cost_usd
        )

        # 5. Audit success. Propagate budget_warning into response metadata.
        if policy.budget_warning:
            response.metadata["budget_warning"] = True

        await self._audit.write(
            request_id=response.request_id,
            outcome="success",
            metadata={
                "user_id": request.user_id,
                "agent": request.agent_name,
                "capability": request.task_capability,
                "model": response.model_used,
                "provider": response.provider_used,
                "tokens": response.usage.total_tokens,
                "latency_ms": response.latency_ms,
                "used_platform_key": response.used_platform_key,
                "budget_warning": policy.budget_warning,
            },
        )

        return response
