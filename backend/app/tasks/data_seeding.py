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
import httpx
import json

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


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def download_scryfall_bulk_data_task(self) -> dict[str, Any]:
    """
    Download and process Scryfall bulk data files.
    
    Scryfall provides bulk data downloads that include all cards with prices.
    This task downloads the bulk data and extracts price information.
    
    Returns:
        Summary of processing results.
    """
    return run_async(_download_scryfall_bulk_data_async())


async def _download_scryfall_bulk_data_async() -> dict[str, Any]:
    """
    Download Scryfall bulk data and extract prices.
    
    Process:
    1. Get bulk data manifest from Scryfall
    2. Find default_cards or all_cards file
    3. Download and process each card
    4. Extract prices and create price snapshots
    """
    logger.info("Starting Scryfall bulk data download")
    
    BULK_DATA_URL = "https://api.scryfall.com/bulk-data"
    results = {
        "cards_processed": 0,
        "snapshots_created": 0,
        "errors": [],
    }
    
    session_maker, engine = create_task_session_maker()
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Get manifest
            logger.info("Fetching Scryfall bulk data manifest")
            response = await client.get(BULK_DATA_URL)
            response.raise_for_status()
            manifest = response.json()
            
            # Find default_cards or all_cards file
            target_file = None
            for file_info in manifest.get("data", []):
                if file_info.get("type") in ["default_cards", "all_cards"]:
                    target_file = file_info
                    break
            
            if not target_file:
                logger.warning("No default_cards or all_cards file found in manifest")
                return results
            
            download_uri = target_file.get("download_uri")
            if not download_uri:
                logger.warning("No download URI found for bulk data file")
                return results
            
            logger.info(
                "Found bulk data file",
                type=target_file.get("type"),
                size_mb=target_file.get("size") / (1024 * 1024) if target_file.get("size") else None,
                updated_at=target_file.get("updated_at"),
            )
            
            # Download file (this can be very large, so we stream it)
            # NOTE: For very large files (100MB+), consider using a streaming JSON parser
            # For now, we accumulate the entire file in memory which works for most cases
            logger.info("Downloading bulk data file", uri=download_uri)
            async with client.stream("GET", download_uri) as response:
                response.raise_for_status()
                
                # Accumulate file content
                buffer = b""
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    buffer += chunk
                
                # Parse the complete file
                # TODO: For very large files, consider using ijson for streaming JSON parsing
                # to avoid loading entire file into memory
                try:
                    cards_data = json.loads(buffer.decode("utf-8"))
                    logger.info("Parsed bulk data file", total_cards=len(cards_data))
                except json.JSONDecodeError as e:
                    logger.error("Failed to parse bulk data JSON", error=str(e))
                    return results
                except MemoryError as e:
                    logger.error("Insufficient memory to parse bulk data file", error=str(e))
                    results["errors"].append("File too large to process in memory. Consider using streaming parser.")
                    return results
            
            # Process cards
            async with session_maker() as db:
                # Get or create marketplaces
                marketplace_map = {
                    "usd": ("tcgplayer", "TCGPlayer", "USD"),
                    "eur": ("cardmarket", "Cardmarket", "EUR"),
                    "tix": ("mtgo", "MTGO", "TIX"),
                }
                
                marketplaces = {}
                for price_key, (slug, name, currency) in marketplace_map.items():
                    marketplace = await db.scalar(
                        select(Marketplace).where(Marketplace.slug == slug).limit(1)
                    )
                    if not marketplace:
                        marketplace = Marketplace(
                            name=name,
                            slug=slug,
                            base_url=f"https://{slug}.com",
                            default_currency=currency,
                            is_enabled=True,
                            supports_api=True,
                        )
                        db.add(marketplace)
                        await db.flush()
                    marketplaces[price_key] = marketplace
                
                # Process each card
                processed = 0
                snapshots_created = 0
                for card_data in cards_data:
                    try:
                        # process_bulk_card returns number of snapshots created
                        snapshots = await process_bulk_card(card_data, db, marketplaces)
                        if snapshots > 0:
                            snapshots_created += snapshots
                        processed += 1
                        results["cards_processed"] = processed
                        results["snapshots_created"] = snapshots_created
                        
                        # Commit in batches to avoid memory issues
                        if processed % 1000 == 0:
                            await db.commit()
                            logger.debug("Processed cards batch", count=processed, snapshots=snapshots_created)
                    
                    except Exception as e:
                        error_msg = f"Card {card_data.get('name', 'unknown')}: {str(e)}"
                        results["errors"].append(error_msg)
                        logger.warning("Failed to process bulk card", error=str(e))
                        continue
                
                await db.commit()
                logger.info("Completed bulk data processing", processed=processed, snapshots=snapshots_created)
        
    except Exception as e:
        logger.error("Scryfall bulk data download failed", error=str(e))
        results["errors"].append(f"Download failed: {str(e)}")
    finally:
        await engine.dispose()
    
    return results


async def process_bulk_card(
    card_data: dict[str, Any],
    db: AsyncSession,
    marketplaces: dict[str, Marketplace],
) -> int:
    """
    Extract prices from Scryfall bulk card data and create price snapshots.
    
    Args:
        card_data: Card data from Scryfall bulk file
        db: Database session
        marketplaces: Dictionary mapping price keys to Marketplace objects
    
    Returns:
        Number of snapshots created
    """
    # Get or create card
    scryfall_id = card_data.get("id")
    if not scryfall_id:
        return 0
    
    card = await db.scalar(
        select(Card).where(Card.scryfall_id == scryfall_id).limit(1)
    )
    
    if not card:
        # Card doesn't exist in our database, skip it
        # (We only process cards we're already tracking)
        return 0
    
    # Extract prices
    prices = card_data.get("prices", {})
    if not prices:
        return 0
    
    snapshots_created = 0
    
    # Get updated_at timestamp from card data
    updated_at_str = card_data.get("updated_at")
    snapshot_time = datetime.utcnow()
    if updated_at_str:
        try:
            # Scryfall timestamps are ISO format
            snapshot_time = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
        except Exception:
            pass
    
    # Process each price type
    for price_key, (slug, name, currency) in [
        ("usd", ("tcgplayer", "TCGPlayer", "USD")),
        ("eur", ("cardmarket", "Cardmarket", "EUR")),
        ("tix", ("mtgo", "MTGO", "TIX")),
    ]:
        price_value = prices.get(price_key)
        if price_value and float(price_value) > 0:
            marketplace = marketplaces.get(price_key)
            if not marketplace:
                continue
            
            # Check if snapshot already exists (within 24 hours)
            existing = await db.scalar(
                select(PriceSnapshot).where(
                    PriceSnapshot.card_id == card.id,
                    PriceSnapshot.marketplace_id == marketplace.id,
                    PriceSnapshot.snapshot_time >= snapshot_time - timedelta(hours=24),
                ).limit(1)
            )
            
            if not existing:
                # Get foil price if available
                foil_key = f"{price_key}_foil"
                price_foil = prices.get(foil_key)
                price_foil_float = float(price_foil) if price_foil and float(price_foil) > 0 else None
                
                snapshot = PriceSnapshot(
                    card_id=card.id,
                    marketplace_id=marketplace.id,
                    snapshot_time=snapshot_time,
                    price=float(price_value),
                    currency=currency,
                    price_foil=price_foil_float,
                )
                db.add(snapshot)
                snapshots_created += 1
    
    return snapshots_created


async def _seed_comprehensive_price_data_async() -> dict[str, Any]:
    """
    Async implementation of comprehensive price data seeding.
    
    Workflow:
    1. Collect Scryfall card names (get all cards from database - cards are sourced from Scryfall)
    2. Match MTGJSON card names to Scryfall card names (by name, set_code, collector_number)
    3. Generate 30-day history using MTGJSON data
    4. Collect current prices from CardTrader (if API token available)
    5. Store all data in database
    
    This ensures:
    - All cards have current prices from Scryfall (TCGPlayer, Cardmarket, MTGO)
    - All cards have 30-day historical data from MTGJSON where available
    - Cards have current prices from CardTrader (European market) if configured
    """
    from datetime import timezone
    
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
                "started_at": datetime.now(timezone.utc).isoformat(),
                "total_cards": len(all_cards),
                "current_snapshots": 0,
                "historical_snapshots": 0,
                "cardtrader_snapshots": 0,
                "cards_processed": 0,
                "errors": [],
            }
            
            # Helper to get or create marketplace (shared across phases)
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
            
            # Phase 2: Pull current prices from Scryfall (broken down by marketplace)
            # Cards are already in database from Scryfall, now we get their current prices
            scryfall = ScryfallAdapter()
            try:
                logger.info("Phase 2: Collecting current prices from Scryfall for all cards", cards=len(all_cards))
                
                for i, card in enumerate(all_cards):
                    try:
                        # Fetch all marketplace prices from Scryfall (TCGPlayer, Cardmarket, etc.)
                        all_prices = await scryfall.fetch_all_marketplace_prices(
                            card_name=card.name,
                            set_code=card.set_code,
                            collector_number=card.collector_number,
                            scryfall_id=card.scryfall_id,
                        )
                        
                        now = datetime.now(timezone.utc)
                        
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
            
            # Phase 3: Match MTGJSON card names to Scryfall cards and pull 30-day historical data
            # MTGJSON matches cards by name, set_code, and collector_number
            mtgjson = MTGJSONAdapter()
            try:
                logger.info("Phase 3: Matching MTGJSON cards to Scryfall cards and collecting 30-day historical prices")
                
                # Process cards in batches to avoid memory issues
                batch_size = 50
                for batch_start in range(0, len(all_cards), batch_size):
                    batch = all_cards[batch_start:batch_start + batch_size]
                    
                    for card in batch:
                        try:
                            # Match MTGJSON card by name, set_code, and collector_number
                            # MTGJSON provides ~90 days of weekly data, but we focus on 30 days for startup
                            historical_prices = await mtgjson.fetch_price_history(
                                card_name=card.name,
                                set_code=card.set_code,
                                collector_number=card.collector_number,
                                scryfall_id=card.scryfall_id,
                                days=30,  # Focus on 30-day history for startup seeding
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
                            
                            # Check how many days of data we have for this card
                            now = datetime.now(timezone.utc)
                            thirty_days_ago = now - timedelta(days=30)
                            history_check_query = select(func.count(PriceSnapshot.id)).where(
                                PriceSnapshot.card_id == card.id,
                                PriceSnapshot.snapshot_time >= thirty_days_ago,
                            )
                            history_count = await db.scalar(history_check_query) or 0
                            
                            # If we have less than 10 data points, backfill
                            if history_count < 10:
                                # Get most recent snapshot as base
                                recent_query = select(PriceSnapshot).where(
                                    PriceSnapshot.card_id == card.id,
                                    PriceSnapshot.snapshot_time >= now - timedelta(hours=48),
                                ).order_by(PriceSnapshot.snapshot_time.desc()).limit(1)
                                recent_result = await db.execute(recent_query)
                                recent_snapshot = recent_result.scalar_one_or_none()
                                
                                # NOTE: Synthetic backfilling has been disabled per CHARTING_ANALYSIS.md recommendations.
                                # Synthetic data creates artificial patterns that contaminate charts and ML training data.
                                # Instead, we use interpolation in chart endpoints to fill gaps (see market.py and inventory.py).
                                # If historical data is needed, use real sources like Scryfall bulk data or MTGJSON.
                                #
                                # if recent_snapshot:
                                #     import hashlib
                                #     base_price = float(recent_snapshot.price)
                                #     base_currency = recent_snapshot.currency
                                #     base_foil_price = float(recent_snapshot.price_foil) if recent_snapshot.price_foil else None
                                #     
                                #     backfilled = 0
                                #     for day_offset in range(30, 0, -1):
                                #         snapshot_date = now - timedelta(days=day_offset)
                                #         
                                #         # Check if data exists for this day
                                #         # Use count to avoid MultipleResultsFound error if multiple snapshots exist
                                #         existing_query = select(func.count(PriceSnapshot.id)).where(
                                #             PriceSnapshot.card_id == card.id,
                                #             PriceSnapshot.marketplace_id == recent_snapshot.marketplace_id,
                                #             PriceSnapshot.snapshot_time >= snapshot_date - timedelta(hours=12),
                                #             PriceSnapshot.snapshot_time <= snapshot_date + timedelta(hours=12),
                                #         )
                                #         existing_count = await db.scalar(existing_query) or 0
                                #         if existing_count > 0:
                                #             continue
                                #         
                                #         # Generate deterministic price
                                #         seed = f"{card.id}_{recent_snapshot.marketplace_id}_{day_offset}"
                                #         hash_value = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
                                #         variation = ((hash_value % 600) / 10000.0) - 0.03
                                #         trend_factor = 1.0 - (day_offset * 0.001)
                                #         historical_price = base_price * trend_factor * (1 + variation)
                                #         historical_price = max(0.01, historical_price)
                                #         
                                #         historical_foil_price = None
                                #         if base_foil_price:
                                #             foil_seed = f"{card.id}_{recent_snapshot.marketplace_id}_foil_{day_offset}"
                                #             foil_hash = int(hashlib.md5(foil_seed.encode()).hexdigest()[:8], 16)
                                #             foil_variation = ((foil_hash % 600) / 10000.0) - 0.03
                                #             historical_foil_price = base_foil_price * trend_factor * (1 + foil_variation)
                                #             historical_foil_price = max(0.01, historical_foil_price)
                                #         
                                #         snapshot = PriceSnapshot(
                                #             card_id=card.id,
                                #             marketplace_id=recent_snapshot.marketplace_id,
                                #             snapshot_time=snapshot_date,
                                #             price=historical_price,
                                #             currency=base_currency,
                                #             price_foil=historical_foil_price,
                                #         )
                                #         db.add(snapshot)
                                #         backfilled += 1
                                #         results["historical_snapshots"] += 1
                                #     
                                #     if backfilled > 0:
                                #         logger.debug(
                                #             "Backfilled historical data for card",
                                #             card_id=card.id,
                                #             backfilled=backfilled,
                                #         )
                        
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
            
            # Phase 4: Collect current prices from CardTrader (if API token available)
            # Note: CardTrader doesn't provide historical data, only current prices
            if settings.cardtrader_api_token:
                from app.services.ingestion import get_adapter
                cardtrader = get_adapter("cardtrader", cached=False)
                try:
                    logger.info("Phase 4: Collecting current prices from CardTrader", cards=len(all_cards))
                    
                    # Get or create CardTrader marketplace
                    cardtrader_mp = await get_or_create_marketplace(
                        "cardtrader", "CardTrader", "https://www.cardtrader.com", "EUR"
                    )
                    
                    now = datetime.now(timezone.utc)
                    
                    for card in all_cards:
                        try:
                            # Fetch current price from CardTrader
                            price_data = await cardtrader.fetch_price(
                                card_name=card.name,
                                set_code=card.set_code,
                                collector_number=card.collector_number,
                                scryfall_id=card.scryfall_id,
                            )
                            
                            if price_data and price_data.price > 0:
                                # Check if we already have a recent snapshot (within last 24 hours)
                                recent_snapshot_query = select(PriceSnapshot).where(
                                    and_(
                                        PriceSnapshot.card_id == card.id,
                                        PriceSnapshot.marketplace_id == cardtrader_mp.id,
                                        PriceSnapshot.snapshot_time >= now - timedelta(hours=24),
                                    )
                                )
                                recent_result = await db.execute(recent_snapshot_query)
                                recent_snapshot = recent_result.scalar_one_or_none()
                                
                                if not recent_snapshot:
                                    # Create price snapshot
                                    snapshot = PriceSnapshot(
                                        card_id=card.id,
                                        marketplace_id=cardtrader_mp.id,
                                        snapshot_time=now,
                                        price=price_data.price,
                                        currency=price_data.currency,
                                        price_foil=price_data.price_foil,
                                        min_price=price_data.price_low,
                                        max_price=price_data.price_high,
                                        num_listings=price_data.num_listings,
                                    )
                                    db.add(snapshot)
                                    results["cardtrader_snapshots"] += 1
                                    
                                    # Flush periodically
                                    if results["cardtrader_snapshots"] % 100 == 0:
                                        await db.flush()
                        
                        except Exception as e:
                            error_msg = f"CardTrader card {card.id} ({card.name}): {str(e)}"
                            results["errors"].append(error_msg)
                            logger.warning("Failed to fetch CardTrader price", card_id=card.id, error=str(e))
                            continue
                    
                    await db.flush()
                    logger.info("Phase 4 complete: CardTrader prices collected", snapshots=results["cardtrader_snapshots"])
                
                finally:
                    await cardtrader.close()
            else:
                logger.info("Phase 4: Skipping CardTrader (API token not configured)")
            
            # Phase 5: Commit all changes
            await db.commit()
            
            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            results["total_snapshots"] = (
                results["current_snapshots"] + 
                results["historical_snapshots"] + 
                results.get("cardtrader_snapshots", 0)
            )
            
            logger.info(
                "Comprehensive price data seeding completed",
                cards_processed=results["cards_processed"],
                current_snapshots=results["current_snapshots"],
                historical_snapshots=results["historical_snapshots"],
                cardtrader_snapshots=results.get("cardtrader_snapshots", 0),
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

