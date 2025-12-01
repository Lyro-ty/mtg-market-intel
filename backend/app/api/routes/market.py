"""
Market API endpoints for market-wide analytics and charts.
"""
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_dashboard_cache
from app.core.config import get_settings
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
cache = get_dashboard_cache()


@router.get("/overview")
async def get_market_overview(
    db: AsyncSession = Depends(get_db),
):
    """
    Get market overview statistics.
    
    Returns key market metrics for the dashboard stats strip.
    """
    # Check cache first
    cache_key = "market:overview"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
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
    
    # Active formats tracked - use a more efficient approach
    # Instead of parsing 1000 cards, use a smaller sample and cache the result
    # Common formats we track
    COMMON_FORMATS = ["Standard", "Modern", "Legacy", "Vintage", "Commander", "Pioneer", "Pauper", "Historic", "Brawl", "Alchemy"]
    
    # Count formats by checking if any card is legal in each format
    # Use a more efficient query that checks for format existence
    sample_cards = await db.execute(
        select(Card.legalities).where(
            Card.legalities.isnot(None),
            Card.legalities != ""
        ).limit(100)  # Reduced from 1000 to 100 for faster parsing
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
                        # Early exit if we've found all common formats
                        if len(formats_set) >= len(COMMON_FORMATS):
                            break
            except (json.JSONDecodeError, TypeError):
                continue
        if len(formats_set) >= len(COMMON_FORMATS):
            break
    
    active_formats_tracked = len(formats_set) if formats_set else len(COMMON_FORMATS)
    
    result = {
        "totalCardsTracked": total_cards,
        "totalListings": int(total_listings),
        "volume24hUsd": float(volume_24h),
        "avgPriceChange24hPct": avg_price_change_24h,
        "activeFormatsTracked": active_formats_tracked,
    }
    
    # Cache result for 5 minutes
    cache.set(cache_key, result, ttl=300)
    
    return result


@router.get("/index")
async def get_market_index(
    range: str = Query("7d", regex="^(7d|30d|90d|1y)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get market index data for charting using time-bucketed price snapshots.
    
    The market index is a normalized aggregate of card prices over time.
    Uses price snapshots grouped by time intervals (30 minutes for recent data,
    larger buckets for longer ranges to avoid too many data points).
    """
    settings = get_settings()
    scrape_interval_minutes = settings.scrape_interval_minutes
    
    # Determine date range and bucket size
    now = datetime.utcnow()
    if range == "7d":
        start_date = now - timedelta(days=7)
        bucket_minutes = scrape_interval_minutes  # 30 minutes
    elif range == "30d":
        start_date = now - timedelta(days=30)
        bucket_minutes = 60  # 1 hour buckets for 30 days
    elif range == "90d":
        start_date = now - timedelta(days=90)
        bucket_minutes = 240  # 4 hour buckets for 90 days
    else:  # 1y
        start_date = now - timedelta(days=365)
        bucket_minutes = 1440  # Daily buckets for 1 year
    
    # Get time-bucketed average prices from price snapshots
    # Use epoch-based bucketing for flexible intervals
    bucket_seconds = bucket_minutes * 60
    
    # Create bucket expression: floor(epoch / bucket_seconds) * bucket_seconds, then convert back to timestamp
    bucket_expr = func.to_timestamp(
        func.floor(func.extract('epoch', PriceSnapshot.snapshot_time) / bucket_seconds) * bucket_seconds
    )
    
    query = select(
        bucket_expr.label("bucket_time"),
        func.avg(PriceSnapshot.price).label("avg_price"),
        func.count(func.distinct(PriceSnapshot.card_id)).label("card_count"),
    ).where(
        PriceSnapshot.snapshot_time >= start_date,
        PriceSnapshot.price.isnot(None),
        PriceSnapshot.price > 0,
    ).group_by(
        bucket_expr
    ).order_by(
        bucket_expr
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    if not rows:
        # Return mock data if no real data available
        points = []
        base_value = 100.0
        num_points = 7 if range == "7d" else (30 if range == "30d" else (90 if range == "90d" else 365))
        if range == "7d":
            # For 7d, create points every 30 minutes
            num_points = 7 * 24 * 2  # 7 days * 24 hours * 2 (30-min intervals)
        elif range == "30d":
            num_points = 30 * 24  # 30 days * 24 hours
        elif range == "90d":
            num_points = 90 * 6  # 90 days * 6 (4-hour intervals)
        
        for i in range(min(num_points, 1000)):  # Cap at 1000 points
            date = start_date + timedelta(minutes=i * bucket_minutes)
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
            
            # bucket_time is already a datetime from PostgreSQL
            bucket_dt = row.bucket_time
            if isinstance(bucket_dt, datetime):
                timestamp_str = bucket_dt.isoformat()
            else:
                # Fallback if it's a string or other type
                timestamp_str = str(bucket_dt)
            
            points.append({
                "timestamp": timestamp_str,
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
        
        # Get the actual change value from metrics object
        if window == "24h":
            change_value = metrics.price_change_pct_1d
        else:
            change_value = metrics.price_change_pct_7d
        
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
            "changePct": float(change_value) if change_value is not None else 0.0,
            "volume": volume,
        })
    
    # Format losers
    losers = []
    for metrics, card in losers_rows:
        # Get volume
        volume = metrics.total_listings or 0
        
        # Get the actual change value from metrics object
        if window == "24h":
            change_value = metrics.price_change_pct_1d
        else:
            change_value = metrics.price_change_pct_7d
        
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
            "changePct": float(change_value) if change_value is not None else 0.0,
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
    Get trading volume grouped by format over time using time-bucketed price snapshots.
    """
    settings = get_settings()
    scrape_interval_minutes = settings.scrape_interval_minutes
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Determine bucket size based on days
    if days <= 7:
        bucket_minutes = scrape_interval_minutes  # 30 minutes
    elif days <= 30:
        bucket_minutes = 60  # 1 hour
    elif days <= 90:
        bucket_minutes = 240  # 4 hours
    else:
        bucket_minutes = 1440  # Daily
    
    bucket_seconds = bucket_minutes * 60
    
    # Create bucket expression for time bucketing
    bucket_expr = func.to_timestamp(
        func.floor(func.extract('epoch', PriceSnapshot.snapshot_time) / bucket_seconds) * bucket_seconds
    )
    
    # Get cards with legalities and their price snapshots, grouped by time bucket
    query = select(
        Card.legalities,
        bucket_expr.label("bucket_time"),
        func.sum(PriceSnapshot.price * func.coalesce(PriceSnapshot.num_listings, 1)).label("volume"),
    ).join(
        PriceSnapshot, Card.id == PriceSnapshot.card_id
    ).where(
        PriceSnapshot.snapshot_time >= start_date,
        PriceSnapshot.price.isnot(None),
        PriceSnapshot.price > 0,
        Card.legalities.isnot(None),
        Card.legalities != "",
    ).group_by(
        Card.legalities,
        bucket_expr
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
    
    # Group by format and time bucket
    format_data = {}
    
    for row in rows:
        if not row.legalities:
            continue
        
        try:
            legalities = json.loads(row.legalities)
            volume = float(row.volume) if row.volume else 0.0
            
            # Get timestamp string
            bucket_dt = row.bucket_time
            if isinstance(bucket_dt, datetime):
                timestamp_str = bucket_dt.isoformat()
            else:
                timestamp_str = str(bucket_dt)
            
            # Distribute volume across all formats where card is legal
            legal_formats = [fmt for fmt, status in legalities.items() if status == "legal"]
            
            if legal_formats:
                volume_per_format = volume / len(legal_formats)
                for fmt in legal_formats:
                    if fmt not in format_data:
                        format_data[fmt] = {}
                    if timestamp_str not in format_data[fmt]:
                        format_data[fmt][timestamp_str] = 0.0
                    format_data[fmt][timestamp_str] += volume_per_format
        except (json.JSONDecodeError, TypeError):
            continue
    
    # Convert to array format
    formats = []
    for format_name, timestamps in format_data.items():
        points = [
            {"timestamp": ts, "volume": round(vol, 2)}
            for ts, vol in sorted(timestamps.items())
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


@router.get("/color-distribution")
async def get_color_distribution(
    window: str = Query("7d", regex="^(7d|30d)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get color/archetype distribution by format using price snapshots.
    
    Returns a matrix showing the share of volume for each color identity
    within each format, aggregated across the time window.
    """
    # Determine time window
    if window == "7d":
        start_date = datetime.utcnow() - timedelta(days=7)
    else:  # 30d
        start_date = datetime.utcnow() - timedelta(days=30)
    
    # Get cards with color identity and their price snapshots
    # Aggregate volume across all snapshots in the time window
    query = select(
        Card.color_identity,
        Card.legalities,
        func.sum(PriceSnapshot.price * func.coalesce(PriceSnapshot.num_listings, 1)).label("volume"),
    ).join(
        PriceSnapshot, Card.id == PriceSnapshot.card_id
    ).where(
        PriceSnapshot.snapshot_time >= start_date,
        PriceSnapshot.price.isnot(None),
        PriceSnapshot.price > 0,
        Card.color_identity.isnot(None),
        Card.color_identity != "",
        Card.legalities.isnot(None),
        Card.legalities != "",
    ).group_by(
        Card.color_identity,
        Card.legalities
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    if not rows:
        # Return mock data
        return {
            "window": window,
            "formats": ["Commander", "Modern", "Pioneer", "Standard", "Legacy"],
            "colors": ["W", "U", "B", "R", "G", "Multicolor", "Colorless"],
            "matrix": _get_mock_color_distribution(),
            "isMockData": True,
        }
    
    # Define color categories
    COLOR_CATEGORIES = {
        "W": ["W"],
        "U": ["U"],
        "B": ["B"],
        "R": ["R"],
        "G": ["G"],
        "Multicolor": ["WU", "WB", "WR", "WG", "UB", "UR", "UG", "BR", "BG", "RG",
                       "WUB", "WUR", "WUG", "WBR", "WBG", "WRG", "UBR", "UBG", "URG", "BRG",
                       "WUBR", "WUBG", "WURG", "WBRG", "UBRG", "WUBRG"],
        "Colorless": [""],
    }
    
    # Common formats
    FORMATS = ["Commander", "Modern", "Pioneer", "Standard", "Legacy", "Vintage", "Pauper"]
    
    # Aggregate volume by format and color
    format_color_volume: dict[str, dict[str, float]] = {}
    
    for row in rows:
        if not row.color_identity or not row.legalities:
            continue
        
        try:
            color_identity = json.loads(row.color_identity) if isinstance(row.color_identity, str) else row.color_identity
            legalities = json.loads(row.legalities) if isinstance(row.legalities, str) else row.legalities
            volume = float(row.volume) if row.volume else 0.0
            
            # Determine color category
            color_str = "".join(sorted(color_identity)) if isinstance(color_identity, list) else str(color_identity)
            color_category = "Colorless"
            if not color_str or color_str == "[]":
                color_category = "Colorless"
            elif len(color_str) == 1:
                color_category = color_str.upper()
            else:
                color_category = "Multicolor"
            
            # Distribute volume across formats where card is legal
            legal_formats = [fmt for fmt, status in legalities.items() 
                           if status == "legal" and fmt in FORMATS]
            
            if legal_formats:
                volume_per_format = volume / len(legal_formats)
                for fmt in legal_formats:
                    if fmt not in format_color_volume:
                        format_color_volume[fmt] = {}
                    if color_category not in format_color_volume[fmt]:
                        format_color_volume[fmt][color_category] = 0.0
                    format_color_volume[fmt][color_category] += volume_per_format
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
    
    # Build matrix: matrix[i][j] = share of format i's volume for color j
    colors = ["W", "U", "B", "R", "G", "Multicolor", "Colorless"]
    formats = [fmt for fmt in FORMATS if fmt in format_color_volume]
    
    if not formats:
        formats = FORMATS[:5]  # Default formats
    
    matrix = []
    for fmt in formats:
        format_total = sum(format_color_volume.get(fmt, {}).values())
        if format_total == 0:
            # Equal distribution if no data
            row = [1.0 / len(colors)] * len(colors)
        else:
            row = [
                format_color_volume.get(fmt, {}).get(color, 0.0) / format_total
                for color in colors
            ]
        matrix.append(row)
    
    # If no data, return mock
    if not any(any(row) for row in matrix):
        return {
            "window": window,
            "formats": formats,
            "colors": colors,
            "matrix": _get_mock_color_distribution(),
            "isMockData": True,
        }
    
    return {
        "window": window,
        "formats": formats,
        "colors": colors,
        "matrix": matrix,
        "isMockData": False,
    }


def _get_mock_color_distribution():
    """Generate mock color distribution matrix."""
    # 5 formats x 7 colors
    # Simulate realistic distribution
    return [
        [0.15, 0.18, 0.12, 0.20, 0.15, 0.15, 0.05],  # Commander
        [0.12, 0.15, 0.18, 0.20, 0.12, 0.18, 0.05],  # Modern
        [0.18, 0.15, 0.12, 0.18, 0.15, 0.15, 0.07],  # Pioneer
        [0.20, 0.18, 0.15, 0.20, 0.15, 0.10, 0.02],  # Standard
        [0.10, 0.12, 0.15, 0.18, 0.10, 0.30, 0.05],  # Legacy
    ]

