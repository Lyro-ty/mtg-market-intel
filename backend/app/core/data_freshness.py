"""
Data freshness checking utilities.

Used to determine if data needs to be refreshed on startup,
avoiding unnecessary task execution when recent data exists.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PriceSnapshot, MetricsCardsDaily, Recommendation
from app.models.card import Card
from app.models.mtg_set import MTGSet
from app.models.tournament import Tournament
from app.models.feature_vector import CardFeatureVector

logger = structlog.get_logger()


# Freshness thresholds (in hours)
PRICE_SNAPSHOT_FRESHNESS_HOURS = 1  # Price data considered fresh if < 1 hour old
ANALYTICS_FRESHNESS_HOURS = 2  # Analytics considered fresh if < 2 hours old
RECOMMENDATIONS_FRESHNESS_HOURS = 6  # Recommendations considered fresh if < 6 hours old


async def get_latest_price_snapshot_time(db: AsyncSession) -> Optional[datetime]:
    """Get the timestamp of the most recent price snapshot."""
    result = await db.scalar(
        select(func.max(PriceSnapshot.time))
    )
    return result


async def get_latest_metrics_date(db: AsyncSession) -> Optional[datetime]:
    """Get the date of the most recent metrics entry."""
    result = await db.scalar(
        select(func.max(MetricsCardsDaily.date))
    )
    if result:
        # Convert date to datetime for comparison
        return datetime.combine(result, datetime.min.time(), tzinfo=timezone.utc)
    return None


async def get_latest_recommendation_time(db: AsyncSession) -> Optional[datetime]:
    """Get the created_at timestamp of the most recent active recommendation."""
    result = await db.scalar(
        select(func.max(Recommendation.created_at)).where(
            Recommendation.is_active == True
        )
    )
    return result


async def get_price_snapshot_count(db: AsyncSession) -> int:
    """Get total count of price snapshots."""
    result = await db.scalar(
        select(func.count(PriceSnapshot.time))
    )
    return result or 0


async def get_metrics_count(db: AsyncSession) -> int:
    """Get total count of metrics entries."""
    result = await db.scalar(
        select(func.count(MetricsCardsDaily.id))
    )
    return result or 0


async def get_recommendations_count(db: AsyncSession) -> int:
    """Get total count of active recommendations."""
    result = await db.scalar(
        select(func.count(Recommendation.id)).where(
            Recommendation.is_active == True
        )
    )
    return result or 0


def is_data_fresh(
    latest_time: Optional[datetime],
    freshness_hours: float
) -> bool:
    """
    Check if data is considered fresh based on the latest timestamp.

    Args:
        latest_time: The timestamp of the most recent data
        freshness_hours: Maximum age in hours for data to be considered fresh

    Returns:
        True if data is fresh, False if stale or missing
    """
    if latest_time is None:
        return False

    now = datetime.now(timezone.utc)

    # Ensure latest_time is timezone-aware
    if latest_time.tzinfo is None:
        latest_time = latest_time.replace(tzinfo=timezone.utc)

    age = now - latest_time
    max_age = timedelta(hours=freshness_hours)

    return age <= max_age


async def check_data_freshness(db: AsyncSession) -> dict:
    """
    Check freshness of all data types.

    Returns:
        Dictionary with freshness status for each data type:
        {
            "price_snapshots": {"fresh": bool, "latest": datetime, "count": int, "age_hours": float},
            "analytics": {"fresh": bool, "latest": datetime, "count": int, "age_hours": float},
            "recommendations": {"fresh": bool, "latest": datetime, "count": int, "age_hours": float},
        }
    """
    now = datetime.now(timezone.utc)

    # Get latest timestamps and counts
    latest_snapshot = await get_latest_price_snapshot_time(db)
    latest_metrics = await get_latest_metrics_date(db)
    latest_recommendation = await get_latest_recommendation_time(db)

    snapshot_count = await get_price_snapshot_count(db)
    metrics_count = await get_metrics_count(db)
    recommendations_count = await get_recommendations_count(db)

    def calc_age_hours(latest: Optional[datetime]) -> Optional[float]:
        if latest is None:
            return None
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        age = now - latest
        return round(age.total_seconds() / 3600, 2)

    result = {
        "price_snapshots": {
            "fresh": is_data_fresh(latest_snapshot, PRICE_SNAPSHOT_FRESHNESS_HOURS),
            "latest": latest_snapshot,
            "count": snapshot_count,
            "age_hours": calc_age_hours(latest_snapshot),
            "threshold_hours": PRICE_SNAPSHOT_FRESHNESS_HOURS,
        },
        "analytics": {
            "fresh": is_data_fresh(latest_metrics, ANALYTICS_FRESHNESS_HOURS),
            "latest": latest_metrics,
            "count": metrics_count,
            "age_hours": calc_age_hours(latest_metrics),
            "threshold_hours": ANALYTICS_FRESHNESS_HOURS,
        },
        "recommendations": {
            "fresh": is_data_fresh(latest_recommendation, RECOMMENDATIONS_FRESHNESS_HOURS),
            "latest": latest_recommendation,
            "count": recommendations_count,
            "age_hours": calc_age_hours(latest_recommendation),
            "threshold_hours": RECOMMENDATIONS_FRESHNESS_HOURS,
        },
    }

    logger.info(
        "Data freshness check completed",
        price_snapshots_fresh=result["price_snapshots"]["fresh"],
        price_snapshots_count=snapshot_count,
        price_snapshots_age_hours=result["price_snapshots"]["age_hours"],
        analytics_fresh=result["analytics"]["fresh"],
        analytics_count=metrics_count,
        analytics_age_hours=result["analytics"]["age_hours"],
        recommendations_fresh=result["recommendations"]["fresh"],
        recommendations_count=recommendations_count,
        recommendations_age_hours=result["recommendations"]["age_hours"],
    )

    return result


async def should_run_price_collection(db: AsyncSession) -> bool:
    """Check if price collection task should run."""
    latest = await get_latest_price_snapshot_time(db)
    should_run = not is_data_fresh(latest, PRICE_SNAPSHOT_FRESHNESS_HOURS)

    if not should_run:
        logger.info(
            "Skipping price collection - data is fresh",
            latest_snapshot=latest,
            threshold_hours=PRICE_SNAPSHOT_FRESHNESS_HOURS,
        )

    return should_run


async def should_run_analytics(db: AsyncSession) -> bool:
    """Check if analytics task should run."""
    latest = await get_latest_metrics_date(db)
    should_run = not is_data_fresh(latest, ANALYTICS_FRESHNESS_HOURS)

    if not should_run:
        logger.info(
            "Skipping analytics - data is fresh",
            latest_metrics=latest,
            threshold_hours=ANALYTICS_FRESHNESS_HOURS,
        )

    return should_run


async def should_run_recommendations(db: AsyncSession) -> bool:
    """Check if recommendations task should run."""
    latest = await get_latest_recommendation_time(db)
    should_run = not is_data_fresh(latest, RECOMMENDATIONS_FRESHNESS_HOURS)

    if not should_run:
        logger.info(
            "Skipping recommendations - data is fresh",
            latest_recommendation=latest,
            threshold_hours=RECOMMENDATIONS_FRESHNESS_HOURS,
        )

    return should_run


async def should_run_historical_backfill(db: AsyncSession, min_snapshots: int = 1000) -> bool:
    """
    Check if historical backfill should run.

    Args:
        db: Database session
        min_snapshots: Minimum number of snapshots to consider data sufficient

    Returns:
        True if backfill should run (insufficient data), False otherwise
    """
    count = await get_price_snapshot_count(db)
    should_run = count < min_snapshots

    if not should_run:
        logger.info(
            "Skipping historical backfill - sufficient data exists",
            snapshot_count=count,
            min_required=min_snapshots,
        )
    else:
        logger.info(
            "Historical backfill needed",
            snapshot_count=count,
            min_required=min_snapshots,
        )

    return should_run


# Minimum data thresholds
MIN_CARDS_FOR_FULL_CATALOG = 10000  # Scryfall has ~90k unique cards, 10k is clearly incomplete
MIN_EMBEDDINGS_COVERAGE = 0.50  # 50% of cards should have embeddings


async def get_cards_count(db: AsyncSession) -> int:
    """Get total count of cards in the catalog."""
    result = await db.scalar(select(func.count(Card.id)))
    return result or 0


async def get_sets_count(db: AsyncSession) -> int:
    """Get total count of MTG sets."""
    result = await db.scalar(select(func.count(MTGSet.id)))
    return result or 0


async def get_embeddings_count(db: AsyncSession) -> int:
    """Get total count of card embeddings."""
    result = await db.scalar(select(func.count(CardFeatureVector.card_id)))
    return result or 0


async def get_tournaments_count(db: AsyncSession) -> int:
    """Get total count of tournaments."""
    result = await db.scalar(select(func.count(Tournament.id)))
    return result or 0


async def should_run_full_card_import(db: AsyncSession) -> bool:
    """Check if full card catalog import should run."""
    count = await get_cards_count(db)
    should_run = count < MIN_CARDS_FOR_FULL_CATALOG

    if should_run:
        logger.info(
            "Full card import needed",
            card_count=count,
            min_required=MIN_CARDS_FOR_FULL_CATALOG,
        )
    else:
        logger.info(
            "Skipping full card import - sufficient cards exist",
            card_count=count,
            min_required=MIN_CARDS_FOR_FULL_CATALOG,
        )

    return should_run


async def should_run_sets_sync(db: AsyncSession) -> bool:
    """Check if sets sync should run."""
    count = await get_sets_count(db)
    should_run = count == 0

    if should_run:
        logger.info("Sets sync needed - no sets found")
    else:
        logger.info("Skipping sets sync - sets exist", set_count=count)

    return should_run


async def should_run_embeddings_refresh(db: AsyncSession) -> bool:
    """Check if embeddings refresh should run (< 50% coverage)."""
    cards_count = await get_cards_count(db)
    embeddings_count = await get_embeddings_count(db)

    if cards_count == 0:
        logger.info("Skipping embeddings refresh - no cards to embed")
        return False

    coverage = embeddings_count / cards_count
    should_run = coverage < MIN_EMBEDDINGS_COVERAGE

    if should_run:
        logger.info(
            "Embeddings refresh needed",
            embeddings_count=embeddings_count,
            cards_count=cards_count,
            coverage_pct=round(coverage * 100, 1),
            min_coverage_pct=MIN_EMBEDDINGS_COVERAGE * 100,
        )
    else:
        logger.info(
            "Skipping embeddings refresh - sufficient coverage",
            embeddings_count=embeddings_count,
            cards_count=cards_count,
            coverage_pct=round(coverage * 100, 1),
        )

    return should_run


async def should_run_tournaments_ingestion(db: AsyncSession) -> bool:
    """Check if tournament ingestion should run."""
    count = await get_tournaments_count(db)
    should_run = count == 0

    if should_run:
        logger.info("Tournament ingestion needed - no tournaments found")
    else:
        logger.info("Skipping tournament ingestion - tournaments exist", tournament_count=count)

    return should_run


async def check_full_data_freshness(db: AsyncSession) -> dict:
    """
    Extended freshness check including cards, sets, embeddings, and tournaments.

    Returns:
        Dictionary with freshness/existence status for all data types
    """
    # Get the basic freshness check
    basic_freshness = await check_data_freshness(db)

    # Get additional counts
    cards_count = await get_cards_count(db)
    sets_count = await get_sets_count(db)
    embeddings_count = await get_embeddings_count(db)
    tournaments_count = await get_tournaments_count(db)

    # Calculate embeddings coverage
    embeddings_coverage = embeddings_count / cards_count if cards_count > 0 else 0

    # Add extended data
    basic_freshness["cards"] = {
        "count": cards_count,
        "sufficient": cards_count >= MIN_CARDS_FOR_FULL_CATALOG,
        "min_required": MIN_CARDS_FOR_FULL_CATALOG,
    }
    basic_freshness["sets"] = {
        "count": sets_count,
        "exists": sets_count > 0,
    }
    basic_freshness["embeddings"] = {
        "count": embeddings_count,
        "coverage_pct": round(embeddings_coverage * 100, 1),
        "sufficient": embeddings_coverage >= MIN_EMBEDDINGS_COVERAGE,
        "min_coverage_pct": MIN_EMBEDDINGS_COVERAGE * 100,
    }
    basic_freshness["tournaments"] = {
        "count": tournaments_count,
        "exists": tournaments_count > 0,
    }

    logger.info(
        "Full data freshness check completed",
        cards_count=cards_count,
        cards_sufficient=cards_count >= MIN_CARDS_FOR_FULL_CATALOG,
        sets_count=sets_count,
        embeddings_count=embeddings_count,
        embeddings_coverage_pct=round(embeddings_coverage * 100, 1),
        tournaments_count=tournaments_count,
    )

    return basic_freshness
