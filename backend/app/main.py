"""
Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.services.ingestion import enable_adapter_caching

# Setup logging
setup_logging()
logger = structlog.get_logger()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


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
    
    # Trigger initial tasks on startup
    try:
        from app.tasks.data_seeding import seed_comprehensive_price_data
        from app.tasks.ingestion import collect_price_data
        from app.tasks.analytics import run_analytics
        from app.tasks.recommendations import generate_recommendations
        
        logger.info("Triggering startup tasks: comprehensive seeding, price collection, analytics, recommendations")
        
        # Phase 1: Comprehensive data seeding (current + historical for all cards)
        # This pulls current prices from Scryfall + historical from MTGJSON
        seeding_task = seed_comprehensive_price_data.delay()
        logger.info("Comprehensive data seeding task queued", task_id=str(seeding_task.id))
        
        # Phase 2: Regular price collection (runs in background, continues after seeding)
        price_task = collect_price_data.delay()
        logger.info("Price collection task queued", task_id=str(price_task.id))
        
        # Phase 3: Analytics (runs after data is available)
        analytics_task = run_analytics.delay()
        logger.info("Analytics task queued", task_id=str(analytics_task.id))
        
        # Phase 4: Recommendations (runs after analytics)
        rec_task = generate_recommendations.delay()
        logger.info("Recommendations task queued", task_id=str(rec_task.id))
        
    except Exception as exc:
        # Don't fail startup if Celery isn't available (e.g., in dev)
        logger.warning(
            "Failed to trigger startup tasks (Celery may not be ready)",
            error=str(exc)
        )
    
    yield
    
    # Shutdown
    logger.info("Shutting down MTG Market Intel API")
    
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

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

