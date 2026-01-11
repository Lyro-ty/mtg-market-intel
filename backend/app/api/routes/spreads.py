"""
Spread analysis API endpoints.

Provides insights on buylist-to-retail spreads and cross-marketplace arbitrage opportunities.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError, TimeoutError as SQLTimeoutError, DBAPIError

from app.db.session import get_db
from app.models import Card, PriceSnapshot, Marketplace, BuylistSnapshot

router = APIRouter(prefix="/spreads", tags=["spreads"])
logger = structlog.get_logger(__name__)


class BuylistOpportunity(BaseModel):
    """A card with a favorable buylist-to-retail spread."""
    card_id: int
    card_name: str
    set_code: str
    image_url: str | None = None
    retail_price: float
    buylist_price: float
    vendor: str
    spread: float
    spread_pct: float
    credit_price: float | None = None
    credit_spread_pct: float | None = None


class ArbitrageOpportunity(BaseModel):
    """A cross-marketplace arbitrage opportunity."""
    card_id: int
    card_name: str
    set_code: str
    image_url: str | None = None
    buy_marketplace: str
    buy_price: float
    sell_marketplace: str
    sell_price: float
    profit: float
    profit_pct: float


class BuylistOpportunitiesResponse(BaseModel):
    """Response for buylist opportunities endpoint."""
    opportunities: list[BuylistOpportunity]
    total: int


class ArbitrageOpportunitiesResponse(BaseModel):
    """Response for arbitrage opportunities endpoint."""
    opportunities: list[ArbitrageOpportunity]
    total: int


@router.get("/best-buylist-opportunities", response_model=BuylistOpportunitiesResponse)
async def get_best_buylist_opportunities(
    limit: int = Query(default=20, le=100),
    min_spread_pct: float = Query(default=10.0, description="Minimum spread percentage"),
    min_price: float = Query(default=1.0, description="Minimum retail price to consider"),
    vendor: Optional[str] = Query(None, description="Filter by vendor (cardkingdom, etc.)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Find cards with the best buylist-to-retail spreads.

    A high spread means there's a large difference between what you pay retail
    and what vendors will pay you on buylist. This can indicate:
    - Cards that are undervalued at retail
    - Cards vendors are aggressively buying
    - Good selling opportunities for your collection

    Returns cards sorted by spread percentage (highest first).
    """
    # Get latest retail prices
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    # Subquery for latest retail price per card
    retail_subq = (
        select(
            PriceSnapshot.card_id,
            func.max(PriceSnapshot.time).label("latest_time"),
        )
        .where(PriceSnapshot.time >= cutoff)
        .group_by(PriceSnapshot.card_id)
        .subquery()
    )

    # Subquery for latest buylist price per card
    buylist_subq = (
        select(
            BuylistSnapshot.card_id,
            BuylistSnapshot.vendor,
            func.max(BuylistSnapshot.time).label("latest_time"),
        )
        .where(BuylistSnapshot.time >= cutoff)
        .group_by(BuylistSnapshot.card_id, BuylistSnapshot.vendor)
        .subquery()
    )

    # Main query joining cards, retail prices, and buylist prices
    query = (
        select(
            Card.id.label("card_id"),
            Card.name.label("card_name"),
            Card.set_code,
            Card.image_url_small.label("image_url"),
            PriceSnapshot.price.label("retail_price"),
            BuylistSnapshot.price.label("buylist_price"),
            BuylistSnapshot.vendor,
            BuylistSnapshot.credit_price,
        )
        .join(retail_subq, Card.id == retail_subq.c.card_id)
        .join(
            PriceSnapshot,
            (PriceSnapshot.card_id == retail_subq.c.card_id) &
            (PriceSnapshot.time == retail_subq.c.latest_time)
        )
        .join(buylist_subq, Card.id == buylist_subq.c.card_id)
        .join(
            BuylistSnapshot,
            (BuylistSnapshot.card_id == buylist_subq.c.card_id) &
            (BuylistSnapshot.vendor == buylist_subq.c.vendor) &
            (BuylistSnapshot.time == buylist_subq.c.latest_time)
        )
        .where(PriceSnapshot.price >= min_price)
        .where(BuylistSnapshot.price > 0)
    )

    if vendor:
        query = query.where(BuylistSnapshot.vendor == vendor.lower())

    result = await db.execute(query)
    rows = result.all()

    # Calculate spreads and filter
    opportunities = []
    for row in rows:
        if row.retail_price <= 0:
            continue

        spread = row.retail_price - row.buylist_price
        spread_pct = (spread / row.retail_price) * 100

        # We want LOWER spreads for buylist opportunities
        # Low spread = vendor paying close to retail = good for selling
        # But the plan asks for "largest spread" which means high profit margin for buying
        # Let's interpret this as: cards where spread is interesting for analysis

        if spread_pct < min_spread_pct:
            continue

        credit_spread_pct = None
        if row.credit_price and row.credit_price > 0:
            credit_spread = row.retail_price - row.credit_price
            credit_spread_pct = (credit_spread / row.retail_price) * 100

        opportunities.append(BuylistOpportunity(
            card_id=row.card_id,
            card_name=row.card_name,
            set_code=row.set_code,
            image_url=row.image_url,
            retail_price=float(row.retail_price),
            buylist_price=float(row.buylist_price),
            vendor=row.vendor,
            spread=spread,
            spread_pct=spread_pct,
            credit_price=float(row.credit_price) if row.credit_price else None,
            credit_spread_pct=credit_spread_pct,
        ))

    # Sort by spread percentage (highest first) and limit
    opportunities.sort(key=lambda x: x.spread_pct, reverse=True)
    opportunities = opportunities[:limit]

    return BuylistOpportunitiesResponse(
        opportunities=opportunities,
        total=len(opportunities),
    )


@router.get("/best-selling-opportunities", response_model=BuylistOpportunitiesResponse)
async def get_best_selling_opportunities(
    limit: int = Query(default=20, le=100),
    max_spread_pct: float = Query(default=50.0, description="Maximum spread percentage (lower = better for selling)"),
    min_buylist: float = Query(default=1.0, description="Minimum buylist price"),
    db: AsyncSession = Depends(get_db),
):
    """
    Find cards where buylist prices are closest to retail (best for selling).

    A LOW spread means vendors are paying close to retail price - these are
    the best cards to sell on buylist rather than waiting for a buyer.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    # Subquery for latest retail price per card
    retail_subq = (
        select(
            PriceSnapshot.card_id,
            func.max(PriceSnapshot.time).label("latest_time"),
        )
        .where(PriceSnapshot.time >= cutoff)
        .group_by(PriceSnapshot.card_id)
        .subquery()
    )

    # Subquery for latest buylist price per card
    buylist_subq = (
        select(
            BuylistSnapshot.card_id,
            BuylistSnapshot.vendor,
            func.max(BuylistSnapshot.time).label("latest_time"),
        )
        .where(BuylistSnapshot.time >= cutoff)
        .group_by(BuylistSnapshot.card_id, BuylistSnapshot.vendor)
        .subquery()
    )

    # Main query
    query = (
        select(
            Card.id.label("card_id"),
            Card.name.label("card_name"),
            Card.set_code,
            Card.image_url_small.label("image_url"),
            PriceSnapshot.price.label("retail_price"),
            BuylistSnapshot.price.label("buylist_price"),
            BuylistSnapshot.vendor,
            BuylistSnapshot.credit_price,
        )
        .join(retail_subq, Card.id == retail_subq.c.card_id)
        .join(
            PriceSnapshot,
            (PriceSnapshot.card_id == retail_subq.c.card_id) &
            (PriceSnapshot.time == retail_subq.c.latest_time)
        )
        .join(buylist_subq, Card.id == buylist_subq.c.card_id)
        .join(
            BuylistSnapshot,
            (BuylistSnapshot.card_id == buylist_subq.c.card_id) &
            (BuylistSnapshot.vendor == buylist_subq.c.vendor) &
            (BuylistSnapshot.time == buylist_subq.c.latest_time)
        )
        .where(BuylistSnapshot.price >= min_buylist)
        .where(PriceSnapshot.price > 0)
    )

    result = await db.execute(query)
    rows = result.all()

    opportunities = []
    for row in rows:
        if row.retail_price <= 0:
            continue

        spread = row.retail_price - row.buylist_price
        spread_pct = (spread / row.retail_price) * 100

        # For selling, we want LOW spreads
        if spread_pct > max_spread_pct:
            continue

        credit_spread_pct = None
        if row.credit_price and row.credit_price > 0:
            credit_spread = row.retail_price - row.credit_price
            credit_spread_pct = (credit_spread / row.retail_price) * 100

        opportunities.append(BuylistOpportunity(
            card_id=row.card_id,
            card_name=row.card_name,
            set_code=row.set_code,
            image_url=row.image_url,
            retail_price=float(row.retail_price),
            buylist_price=float(row.buylist_price),
            vendor=row.vendor,
            spread=spread,
            spread_pct=spread_pct,
            credit_price=float(row.credit_price) if row.credit_price else None,
            credit_spread_pct=credit_spread_pct,
        ))

    # Sort by spread percentage (lowest first = best for selling)
    opportunities.sort(key=lambda x: x.spread_pct)
    opportunities = opportunities[:limit]

    return BuylistOpportunitiesResponse(
        opportunities=opportunities,
        total=len(opportunities),
    )


@router.get("/arbitrage-opportunities", response_model=ArbitrageOpportunitiesResponse)
async def get_arbitrage_opportunities(
    limit: int = Query(default=20, le=100),
    min_profit_pct: float = Query(default=15.0, description="Minimum profit percentage"),
    min_profit: float = Query(default=1.0, description="Minimum absolute profit in USD"),
    db: AsyncSession = Depends(get_db),
):
    """
    Find cross-marketplace arbitrage opportunities.

    Returns cards where the price difference between marketplaces
    is large enough to potentially profit from buying low and selling high.

    Note: Does not account for fees, shipping, or transaction costs.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    # Get latest prices grouped by card and marketplace
    latest_prices_subq = (
        select(
            PriceSnapshot.card_id,
            PriceSnapshot.marketplace_id,
            func.max(PriceSnapshot.time).label("latest_time"),
        )
        .where(PriceSnapshot.time >= cutoff)
        .group_by(PriceSnapshot.card_id, PriceSnapshot.marketplace_id)
        .subquery()
    )

    # Get full price data for latest snapshots
    prices_query = (
        select(
            Card.id.label("card_id"),
            Card.name.label("card_name"),
            Card.set_code,
            Card.image_url_small.label("image_url"),
            PriceSnapshot.marketplace_id,
            Marketplace.name.label("marketplace_name"),
            PriceSnapshot.price,
        )
        .join(latest_prices_subq, Card.id == latest_prices_subq.c.card_id)
        .join(
            PriceSnapshot,
            (PriceSnapshot.card_id == latest_prices_subq.c.card_id) &
            (PriceSnapshot.marketplace_id == latest_prices_subq.c.marketplace_id) &
            (PriceSnapshot.time == latest_prices_subq.c.latest_time)
        )
        .join(Marketplace, PriceSnapshot.marketplace_id == Marketplace.id)
        .where(PriceSnapshot.price > 0)
    )

    result = await db.execute(prices_query)
    rows = result.all()

    # Group prices by card
    card_prices: dict[int, list] = {}
    for row in rows:
        if row.card_id not in card_prices:
            card_prices[row.card_id] = []
        card_prices[row.card_id].append({
            "card_name": row.card_name,
            "set_code": row.set_code,
            "image_url": row.image_url,
            "marketplace_id": row.marketplace_id,
            "marketplace_name": row.marketplace_name,
            "price": float(row.price),
        })

    # Find arbitrage opportunities
    opportunities = []
    for card_id, prices in card_prices.items():
        if len(prices) < 2:
            continue

        # Find min and max prices
        min_price_data = min(prices, key=lambda x: x["price"])
        max_price_data = max(prices, key=lambda x: x["price"])

        if min_price_data["marketplace_id"] == max_price_data["marketplace_id"]:
            continue

        profit = max_price_data["price"] - min_price_data["price"]
        profit_pct = (profit / min_price_data["price"]) * 100

        if profit < min_profit or profit_pct < min_profit_pct:
            continue

        opportunities.append(ArbitrageOpportunity(
            card_id=card_id,
            card_name=min_price_data["card_name"],
            set_code=min_price_data["set_code"],
            image_url=min_price_data["image_url"],
            buy_marketplace=min_price_data["marketplace_name"],
            buy_price=min_price_data["price"],
            sell_marketplace=max_price_data["marketplace_name"],
            sell_price=max_price_data["price"],
            profit=profit,
            profit_pct=profit_pct,
        ))

    # Sort by profit (highest first)
    opportunities.sort(key=lambda x: x.profit, reverse=True)
    opportunities = opportunities[:limit]

    return ArbitrageOpportunitiesResponse(
        opportunities=opportunities,
        total=len(opportunities),
    )


@router.get("/market-summary")
async def get_spread_market_summary(
    db: AsyncSession = Depends(get_db),
):
    """
    Get summary statistics for spread analysis.

    Returns average spreads, arbitrage opportunity counts, etc.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    # Count cards with buylist data
    buylist_count_query = (
        select(func.count(func.distinct(BuylistSnapshot.card_id)))
        .where(BuylistSnapshot.time >= cutoff)
    )
    buylist_card_count = await db.scalar(buylist_count_query) or 0

    # Get average spread
    # This is a simplified calculation - in production you'd use a more complex query
    avg_spread_query = text("""
        WITH latest_buylist AS (
            SELECT DISTINCT ON (card_id, vendor)
                card_id, price as buylist_price
            FROM buylist_snapshots
            WHERE time >= :cutoff
            ORDER BY card_id, vendor, time DESC
        ),
        latest_retail AS (
            SELECT DISTINCT ON (card_id)
                card_id, price as retail_price
            FROM price_snapshots
            WHERE time >= :cutoff AND price > 0
            ORDER BY card_id, time DESC
        )
        SELECT
            AVG((lr.retail_price - lb.buylist_price) / lr.retail_price * 100) as avg_spread_pct,
            COUNT(*) as sample_size
        FROM latest_retail lr
        JOIN latest_buylist lb ON lr.card_id = lb.card_id
        WHERE lr.retail_price > lb.buylist_price
    """)

    try:
        result = await db.execute(avg_spread_query, {"cutoff": cutoff})
        row = result.first()
        avg_spread_pct = float(row.avg_spread_pct) if row and row.avg_spread_pct else None
        sample_size = row.sample_size if row else 0
    except (OperationalError, SQLTimeoutError, DBAPIError) as e:
        logger.warning("Database error calculating average spread", error=str(e), error_type=type(e).__name__)
        avg_spread_pct = None
        sample_size = 0
    except (ValueError, TypeError) as e:
        logger.warning("Data parsing error calculating average spread", error=str(e))
        avg_spread_pct = None
        sample_size = 0

    return {
        "cards_with_buylist_data": buylist_card_count,
        "average_spread_pct": avg_spread_pct,
        "sample_size": sample_size,
        "data_freshness_hours": 48,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
