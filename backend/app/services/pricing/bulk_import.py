"""Bulk price import service using Scryfall bulk data."""
import asyncio
import json
import logging
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
import ijson
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.card import Card
from app.models.price_snapshot import PriceSnapshot
from app.models.marketplace import Marketplace
from app.core.constants import CardCondition, CardLanguage

logger = logging.getLogger(__name__)

SCRYFALL_BULK_API = "https://api.scryfall.com/bulk-data"
SCRYFALL_USER_AGENT = "DualcasterDeals/1.0"


class BulkPriceImporter:
    """Import prices from Scryfall bulk data files."""

    def __init__(self):
        self.headers = {
            "User-Agent": SCRYFALL_USER_AGENT,
            "Accept": "application/json"
        }

    def parse_scryfall_prices(self, card_data: dict[str, Any]) -> dict[str, Any]:
        """Extract price and semantic fields from Scryfall card data."""
        prices = card_data.get("prices", {})

        def parse_price(val: Optional[str]) -> Optional[float]:
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        return {
            "scryfall_id": card_data.get("id"),
            "oracle_id": card_data.get("oracle_id"),
            "name": card_data.get("name"),
            "set_code": card_data.get("set"),
            "collector_number": card_data.get("collector_number"),
            # Prices
            "usd": parse_price(prices.get("usd")),
            "usd_foil": parse_price(prices.get("usd_foil")),
            "usd_etched": parse_price(prices.get("usd_etched")),
            "eur": parse_price(prices.get("eur")),
            "eur_foil": parse_price(prices.get("eur_foil")),
            "tix": parse_price(prices.get("tix")),
            # Semantic fields
            "keywords": card_data.get("keywords", []),
            "flavor_text": card_data.get("flavor_text"),
            "edhrec_rank": card_data.get("edhrec_rank"),
            "reserved": card_data.get("reserved", False),
        }

    async def get_bulk_data_url(self, data_type: str = "default_cards") -> str:
        """Fetch the current bulk data download URL from Scryfall."""
        async with httpx.AsyncClient(headers=self.headers) as client:
            response = await client.get(SCRYFALL_BULK_API)
            response.raise_for_status()
            data = response.json()

        for item in data.get("data", []):
            if item.get("type") == data_type:
                return item["download_uri"]

        raise ValueError(f"Bulk data type '{data_type}' not found")

    async def download_bulk_file(self, url: str, dest_path: Path) -> None:
        """Download bulk data file with streaming."""
        async with httpx.AsyncClient(headers=self.headers, timeout=600.0) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

    def stream_cards_sync(self, file_path: Path):
        """Synchronously stream parse cards from bulk JSON file."""
        with open(file_path, "rb") as f:
            parser = ijson.items(f, "item")
            for card in parser:
                yield card

    async def import_prices(
        self,
        db: AsyncSession,
        progress_callback: Optional[Callable[[dict[str, int]], None]] = None
    ) -> dict[str, int]:
        """
        Download and import all prices from Scryfall bulk data.

        Returns dict with counts: cards_updated, snapshots_created, errors
        """
        stats = {"cards_updated": 0, "snapshots_created": 0, "errors": 0}

        # Get bulk data URL
        url = await self.get_bulk_data_url()
        logger.info(f"Downloading bulk data from {url}")

        # Download to temp file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            await self.download_bulk_file(url, tmp_path)
            logger.info(f"Downloaded to {tmp_path}")

            # Get marketplace IDs
            tcgplayer = await self._get_or_create_marketplace(db, "tcgplayer", "TCGPlayer")
            cardmarket = await self._get_or_create_marketplace(db, "cardmarket", "Cardmarket")

            now = datetime.now(timezone.utc)
            batch_size = 500
            batch: list[dict[str, Any]] = []

            # Process cards synchronously (ijson doesn't support async)
            loop = asyncio.get_event_loop()
            cards_gen = await loop.run_in_executor(
                None, lambda: list(self.stream_cards_sync(tmp_path))
            )

            for card_data in cards_gen:
                try:
                    parsed = self.parse_scryfall_prices(card_data)

                    # Update card semantic fields
                    await self._update_card_fields(db, parsed)
                    stats["cards_updated"] += 1

                    # Create price snapshots
                    snapshots = self._create_snapshots(parsed, now, tcgplayer.id, cardmarket.id)
                    batch.extend(snapshots)

                    if len(batch) >= batch_size:
                        await self._insert_snapshots(db, batch)
                        stats["snapshots_created"] += len(batch)
                        batch = []

                        if progress_callback:
                            progress_callback(stats)

                except Exception as e:
                    # Rollback to recover from database errors
                    await db.rollback()
                    logger.warning(f"Error processing card: {e}")
                    stats["errors"] += 1

            # Insert remaining batch
            if batch:
                await self._insert_snapshots(db, batch)
                stats["snapshots_created"] += len(batch)

            await db.commit()

        finally:
            tmp_path.unlink(missing_ok=True)

        return stats

    async def _get_or_create_marketplace(
        self, db: AsyncSession, slug: str, name: str
    ) -> Marketplace:
        """Get or create a marketplace by slug."""
        result = await db.execute(
            select(Marketplace).where(Marketplace.slug == slug)
        )
        marketplace = result.scalar_one_or_none()

        if not marketplace:
            marketplace = Marketplace(
                slug=slug,
                name=name,
                base_url=f"https://{slug}.com",
                is_enabled=True,
            )
            db.add(marketplace)
            await db.flush()

        return marketplace

    async def _update_card_fields(self, db: AsyncSession, parsed: dict) -> None:
        """Update card with semantic fields from Scryfall."""
        if not parsed.get("scryfall_id"):
            return

        await db.execute(
            update(Card)
            .where(Card.scryfall_id == parsed["scryfall_id"])
            .values(
                keywords=json.dumps(parsed.get("keywords", [])),
                flavor_text=parsed.get("flavor_text"),
                edhrec_rank=parsed.get("edhrec_rank"),
                reserved_list=parsed.get("reserved", False),
            )
        )

    def _create_snapshots(
        self,
        parsed: dict,
        timestamp: datetime,
        tcgplayer_id: int,
        cardmarket_id: int
    ) -> list[dict[str, Any]]:
        """Create snapshot dicts for insertion."""
        snapshots: list[dict[str, Any]] = []
        scryfall_id = parsed.get("scryfall_id")

        if not scryfall_id:
            return snapshots

        # USD (TCGPlayer) - Non-foil
        if parsed.get("usd"):
            snapshots.append({
                "scryfall_id": scryfall_id,
                "marketplace_id": tcgplayer_id,
                "time": timestamp,
                "price": parsed["usd"],
                "currency": "USD",
                "condition": "NEAR_MINT",
                "is_foil": False,
                "source": "bulk",
            })

        # USD Foil (TCGPlayer)
        if parsed.get("usd_foil"):
            snapshots.append({
                "scryfall_id": scryfall_id,
                "marketplace_id": tcgplayer_id,
                "time": timestamp,
                "price": parsed["usd_foil"],
                "currency": "USD",
                "condition": "NEAR_MINT",
                "is_foil": True,
                "source": "bulk",
            })

        # EUR (Cardmarket) - Non-foil
        if parsed.get("eur"):
            snapshots.append({
                "scryfall_id": scryfall_id,
                "marketplace_id": cardmarket_id,
                "time": timestamp,
                "price": parsed["eur"],
                "currency": "EUR",
                "condition": "NEAR_MINT",
                "is_foil": False,
                "source": "bulk",
            })

        # EUR Foil (Cardmarket)
        if parsed.get("eur_foil"):
            snapshots.append({
                "scryfall_id": scryfall_id,
                "marketplace_id": cardmarket_id,
                "time": timestamp,
                "price": parsed["eur_foil"],
                "currency": "EUR",
                "condition": "NEAR_MINT",
                "is_foil": True,
                "source": "bulk",
            })

        return snapshots

    async def _insert_snapshots(self, db: AsyncSession, snapshots: list[dict]) -> None:
        """Bulk insert snapshots, joining on card_id."""
        if not snapshots:
            return

        # Get card IDs for scryfall_ids
        scryfall_ids = list(set(s["scryfall_id"] for s in snapshots))
        result = await db.execute(
            select(Card.id, Card.scryfall_id).where(Card.scryfall_id.in_(scryfall_ids))
        )
        id_map = {row.scryfall_id: row.id for row in result}

        # Build insert values
        values = []
        for s in snapshots:
            card_id = id_map.get(s["scryfall_id"])
            if card_id:
                values.append({
                    "card_id": card_id,
                    "marketplace_id": s["marketplace_id"],
                    "time": s["time"],
                    "price": s["price"],
                    "currency": s["currency"],
                    "condition": s["condition"],
                    "is_foil": s["is_foil"],
                    "source": s["source"],
                    "language": "English",
                })

        if values:
            stmt = insert(PriceSnapshot).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["time", "card_id", "marketplace_id", "condition", "is_foil", "language"],
                set_={
                    "price": stmt.excluded.price,
                    "source": stmt.excluded.source,
                }
            )
            await db.execute(stmt)

    async def import_prices_with_copy(
        self,
        pool,  # asyncpg.Pool
        db: AsyncSession,
        progress_callback: Optional[Callable[[dict[str, int]], None]] = None
    ) -> dict[str, int]:
        """
        Import prices using PostgreSQL COPY for maximum speed.

        COPY is 10-50x faster than batch INSERT for large datasets.
        Use this for initial imports or large backfills.

        Args:
            pool: asyncpg connection pool (not SQLAlchemy)
            db: SQLAlchemy session for marketplace/card lookups
            progress_callback: Optional callback for progress updates

        Returns:
            dict with counts: cards_updated, snapshots_created, errors
        """
        from app.services.ingestion.bulk_ops import bulk_copy_snapshots, COPY_COLUMNS

        stats = {"cards_updated": 0, "snapshots_created": 0, "errors": 0, "batches": 0}

        # Get bulk data URL
        url = await self.get_bulk_data_url()
        logger.info(f"Downloading bulk data from {url}")

        # Download to temp file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            await self.download_bulk_file(url, tmp_path)
            logger.info(f"Downloaded to {tmp_path}")

            # Get marketplace IDs
            tcgplayer = await self._get_or_create_marketplace(db, "tcgplayer", "TCGPlayer")
            cardmarket = await self._get_or_create_marketplace(db, "cardmarket", "Cardmarket")
            await db.commit()

            # Build scryfall_id -> card_id lookup
            result = await db.execute(select(Card.id, Card.scryfall_id))
            card_lookup = {row.scryfall_id: row.id for row in result}

            now = datetime.now(timezone.utc)
            batch_size = 10000  # Larger batches for COPY
            records: list[tuple] = []

            # Process cards synchronously (ijson doesn't support async)
            loop = asyncio.get_event_loop()
            cards_gen = await loop.run_in_executor(
                None, lambda: list(self.stream_cards_sync(tmp_path))
            )

            for card_data in cards_gen:
                try:
                    parsed = self.parse_scryfall_prices(card_data)
                    scryfall_id = parsed.get("scryfall_id")
                    card_id = card_lookup.get(scryfall_id)

                    if not card_id:
                        continue

                    # Create COPY records (tuples in COPY_COLUMNS order)
                    copy_records = self._create_copy_records(
                        parsed, now, card_id, tcgplayer.id, cardmarket.id
                    )
                    records.extend(copy_records)
                    stats["cards_updated"] += 1

                    if len(records) >= batch_size:
                        async with pool.acquire() as conn:
                            count = await bulk_copy_snapshots(conn, records, COPY_COLUMNS)
                            stats["snapshots_created"] += count
                            stats["batches"] += 1
                        records = []

                        if progress_callback:
                            progress_callback(stats)

                except Exception as e:
                    logger.warning(f"Error processing card: {e}")
                    stats["errors"] += 1

            # Insert remaining records
            if records:
                async with pool.acquire() as conn:
                    count = await bulk_copy_snapshots(conn, records, COPY_COLUMNS)
                    stats["snapshots_created"] += count
                    stats["batches"] += 1

        finally:
            tmp_path.unlink(missing_ok=True)

        return stats

    def _create_copy_records(
        self,
        parsed: dict,
        timestamp: datetime,
        card_id: int,
        tcgplayer_id: int,
        cardmarket_id: int
    ) -> list[tuple]:
        """Create tuple records for COPY in COPY_COLUMNS order."""
        from app.services.ingestion.bulk_ops import prepare_copy_record

        records = []

        # USD (TCGPlayer) - Non-foil
        if parsed.get("usd"):
            records.append(prepare_copy_record(
                card_id=card_id,
                marketplace_id=tcgplayer_id,
                price=parsed["usd"],
                time=timestamp,
                condition=CardCondition.NEAR_MINT.value,
                is_foil=False,
                language=CardLanguage.ENGLISH.value,
                currency="USD",
                source="bulk",
            ))

        # USD Foil (TCGPlayer)
        if parsed.get("usd_foil"):
            records.append(prepare_copy_record(
                card_id=card_id,
                marketplace_id=tcgplayer_id,
                price=parsed["usd_foil"],
                time=timestamp,
                condition=CardCondition.NEAR_MINT.value,
                is_foil=True,
                language=CardLanguage.ENGLISH.value,
                currency="USD",
                source="bulk",
            ))

        # EUR (Cardmarket) - Non-foil
        if parsed.get("eur"):
            records.append(prepare_copy_record(
                card_id=card_id,
                marketplace_id=cardmarket_id,
                price=parsed["eur"],
                time=timestamp,
                condition=CardCondition.NEAR_MINT.value,
                is_foil=False,
                language=CardLanguage.ENGLISH.value,
                currency="EUR",
                source="bulk",
            ))

        # EUR Foil (Cardmarket)
        if parsed.get("eur_foil"):
            records.append(prepare_copy_record(
                card_id=card_id,
                marketplace_id=cardmarket_id,
                price=parsed["eur_foil"],
                time=timestamp,
                condition=CardCondition.NEAR_MINT.value,
                is_foil=True,
                language=CardLanguage.ENGLISH.value,
                currency="EUR",
                source="bulk",
            ))

        return records
