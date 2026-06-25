"""Tests for AI Gateway exception hierarchy."""

import pytest

from app.gateway.exceptions import (
    GatewayAuthError,
    GatewayConfigError,
    GatewayError,
    GatewayPolicyError,
    GatewayProviderError,
    GatewaySecurityError,
    GatewayTimeoutError,
    GatewayUnavailableError,
)


class TestGatewayErrorHierarchy:
    def test_all_errors_inherit_from_gateway_error(self) -> None:
        assert issubclass(GatewayPolicyError, GatewayError)
        assert issubclass(GatewayAuthError, GatewayError)
        assert issubclass(GatewayProviderError, GatewayError)
        assert issubclass(GatewayTimeoutError, GatewayError)
        assert issubclass(GatewayTimeoutError, GatewayProviderError)
        assert issubclass(GatewayUnavailableError, GatewayError)
        assert issubclass(GatewayUnavailableError, GatewayProviderError)
        assert issubclass(GatewaySecurityError, GatewayError)
        assert issubclass(GatewayConfigError, GatewayError)

    def test_gateway_error_has_code_and_message(self) -> None:
        err = GatewayError("test message", code="test_code")
        assert err.code == "test_code"
        assert err.message == "test message"
        assert str(err) == "test message"

    def test_policy_error_has_retry_after(self) -> None:
        err = GatewayPolicyError("rate limited", code="rate_limited", retry_after=30)
        assert err.retry_after == 30
        assert err.code == "rate_limited"

    def test_policy_error_without_retry_after(self) -> None:
        err = GatewayPolicyError("budget exceeded", code="budget_exceeded")
        assert err.retry_after is None

    def test_provider_error_has_provider(self) -> None:
        err = GatewayProviderError("service error", provider="anthropic")
        assert err.provider == "anthropic"

    def test_timeout_error_has_provider_and_timeout(self) -> None:
        err = GatewayTimeoutError(provider="openai", timeout_seconds=60)
        assert err.provider == "openai"
        assert err.timeout_seconds == 60
        assert err.code == "timeout"

    def test_unavailable_error_message(self) -> None:
        err = GatewayUnavailableError(provider="anthropic")
        assert "anthropic" in str(err)
        assert err.code == "provider_unavailable"

    def test_gateway_error_is_catchable_as_exception(self) -> None:
        with pytest.raises(GatewayError):
            raise GatewayPolicyError("plan insufficient", code="plan_insufficient")

    def test_provider_error_is_catchable_as_gateway_error(self) -> None:
        with pytest.raises(GatewayError):
            raise GatewayTimeoutError(provider="anthropic", timeout_seconds=30)

    def test_repr_includes_code_and_message(self) -> None:
        err = GatewayError("some error", code="some_code")
        r = repr(err)
        assert "some_code" in r
        assert "some error" in r
