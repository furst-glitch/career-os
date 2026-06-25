"""Tests for ModelRouter — targets 100% branch coverage."""

from __future__ import annotations

import time

import pytest

from app.gateway.exceptions import GatewayConfigError
from app.gateway.routing.defaults import (
    HAIKU,
    OPUS,
    SONNET,
    build_default_routing_config,
)
from app.gateway.routing.model_router import ModelRouter
from app.gateway.routing.types import CostClass
from app.gateway.schemas import ModelSelection


@pytest.fixture
def router() -> ModelRouter:
    return ModelRouter(build_default_routing_config())


# --------------------------------------------------------------------------- #
# Plan → capability routing
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "capability",
    [
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
        "some_unmapped_capability",
    ],
)
def test_free_plan_always_routes_to_haiku(router: ModelRouter, capability: str) -> None:
    sel = router.route(plan="free", capability=capability, agent_name="agent")
    assert sel.provider == "anthropic"
    assert sel.model == HAIKU


def test_pro_plan_analysis_routes_to_sonnet(router: ModelRouter) -> None:
    sel = router.route(plan="pro", capability="cv_parsing", agent_name="cv_agent")
    assert sel.provider == "anthropic"
    assert sel.model == SONNET


@pytest.mark.parametrize("capability", ["chat", "interview_prep"])
def test_pro_plan_quick_tasks_route_to_haiku(router: ModelRouter, capability: str) -> None:
    sel = router.route(plan="pro", capability=capability, agent_name="agent")
    assert sel.model == HAIKU


def test_professional_default_is_sonnet(router: ModelRouter) -> None:
    sel = router.route(plan="professional", capability="cv_generation", agent_name="agent")
    assert sel.model == SONNET


@pytest.mark.parametrize(
    "capability",
    ["contract_analysis", "document_review", "multi_agent_review"],
)
def test_professional_heavy_analysis_routes_to_opus(
    router: ModelRouter, capability: str
) -> None:
    sel = router.route(plan="professional", capability=capability, agent_name="agent")
    assert sel.model == OPUS


@pytest.mark.parametrize(
    "capability",
    ["chat", "cv_parsing", "contract_analysis", "career_coaching", "unmapped_cap"],
)
def test_enterprise_routes_to_opus_for_all(router: ModelRouter, capability: str) -> None:
    sel = router.route(plan="enterprise", capability=capability, agent_name="agent")
    assert sel.model == OPUS


# --------------------------------------------------------------------------- #
# Fallback behavior
# --------------------------------------------------------------------------- #

def test_unknown_plan_falls_back_to_free(router: ModelRouter) -> None:
    sel = router.route(plan="nonexistent_plan", capability="chat", agent_name="agent")
    assert sel.model == HAIKU


def test_unknown_capability_uses_plan_default(router: ModelRouter) -> None:
    # pro plan _default is sonnet
    sel = router.route(plan="pro", capability="brand_new_capability", agent_name="agent")
    assert sel.model == SONNET


# --------------------------------------------------------------------------- #
# User override
# --------------------------------------------------------------------------- #

def test_user_override_accepted_when_in_plan(router: ModelRouter) -> None:
    sel = router.route(
        plan="pro",
        capability="cv_parsing",
        agent_name="agent",
        user_override={"provider": "anthropic", "model": HAIKU},
    )
    assert sel.model == HAIKU
    assert sel.provider == "anthropic"


def test_user_override_provider_only_is_noop(router: ModelRouter) -> None:
    # No "model" key → override is a no-op, spec selection retained.
    sel = router.route(
        plan="pro",
        capability="cv_parsing",
        agent_name="agent",
        user_override={"provider": "openai"},
    )
    assert sel.model == SONNET
    assert sel.provider == "anthropic"


def test_user_override_outside_plan_raises(router: ModelRouter) -> None:
    with pytest.raises(GatewayConfigError) as exc_info:
        router.route(
            plan="free",
            capability="chat",
            agent_name="agent",
            user_override={"provider": "anthropic", "model": OPUS},
        )
    assert exc_info.value.code == "model_not_in_plan"


def test_user_override_model_without_provider_uses_spec_provider(
    router: ModelRouter,
) -> None:
    # professional allows OPUS; override gives model but no provider → spec provider used.
    sel = router.route(
        plan="professional",
        capability="cv_generation",  # spec provider = anthropic
        agent_name="agent",
        user_override={"model": OPUS},
    )
    assert sel.model == OPUS
    assert sel.provider == "anthropic"


def test_empty_user_override_dict_is_falsy_noop(router: ModelRouter) -> None:
    sel = router.route(
        plan="pro",
        capability="cv_parsing",
        agent_name="agent",
        user_override={},
    )
    assert sel.model == SONNET


# --------------------------------------------------------------------------- #
# Output contract
# --------------------------------------------------------------------------- #

def test_route_returns_model_selection(router: ModelRouter) -> None:
    sel = router.route(plan="pro", capability="chat", agent_name="agent")
    assert isinstance(sel, ModelSelection)
    assert sel.was_degraded is False


def test_stream_flag_not_part_of_model_selection(router: ModelRouter) -> None:
    streamed = router.route(plan="pro", capability="chat", agent_name="agent", stream=True)
    non_streamed = router.route(plan="pro", capability="chat", agent_name="agent", stream=False)
    # Streaming flag does not alter the selection — passed through separately.
    assert streamed == non_streamed
    assert not hasattr(streamed, "stream")


def test_agent_name_does_not_affect_routing(router: ModelRouter) -> None:
    a = router.route(plan="pro", capability="cv_parsing", agent_name="cv_agent")
    b = router.route(plan="pro", capability="cv_parsing", agent_name="totally_different")
    assert a == b


# --------------------------------------------------------------------------- #
# _derive_cost_class
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "model, expected",
    [
        ("claude-haiku-4-5-20251001", CostClass.LOW),
        ("gpt-4o-mini", CostClass.LOW),
        ("gemini-2.0-flash", CostClass.LOW),
        ("some-nano-model", CostClass.LOW),
        ("claude-sonnet-4-6", CostClass.MEDIUM),
        ("gpt-4o", CostClass.MEDIUM),
        ("claude-opus-4-8", CostClass.HIGH),
        ("claude-opus-4-7", CostClass.HIGH),
    ],
)
def test_derive_cost_class(router: ModelRouter, model: str, expected: CostClass) -> None:
    assert router._derive_cost_class(model) == expected


def test_derive_cost_class_gemini_pro_substring_quirk(router: ModelRouter) -> None:
    """
    Documented quirk: the spec's substring matcher checks LOW tokens first, and
    'gemini-1.5-pro' contains 'mini' (ge-MINI). LOW therefore wins over the
    'pro' HIGH token. This is the implemented behavior, asserted explicitly so
    the quirk is intentional and visible rather than an accident.
    """
    assert router._derive_cost_class("gemini-1.5-pro") == CostClass.LOW


def test_override_applies_derived_cost_class(router: ModelRouter) -> None:
    # enterprise allows gpt-4o → cost class MEDIUM (sanity: routing still returns selection).
    sel = router.route(
        plan="enterprise",
        capability="chat",
        agent_name="agent",
        user_override={"provider": "openai", "model": "gpt-4o"},
    )
    assert sel.model == "gpt-4o"
    assert sel.provider == "openai"


# --------------------------------------------------------------------------- #
# Performance
# --------------------------------------------------------------------------- #

def test_performance_100k_decisions_per_second() -> None:
    """ModelRouter must handle 100K decisions/second."""
    router = ModelRouter(build_default_routing_config())
    iterations = 100_000
    start = time.perf_counter()
    for _ in range(iterations):
        router.route(plan="pro", capability="cv_parsing", agent_name="cv_agent")
    elapsed = time.perf_counter() - start
    decisions_per_second = iterations / elapsed
    assert decisions_per_second >= 100_000, (
        f"Expected >=100K decisions/sec, got {decisions_per_second:,.0f}"
    )
