"""
Rate limiting — bruger-aware via JWT sub-claim.

Nøglefunktion: extraherer user_id fra Authorization-header uden fuld JWT-validering
(kun til rate limiting — autentificering sker separat i get_current_user).
Falder tilbage til IP-adresse for uautentificerede forespørgsler.

Limits:
  CV Upload         5 / hour
  Job Discovery     20 / hour
  Career Coach      10 / hour
  Application gen   20 / hour
  General AI calls  30 / hour

Override med env RATE_LIMIT_MULTIPLIER=2 for at fordoble alle limits (staging).
"""
from __future__ import annotations

import base64
import json as _json
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded


def _extract_jwt_sub(token: str) -> str | None:
    """Decode JWT payload (no signature verification) to extract sub claim.

    Safe for rate-limiting only — never use for authentication.
    An attacker can forge the sub claim, but that only affects their own rate bucket.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        # Restore base64 padding
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = _json.loads(base64.b64decode(payload_b64))
        return payload.get("sub")
    except Exception:
        return None


def _key_func(request: Request) -> str:
    """Per-user rate limit key. Falls back to IP for unauthenticated requests."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        sub = _extract_jwt_sub(auth[7:])
        if sub:
            return f"user:{sub}"
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
