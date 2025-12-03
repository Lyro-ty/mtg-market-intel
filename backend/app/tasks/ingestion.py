"""
Ingestion tasks for marketplace data collection.

Focus: Aggressive price data collection from Scryfall and MTGJSON.
No web scraping - using free, reliable APIs only.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models import Card, Marketplace, Listing, PriceSnapshot, InventoryItem, CardFeatureVector
from app.services.ingestion import get_adapter, get_all_adapters, ScryfallAdapter
from app.services.agents.normalization import NormalizationService
from app.services.vectorization import get_vectorization_service
from app.services.vectorization.service import VectorizationService
from app.services.vectorization.ingestion import vectorize_card, vectorize_listing

logger = structlog.get_logger()


def create_task_session_maker():
    """Create a new async engine and session maker for the current event loop."""
    engine = create_async_engine(
        settings.database_url_computed,
        echo=settings.api_debug,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    ), engine


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def collect_price_data(self) -> dict[str, Any]:
    """
    Aggressively collect price data from Scryfall and MTGJSON.
    
    This replaces the old scraping approach. Focuses on:
    - Scryfall: Real-time aggregated prices (TCGPlayer, Cardmarket)
    - MTGJSON: Historical price data
    
    Returns:
        Summary of price collection results.
    """
    return run_async(_collect_price_data_async())


async def _collect_price_data_async() -> dict[str, Any]:
    """
    Aggressively collect price data from Scryfall and MTGJSON.
    
    Strategy:
    - Scryfall: Real-time prices for all cards (prioritize inventory)
    - MTGJSON: Historical prices (run less frequently, daily)
    - Focus on price snapshots, not individual listings
    - Collect as much data as possible, as quickly as possible
    """
    logger.info("Starting aggressive price data collection")
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # PRIORITY 1: Get all cards in user's inventory (always collect these first)
            inventory_cards_query = (
                select(Card)
                .join(InventoryItem, InventoryItem.card_id == Card.id)
                .distinct()
            )
            result = await db.execute(inventory_cards_query)
            inventory_cards = list(result.scalars().all())
            inventory_card_ids = {c.id for c in inventory_cards}
            
            logger.info("Collecting prices for inventory cards first", count=len(inventory_cards))
            
            # PRIORITY 2: Get cards without recent data (within 24 hours) - prioritize these
            # Cards without data should be processed first to ensure all cards get data within 24 hours
            now = datetime.utcnow()
            stale_threshold = now - timedelta(hours=24)
            
            # Get cards that have no snapshots or only stale snapshots
            cards_without_data_query = (
                select(Card)
                .outerjoin(
                    PriceSnapshot,
                    and_(
                        PriceSnapshot.card_id == Card.id,
                        PriceSnapshot.snapshot_time >= stale_threshold
                    )
                )
                .where(
                    Card.id.notin_(inventory_card_ids) if inventory_card_ids else True,
                    PriceSnapshot.id.is_(None)  # No recent snapshots
                )
                .distinct()
            )
            result = await db.execute(cards_without_data_query)
            cards_without_data = list(result.scalars().all())
            
            # PRIORITY 3: Get all other cards (have recent data, but still refresh periodically)
            cards_with_data_ids = {c.id for c in cards_without_data}
            other_cards_query = (
                select(Card)
                .where(
                    Card.id.notin_(inventory_card_ids) if inventory_card_ids else True,
                    Card.id.notin_(cards_with_data_ids) if cards_with_data_ids else True
                )
            )
            result = await db.execute(other_cards_query)
            other_cards = list(result.scalars().all())
            
            # Combine: inventory cards first, then cards without data, then others
            cards = inventory_cards + cards_without_data + other_cards
            logger.info(
                "Total cards for price collection",
                inventory=len(inventory_cards),
                without_data=len(cards_without_data),
                with_data=len(other_cards),
                total=len(cards),
            )
            
            results = {
                "started_at": datetime.utcnow().isoformat(),
                "scryfall_snapshots": 0,
                "mtgjson_snapshots": 0,
                "total_snapshots": 0,
                "cards_processed": 0,
                "errors": [],
            }
            
            # Get or create Scryfall marketplace
            scryfall_mp = await _get_or_create_scryfall_marketplace(db)
            
            # Get Scryfall adapter
            scryfall = ScryfallAdapter()
            
            try:
                # Collect prices from Scryfall for all cards
                logger.info("Collecting Scryfall price data", card_count=len(cards))
                
                for i, card in enumerate(cards):
                    try:
                        # Fetch price data from Scryfall
                        price_data = await scryfall.fetch_price(
                            card_name=card.name,
                            set_code=card.set_code,
                            collector_number=card.collector_number,
                            scryfall_id=card.scryfall_id,
                        )
                        
                        if price_data and price_data.price > 0:
                            # Check if we already have a recent snapshot (within last 24 hours)
                            # Scryfall only updates prices once per day, so we cache for 24 hours
                            # to avoid unnecessary API calls and respect rate limits
                            from sqlalchemy import and_
                            recent_snapshot_query = select(PriceSnapshot).where(
                                and_(
                                    PriceSnapshot.card_id == card.id,
                                    PriceSnapshot.marketplace_id == scryfall_mp.id,
                                    PriceSnapshot.snapshot_time >= datetime.utcnow() - timedelta(hours=24),
                                )
                            )
                            recent_result = await db.execute(recent_snapshot_query)
                            recent_snapshot = recent_result.scalar_one_or_none()
                            
                            if not recent_snapshot:
                                # Create price snapshot
                                snapshot = PriceSnapshot(
                                    card_id=card.id,
                                    marketplace_id=scryfall_mp.id,
                                    snapshot_time=datetime.utcnow(),
                                    price=price_data.price,
                                    currency=price_data.currency,
                                    price_foil=price_data.price_foil,
                                )
                                db.add(snapshot)
                                results["scryfall_snapshots"] += 1
                                results["total_snapshots"] += 1
                            else:
                                # Update existing snapshot if price changed significantly
                                price_diff = abs(recent_snapshot.price - price_data.price)
                                price_change_pct = (price_diff / recent_snapshot.price * 100) if recent_snapshot.price > 0 else 0
                                
                                # Update if price changed by more than 5%
                                if price_change_pct > 5.0:
                                    recent_snapshot.price = price_data.price
                                    recent_snapshot.price_foil = price_data.price_foil
                                    recent_snapshot.snapshot_time = datetime.utcnow()
                                    results["scryfall_snapshots"] += 1
                        
                        results["cards_processed"] += 1
                        
                        # Flush periodically to avoid memory issues
                        if results["cards_processed"] % 100 == 0:
                            await db.flush()
                            logger.debug(
                                "Price collection progress",
                                processed=results["cards_processed"],
                                snapshots=results["total_snapshots"],
                            )
                    
                    except Exception as e:
                        error_msg = f"Card {card.id} ({card.name}): {str(e)}"
                        results["errors"].append(error_msg)
                        logger.warning("Failed to collect price for card", card_id=card.id, card_name=card.name, error=str(e))
                        continue
                
                await db.commit()
                results["completed_at"] = datetime.utcnow().isoformat()
                
                logger.info(
                    "Price data collection completed",
                    cards_processed=results["cards_processed"],
                    scryfall_snapshots=results["scryfall_snapshots"],
                    total_snapshots=results["total_snapshots"],
                    errors_count=len(results["errors"]),
                )
                
                return results
            finally:
                await scryfall.close()
    finally:
        await engine.dispose()


async def _get_or_create_scryfall_marketplace(db: AsyncSession) -> Marketplace:
    """Get or create Scryfall marketplace entry."""
    query = select(Marketplace).where(Marketplace.slug == "scryfall")
    result = await db.execute(query)
    mp = result.scalar_one_or_none()
    
    if not mp:
        mp = Marketplace(
            name="Scryfall",
            slug="scryfall",
            base_url="https://scryfall.com",
            api_url="https://api.scryfall.com",
            is_enabled=True,
            supports_api=True,
            default_currency="USD",
            rate_limit_seconds=0.1,  # Scryfall allows 50-100ms between requests
        )
        db.add(mp)
        await db.flush()
    
    return mp




@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def collect_inventory_prices(self) -> dict[str, Any]:
    """
    Aggressively collect price data for all cards in user's inventory.
    
    This prioritizes inventory cards and updates them frequently.
    Uses Scryfall for real-time price data.
    
    Returns:
        Summary of price collection results.
    """
    return run_async(_collect_inventory_prices_async())


async def _collect_inventory_prices_async() -> dict[str, Any]:
    """Async implementation of inventory-only price collection."""
    logger.info("Starting inventory cards price collection")
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Get only cards that are in inventory
            inventory_cards_query = (
                select(Card)
                .join(InventoryItem, InventoryItem.card_id == Card.id)
                .distinct()
            )
            result = await db.execute(inventory_cards_query)
            cards = list(result.scalars().all())
            
            if not cards:
                logger.info("No inventory cards to collect prices for")
                return {"status": "no_inventory", "snapshots": 0}
            
            logger.info("Collecting prices for inventory cards", count=len(cards))
            
            results = {
                "started_at": datetime.utcnow().isoformat(),
                "inventory_cards": len(cards),
                "snapshots_created": 0,
                "snapshots_updated": 0,
                "errors": [],
            }
            
            # Get or create Scryfall marketplace
            scryfall_mp = await _get_or_create_scryfall_marketplace(db)
            
            # Get Scryfall adapter
            scryfall = ScryfallAdapter()
            
            try:
                for card in cards:
                    try:
                        # Fetch price data from Scryfall
                        price_data = await scryfall.fetch_price(
                            card_name=card.name,
                            set_code=card.set_code,
                            collector_number=card.collector_number,
                            scryfall_id=card.scryfall_id,
                        )
                        
                        if price_data and price_data.price > 0:
                            # Check for recent snapshot (within last 24 hours)
                            # Scryfall only updates prices once per day, so we cache for 24 hours
                            # to avoid unnecessary API calls and respect rate limits
                            from sqlalchemy import and_
                            recent_snapshot_query = select(PriceSnapshot).where(
                                and_(
                                    PriceSnapshot.card_id == card.id,
                                    PriceSnapshot.marketplace_id == scryfall_mp.id,
                                    PriceSnapshot.snapshot_time >= datetime.utcnow() - timedelta(hours=24),
                                )
                            )
                            recent_result = await db.execute(recent_snapshot_query)
                            recent_snapshot = recent_result.scalar_one_or_none()
                            
                            if not recent_snapshot:
                                # Create new snapshot
                                snapshot = PriceSnapshot(
                                    card_id=card.id,
                                    marketplace_id=scryfall_mp.id,
                                    snapshot_time=datetime.utcnow(),
                                    price=price_data.price,
                                    currency=price_data.currency,
                                    price_foil=price_data.price_foil,
                                )
                                db.add(snapshot)
                                results["snapshots_created"] += 1
                            else:
                                # Always update inventory card prices (they change frequently)
                                recent_snapshot.price = price_data.price
                                recent_snapshot.price_foil = price_data.price_foil
                                recent_snapshot.snapshot_time = datetime.utcnow()
                                results["snapshots_updated"] += 1
                    
                    except Exception as e:
                        error_msg = f"Card {card.id} ({card.name}): {str(e)}"
                        results["errors"].append(error_msg)
                        logger.warning("Failed to collect price for inventory card", card_id=card.id, error=str(e))
                        continue
                
                await db.commit()
                results["completed_at"] = datetime.utcnow().isoformat()
                
                logger.info(
                    "Inventory price collection completed",
                    cards=len(cards),
                    snapshots_created=results["snapshots_created"],
                    snapshots_updated=results["snapshots_updated"],
                )
                
                return results
            finally:
                await scryfall.close()
    finally:
        await engine.dispose()


@shared_task(bind=True, max_retries=2, default_retry_delay=600)
def sync_card_catalog(self, set_codes: list[str] | None = None) -> dict[str, Any]:
    """
    Sync card catalog from Scryfall.
    
    Args:
        set_codes: Optional list of set codes to sync. None = recent sets.
        
    Returns:
        Sync results.
    """
    return run_async(_sync_card_catalog_async(set_codes))


async def _sync_card_catalog_async(set_codes: list[str] | None) -> dict[str, Any]:
    """Async implementation of card catalog sync."""
    logger.info("Starting card catalog sync")
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            normalizer = NormalizationService(db)
            
            # Default to recent popular sets if not specified
            if not set_codes:
                set_codes = [
                    "ONE", "MOM", "WOE", "LCI", "MKM",  # Recent Standard sets
                    "2XM", "2X2", "CLB",  # Recent special sets
                ]
            
            results = {
                "sets_synced": [],
                "total_cards": 0,
                "errors": [],
            }
            
            for set_code in set_codes:
                try:
                    count = await normalizer.sync_cards_from_set(set_code)
                    results["sets_synced"].append(set_code)
                    results["total_cards"] += count
                except Exception as e:
                    results["errors"].append(f"{set_code}: {str(e)}")
                    logger.error("Failed to sync set", set_code=set_code, error=str(e))
            
            await normalizer.close()
            
            logger.info("Card catalog sync completed", results=results)
            return results
    finally:
        await engine.dispose()


@shared_task(bind=True)
def sync_single_card(self, scryfall_id: str) -> dict[str, Any]:
    """
    Sync a single card from Scryfall.
    
    Args:
        scryfall_id: Scryfall card ID.
        
    Returns:
        Sync result.
    """
    return run_async(_sync_single_card_async(scryfall_id))


async def _sync_single_card_async(scryfall_id: str) -> dict[str, Any]:
    """Async implementation of single card sync."""
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            normalizer = NormalizationService(db)
            
            try:
                scryfall = ScryfallAdapter()
                card_data = await scryfall.fetch_card_by_id(scryfall_id)
                await scryfall.close()
                
                if not card_data:
                    return {"error": "Card not found on Scryfall"}
                
                card = await normalizer.create_card_from_scryfall(card_data)
                await db.commit()
                await normalizer.close()
                
                return {
                    "card_id": card.id,
                    "name": card.name,
                    "set_code": card.set_code,
                    "synced": True,
                }
            except Exception as e:
                return {"error": str(e)}
    finally:
        await engine.dispose()


@shared_task(bind=True, max_retries=2, default_retry_delay=600)
def import_mtgjson_historical_prices(
    self,
    card_ids: list[int] | None = None,
    days: int = 90,
) -> dict[str, Any]:
    """
    Import historical price data from MTGJSON.
    
    This supplements our real-time scrapers with historical price trends.
    MTGJSON provides weekly price intervals going back ~3 months.
    
    Args:
        card_ids: Optional list of card IDs to import. None = all cards.
        days: Number of days of history to import (max ~90 days).
        
    Returns:
        Import results.
    """
    return run_async(_import_mtgjson_historical_prices_async(card_ids, days))


async def _import_mtgjson_historical_prices_async(
    card_ids: list[int] | None,
    days: int,
) -> dict[str, Any]:
    """Async implementation of MTGJSON historical price import."""
    logger.info("Starting MTGJSON historical price import", days=days)
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Get or create MTGJSON marketplace
            mtgjson_query = select(Marketplace).where(Marketplace.slug == "mtgjson")
            result = await db.execute(mtgjson_query)
            mtgjson_marketplace = result.scalar_one_or_none()
            
            if not mtgjson_marketplace:
                # Create MTGJSON marketplace entry
                mtgjson_marketplace = Marketplace(
                    name="MTGJSON",
                    slug="mtgjson",
                    base_url="https://mtgjson.com",
                    api_url="https://mtgjson.com/api/v5",
                    is_enabled=True,
                    supports_api=True,
                    default_currency="USD",
                    rate_limit_seconds=1.0,
                )
                db.add(mtgjson_marketplace)
                await db.flush()
                logger.info("Created MTGJSON marketplace entry")
            
            # Get cards to import
            if card_ids:
                cards_query = select(Card).where(Card.id.in_(card_ids))
            else:
                # Prioritize inventory cards, then limit to 1000 for efficiency
                inventory_query = (
                    select(Card)
                    .join(InventoryItem, InventoryItem.card_id == Card.id)
                    .distinct()
                )
                result = await db.execute(inventory_query)
                inventory_cards = list(result.scalars().all())
                inventory_ids = {c.id for c in inventory_cards}
                
                # Get additional cards up to 1000 total
                remaining = max(0, 1000 - len(inventory_cards))
                if remaining > 0:
                    other_query = (
                        select(Card)
                        .where(Card.id.notin_(inventory_ids) if inventory_ids else True)
                        .limit(remaining)
                    )
                    result = await db.execute(other_query)
                    other_cards = list(result.scalars().all())
                else:
                    other_cards = []
                
                cards = inventory_cards + other_cards
                cards_query = select(Card).where(Card.id.in_([c.id for c in cards]))
            
            result = await db.execute(cards_query)
            cards = list(result.scalars().all())
            
            if not cards:
                logger.warning("No cards found to import MTGJSON prices for")
                return {"status": "no_cards", "imported": 0}
            
            logger.info("Importing MTGJSON prices", card_count=len(cards))
            
            # Get MTGJSON adapter
            from app.services.ingestion import get_adapter
            adapter = get_adapter("mtgjson", cached=False)
            
            results = {
                "started_at": datetime.utcnow().isoformat(),
                "cards_processed": 0,
                "snapshots_created": 0,
                "snapshots_skipped": 0,
                "errors": [],
            }
            
            try:
                for card in cards:
                    try:
                        # Fetch historical prices
                        historical_prices = await adapter.fetch_price_history(
                            card_name=card.name,
                            set_code=card.set_code,
                            collector_number=card.collector_number,
                            scryfall_id=card.scryfall_id,
                            days=days,
                        )
                        
                        if not historical_prices:
                            continue
                        
                        # Create price snapshots for each historical price
                        for price_data in historical_prices:
                            # Check if snapshot already exists for this timestamp
                            existing_query = select(PriceSnapshot).where(
                                PriceSnapshot.card_id == card.id,
                                PriceSnapshot.marketplace_id == mtgjson_marketplace.id,
                                PriceSnapshot.snapshot_time == price_data.snapshot_time,
                            )
                            existing_result = await db.execute(existing_query)
                            existing = existing_result.scalar_one_or_none()
                            
                            if existing:
                                # Update existing snapshot
                                existing.price = price_data.price
                                existing.currency = price_data.currency
                                existing.price_foil = price_data.price_foil
                                results["snapshots_skipped"] += 1
                            else:
                                # Create new snapshot
                                snapshot = PriceSnapshot(
                                    card_id=card.id,
                                    marketplace_id=mtgjson_marketplace.id,
                                    snapshot_time=price_data.snapshot_time,
                                    price=price_data.price,
                                    currency=price_data.currency,
                                    price_foil=price_data.price_foil,
                                )
                                db.add(snapshot)
                                results["snapshots_created"] += 1
                        
                        results["cards_processed"] += 1
                        
                        # Flush periodically to avoid memory issues
                        if results["cards_processed"] % 50 == 0:
                            await db.flush()
                            logger.debug(
                                "MTGJSON import progress",
                                processed=results["cards_processed"],
                                snapshots=results["snapshots_created"],
                            )
                    
                    except Exception as e:
                        error_msg = f"Card {card.id} ({card.name}): {str(e)}"
                        results["errors"].append(error_msg)
                        logger.warning(
                            "Failed to import MTGJSON prices for card",
                            card_id=card.id,
                            card_name=card.name,
                            error=str(e),
                        )
                        continue
                
                await db.commit()
                results["completed_at"] = datetime.utcnow().isoformat()
                
                logger.info(
                    "MTGJSON historical price import completed",
                    cards_processed=results["cards_processed"],
                    snapshots_created=results["snapshots_created"],
                    snapshots_skipped=results["snapshots_skipped"],
                    errors_count=len(results["errors"]),
                )
                
                return results
            finally:
                if hasattr(adapter, 'close'):
                    await adapter.close()
    finally:
        await engine.dispose()


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def bulk_vectorize_cards(
    self,
    card_ids: list[int] | None = None,
    batch_size: int = 100,
    prioritize_missing: bool = True,
) -> dict[str, Any]:
    """
    Bulk vectorize cards from Scryfall default card data.
    
    This task:
    1. Gets all cards (or specified cards)
    2. Prioritizes cards without vectors if prioritize_missing=True
    3. Vectorizes cards in batches
    4. Updates existing vectors if card data changed
    
    Args:
        card_ids: Optional list of card IDs to vectorize. None = all cards.
        batch_size: Number of cards to process per batch.
        prioritize_missing: If True, prioritize cards without vectors.
        
    Returns:
        Vectorization results.
    """
    return run_async(_bulk_vectorize_cards_async(card_ids, batch_size, prioritize_missing))


async def _bulk_vectorize_cards_async(
    card_ids: list[int] | None,
    batch_size: int,
    prioritize_missing: bool,
) -> dict[str, Any]:
    """Async implementation of bulk card vectorization."""
    logger.info(
        "Starting bulk card vectorization",
        batch_size=batch_size,
        prioritize_missing=prioritize_missing,
    )
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Get vectorization service (cached instance)
            vectorizer = get_vectorization_service()
            
            # Build query
            if card_ids:
                cards_query = select(Card).where(Card.id.in_(card_ids))
                result = await db.execute(cards_query)
                cards = list(result.scalars().all())
            elif prioritize_missing:
                # Get cards without vectors first, then all others
                from sqlalchemy import and_
                cards_without_vectors_query = (
                    select(Card)
                    .outerjoin(CardFeatureVector, Card.id == CardFeatureVector.card_id)
                    .where(CardFeatureVector.card_id.is_(None))
                )
                result = await db.execute(cards_without_vectors_query)
                cards_without_vectors = list(result.scalars().all())
                
                # Get cards with vectors (for potential updates)
                cards_with_vectors_query = (
                    select(Card)
                    .join(CardFeatureVector, Card.id == CardFeatureVector.card_id)
                )
                result = await db.execute(cards_with_vectors_query)
                cards_with_vectors = list(result.scalars().all())
                
                # Prioritize cards without vectors
                cards = cards_without_vectors + cards_with_vectors
            else:
                cards_query = select(Card)
                result = await db.execute(cards_query)
                cards = list(result.scalars().all())
            
            if not cards:
                logger.warning("No cards found to vectorize")
                return {
                    "status": "no_cards",
                    "vectors_created": 0,
                    "vectors_updated": 0,
                    "vectors_skipped": 0,
                }
            
            logger.info("Vectorizing cards", total_cards=len(cards))
            
            results = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "total_cards": len(cards),
                "vectors_created": 0,
                "vectors_updated": 0,
                "vectors_skipped": 0,
                "errors": [],
            }
            
            # Process in batches
            for batch_start in range(0, len(cards), batch_size):
                batch = cards[batch_start:batch_start + batch_size]
                
                for card in batch:
                    try:
                        # Check if vector exists
                        existing_query = select(CardFeatureVector).where(
                            CardFeatureVector.card_id == card.id
                        )
                        result = await db.execute(existing_query)
                        existing_vector = result.scalar_one_or_none()
                        
                        # Prepare card data for vectorization
                        card_data = {
                            "name": card.name,
                            "type_line": card.type_line,
                            "oracle_text": card.oracle_text,
                            "rarity": card.rarity,
                            "cmc": card.cmc,
                            "colors": json.loads(card.colors) if card.colors else None,
                            "mana_cost": card.mana_cost,
                        }
                        
                        # Vectorize
                        card_vector_obj = await vectorize_card(db, card, vectorizer)
                        
                        if card_vector_obj:
                            if existing_vector:
                                results["vectors_updated"] += 1
                            else:
                                results["vectors_created"] += 1
                        else:
                            results["vectors_skipped"] += 1
                        
                        # Commit every 10 batches to avoid long transactions
                        if (batch_start // batch_size + 1) % 10 == 0:
                            await db.commit()
                            logger.info(
                                "Vectorization progress",
                                processed=batch_start + len(batch),
                                total=len(cards),
                                created=results["vectors_created"],
                                updated=results["vectors_updated"],
                            )
                    
                    except Exception as e:
                        logger.warning(
                            "Failed to vectorize card",
                            card_id=card.id,
                            error=str(e),
                        )
                        results["errors"].append({"card_id": card.id, "error": str(e)})
                
                # Commit batch
                await db.commit()
            
            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(
                "Bulk vectorization complete",
                vectors_created=results["vectors_created"],
                vectors_updated=results["vectors_updated"],
                vectors_skipped=results["vectors_skipped"],
                errors=len(results["errors"]),
            )
            
            return results
    finally:
        await engine.dispose()

