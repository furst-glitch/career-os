"""
Shared LiteLLM → GatewayError normalization.

Pure function, no I/O. Used by all LiteLLM-backed adapters so the mapping
logic lives in exactly one place. Each adapter still exposes its own
normalize_error() method (per the adapter contract) that delegates here with
its provider name.

Defensive against litellm version drift: some litellm releases do not expose
every exception symbol (e.g. APITimeoutError). We resolve symbols via getattr
with safe fallbacks so an isinstance check never raises AttributeError.
"""

from __future__ import annotations

from app.gateway.exceptions import (
    GatewayAuthError,
    GatewayConfigError,
    GatewayError,
    GatewayPolicyError,
    GatewayProviderError,
    GatewayTimeoutError,
    GatewayUnavailableError,
)


def normalize_litellm_error(exc: Exception, provider: str) -> GatewayError:
    """Map a litellm/httpx exception to the GatewayError hierarchy."""
    try:
        import litellm
    except ImportError:
        return GatewayProviderError(str(exc), provider=provider)

    type_name = type(exc).__name__

    # Resolve exception classes defensively — fall back to a never-matching
    # sentinel type when a symbol is absent in this litellm version.
    class _Never(Exception):
        """Sentinel that nothing is an instance of (besides itself, never raised)."""

    auth_error = getattr(litellm, "AuthenticationError", _Never)
    rate_limit_error = getattr(litellm, "RateLimitError", _Never)
    context_window_error = getattr(litellm, "ContextWindowExceededError", _Never)
    timeout_error = getattr(litellm, "Timeout", _Never)
    api_timeout_error = getattr(litellm, "APITimeoutError", timeout_error)
    unavailable_error = getattr(litellm, "ServiceUnavailableError", _Never)
    bad_request_error = getattr(litellm, "BadRequestError", _Never)

    if isinstance(exc, auth_error):
        return GatewayAuthError(f"{provider} authentication failed: {exc}", code="auth_error")
    if isinstance(exc, rate_limit_error):
        return GatewayPolicyError(f"{provider} rate limit: {exc}", code="provider_rate_limited")
    if isinstance(exc, context_window_error):
        return GatewayConfigError(
            f"Context window exceeded: {exc}", code="context_window_exceeded"
        )
    if isinstance(exc, (timeout_error, api_timeout_error)):
        return GatewayTimeoutError(provider=provider, timeout_seconds=0)
    if isinstance(exc, unavailable_error):
        return GatewayUnavailableError(provider=provider)
    if "BadRequestError" in type_name or isinstance(exc, bad_request_error):
        return GatewayProviderError(f"Bad request: {exc}", provider=provider, code="bad_request")

    return GatewayProviderError(str(exc), provider=provider)
