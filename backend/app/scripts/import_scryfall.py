"""
Import full Scryfall card database.

This script downloads the bulk card data from Scryfall and imports it
into the local database. Run this to populate the database with real cards.

Usage:
    python -m app.scripts.import_scryfall [--type default_cards]
    
Types:
    - default_cards: One card per Oracle ID (recommended, ~30k cards)
    - all_cards: All printings (~90k cards)
    - oracle_cards: Only English cards with Oracle text (~25k cards)
"""
import argparse
import asyncio
import gzip
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator, Sequence

import httpx
import ijson
import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Setup path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db.session import async_session_maker
from app.models.card import Card
from app.models.marketplace import Marketplace
from app.models.price_snapshot import PriceSnapshot
from app.services.ingestion.scryfall import ScryfallAdapter

logger = structlog.get_logger()

BULK_DATA_TYPES = {
    "default_cards": "One version of each card (recommended)",
    "all_cards": "All card printings (large)",
    "oracle_cards": "English cards with Oracle text only",
    "unique_artwork": "One card per unique artwork",
}


async def get_bulk_data_url(data_type: str) -> tuple[str, int]:
    """Fetch the bulk data download URL from Scryfall."""
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.scryfall.com/bulk-data")
        response.raise_for_status()
        data = response.json()
        
        for item in data.get("data", []):
            if item.get("type") == data_type:
                return item.get("download_uri"), item.get("size", 0)
        
        raise ValueError(f"Unknown bulk data type: {data_type}")


async def download_bulk_data(url: str, output_path: Path) -> Path:
    """Download bulk data file with progress."""
    logger.info("Downloading bulk data", url=url)
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=300) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            
            downloaded = 0
            with open(output_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = (downloaded / total) * 100
                        print(f"\rDownloading: {pct:.1f}% ({downloaded / 1024 / 1024:.1f} MB)", end="", flush=True)
            
            print()  # Newline after progress
    
    logger.info("Download complete", path=str(output_path), size_mb=downloaded / 1024 / 1024)
    return output_path


def parse_released_at(value: str | None) -> datetime | None:
    """Convert Scryfall's released_at string into a timezone-aware datetime."""
    if not value:
        return None
    
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Invalid released_at format", released_at=value)
        return None
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_card_data(card: dict) -> dict:
    """Parse Scryfall card data into database model format."""
    # Handle double-faced cards
    image_uris = card.get("image_uris", {})
    if not image_uris and card.get("card_faces"):
        image_uris = card["card_faces"][0].get("image_uris", {})
    
    # Parse colors
    colors = card.get("colors", [])
    color_identity = card.get("color_identity", [])
    legalities = card.get("legalities", {})
    
    return {
        "scryfall_id": card.get("id"),
        "oracle_id": card.get("oracle_id"),
        "name": card.get("name", "")[:255],  # Truncate to fit column
        "set_code": card.get("set", "").upper(),
        "set_name": card.get("set_name"),
        "collector_number": card.get("collector_number", "")[:20],
        "rarity": card.get("rarity"),
        "mana_cost": card.get("mana_cost"),
        "cmc": card.get("cmc"),
        "type_line": card.get("type_line"),
        "oracle_text": card.get("oracle_text"),
        "colors": json.dumps(colors) if colors else None,
        "color_identity": json.dumps(color_identity) if color_identity else None,
        "power": card.get("power"),
        "toughness": card.get("toughness"),
        "legalities": json.dumps(legalities) if legalities else None,
        "image_url": image_uris.get("normal"),
        "image_url_small": image_uris.get("small"),
        "image_url_large": image_uris.get("large") or image_uris.get("png"),
        "released_at": parse_released_at(card.get("released_at")),
    }


def extract_prices(card: dict) -> dict | None:
    """Extract price data from card."""
    prices = card.get("prices", {})
    usd = prices.get("usd")
    usd_foil = prices.get("usd_foil")
    eur = prices.get("eur")
    
    if not usd and not eur:
        return None
    
    return {
        "usd": float(usd) if usd else None,
        "usd_foil": float(usd_foil) if usd_foil else None,
        "eur": float(eur) if eur else None,
        "eur_foil": float(prices.get("eur_foil")) if prices.get("eur_foil") else None,
    }


@contextmanager
def open_bulk_file(json_path: Path) -> Iterator[BinaryIO]:
    """
    Open a bulk file transparently handling gzip-compressed inputs.
    
    Scryfall sometimes serves .json.gz payloads even when the URL ends with .json,
    so we inspect the first two bytes and wrap with gzip when needed.
    """
    raw = open(json_path, "rb")
    try:
        signature = raw.read(2)
        raw.seek(0)
        if signature == b"\x1f\x8b":
            with gzip.GzipFile(fileobj=raw) as gz:
                yield gz
        else:
            yield raw
    finally:
        if not raw.closed:
            raw.close()


def should_skip_card(card: dict) -> bool:
    """Return True when card layout is a token/emblem/etc we don't persist."""
    return card.get("layout") in {"token", "emblem", "art_series"}


async def process_batch(
    session,
    batch: Sequence[dict],
    tcgplayer: Marketplace | None,
    cardmarket: Marketplace | None,
    stats: dict,
    language: str | None,
) -> None:
    """Process a batch of cards and persist to the database."""
    card_records: list[dict] = []
    price_records: list[dict] = []
    
    for card in batch:
        try:
            if should_skip_card(card):
                stats["cards_skipped"] += 1
                continue

            card_lang = (card.get("lang") or "").lower()
            if language and card_lang and card_lang != language:
                stats["cards_skipped"] += 1
                continue
            
            card_record = parse_card_data(card)
            card_records.append(card_record)
            
            prices = extract_prices(card)
            if prices and card_record["scryfall_id"]:
                if tcgplayer and prices.get("usd"):
                    price_records.append({
                        "scryfall_id": card_record["scryfall_id"],
                        "marketplace_id": tcgplayer.id,
                        "price": prices["usd"],
                        "price_foil": prices.get("usd_foil"),
                        "currency": "USD",
                    })
                
                if cardmarket and prices.get("eur"):
                    price_records.append({
                        "scryfall_id": card_record["scryfall_id"],
                        "marketplace_id": cardmarket.id,
                        "price": prices["eur"],
                        "price_foil": prices.get("eur_foil"),
                        "currency": "EUR",
                    })
            
            stats["cards_processed"] += 1
        
        except Exception as exc:
            logger.error(
                "Error processing card",
                card_name=card.get("name"),
                error=str(exc),
            )
            stats["errors"] += 1
    
    if card_records:
        stmt = pg_insert(Card).values(card_records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["scryfall_id"],
            set_={
                "name": stmt.excluded.name,
                "set_name": stmt.excluded.set_name,
                "rarity": stmt.excluded.rarity,
                "mana_cost": stmt.excluded.mana_cost,
                "cmc": stmt.excluded.cmc,
                "type_line": stmt.excluded.type_line,
                "oracle_text": stmt.excluded.oracle_text,
                "colors": stmt.excluded.colors,
                "color_identity": stmt.excluded.color_identity,
                "power": stmt.excluded.power,
                "toughness": stmt.excluded.toughness,
                "legalities": stmt.excluded.legalities,
                "image_url": stmt.excluded.image_url,
                "image_url_small": stmt.excluded.image_url_small,
                "image_url_large": stmt.excluded.image_url_large,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        stats["cards_inserted"] += len(card_records)
    
    if price_records:
        scryfall_ids = [p["scryfall_id"] for p in price_records]
        result = await session.execute(
            select(Card.id, Card.scryfall_id).where(Card.scryfall_id.in_(scryfall_ids))
        )
        card_id_map = {row.scryfall_id: row.id for row in result}
        
        now = datetime.utcnow()
        snapshot_records = []
        for pr in price_records:
            card_id = card_id_map.get(pr["scryfall_id"])
            if card_id:
                snapshot_records.append({
                    "card_id": card_id,
                    "marketplace_id": pr["marketplace_id"],
                    "price": pr["price"],
                    "price_foil": pr.get("price_foil"),
                    "currency": pr["currency"],
                    "snapshot_time": now,
                })
        
        if snapshot_records:
            await session.execute(pg_insert(PriceSnapshot).values(snapshot_records))
            stats["prices_added"] += len(snapshot_records)
    
    await session.commit()


async def import_cards(
    json_path: Path,
    batch_size: int = 1000,
    language: str | None = "en",
) -> dict:
    """Import cards from JSON file into database."""
    logger.info("Starting card import", path=str(json_path), batch_size=batch_size)
    
    stats = {
        "cards_processed": 0,
        "cards_inserted": 0,
        "prices_added": 0,
        "cards_skipped": 0,
        "errors": 0,
    }
    
    async with async_session_maker() as session:
        tcgplayer = await session.execute(
            select(Marketplace).where(Marketplace.slug == "tcgplayer")
        )
        tcgplayer = tcgplayer.scalar_one_or_none()
        
        cardmarket = await session.execute(
            select(Marketplace).where(Marketplace.slug == "cardmarket")
        )
        cardmarket = cardmarket.scalar_one_or_none()
        
        with open_bulk_file(json_path) as fh:
            parser = ijson.items(fh, "item")
            batch: list[dict] = []
            
            for card in parser:
                batch.append(card)
                if len(batch) >= batch_size:
                    await process_batch(
                        session, batch, tcgplayer, cardmarket, stats, language
                    )
                    print(
                        f"\rProcessed: {stats['cards_processed']:,} cards",
                        end="",
                        flush=True,
                    )
                    batch.clear()
            
            if batch:
                await process_batch(
                    session, batch, tcgplayer, cardmarket, stats, language
                )
                print(
                    f"\rProcessed: {stats['cards_processed']:,} cards",
                    end="",
                    flush=True,
                )
    
    if stats["cards_processed"]:
        print(
            f"\rProcessed: {stats['cards_processed']:,} cards",
            end="",
            flush=True,
        )
    print()  # newline after final progress update
    return stats


async def main():
    parser = argparse.ArgumentParser(description="Import Scryfall bulk data")
    parser.add_argument(
        "--type",
        choices=list(BULK_DATA_TYPES.keys()),
        default="default_cards",
        help="Type of bulk data to import",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download if file already exists",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for database inserts",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        help="Limit to a specific Scryfall language code (e.g., 'en'). Use '' to import all languages.",
    )
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"  Scryfall Bulk Import: {args.type}")
    print(f"  {BULK_DATA_TYPES[args.type]}")
    print(f"{'='*60}\n")
    
    # Create data directory (use /tmp in container for write access)
    if Path("/app").exists():
        data_dir = Path("/tmp/scryfall_data")
    else:
        data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    
    json_path = data_dir / f"scryfall_{args.type}.json"
    
    # Download if needed
    if not json_path.exists() or not args.skip_download:
        url, size = await get_bulk_data_url(args.type)
        logger.info("Bulk data info", url=url, size_mb=size / 1024 / 1024)
        await download_bulk_data(url, json_path)
    else:
        logger.info("Using existing file", path=str(json_path))
    
    # Import cards
    language = args.language or None
    stats = await import_cards(
        json_path,
        batch_size=args.batch_size,
        language=language.lower() if language else None,
    )
    
    print(f"\n{'='*60}")
    print("  Import Complete!")
    print(f"{'='*60}")
    print(f"  Cards processed: {stats['cards_processed']:,}")
    print(f"  Cards upserted: {stats['cards_inserted']:,}")
    print(f"  Cards skipped: {stats['cards_skipped']:,}")
    print(f"  Price snapshots added: {stats['prices_added']:,}")
    print(f"  Errors: {stats['errors']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
