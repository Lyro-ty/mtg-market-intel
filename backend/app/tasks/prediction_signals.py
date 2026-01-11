"""
Price Prediction Signals Task.

Generates price prediction signals using technical analysis of historical price data.
Identifies momentum patterns, trend reversals, and generates buy/sell predictions.
"""
import json
from datetime import date, datetime, timezone
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.signal import Signal
from app.tasks.utils import run_async

logger = structlog.get_logger(__name__)


# Signal type constants
SIGNAL_MOMENTUM_BULLISH = "momentum_bullish"
SIGNAL_MOMENTUM_BEARISH = "momentum_bearish"
SIGNAL_TREND_REVERSAL_UP = "trend_reversal_up"
SIGNAL_TREND_REVERSAL_DOWN = "trend_reversal_down"
SIGNAL_BREAKOUT = "breakout"
SIGNAL_BREAKDOWN = "breakdown"
SIGNAL_ACCUMULATION = "accumulation"
SIGNAL_DISTRIBUTION = "distribution"


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="generate_prediction_signals")
def generate_prediction_signals(self, limit: int = 500) -> dict[str, Any]:
    """
    Generate price prediction signals for top cards.

    Args:
        limit: Maximum number of cards to analyze

    Returns:
        Summary of signals generated
    """
    return run_async(_generate_prediction_signals_async(limit))


async def _generate_prediction_signals_async(limit: int) -> dict[str, Any]:
    """Async implementation of prediction signal generation."""
    logger.info("Starting prediction signal generation", limit=limit)
    start_time = datetime.now(timezone.utc)

    signals_created = 0
    cards_analyzed = 0
    errors = 0

    try:
        async with async_session_maker() as db:
            # Get cards with recent price activity
            cards = await _get_active_cards(db, limit)
            logger.info("Found cards for prediction analysis", count=len(cards))

            today = date.today()

            for card_id, card_name in cards:
                try:
                    # Get price history
                    prices = await _get_price_history(db, card_id, days=30)

                    if len(prices) < 7:
                        # Not enough data for meaningful analysis
                        continue

                    cards_analyzed += 1

                    # Calculate indicators
                    indicators = _calculate_indicators(prices)

                    # Generate signals based on indicators
                    signals = _generate_signals_from_indicators(
                        card_id=card_id,
                        card_name=card_name,
                        indicators=indicators,
                        today=today,
                    )

                    # Save signals to database
                    for signal_data in signals:
                        await _create_signal(db, signal_data)
                        signals_created += 1

                except Exception as e:
                    errors += 1
                    logger.warning(
                        "Failed to analyze card",
                        card_id=card_id,
                        error=str(e),
                    )

            await db.commit()

    except Exception as e:
        error_msg = f"Failed to generate prediction signals: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
        }

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        "Prediction signal generation complete",
        cards_analyzed=cards_analyzed,
        signals_created=signals_created,
        errors=errors,
        elapsed_seconds=elapsed,
    )

    return {
        "success": True,
        "cards_analyzed": cards_analyzed,
        "signals_created": signals_created,
        "errors": errors,
        "elapsed_seconds": elapsed,
    }


async def _get_active_cards(db: AsyncSession, limit: int) -> list[tuple[int, str]]:
    """Get cards with recent price activity."""
    query = text("""
        SELECT DISTINCT c.id, c.name
        FROM cards c
        JOIN price_snapshots ps ON c.id = ps.card_id
        WHERE ps.time > NOW() - INTERVAL '7 days'
          AND ps.price >= 1.00
        ORDER BY c.id
        LIMIT :limit
    """)
    result = await db.execute(query, {"limit": limit})
    return [(row[0], row[1]) for row in result.all()]


async def _get_price_history(
    db: AsyncSession,
    card_id: int,
    days: int = 30,
) -> list[dict]:
    """Get daily price history for a card."""
    query = text("""
        SELECT
            DATE(time) as date,
            AVG(price) as avg_price,
            MIN(price) as low_price,
            MAX(price) as high_price,
            COUNT(*) as samples
        FROM price_snapshots
        WHERE card_id = :card_id
          AND time > NOW() - INTERVAL :days DAY
        GROUP BY DATE(time)
        ORDER BY date ASC
    """)
    result = await db.execute(query, {"card_id": card_id, "days": f"{days} days"})
    return [
        {
            "date": row[0],
            "avg_price": float(row[1]),
            "low_price": float(row[2]),
            "high_price": float(row[3]),
            "samples": row[4],
        }
        for row in result.all()
    ]


def _calculate_indicators(prices: list[dict]) -> dict:
    """Calculate technical indicators from price history."""
    if len(prices) < 2:
        return {}

    closes = [p["avg_price"] for p in prices]
    current_price = closes[-1]
    prev_price = closes[-2] if len(closes) > 1 else current_price

    # Simple Moving Averages
    sma_7 = sum(closes[-7:]) / min(len(closes), 7) if len(closes) >= 1 else current_price
    sma_14 = sum(closes[-14:]) / min(len(closes), 14) if len(closes) >= 1 else current_price

    # Price momentum (rate of change)
    if len(closes) >= 7:
        momentum_7d = ((closes[-1] - closes[-7]) / closes[-7] * 100) if closes[-7] > 0 else 0
    else:
        momentum_7d = 0

    if len(closes) >= 14:
        momentum_14d = ((closes[-1] - closes[-14]) / closes[-14] * 100) if closes[-14] > 0 else 0
    else:
        momentum_14d = 0

    # Volatility (standard deviation of daily returns)
    if len(closes) >= 7:
        returns = [(closes[i] - closes[i - 1]) / closes[i - 1] * 100
                   for i in range(1, len(closes)) if closes[i - 1] > 0]
        if returns:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = variance ** 0.5
        else:
            volatility = 0
    else:
        volatility = 0

    # Trend direction (based on SMA crossover)
    trend_bullish = sma_7 > sma_14
    trend_strength = abs(sma_7 - sma_14) / sma_14 * 100 if sma_14 > 0 else 0

    # Price relative to range (0-100, like RSI)
    if len(prices) >= 7:
        recent_prices = prices[-7:]
        high = max(p["high_price"] for p in recent_prices)
        low = min(p["low_price"] for p in recent_prices)
        price_range = high - low
        if price_range > 0:
            relative_position = (current_price - low) / price_range * 100
        else:
            relative_position = 50
    else:
        relative_position = 50

    # Breakout detection
    if len(prices) >= 14:
        prev_high = max(p["high_price"] for p in prices[-14:-1])
        prev_low = min(p["low_price"] for p in prices[-14:-1])
        is_breakout = current_price > prev_high
        is_breakdown = current_price < prev_low
    else:
        prev_high = current_price
        prev_low = current_price
        is_breakout = False
        is_breakdown = False

    # Accumulation/Distribution pattern
    # Rising price with increasing samples suggests accumulation
    if len(prices) >= 7:
        recent = prices[-3:]
        older = prices[-7:-3]
        avg_recent_samples = sum(p["samples"] for p in recent) / len(recent)
        avg_older_samples = sum(p["samples"] for p in older) / len(older) if older else avg_recent_samples
        volume_increasing = avg_recent_samples > avg_older_samples * 1.2
    else:
        volume_increasing = False

    return {
        "current_price": current_price,
        "prev_price": prev_price,
        "sma_7": sma_7,
        "sma_14": sma_14,
        "momentum_7d": momentum_7d,
        "momentum_14d": momentum_14d,
        "volatility": volatility,
        "trend_bullish": trend_bullish,
        "trend_strength": trend_strength,
        "relative_position": relative_position,
        "is_breakout": is_breakout,
        "is_breakdown": is_breakdown,
        "prev_high": prev_high,
        "prev_low": prev_low,
        "volume_increasing": volume_increasing,
    }


def _generate_signals_from_indicators(
    card_id: int,
    card_name: str,
    indicators: dict,
    today: date,
) -> list[dict]:
    """Generate prediction signals based on indicators."""
    signals = []

    if not indicators:
        return signals

    momentum_7d = indicators.get("momentum_7d", 0)
    momentum_14d = indicators.get("momentum_14d", 0)
    _trend_bullish = indicators.get("trend_bullish", False)  # noqa: F841 - reserved for future signals
    relative_position = indicators.get("relative_position", 50)
    is_breakout = indicators.get("is_breakout", False)
    is_breakdown = indicators.get("is_breakdown", False)
    volume_increasing = indicators.get("volume_increasing", False)
    _volatility = indicators.get("volatility", 0)  # noqa: F841 - reserved for future signals
    current_price = indicators.get("current_price", 0)

    # Momentum signals
    if momentum_7d > 10 and momentum_14d > 5:
        confidence = min(0.9, 0.5 + momentum_7d / 50)
        signals.append({
            "card_id": card_id,
            "date": today,
            "signal_type": SIGNAL_MOMENTUM_BULLISH,
            "value": momentum_7d,
            "confidence": confidence,
            "details": {
                "momentum_7d": round(momentum_7d, 2),
                "momentum_14d": round(momentum_14d, 2),
                "current_price": round(current_price, 2),
            },
            "insight": f"{card_name} showing strong upward momentum: +{momentum_7d:.1f}% over 7 days",
        })
    elif momentum_7d < -10 and momentum_14d < -5:
        confidence = min(0.9, 0.5 + abs(momentum_7d) / 50)
        signals.append({
            "card_id": card_id,
            "date": today,
            "signal_type": SIGNAL_MOMENTUM_BEARISH,
            "value": momentum_7d,
            "confidence": confidence,
            "details": {
                "momentum_7d": round(momentum_7d, 2),
                "momentum_14d": round(momentum_14d, 2),
                "current_price": round(current_price, 2),
            },
            "insight": f"{card_name} showing downward momentum: {momentum_7d:.1f}% over 7 days",
        })

    # Breakout/Breakdown signals
    if is_breakout:
        signals.append({
            "card_id": card_id,
            "date": today,
            "signal_type": SIGNAL_BREAKOUT,
            "value": current_price,
            "confidence": 0.75 if volume_increasing else 0.6,
            "details": {
                "current_price": round(current_price, 2),
                "prev_high": round(indicators.get("prev_high", 0), 2),
                "volume_increasing": volume_increasing,
            },
            "insight": f"{card_name} broke above 14-day high resistance at ${indicators.get('prev_high', 0):.2f}",
        })
    elif is_breakdown:
        signals.append({
            "card_id": card_id,
            "date": today,
            "signal_type": SIGNAL_BREAKDOWN,
            "value": current_price,
            "confidence": 0.75 if volume_increasing else 0.6,
            "details": {
                "current_price": round(current_price, 2),
                "prev_low": round(indicators.get("prev_low", 0), 2),
                "volume_increasing": volume_increasing,
            },
            "insight": f"{card_name} broke below 14-day low support at ${indicators.get('prev_low', 0):.2f}",
        })

    # Trend reversal signals
    _sma_7 = indicators.get("sma_7", 0)  # noqa: F841 - reserved for future trend signals
    sma_14 = indicators.get("sma_14", 0)
    prev_price = indicators.get("prev_price", 0)

    # Bullish reversal: price was below SMA14, now crossing above
    if current_price > sma_14 > prev_price and relative_position > 60:
        signals.append({
            "card_id": card_id,
            "date": today,
            "signal_type": SIGNAL_TREND_REVERSAL_UP,
            "value": current_price - sma_14,
            "confidence": 0.65,
            "details": {
                "current_price": round(current_price, 2),
                "sma_14": round(sma_14, 2),
                "relative_position": round(relative_position, 1),
            },
            "insight": f"{card_name} showing potential bullish reversal, crossing above 14-day average",
        })

    # Bearish reversal: price was above SMA14, now crossing below
    if current_price < sma_14 < prev_price and relative_position < 40:
        signals.append({
            "card_id": card_id,
            "date": today,
            "signal_type": SIGNAL_TREND_REVERSAL_DOWN,
            "value": sma_14 - current_price,
            "confidence": 0.65,
            "details": {
                "current_price": round(current_price, 2),
                "sma_14": round(sma_14, 2),
                "relative_position": round(relative_position, 1),
            },
            "insight": f"{card_name} showing potential bearish reversal, crossing below 14-day average",
        })

    # Accumulation signal (rising volume + rising price in lower range)
    if volume_increasing and momentum_7d > 0 and relative_position < 50:
        signals.append({
            "card_id": card_id,
            "date": today,
            "signal_type": SIGNAL_ACCUMULATION,
            "value": momentum_7d,
            "confidence": 0.6,
            "details": {
                "momentum_7d": round(momentum_7d, 2),
                "relative_position": round(relative_position, 1),
                "volume_increasing": True,
            },
            "insight": f"{card_name} showing accumulation pattern: rising volume with price in lower range",
        })

    # Distribution signal (rising volume + falling price in upper range)
    if volume_increasing and momentum_7d < 0 and relative_position > 50:
        signals.append({
            "card_id": card_id,
            "date": today,
            "signal_type": SIGNAL_DISTRIBUTION,
            "value": momentum_7d,
            "confidence": 0.6,
            "details": {
                "momentum_7d": round(momentum_7d, 2),
                "relative_position": round(relative_position, 1),
                "volume_increasing": True,
            },
            "insight": f"{card_name} showing distribution pattern: rising volume with price in upper range",
        })

    return signals


async def _create_signal(db: AsyncSession, signal_data: dict) -> None:
    """Create a signal in the database."""
    # Check if signal already exists for this card/date/type
    existing = await db.execute(
        select(Signal)
        .where(Signal.card_id == signal_data["card_id"])
        .where(Signal.date == signal_data["date"])
        .where(Signal.signal_type == signal_data["signal_type"])
    )
    if existing.scalar_one_or_none():
        # Update existing signal
        await db.execute(
            text("""
                UPDATE signals
                SET value = :value, confidence = :confidence,
                    details = :details, llm_insight = :insight
                WHERE card_id = :card_id AND date = :date AND signal_type = :signal_type
            """),
            {
                "card_id": signal_data["card_id"],
                "date": signal_data["date"],
                "signal_type": signal_data["signal_type"],
                "value": signal_data.get("value"),
                "confidence": signal_data.get("confidence"),
                "details": json.dumps(signal_data.get("details", {})),
                "insight": signal_data.get("insight"),
            },
        )
    else:
        # Create new signal
        signal = Signal(
            card_id=signal_data["card_id"],
            date=signal_data["date"],
            signal_type=signal_data["signal_type"],
            value=signal_data.get("value"),
            confidence=signal_data.get("confidence"),
            details=json.dumps(signal_data.get("details", {})),
            llm_insight=signal_data.get("insight"),
        )
        db.add(signal)
