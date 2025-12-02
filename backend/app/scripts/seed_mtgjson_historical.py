"""
Seed marketplaces with MTGJSON 30-day historical price data.

This script:
1. Fetches all cards from the database
2. For each card, fetches 30 days of historical price data from MTGJSON
3. Stores prices broken down by marketplace (TCGPlayer, Cardmarket)
4. Skips cards that already have recent historical data

Usage:
    python -m app.scripts.seed_mtgjson_historical [--card-limit N] [--skip-existing]
    
Options:
    --card-limit: Limit number of cards to process (useful for testing)
    --skip-existing: Skip cards that already have MTGJSON historical data
    --days: Number of days of history to fetch (default: 30)
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog
from sqlalchemy import select, and_

# Setup path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db.session import async_session_maker
from app.models.card import Card
from app.models.marketplace import Marketplace
from app.models.price_snapshot import PriceSnapshot
from app.services.ingestion import get_adapter

logger = structlog.get_logger()


async def get_or_create_marketplace(
    db, slug: str, name: str, base_url: str, currency: str
) -> Marketplace:
    """Get or create a marketplace by slug."""
    query = select(Marketplace).where(Marketplace.slug == slug)
    result = await db.execute(query)
    mp = result.scalar_one_or_none()
    
    if not mp:
        mp = Marketplace(
            name=name,
            slug=slug,
            base_url=base_url,
            api_url=None,
            is_enabled=True,
            supports_api=False,
            default_currency=currency,
            rate_limit_seconds=1.0,
        )
        db.add(mp)
        await db.flush()
    
    return mp


async def has_recent_mtgjson_data(db, card_id: int, days: int) -> bool:
    """Check if card already has MTGJSON historical data within the specified days."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Check for TCGPlayer or Cardmarket snapshots (from MTGJSON)
    query = select(PriceSnapshot).join(Marketplace).where(
        and_(
            PriceSnapshot.card_id == card_id,
            Marketplace.slug.in_(["tcgplayer", "cardmarket"]),
            PriceSnapshot.snapshot_time >= cutoff_date,
        )
    ).limit(1)
    
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


async def seed_mtgjson_historical(
    card_limit: int | None = None,
    skip_existing: bool = False,
    days: int = 30,
    batch_size: int = 50,
) -> dict:
    """
    Seed marketplaces with MTGJSON 30-day historical data.
    
    Args:
        card_limit: Maximum number of cards to process (None = all cards)
        skip_existing: Skip cards that already have historical data
        days: Number of days of history to fetch
        batch_size: Number of cards to process in each batch
        
    Returns:
        Statistics about the seeding process
    """
    logger.info(
        "Starting MTGJSON historical data seeding",
        card_limit=card_limit,
        skip_existing=skip_existing,
        days=days,
    )
    
    stats = {
        "cards_processed": 0,
        "cards_skipped": 0,
        "snapshots_created": 0,
        "snapshots_skipped": 0,
        "errors": 0,
        "start_time": datetime.now(timezone.utc),
    }
    
    async with async_session_maker() as db:
        # Get MTGJSON adapter
        mtgjson = get_adapter("mtgjson", cached=False)
        
        try:
            # Get all cards
            query = select(Card)
            if card_limit:
                query = query.limit(card_limit)
            
            result = await db.execute(query)
            all_cards = list(result.scalars().all())
            
            logger.info("Found cards to process", total=len(all_cards))
            
            if not all_cards:
                logger.warning("No cards found in database")
                return stats
            
            # Process cards in batches
            for batch_start in range(0, len(all_cards), batch_size):
                batch = all_cards[batch_start : batch_start + batch_size]
                
                for card in batch:
                    try:
                        # Check if we should skip this card
                        if skip_existing and await has_recent_mtgjson_data(db, card.id, days):
                            stats["cards_skipped"] += 1
                            continue
                        
                        # Fetch 30-day historical prices from MTGJSON
                        historical_prices = await mtgjson.fetch_price_history(
                            card_name=card.name,
                            set_code=card.set_code,
                            collector_number=card.collector_number,
                            scryfall_id=card.scryfall_id,
                            days=days,
                        )
                        
                        if not historical_prices:
                            stats["cards_skipped"] += 1
                            continue
                        
                        # Store prices broken down by marketplace
                        for price_data in historical_prices:
                            if not price_data or price_data.price <= 0:
                                continue
                            
                            # Map currency to marketplace
                            marketplace_map = {
                                "USD": ("tcgplayer", "TCGPlayer", "https://www.tcgplayer.com"),
                                "EUR": ("cardmarket", "Cardmarket", "https://www.cardmarket.com"),
                            }
                            
                            slug, name, base_url = marketplace_map.get(
                                price_data.currency, (None, None, None)
                            )
                            if not slug:
                                continue
                            
                            # Get or create marketplace
                            marketplace = await get_or_create_marketplace(
                                db, slug, name, base_url, price_data.currency
                            )
                            
                            # Check if snapshot already exists
                            existing_query = select(PriceSnapshot).where(
                                and_(
                                    PriceSnapshot.card_id == card.id,
                                    PriceSnapshot.marketplace_id == marketplace.id,
                                    PriceSnapshot.snapshot_time == price_data.snapshot_time,
                                )
                            )
                            existing_result = await db.execute(existing_query)
                            existing = existing_result.scalar_one_or_none()
                            
                            if existing:
                                stats["snapshots_skipped"] += 1
                            else:
                                # Create new snapshot
                                snapshot = PriceSnapshot(
                                    card_id=card.id,
                                    marketplace_id=marketplace.id,
                                    snapshot_time=price_data.snapshot_time,
                                    price=price_data.price,
                                    currency=price_data.currency,
                                    price_foil=price_data.price_foil,
                                )
                                db.add(snapshot)
                                stats["snapshots_created"] += 1
                        
                        stats["cards_processed"] += 1
                        
                        # Progress logging
                        if stats["cards_processed"] % 100 == 0:
                            await db.flush()
                            logger.info(
                                "Progress",
                                processed=stats["cards_processed"],
                                created=stats["snapshots_created"],
                                skipped=stats["snapshots_skipped"],
                            )
                    
                    except Exception as e:
                        stats["errors"] += 1
                        logger.warning(
                            "Failed to process card",
                            card_id=card.id,
                            card_name=card.name,
                            error=str(e),
                        )
                        continue
                
                # Flush batch
                await db.flush()
                logger.info(
                    "Batch complete",
                    batch_start=batch_start,
                    batch_size=len(batch),
                    total_processed=stats["cards_processed"],
                    total_created=stats["snapshots_created"],
                )
            
            # Final commit
            await db.commit()
            
            stats["end_time"] = datetime.now(timezone.utc)
            stats["duration_seconds"] = (
                stats["end_time"] - stats["start_time"]
            ).total_seconds()
            
            logger.info(
                "MTGJSON historical data seeding complete",
                **stats,
            )
            
        finally:
            await mtgjson.close()
    
    return stats


async def main():
    parser = argparse.ArgumentParser(
        description="Seed marketplaces with MTGJSON 30-day historical data"
    )
    parser.add_argument(
        "--card-limit",
        type=int,
        default=None,
        help="Limit number of cards to process (useful for testing)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip cards that already have MTGJSON historical data",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of history to fetch (default: 30)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of cards to process in each batch (default: 50)",
    )
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print("  Seed MTGJSON Historical Data")
    print(f"{'='*60}\n")
    print(f"  Days of history: {args.days}")
    print(f"  Card limit: {args.card_limit or 'All cards'}")
    print(f"  Skip existing: {args.skip_existing}")
    print(f"  Batch size: {args.batch_size}\n")
    
    stats = await seed_mtgjson_historical(
        card_limit=args.card_limit,
        skip_existing=args.skip_existing,
        days=args.days,
        batch_size=args.batch_size,
    )
    
    print(f"\n{'='*60}")
    print("  Seeding Complete!")
    print(f"{'='*60}")
    print(f"  Cards processed: {stats['cards_processed']:,}")
    print(f"  Cards skipped: {stats['cards_skipped']:,}")
    print(f"  Snapshots created: {stats['snapshots_created']:,}")
    print(f"  Snapshots skipped: {stats['snapshots_skipped']:,}")
    print(f"  Errors: {stats['errors']}")
    if "duration_seconds" in stats:
        duration_min = stats["duration_seconds"] / 60
        print(f"  Duration: {duration_min:.1f} minutes")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())

