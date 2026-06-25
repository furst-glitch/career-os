"""
Gateway factory — builds a fully-configured AIGateway instance.

Call once at request time or once at application startup.
Do NOT store in module-level scope — inject via dependency injection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client

    from app.gateway.gateway import AIGateway


def build_gateway(supabase: "Client", cache: object, *, settings: object = None) -> "AIGateway":
    """Build and return a complete, wired AIGateway.

    ``settings`` is injected in tests to avoid loading app.core.config (which
    requires env vars). Production callers omit it.
    """
    if settings is None:
        from app.core.config import settings as _real_settings
        settings = _real_settings
    from app.gateway.audit_writer import AuditWriter
    from app.gateway.cost.cost_engine import CostEngine
    from app.gateway.cost.defaults import build_default_pricing_repository
    from app.gateway.execution_service import AIExecutionService
    from app.gateway.gateway import AIGateway
    from app.gateway.key_resolver import KeyResolver
    from app.gateway.pii_scanner import PIIScanner
    from app.gateway.policy_service import AIPolicyService
    from app.gateway.providers.factory import build_default_provider_registry
    from app.gateway.routing.defaults import build_default_routing_config
    from app.gateway.routing.model_router import ModelRouter
    from app.gateway.usage_tracker import UsageTracker

    return AIGateway(
        policy_service=AIPolicyService(supabase=supabase, cache=cache),
        execution_service=AIExecutionService(
            registry=build_default_provider_registry(),
            key_resolver=KeyResolver(supabase=supabase, settings=settings),
            pii_scanner=PIIScanner(),
            model_router=ModelRouter(config=build_default_routing_config()),
            cost_engine=CostEngine(repository=build_default_pricing_repository()),
            usage_tracker=UsageTracker(supabase=supabase),
        ),
        audit_writer=AuditWriter(supabase=supabase),
    )
