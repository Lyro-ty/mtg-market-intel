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
from app.models import Card, Marketplace, Listing, PriceSnapshot
from app.services.ingestion import get_adapter, get_all_adapters, ScryfallAdapter
from app.services.agents.normalization import NormalizationService

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
            
            # Get sample cards to scrape (top cards by activity or all)
            cards_query = select(Card).limit(500)  # Process 500 cards per run
            result = await db.execute(cards_query)
            cards = result.scalars().all()
            
            results = {
                "started_at": datetime.utcnow().isoformat(),
                "marketplaces": {},
                "total_listings": 0,
                "total_snapshots": 0,
                "errors": [],
            }
            
            normalizer = NormalizationService(db)
            
            for marketplace in marketplaces:
                try:
                    adapter = get_adapter(marketplace.slug, cached=True)
                    mp_results = await _scrape_marketplace(
                        db, adapter, marketplace, cards, normalizer
                    )
                    results["marketplaces"][marketplace.slug] = mp_results
                    results["total_listings"] += mp_results.get("listings", 0)
                    results["total_snapshots"] += mp_results.get("snapshots", 0)
                except Exception as e:
                    error_msg = f"{marketplace.slug}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error("Marketplace scrape failed", marketplace=marketplace.slug, error=str(e))
            
            await db.commit()
            results["completed_at"] = datetime.utcnow().isoformat()
            
            logger.info("Marketplace scrape completed", results=results)
            return results
    finally:
        await engine.dispose()


async def _scrape_marketplace(
    db: AsyncSession,
    adapter,
    marketplace: Marketplace,
    cards: list[Card],
    normalizer: NormalizationService,
) -> dict[str, Any]:
    """Scrape data from a single marketplace."""
    listings_created = 0
    snapshots_created = 0
    
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
                limit=20,
            )
            
            for listing_data in listings:
                # Update or create listing
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
                
        except Exception as e:
            logger.warning(
                "Failed to scrape card",
                card_name=card.name,
                marketplace=marketplace.slug,
                error=str(e),
            )
    
    return {
        "listings": listings_created,
        "snapshots": snapshots_created,
        "cards_processed": len(cards),
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
            
            adapter = get_adapter(marketplace_slug)
            normalizer = NormalizationService(db)
            
            results = await _scrape_marketplace(db, adapter, marketplace, cards, normalizer)
            await db.commit()
            
            return {
                "marketplace": marketplace_slug,
                **results,
            }
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

