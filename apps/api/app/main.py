"""Echo Protocol API entrypoint.

Production hardening included:
- Structured JSON logging
- Request context (request_id, timing, user_id)
- Stripe-style error envelope
- CORS with subdomain regex support
- TrustedHost enforcement
- Sentry integration (opt-in)
- Liveness + Readiness probes with timeouts
"""
import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.core.errors import EchoError, echo_error_handler, http_exception_handler
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.routers import (
    auth_routes, billing, capital, certs, lease, models, predict, wallet,
)

# ─── Optional Sentry ─────────────────────────────────────────
try:
    import sentry_sdk
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1,
            environment=settings.environment,
            release=os.getenv("GIT_SHA", "dev"),
        )
except ImportError:
    pass

setup_logging(level=settings.log_level)
logger = logging.getLogger("echo.api")

# ─── Lifespan ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api_startup", extra={"version": "0.4.1", "env": settings.environment})
    yield
    # Graceful shutdown
    from app.db.session import close_engine
    await close_engine()
    logger.info("api_shutdown")

# ─── App ─────────────────────────────────────────────────────
app = FastAPI(
    title="Echo Protocol API",
    version="0.4.1",
    description="The decentralized quant fund infrastructure for the agent economy.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ─── CORS: support both static origins AND subdomain wildcards ─────
def _wildcard_to_regex(pattern: str) -> str:
    """Convert "https://*.echo.ai" → r"https://[^.]+\\.echo\\.ai"."""
    return re.escape(pattern).replace(r"\*", r"[^.]+")

_static_origins = [o for o in settings.cors_origins if "*" not in o]
_wildcard_origins = [o for o in settings.cors_origins if "*" in o]
_origin_regex: str | None = None
if _wildcard_origins:
    _origin_regex = "|".join(f"^{_wildcard_to_regex(o)}$" for o in _wildcard_origins)

# Middleware order matters: outermost (added last) runs first per request
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_static_origins,
    allow_origin_regex=_origin_regex,
    allow_methods=["GET", "POST", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization", "Content-Type", "X-Request-ID",
        "Idempotency-Key", "X-CC-Webhook-Signature",
    ],
    expose_headers=["X-Request-ID", "X-Response-Time"],
    allow_credentials=True,
    max_age=3600,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

# ─── Error handlers ──────────────────────────────────────────
app.add_exception_handler(EchoError, echo_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

# ─── Routers ─────────────────────────────────────────────────
app.include_router(auth_routes.router, tags=["auth"])
app.include_router(predict.router, tags=["predict"])
app.include_router(lease.router, tags=["lease"])
app.include_router(certs.router, tags=["certs"])
app.include_router(wallet.router, tags=["wallet"])
app.include_router(capital.router, tags=["capital"])
app.include_router(models.router, tags=["models"])
app.include_router(billing.router, tags=["billing"])

# ─── Meta endpoints ──────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "Echo Protocol",
        "version": "0.4.1",
        "tagline": "The decentralized quant fund infrastructure for the agent economy.",
        "docs": "/docs",
        "github": "https://github.com/echo-protocol/echo",
        "status_page": "https://status.echo.ai",
    }

@app.get("/health", tags=["meta"])
async def health():
    """Liveness probe. Returns 200 if process is alive."""
    return {"status": "ok"}

@app.get("/ready", tags=["meta"])
async def ready():
    """Readiness probe. Checks DB + Redis with short timeouts.

    Returns 200 only if ALL dependencies respond within bounds.
    K8s/Fly/Railway should use this for routing decisions.
    """
    from app.core.ratelimit import get_redis
    from app.db.session import engine

    checks: dict[str, str] = {}

    async def _check_db():
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(_check_db(), timeout=2.0)
        checks["database"] = "ok"
    except asyncio.TimeoutError:
        checks["database"] = "timeout"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"

    try:
        await asyncio.wait_for(get_redis().ping(), timeout=1.0)
        checks["redis"] = "ok"
    except asyncio.TimeoutError:
        checks["redis"] = "timeout"
    except Exception as e:
        checks["redis"] = f"error: {type(e).__name__}"

    is_ready = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"ready": is_ready, "checks": checks},
    )
