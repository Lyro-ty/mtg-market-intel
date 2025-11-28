"""
Dashboard API endpoints.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Card, MetricsCardsDaily, Recommendation, Marketplace, PriceSnapshot
from app.schemas.dashboard import DashboardSummary, TopCard, MarketSpread

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
):
    """
    Get dashboard summary with key metrics and top movers.
    """
    # Get total counts
    total_cards = await db.scalar(select(func.count(Card.id))) or 0
    total_marketplaces = await db.scalar(
        select(func.count(Marketplace.id)).where(Marketplace.is_enabled == True)
    ) or 0
    
    # Cards with recent prices
    week_ago = datetime.utcnow() - timedelta(days=7)
    cards_with_prices = await db.scalar(
        select(func.count(func.distinct(PriceSnapshot.card_id))).where(
            PriceSnapshot.snapshot_time >= week_ago
        )
    ) or 0
    
    # Get top gainers (7-day change)
    top_gainers = await _get_top_movers(db, ascending=False, limit=5)
    
    # Get top losers (7-day change)
    top_losers = await _get_top_movers(db, ascending=True, limit=5)
    
    # Get highest spreads
    highest_spreads = await _get_highest_spreads(db, limit=5)
    
    # Recommendation counts
    rec_counts = await db.execute(
        select(
            Recommendation.action,
            func.count(Recommendation.id).label("count"),
        ).where(
            Recommendation.is_active == True
        ).group_by(Recommendation.action)
    )
    rec_by_action = {row.action: row.count for row in rec_counts.all()}
    
    total_recs = sum(rec_by_action.values())
    
    # Average stats
    avg_stats = await db.execute(
        select(
            func.avg(MetricsCardsDaily.price_change_pct_7d).label("avg_change_7d"),
            func.avg(MetricsCardsDaily.spread_pct).label("avg_spread"),
        ).where(
            MetricsCardsDaily.date >= datetime.utcnow().date() - timedelta(days=1)
        )
    )
    stats_row = avg_stats.first()
    
    return DashboardSummary(
        total_cards=total_cards,
        total_with_prices=cards_with_prices,
        total_marketplaces=total_marketplaces,
        top_gainers=top_gainers,
        top_losers=top_losers,
        highest_spreads=highest_spreads,
        total_recommendations=total_recs,
        buy_recommendations=rec_by_action.get("BUY", 0),
        sell_recommendations=rec_by_action.get("SELL", 0),
        hold_recommendations=rec_by_action.get("HOLD", 0),
        avg_price_change_7d=float(stats_row.avg_change_7d) if stats_row and stats_row.avg_change_7d else None,
        avg_spread_pct=float(stats_row.avg_spread) if stats_row and stats_row.avg_spread else None,
    )


async def _get_top_movers(
    db: AsyncSession,
    ascending: bool = False,
    limit: int = 5,
) -> list[TopCard]:
    """Get top gaining or losing cards."""
    # Get latest metrics date
    latest_date = await db.scalar(
        select(func.max(MetricsCardsDaily.date))
    )
    
    if not latest_date:
        return []
    
    query = select(MetricsCardsDaily, Card).join(
        Card, MetricsCardsDaily.card_id == Card.id
    ).where(
        MetricsCardsDaily.date == latest_date,
        MetricsCardsDaily.price_change_pct_7d.isnot(None),
    )
    
    if ascending:
        query = query.order_by(MetricsCardsDaily.price_change_pct_7d.asc())
    else:
        query = query.order_by(MetricsCardsDaily.price_change_pct_7d.desc())
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    return [
        TopCard(
            card_id=card.id,
            card_name=card.name,
            set_code=card.set_code,
            image_url=card.image_url_small,
            current_price=float(metrics.avg_price) if metrics.avg_price else None,
            price_change_pct=float(metrics.price_change_pct_7d),
            price_change_period="7d",
        )
        for metrics, card in rows
    ]


async def _get_highest_spreads(
    db: AsyncSession,
    limit: int = 5,
) -> list[MarketSpread]:
    """Get cards with highest price spreads across marketplaces."""
    # Get latest metrics with high spreads
    latest_date = await db.scalar(
        select(func.max(MetricsCardsDaily.date))
    )
    
    if not latest_date:
        return []
    
    query = select(MetricsCardsDaily, Card).join(
        Card, MetricsCardsDaily.card_id == Card.id
    ).where(
        MetricsCardsDaily.date == latest_date,
        MetricsCardsDaily.spread_pct.isnot(None),
        MetricsCardsDaily.spread_pct > 10,  # At least 10% spread
    ).order_by(
        MetricsCardsDaily.spread_pct.desc()
    ).limit(limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    spreads = []
    for metrics, card in rows:
        # Get marketplaces for this card
        snapshot_query = select(PriceSnapshot, Marketplace).join(
            Marketplace, PriceSnapshot.marketplace_id == Marketplace.id
        ).where(
            PriceSnapshot.card_id == card.id,
            func.date(PriceSnapshot.snapshot_time) == latest_date,
        ).order_by(PriceSnapshot.price)
        
        snapshot_result = await db.execute(snapshot_query)
        snapshot_rows = snapshot_result.all()
        
        if len(snapshot_rows) >= 2:
            lowest_snapshot, lowest_mp = snapshot_rows[0]
            highest_snapshot, highest_mp = snapshot_rows[-1]
            
            spreads.append(MarketSpread(
                card_id=card.id,
                card_name=card.name,
                set_code=card.set_code,
                image_url=card.image_url_small,
                lowest_price=float(lowest_snapshot.price),
                lowest_marketplace=lowest_mp.name,
                highest_price=float(highest_snapshot.price),
                highest_marketplace=highest_mp.name,
                spread_pct=float(metrics.spread_pct) if metrics.spread_pct else 0,
            ))
    
    return spreads


@router.get("/stats")
async def get_quick_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    Get quick statistics for the dashboard header.
    """
    total_cards = await db.scalar(select(func.count(Card.id))) or 0
    active_recs = await db.scalar(
        select(func.count(Recommendation.id)).where(Recommendation.is_active == True)
    ) or 0
    
    # Get price change stats
    latest_date = await db.scalar(select(func.max(MetricsCardsDaily.date)))
    
    if latest_date:
        stats = await db.execute(
            select(
                func.avg(MetricsCardsDaily.price_change_pct_7d).label("avg_change"),
                func.count().label("count"),
            ).where(
                MetricsCardsDaily.date == latest_date,
                MetricsCardsDaily.price_change_pct_7d.isnot(None),
            )
        )
        row = stats.first()
        avg_change = float(row.avg_change) if row and row.avg_change else 0
        tracked_cards = row.count if row else 0
    else:
        avg_change = 0
        tracked_cards = 0
    
    return {
        "total_cards": total_cards,
        "tracked_cards": tracked_cards,
        "active_recommendations": active_recs,
        "avg_price_change_7d": round(avg_change, 2),
    }

