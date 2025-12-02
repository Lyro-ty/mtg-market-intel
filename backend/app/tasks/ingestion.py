"""
Ingestion tasks for marketplace data collection.
"""
import asyncio
from datetime import datetime
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models import Card, Marketplace, Listing, PriceSnapshot, InventoryItem
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
def scrape_all_marketplaces(self) -> dict[str, Any]:
    """
    Scrape data from all enabled marketplaces.
    
    Returns:
        Summary of scraping results.
    """
    return run_async(_scrape_all_marketplaces_async())


async def _scrape_all_marketplaces_async() -> dict[str, Any]:
    """Async implementation of marketplace scraping."""
    logger.info("Starting marketplace scrape")
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Get enabled marketplaces
            query = select(Marketplace).where(Marketplace.is_enabled == True)
            result = await db.execute(query)
            marketplaces = result.scalars().all()
            
            if not marketplaces:
                logger.warning("No enabled marketplaces found")
                return {"status": "no_marketplaces", "scraped": 0}
            
            # PRIORITY 1: Get all cards in user's inventory (always scrape these)
            inventory_cards_query = (
                select(Card)
                .join(InventoryItem, InventoryItem.card_id == Card.id)
                .distinct()
            )
            result = await db.execute(inventory_cards_query)
            inventory_cards = list(result.scalars().all())
            inventory_card_ids = {c.id for c in inventory_cards}
            
            logger.info("Scraping inventory cards first", count=len(inventory_cards))
            
            # PRIORITY 2: Fill remaining slots with other cards (up to 2000 total - increased from 500)
            remaining_slots = max(0, 2000 - len(inventory_cards))
            if remaining_slots > 0:
                other_cards_query = (
                    select(Card)
                    .where(Card.id.notin_(inventory_card_ids) if inventory_card_ids else True)
                    .limit(remaining_slots)
                )
                result = await db.execute(other_cards_query)
                other_cards = list(result.scalars().all())
            else:
                other_cards = []
            
            # Combine: inventory cards first, then others
            cards = inventory_cards + other_cards
            logger.info(
                "Total cards to scrape",
                inventory=len(inventory_cards),
                other=len(other_cards),
                total=len(cards),
                marketplaces=len(marketplaces),
            )
            
            results = {
                "started_at": datetime.utcnow().isoformat(),
                "marketplaces": {},
                "total_listings": 0,
                "total_snapshots": 0,
                "total_vectors": 0,
                "errors": [],
            }
            
            normalizer = NormalizationService(db)
            vectorizer = get_vectorization_service()  # Use cached instance
            
            try:
                for marketplace in marketplaces:
                    # Create fresh adapter for each marketplace (don't cache across event loops)
                    adapter = get_adapter(marketplace.slug, cached=False)
                    try:
                        logger.info(
                            "Starting marketplace scrape",
                            marketplace=marketplace.slug,
                            cards_count=len(cards),
                        )
                        mp_results = await _scrape_marketplace(
                            db, adapter, marketplace, cards, normalizer, vectorizer
                        )
                        results["marketplaces"][marketplace.slug] = mp_results
                        results["total_listings"] += mp_results.get("listings", 0)
                        results["total_snapshots"] += mp_results.get("snapshots", 0)
                        results["total_vectors"] += mp_results.get("vectors_created", 0)
                        
                        logger.info(
                            "Marketplace scrape completed",
                            marketplace=marketplace.slug,
                            listings=mp_results.get("listings", 0),
                            snapshots=mp_results.get("snapshots", 0),
                            cards_processed=mp_results.get("cards_processed", 0),
                        )
                    except Exception as e:
                        error_msg = f"{marketplace.slug}: {str(e)}"
                        results["errors"].append(error_msg)
                        logger.error("Marketplace scrape failed", marketplace=marketplace.slug, error=str(e), exc_info=True)
                    finally:
                        # Always close adapter to release HTTP client resources
                        if hasattr(adapter, 'close'):
                            await adapter.close()
                
                await db.commit()
                results["completed_at"] = datetime.utcnow().isoformat()
                
                logger.info(
                    "Marketplace scrape completed",
                    total_listings=results["total_listings"],
                    total_snapshots=results["total_snapshots"],
                    total_vectors=results["total_vectors"],
                    errors_count=len(results["errors"]),
                )
                return results
            finally:
                # Always close normalizer to release resources
                await normalizer.close()
                # Don't close cached vectorizer - it's shared across requests
    finally:
        await engine.dispose()


async def _scrape_marketplace(
    db: AsyncSession,
    adapter,
    marketplace: Marketplace,
    cards: list[Card],
    normalizer: NormalizationService,
    vectorizer: VectorizationService | None = None,
) -> dict[str, Any]:
    """Scrape data from a single marketplace."""
    listings_created = 0
    listings_updated = 0
    snapshots_created = 0
    vectors_created = 0
    cards_with_listings = 0
    cards_without_listings = 0
    
    for card in cards:
        try:
            # Fetch price data
            price_data = await adapter.fetch_price(
                card_name=card.name,
                set_code=card.set_code,
                collector_number=card.collector_number,
                scryfall_id=card.scryfall_id,
            )
            
            if price_data and price_data.price > 0:
                # Create price snapshot
                snapshot = PriceSnapshot(
                    card_id=card.id,
                    marketplace_id=marketplace.id,
                    snapshot_time=datetime.utcnow(),
                    price=price_data.price,
                    currency=price_data.currency,
                    price_foil=price_data.price_foil,
                    min_price=price_data.price_low,
                    max_price=price_data.price_high,
                    avg_price=price_data.price_mid,
                    median_price=price_data.price_market,
                    num_listings=price_data.num_listings,
                    total_quantity=price_data.total_quantity,
                )
                db.add(snapshot)
                snapshots_created += 1
            
            # Fetch individual listings if supported
            listings = await adapter.fetch_listings(
                card_name=card.name,
                set_code=card.set_code,
                scryfall_id=card.scryfall_id,
                limit=100,  # Increased from 20 to get more listings
            )
            
            if len(listings) > 0:
                cards_with_listings += 1
                logger.debug(
                    "Fetched listings from adapter",
                    card_id=card.id,
                    card_name=card.name,
                    marketplace=marketplace.slug,
                    listings_count=len(listings),
                )
            else:
                cards_without_listings += 1
            
            # Vectorize card if vectorizer is available (once per card)
            card_vector_obj = None
            if vectorizer:
                card_vector_obj = await vectorize_card(db, card, vectorizer)
                if card_vector_obj:
                    vectors_created += 1
                    await db.flush()
            
            for listing_data in listings:
                try:
                    # Check if listing already exists by external_id
                    existing = None
                    if listing_data.external_id:
                        existing_query = select(Listing).where(
                            Listing.external_id == listing_data.external_id,
                            Listing.marketplace_id == marketplace.id,
                        )
                        existing_result = await db.execute(existing_query)
                        existing = existing_result.scalar_one_or_none()
                    
                    if existing:
                        # Update existing listing
                        existing.condition = listing_data.condition
                        existing.language = listing_data.language
                        existing.is_foil = listing_data.is_foil
                        existing.price = listing_data.price
                        existing.currency = listing_data.currency
                        existing.quantity = listing_data.quantity
                        existing.seller_name = listing_data.seller_name
                        existing.seller_rating = listing_data.seller_rating
                        existing.listing_url = listing_data.listing_url
                        existing.last_seen_at = datetime.utcnow()
                        listings_updated += 1
                        # Don't increment created count for updates
                    else:
                        # Create new listing
                        listing = Listing(
                            card_id=card.id,
                            marketplace_id=marketplace.id,
                            condition=listing_data.condition,
                            language=listing_data.language,
                            is_foil=listing_data.is_foil,
                            price=listing_data.price,
                            currency=listing_data.currency,
                            quantity=listing_data.quantity,
                            seller_name=listing_data.seller_name,
                            seller_rating=listing_data.seller_rating,
                            external_id=listing_data.external_id,
                            listing_url=listing_data.listing_url,
                            last_seen_at=datetime.utcnow(),
                        )
                        db.add(listing)
                        listings_created += 1
                        
                        # Vectorize listing if vectorizer is available
                        if vectorizer:
                            listing_vector = await vectorize_listing(db, listing, card_vector_obj, vectorizer)
                            if listing_vector:
                                vectors_created += 1
                
                except Exception as listing_error:
                    logger.warning(
                        "Failed to save listing",
                        card_id=card.id,
                        card_name=card.name,
                        marketplace=marketplace.slug,
                        external_id=listing_data.external_id,
                        error=str(listing_error),
                    )
                    # Don't increment count if listing creation failed
                    continue
                
        except Exception as e:
            logger.warning(
                "Failed to scrape card",
                card_name=card.name,
                marketplace=marketplace.slug,
                error=str(e),
            )
    
    logger.info(
        "Marketplace scrape summary",
        marketplace=marketplace.slug,
        cards_processed=len(cards),
        cards_with_listings=cards_with_listings,
        cards_without_listings=cards_without_listings,
        listings_created=listings_created,
        listings_updated=listings_updated,
        snapshots_created=snapshots_created,
        vectors_created=vectors_created,
        success_rate=f"{(cards_with_listings / len(cards) * 100):.1f}%" if cards else "0%",
    )
    
    return {
        "listings": listings_created,
        "listings_updated": listings_updated,
        "snapshots": snapshots_created,
        "cards_processed": len(cards),
        "cards_with_listings": cards_with_listings,
        "cards_without_listings": cards_without_listings,
        "vectors_created": vectors_created,
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def scrape_marketplace(self, marketplace_slug: str, card_ids: list[int] | None = None) -> dict[str, Any]:
    """
    Scrape data from a specific marketplace.
    
    Args:
        marketplace_slug: Marketplace to scrape.
        card_ids: Optional list of card IDs to scrape. None = all.
        
    Returns:
        Scraping results.
    """
    return run_async(_scrape_marketplace_task_async(marketplace_slug, card_ids))


async def _scrape_marketplace_task_async(
    marketplace_slug: str,
    card_ids: list[int] | None,
) -> dict[str, Any]:
    """Async implementation of single marketplace scraping."""
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Get marketplace
            query = select(Marketplace).where(Marketplace.slug == marketplace_slug)
            result = await db.execute(query)
            marketplace = result.scalar_one_or_none()
            
            if not marketplace:
                return {"error": f"Marketplace not found: {marketplace_slug}"}
            
            # Get cards
            if card_ids:
                cards_query = select(Card).where(Card.id.in_(card_ids))
            else:
                cards_query = select(Card).limit(500)
            
            result = await db.execute(cards_query)
            cards = result.scalars().all()
            
            # Create fresh adapter (don't cache across event loops)
            adapter = get_adapter(marketplace_slug, cached=False)
            normalizer = NormalizationService(db)
            
            try:
                results = await _scrape_marketplace(db, adapter, marketplace, cards, normalizer)
                await db.commit()
                
                return {
                    "marketplace": marketplace_slug,
                    **results,
                }
            finally:
                # Always close adapter and normalizer to release HTTP client resources
                if hasattr(adapter, 'close'):
                    await adapter.close()
                await normalizer.close()
    finally:
        await engine.dispose()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_inventory_cards(self) -> dict[str, Any]:
    """
    Scrape price data for all cards in user's inventory.
    
    This is a faster, targeted scrape that only updates inventory cards.
    Useful for quick refreshes from the inventory page.
    
    Returns:
        Summary of scraping results.
    """
    return run_async(_scrape_inventory_cards_async())


async def _scrape_inventory_cards_async() -> dict[str, Any]:
    """Async implementation of inventory-only scraping."""
    logger.info("Starting inventory cards scrape")
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Get enabled marketplaces
            query = select(Marketplace).where(Marketplace.is_enabled == True)
            result = await db.execute(query)
            marketplaces = result.scalars().all()
            
            if not marketplaces:
                logger.warning("No enabled marketplaces found")
                return {"status": "no_marketplaces", "scraped": 0}
            
            # Get only cards that are in inventory
            inventory_cards_query = (
                select(Card)
                .join(InventoryItem, InventoryItem.card_id == Card.id)
                .distinct()
            )
            result = await db.execute(inventory_cards_query)
            cards = list(result.scalars().all())
            
            if not cards:
                logger.info("No inventory cards to scrape")
                return {"status": "no_inventory", "scraped": 0}
            
            logger.info("Scraping inventory cards", count=len(cards))
            
            results = {
                "started_at": datetime.utcnow().isoformat(),
                "inventory_cards": len(cards),
                "marketplaces": {},
                "total_listings": 0,
                "total_snapshots": 0,
                "errors": [],
            }
            
            normalizer = NormalizationService(db)
            vectorizer = get_vectorization_service()  # Use cached instance
            
            try:
                for marketplace in marketplaces:
                    adapter = get_adapter(marketplace.slug, cached=False)
                    try:
                        mp_results = await _scrape_marketplace(
                            db, adapter, marketplace, cards, normalizer, vectorizer
                        )
                        results["marketplaces"][marketplace.slug] = mp_results
                        results["total_listings"] += mp_results.get("listings", 0)
                        results["total_snapshots"] += mp_results.get("snapshots", 0)
                        results["total_vectors"] = results.get("total_vectors", 0) + mp_results.get("vectors_created", 0)
                    except Exception as e:
                        error_msg = f"{marketplace.slug}: {str(e)}"
                        results["errors"].append(error_msg)
                        logger.error("Marketplace scrape failed", marketplace=marketplace.slug, error=str(e))
                    finally:
                        if hasattr(adapter, 'close'):
                            await adapter.close()
                
                await db.commit()
                results["completed_at"] = datetime.utcnow().isoformat()
                
                logger.info("Inventory scrape completed", results=results)
                return results
            finally:
                await normalizer.close()
                # Don't close cached vectorizer - it's shared across requests
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

