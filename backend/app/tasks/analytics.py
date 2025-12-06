"""
Analytics tasks for computing metrics and generating signals.
"""
from datetime import date
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select

from app.models import Card
from app.services.agents.analytics import AnalyticsAgent
from app.tasks.utils import create_task_session_maker, run_async

logger = structlog.get_logger()


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def run_analytics(self, card_ids: list[int] | None = None, target_date: str | None = None) -> dict[str, Any]:
    """
    Run analytics for cards.
    
    Args:
        card_ids: Optional list of card IDs. None = all cards with data.
        target_date: Date string (YYYY-MM-DD). None = today.
        
    Returns:
        Analytics results summary.
    """
    parsed_date = date.fromisoformat(target_date) if target_date else None
    return run_async(_run_analytics_async(card_ids, parsed_date))


async def _run_analytics_async(
    card_ids: list[int] | None,
    target_date: date | None,
) -> dict[str, Any]:
    """Async implementation of analytics run."""
    logger.info("Starting analytics run", card_ids=card_ids, date=target_date)
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            agent = AnalyticsAgent(db)
            
            results = await agent.run_daily_analytics(
                card_ids=card_ids,
                target_date=target_date,
                generate_insights=True,
            )
            
            logger.info("Analytics run completed", results=results)
            return results
    finally:
        await engine.dispose()


@shared_task(bind=True)
def compute_card_metrics(self, card_id: int, target_date: str | None = None) -> dict[str, Any]:
    """
    Compute metrics for a single card.
    
    Args:
        card_id: Card ID to process.
        target_date: Date string (YYYY-MM-DD). None = today.
        
    Returns:
        Metrics result.
    """
    parsed_date = date.fromisoformat(target_date) if target_date else None
    return run_async(_compute_card_metrics_async(card_id, parsed_date))


async def _compute_card_metrics_async(card_id: int, target_date: date | None) -> dict[str, Any]:
    """Async implementation of single card metrics computation."""
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            agent = AnalyticsAgent(db)
            
            metrics = await agent.compute_daily_metrics(card_id, target_date)
            
            if not metrics:
                return {"card_id": card_id, "error": "No data available"}
            
            signals = await agent.generate_signals(card_id, target_date or date.today())
            insight = await agent.generate_llm_insight(card_id, target_date or date.today())
            
            await db.commit()
            
            return {
                "card_id": card_id,
                "date": str(target_date or date.today()),
                "avg_price": float(metrics.avg_price) if metrics.avg_price else None,
                "price_change_7d": float(metrics.price_change_pct_7d) if metrics.price_change_pct_7d else None,
                "signals_generated": len(signals),
                "has_insight": insight is not None,
            }
    finally:
        await engine.dispose()


@shared_task(bind=True)
def generate_card_signals(self, card_id: int, target_date: str | None = None) -> dict[str, Any]:
    """
    Generate signals for a single card.
    
    Args:
        card_id: Card ID to process.
        target_date: Date string (YYYY-MM-DD). None = today.
        
    Returns:
        Signal generation result.
    """
    parsed_date = date.fromisoformat(target_date) if target_date else None
    return run_async(_generate_card_signals_async(card_id, parsed_date))


async def _generate_card_signals_async(card_id: int, target_date: date | None) -> dict[str, Any]:
    """Async implementation of signal generation."""
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            agent = AnalyticsAgent(db)
            
            signals = await agent.generate_signals(card_id, target_date or date.today())
            await db.commit()
            
            return {
                "card_id": card_id,
                "date": str(target_date or date.today()),
                "signals": [
                    {
                        "type": s.signal_type,
                        "value": float(s.value) if s.value else None,
                        "confidence": float(s.confidence) if s.confidence else None,
                    }
                    for s in signals
                ],
            }
    finally:
        await engine.dispose()


@shared_task(bind=True)
def backfill_analytics(
    self,
    card_ids: list[int] | None = None,
    days: int = 30,
) -> dict[str, Any]:
    """
    Backfill analytics for historical dates.
    
    Args:
        card_ids: Optional list of card IDs. None = all.
        days: Number of days to backfill.
        
    Returns:
        Backfill results.
    """
    return run_async(_backfill_analytics_async(card_ids, days))


async def _backfill_analytics_async(
    card_ids: list[int] | None,
    days: int,
) -> dict[str, Any]:
    """Async implementation of analytics backfill."""
    from datetime import timedelta
    
    logger.info("Starting analytics backfill", days=days)
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            agent = AnalyticsAgent(db)
            
            results = {
                "days_processed": 0,
                "total_metrics": 0,
                "errors": [],
            }
            
            today = date.today()
            
            for i in range(days):
                target_date = today - timedelta(days=i)
                try:
                    day_results = await agent.run_daily_analytics(
                        card_ids=card_ids,
                        target_date=target_date,
                        generate_insights=False,  # Skip LLM for backfill
                    )
                    results["days_processed"] += 1
                    results["total_metrics"] += day_results.get("cards_processed", 0)
                except Exception as e:
                    results["errors"].append(f"{target_date}: {str(e)}")
            
            logger.info("Analytics backfill completed", results=results)
            return results
    finally:
        await engine.dispose()

