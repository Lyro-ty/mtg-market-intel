"""
Analytics tasks for computing metrics and generating signals.

Provides two separate analytics flows:
- Market analytics: For global market data (market page)
- Inventory analytics: For user-specific portfolio data (inventory page)
"""
from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select

from app.models import PriceSnapshot
from app.services.agents.analytics import AnalyticsAgent
from app.tasks.utils import create_task_session_maker, run_async, single_instance

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


# =============================================================================
# Market Analytics (for market page - independent of user inventories)
# =============================================================================

@shared_task(bind=True, max_retries=2, default_retry_delay=300)
@single_instance("market_analytics", timeout=1800)
def run_market_analytics(self, batch_size: int = 2000, target_date: str | None = None) -> dict[str, Any]:
    """
    Run analytics for MARKET cards only.

    This is separate from inventory analytics to ensure the market page
    has global data. Processes cards with recent price snapshots,
    NOT filtered by user inventories.

    Args:
        batch_size: Maximum cards to process (default 2000)
        target_date: Date string (YYYY-MM-DD). None = today.

    Returns:
        Analytics results summary.
    """
    parsed_date = date.fromisoformat(target_date) if target_date else None
    return run_async(_run_market_analytics_async(batch_size, parsed_date))


async def _run_market_analytics_async(
    batch_size: int,
    target_date: date | None,
) -> dict[str, Any]:
    """Async implementation of market analytics run."""
    logger.info("Starting MARKET analytics run", batch_size=batch_size, date=target_date)

    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Get cards with recent price snapshots (market-relevant cards)
            # This mirrors the selection logic in _get_market_card_ids()
            now = datetime.now(timezone.utc)
            recent_threshold = now - timedelta(days=2)  # Cards with data in last 2 days

            market_cards_query = (
                select(PriceSnapshot.card_id)
                .where(
                    PriceSnapshot.time >= recent_threshold,
                    PriceSnapshot.currency == "USD",  # Focus on USD for metrics
                )
                .distinct()
                .limit(batch_size)
            )
            result = await db.execute(market_cards_query)
            card_ids = list(result.scalars().all())

            if not card_ids:
                logger.info("No market cards to process")
                return {
                    "analytics_type": "market",
                    "date": str(target_date or date.today()),
                    "cards_processed": 0,
                    "errors": 0,
                    "total_cards": 0,
                }

            logger.info(f"Processing {len(card_ids)} market cards for analytics")

            # Run analytics for these cards
            agent = AnalyticsAgent(db)

            results = await agent.run_daily_analytics(
                card_ids=card_ids,
                target_date=target_date,
                generate_insights=False,  # Skip LLM for hourly runs (cost saving)
            )

            results["analytics_type"] = "market"
            logger.info("Market analytics run completed", results=results)
            return results

    finally:
        await engine.dispose()


# =============================================================================
# Single Card Analytics
# =============================================================================

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

