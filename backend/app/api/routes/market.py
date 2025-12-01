"""
Market API endpoints for market-wide analytics and charts.
"""
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import (
    Card,
    MetricsCardsDaily,
    PriceSnapshot,
    Listing,
    Marketplace,
)
from app.schemas.dashboard import TopCard

router = APIRouter()


@router.get("/overview")
async def get_market_overview(
    db: AsyncSession = Depends(get_db),
):
    """
    Get market overview statistics.
    
    Returns key market metrics for the dashboard stats strip.
    """
    # Total cards tracked
    total_cards = await db.scalar(select(func.count(Card.id))) or 0
    
    # Total listings (active listings from last 24h)
    day_ago = datetime.utcnow() - timedelta(days=1)
    total_listings = await db.scalar(
        select(func.sum(Listing.quantity)).where(
            Listing.last_seen_at >= day_ago
        )
    ) or 0
    
    # 24h trade volume (USD) - estimate from price snapshots and listings
    # This is an approximation: sum of (price * quantity) for recent listings
    volume_24h = await db.scalar(
        select(func.sum(Listing.price * Listing.quantity)).where(
            Listing.last_seen_at >= day_ago,
            Listing.currency == "USD"
        )
    ) or 0
    
    # If no USD listings, try to estimate from other currencies (rough conversion)
    if volume_24h == 0:
        volume_24h = await db.scalar(
            select(func.sum(Listing.price * Listing.quantity)).where(
                Listing.last_seen_at >= day_ago
            )
        ) or 0
    
    # 24h average price change
    latest_date = await db.scalar(select(func.max(MetricsCardsDaily.date)))
    avg_price_change_24h = None
    if latest_date:
        result = await db.execute(
            select(
                func.avg(MetricsCardsDaily.price_change_pct_1d).label("avg_change")
            ).where(
                MetricsCardsDaily.date == latest_date,
                MetricsCardsDaily.price_change_pct_1d.isnot(None),
            )
        )
        row = result.first()
        if row and row.avg_change:
            avg_price_change_24h = float(row.avg_change)
    
    # Active formats tracked - count unique formats from card legalities
    # Parse legalities JSON to count formats where card is legal
    # For now, we'll use a simple count of cards with legalities data
    # In a real implementation, you'd parse the JSON and count unique formats
    cards_with_legalities = await db.scalar(
        select(func.count(Card.id)).where(
            Card.legalities.isnot(None),
            Card.legalities != ""
        )
    ) or 0
    
    # Estimate active formats by parsing a sample of legalities
    # This is a simplified approach - in production you'd want to cache this
    sample_cards = await db.execute(
        select(Card.legalities).where(
            Card.legalities.isnot(None),
            Card.legalities != ""
        ).limit(1000)
    )
    
    formats_set = set()
    for row in sample_cards.all():
        if row.legalities:
            try:
                legalities = json.loads(row.legalities)
                # Count formats where card is legal (not banned/restricted)
                for format_name, status in legalities.items():
                    if status in ["legal", "restricted"]:
                        formats_set.add(format_name)
            except (json.JSONDecodeError, TypeError):
                continue
    
    active_formats_tracked = len(formats_set) if formats_set else 0
    
    # If we couldn't determine formats, use a default estimate
    if active_formats_tracked == 0:
        active_formats_tracked = 10  # Common formats: Standard, Modern, Legacy, Vintage, Commander, etc.
    
    return {
        "totalCardsTracked": total_cards,
        "totalListings": int(total_listings),
        "volume24hUsd": float(volume_24h),
        "avgPriceChange24hPct": avg_price_change_24h,
        "activeFormatsTracked": active_formats_tracked,
    }


@router.get("/index")
async def get_market_index(
    range: str = Query("7d", regex="^(7d|30d|90d|1y)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get market index data for charting.
    
    The market index is a normalized aggregate of card prices over time.
    """
    # Determine date range
    now = datetime.utcnow()
    if range == "7d":
        start_date = now - timedelta(days=7)
    elif range == "30d":
        start_date = now - timedelta(days=30)
    elif range == "90d":
        start_date = now - timedelta(days=90)
    else:  # 1y
        start_date = now - timedelta(days=365)
    
    # Get daily average prices across all cards
    # This creates a market index by averaging card prices each day
    query = select(
        func.date(MetricsCardsDaily.date).label("date"),
        func.avg(MetricsCardsDaily.avg_price).label("avg_price"),
        func.count(func.distinct(MetricsCardsDaily.card_id)).label("card_count"),
    ).where(
        MetricsCardsDaily.date >= start_date.date(),
        MetricsCardsDaily.avg_price.isnot(None),
    ).group_by(
        func.date(MetricsCardsDaily.date)
    ).order_by(
        func.date(MetricsCardsDaily.date)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    if not rows:
        # Return mock data if no real data available
        points = []
        base_value = 100.0
        for i in range(7 if range == "7d" else (30 if range == "30d" else (90 if range == "90d" else 365))):
            date = start_date + timedelta(days=i)
            # Simulate small variations
            value = base_value + (i % 10 - 5) * 0.5
            points.append({
                "timestamp": date.isoformat(),
                "indexValue": round(value, 2),
            })
        return {
            "range": range,
            "points": points,
            "isMockData": True,
        }
    
    # Calculate normalized index (base 100 at first point)
    points = []
    base_value = None
    
    for row in rows:
        if row.avg_price:
            if base_value is None:
                base_value = float(row.avg_price)
            
            # Normalize to base 100
            index_value = (float(row.avg_price) / base_value) * 100.0
            
            points.append({
                "timestamp": row.date.isoformat() if isinstance(row.date, datetime) else str(row.date),
                "indexValue": round(index_value, 2),
            })
    
    return {
        "range": range,
        "points": points,
        "isMockData": False,
    }


@router.get("/top-movers")
async def get_top_movers(
    window: str = Query("24h", regex="^(24h|7d)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get top gaining and losing cards.
    """
    # Determine time window
    if window == "24h":
        change_field = MetricsCardsDaily.price_change_pct_1d
        period = "1d"
    else:  # 7d
        change_field = MetricsCardsDaily.price_change_pct_7d
        period = "7d"
    
    latest_date = await db.scalar(select(func.max(MetricsCardsDaily.date)))
    
    if not latest_date:
        return {
            "window": window,
            "gainers": [],
            "losers": [],
            "isMockData": True,
        }
    
    # Get top gainers
    gainers_query = select(MetricsCardsDaily, Card).join(
        Card, MetricsCardsDaily.card_id == Card.id
    ).where(
        MetricsCardsDaily.date == latest_date,
        change_field.isnot(None),
        change_field > 0,  # Only positive changes
    ).order_by(
        desc(change_field)
    ).limit(10)
    
    gainers_result = await db.execute(gainers_query)
    gainers_rows = gainers_result.all()
    
    # Get top losers
    losers_query = select(MetricsCardsDaily, Card).join(
        Card, MetricsCardsDaily.card_id == Card.id
    ).where(
        MetricsCardsDaily.date == latest_date,
        change_field.isnot(None),
        change_field < 0,  # Only negative changes
    ).order_by(
        change_field.asc()  # Most negative first
    ).limit(10)
    
    losers_result = await db.execute(losers_query)
    losers_rows = losers_result.all()
    
    # Format gainers
    gainers = []
    for metrics, card in gainers_rows:
        # Get volume (number of listings)
        volume = metrics.total_listings or 0
        
        # Try to determine format from legalities
        format_name = "Standard"  # Default
        if card.legalities:
            try:
                legalities = json.loads(card.legalities)
                # Find first format where card is legal
                for fmt, status in legalities.items():
                    if status == "legal":
                        format_name = fmt
                        break
            except (json.JSONDecodeError, TypeError):
                pass
        
        gainers.append({
            "cardName": card.name,
            "setCode": card.set_code,
            "format": format_name,
            "currentPriceUsd": float(metrics.avg_price) if metrics.avg_price else 0.0,
            "changePct": float(change_field) if change_field else 0.0,
            "volume": volume,
        })
    
    # Format losers
    losers = []
    for metrics, card in losers_rows:
        # Get volume
        volume = metrics.total_listings or 0
        
        # Try to determine format
        format_name = "Standard"  # Default
        if card.legalities:
            try:
                legalities = json.loads(card.legalities)
                for fmt, status in legalities.items():
                    if status == "legal":
                        format_name = fmt
                        break
            except (json.JSONDecodeError, TypeError):
                pass
        
        losers.append({
            "cardName": card.name,
            "setCode": card.set_code,
            "format": format_name,
            "currentPriceUsd": float(metrics.avg_price) if metrics.avg_price else 0.0,
            "changePct": float(change_field) if change_field else 0.0,
            "volume": volume,
        })
    
    # If no data, return mock data
    if not gainers and not losers:
        return {
            "window": window,
            "gainers": _get_mock_gainers(),
            "losers": _get_mock_losers(),
            "isMockData": True,
        }
    
    return {
        "window": window,
        "gainers": gainers,
        "losers": losers,
        "isMockData": False,
    }


@router.get("/volume-by-format")
async def get_volume_by_format(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
):
    """
    Get trading volume grouped by format over time.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get cards with legalities and their metrics
    query = select(
        Card.legalities,
        MetricsCardsDaily.date,
        func.sum(MetricsCardsDaily.total_listings * MetricsCardsDaily.avg_price).label("volume"),
    ).join(
        MetricsCardsDaily, Card.id == MetricsCardsDaily.card_id
    ).where(
        MetricsCardsDaily.date >= start_date.date(),
        MetricsCardsDaily.avg_price.isnot(None),
        MetricsCardsDaily.total_listings.isnot(None),
        Card.legalities.isnot(None),
        Card.legalities != "",
    ).group_by(
        Card.legalities,
        MetricsCardsDaily.date
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    if not rows:
        # Return mock data
        return {
            "days": days,
            "formats": _get_mock_volume_by_format(days),
            "isMockData": True,
        }
    
    # Group by format and date
    format_data = {}
    
    for row in rows:
        if not row.legalities:
            continue
        
        try:
            legalities = json.loads(row.legalities)
            volume = float(row.volume) if row.volume else 0.0
            date_str = row.date.isoformat() if isinstance(row.date, datetime) else str(row.date)
            
            # Distribute volume across all formats where card is legal
            legal_formats = [fmt for fmt, status in legalities.items() if status == "legal"]
            
            if legal_formats:
                volume_per_format = volume / len(legal_formats)
                for fmt in legal_formats:
                    if fmt not in format_data:
                        format_data[fmt] = {}
                    if date_str not in format_data[fmt]:
                        format_data[fmt][date_str] = 0.0
                    format_data[fmt][date_str] += volume_per_format
        except (json.JSONDecodeError, TypeError):
            continue
    
    # Convert to array format
    formats = []
    for format_name, dates in format_data.items():
        points = [
            {"timestamp": date, "volume": round(vol, 2)}
            for date, vol in sorted(dates.items())
        ]
        formats.append({
            "format": format_name,
            "data": points,
        })
    
    # If no data, return mock
    if not formats:
        return {
            "days": days,
            "formats": _get_mock_volume_by_format(days),
            "isMockData": True,
        }
    
    return {
        "days": days,
        "formats": formats,
        "isMockData": False,
    }


def _get_mock_gainers():
    """Generate mock gainers data."""
    return [
        {
            "cardName": "Lightning Bolt",
            "setCode": "M21",
            "format": "Modern",
            "currentPriceUsd": 2.50,
            "changePct": 15.3,
            "volume": 245,
        },
        {
            "cardName": "Sol Ring",
            "setCode": "C21",
            "format": "Commander",
            "currentPriceUsd": 1.25,
            "changePct": 12.8,
            "volume": 189,
        },
        {
            "cardName": "Counterspell",
            "setCode": "2XM",
            "format": "Legacy",
            "currentPriceUsd": 3.75,
            "changePct": 11.2,
            "volume": 156,
        },
    ]


def _get_mock_losers():
    """Generate mock losers data."""
    return [
        {
            "cardName": "Example Card A",
            "setCode": "STX",
            "format": "Standard",
            "currentPriceUsd": 5.00,
            "changePct": -8.5,
            "volume": 98,
        },
        {
            "cardName": "Example Card B",
            "setCode": "KHM",
            "format": "Standard",
            "currentPriceUsd": 2.30,
            "changePct": -7.2,
            "volume": 112,
        },
        {
            "cardName": "Example Card C",
            "setCode": "ZNR",
            "format": "Modern",
            "currentPriceUsd": 1.50,
            "changePct": -6.1,
            "volume": 87,
        },
    ]


def _get_mock_volume_by_format(days: int):
    """Generate mock volume by format data."""
    formats = ["Standard", "Modern", "Commander", "Legacy", "Vintage"]
    points_per_format = max(7, min(30, days // 7))  # Roughly weekly points
    
    result = []
    base_date = datetime.utcnow() - timedelta(days=days)
    
    for fmt in formats:
        data = []
        base_volume = 10000 + (hash(fmt) % 50000)  # Vary by format
        
        for i in range(points_per_format):
            date = base_date + timedelta(days=i * (days // points_per_format))
            # Add some variation
            volume = base_volume + (i % 10 - 5) * 500
            data.append({
                "timestamp": date.isoformat(),
                "volume": round(volume, 2),
            })
        
        result.append({
            "format": fmt,
            "data": data,
        })
    
    return result

