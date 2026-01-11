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

from app.api.deps import Cache
from app.core.config import get_settings, settings
from app.db.session import get_db
from app.models import (
    Card,
    MetricsCardsDaily,
    PriceSnapshot,
    Marketplace,
)
from app.schemas.dashboard import TopCard
from app.api.utils import (
    handle_database_query,
    get_empty_market_overview_response,
    get_empty_market_index_response,
    get_empty_top_movers_response,
    get_empty_volume_by_format_response,
    interpolate_missing_points,
)

router = APIRouter()
logger = structlog.get_logger()

# Query timeout in seconds (from centralized config)
QUERY_TIMEOUT = settings.db_query_timeout


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
        select(func.count(PriceSnapshot.time))
    ) or 0
    
    # Count snapshots in different time ranges
    recent_7d = await db.scalar(
        select(func.count(PriceSnapshot.time)).where(
            PriceSnapshot.time >= seven_days_ago
        )
    ) or 0
    
    recent_30d = await db.scalar(
        select(func.count(PriceSnapshot.time)).where(
            PriceSnapshot.time >= thirty_days_ago
        )
    ) or 0
    
    # Count by currency
    usd_count = await db.scalar(
        select(func.count(PriceSnapshot.time)).where(
            PriceSnapshot.currency == "USD"
        )
    ) or 0
    
    eur_count = await db.scalar(
        select(func.count(PriceSnapshot.time)).where(
            PriceSnapshot.currency == "EUR"
        )
    ) or 0
    
    # Count cards with snapshots
    cards_with_snapshots = await db.scalar(
        select(func.count(func.distinct(PriceSnapshot.card_id)))
    ) or 0
    
    # Count total cards
    total_cards = await db.scalar(
        select(func.count(Card.id))
    ) or 0
    
    # Get sample snapshot
    sample_query = select(PriceSnapshot).order_by(PriceSnapshot.time.desc()).limit(1)
    sample_result = await db.execute(sample_query)
    sample = sample_result.scalar_one_or_none()
    
    # Get oldest and newest snapshots
    oldest_query = select(PriceSnapshot).order_by(PriceSnapshot.time.asc()).limit(1)
    oldest_result = await db.execute(oldest_query)
    oldest = oldest_result.scalar_one_or_none()
    
    # Test the actual query that the index uses (7d range, USD currency - what chart defaults to)
    test_start_date = now - timedelta(days=7)
    test_bucket_seconds = 30 * 60  # 30 minutes
    test_bucket_expr = func.to_timestamp(
        func.floor(func.extract('epoch', PriceSnapshot.time) / test_bucket_seconds) * test_bucket_seconds
    )
    test_query = select(
        test_bucket_expr.label("bucket_time"),
        func.avg(PriceSnapshot.price).label("avg_price"),
        func.count(func.distinct(PriceSnapshot.card_id)).label("card_count"),
    ).where(
        and_(
            PriceSnapshot.time >= test_start_date,
            PriceSnapshot.currency == "USD",  # Chart defaults to USD
            PriceSnapshot.price.isnot(None),
            PriceSnapshot.price > 0,
        )
    ).group_by(test_bucket_expr).order_by(test_bucket_expr)
    
    test_result = await db.execute(test_query)
    test_rows = test_result.all()
    
    # Count USD snapshots in last 7 days (what chart needs)
    usd_recent_7d = await db.scalar(
        select(func.count(PriceSnapshot.time)).where(
            and_(
                PriceSnapshot.time >= test_start_date,
                PriceSnapshot.currency == "USD",
                PriceSnapshot.price.isnot(None),
                PriceSnapshot.price > 0,
            )
        )
    ) or 0
    
    # Get marketplace info for sample
    sample_marketplace = None
    if sample:
        marketplace_query = select(Marketplace).where(Marketplace.id == sample.marketplace_id)
        marketplace_result = await db.execute(marketplace_query)
        sample_marketplace = marketplace_result.scalar_one_or_none()
    
    return {
        "total_snapshots": total_snapshots,
        "recent_7d": recent_7d,
        "recent_30d": recent_30d,
        "usd_snapshots": usd_count,
        "eur_snapshots": eur_count,
        "usd_recent_7d": usd_recent_7d,  # What chart actually needs
        "cards_with_snapshots": cards_with_snapshots,
        "total_cards": total_cards,
        "test_query_rows": len(test_rows),
        "sample_snapshot": {
            "card_id": sample.card_id if sample else None,
            "marketplace_id": sample.marketplace_id if sample else None,
            "marketplace_slug": sample_marketplace.slug if sample_marketplace else None,
            "snapshot_time": sample.time.isoformat() if sample else None,
            "price": float(sample.price) if sample else None,
            "currency": sample.currency if sample else None,
        } if sample else None,
        "oldest_snapshot": {
            "snapshot_time": oldest.time.isoformat() if oldest else None,
            "price": float(oldest.price) if oldest else None,
            "currency": oldest.currency if oldest else None,
        } if oldest else None,
        "current_time": now.isoformat(),
        "seed_status": "No data - seed process may not have run yet" if total_snapshots == 0 else "Data exists",
        "chart_issue": (
            "No USD snapshots in last 7 days - chart will show 'No data available'" 
            if usd_recent_7d == 0 and total_snapshots > 0 
            else "No snapshots at all - run seed_comprehensive_price_data task" 
            if total_snapshots == 0 
            else "Data exists and should work"
        ),
    }


@router.get("/overview")
async def get_market_overview(
    db: AsyncSession = Depends(get_db),
    cache: Cache = None,
):
    """
    Get market overview statistics.

    Returns key market metrics for the dashboard stats strip.
    """
    # Check cache first
    cached = await cache.get("market", "overview")
    if cached is not None:
        return cached
    
    # Total cards tracked
    total_cards = await handle_database_query(
        lambda: db.scalar(select(func.count(Card.id))),
        default_value=0,
        error_context={"endpoint": "market_overview", "operation": "count_cards"},
        timeout=QUERY_TIMEOUT,
    ) or 0
    
    if total_cards == 0:
        # If we got 0 due to error, return empty response
        return get_empty_market_overview_response()
    
    # Total price snapshots (active price data from last 24h)
    # Note: We no longer collect individual listings - using price snapshots from Scryfall/MTGJSON
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    
    total_snapshots = await handle_database_query(
        lambda: db.scalar(
            select(func.count(PriceSnapshot.time)).where(
                PriceSnapshot.time >= day_ago
            )
        ),
        default_value=0,
        error_context={"endpoint": "market_overview", "operation": "count_snapshots"},
        timeout=QUERY_TIMEOUT,
    ) or 0
    
    # 24h trade volume (USD) - estimate from price snapshots
    # Estimate: sum of prices * estimated quantity (using num_listings if available, else 1)
    # This is a rough approximation since we don't have exact listing quantities
    volume_24h = await handle_database_query(
        lambda: db.scalar(
            select(
                func.sum(
                    PriceSnapshot.price * func.coalesce(PriceSnapshot.num_listings, 1)
                )
            ).where(
                PriceSnapshot.time >= day_ago,
                PriceSnapshot.currency == "USD",
                PriceSnapshot.price > 0
            )
        ),
        default_value=0,
        error_context={"endpoint": "market_overview", "operation": "volume_24h_usd"},
        timeout=QUERY_TIMEOUT,
    ) or 0
    
    # If no USD snapshots, try to estimate from other currencies
    if volume_24h == 0:
        volume_24h = await handle_database_query(
            lambda: db.scalar(
                select(
                    func.sum(
                        PriceSnapshot.price * func.coalesce(PriceSnapshot.num_listings, 1)
                    )
                ).where(
                    PriceSnapshot.time >= day_ago,
                    PriceSnapshot.price > 0
                )
            ),
            default_value=0,
            error_context={"endpoint": "market_overview", "operation": "volume_24h_all"},
            timeout=QUERY_TIMEOUT,
        ) or 0
    
    # 24h average price change
    latest_date = await handle_database_query(
        lambda: db.scalar(select(func.max(MetricsCardsDaily.date))),
        default_value=None,
        error_context={"endpoint": "market_overview", "operation": "latest_date"},
        timeout=QUERY_TIMEOUT,
    )
    
    avg_price_change_24h = None
    if latest_date:
        result = await handle_database_query(
            lambda: db.execute(
                select(
                    func.avg(MetricsCardsDaily.price_change_pct_1d).label("avg_change")
                ).where(
                    MetricsCardsDaily.date == latest_date,
                    MetricsCardsDaily.price_change_pct_1d.isnot(None),
                )
            ),
            default_value=None,
            error_context={"endpoint": "market_overview", "operation": "avg_price_change"},
            timeout=QUERY_TIMEOUT,
        )
        if result:
            row = result.first()
            if row and row.avg_change:
                avg_price_change_24h = float(row.avg_change)
    
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
    
    # Cache result for 5 minutes (uses default TTL from CacheRepository)
    try:
        await cache.set("market", "overview", value=result)
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
        price_field = PriceSnapshot.price_market
        price_condition = PriceSnapshot.price_market.isnot(None)
    elif is_foil is False:
        # Exclude foil prices (only non-foil)
        price_field = PriceSnapshot.price
        price_condition = PriceSnapshot.price_market.is_(None)
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
            PriceSnapshot.time >= start_date,
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
    except (asyncio.TimeoutError, OperationalError, SQLTimeoutError) as e:
        logger.error(f"Error fetching {currency} index: database timeout", error=str(e))
        return []
    except Exception as e:
        logger.error(f"Error fetching {currency} index", error=str(e), error_type=type(e).__name__)
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
        base_price_field = PriceSnapshot.price_market
        base_condition = PriceSnapshot.price_market.isnot(None)
    elif is_foil is False:
        base_price_field = PriceSnapshot.price
        base_condition = PriceSnapshot.price_market.is_(None)
    else:
        base_price_field = PriceSnapshot.price
        base_condition = PriceSnapshot.price.isnot(None)
    base_query = select(func.avg(base_price_field)).where(
        and_(
            PriceSnapshot.time >= start_date,
            PriceSnapshot.time < base_date,
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
    currency: str = Query("USD", regex="^USD$", description="Only USD is supported"),
    separate_currencies: bool = Query(
        False,
        description="USD-only mode; EUR charts are no longer supported",
    ),
    is_foil: Optional[str] = Query(None, description="Filter by foil pricing. 'true' uses price_foil, 'false' excludes foil prices, None uses regular prices."),
    db: AsyncSession = Depends(get_db),
):
    """
    Get market index data for charting using time-bucketed price snapshots.
    
    The market index is a normalized aggregate of USD card prices over time.
    Uses price snapshots grouped by time intervals (30 minutes for recent data,
    larger buckets for longer ranges to avoid too many data points). Only USD
    pricing is returned to avoid multi-currency mixing.
    
    Args:
        range: Time range (7d, 30d, 90d, 1y)
        currency: USD only
        separate_currencies: Disabled; present for backward compatibility only
        is_foil: Filter by foil pricing ('true', 'false', or None)
    """
    # Hard-enforce USD-only responses
    if separate_currencies:
        raise HTTPException(
            status_code=400,
            detail="Only USD currency is supported; separate currency charts are disabled.",
        )
    currency = "USD"
    
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
        func.floor(func.extract('epoch', PriceSnapshot.time) / bucket_seconds) * bucket_seconds
    )
    
    # Determine which price field to use based on foil filter
    if is_foil_bool is True:
        # Use foil prices only
        price_field = PriceSnapshot.price_market
        price_condition = PriceSnapshot.price_market.isnot(None)
    elif is_foil_bool is False:
        # Exclude foil prices (only non-foil)
        price_field = PriceSnapshot.price
        price_condition = PriceSnapshot.price_market.is_(None)
    else:
        # Default: use regular prices
        price_field = PriceSnapshot.price
        price_condition = PriceSnapshot.price.isnot(None)
    
    # Standard query with optional currency and foil filters
    query_conditions = [
        PriceSnapshot.time >= start_date,
        price_condition,
        price_field > 0,
        PriceSnapshot.currency == "USD",
    ]
    
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
        # Return empty data with error message on timeout (never mock data)
        return {
            "range": range,
            "currency": currency or "ALL",
            "points": [],
            "isMockData": False,
            "error": "Database timeout - please retry",
        }
    except Exception as e:
        from app.api.utils.error_handling import is_database_connection_error
        
        logger.error("Error fetching market index", error=str(e), error_type=type(e).__name__, range=range)
        
        # Check if it's a connection pool error
        if is_database_connection_error(e):
            # Return empty data on pool exhaustion
            return get_empty_market_index_response(range, currency)
        
        raise HTTPException(status_code=500, detail="Failed to fetch market index")
    
    if not rows:
        # Log diagnostic info when no data found
        # Check if there's any price snapshot data at all
        total_snapshots = await db.scalar(
            select(func.count(PriceSnapshot.time))
        ) or 0
        
        recent_snapshots = await db.scalar(
            select(func.count(PriceSnapshot.time)).where(
                PriceSnapshot.time >= start_date
            )
        ) or 0
        
        # Check snapshots with price conditions
        price_field_name = "price_foil" if is_foil_bool is True else "price"
        if is_foil_bool is True:
            price_condition_check = PriceSnapshot.price_market.isnot(None)
        elif is_foil_bool is False:
            price_condition_check = PriceSnapshot.price_market.is_(None)
        else:
            price_condition_check = PriceSnapshot.price.isnot(None)
        
        snapshots_with_price = await db.scalar(
            select(func.count(PriceSnapshot.time)).where(
                and_(
                    PriceSnapshot.time >= start_date,
                    price_condition_check,
                )
            )
        ) or 0
        
        # Check by currency if specified
        currency_snapshots = recent_snapshots
        if currency:
            currency_snapshots = await db.scalar(
                select(func.count(PriceSnapshot.time)).where(
                    and_(
                        PriceSnapshot.time >= start_date,
                        PriceSnapshot.currency == currency,
                    )
                )
            ) or 0
        
        # Check what currencies actually exist in the database
        currency_distribution = await db.execute(
            select(
                PriceSnapshot.currency,
                func.count(PriceSnapshot.time).label("count")
            ).where(
                PriceSnapshot.time >= start_date
            ).group_by(PriceSnapshot.currency)
        )
        available_currencies = {row.currency: row.count for row in currency_distribution.all()}
        
        # Additional diagnostic: check if there are ANY snapshots with this currency
        any_currency_snapshots = await db.scalar(
            select(func.count(PriceSnapshot.time)).where(
                PriceSnapshot.currency == currency
            )
        ) or 0
        
        logger.warning(
            "No market index data found",
            range=range,
            currency=currency or "ALL",
            is_foil=is_foil_bool,
            total_snapshots_in_db=total_snapshots,
            recent_snapshots_in_range=recent_snapshots,
            snapshots_with_price_condition=snapshots_with_price,
            currency_snapshots=currency_snapshots if currency else recent_snapshots,
            any_currency_snapshots=any_currency_snapshots,
            available_currencies=available_currencies,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            price_field=price_field_name,
            diagnostic_message=(
                f"No {currency} snapshots in last {range}. "
                f"Total {currency} snapshots: {any_currency_snapshots}. "
                f"Available currencies in range: {available_currencies}. "
                f"Run seed_comprehensive_price_data or collect_price_data tasks."
            ) if any_currency_snapshots == 0 else (
                f"No {currency} snapshots in date range {range}, but {any_currency_snapshots} exist outside range. "
                f"Available currencies in range: {available_currencies}. "
                f"Data may be too old or tasks not running frequently enough."
            ),
        )
        
        # Return empty data if no real data available
        return {
            "range": range,
            "currency": currency or "ALL",
            "points": [],
            "isMockData": False,
            "data_freshness_minutes": None,
            "latest_snapshot_time": None,
            "diagnostic": {
                "total_snapshots": total_snapshots,
                "currency_snapshots": any_currency_snapshots,
                "recent_snapshots_in_range": recent_snapshots,
                "available_currencies": available_currencies,
                "message": (
                    f"No {currency} snapshots found. "
                    f"Total snapshots: {total_snapshots}, {currency} snapshots: {any_currency_snapshots}. "
                    f"Available currencies in range: {list(available_currencies.keys())}. "
                    f"Please run price collection tasks or try a different currency."
                ) if any_currency_snapshots == 0 else (
                    f"No {currency} snapshots in {range} range. "
                    f"Data exists but is outside the requested time range. "
                    f"Available currencies in range: {list(available_currencies.keys())}."
                ),
            },
        }
    
    # Calculate normalized index using fixed base point (improved normalization)
    points = []
    avg_prices = [float(row.avg_price) for row in rows if row.avg_price and row.avg_price > 0]
    
    logger.info(
        "Market index query results",
        range=range,
        currency=currency,
        total_rows=len(rows),
        valid_avg_prices=len(avg_prices),
        first_few_prices=avg_prices[:5] if len(avg_prices) > 0 else [],
    )
    
    if not avg_prices:
        # Log why we have no valid prices
        rows_with_none = sum(1 for row in rows if row.avg_price is None)
        rows_with_zero = sum(1 for row in rows if row.avg_price == 0)
        logger.warning(
            "No valid average prices in query results",
            range=range,
            total_rows=len(rows),
            rows_with_none_price=rows_with_none,
            rows_with_zero_price=rows_with_zero,
            valid_avg_prices=len(avg_prices),
        )
        # No data available
        return {
            "range": range,
            "currency": currency or "ALL",
            "points": [],
            "isMockData": False,
        }
    
    # Use improved base point calculation: median of first 25% of points
    # This is more robust than average and less affected by outliers
    # If we have fewer than 4 points, use median of all points
    num_points_for_base = max(4, len(avg_prices) // 4)
    base_price_values = sorted(avg_prices[:num_points_for_base])
    
    # Calculate median
    if len(base_price_values) % 2 == 0:
        # Even number of points: average of two middle values
        mid = len(base_price_values) // 2
        base_value = (base_price_values[mid - 1] + base_price_values[mid]) / 2.0
    else:
        # Odd number of points: middle value
        mid = len(base_price_values) // 2
        base_value = base_price_values[mid]
    
    # Validate base value is reasonable (should be positive and not an extreme outlier)
    if not base_value or base_value <= 0:
        # Fallback to first point if median calculation failed
        base_value = avg_prices[0] if avg_prices else 100.0
        logger.warning(
            "Base value calculation failed, using first point as fallback",
            range=range,
            currency=currency,
            first_point_value=base_value
        )
    
    # Additional validation: ensure base value is within reasonable range
    # If base value is more than 10x different from first point, something is wrong
    if avg_prices and abs(base_value - avg_prices[0]) / avg_prices[0] > 10.0:
        logger.warning(
            "Base value seems like an outlier, using first point instead",
            range=range,
            currency=currency,
            base_value=base_value,
            first_point=avg_prices[0]
        )
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
    
    logger.info(
        "Points created before interpolation",
        range=range,
        currency=currency,
        points_count=len(points),
        sample_points=points[:3] if len(points) > 0 else [],
    )
    
    # Apply interpolation to fill gaps
    points_before_interp = len(points)
    points = interpolate_missing_points(points, start_date, end_date, bucket_minutes)
    
    logger.info(
        "Points after interpolation",
        range=range,
        currency=currency,
        points_before=points_before_interp,
        points_after=len(points),
    )
    
    # Calculate data freshness - find the most recent snapshot timestamp
    latest_snapshot_query = select(
        func.max(PriceSnapshot.time)
    ).where(
        and_(
            PriceSnapshot.time >= start_date,
            price_condition,
            price_field > 0,
            PriceSnapshot.currency == currency,
        )
    )
    latest_snapshot_time = await db.scalar(latest_snapshot_query)
    
    # Calculate freshness in minutes
    data_freshness_minutes = None
    if latest_snapshot_time:
        age_delta = now - latest_snapshot_time
        data_freshness_minutes = int(age_delta.total_seconds() / 60)
    
    return {
        "range": range,
        "currency": currency or "ALL",
        "points": points,
        "isMockData": False,
        "data_freshness_minutes": data_freshness_minutes,
        "latest_snapshot_time": latest_snapshot_time.isoformat() if latest_snapshot_time else None,
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
        # Get the latest date that actually has price change data
        # This handles cases where the most recent date exists but hasn't had
        # price change calculations run yet (e.g., today's date with no data)
        latest_date_with_data = await asyncio.wait_for(
            db.scalar(
                select(func.max(MetricsCardsDaily.date)).where(
                    change_field.isnot(None)
                )
            ),
            timeout=QUERY_TIMEOUT
        )

        if not latest_date_with_data:
            logger.warning(
                "No metrics data with price change found for top movers",
                window=window,
                change_field=str(change_field)
            )
            return {
                "window": window,
                "gainers": [],
                "losers": [],
                "isMockData": False,
            }

        query_date = latest_date_with_data
        logger.debug(
            "Using date with price change data for top movers",
            query_date=query_date.isoformat(),
            window=window
        )
        
        # Minimum thresholds to filter out noise
        # Require at least 1% change and minimum volume of 1 listing
        # Note: total_listings reflects marketplace sources, not individual listings
        min_change_pct = 1.0  # At least 1% change
        min_volume = 1  # At least 1 marketplace source
        
        # Get top gainers
        gainers_query = select(MetricsCardsDaily, Card).join(
            Card, MetricsCardsDaily.card_id == Card.id
        ).where(
            MetricsCardsDaily.date == query_date,
            change_field.isnot(None),
            change_field >= min_change_pct,  # At least 1% gain
            MetricsCardsDaily.total_listings >= min_volume,  # Minimum volume
            MetricsCardsDaily.avg_price.isnot(None),
            MetricsCardsDaily.avg_price > 0,  # Valid price
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
            MetricsCardsDaily.date == query_date,
            change_field.isnot(None),
            change_field <= -min_change_pct,  # At least 1% loss
            MetricsCardsDaily.total_listings >= min_volume,  # Minimum volume
            MetricsCardsDaily.avg_price.isnot(None),
            MetricsCardsDaily.avg_price > 0,  # Valid price
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
        return get_empty_top_movers_response(window)
    except Exception as e:
        from app.api.utils.error_handling import is_database_connection_error
        
        logger.error("Error fetching top movers", error=str(e), error_type=type(e).__name__, window=window)
        # Check if it's a connection pool error
        if is_database_connection_error(e):
            return get_empty_top_movers_response(window)
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
        func.floor(func.extract('epoch', PriceSnapshot.time) / bucket_seconds) * bucket_seconds
    )
    
    # Get cards with legalities and their price snapshots, grouped by time bucket
    query = select(
        Card.legalities,
        bucket_expr.label("bucket_time"),
        func.sum(PriceSnapshot.price * func.coalesce(PriceSnapshot.num_listings, 1)).label("volume"),
    ).join(
        PriceSnapshot, Card.id == PriceSnapshot.card_id
    ).where(
        PriceSnapshot.time >= start_date,
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
        return get_empty_volume_by_format_response(days)
    except Exception as e:
        from app.api.utils.error_handling import is_database_connection_error
        
        logger.error("Error fetching volume by format", error=str(e), error_type=type(e).__name__, days=days)
        if is_database_connection_error(e):
            return get_empty_volume_by_format_response(days)
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



