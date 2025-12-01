"""
Recommendation tasks for generating trading recommendations.
"""
import asyncio
from datetime import date
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models import Card, AppSettings
from app.services.agents.recommendation import RecommendationAgent

logger = structlog.get_logger()


def create_task_session_maker():
    """Create a new async engine and session maker for the current event loop."""
    engine = create_async_engine(
        settings.database_url_computed,
        echo=settings.api_debug,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    ), engine


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _get_settings_value(db, user_id: int | None, key: str, default: Any) -> Any:
    """
    Get a setting value from the database for a specific user.
    
    If user_id is None, tries to get from system user, otherwise uses default.
    """
    from app.models.settings import DEFAULT_SETTINGS
    
    # Try to get from specified user
    if user_id:
        query = select(AppSettings).where(
            AppSettings.user_id == user_id,
            AppSettings.key == key
        )
        result = await db.execute(query)
        setting = result.scalar_one_or_none()
        
        if setting:
            return _parse_setting_value(setting.value, setting.value_type)
    
    # Try system user as fallback
    from app.models.user import User
    system_user_query = select(User).where(User.username == "system")
    system_result = await db.execute(system_user_query)
    system_user = system_result.scalar_one_or_none()
    
    if system_user:
        query = select(AppSettings).where(
            AppSettings.user_id == system_user.id,
            AppSettings.key == key
        )
        result = await db.execute(query)
        setting = result.scalar_one_or_none()
        
        if setting:
            return _parse_setting_value(setting.value, setting.value_type)
    
    # Use default from DEFAULT_SETTINGS if available
    if key in DEFAULT_SETTINGS:
        return _parse_setting_value(
            DEFAULT_SETTINGS[key]["value"],
            DEFAULT_SETTINGS[key]["value_type"]
        )
    
    return default


def _parse_setting_value(value: str, value_type: str) -> Any:
    """Parse a setting value based on its type."""
    if value_type == "float":
        return float(value)
    elif value_type == "integer":
        return int(value)
    elif value_type == "boolean":
        return value.lower() == "true"
    elif value_type == "json":
        import json
        return json.loads(value)
    return value


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def generate_recommendations(
    self,
    card_ids: list[int] | None = None,
    target_date: str | None = None,
) -> dict[str, Any]:
    """
    Generate recommendations for cards.
    
    Args:
        card_ids: Optional list of card IDs. None = cards with signals.
        target_date: Date string (YYYY-MM-DD). None = today.
        
    Returns:
        Recommendation generation results.
    """
    parsed_date = date.fromisoformat(target_date) if target_date else None
    return run_async(_generate_recommendations_async(card_ids, parsed_date))


async def _generate_recommendations_async(
    card_ids: list[int] | None,
    target_date: date | None,
) -> dict[str, Any]:
    """Async implementation of recommendation generation."""
    logger.info("Starting recommendation generation", card_ids=card_ids, date=target_date)
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Get settings (use None for user_id to get system/default settings)
            min_roi = await _get_settings_value(db, None, "min_roi_threshold", 0.10)
            min_confidence = await _get_settings_value(db, None, "min_confidence_threshold", 0.60)
            horizon_days = await _get_settings_value(db, None, "recommendation_horizon_days", 7)
            
            agent = RecommendationAgent(
                db,
                min_roi=min_roi,
                min_confidence=min_confidence,
                horizon_days=horizon_days,
            )
            
            results = await agent.run_recommendations(
                card_ids=card_ids,
                target_date=target_date,
            )
            
            logger.info("Recommendation generation completed", results=results)
            return results
    finally:
        await engine.dispose()


@shared_task(bind=True)
def generate_card_recommendations(
    self,
    card_id: int,
    target_date: str | None = None,
) -> dict[str, Any]:
    """
    Generate recommendations for a single card.
    
    Args:
        card_id: Card ID to process.
        target_date: Date string (YYYY-MM-DD). None = today.
        
    Returns:
        Recommendations for the card.
    """
    parsed_date = date.fromisoformat(target_date) if target_date else None
    return run_async(_generate_card_recommendations_async(card_id, parsed_date))


async def _generate_card_recommendations_async(
    card_id: int,
    target_date: date | None,
) -> dict[str, Any]:
    """Async implementation of single card recommendation generation."""
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Get settings (use None for user_id to get system/default settings)
            min_roi = await _get_settings_value(db, None, "min_roi_threshold", 0.10)
            min_confidence = await _get_settings_value(db, None, "min_confidence_threshold", 0.60)
            horizon_days = await _get_settings_value(db, None, "recommendation_horizon_days", 7)
            
            agent = RecommendationAgent(
                db,
                min_roi=min_roi,
                min_confidence=min_confidence,
                horizon_days=horizon_days,
            )
            
            recommendations = await agent.generate_recommendations(card_id, target_date)
            await db.commit()
            
            return {
                "card_id": card_id,
                "date": str(target_date or date.today()),
                "recommendations": [
                    {
                        "action": r.action,
                        "confidence": float(r.confidence),
                        "rationale": r.rationale,
                        "current_price": float(r.current_price) if r.current_price else None,
                        "target_price": float(r.target_price) if r.target_price else None,
                        "potential_profit_pct": float(r.potential_profit_pct) if r.potential_profit_pct else None,
                    }
                    for r in recommendations
                ],
            }
    finally:
        await engine.dispose()


@shared_task(bind=True)
def cleanup_old_recommendations(self, days: int = 30) -> dict[str, Any]:
    """
    Clean up old inactive recommendations.
    
    Args:
        days: Delete recommendations older than this many days.
        
    Returns:
        Cleanup results.
    """
    return run_async(_cleanup_old_recommendations_async(days))


async def _cleanup_old_recommendations_async(days: int) -> dict[str, Any]:
    """Async implementation of recommendation cleanup."""
    from datetime import datetime, timedelta
    from app.models import Recommendation
    from sqlalchemy import delete
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            # Delete old inactive recommendations
            stmt = delete(Recommendation).where(
                Recommendation.is_active == False,
                Recommendation.created_at < cutoff,
            )
            result = await db.execute(stmt)
            deleted = result.rowcount
            
            await db.commit()
            
            logger.info("Cleaned up old recommendations", deleted=deleted, cutoff=str(cutoff))
            
            return {
                "deleted": deleted,
                "cutoff_date": str(cutoff),
            }
    finally:
        await engine.dispose()

