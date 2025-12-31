"""
Meta analysis signal generation task.

Generates signals based on changes in tournament meta statistics:
- META_SPIKE: Card's meta presence significantly increased
- META_DROP: Card's meta presence significantly decreased
"""
import json
from datetime import date, datetime, timezone
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models import Card, CardMetaStats, Signal
from app.tasks.utils import run_async

logger = structlog.get_logger()

# Thresholds for signal generation
META_SPIKE_THRESHOLD = 0.20  # 20% increase in inclusion rate
META_DROP_THRESHOLD = -0.20  # 20% decrease in inclusion rate
TOP8_SPIKE_THRESHOLD = 0.15  # 15% increase in top8 rate


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="generate_meta_signals")
def generate_meta_signals(self, format: str = None) -> dict[str, Any]:
    """
    Generate META_SPIKE and META_DROP signals from tournament data.

    Compares 7d vs 30d periods to detect sudden meta shifts.

    Args:
        format: Specific format to analyze (optional, defaults to all)

    Returns:
        Dict with signal generation statistics
    """
    return run_async(_generate_meta_signals_async(format))


async def _generate_meta_signals_async(format: str = None) -> dict[str, Any]:
    """Async implementation of meta signal generation."""
    stats = {
        "cards_analyzed": 0,
        "meta_spike_signals": 0,
        "meta_drop_signals": 0,
        "top8_spike_signals": 0,
        "errors": [],
    }

    formats_to_analyze = [format] if format else ["Modern", "Pioneer", "Standard", "Legacy", "Pauper", "Vintage"]

    async with async_session_maker() as db:
        try:
            for fmt in formats_to_analyze:
                format_stats = await _analyze_format(db, fmt)
                stats["cards_analyzed"] += format_stats["cards_analyzed"]
                stats["meta_spike_signals"] += format_stats["meta_spike_signals"]
                stats["meta_drop_signals"] += format_stats["meta_drop_signals"]
                stats["top8_spike_signals"] += format_stats["top8_spike_signals"]

            await db.commit()

            logger.info("Meta signals generated", **stats)

        except Exception as e:
            error_msg = f"Failed to generate meta signals: {str(e)}"
            logger.error(error_msg, error=str(e))
            stats["errors"].append(error_msg)
            await db.rollback()

    return stats


async def _analyze_format(db: AsyncSession, format: str) -> dict[str, int]:
    """
    Analyze a single format for meta changes.

    Compares 7d stats against 30d stats to detect sudden shifts.
    """
    stats = {
        "cards_analyzed": 0,
        "meta_spike_signals": 0,
        "meta_drop_signals": 0,
        "top8_spike_signals": 0,
    }

    today = date.today()

    # Get all cards with both 7d and 30d stats for this format
    query = select(CardMetaStats).where(
        and_(
            CardMetaStats.format == format,
            CardMetaStats.period == "7d"
        )
    )
    result = await db.execute(query)
    short_period_stats = {s.card_id: s for s in result.scalars()}

    query = select(CardMetaStats).where(
        and_(
            CardMetaStats.format == format,
            CardMetaStats.period == "30d"
        )
    )
    result = await db.execute(query)
    long_period_stats = {s.card_id: s for s in result.scalars()}

    # Analyze cards that have both periods
    common_cards = set(short_period_stats.keys()) & set(long_period_stats.keys())

    for card_id in common_cards:
        stats["cards_analyzed"] += 1

        short = short_period_stats[card_id]
        long = long_period_stats[card_id]

        # Calculate inclusion rate change (relative to long period)
        if long.deck_inclusion_rate > 0.01:  # Avoid division by near-zero
            inclusion_change = (short.deck_inclusion_rate - long.deck_inclusion_rate) / long.deck_inclusion_rate
        else:
            inclusion_change = short.deck_inclusion_rate - long.deck_inclusion_rate

        # Calculate top8 rate change
        if long.top8_rate > 0.01:
            top8_change = (short.top8_rate - long.top8_rate) / long.top8_rate
        else:
            top8_change = short.top8_rate - long.top8_rate

        # Generate META_SPIKE signal
        if inclusion_change >= META_SPIKE_THRESHOLD:
            await _create_signal(
                db=db,
                card_id=card_id,
                signal_type="meta_spike",
                value=inclusion_change,
                confidence=min(0.9, 0.5 + inclusion_change),
                details={
                    "format": format,
                    "short_period": "7d",
                    "long_period": "30d",
                    "short_inclusion": short.deck_inclusion_rate,
                    "long_inclusion": long.deck_inclusion_rate,
                    "change_pct": inclusion_change,
                }
            )
            stats["meta_spike_signals"] += 1

        # Generate META_DROP signal
        elif inclusion_change <= META_DROP_THRESHOLD:
            await _create_signal(
                db=db,
                card_id=card_id,
                signal_type="meta_drop",
                value=inclusion_change,
                confidence=min(0.9, 0.5 + abs(inclusion_change)),
                details={
                    "format": format,
                    "short_period": "7d",
                    "long_period": "30d",
                    "short_inclusion": short.deck_inclusion_rate,
                    "long_inclusion": long.deck_inclusion_rate,
                    "change_pct": inclusion_change,
                }
            )
            stats["meta_drop_signals"] += 1

        # Generate TOP8_SPIKE signal (separate from meta_spike)
        if top8_change >= TOP8_SPIKE_THRESHOLD and short.top8_rate >= 0.10:
            await _create_signal(
                db=db,
                card_id=card_id,
                signal_type="top8_spike",
                value=top8_change,
                confidence=min(0.9, 0.5 + top8_change),
                details={
                    "format": format,
                    "short_period": "7d",
                    "long_period": "30d",
                    "short_top8": short.top8_rate,
                    "long_top8": long.top8_rate,
                    "change_pct": top8_change,
                }
            )
            stats["top8_spike_signals"] += 1

    logger.debug(
        "Format analysis complete",
        format=format,
        **stats
    )

    return stats


async def _create_signal(
    db: AsyncSession,
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
