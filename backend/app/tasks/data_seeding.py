"""
Comprehensive data seeding task for startup and periodic updates.

This task:
1. Pulls current prices for ALL cards from Scryfall
2. Pulls historical data (30d/90d/6m/1y) from MTGJSON
3. Combines and stores in database
4. Ensures data quality for ML training and dashboard charts
"""
import asyncio
from datetime import datetime, timedelta
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
from app.models import Card, Marketplace, PriceSnapshot
from app.services.ingestion import ScryfallAdapter
from app.services.ingestion.adapters.mtgjson import MTGJSONAdapter

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


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def seed_comprehensive_price_data(self) -> dict[str, Any]:
    """
    Comprehensive price data seeding for startup and periodic updates.
    
    This task:
    1. Pulls current prices for ALL cards from Scryfall
    2. Pulls historical data (30d/90d/6m/1y) from MTGJSON
    3. Combines and stores in database
    4. Ensures data is ready for dashboard charts and ML training
    
    Returns:
        Summary of seeding results.
    """
    return run_async(_seed_comprehensive_price_data_async())


async def _seed_comprehensive_price_data_async() -> dict[str, Any]:
    """
    Async implementation of comprehensive price data seeding.
    
    Strategy:
    - Phase 1: Get all cards from database
    - Phase 2: Pull current prices from Scryfall (all cards)
    - Phase 3: Pull historical data from MTGJSON (30d/90d/6m/1y)
    - Phase 4: Combine and store in database
    - Phase 5: Ensure data quality for charts and ML
    """
    logger.info("Starting comprehensive price data seeding")
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Note: We no longer use a single "Scryfall" or "MTGJSON" marketplace
            # Instead, prices are stored by actual marketplace (TCGPlayer, Cardmarket, etc.)
            
            # Phase 1: Get ALL cards from database
            cards_query = select(Card)
            result = await db.execute(cards_query)
            all_cards = list(result.scalars().all())
            
            logger.info("Found cards for seeding", total_cards=len(all_cards))
            
            if not all_cards:
                logger.warning("No cards found in database - skipping seeding")
                return {
                    "status": "no_cards",
                    "cards_processed": 0,
                    "current_snapshots": 0,
                    "historical_snapshots": 0,
                }
            
            results = {
                "started_at": datetime.utcnow().isoformat(),
                "total_cards": len(all_cards),
                "current_snapshots": 0,
                "historical_snapshots": 0,
                "cards_processed": 0,
                "errors": [],
            }
            
            # Phase 2: Pull current prices from Scryfall (broken down by marketplace)
            scryfall = ScryfallAdapter()
            try:
                logger.info("Phase 2: Pulling current prices from Scryfall", cards=len(all_cards))
                
                # Helper to get or create marketplace
                async def get_or_create_marketplace(slug: str, name: str, base_url: str, currency: str) -> Marketplace:
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
                
                for i, card in enumerate(all_cards):
                    try:
                        # Fetch all marketplace prices from Scryfall (TCGPlayer, Cardmarket, etc.)
                        all_prices = await scryfall.fetch_all_marketplace_prices(
                            card_name=card.name,
                            set_code=card.set_code,
                            collector_number=card.collector_number,
                            scryfall_id=card.scryfall_id,
                        )
                        
                        now = datetime.utcnow()
                        
                        for price_data in all_prices:
                            if not price_data or price_data.price <= 0:
                                continue
                            
                            # Map currency to marketplace
                            marketplace_map = {
                                "USD": ("tcgplayer", "TCGPlayer", "https://www.tcgplayer.com"),
                                "EUR": ("cardmarket", "Cardmarket", "https://www.cardmarket.com"),
                                "TIX": ("mtgo", "MTGO", "https://www.mtgo.com"),
                            }
                            
                            slug, name, base_url = marketplace_map.get(price_data.currency, (None, None, None))
                            if not slug:
                                continue
                            
                            # Get or create marketplace
                            marketplace = await get_or_create_marketplace(slug, name, base_url, price_data.currency)
                            
                            # Check if we already have a recent snapshot (within last 24 hours)
                            # Scryfall only updates prices once per day, so we cache for 24 hours
                            # to avoid unnecessary API calls and respect rate limits
                            recent_snapshot_query = select(PriceSnapshot).where(
                                and_(
                                    PriceSnapshot.card_id == card.id,
                                    PriceSnapshot.marketplace_id == marketplace.id,
                                    PriceSnapshot.snapshot_time >= now - timedelta(hours=24),
                                )
                            )
                            recent_result = await db.execute(recent_snapshot_query)
                            recent_snapshot = recent_result.scalar_one_or_none()
                            
                            if not recent_snapshot:
                                # Create new price snapshot
                                snapshot = PriceSnapshot(
                                    card_id=card.id,
                                    marketplace_id=marketplace.id,
                                    snapshot_time=now,
                                    price=price_data.price,
                                    currency=price_data.currency,
                                    price_foil=price_data.price_foil,
                                )
                                db.add(snapshot)
                                results["current_snapshots"] += 1
                        
                        results["cards_processed"] += 1
                        
                        # Flush periodically to avoid memory issues
                        if results["cards_processed"] % 100 == 0:
                            await db.flush()
                            logger.debug(
                                "Current price collection progress",
                                processed=results["cards_processed"],
                                snapshots=results["current_snapshots"],
                            )
                        
                        # Rate limiting is handled by ScryfallAdapter (75ms default)
                        # No need for manual sleep here
                    
                    except Exception as e:
                        error_msg = f"Card {card.id} ({card.name}): {str(e)}"
                        results["errors"].append(error_msg)
                        logger.warning("Failed to fetch Scryfall price", card_id=card.id, error=str(e))
                        continue
                
                await db.flush()
                logger.info("Phase 2 complete: Current prices collected", snapshots=results["current_snapshots"])
            
            finally:
                await scryfall.close()
            
            # Phase 3: Pull historical data from MTGJSON (by marketplace)
            mtgjson = MTGJSONAdapter()
            try:
                logger.info("Phase 3: Pulling historical prices from MTGJSON")
                
                # Helper to get or create marketplace (reuse from Phase 2)
                async def get_or_create_marketplace(slug: str, name: str, base_url: str, currency: str) -> Marketplace:
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
                
                # Process cards in batches to avoid memory issues
                batch_size = 50
                for batch_start in range(0, len(all_cards), batch_size):
                    batch = all_cards[batch_start:batch_start + batch_size]
                    
                    for card in batch:
                        try:
                            # Fetch historical prices for multiple time ranges
                            # MTGJSON provides ~90 days of weekly data, so we'll get what's available
                            historical_prices = await mtgjson.fetch_price_history(
                                card_name=card.name,
                                set_code=card.set_code,
                                collector_number=card.collector_number,
                                scryfall_id=card.scryfall_id,
                                days=365,  # Get as much as possible (MTGJSON has ~90 days)
                            )
                            
                            if historical_prices:
                                for price_data in historical_prices:
                                    if not price_data or price_data.price <= 0:
                                        continue
                                    
                                    # Map currency to marketplace (same as Scryfall)
                                    marketplace_map = {
                                        "USD": ("tcgplayer", "TCGPlayer", "https://www.tcgplayer.com"),
                                        "EUR": ("cardmarket", "Cardmarket", "https://www.cardmarket.com"),
                                    }
                                    
                                    slug, name, base_url = marketplace_map.get(price_data.currency, (None, None, None))
                                    if not slug:
                                        continue
                                    
                                    # Get or create marketplace
                                    marketplace = await get_or_create_marketplace(slug, name, base_url, price_data.currency)
                                    
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
                                    
                                    if not existing:
                                        snapshot = PriceSnapshot(
                                            card_id=card.id,
                                            marketplace_id=marketplace.id,
                                            snapshot_time=price_data.snapshot_time,
                                            price=price_data.price,
                                            currency=price_data.currency,
                                            price_foil=price_data.price_foil,
                                        )
                                        db.add(snapshot)
                                        results["historical_snapshots"] += 1
                            
                            # Flush periodically
                            if results["historical_snapshots"] % 100 == 0:
                                await db.flush()
                                logger.debug(
                                    "Historical price collection progress",
                                    processed=len(batch),
                                    snapshots=results["historical_snapshots"],
                                )
                        
                        except Exception as e:
                            error_msg = f"Card {card.id} ({card.name}): {str(e)}"
                            results["errors"].append(error_msg)
                            logger.warning("Failed to fetch MTGJSON history", card_id=card.id, error=str(e))
                            continue
                    
                    # Flush batch
                    await db.flush()
                    logger.info(
                        "Historical batch complete",
                        batch_start=batch_start,
                        batch_size=len(batch),
                        total_snapshots=results["historical_snapshots"],
                    )
                
                logger.info("Phase 3 complete: Historical prices collected", snapshots=results["historical_snapshots"])
            
            finally:
                await mtgjson.close()
            
            # Phase 4: Commit all changes
            await db.commit()
            
            results["completed_at"] = datetime.utcnow().isoformat()
            results["total_snapshots"] = results["current_snapshots"] + results["historical_snapshots"]
            
            logger.info(
                "Comprehensive price data seeding completed",
                cards_processed=results["cards_processed"],
                current_snapshots=results["current_snapshots"],
                historical_snapshots=results["historical_snapshots"],
                total_snapshots=results["total_snapshots"],
                errors_count=len(results["errors"]),
            )
            
            return results
    
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
            rate_limit_seconds=0.1,
        )
        db.add(mp)
        await db.flush()
    
    return mp


async def _get_or_create_mtgjson_marketplace(db: AsyncSession) -> Marketplace:
    """Get or create MTGJSON marketplace entry."""
    query = select(Marketplace).where(Marketplace.slug == "mtgjson")
    result = await db.execute(query)
    mp = result.scalar_one_or_none()
    
    if not mp:
        mp = Marketplace(
            name="MTGJSON",
            slug="mtgjson",
            base_url="https://mtgjson.com",
            api_url="https://mtgjson.com",
            is_enabled=True,
            supports_api=True,
            default_currency="USD",
            rate_limit_seconds=1.0,
        )
        db.add(mp)
        await db.flush()
    
    return mp

