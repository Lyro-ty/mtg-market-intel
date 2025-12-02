"""
Market API endpoints for market-wide analytics and charts.
"""
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, desc, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError, TimeoutError as SQLTimeoutError

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
logger = structlog.get_logger()

# Query timeout in seconds
QUERY_TIMEOUT = 25  # Slightly less than DB timeout to provide better error messages


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
    
    try:
        # Total cards tracked
        total_cards = await asyncio.wait_for(
            db.scalar(select(func.count(Card.id))),
            timeout=QUERY_TIMEOUT
        ) or 0
    except (asyncio.TimeoutError, OperationalError, SQLTimeoutError) as e:
        logger.error(
            "Database query timeout or pool exhaustion in market overview",
            error=str(e),
            error_type=type(e).__name__
        )
        # Return cached or default values instead of failing
        return {
            "totalCardsTracked": 0,
            "totalListings": 0,
            "volume24hUsd": 0.0,
            "avgPriceChange24hPct": None,
            "activeFormatsTracked": 10,
        }
    except Exception as e:
        logger.error("Error fetching total cards", error=str(e), error_type=type(e).__name__)
        if "QueuePool" in str(e) or "connection timed out" in str(e).lower():
            return {
                "totalCardsTracked": 0,
                "totalListings": 0,
                "volume24hUsd": 0.0,
                "avgPriceChange24hPct": None,
                "activeFormatsTracked": 10,
            }
        raise HTTPException(status_code=500, detail="Failed to fetch market overview")
    
    # Total price snapshots (active price data from last 24h)
    # Note: We no longer collect individual listings - using price snapshots from Scryfall/MTGJSON
    day_ago = datetime.utcnow() - timedelta(days=1)
    try:
        total_snapshots = await asyncio.wait_for(
            db.scalar(
                select(func.count(PriceSnapshot.id)).where(
                    PriceSnapshot.snapshot_time >= day_ago
                )
            ),
            timeout=QUERY_TIMEOUT
        ) or 0
        
        # 24h trade volume (USD) - estimate from price snapshots
        # Estimate: sum of prices * estimated quantity (using num_listings if available, else 1)
        # This is a rough approximation since we don't have exact listing quantities
        volume_24h = await asyncio.wait_for(
            db.scalar(
                select(
                    func.sum(
                        PriceSnapshot.price * func.coalesce(PriceSnapshot.num_listings, 1)
                    )
                ).where(
                    PriceSnapshot.snapshot_time >= day_ago,
                    PriceSnapshot.currency == "USD",
                    PriceSnapshot.price > 0
                )
            ),
            timeout=QUERY_TIMEOUT
        ) or 0
        
        # If no USD snapshots, try to estimate from other currencies
        if volume_24h == 0:
            volume_24h = await asyncio.wait_for(
                db.scalar(
                    select(
                        func.sum(
                            PriceSnapshot.price * func.coalesce(PriceSnapshot.num_listings, 1)
                        )
                    ).where(
                        PriceSnapshot.snapshot_time >= day_ago,
                        PriceSnapshot.price > 0
                    )
                ),
                timeout=QUERY_TIMEOUT
            ) or 0
        
        # 24h average price change
        latest_date = await asyncio.wait_for(
            db.scalar(select(func.max(MetricsCardsDaily.date))),
            timeout=QUERY_TIMEOUT
        )
        avg_price_change_24h = None
        if latest_date:
            result = await asyncio.wait_for(
                db.execute(
                    select(
                        func.avg(MetricsCardsDaily.price_change_pct_1d).label("avg_change")
                    ).where(
                        MetricsCardsDaily.date == latest_date,
                        MetricsCardsDaily.price_change_pct_1d.isnot(None),
                    )
                ),
                timeout=QUERY_TIMEOUT
            )
            row = result.first()
            if row and row.avg_change:
                avg_price_change_24h = float(row.avg_change)
    except (asyncio.TimeoutError, OperationalError, SQLTimeoutError) as e:
        logger.error(
            "Database query timeout or pool exhaustion in market overview",
            error=str(e),
            error_type=type(e).__name__
        )
        # Return default values instead of failing
        return {
            "totalCardsTracked": 0,
            "totalListings": 0,
            "volume24hUsd": 0.0,
            "avgPriceChange24hPct": None,
            "activeFormatsTracked": 10,
        }
    except Exception as e:
        logger.error("Error fetching market overview data", error=str(e), error_type=type(e).__name__)
        if "QueuePool" in str(e) or "connection timed out" in str(e).lower():
            return {
                "totalCardsTracked": 0,
                "totalListings": 0,
                "volume24hUsd": 0.0,
                "avgPriceChange24hPct": None,
                "activeFormatsTracked": 10,
            }
        raise HTTPException(status_code=500, detail="Failed to fetch market overview")
    
    # Active formats tracked - use a more efficient approach
    # Instead of parsing 1000 cards, use a smaller sample and cache the result
    # Common formats we track
    COMMON_FORMATS = ["Standard", "Modern", "Legacy", "Vintage", "Commander", "Pioneer", "Pauper", "Historic", "Brawl", "Alchemy"]
    
    try:
        # Count formats by checking if any card is legal in each format
        # Use a more efficient query that checks for format existence
        sample_cards = await asyncio.wait_for(
            db.execute(
                select(Card.legalities).where(
                    Card.legalities.isnot(None),
                    Card.legalities != ""
                ).limit(100)  # Reduced from 1000 to 100 for faster parsing
            ),
            timeout=QUERY_TIMEOUT
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
    except (asyncio.TimeoutError, OperationalError, SQLTimeoutError) as e:
        logger.error("Database query timeout in formats tracking", error=str(e))
        # Use default value if query fails
        active_formats_tracked = len(COMMON_FORMATS)
    except Exception as e:
        logger.error("Error fetching formats", error=str(e))
        active_formats_tracked = len(COMMON_FORMATS)
    
    result = {
        "totalCardsTracked": total_cards,
        "totalSnapshots": int(total_snapshots),  # Price snapshots (replaces listings)
        "volume24hUsd": float(volume_24h),
        "avgPriceChange24hPct": avg_price_change_24h,
        "activeFormatsTracked": active_formats_tracked,
    }
    
    # Cache result for 5 minutes
    try:
        cache.set(cache_key, result, ttl=300)
    except Exception as e:
        logger.warning("Failed to cache market overview", error=str(e))
    
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
    # Determine date range and bucket size
    now = datetime.utcnow()
    if range == "7d":
        start_date = now - timedelta(days=7)
        bucket_minutes = 30  # 30 minutes for 7 days
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
    
    try:
        result = await asyncio.wait_for(
            db.execute(query),
            timeout=QUERY_TIMEOUT
        )
        rows = result.all()
    except (asyncio.TimeoutError, OperationalError, SQLTimeoutError) as e:
        logger.error(
            "Database query timeout or pool exhaustion in market index",
            error=str(e),
            error_type=type(e).__name__,
            range=range
        )
        # Return mock data on timeout
        points = []
        base_value = 100.0
        num_points = 7 if range == "7d" else (30 if range == "30d" else (90 if range == "90d" else 365))
        if range == "7d":
            num_points = 7 * 24 * 2
        elif range == "30d":
            num_points = 30 * 24
        elif range == "90d":
            num_points = 90 * 6
        
        for i in range(min(num_points, 1000)):
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
    except Exception as e:
        logger.error("Error fetching market index", error=str(e), error_type=type(e).__name__, range=range)
        # Check if it's a connection pool error
        if "QueuePool" in str(e) or "connection timed out" in str(e).lower():
            # Return mock data on pool exhaustion
            points = []
            base_value = 100.0
            num_points = 7 if range == "7d" else (30 if range == "30d" else (90 if range == "90d" else 365))
            if range == "7d":
                num_points = 7 * 24 * 2
            elif range == "30d":
                num_points = 30 * 24
            elif range == "90d":
                num_points = 90 * 6
            
            for i in range(min(num_points, 1000)):
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
        raise HTTPException(status_code=500, detail="Failed to fetch market index")
    
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
    
    try:
        latest_date = await asyncio.wait_for(
            db.scalar(select(func.max(MetricsCardsDaily.date))),
            timeout=QUERY_TIMEOUT
        )
        
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
        
        gainers_result = await asyncio.wait_for(
            db.execute(gainers_query),
            timeout=QUERY_TIMEOUT
        )
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
        
        losers_result = await asyncio.wait_for(
            db.execute(losers_query),
            timeout=QUERY_TIMEOUT
        )
        losers_rows = losers_result.all()
    except (asyncio.TimeoutError, OperationalError, SQLTimeoutError) as e:
        logger.error(
            "Database query timeout or pool exhaustion in top movers",
            error=str(e),
            error_type=type(e).__name__,
            window=window
        )
        # Return mock data on timeout or pool exhaustion
        return {
            "window": window,
            "gainers": _get_mock_gainers(),
            "losers": _get_mock_losers(),
            "isMockData": True,
        }
    except Exception as e:
        logger.error("Error fetching top movers", error=str(e), error_type=type(e).__name__, window=window)
        # Check if it's a connection pool error
        if "QueuePool" in str(e) or "connection timed out" in str(e).lower():
            return {
                "window": window,
                "gainers": _get_mock_gainers(),
                "losers": _get_mock_losers(),
                "isMockData": True,
            }
        raise HTTPException(status_code=500, detail="Failed to fetch top movers")
    
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
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Determine bucket size based on days
    if days <= 7:
        bucket_minutes = 30  # 30 minutes
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
    
    try:
        result = await asyncio.wait_for(
            db.execute(query),
            timeout=QUERY_TIMEOUT
        )
        rows = result.all()
    except (asyncio.TimeoutError, OperationalError, SQLTimeoutError) as e:
        logger.error(
            "Database query timeout or pool exhaustion in volume by format",
            error=str(e),
            error_type=type(e).__name__,
            days=days
        )
        return {
            "days": days,
            "formats": _get_mock_volume_by_format(days),
            "isMockData": True,
        }
    except Exception as e:
        logger.error("Error fetching volume by format", error=str(e), error_type=type(e).__name__, days=days)
        if "QueuePool" in str(e) or "connection timed out" in str(e).lower():
            return {
                "days": days,
                "formats": _get_mock_volume_by_format(days),
                "isMockData": True,
            }
        raise HTTPException(status_code=500, detail="Failed to fetch volume by format")
    
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
    Get color distribution based on cards in our database.
    
    Analyzes color distribution from all cards tracked, providing overall meta insights.
    """
    # Get cards with color identity
    query = select(
        Card.color_identity,
        func.count(Card.id).label("count"),
    ).where(
        Card.color_identity.isnot(None),
        Card.color_identity != "",
    ).group_by(
        Card.color_identity
    )
    
    try:
        result = await asyncio.wait_for(
            db.execute(query),
            timeout=QUERY_TIMEOUT
        )
        rows = result.all()
    except (asyncio.TimeoutError, OperationalError, SQLTimeoutError) as e:
        logger.error(
            "Database query timeout in color distribution",
            error=str(e),
            error_type=type(e).__name__,
            window=window
        )
        return {
            "window": window,
            "colors": ["W", "U", "B", "R", "G", "Multicolor", "Colorless"],
            "distribution": _get_mock_color_distribution_simple(),
            "isMockData": True,
        }
    except Exception as e:
        logger.error("Error fetching color distribution", error=str(e), error_type=type(e).__name__, window=window)
        return {
            "window": window,
            "colors": ["W", "U", "B", "R", "G", "Multicolor", "Colorless"],
            "distribution": _get_mock_color_distribution_simple(),
            "isMockData": True,
        }
    
    if not rows:
        return {
            "window": window,
            "colors": ["W", "U", "B", "R", "G", "Multicolor", "Colorless"],
            "distribution": _get_mock_color_distribution_simple(),
            "isMockData": True,
        }
    
    # Aggregate by color category
    color_counts: dict[str, int] = {
        "W": 0,
        "U": 0,
        "B": 0,
        "R": 0,
        "G": 0,
        "Multicolor": 0,
        "Colorless": 0,
    }
    
    for row in rows:
        if not row.color_identity:
            continue
        
        try:
            color_identity = json.loads(row.color_identity) if isinstance(row.color_identity, str) else row.color_identity
            count = int(row.count) if row.count else 0
            
            # Determine color category
            if isinstance(color_identity, list):
                color_str = "".join(sorted(color_identity))
            else:
                color_str = str(color_identity)
            
            if not color_str or color_str == "[]" or color_str == "":
                color_category = "Colorless"
            elif len(color_str) == 1:
                color_category = color_str.upper()
            else:
                color_category = "Multicolor"
            
            color_counts[color_category] += count
        except (json.JSONDecodeError, TypeError, AttributeError, KeyError):
            continue
    
    # Convert to percentages
    total = sum(color_counts.values())
    if total == 0:
        distribution = _get_mock_color_distribution_simple()
    else:
        distribution = {
            color: round((count / total) * 100, 2)
            for color, count in color_counts.items()
        }
    
    return {
        "window": window,
        "colors": list(color_counts.keys()),
        "distribution": distribution,
        "isMockData": False,
    }


def _get_mock_color_distribution_simple():
    """Generate mock color distribution percentages."""
    return {
        "W": 18.5,
        "U": 16.2,
        "B": 14.8,
        "R": 19.3,
        "G": 17.1,
        "Multicolor": 13.2,
        "Colorless": 0.9,
    }

