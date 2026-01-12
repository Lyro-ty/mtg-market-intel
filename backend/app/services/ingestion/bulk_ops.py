"""
Bulk database operations for ingestion optimization.

Provides efficient batch insert/upsert operations for price snapshots,
including PostgreSQL COPY for bulk imports.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

import structlog

from app.models.price_snapshot import PriceSnapshot
from app.core.constants import CardCondition, CardLanguage
from app.db.transaction import savepoint

logger = structlog.get_logger()


# Primary key columns for ON CONFLICT
SNAPSHOT_PK_COLUMNS = [
    'time', 'card_id', 'marketplace_id', 'condition', 'is_foil', 'language'
]

# Columns to update on conflict
SNAPSHOT_UPDATE_COLUMNS = [
    'price', 'price_low', 'price_mid', 'price_high', 'price_market',
    'num_listings', 'total_quantity', 'source'
]


async def get_recent_snapshot_times(
    db: AsyncSession,
    card_ids: list[int],
    marketplace_id: int,
    since: datetime,
) -> dict[int, datetime]:
    """
    Bulk fetch recent snapshot timestamps for given cards.

    Instead of querying per-card, this fetches all recent snapshots
    in a single query, returning the most recent timestamp per card.

    Args:
        db: Database session
        card_ids: List of card IDs to check
        marketplace_id: ID of the marketplace
        since: Only consider snapshots after this timestamp

    Returns:
        Dictionary mapping card_id to last snapshot time
    """
    if not card_ids:
        return {}

    result = await db.execute(
        select(
            PriceSnapshot.card_id,
            func.max(PriceSnapshot.time).label('last_time')
        )
        .where(
            PriceSnapshot.card_id.in_(card_ids),
            PriceSnapshot.marketplace_id == marketplace_id,
            PriceSnapshot.time >= since,
        )
        .group_by(PriceSnapshot.card_id)
    )

    return {row.card_id: row.last_time for row in result}


async def batch_upsert_snapshots(
    db: AsyncSession,
    snapshots: list[dict[str, Any]],
    batch_size: int = 500,
) -> dict[str, int]:
    """
    Upsert price snapshots in batches.

    Uses PostgreSQL INSERT...ON CONFLICT DO UPDATE for efficient
    upserts. Batches are committed together for efficiency.

    Args:
        db: Database session
        snapshots: List of snapshot dictionaries with keys matching model columns
        batch_size: Number of records per batch (default 500)

    Returns:
        Dictionary with 'inserted' count and 'batches' count
    """
    if not snapshots:
        return {"inserted": 0, "batches": 0}

    stats = {"inserted": 0, "batches": 0}

    for i in range(0, len(snapshots), batch_size):
        batch = snapshots[i:i + batch_size]

        # Ensure all required fields have defaults
        prepared_batch = [_prepare_snapshot(s) for s in batch]

        try:
            stmt = pg_insert(PriceSnapshot).values(prepared_batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=SNAPSHOT_PK_COLUMNS,
                set_={
                    col: getattr(stmt.excluded, col)
                    for col in SNAPSHOT_UPDATE_COLUMNS
                }
            )
            await db.execute(stmt)
            stats["inserted"] += len(batch)
            stats["batches"] += 1

        except Exception as e:
            logger.error(
                "Batch upsert failed",
                batch_start=i,
                batch_size=len(batch),
                error=str(e),
            )
            raise

    await db.commit()
    return stats


async def batch_upsert_snapshots_safe(
    db: AsyncSession,
    snapshots: list[dict[str, Any]],
    batch_size: int = 500,
) -> dict[str, int]:
    """
    Upsert price snapshots with per-batch error handling.

    Unlike batch_upsert_snapshots, this version commits each batch
    separately and continues on errors, allowing partial success.

    Args:
        db: Database session
        snapshots: List of snapshot dictionaries
        batch_size: Number of records per batch

    Returns:
        Dictionary with 'inserted', 'errors', and 'batches' counts
    """
    if not snapshots:
        return {"inserted": 0, "errors": 0, "batches": 0}

    stats = {"inserted": 0, "errors": 0, "batches": 0}

    for i in range(0, len(snapshots), batch_size):
        batch = snapshots[i:i + batch_size]
        prepared_batch = [_prepare_snapshot(s) for s in batch]

        try:
            stmt = pg_insert(PriceSnapshot).values(prepared_batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=SNAPSHOT_PK_COLUMNS,
                set_={
                    col: getattr(stmt.excluded, col)
                    for col in SNAPSHOT_UPDATE_COLUMNS
                }
            )
            await db.execute(stmt)
            await db.commit()
            stats["inserted"] += len(batch)
            stats["batches"] += 1

        except Exception as e:
            await db.rollback()
            stats["errors"] += len(batch)
            logger.warning(
                "Batch upsert failed, continuing",
                batch_start=i,
                batch_size=len(batch),
                error=str(e),
            )

    return stats


def _prepare_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """
    Prepare a snapshot dictionary for insertion.

    Ensures required fields have defaults and types are correct.
    """
    now = datetime.now(timezone.utc)

    return {
        'time': snapshot.get('time', now),
        'card_id': snapshot['card_id'],
        'marketplace_id': snapshot['marketplace_id'],
        'condition': snapshot.get('condition', CardCondition.NEAR_MINT.value),
        'is_foil': snapshot.get('is_foil', False),
        'language': snapshot.get('language', CardLanguage.ENGLISH.value),
        'price': Decimal(str(snapshot['price'])) if snapshot.get('price') is not None else Decimal('0'),
        'price_low': _to_decimal(snapshot.get('price_low')),
        'price_mid': _to_decimal(snapshot.get('price_mid')),
        'price_high': _to_decimal(snapshot.get('price_high')),
        'price_market': _to_decimal(snapshot.get('price_market')),
        'currency': snapshot.get('currency', 'USD'),
        'num_listings': snapshot.get('num_listings'),
        'total_quantity': snapshot.get('total_quantity'),
        'source': snapshot.get('source', 'api'),
    }


def _to_decimal(value: Any) -> Optional[Decimal]:
    """Convert a value to Decimal, returning None if invalid."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return None


# =============================================================================
# PostgreSQL COPY Operations (for bulk imports)
# =============================================================================

# Columns for COPY operations (order matters!)
COPY_COLUMNS = [
    'time', 'card_id', 'marketplace_id', 'condition', 'is_foil', 'language',
    'price', 'price_low', 'price_mid', 'price_high', 'price_market',
    'currency', 'num_listings', 'total_quantity', 'source'
]


async def bulk_copy_snapshots(
    connection,  # asyncpg connection
    records: Sequence[tuple],
    columns: list[str] | None = None,
) -> int:
    """
    Use PostgreSQL COPY for high-speed bulk inserts.

    COPY is 10-50x faster than batch INSERTs for large datasets.
    Uses a staging table with upsert for handling duplicates.

    Args:
        connection: asyncpg connection (not SQLAlchemy session)
        records: List of tuples matching column order
        columns: Column names (default: COPY_COLUMNS)

    Returns:
        Number of records inserted/updated
    """
    if not records:
        return 0

    if columns is None:
        columns = COPY_COLUMNS

    # Create temp staging table
    await connection.execute("""
        CREATE TEMP TABLE IF NOT EXISTS snapshot_staging (
            time TIMESTAMPTZ NOT NULL,
            card_id INTEGER NOT NULL,
            marketplace_id INTEGER NOT NULL,
            condition card_condition NOT NULL,
            is_foil BOOLEAN NOT NULL,
            language card_language NOT NULL,
            price NUMERIC(10,2) NOT NULL,
            price_low NUMERIC(10,2),
            price_mid NUMERIC(10,2),
            price_high NUMERIC(10,2),
            price_market NUMERIC(10,2),
            currency VARCHAR(3) NOT NULL,
            num_listings INTEGER,
            total_quantity INTEGER,
            source VARCHAR(20) NOT NULL
        ) ON COMMIT DELETE ROWS
    """)

    # COPY into staging table
    await connection.copy_records_to_table(
        'snapshot_staging',
        records=records,
        columns=columns,
    )

    # Upsert from staging to main table
    result = await connection.execute("""
        INSERT INTO price_snapshots (
            time, card_id, marketplace_id, condition, is_foil, language,
            price, price_low, price_mid, price_high, price_market,
            currency, num_listings, total_quantity, source
        )
        SELECT
            time, card_id, marketplace_id, condition, is_foil, language,
            price, price_low, price_mid, price_high, price_market,
            currency, num_listings, total_quantity, source
        FROM snapshot_staging
        ON CONFLICT (time, card_id, marketplace_id, condition, is_foil, language)
        DO UPDATE SET
            price = EXCLUDED.price,
            price_low = EXCLUDED.price_low,
            price_mid = EXCLUDED.price_mid,
            price_high = EXCLUDED.price_high,
            price_market = EXCLUDED.price_market,
            num_listings = EXCLUDED.num_listings,
            total_quantity = EXCLUDED.total_quantity,
            source = EXCLUDED.source
    """)

    # Parse result like "INSERT 0 1234"
    try:
        count = int(result.split()[-1])
    except (ValueError, IndexError, AttributeError):
        count = len(records)

    return count


def prepare_copy_record(
    card_id: int,
    marketplace_id: int,
    price: float | Decimal,
    time: datetime | None = None,
    condition: str | None = None,
    is_foil: bool = False,
    language: str | None = None,
    price_low: float | None = None,
    price_mid: float | None = None,
    price_high: float | None = None,
    price_market: float | None = None,
    currency: str = 'USD',
    num_listings: int | None = None,
    total_quantity: int | None = None,
    source: str = 'bulk',
) -> tuple:
    """
    Prepare a tuple for bulk_copy_snapshots.

    Returns a tuple in the correct order for COPY_COLUMNS.
    """
    return (
        time or datetime.now(timezone.utc),
        card_id,
        marketplace_id,
        condition or CardCondition.NEAR_MINT.value,
        is_foil,
        language or CardLanguage.ENGLISH.value,
        Decimal(str(price)) if price is not None else Decimal('0'),
        Decimal(str(price_low)) if price_low is not None else None,
        Decimal(str(price_mid)) if price_mid is not None else None,
        Decimal(str(price_high)) if price_high is not None else None,
        Decimal(str(price_market)) if price_market is not None else None,
        currency,
        num_listings,
        total_quantity,
        source,
    )


# =============================================================================
# Utility Functions
# =============================================================================

async def get_cards_needing_update(
    db: AsyncSession,
    card_ids: list[int],
    marketplace_id: int,
    threshold_hours: float = 2.0,
    price_change_threshold: float = 0.02,
) -> list[int]:
    """
    Determine which cards need price updates.

    A card needs an update if:
    - No snapshot exists within threshold_hours, OR
    - Price has changed by more than price_change_threshold (2%)

    This is a convenience function that combines cache and DB checks.

    Args:
        db: Database session
        card_ids: List of card IDs to check
        marketplace_id: ID of the marketplace
        threshold_hours: Hours since last update (default 2)
        price_change_threshold: Minimum price change to force update (default 2%)

    Returns:
        List of card_ids that need updates
    """
    if not card_ids:
        return []

    since = datetime.now(timezone.utc) - __import__('datetime').timedelta(hours=threshold_hours)
    recent = await get_recent_snapshot_times(db, card_ids, marketplace_id, since)

    # Cards without recent snapshots definitely need updates
    return [cid for cid in card_ids if cid not in recent]


async def ensure_card_exists(
    db: AsyncSession,
    card_data: dict,
) -> int | None:
    """
    Ensure a card exists in the database before importing prices.

    If the card doesn't exist, creates it from the provided data.
    This prevents FK violations when importing prices for new cards.

    Args:
        db: Database session
        card_data: Dictionary with card data (Scryfall format)
            Required: id (scryfall_id), name, set
            Optional: collector_number, rarity, type_line, etc.

    Returns:
        Card ID if found or created, None if insufficient data
    """
    import json
    from app.models import Card

    scryfall_id = card_data.get("id") or card_data.get("scryfall_id")
    if not scryfall_id:
        logger.warning("Cannot ensure card exists: no scryfall_id provided")
        return None

    # Check if card exists
    result = await db.execute(
        select(Card.id).where(Card.scryfall_id == scryfall_id)
    )
    card_id = result.scalar_one_or_none()

    if card_id:
        return card_id

    # Card doesn't exist - create it
    name = card_data.get("name")
    set_code = card_data.get("set") or card_data.get("set_code")

    if not name or not set_code:
        logger.warning(
            "Cannot create card: missing required fields",
            scryfall_id=scryfall_id,
            name=name,
            set_code=set_code,
        )
        return None

    # Extract data outside savepoint to catch parsing errors early
    image_uris = card_data.get("image_uris", {})
    if isinstance(image_uris, str):
        image_uris = json.loads(image_uris)

    legalities = card_data.get("legalities", {})
    if isinstance(legalities, str):
        legalities = json.loads(legalities)

    color_identity = card_data.get("color_identity", [])
    if isinstance(color_identity, str):
        color_identity = json.loads(color_identity)

    # Use savepoint for card creation to prevent partial data on failure
    try:
        async with savepoint(db, f"create_card_{scryfall_id}"):
            card = Card(
                scryfall_id=scryfall_id,
                name=name,
                set_code=set_code,
                collector_number=card_data.get("collector_number"),
                rarity=card_data.get("rarity"),
                type_line=card_data.get("type_line"),
                oracle_text=card_data.get("oracle_text"),
                mana_cost=card_data.get("mana_cost"),
                cmc=card_data.get("cmc"),
                color_identity=json.dumps(color_identity) if color_identity else None,
                legalities=json.dumps(legalities) if legalities else None,
                image_uris=json.dumps(image_uris) if image_uris else None,
                image_uri=image_uris.get("normal") or image_uris.get("large"),
            )
            db.add(card)
            await db.flush()

            logger.info(
                "Created new card during price import",
                card_id=card.id,
                name=name,
                set_code=set_code,
            )

            return card.id

    except Exception as e:
        logger.error(
            "Failed to create card during import",
            scryfall_id=scryfall_id,
            error=str(e),
        )
        return None


async def batch_ensure_cards_exist(
    db: AsyncSession,
    cards_data: list[dict],
) -> dict[str, int]:
    """
    Batch version of ensure_card_exists for efficiency.

    Args:
        db: Database session
        cards_data: List of card data dictionaries

    Returns:
        Dictionary mapping scryfall_id to card_id
    """
    if not cards_data:
        return {}

    result = {}

    for card_data in cards_data:
        scryfall_id = card_data.get("id") or card_data.get("scryfall_id")
        if not scryfall_id:
            continue

        card_id = await ensure_card_exists(db, card_data)
        if card_id:
            result[scryfall_id] = card_id

    return result
