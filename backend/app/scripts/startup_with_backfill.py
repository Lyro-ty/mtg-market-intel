"""
Startup script that seeds data and backfills MTGJSON historical data before starting the API server.

This script:
1. Runs database migrations
2. Seeds basic data (marketplaces, settings, cards) - NO mock prices
3. Backfills MTGJSON historical data (with 5-minute timeout)
4. Starts the API server
5. Continues backfilling in background via Celery task
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
    """Seed basic data (marketplaces, settings, cards) - NO mock prices."""
    logger.info("Seeding basic data (marketplaces, settings, cards)...")
    try:
        # Import the seed functions directly
        from app.scripts.seed_data import (
            seed_marketplaces,
            seed_settings,
            seed_cards_from_scryfall,
        )
        from app.db.session import async_session_maker
        from app.scripts.seed_data import SEED_SETS
        
        async with async_session_maker() as db:
            # Seed marketplaces
            mp_count = await seed_marketplaces(db)
            logger.info("Seeded marketplaces", count=mp_count)
            
            # Seed settings
            settings_count = await seed_settings(db)
            logger.info("Seeded settings", count=settings_count)
            
            # Seed cards from Scryfall (30 cards per set for faster startup)
            cards_count = await seed_cards_from_scryfall(
                db, SEED_SETS, cards_per_set=30
            )
            logger.info("Seeded cards", count=cards_count)
            
            # NOTE: We do NOT seed mock prices - only real MTGJSON historical data
            
            # Commit all changes
            await db.commit()
            
            logger.info("Basic data seeding completed successfully (no mock prices)")
            return True
    
    except Exception as e:
        logger.error("Basic data seeding failed", error=str(e))
        return False


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


async def main():
    """Main startup function."""
    logger.info("Starting application with MTGJSON historical data backfill...")
    
    # Step 1: Run migrations
    if not await run_migrations():
        logger.error("Migrations failed, exiting")
        sys.exit(1)
    
    # Step 2: Seed basic data (NO mock prices)
    if not await seed_basic_data():
        logger.error("Basic data seeding failed, exiting")
        sys.exit(1)
    
    # Step 3: Backfill MTGJSON historical data (with 5-minute timeout, process up to 4000 cards)
    backfill_stats = await backfill_historical_data(timeout_minutes=5, card_limit=4000)
    
    # Step 4: Trigger background backfill task to continue processing all cards
    await trigger_background_backfill()
    
    logger.info(
        "Startup seeding completed",
        backfill_status=backfill_stats.get("status", "completed"),
        cards_processed=backfill_stats.get("cards_processed", 0),
        snapshots_created=backfill_stats.get("snapshots_created", 0),
        message="Starting API server..."
    )
    
    # Step 5: Start the API server using subprocess
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

