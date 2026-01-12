"""
Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.middleware.enumeration_protection import EnumerationProtectionMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.services.ingestion import enable_adapter_caching

# Setup logging
setup_logging()
logger = structlog.get_logger()

# Initialize Sentry error tracking
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
        profiles_sample_rate=0.1,  # 10% of sampled transactions for profiling
        send_default_pii=False,  # Don't send personally identifiable information
    )
    logger.info("Sentry initialized", environment=settings.environment)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup and shutdown events.
    """
    # Startup
    logger.info(
        "Starting MTG Market Intel API",
        version="1.0.0",
        debug=settings.api_debug,
    )

    # Enable adapter caching for FastAPI (single event loop)
    # This is safe here because FastAPI runs in a single event loop
    # Celery workers should NOT enable this as they create new loops per task
    enable_adapter_caching(True)

    # Check data freshness and only trigger tasks if needed
    try:
        from app.db.session import async_session_maker
        from app.core.data_freshness import (
            check_data_freshness,
            should_run_tournaments_ingestion,
        )
        from app.tasks.data_seeding import seed_comprehensive_price_data
        from app.tasks.ingestion import collect_price_data, import_mtgjson_historical_prices
        from app.tasks.analytics import run_analytics
        from app.tasks.recommendations import generate_recommendations
        from app.tasks.tournaments import ingest_recent_tournaments

        # Check existing data freshness
        async with async_session_maker() as db:
            freshness = await check_data_freshness(db)

            price_fresh = freshness["price_snapshots"]["fresh"]
            analytics_fresh = freshness["analytics"]["fresh"]
            recommendations_fresh = freshness["recommendations"]["fresh"]

            price_count = freshness["price_snapshots"]["count"]
            analytics_count = freshness["analytics"]["count"]
            recommendations_count = freshness["recommendations"]["count"]

        logger.info(
            "Data freshness check on startup",
            price_snapshots_fresh=price_fresh,
            price_snapshots_count=price_count,
            analytics_fresh=analytics_fresh,
            analytics_count=analytics_count,
            recommendations_fresh=recommendations_fresh,
            recommendations_count=recommendations_count,
        )

        # Only trigger tasks for stale or missing data
        tasks_triggered = []

        # Price collection - only if data is stale or missing
        if not price_fresh or price_count < 100:
            # Phase 1: Comprehensive data seeding (current + historical for all cards)
            seeding_task = seed_comprehensive_price_data.delay()
            logger.info("Comprehensive data seeding task queued", task_id=str(seeding_task.id))
            tasks_triggered.append("seed_comprehensive_price_data")

            # Phase 1.5: Import MTGJSON historical data for inventory cards (30 days)
            mtgjson_task = import_mtgjson_historical_prices.delay(card_ids=None, days=30)
            logger.info("MTGJSON historical import queued", task_id=str(mtgjson_task.id))
            tasks_triggered.append("import_mtgjson_historical_prices")

            # Phase 2: Regular price collection
            price_task = collect_price_data.delay()
            logger.info("Price collection task queued", task_id=str(price_task.id))
            tasks_triggered.append("collect_price_data")
        else:
            logger.info("Skipping price collection tasks - data is fresh")

        # Analytics - only if data is stale or missing
        if not analytics_fresh or analytics_count == 0:
            analytics_task = run_analytics.delay()
            logger.info("Analytics task queued", task_id=str(analytics_task.id))
            tasks_triggered.append("run_analytics")
        else:
            logger.info("Skipping analytics task - data is fresh")

        # Recommendations - only if data is stale or missing
        if not recommendations_fresh or recommendations_count == 0:
            rec_task = generate_recommendations.delay()
            logger.info("Recommendations task queued", task_id=str(rec_task.id))
            tasks_triggered.append("generate_recommendations")
        else:
            logger.info("Skipping recommendations task - data is fresh")

        # Tournaments - only if no tournaments exist
        async with async_session_maker() as db:
            should_ingest_tournaments = await should_run_tournaments_ingestion(db)
        if should_ingest_tournaments:
            tournaments_task = ingest_recent_tournaments.delay()
            logger.info("Tournament ingestion task queued", task_id=str(tournaments_task.id))
            tasks_triggered.append("ingest_recent_tournaments")
        else:
            logger.info("Skipping tournament ingestion - tournaments exist")

        if tasks_triggered:
            logger.info("Startup tasks triggered", tasks=tasks_triggered)
        else:
            logger.info("All data is fresh - no startup tasks needed, charts will load instantly")

    except Exception as exc:
        # Don't fail startup if Celery isn't available (e.g., in dev)
        logger.warning(
            "Failed to check freshness or trigger startup tasks (Celery may not be ready)",
            error=str(exc)
        )

    yield

    # Shutdown
    logger.info("Shutting down MTG Market Intel API")

    # Close Redis connections
    from app.api.deps import close_redis
    await close_redis()
    logger.info("Redis connections closed")

    # Disable caching and clean up adapters
    enable_adapter_caching(False)


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="MTG Market Intelligence - Card price tracking, analytics, and trading recommendations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware (after CORS)
# Note: 300/min allows ~5 requests/sec which is plenty for normal usage
# Card detail pages make many parallel requests (card, history, news, similar, etc.)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=300,
    auth_requests_per_minute=10,
)

# Add session middleware for OAuth state management
# Note: CSRF protection is inherently provided by JWT in Authorization headers
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=not settings.api_debug,
)

# Add request ID middleware for distributed tracing
# Runs before other middleware to ensure request_id is available early
app.add_middleware(RequestIdMiddleware)

# Add enumeration protection middleware
# Detects and blocks ID enumeration attacks by tracking 404 patterns
app.add_middleware(EnumerationProtectionMiddleware)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    from sqlalchemy.exc import TimeoutError as SQLTimeoutError

    error_type = type(exc).__name__
    error_str = str(exc)

    # Check for connection pool exhaustion
    # SQLAlchemy raises TimeoutError for pool exhaustion, not PoolError
    is_pool_error = (
        isinstance(exc, SQLTimeoutError) or
        "QueuePool" in error_str or
        "connection timed out" in error_str.lower() or
        "pool limit" in error_str.lower()
    )

    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=error_str,
        error_type=error_type,
        is_pool_error=is_pool_error,
    )

    # Report to Sentry (if configured)
    if settings.sentry_dsn:
        sentry_sdk.capture_exception(exc)

    # Return a more helpful error for pool exhaustion
    if is_pool_error:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Service temporarily unavailable due to high load. Please try again in a moment.",
                "error_type": "connection_pool_exhausted"
            },
        )

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Include API routes with /api prefix
app.include_router(api_router, prefix="/api")


# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests."""
    logger.debug(
        "Request",
        method=request.method,
        path=request.url.path,
    )
    response = await call_next(request)
    logger.debug(
        "Response",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
    )
    return response


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
    )

