"""
Supply analysis signal generation task.

Generates signals based on marketplace supply data:
- SUPPLY_LOW: Unusually few listings for a card (potential scarcity)
- SUPPLY_VELOCITY: Rapid change in supply (decreasing = buying pressure, increasing = dumping)
"""
import json
from datetime import date, timedelta
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select, func, and_

from app.db.session import async_session_maker
from app.models import PriceSnapshot, Signal
from app.tasks.utils import run_async

logger = structlog.get_logger()

# Thresholds for signal generation
SUPPLY_LOW_THRESHOLD = 5  # Cards with fewer than 5 listings across all marketplaces
SUPPLY_LOW_MIN_PRICE = 5.0  # Only flag low supply for cards worth at least $5
SUPPLY_VELOCITY_THRESHOLD = 0.30  # 30% change in listings count
SUPPLY_VELOCITY_MIN_LISTINGS = 10  # Need at least 10 listings to measure velocity


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="generate_supply_signals")
def generate_supply_signals(self) -> dict[str, Any]:
    """
    Generate SUPPLY_LOW and SUPPLY_VELOCITY signals from marketplace data.

    Analyzes price_snapshots for listing counts to detect:
    - Scarce supply on valuable cards
    - Rapid changes in available inventory

    Returns:
        Dict with signal generation statistics
    """
    return run_async(_generate_supply_signals_async())


async def _generate_supply_signals_async() -> dict[str, Any]:
    """Async implementation of supply signal generation."""
    stats = {
        "cards_analyzed": 0,
        "supply_low_signals": 0,
        "supply_velocity_signals": 0,
        "supply_decreasing": 0,
        "supply_increasing": 0,
        "errors": [],
    }

    async with async_session_maker() as db:
        try:
            today = date.today()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)

            # Get current supply levels (last 24 hours)
            current_supply = await _get_supply_snapshot(db, today - timedelta(days=1), today)

            # Get 7d average supply
            supply_7d = await _get_supply_snapshot(db, week_ago, today)

            # Get 30d average supply
            supply_30d = await _get_supply_snapshot(db, month_ago, today)

            # Analyze each card with current data
            analyzed_cards = set()

            for card_id, current_data in current_supply.items():
                analyzed_cards.add(card_id)
                stats["cards_analyzed"] += 1

                # Check for SUPPLY_LOW signal
                if await _check_supply_low(
                    db, card_id, current_data, stats
                ):
                    pass  # Signal created in helper

                # Check for SUPPLY_VELOCITY signal
                if card_id in supply_30d:
                    await _check_supply_velocity(
                        db, card_id, current_data, supply_7d.get(card_id), supply_30d[card_id], stats
                    )

            await db.commit()
            logger.info("Supply signals generated", **stats)

        except Exception as e:
            error_msg = f"Failed to generate supply signals: {str(e)}"
            logger.error(error_msg, error=str(e))
            stats["errors"].append(error_msg)
            await db.rollback()

    return stats


async def _get_supply_snapshot(db, start_date: date, end_date: date) -> dict[int, dict]:
    """
    Get aggregate supply data for all cards in a date range.

    Returns dict mapping card_id -> {total_listings, avg_price, snapshot_count}
    """
    query = select(
        PriceSnapshot.card_id,
        func.sum(PriceSnapshot.num_listings).label('total_listings'),
        func.avg(PriceSnapshot.price).label('avg_price'),
        func.count(PriceSnapshot.id).label('snapshot_count'),
    ).where(
        and_(
            func.date(PriceSnapshot.time) >= start_date,
            func.date(PriceSnapshot.time) <= end_date,
            PriceSnapshot.num_listings.isnot(None),
            PriceSnapshot.currency == "USD",
        )
    ).group_by(PriceSnapshot.card_id)

    result = await db.execute(query)

    return {
        row.card_id: {
            'total_listings': row.total_listings or 0,
            'avg_price': float(row.avg_price) if row.avg_price else 0,
            'snapshot_count': row.snapshot_count or 0,
        }
        for row in result
    }


async def _check_supply_low(
    db,
    card_id: int,
    current_data: dict,
    stats: dict,
) -> bool:
    """Check if card has low supply and create signal if so."""
    total_listings = current_data.get('total_listings', 0)
    avg_price = current_data.get('avg_price', 0)

    # Only flag low supply for valuable cards
    if total_listings < SUPPLY_LOW_THRESHOLD and avg_price >= SUPPLY_LOW_MIN_PRICE:
        confidence = min(0.95, 0.6 + (SUPPLY_LOW_MIN_PRICE - total_listings) * 0.1)

        await _create_signal(
            db=db,
            card_id=card_id,
            signal_type="supply_low",
            value=float(total_listings),
            confidence=confidence,
            details={
                "total_listings": total_listings,
                "avg_price": avg_price,
                "threshold": SUPPLY_LOW_THRESHOLD,
                "min_price_threshold": SUPPLY_LOW_MIN_PRICE,
            }
        )
        stats["supply_low_signals"] += 1
        return True

    return False


async def _check_supply_velocity(
    db,
    card_id: int,
    current_data: dict,
    data_7d: dict | None,
    data_30d: dict,
    stats: dict,
) -> bool:
    """Check for rapid supply changes and create signal if detected."""
    current_listings = current_data.get('total_listings', 0)
    listings_30d = data_30d.get('total_listings', 0)

    # Need minimum listings to measure velocity
    if listings_30d < SUPPLY_VELOCITY_MIN_LISTINGS:
        return False

    # Calculate velocity as percentage change
    # Use average per snapshot to normalize for different snapshot counts
    current_per_snapshot = current_listings / max(1, current_data.get('snapshot_count', 1))
    avg_30d_per_snapshot = listings_30d / max(1, data_30d.get('snapshot_count', 1))

    if avg_30d_per_snapshot < 1:
        return False

    velocity = (current_per_snapshot - avg_30d_per_snapshot) / avg_30d_per_snapshot

    if abs(velocity) >= SUPPLY_VELOCITY_THRESHOLD:
        direction = "decreasing" if velocity < 0 else "increasing"

        await _create_signal(
            db=db,
            card_id=card_id,
            signal_type="supply_velocity",
            value=velocity,
            confidence=min(0.9, 0.5 + abs(velocity)),
            details={
                "current_listings": current_listings,
                "listings_30d_avg": listings_30d,
                "velocity_pct": velocity * 100,
                "direction": direction,
                "threshold": SUPPLY_VELOCITY_THRESHOLD,
            }
        )
        stats["supply_velocity_signals"] += 1

        if velocity < 0:
            stats["supply_decreasing"] += 1
        else:
            stats["supply_increasing"] += 1

        return True

    return False


async def _create_signal(
    db,
    card_id: int,
    signal_type: str,
    value: float,
    confidence: float,
    details: dict,
) -> Signal:
    """Create or update a signal for today."""
    today = date.today()

    # Check for existing signal today
    existing = await db.scalar(
        select(Signal).where(
            and_(
                Signal.card_id == card_id,
                Signal.signal_type == signal_type,
                Signal.date == today
            )
        )
    )

    if existing:
        existing.value = value
        existing.confidence = confidence
        existing.details = json.dumps(details)
        return existing
    else:
        signal = Signal(
            card_id=card_id,
            date=today,
            signal_type=signal_type,
            value=value,
            confidence=confidence,
            details=json.dumps(details),
        )
        db.add(signal)
        return signal
