"""
Startup script that seeds data and backfills MTGJSON historical data before starting the API server.

This script:
1. Runs database migrations
2. Checks existing data freshness (extended check)
3. Seeds basic data (marketplaces, settings) - NO mock prices
4. Syncs MTG sets from Scryfall (blocking, ~10-30s)
5. Queues full card import if < 10k cards (background)
6. Backfills MTGJSON historical data (with 5-minute timeout) - ONLY if needed
7. Queues embeddings if < 50% coverage (background)
8. Queues tournaments if empty (background)
9. Starts the API server
"""
import asyncio
import sys
import subprocess
import os
from pathlib import Path
from datetime import datetime, timezone

import structlog

# Setup path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.scripts.seed_mtgjson_historical import seed_mtgjson_historical

logger = structlog.get_logger()

# Minimum snapshots to consider data sufficient (skip backfill if we have this many)
MIN_SNAPSHOTS_FOR_SKIP = 10000


async def run_migrations():
    """Run database migrations."""
    logger.info("Running database migrations...")
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info("Database migrations completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Database migrations failed", error=e.stderr)
        return False


async def seed_basic_data():
    """Seed basic data (marketplaces, settings) - NO mock prices or cards."""
    logger.info("Seeding basic data (marketplaces, settings)...")
    try:
        from app.scripts.seed_data import seed_marketplaces, seed_settings
        from app.db.session import async_session_maker

        async with async_session_maker() as db:
            # Seed marketplaces
            mp_count = await seed_marketplaces(db)
            logger.info("Seeded marketplaces", count=mp_count)

            # Seed settings
            settings_count = await seed_settings(db)
            logger.info("Seeded settings", count=settings_count)

            # NOTE: Cards are synced via sync_sets + background card catalog import
            # NOTE: We do NOT seed mock prices - only real MTGJSON historical data

            await db.commit()

            logger.info("Basic data seeding completed (no cards, no mock prices)")
            return True

    except Exception as e:
        logger.error("Basic data seeding failed", error=str(e))
        return False


async def sync_sets_if_needed():
    """
    Sync MTG sets from Scryfall (blocking operation).

    This runs synchronously at startup to ensure we have set data
    before queueing the full card import.
    """
    try:
        from app.db.session import async_session_maker
        from app.core.data_freshness import should_run_sets_sync

        async with async_session_maker() as db:
            if not await should_run_sets_sync(db):
                return {"status": "skipped", "reason": "sets_exist"}

        # Run the sync task synchronously (not via Celery)
        logger.info("Syncing MTG sets from Scryfall...")
        from app.tasks.sets_sync import sync_mtg_sets

        # Call the task function directly (not .delay())
        result = sync_mtg_sets()
        logger.info("Sets sync completed", **result)
        return result

    except Exception as e:
        logger.error("Sets sync failed", error=str(e))
        return {"status": "error", "error": str(e)}


async def queue_full_card_import_if_needed():
    """Queue full card catalog import if < 10k cards."""
    try:
        from app.db.session import async_session_maker
        from app.core.data_freshness import should_run_full_card_import

        async with async_session_maker() as db:
            if not await should_run_full_card_import(db):
                return {"status": "skipped", "reason": "sufficient_cards"}

        # Queue the task via Celery
        from app.tasks.ingestion import sync_card_catalog

        logger.info("Queuing full card catalog import...")
        task = sync_card_catalog.delay()
        logger.info("Card catalog import queued", task_id=task.id)
        return {"status": "queued", "task_id": task.id}

    except Exception as e:
        logger.warning("Failed to queue card import", error=str(e))
        return {"status": "error", "error": str(e)}


async def queue_embeddings_if_needed():
    """Queue embeddings refresh if < 50% coverage."""
    try:
        from app.db.session import async_session_maker
        from app.core.data_freshness import should_run_embeddings_refresh

        async with async_session_maker() as db:
            if not await should_run_embeddings_refresh(db):
                return {"status": "skipped", "reason": "sufficient_coverage"}

        # Queue the task via Celery
        from app.tasks.search import refresh_embeddings

        logger.info("Queuing embeddings refresh...")
        task = refresh_embeddings.delay()
        logger.info("Embeddings refresh queued", task_id=task.id)
        return {"status": "queued", "task_id": task.id}

    except Exception as e:
        logger.warning("Failed to queue embeddings refresh", error=str(e))
        return {"status": "error", "error": str(e)}


async def queue_tournaments_if_needed():
    """Queue tournament ingestion if no tournaments exist."""
    try:
        from app.db.session import async_session_maker
        from app.core.data_freshness import should_run_tournaments_ingestion

        async with async_session_maker() as db:
            if not await should_run_tournaments_ingestion(db):
                return {"status": "skipped", "reason": "tournaments_exist"}

        # Queue the task via Celery
        from app.tasks.tournaments import ingest_recent_tournaments

        logger.info("Queuing tournament ingestion...")
        task = ingest_recent_tournaments.delay()
        logger.info("Tournament ingestion queued", task_id=task.id)
        return {"status": "queued", "task_id": task.id}

    except Exception as e:
        logger.warning("Failed to queue tournament ingestion", error=str(e))
        return {"status": "error", "error": str(e)}


async def backfill_historical_data(timeout_minutes: int = 5, card_limit: int = 4000):
    """
    Backfill historical data from MTGJSON with a timeout.
    
    Args:
        timeout_minutes: Maximum time to spend backfilling (default: 5 minutes)
        card_limit: Maximum number of cards to process (default: 200 for faster startup)
    
    Returns:
        Statistics about the backfilling process
    """
    logger.info(
        "Starting MTGJSON historical data backfill",
        timeout_minutes=timeout_minutes,
        card_limit=card_limit
    )
    
    start_time = datetime.now(timezone.utc)
    
    try:
        # Run backfill with timeout
        # Process a limited number of cards initially for faster startup
        stats = await asyncio.wait_for(
            seed_mtgjson_historical(
                card_limit=card_limit,  # Process limited cards for faster startup
                skip_existing=True,  # Skip cards that already have data
                days=30,  # 30 days of history
                batch_size=50,  # Process 50 cards at a time
            ),
            timeout=timeout_minutes * 60  # Convert to seconds
        )
        
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            "MTGJSON historical data backfill completed",
            elapsed_seconds=elapsed,
            cards_processed=stats.get("cards_processed", 0),
            snapshots_created=stats.get("snapshots_created", 0),
        )
        
        return stats
    
    except asyncio.TimeoutError:
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.warning(
            "MTGJSON historical data backfill timed out",
            timeout_minutes=timeout_minutes,
            elapsed_seconds=elapsed,
            message="Backfilling will continue in background via Celery task"
        )
        return {
            "status": "timeout",
            "elapsed_seconds": elapsed,
            "message": "Backfilling will continue in background"
        }
    
    except Exception as e:
        logger.error("MTGJSON historical data backfill failed", error=str(e))
        return {
            "status": "error",
            "error": str(e)
        }


async def trigger_background_backfill():
    """Trigger Celery task to continue backfilling in background."""
    try:
        from app.tasks.data_seeding import seed_comprehensive_price_data

        logger.info("Triggering background MTGJSON backfill task...")
        # Schedule the task to run asynchronously
        task = seed_comprehensive_price_data.delay()
        logger.info("Background backfill task scheduled", task_id=task.id)
        return True
    except Exception as e:
        logger.warning(
            "Failed to trigger background backfill task",
            error=str(e),
            message="Backfilling will need to be triggered manually or via Celery Beat"
        )
        return False


async def check_existing_data():
    """
    Check if sufficient data already exists in the database.

    Returns:
        dict with data counts and freshness info (extended check)
    """
    try:
        from app.db.session import async_session_maker
        from app.core.data_freshness import check_full_data_freshness

        async with async_session_maker() as db:
            freshness = await check_full_data_freshness(db)
            snapshot_count = freshness["price_snapshots"]["count"]
            analytics_count = freshness["analytics"]["count"]
            recommendations_count = freshness["recommendations"]["count"]
            cards_count = freshness["cards"]["count"]
            sets_count = freshness["sets"]["count"]
            embeddings_count = freshness["embeddings"]["count"]
            tournaments_count = freshness["tournaments"]["count"]

            return {
                "snapshot_count": snapshot_count,
                "analytics_count": analytics_count,
                "recommendations_count": recommendations_count,
                "cards_count": cards_count,
                "sets_count": sets_count,
                "embeddings_count": embeddings_count,
                "embeddings_coverage_pct": freshness["embeddings"]["coverage_pct"],
                "tournaments_count": tournaments_count,
                "price_fresh": freshness["price_snapshots"]["fresh"],
                "analytics_fresh": freshness["analytics"]["fresh"],
                "recommendations_fresh": freshness["recommendations"]["fresh"],
                "cards_sufficient": freshness["cards"]["sufficient"],
                "sets_exist": freshness["sets"]["exists"],
                "embeddings_sufficient": freshness["embeddings"]["sufficient"],
                "tournaments_exist": freshness["tournaments"]["exists"],
                "has_sufficient_data": snapshot_count >= MIN_SNAPSHOTS_FOR_SKIP,
            }
    except Exception as e:
        logger.warning("Failed to check existing data", error=str(e))
        return {
            "snapshot_count": 0,
            "analytics_count": 0,
            "recommendations_count": 0,
            "cards_count": 0,
            "sets_count": 0,
            "embeddings_count": 0,
            "embeddings_coverage_pct": 0,
            "tournaments_count": 0,
            "price_fresh": False,
            "analytics_fresh": False,
            "recommendations_fresh": False,
            "cards_sufficient": False,
            "sets_exist": False,
            "embeddings_sufficient": False,
            "tournaments_exist": False,
            "has_sufficient_data": False,
        }


async def main():
    """Main startup function."""
    logger.info("Starting application...")

    # Step 1: Run migrations
    if not await run_migrations():
        logger.error("Migrations failed, exiting")
        sys.exit(1)

    # Step 2: Check existing data (extended check)
    existing_data = await check_existing_data()
    logger.info(
        "Existing data check",
        snapshot_count=existing_data["snapshot_count"],
        analytics_count=existing_data["analytics_count"],
        recommendations_count=existing_data["recommendations_count"],
        cards_count=existing_data["cards_count"],
        sets_count=existing_data["sets_count"],
        embeddings_count=existing_data["embeddings_count"],
        embeddings_coverage_pct=existing_data["embeddings_coverage_pct"],
        tournaments_count=existing_data["tournaments_count"],
        price_fresh=existing_data["price_fresh"],
        analytics_fresh=existing_data["analytics_fresh"],
        recommendations_fresh=existing_data["recommendations_fresh"],
        cards_sufficient=existing_data["cards_sufficient"],
        sets_exist=existing_data["sets_exist"],
        embeddings_sufficient=existing_data["embeddings_sufficient"],
        tournaments_exist=existing_data["tournaments_exist"],
        has_sufficient_data=existing_data["has_sufficient_data"],
    )

    # Step 3: Seed basic data (marketplaces, settings) - always run (idempotent)
    if not await seed_basic_data():
        logger.error("Basic data seeding failed, exiting")
        sys.exit(1)

    # Step 4: Sync MTG sets from Scryfall (blocking, ~10-30s)
    sets_result = await sync_sets_if_needed()
    logger.info("Sets sync result", **sets_result)

    # Step 5: Queue full card import if needed (background)
    card_import_result = await queue_full_card_import_if_needed()
    logger.info("Card import queue result", **card_import_result)

    # Step 6: Backfill MTGJSON historical data - ONLY if insufficient data exists
    if existing_data["has_sufficient_data"]:
        logger.info(
            "Skipping MTGJSON backfill - sufficient data already exists",
            snapshot_count=existing_data["snapshot_count"],
            min_required=MIN_SNAPSHOTS_FOR_SKIP,
        )
        backfill_stats = {
            "status": "skipped",
            "reason": "sufficient_data_exists",
            "existing_snapshots": existing_data["snapshot_count"],
        }
    else:
        logger.info(
            "Running MTGJSON backfill - insufficient data",
            snapshot_count=existing_data["snapshot_count"],
            min_required=MIN_SNAPSHOTS_FOR_SKIP,
        )
        # Backfill with 5-minute timeout, process up to 4000 cards
        backfill_stats = await backfill_historical_data(timeout_minutes=5, card_limit=4000)

        # Trigger background backfill task to continue processing all cards
        await trigger_background_backfill()

    # Step 7: Queue embeddings refresh if needed (background)
    embeddings_result = await queue_embeddings_if_needed()
    logger.info("Embeddings queue result", **embeddings_result)

    # Step 8: Queue tournament ingestion if needed (background)
    tournaments_result = await queue_tournaments_if_needed()
    logger.info("Tournaments queue result", **tournaments_result)

    logger.info(
        "Startup seeding completed",
        backfill_status=backfill_stats.get("status", "completed"),
        cards_processed=backfill_stats.get("cards_processed", 0),
        snapshots_created=backfill_stats.get("snapshots_created", 0),
        sets_sync=sets_result.get("status", "unknown"),
        card_import=card_import_result.get("status", "unknown"),
        embeddings=embeddings_result.get("status", "unknown"),
        tournaments=tournaments_result.get("status", "unknown"),
        message="Starting API server..."
    )

    # Step 9: Start the API server using subprocess
    logger.info("Starting uvicorn server...")

    # Start uvicorn as a subprocess
    process = subprocess.Popen(
        [
            "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8000"
        ],
        env=os.environ
    )

    # Wait for the process to complete
    try:
        process.wait()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        process.terminate()
        process.wait()
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

