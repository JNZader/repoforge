"""FastAPI application entry point for RepoForge Web.

Configures the application with lifespan hooks, middleware stack,
health endpoints, error handling, and router registration.
"""

import asyncio
import re
import time
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.config import settings
from app.middleware.logging_config import configure_logging
from app.middleware.rate_limit import limiter
from app.models.database import Base, async_session_factory, engine
from app.routes.auth import router as auth_router
from app.routes.generate import router as generate_router
from app.routes.history import router as history_router
from app.routes.analytics import router as analytics_router
from app.routes.providers import router as providers_router
from app.services.generation_service import generation_service
from app.services.session_keys import session_key_cleanup_loop

# Configure structured logging before anything else
configure_logging()

logger = structlog.get_logger(__name__)

# Track server start time for uptime calculation
_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    global _start_time
    _start_time = time.monotonic()

    # Fail-fast: settings are validated on import (pydantic-settings)
    if settings.DEBUG:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("dev_mode_db_created")

    # Start session key cleanup background task
    cleanup_task = asyncio.create_task(session_key_cleanup_loop())
    logger.info("session_key_cleanup_started")

    logger.info(
        "server_started",
        debug=settings.DEBUG,
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
    )

    yield

    # Graceful shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # Cancel any running generation tasks
    await generation_service.shutdown()

    await engine.dispose()
    logger.info("database_engine_disposed")


try:
    from importlib.metadata import version as _pkg_version
    APP_VERSION = _pkg_version("repoforge-ai")
except (ImportError, KeyError):
    # ImportError: package not installed; KeyError: missing version metadata
    APP_VERSION = "0.3.0"

app = FastAPI(
    title="RepoForge Web API",
    version=APP_VERSION,
    description="Web API for RepoForge doc/skills generation",
    lifespan=lifespan,
)

# --- Rate limiter setup ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# --- Correlation ID middleware ---
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):  # noqa: ANN001
    """Assign a correlation ID to every request for log tracing."""
    request_id = request.headers.get("X-Request-ID", str(uuid4())[:8])
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    structlog.contextvars.unbind_contextvars("request_id")
    return response


# --- Request logging middleware ---
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):  # noqa: ANN001
    """Log every HTTP request with method, path, status, and duration."""
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)
    path = request.url.path

    # Skip noisy health check logs
    if path != "/health":
        log = logger.info if response.status_code < 400 else logger.warning
        if response.status_code >= 500:
            log = logger.error
        log(
            "http_request",
            method=request.method,
            path=path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
    return response


# --- Security headers middleware ---
_PREVIEW_PATH_RE = re.compile(r"^/api/generate/[^/]+/(preview|files/)")


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):  # noqa: ANN001
    """Add standard security headers to every response.

    Preview/files endpoints get relaxed headers so they can be embedded
    in iframes and load Docsify assets from CDNs.
    """
    response = await call_next(request)

    is_preview = _PREVIEW_PATH_RE.match(request.url.path) is not None

    if is_preview:
        # Allow embedding in iframes from any origin (preview pages)
        response.headers["X-Frame-Options"] = "ALLOWALL"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://cdn.jsdelivr.net https://unpkg.com "
            "data: blob:;"
        )
    else:
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)


# --- Routers ---
app.include_router(auth_router)
app.include_router(generate_router)
app.include_router(history_router)
app.include_router(analytics_router)
app.include_router(providers_router)


# --- Health ---
@app.get("/health")
async def health() -> dict:
    """Simple health check — always returns 200 if the server is running."""
    return {"status": "ok", "version": APP_VERSION}


@app.get("/health/detailed")
async def health_detailed() -> dict:
    """Detailed health check — includes DB connectivity and uptime."""
    start = time.monotonic()
    checks: dict = {}

    # Database check
    try:
        async with async_session_factory() as session:
            db_start = time.monotonic()
            await session.execute(text("SELECT 1"))
            checks["database"] = {
                "ok": True,
                "latency_ms": int((time.monotonic() - db_start) * 1000),
            }
    except (OSError, RuntimeError, ConnectionError) as e:
        # Database connectivity failures (connection refused, timeout, etc.)
        checks["database"] = {"ok": False, "error": str(e)}

    healthy = all(c.get("ok", False) for c in checks.values())
    return {
        "status": "healthy" if healthy else "degraded",
        "uptime_seconds": int(time.monotonic() - _start_time),
        "checks": checks,
        "circuit_breaker": generation_service.circuit_breaker.get_state(),
        "active_generations": generation_service.active_count(),
        "response_ms": int((time.monotonic() - start) * 1000),
    }


# --- Global error handler ---
@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch all unhandled exceptions and return a structured error with correlation ID."""
    error_id = str(uuid4())[:8]
    logger.error(
        "unhandled_error",
        error_id=error_id,
        exc_info=exc,
        method=request.method,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "Internal server error",
            "error_id": error_id,
        },
    )
