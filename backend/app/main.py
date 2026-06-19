import logging
import logging.config

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.config import settings
from app.core.rate_limit import limiter, rate_limit_handler
from app.api.v1 import api_router

# ── Structured logging ────────────────────────────────────────────────────────

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "logging.Formatter",
            "fmt": '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)r}',
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
        },
        "simple": {
            "format": "%(asctime)s %(levelname)-8s %(name)s — %(message)s",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if not settings.debug else "simple",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "uvicorn": {"propagate": True},
        "uvicorn.access": {"level": "WARNING"},  # suppress 200 spam in prod
        "app": {"level": "DEBUG" if settings.debug else "INFO"},
    },
}
logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger("app")

# ── Sentry ────────────────────────────────────────────────────────────────────

if settings.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.2,   # 20% of requests traced
        profiles_sample_rate=0.1,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(),
        ],
        environment="production" if not settings.debug else "development",
        release="careeros@0.1.0",
        # Filter out health-check noise
        before_send=lambda event, hint: None if event.get("request", {}).get("url", "").endswith("/health") else event,
    )
    logger.info("Sentry initialised (DSN configured)")
else:
    logger.info("Sentry disabled (SENTRY_DSN not set)")

app = FastAPI(
    title="CareerOS API",
    version="0.1.0",
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ── Request/response logging middleware ───────────────────────────────────────

import time

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000)
    if request.url.path != "/health":
        logger.info(
            '{"method":"%s","path":"%s","status":%d,"ms":%d}',
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    return response

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health() -> dict:
    from app.core.security import encrypt, decrypt
    try:
        assert decrypt(encrypt("ping")) == "ping"
        crypto = "ok"
    except Exception as e:
        crypto = f"FAILED: {e}"
    return {"status": "ok", "version": "0.1.0", "crypto": crypto}
