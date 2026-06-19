"""
Rate limiting — Sprint 9

Uses slowapi (Starlette-compatible limits library).
Key = user_id from JWT so limits are per-user, not per-IP.
Falls back to IP if no authenticated user.

Limits:
  CV Upload         5 / hour
  Job Discovery     20 / hour
  Career Coach      10 / hour
  Application gen   20 / hour
  General AI calls  30 / hour

Override with env RATE_LIMIT_MULTIPLIER=2 to double all limits (staging).
"""
from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded


def _key_func(request: Request) -> str:
    """Extract user_id from validated JWT or fall back to IP."""
    # The user dict is attached by get_current_user dependency
    user: dict | None = getattr(request.state, "user", None)
    if user:
        return f"user:{user['id']}"
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else request.client.host or "unknown"


_multiplier = int(os.getenv("RATE_LIMIT_MULTIPLIER", "1"))

limiter = Limiter(key_func=_key_func)

# Limit strings — multiplied for staging
LIMIT_UPLOAD    = f"{5  * _multiplier}/hour"
LIMIT_DISCOVERY = f"{20 * _multiplier}/hour"
LIMIT_COACH     = f"{10 * _multiplier}/hour"
LIMIT_APP_GEN   = f"{20 * _multiplier}/hour"
LIMIT_AI        = f"{30 * _multiplier}/hour"


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a friendly 429 JSON response instead of slowapi's default plain text."""
    retry_after = getattr(exc, "retry_after", 60)
    return JSONResponse(
        status_code=429,
        content={
            "detail": "For mange forespørgsler — prøv igen om lidt.",
            "retry_after_seconds": retry_after,
            "limit": str(exc.detail),
        },
        headers={"Retry-After": str(retry_after)},
    )
