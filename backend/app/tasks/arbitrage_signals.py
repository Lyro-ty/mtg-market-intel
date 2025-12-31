"""
Cross-market arbitrage signal generation task.

Generates ARBITRAGE signals when significant price differences exist
between marketplaces for the same card.

An arbitrage opportunity exists when:
- Same card is available on multiple marketplaces
- Price difference exceeds threshold (accounting for fees/shipping)
- There's sufficient supply on both ends
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select, func, and_

from app.db.session import async_session_maker
from app.models import PriceSnapshot, Signal, Marketplace
from app.tasks.utils import run_async

logger = structlog.get_logger()

# Thresholds for arbitrage detection
MIN_PRICE_DIFF_PCT = 0.15  # 15% minimum difference to flag
MIN_CARD_PRICE = 5.0  # Only flag cards worth at least $5 (fee makes low-value arb impractical)
MIN_PROFIT_USD = 1.0  # Minimum $1 profit after estimated fees
ESTIMATED_FEE_PCT = 0.10  # Estimate 10% in fees/shipping per side


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="generate_arbitrage_signals")
def generate_arbitrage_signals(self) -> dict[str, Any]:
    """
    Generate ARBITRAGE signals by comparing prices across marketplaces.

    Looks for cards where buying on one marketplace and selling on another
    would yield a profit after estimated fees.

    Returns:
        Dict with signal generation statistics
    """
    return run_async(_generate_arbitrage_signals_async())


async def _generate_arbitrage_signals_async() -> dict[str, Any]:
    """Async implementation of arbitrage signal generation."""
    stats = {
        "cards_analyzed": 0,
        "arbitrage_signals": 0,
        "total_potential_profit": 0.0,
        "marketplace_pairs": {},
        "errors": [],
    }

    async with async_session_maker() as db:
        try:
            # Get marketplace names for readable output
            marketplace_query = select(Marketplace)
            result = await db.execute(marketplace_query)
            marketplaces = {m.id: m.name for m in result.scalars()}

            # Get recent prices grouped by card and marketplace
            today = date.today()
            yesterday = today - timedelta(days=1)

            # Get latest price per card per marketplace
            subquery = (
                select(
                    PriceSnapshot.card_id,
                    PriceSnapshot.marketplace_id,
                    func.max(PriceSnapshot.time).label('latest_time')
                )
                .where(
                    and_(
                        func.date(PriceSnapshot.time) >= yesterday,
                        PriceSnapshot.currency == "USD",
                        PriceSnapshot.price >= MIN_CARD_PRICE,
                    )
                )
                .group_by(PriceSnapshot.card_id, PriceSnapshot.marketplace_id)
                .subquery()
            )

            # Get actual prices at those times
            prices_query = (
                select(
                    PriceSnapshot.card_id,
                    PriceSnapshot.marketplace_id,
                    PriceSnapshot.price,
                    PriceSnapshot.num_listings,
                )
                .join(
                    subquery,
                    and_(
                        PriceSnapshot.card_id == subquery.c.card_id,
                        PriceSnapshot.marketplace_id == subquery.c.marketplace_id,
                        PriceSnapshot.time == subquery.c.latest_time,
                    )
                )
            )

            result = await db.execute(prices_query)
            prices = result.all()

            # Group prices by card
            card_prices: dict[int, list] = {}
            for row in prices:
                if row.card_id not in card_prices:
                    card_prices[row.card_id] = []
                card_prices[row.card_id].append({
                    'marketplace_id': row.marketplace_id,
                    'price': float(row.price),
                    'num_listings': row.num_listings or 1,
                })

            # Analyze cards with prices on multiple marketplaces
            for card_id, price_list in card_prices.items():
                if len(price_list) < 2:
                    continue

                stats["cards_analyzed"] += 1

                # Find best arbitrage opportunity for this card
                best_arb = await _find_best_arbitrage(price_list, marketplaces)

                if best_arb:
                    await _create_arbitrage_signal(db, card_id, best_arb, stats)

            await db.commit()
            logger.info("Arbitrage signals generated", **stats)

        except Exception as e:
            error_msg = f"Failed to generate arbitrage signals: {str(e)}"
            logger.error(error_msg, error=str(e))
            stats["errors"].append(error_msg)
            await db.rollback()

    return stats


async def _find_best_arbitrage(
    price_list: list[dict],
    marketplaces: dict[int, str],
) -> dict | None:
    """
    Find the best arbitrage opportunity from a list of prices.

    Returns details of the best opportunity or None if none exist.
    """
    best_profit = 0
    best_opportunity = None

    # Compare all pairs
    for i, buy_option in enumerate(price_list):
        for sell_option in price_list[i+1:]:
            # Try both directions
            for buy, sell in [(buy_option, sell_option), (sell_option, buy_option)]:
                buy_price = buy['price']
                sell_price = sell['price']

                # Calculate net profit after fees
                buy_cost = buy_price * (1 + ESTIMATED_FEE_PCT)
                sell_revenue = sell_price * (1 - ESTIMATED_FEE_PCT)
                profit = sell_revenue - buy_cost

                # Check if meets thresholds
                if profit < MIN_PROFIT_USD:
                    continue

                profit_pct = profit / buy_cost
                if profit_pct < MIN_PRICE_DIFF_PCT:
                    continue

                if profit > best_profit:
                    best_profit = profit
                    best_opportunity = {
                        'buy_marketplace_id': buy['marketplace_id'],
                        'sell_marketplace_id': sell['marketplace_id'],
                        'buy_marketplace': marketplaces.get(buy['marketplace_id'], 'Unknown'),
                        'sell_marketplace': marketplaces.get(sell['marketplace_id'], 'Unknown'),
                        'buy_price': buy_price,
                        'sell_price': sell_price,
                        'buy_listings': buy['num_listings'],
                        'sell_listings': sell['num_listings'],
                        'profit': profit,
                        'profit_pct': profit_pct,
                    }

    return best_opportunity


async def _create_arbitrage_signal(
    db,
    card_id: int,
    arb: dict,
    stats: dict,
) -> Signal:
    """Create or update an arbitrage signal for today."""
    today = date.today()

    # Track marketplace pair stats
    pair_key = f"{arb['buy_marketplace']}->{arb['sell_marketplace']}"
    if pair_key not in stats["marketplace_pairs"]:
        stats["marketplace_pairs"][pair_key] = 0
    stats["marketplace_pairs"][pair_key] += 1

    # Update running totals
    stats["arbitrage_signals"] += 1
    stats["total_potential_profit"] += arb['profit']

    confidence = min(0.95, 0.5 + arb['profit_pct'])

    # Check for existing signal today
    existing = await db.scalar(
        select(Signal).where(
            and_(
                Signal.card_id == card_id,
                Signal.signal_type == "arbitrage",
                Signal.date == today
            )
        )
    )

    details = {
        "buy_marketplace": arb['buy_marketplace'],
        "sell_marketplace": arb['sell_marketplace'],
        "buy_price": arb['buy_price'],
        "sell_price": arb['sell_price'],
        "estimated_profit": round(arb['profit'], 2),
        "profit_pct": round(arb['profit_pct'] * 100, 1),
        "buy_listings": arb['buy_listings'],
        "sell_listings": arb['sell_listings'],
        "fee_estimate_pct": ESTIMATED_FEE_PCT * 100,
    }

    if existing:
        existing.value = arb['profit']
        existing.confidence = confidence
        existing.details = json.dumps(details)
        return existing
    else:
        signal = Signal(
            card_id=card_id,
            date=today,
            signal_type="arbitrage",
            value=arb['profit'],
            confidence=confidence,
            details=json.dumps(details),
        )
        db.add(signal)
        return signal
