"""
Market API endpoints for market-wide analytics and charts.
"""
import json
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

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


def interpolate_missing_points(
    points: List[Dict[str, Any]], 
    start_date: datetime, 
    end_date: datetime, 
    bucket_minutes: int
) -> List[Dict[str, Any]]:
    """
    Fill gaps in time-series data using forward-fill and linear interpolation.
    
    Args:
        points: List of points with 'timestamp' and 'indexValue' keys
        start_date: Start of the time range
        end_date: End of the time range
        bucket_minutes: Size of each bucket in minutes
    
    Returns:
        List of points with gaps filled
    """
    if not points:
        return []
    
    # Convert timestamps to datetime objects for easier manipulation
    point_dict = {}
    for point in points:
        if isinstance(point['timestamp'], str):
            ts = datetime.fromisoformat(point['timestamp'].replace('Z', '+00:00'))
        else:
            ts = point['timestamp']
        point_dict[ts] = point['indexValue']
    
    # Generate all expected bucket timestamps
    bucket_timedelta = timedelta(minutes=bucket_minutes)
    expected_times = []
    current = start_date
    while current <= end_date:
        expected_times.append(current)
        current += bucket_timedelta
    
    # Fill missing points using forward-fill, then linear interpolation
    filled_points = []
    last_value = None
    
    for i, expected_time in enumerate(expected_times):
        if expected_time in point_dict:
            # We have actual data for this bucket
            last_value = point_dict[expected_time]
            filled_points.append({
                'timestamp': expected_time.isoformat(),
                'indexValue': last_value
            })
        elif last_value is not None:
            # Forward-fill: use last known value
            filled_points.append({
                'timestamp': expected_time.isoformat(),
                'indexValue': last_value
            })
        else:
            # No data yet, find next known value for interpolation
            next_value = None
            next_time = None
            for future_time in expected_times[i+1:]:
                if future_time in point_dict:
                    next_value = point_dict[future_time]
                    next_time = future_time
                    break
            
            if next_value is not None and last_value is not None:
                # Linear interpolation between last and next
                time_diff = (next_time - expected_times[i-1]).total_seconds()
                if time_diff > 0:
                    interp_factor = (expected_time - expected_times[i-1]).total_seconds() / time_diff
                    interp_value = last_value + (next_value - last_value) * interp_factor
                    filled_points.append({
                        'timestamp': expected_time.isoformat(),
                        'indexValue': round(interp_value, 2)
                    })
                    last_value = interp_value
            elif next_value is not None:
                # Use next value if no previous value
                filled_points.append({
                    'timestamp': expected_time.isoformat(),
                    'indexValue': next_value
                })
                last_value = next_value
            else:
                # No data available, skip this bucket
                continue
    
    return filled_points


@router.get("/diagnostics")
async def get_market_diagnostics(
    db: AsyncSession = Depends(get_db),
):
    """
    Diagnostic endpoint to check if price snapshot data exists.
    Useful for debugging why charts show "No data available".
    """
    from datetime import timezone
    
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    
    # Count total snapshots
    total_snapshots = await db.scalar(
        select(func.count(PriceSnapshot.id))
    ) or 0
    
    # Count snapshots in different time ranges
    recent_7d = await db.scalar(
        select(func.count(PriceSnapshot.id)).where(
            PriceSnapshot.snapshot_time >= seven_days_ago
        )
    ) or 0
    
    recent_30d = await db.scalar(
        select(func.count(PriceSnapshot.id)).where(
            PriceSnapshot.snapshot_time >= thirty_days_ago
        )
    ) or 0
    
    # Count by currency
    usd_count = await db.scalar(
        select(func.count(PriceSnapshot.id)).where(
            PriceSnapshot.currency == "USD"
        )
    ) or 0
    
    eur_count = await db.scalar(
        select(func.count(PriceSnapshot.id)).where(
            PriceSnapshot.currency == "EUR"
        )
    ) or 0
    
    # Count cards with snapshots
    cards_with_snapshots = await db.scalar(
        select(func.count(func.distinct(PriceSnapshot.card_id)))
    ) or 0
    
    # Get sample snapshot
    sample_query = select(PriceSnapshot).order_by(PriceSnapshot.snapshot_time.desc()).limit(1)
    sample_result = await db.execute(sample_query)
    sample = sample_result.scalar_one_or_none()
    
    return {
        "total_snapshots": total_snapshots,
        "recent_7d": recent_7d,
        "recent_30d": recent_30d,
        "usd_snapshots": usd_count,
        "eur_snapshots": eur_count,
        "cards_with_snapshots": cards_with_snapshots,
        "sample_snapshot": {
            "card_id": sample.card_id if sample else None,
            "marketplace_id": sample.marketplace_id if sample else None,
            "snapshot_time": sample.snapshot_time.isoformat() if sample else None,
            "price": float(sample.price) if sample else None,
            "currency": sample.currency if sample else None,
        } if sample else None,
        "current_time": now.isoformat(),
    }


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
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
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


async def _get_currency_index(
    currency: str,
    start_date: datetime,
    bucket_expr,
    bucket_minutes: int,
    db: AsyncSession,
    is_foil: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """
    Helper function to get index points for a specific currency.
    
    Returns list of points with 'timestamp' and 'indexValue' keys.
    """
    # Determine which price field to use based on foil filter
    if is_foil is True:
        # Use foil prices only
        price_field = PriceSnapshot.price_foil
        price_condition = PriceSnapshot.price_foil.isnot(None)
    elif is_foil is False:
        # Exclude foil prices (only non-foil)
        price_field = PriceSnapshot.price
        price_condition = PriceSnapshot.price_foil.is_(None)
    else:
        # Default: use regular prices
        price_field = PriceSnapshot.price
        price_condition = PriceSnapshot.price.isnot(None)
    
    query = select(
        bucket_expr.label("bucket_time"),
        func.avg(price_field).label("avg_price"),
        func.count(func.distinct(PriceSnapshot.card_id)).label("card_count"),
    ).where(
        and_(
            PriceSnapshot.snapshot_time >= start_date,
            PriceSnapshot.currency == currency,  # Filter by currency
            price_condition,
            price_field > 0,
        )
    ).group_by(bucket_expr).order_by(bucket_expr)
    
    try:
        result = await asyncio.wait_for(
            db.execute(query),
            timeout=QUERY_TIMEOUT
        )
        rows = result.all()
    except Exception as e:
        logger.error(f"Error fetching {currency} index", error=str(e))
        return []
    
    if not rows:
        return []
    
    # Normalize to base 100 using fixed base point (start of range + 1 day for stability)
    avg_prices = [float(row.avg_price) for row in rows if row.avg_price]
    if not avg_prices:
        return []
    
    # Use fixed base point: average of first day's data (or first point if less than a day)
    base_date = start_date + timedelta(days=1)
    if is_foil is True:
        base_price_field = PriceSnapshot.price_foil
        base_condition = PriceSnapshot.price_foil.isnot(None)
    elif is_foil is False:
        base_price_field = PriceSnapshot.price
        base_condition = PriceSnapshot.price_foil.is_(None)
    else:
        base_price_field = PriceSnapshot.price
        base_condition = PriceSnapshot.price.isnot(None)
    base_query = select(func.avg(base_price_field)).where(
        and_(
            PriceSnapshot.snapshot_time >= start_date,
            PriceSnapshot.snapshot_time < base_date,
            PriceSnapshot.currency == currency,
            base_condition,
            base_price_field > 0,
        )
    )
    base_value = await db.scalar(base_query)
    
    # Fallback to first point if no base value found
    if not base_value or base_value <= 0:
        base_value = avg_prices[0]
    
    # Convert base_value to float to avoid Decimal/float division issues
    base_value_float = float(base_value) if base_value else 100.0
    
    points = []
    for row in rows:
        if row.avg_price:
            # Normalize to base 100
            index_value = (float(row.avg_price) / base_value_float) * 100.0 if base_value_float > 0 else 100.0
            
            bucket_dt = row.bucket_time
            if isinstance(bucket_dt, datetime):
                timestamp_str = bucket_dt.isoformat()
            else:
                timestamp_str = str(bucket_dt)
            
            points.append({
                "timestamp": timestamp_str,
                "indexValue": round(index_value, 2),
            })
    
    return points


@router.get("/index")
async def get_market_index(
    range: str = Query("7d", regex="^(7d|30d|90d|1y)$"),
    currency: Optional[str] = Query(None, regex="^(USD|EUR)$"),
    separate_currencies: bool = Query(False),
    is_foil: Optional[str] = Query(None, description="Filter by foil pricing. 'true' uses price_foil, 'false' excludes foil prices, None uses regular prices."),
    db: AsyncSession = Depends(get_db),
):
    """
    Get market index data for charting using time-bucketed price snapshots.
    
    The market index is a normalized aggregate of card prices over time.
    Uses price snapshots grouped by time intervals (30 minutes for recent data,
    larger buckets for longer ranges to avoid too many data points).
    
    Args:
        range: Time range (7d, 30d, 90d, 1y)
        currency: Filter by currency (USD or EUR). If not specified, aggregates all currencies.
        separate_currencies: If True, returns separate indices for USD and EUR.
        is_foil: Filter by foil pricing ('true', 'false', or None)
    """
    # Convert string query parameter to boolean
    is_foil_bool: Optional[bool] = None
    if is_foil is not None:
        is_foil_bool = is_foil.lower() in ('true', '1', 'yes')
    # Determine date range and bucket size
    now = datetime.now(timezone.utc)
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
    
    end_date = now
    
    # Get time-bucketed average prices from price snapshots
    # Use epoch-based bucketing for flexible intervals
    bucket_seconds = bucket_minutes * 60
    
    # Create bucket expression: floor(epoch / bucket_seconds) * bucket_seconds, then convert back to timestamp
    bucket_expr = func.to_timestamp(
        func.floor(func.extract('epoch', PriceSnapshot.snapshot_time) / bucket_seconds) * bucket_seconds
    )
    
    # Handle separate currencies mode
    if separate_currencies:
        usd_points = await _get_currency_index("USD", start_date, bucket_expr, bucket_minutes, db, is_foil_bool)
        eur_points = await _get_currency_index("EUR", start_date, bucket_expr, bucket_minutes, db, is_foil_bool)
        
        # Apply interpolation to both currency series
        usd_points = interpolate_missing_points(usd_points, start_date, end_date, bucket_minutes)
        eur_points = interpolate_missing_points(eur_points, start_date, end_date, bucket_minutes)
        
        return {
            "range": range,
            "separate_currencies": True,
            "currencies": {
                "USD": {"currency": "USD", "points": usd_points},
                "EUR": {"currency": "EUR", "points": eur_points},
            },
            "isMockData": False,
        }
    
    # Determine which price field to use based on foil filter
    if is_foil_bool is True:
        # Use foil prices only
        price_field = PriceSnapshot.price_foil
        price_condition = PriceSnapshot.price_foil.isnot(None)
    elif is_foil_bool is False:
        # Exclude foil prices (only non-foil)
        price_field = PriceSnapshot.price
        price_condition = PriceSnapshot.price_foil.is_(None)
    else:
        # Default: use regular prices
        price_field = PriceSnapshot.price
        price_condition = PriceSnapshot.price.isnot(None)
    
    # Standard query with optional currency and foil filters
    query_conditions = [
        PriceSnapshot.snapshot_time >= start_date,
        price_condition,
        price_field > 0,
    ]
    
    # Filter by currency if specified
    if currency:
        query_conditions.append(PriceSnapshot.currency == currency)
    
    query = select(
        bucket_expr.label("bucket_time"),
        func.avg(price_field).label("avg_price"),
        func.count(func.distinct(PriceSnapshot.card_id)).label("card_count"),
    ).where(
        and_(*query_conditions)
    ).group_by(bucket_expr).order_by(bucket_expr)
    
    # Log query details for debugging
    logger.debug(
        "Market index query",
        range=range,
        currency=currency or "ALL",
        is_foil=is_foil_bool,
        start_date=start_date.isoformat(),
        bucket_minutes=bucket_minutes,
        price_field=str(price_field),
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
            "currency": currency or "ALL",
            "points": points,
            "isMockData": False,
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
                "currency": currency or "ALL",
                "points": points,
                "isMockData": False,
            }
        raise HTTPException(status_code=500, detail="Failed to fetch market index")
    
    if not rows:
        # Log diagnostic info when no data found
        # Check if there's any price snapshot data at all
        total_snapshots = await db.scalar(
            select(func.count(PriceSnapshot.id))
        ) or 0
        
        recent_snapshots = await db.scalar(
            select(func.count(PriceSnapshot.id)).where(
                PriceSnapshot.snapshot_time >= start_date
            )
        ) or 0
        
        logger.info(
            "No market index data found",
            range=range,
            currency=currency or "ALL",
            is_foil=is_foil_bool,
            total_snapshots_in_db=total_snapshots,
            recent_snapshots_in_range=recent_snapshots,
            start_date=start_date.isoformat(),
        )
        
        # Return empty data if no real data available
        return {
            "range": range,
            "currency": currency or "ALL",
            "points": [],
            "isMockData": False,
        }
    
    # Calculate normalized index using fixed base point (improved normalization)
    points = []
    avg_prices = [float(row.avg_price) for row in rows if row.avg_price]
    
    if not avg_prices:
        # No data available
        return {
            "range": range,
            "currency": currency or "ALL",
            "points": [],
            "isMockData": False,
        }
    
    # Use fixed base point: average of first day's data (or first point if less than a day)
    # This provides consistent normalization across refreshes
    base_date = start_date + timedelta(days=1)
    if is_foil_bool is True:
        base_price_field = PriceSnapshot.price_foil
        base_condition = PriceSnapshot.price_foil.isnot(None)
    elif is_foil_bool is False:
        base_price_field = PriceSnapshot.price
        base_condition = PriceSnapshot.price_foil.is_(None)
    else:
        base_price_field = PriceSnapshot.price
        base_condition = PriceSnapshot.price.isnot(None)
    base_conditions = [
        PriceSnapshot.snapshot_time >= start_date,
        PriceSnapshot.snapshot_time < base_date,
        base_condition,
        base_price_field > 0,
    ]
    if currency:
        base_conditions.append(PriceSnapshot.currency == currency)
    
    base_query = select(func.avg(base_price_field)).where(
        and_(*base_conditions)
    )
    
    base_value = await db.scalar(base_query)
    
    # Fallback to first point if no base value found
    if not base_value or base_value <= 0:
        base_value = avg_prices[0]
    
    # Convert base_value to float to avoid Decimal/float division issues
    base_value_float = float(base_value) if base_value else 100.0
    
    for row in rows:
        if row.avg_price:
            # Normalize to base 100
            index_value = (float(row.avg_price) / base_value_float) * 100.0 if base_value_float > 0 else 100.0
            
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
    
    # Apply interpolation to fill gaps
    points = interpolate_missing_points(points, start_date, end_date, bucket_minutes)
    
    return {
        "range": range,
        "currency": currency or "ALL",
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
                "isMockData": False,
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
        # Return empty data on timeout or pool exhaustion
        return {
            "window": window,
            "gainers": [],
            "losers": [],
            "isMockData": False,
        }
    except Exception as e:
        logger.error("Error fetching top movers", error=str(e), error_type=type(e).__name__, window=window)
        # Check if it's a connection pool error
        if "QueuePool" in str(e) or "connection timed out" in str(e).lower():
            return {
                "window": window,
                "gainers": [],
                "losers": [],
                "isMockData": False,
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
    
    # If no data, return empty lists
    if not gainers and not losers:
        return {
            "window": window,
            "gainers": [],
            "losers": [],
            "isMockData": False,
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
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
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
            "formats": [],
            "isMockData": False,
        }
    except Exception as e:
        logger.error("Error fetching volume by format", error=str(e), error_type=type(e).__name__, days=days)
        if "QueuePool" in str(e) or "connection timed out" in str(e).lower():
            return {
                "days": days,
                "formats": [],
                "isMockData": False,
            }
        raise HTTPException(status_code=500, detail="Failed to fetch volume by format")
    
    if not rows:
        # Return empty data
        return {
            "days": days,
            "formats": [],
            "isMockData": False,
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
    
    # If no data, return empty
    if not formats:
        return {
            "days": days,
            "formats": [],
            "isMockData": False,
        }
    
    return {
        "days": days,
        "formats": formats,
        "isMockData": False,
    }




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
            "distribution": {},
            "isMockData": False,
        }
    except Exception as e:
        logger.error("Error fetching color distribution", error=str(e), error_type=type(e).__name__, window=window)
        return {
            "window": window,
            "colors": ["W", "U", "B", "R", "G", "Multicolor", "Colorless"],
            "distribution": {},
            "isMockData": False,
        }
    
    if not rows:
        return {
            "window": window,
            "colors": ["W", "U", "B", "R", "G", "Multicolor", "Colorless"],
            "distribution": {},
            "isMockData": False,
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
        distribution = {}
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



