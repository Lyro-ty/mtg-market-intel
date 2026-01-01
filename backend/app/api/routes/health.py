"""
Health check endpoints.
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.card import Card
from app.models.trading_post import TradingPost

router = APIRouter()


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


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint.
    
    Returns service status and database connectivity.
    """
    from datetime import timezone
    
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

