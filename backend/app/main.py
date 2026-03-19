"""
Research-Grade Spatio-Temporal Analytics API
FastAPI Application Entry Point
"""
import hashlib
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import get_settings
from app.database import init_db_pool, close_db_pool
from app.exceptions import APIError, ValidationError, DatabaseError, create_error_response
from app.logging_config import (
    setup_logging,
    get_logger,
    generate_request_id,
    set_request_id,
    get_request_id,
    log_api_request,
)

from app.rate_limit import RateLimitMiddleware
from app.security import SecurityHeadersMiddleware, HTTPSRedirectMiddleware
from app.api.v1.router import api_router

settings = get_settings()

# Initialize logging
setup_logging(
    log_level=settings.log_level if hasattr(
        settings,
        'log_level') else "INFO")
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle: startup and shutdown."""
    logger.info(
        "Starting I-ASCAP API",
        extra={
            "version": settings.app_version})

    # Startup
    try:
        await init_db_pool()
        logger.info("Database connection pool initialized")

    except Exception as e:
        logger.error(f"Failed to initialize resources: {str(e)}")
        # We might want to raise in production, but for now log and allow partial startup
        # raise

    yield

    # Shutdown
    logger.info("Shutting down I-ASCAP API")

    await close_db_pool()
    logger.info("Database connection pool closed")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    **I-ASCAP: Indian Agri-Spatial Comparative Analytics Platform**

    A research-grade infrastructure for longitudinal analysis across
    Indian district boundary evolution (1951-2024).

    ## Key Features
    - **Lineage-First Design**: Districts as temporal graph nodes
    - **Uncertainty Propagation**: All analytics include confidence intervals
    - **Reproducibility Metadata**: Every response includes provenance
    - **Comprehensive Statistics**: Growth rates, trends, correlations

    ## Data Coverage
    - 928+ districts across 38 states/UTs
    - 1+ million agricultural metrics records
    - 399 recorded boundary changes (splits/merges)

    ## API Guidelines
    - All dates use ISO 8601 format
    - Pagination via `limit` and `offset` parameters
    - Rate limit: 60 requests/minute per IP
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

# Rate Limiting Middleware
app.add_middleware(RateLimitMiddleware)


# Security Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(HTTPSRedirectMiddleware)


# -----------------------------------------------------------------------------
# Request Logging Middleware
# -----------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with timing."""
    # Generate and set request ID
    request_id = generate_request_id()
    set_request_id(request_id)

    # Record start time
    start_time = time.time()

    # Process request
    try:
        response = await call_next(request)
    except Exception:
        # Log failed requests
        duration_ms = (time.time() - start_time) * 1000
        log_api_request(
            method=request.method,
            path=request.url.path,
            status_code=500,
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else None
        )
        raise

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Log successful requests
    log_api_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        client_ip=request.client.host if request.client else None
    )

    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration_ms:.0f}ms"

    return response


# -----------------------------------------------------------------------------
# Utility: Query Hash Generator
# -----------------------------------------------------------------------------
def generate_query_hash(request: Request) -> str:
    """Generate SHA-256 hash of normalized query parameters."""
    query_string = str(sorted(request.query_params.items()))
    return f"sha256:{hashlib.sha256(query_string.encode()).hexdigest()[:16]}"


# -----------------------------------------------------------------------------
# Health Check Endpoints
# -----------------------------------------------------------------------------
@app.get("/health", tags=["System"], summary="Health check")
async def health_check():
    """
    Basic health check endpoint.

    Returns 200 if the application is running.
    Used by Render for health monitoring.
    """
    return {
        "status": "healthy",
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health/ready", tags=["System"], summary="Readiness check")
async def readiness_check():
    """
    Readiness check endpoint.

    Returns 200 if the application can serve traffic (database connected).
    """
    from app.database import get_pool

    pool = await get_pool()
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "Database pool not initialized",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    # Test database connection
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": f"Database connection failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    return {
        "status": "ready",
        "database": "connected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", tags=["System"], summary="API root")
async def root():
    """API root with navigation links."""
    return {
        "name": "I-ASCAP API",
        "description": "Indian Agri-Spatial Comparative Analytics Platform",
        "version": settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "stats": "/stats",
        "api": "/api/v1",
    }


@app.get("/stats", tags=["System"], summary="System statistics")
async def get_system_stats(request: Request):
    """
    Get system statistics including cache and rate limiter metrics.

    Protected: requires X-Admin-Key header matching the configured API key.
    """
    # Guard: only allow if admin key is configured and matches
    admin_key = request.headers.get("X-Admin-Key")
    if settings.api_key and admin_key != settings.api_key:
        return JSONResponse(
            status_code=403,
            content={"error": "Forbidden: admin access required"}
        )

    from app.cache import get_cache
    from app.rate_limit import get_rate_limiter
    from app.database import get_pool

    cache = get_cache()
    rate_limiter = get_rate_limiter()
    pool = await get_pool()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cache": await cache.stats(),
        "rate_limiter": rate_limiter.stats(),
        "database": {
            "pool_size": pool.get_size() if pool else 0,
            "pool_free": pool.get_idle_size() if pool else 0,
            "min_size": settings.db_pool_min_size,
            "max_size": settings.db_pool_max_size,
        },
    }


# -----------------------------------------------------------------------------
# Import and Include API Routers
# -----------------------------------------------------------------------------
app.include_router(api_router, prefix="/api/v1")


# -----------------------------------------------------------------------------
# Exception Handlers
# -----------------------------------------------------------------------------
@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    """Handle custom API errors."""
    logger.warning(
        f"API Error: {exc.error_code} - {exc.detail}",
        extra={"status_code": exc.status_code, "path": request.url.path}
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc, request_id=get_request_id()),
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle validation errors."""
    logger.warning(
        f"Validation Error: {exc.detail}",
        extra={"status_code": exc.status_code, "path": request.url.path}
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc, request_id=get_request_id()),
    )


@app.exception_handler(RequestValidationError)
async def fastapi_validation_error_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI/Pydantic validation errors."""
    errors = exc.errors()
    detail = "; ".join([f"{e['loc'][-1]}: {e['msg']}" for e in errors])

    api_error = ValidationError(detail=detail)

    return JSONResponse(
        status_code=400,
        content=create_error_response(api_error, request_id=get_request_id()),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler with logging."""
    logger.error(
        f"Unhandled exception: {type(exc).__name__} - {str(exc)}",
        exc_info=True,
        extra={"path": request.url.path}
    )

    # Create generic error response
    error = DatabaseError(
        detail="An unexpected error occurred" if not settings.debug else str(exc))

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": error.detail,
                "status_code": 500,
            },
            "request_id": get_request_id(),
            "provenance": {
                "query_hash": generate_query_hash(request),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
