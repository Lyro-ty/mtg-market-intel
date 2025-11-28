"""
Recommendation tasks for generating trading recommendations.
"""
import asyncio
from datetime import date
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select

from app.db.session import async_session_maker
from app.models import Card, AppSettings
from app.services.agents.recommendation import RecommendationAgent

logger = structlog.get_logger()


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _get_settings_value(db, key: str, default: Any) -> Any:
    """Get a setting value from the database."""
    query = select(AppSettings).where(AppSettings.key == key)
    result = await db.execute(query)
    setting = result.scalar_one_or_none()
    
    if not setting:
        return default
    
    if setting.value_type == "float":
        return float(setting.value)
    elif setting.value_type == "integer":
        return int(setting.value)
    elif setting.value_type == "boolean":
        return setting.value.lower() == "true"
    elif setting.value_type == "json":
        import json
        return json.loads(setting.value)
    
    return setting.value


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
    
    async with async_session_maker() as db:
        # Get settings
        min_roi = await _get_settings_value(db, "min_roi_threshold", 0.10)
        min_confidence = await _get_settings_value(db, "min_confidence_threshold", 0.60)
        horizon_days = await _get_settings_value(db, "recommendation_horizon_days", 7)
        
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
    async with async_session_maker() as db:
        # Get settings
        min_roi = await _get_settings_value(db, "min_roi_threshold", 0.10)
        min_confidence = await _get_settings_value(db, "min_confidence_threshold", 0.60)
        horizon_days = await _get_settings_value(db, "recommendation_horizon_days", 7)
        
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
    
    async with async_session_maker() as db:
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

