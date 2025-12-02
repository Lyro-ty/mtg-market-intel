"""
Slim database to only cards in Scryfall's default_cards bulk data.

This script:
1. Downloads Scryfall's default_cards bulk data (or uses existing file)
2. Extracts all scryfall_ids from it
3. Deletes all cards from the database that are NOT in that set
4. Related data (listings, price_snapshots, etc.) will be deleted via cascade

Usage:
    python -m app.scripts.slim_to_default_cards [--skip-download] [--dry-run]
    
WARNING: This will permanently delete cards and all related data!
"""
import argparse
import asyncio
import sys
from pathlib import Path

import ijson
import structlog
from sqlalchemy import select

# Setup path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db.session import async_session_maker
from app.models.card import Card
from app.scripts.import_scryfall import (
    download_bulk_data,
    get_bulk_data_url,
    open_bulk_file,
)

logger = structlog.get_logger()


async def extract_scryfall_ids(json_path: Path) -> set[str]:
    """Extract all scryfall_ids from the bulk data file."""
    logger.info("Extracting scryfall_ids from bulk data", path=str(json_path))
    
    scryfall_ids: set[str] = set()
    
    with open_bulk_file(json_path) as fh:
        parser = ijson.items(fh, "item")
        
        for card in parser:
            card_id = card.get("id")
            if card_id:
                scryfall_ids.add(card_id)
    
    logger.info("Extracted scryfall_ids", count=len(scryfall_ids))
    return scryfall_ids


async def find_cards_to_delete(
    session, valid_scryfall_ids: set[str], batch_size: int = 1000
) -> tuple[list[int], int]:
    """Find all card IDs that should be deleted and total card count."""
    logger.info("Finding cards to delete", valid_count=len(valid_scryfall_ids))
    
    cards_to_delete: list[int] = []
    total_cards = 0
    offset = 0
    
    while True:
        result = await session.execute(
            select(Card.id, Card.scryfall_id)
            .offset(offset)
            .limit(batch_size)
        )
        rows = result.all()
        
        if not rows:
            break
        
        total_cards += len(rows)
        
        for row in rows:
            if row.scryfall_id not in valid_scryfall_ids:
                cards_to_delete.append(row.id)
        
        offset += batch_size
        
        if len(rows) < batch_size:
            break
    
    logger.info("Found cards to delete", count=len(cards_to_delete), total=total_cards)
    return cards_to_delete, total_cards


async def delete_cards(session, card_ids: list[int], batch_size: int = 1000) -> int:
    """Delete cards in batches."""
    total_deleted = 0
    
    for i in range(0, len(card_ids), batch_size):
        batch = card_ids[i : i + batch_size]
        
        result = await session.execute(
            select(Card).where(Card.id.in_(batch))
        )
        cards = result.scalars().all()
        
        for card in cards:
            await session.delete(card)
        
        await session.commit()
        total_deleted += len(cards)
        
        logger.info(
            "Deleted batch",
            batch_size=len(cards),
            total_deleted=total_deleted,
            remaining=len(card_ids) - total_deleted,
        )
    
    return total_deleted


async def main():
    parser = argparse.ArgumentParser(
        description="Slim database to only Scryfall default_cards"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download if file already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for database operations",
    )
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print("  Slim Database to Default Cards")
    print(f"{'='*60}\n")
    
    if args.dry_run:
        print("  ⚠️  DRY RUN MODE - No changes will be made\n")
    else:
        print("  ⚠️  WARNING: This will permanently delete cards and related data!\n")
        response = input("  Type 'yes' to continue: ")
        if response.lower() != "yes":
            print("  Aborted.")
            return
    
    # Create data directory
    if Path("/app").exists():
        data_dir = Path("/tmp/scryfall_data")
    else:
        data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    
    json_path = data_dir / "scryfall_default_cards.json"
    
    # Download if needed
    if not json_path.exists() or not args.skip_download:
        url, size = await get_bulk_data_url("default_cards")
        logger.info("Bulk data info", url=url, size_mb=size / 1024 / 1024)
        await download_bulk_data(url, json_path)
    else:
        logger.info("Using existing file", path=str(json_path))
    
    # Extract valid scryfall_ids
    valid_scryfall_ids = await extract_scryfall_ids(json_path)
    
    # Find cards to delete
    async with async_session_maker() as session:
        cards_to_delete, total_cards = await find_cards_to_delete(
            session, valid_scryfall_ids, batch_size=args.batch_size
        )
        
        if not cards_to_delete:
            print("\n  ✅ No cards to delete. Database already contains only default_cards.")
            return
        
        print(f"\n  Current database: {total_cards:,} cards")
        print(f"  Valid default_cards: {len(valid_scryfall_ids):,} cards")
        print(f"  Cards to delete: {len(cards_to_delete):,} cards")
        print(f"  Cards to keep: {total_cards - len(cards_to_delete):,} cards")
        
        if args.dry_run:
            # Show sample of cards that would be deleted
            result = await session.execute(
                select(Card.name, Card.set_code, Card.scryfall_id)
                .where(Card.id.in_(cards_to_delete[:10]))
            )
            sample = result.all()
            
            print("\n  Sample of cards that would be deleted:")
            for name, set_code, scryfall_id in sample:
                print(f"    - {name} ({set_code}) - {scryfall_id}")
            
            if len(cards_to_delete) > 10:
                print(f"    ... and {len(cards_to_delete) - 10:,} more")
            
            print("\n  Run without --dry-run to actually delete these cards.")
        else:
            # Delete cards
            deleted_count = await delete_cards(
                session, cards_to_delete, batch_size=args.batch_size
            )
            
            print(f"\n{'='*60}")
            print("  Deletion Complete!")
            print(f"{'='*60}")
            print(f"  Cards deleted: {deleted_count:,}")
            print(f"  Cards remaining: {total_cards - deleted_count:,}")
            print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())

