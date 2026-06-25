"""
AI Gateway exception hierarchy.
All gateway errors inherit from GatewayError.
Callers catch GatewayError — never provider-specific exceptions.
"""


class GatewayError(Exception):
    """Base class for all AI Gateway errors."""

    def __init__(self, message: str, code: str = "gateway_error") -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


class GatewayPolicyError(GatewayError):
    """Policy violation: plan insufficient, budget exceeded, rate limited, feature not enabled."""

    def __init__(self, message: str, code: str, retry_after: int | None = None) -> None:
        super().__init__(message, code)
        self.retry_after = retry_after  # Seconds until retry is allowed (rate limit only)


class GatewayAuthError(GatewayError):
    """Authentication failure: no API key, invalid key."""

    def __init__(self, message: str, code: str = "auth_error") -> None:
        super().__init__(message, code)


class GatewayProviderError(GatewayError):
    """Provider-side error: 5xx, service error."""

    def __init__(self, message: str, provider: str, code: str = "provider_error") -> None:
        super().__init__(message, code)
        self.provider = provider


class GatewayTimeoutError(GatewayProviderError):
    """Provider call timed out."""

    def __init__(self, provider: str, timeout_seconds: int) -> None:
        super().__init__(
            f"Provider {provider!r} timed out after {timeout_seconds}s",
            provider=provider,
            code="timeout",
        )
        self.timeout_seconds = timeout_seconds


class GatewayUnavailableError(GatewayProviderError):
    """Provider is unavailable (circuit breaker open or service down)."""

    def __init__(self, provider: str) -> None:
        super().__init__(
            f"Provider {provider!r} is currently unavailable",
            provider=provider,
            code="provider_unavailable",
        )


class GatewaySecurityError(GatewayError):
    """Security violation: PII detected, prompt injection attempt."""

    def __init__(self, message: str, code: str = "security_error") -> None:
        super().__init__(message, code)


class GatewayConfigError(GatewayError):
    """Configuration error: unknown model, unknown agent, missing config."""

    def __init__(self, message: str, code: str = "config_error") -> None:
        super().__init__(message, code)
