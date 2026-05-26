import logging, os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.core.errors import EchoError, echo_error_handler, http_exception_handler
from app.routers import auth_routes, predict, lease, certs, wallet, capital, models, billing

# Optional Sentry
try:
    import sentry_sdk
    if os.getenv("SENTRY_DSN"):
        sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"), traces_sample_rate=0.1)
except ImportError:
    pass

setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("echo.api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api_startup", extra={"version": "0.4.1"})
    yield
    logger.info("api_shutdown")

app = FastAPI(
    title="Echo Protocol API",
    version="0.4.1",
    description="The decentralized quant fund infrastructure for the agent economy.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Middleware order matters: outermost first
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    allow_credentials=True,
    max_age=3600,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

# Error handlers
app.add_exception_handler(EchoError, echo_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

# Routers
app.include_router(auth_routes.router, tags=["auth"])
app.include_router(predict.router, tags=["predict"])
app.include_router(lease.router, tags=["lease"])
app.include_router(certs.router, tags=["certs"])
app.include_router(wallet.router, tags=["wallet"])
app.include_router(capital.router, tags=["capital"])
app.include_router(models.router, tags=["models"])
app.include_router(billing.router, tags=["billing"])

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
    """Readiness probe. Checks DB + Redis."""
    from app.db.session import engine
    from app.core.ratelimit import get_redis
    checks = {}
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
    
    ready = all(v == "ok" for v in checks.values())
    return {"ready": ready, "checks": checks}
