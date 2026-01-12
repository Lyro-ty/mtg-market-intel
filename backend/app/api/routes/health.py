"""
Health check endpoints.

Provides basic and detailed health checks for monitoring.
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_redis
from app.models.user import User
from app.models.card import Card
from app.models.trading_post import TradingPost

router = APIRouter()

# Track application startup time for uptime calculation
_startup_time = time.time()


# -----------------------------------------------------------------------------
# Response Models for Detailed Health Check
# -----------------------------------------------------------------------------


class DependencyHealth(BaseModel):
    """Health status of a single dependency."""
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    latency_ms: float
    message: Optional[str] = None


class DetailedHealthResponse(BaseModel):
    """Comprehensive health check response for monitoring dashboards."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    uptime_seconds: float
    dependencies: list[DependencyHealth]


# -----------------------------------------------------------------------------
# Health Check Helper Functions
# -----------------------------------------------------------------------------


async def _check_database(db: AsyncSession) -> DependencyHealth:
    """Check database connectivity and measure latency."""
    start = time.time()
    try:
        await db.execute(text("SELECT 1"))
        latency = (time.time() - start) * 1000
        # Consider degraded if latency > 100ms
        status = "healthy" if latency < 100 else "degraded"
        return DependencyHealth(
            name="database",
            status=status,
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        return DependencyHealth(
            name="database",
            status="unhealthy",
            latency_ms=-1,
            message=str(e),
        )


async def _check_redis(redis) -> DependencyHealth:
    """Check Redis connectivity and measure latency."""
    start = time.time()
    try:
        await redis.ping()
        latency = (time.time() - start) * 1000
        # Consider degraded if latency > 50ms
        status = "healthy" if latency < 50 else "degraded"
        return DependencyHealth(
            name="redis",
            status=status,
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        return DependencyHealth(
            name="redis",
            status="unhealthy",
            latency_ms=-1,
            message=str(e),
        )


class SiteStats(BaseModel):
    """Public site statistics for the landing page."""
    seekers: int  # User count (fantasy term)
    trading_posts: int  # LGS count (future feature)
    cards_in_vault: int  # Total cards tracked

    class Config:
        from_attributes = True


@router.get("/stats", response_model=SiteStats)
async def get_site_stats(db: AsyncSession = Depends(get_db)):
    """
    Get public site statistics for the landing page.

    Returns live counts of users, shops, and cards.
    No authentication required.
    """
    # Count active users (Seekers)
    user_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    seeker_count = user_result.scalar() or 0

    # Count cards in the database (Vault)
    card_result = await db.execute(
        select(func.count(Card.id))
    )
    card_count = card_result.scalar() or 0

    # Count verified Trading Posts
    trading_post_result = await db.execute(
        select(func.count(TradingPost.id)).where(
            TradingPost.email_verified_at.isnot(None)
        )
    )
    trading_post_count = trading_post_result.scalar() or 0

    return SiteStats(
        seekers=seeker_count,
        trading_posts=trading_post_count,
        cards_in_vault=card_count,
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
):
    """
    Detailed health check for monitoring dashboards.

    Checks all dependencies (database, Redis) in parallel and returns:
    - Overall status: healthy, degraded, or unhealthy
    - Per-dependency latency metrics
    - Application uptime
    - Error messages for unhealthy dependencies

    Status logic:
    - unhealthy: Any dependency is down
    - degraded: Any dependency has high latency
    - healthy: All dependencies responding normally
    """
    # Check dependencies in parallel for efficiency
    db_health, redis_health = await asyncio.gather(
        _check_database(db),
        _check_redis(redis),
    )

    dependencies = [db_health, redis_health]

    # Determine overall status (worst status wins)
    if any(d.status == "unhealthy" for d in dependencies):
        overall_status = "unhealthy"
    elif any(d.status == "degraded" for d in dependencies):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return DetailedHealthResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=round(time.time() - _startup_time, 2),
        dependencies=dependencies,
    )


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Basic health check endpoint.

    Returns service status and database connectivity.
    For detailed monitoring data, use /health/detailed.
    """
    # Check database
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        import structlog
        structlog.get_logger().warning("Health check: database connection failed", error=str(e))

    return {
        "status": "healthy" if db_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "api": "ok",
            "database": "ok" if db_ok else "error",
        },
    }


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MTG Market Intel API",
        "version": "1.0.0",
        "docs": "/docs",
    }

