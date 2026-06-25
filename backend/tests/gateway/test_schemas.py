"""Tests for AI Gateway schema dataclasses."""

from decimal import Decimal

from app.gateway.schemas import (
    GatewayRequest,
    GatewayResponse,
    GatewayUsage,
    KeyResolution,
    ModelPricing,
    ModelSelection,
    PIIScanResult,
    PolicyDecision,
    ProviderResponse,
)


class TestGatewayRequest:
    def test_minimal_request(self) -> None:
        req = GatewayRequest(
            user_id="user-123",
            agent_name="cv_agent",
            messages=[{"role": "user", "content": "hello"}],
            task_capability="cv_parsing",
        )
        assert req.user_id == "user-123"
        assert req.stream is False
        assert req.metadata == {}
        assert req.provider is None

    def test_full_request(self) -> None:
        req = GatewayRequest(
            user_id="user-123",
            agent_name="cv_agent",
            messages=[{"role": "user", "content": "hello"}],
            task_capability="cv_parsing",
            stream=True,
            provider="anthropic",
            temperature=0.5,
            max_tokens=2000,
            response_format={"type": "json_object"},
            metadata={"source": "test"},
        )
        assert req.stream is True
        assert req.provider == "anthropic"
        assert req.temperature == 0.5
        assert req.response_format == {"type": "json_object"}


class TestGatewayUsage:
    def test_defaults(self) -> None:
        usage = GatewayUsage()
        assert usage.prompt_tokens == 0
        assert usage.cost_usd == Decimal("0")
        assert usage.model == ""

    def test_cost_is_decimal(self) -> None:
        usage = GatewayUsage(cost_usd=Decimal("0.00123"))
        assert isinstance(usage.cost_usd, Decimal)


class TestGatewayResponse:
    def test_response_construction(self) -> None:
        usage = GatewayUsage(prompt_tokens=100, completion_tokens=50)
        resp = GatewayResponse(
            content="test response",
            usage=usage,
            request_id="req-123",
            model_used="claude-sonnet-4-6",
            provider_used="anthropic",
            latency_ms=1234,
            used_platform_key=True,
        )
        assert resp.content == "test response"
        assert resp.latency_ms == 1234
        assert resp.used_platform_key is True
        assert resp.metadata == {}


class TestPolicyDecision:
    def test_approved_decision(self) -> None:
        d = PolicyDecision(approved=True, user_plan="pro")
        assert d.approved is True
        assert d.denial_reason is None

    def test_denied_decision(self) -> None:
        d = PolicyDecision(
            approved=False,
            user_plan="free",
            denial_reason="Budget exceeded",
            denial_code="budget_exceeded",
        )
        assert d.approved is False
        assert d.denial_code == "budget_exceeded"

    def test_budget_warning(self) -> None:
        d = PolicyDecision(approved=True, user_plan="pro", budget_warning=True)
        assert d.budget_warning is True


class TestModelSelection:
    def test_normal_selection(self) -> None:
        sel = ModelSelection(
            provider="anthropic",
            model="claude-sonnet-4-6",
            fallback_provider="openai",
            fallback_model="gpt-4o",
        )
        assert sel.provider == "anthropic"
        assert sel.was_degraded is False

    def test_degraded_selection(self) -> None:
        sel = ModelSelection(
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            was_degraded=True,
        )
        assert sel.was_degraded is True


class TestKeyResolution:
    def test_platform_key(self) -> None:
        res = KeyResolution(
            api_key="sk-platform-key",
            api_base=None,
            used_platform_key=True,
        )
        assert res.used_platform_key is True

    def test_byok(self) -> None:
        res = KeyResolution(
            api_key="sk-user-byok-key",
            api_base=None,
            used_platform_key=False,
        )
        assert res.used_platform_key is False

    def test_ollama_has_base_url(self) -> None:
        res = KeyResolution(
            api_key=None,
            api_base="http://localhost:11434",
            used_platform_key=False,
        )
        assert res.api_key is None
        assert res.api_base is not None


class TestPIIScanResult:
    def test_clean_text(self) -> None:
        result = PIIScanResult(
            has_pii=False,
            scan_types_found=[],
            sanitized_text="clean text",
        )
        assert result.has_pii is False
        assert result.sanitized_text == "clean text"

    def test_pii_detected(self) -> None:
        result = PIIScanResult(
            has_pii=True,
            scan_types_found=["CPR", "IBAN"],
            sanitized_text="[REDACTED:CPR] works at [REDACTED:IBAN]",
        )
        assert result.has_pii is True
        assert "CPR" in result.scan_types_found
