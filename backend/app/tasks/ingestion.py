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
from sqlalchemy import select, and_, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import CardCondition, CardLanguage
from app.models import Card, Marketplace, PriceSnapshot, InventoryItem, CardFeatureVector
from app.services.ingestion import get_adapter, get_all_adapters, ScryfallAdapter
from app.services.ingestion.base import AdapterConfig
from app.services.agents.normalization import NormalizationService
from app.services.vectorization import get_vectorization_service
from app.services.vectorization.service import VectorizationService
from app.services.vectorization.ingestion import vectorize_card
from app.tasks.utils import create_task_session_maker, run_async

logger = structlog.get_logger()


async def _upsert_price_snapshot(
    db: AsyncSession,
    card_id: int,
    marketplace_id: int,
    time: datetime,
    price: float,
    currency: str,
    condition: CardCondition = CardCondition.NEAR_MINT,
    is_foil: bool = False,
    language: CardLanguage = CardLanguage.ENGLISH,
    price_low: float | None = None,
    price_mid: float | None = None,
    price_high: float | None = None,
    price_market: float | None = None,
    num_listings: int | None = None,
    total_quantity: int | None = None,
    source: str = "api",
) -> PriceSnapshot:
    """
    Upsert a price snapshot using PostgreSQL ON CONFLICT.

    This prevents race conditions where multiple tasks try to create the same snapshot.
    The composite primary key is (time, card_id, marketplace_id, condition, is_foil, language).

    Returns:
        The created or updated PriceSnapshot.
    """
    # Use PostgreSQL INSERT ... ON CONFLICT DO UPDATE
    values_dict = {
        'time': time,
        'card_id': card_id,
        'marketplace_id': marketplace_id,
        'condition': condition.value,
        'is_foil': is_foil,
        'language': language.value,
        'price': price,
        'currency': currency,
        'price_low': price_low,
        'price_mid': price_mid,
        'price_high': price_high,
        'price_market': price_market,
        'num_listings': num_listings,
        'total_quantity': total_quantity,
        'source': source,
    }

    stmt = pg_insert(PriceSnapshot).values(**values_dict)

    # On conflict with composite primary key, update the price fields
    update_dict = {
        'price': stmt.excluded.price,
        'currency': stmt.excluded.currency,
        'price_low': stmt.excluded.price_low,
        'price_mid': stmt.excluded.price_mid,
        'price_high': stmt.excluded.price_high,
        'price_market': stmt.excluded.price_market,
        'num_listings': stmt.excluded.num_listings,
        'total_quantity': stmt.excluded.total_quantity,
        'source': stmt.excluded.source,
    }

    # Use index_elements for composite primary key conflict
    stmt = stmt.on_conflict_do_update(
        index_elements=['time', 'card_id', 'marketplace_id', 'condition', 'is_foil', 'language'],
        set_=update_dict
    )

    await db.execute(stmt)
    await db.flush()

    # Fetch the snapshot to return it
    result = await db.execute(
        select(PriceSnapshot).where(
            and_(
                PriceSnapshot.time == time,
                PriceSnapshot.card_id == card_id,
                PriceSnapshot.marketplace_id == marketplace_id,
                PriceSnapshot.condition == condition.value,
                PriceSnapshot.is_foil == is_foil,
                PriceSnapshot.language == language.value,
            )
        )
    )
    return result.scalar_one()


async def _backfill_historical_snapshots_for_charting(
    db: AsyncSession,
    card_id: int,
    marketplace_id: int,
    current_price: float,
    current_currency: str,
    current_foil_price: float | None,
    snapshot_time: datetime,
    condition: CardCondition = CardCondition.NEAR_MINT,
    is_foil: bool = False,
    language: CardLanguage = CardLanguage.ENGLISH,
) -> int:
    """
    Create historical snapshots for instant charting when we first collect data for a card.

    This creates placeholder snapshots going back 90 days using the current price,
    so charts have data immediately. Real historical data from MTGJSON will replace these.

    Returns:
        Number of snapshots created.
    """
    # Check how many snapshots we have in the last 30 days
    thirty_days_ago = snapshot_time - timedelta(days=30)
    existing_count_30d = await db.scalar(
        select(func.count()).select_from(PriceSnapshot).where(
            and_(
                PriceSnapshot.card_id == card_id,
                PriceSnapshot.marketplace_id == marketplace_id,
                PriceSnapshot.time >= thirty_days_ago,
            )
        )
    ) or 0

    # Only backfill if we have fewer than 15 snapshots in the last 30 days
    # This ensures we create enough data points for 30-day charts
    if existing_count_30d >= 15:
        return 0

    # Create snapshots going back 90 days
    # Use bucket sizes that match chart ranges: daily for 7d/30d, every 3 days for 90d
    created = 0
    now = snapshot_time

    # For 7d range: create daily snapshots (7 snapshots)
    for day in range(7, 0, -1):
        snapshot_date = now - timedelta(days=day)
        # Check if snapshot already exists for this date (within 12 hours)
        existing = await db.scalar(
            select(func.count()).select_from(PriceSnapshot).where(
                and_(
                    PriceSnapshot.card_id == card_id,
                    PriceSnapshot.marketplace_id == marketplace_id,
                    PriceSnapshot.time >= snapshot_date - timedelta(hours=12),
                    PriceSnapshot.time <= snapshot_date + timedelta(hours=12),
                )
            )
        ) or 0

        if existing == 0:
            snapshot = PriceSnapshot(
                time=snapshot_date,
                card_id=card_id,
                marketplace_id=marketplace_id,
                condition=condition.value,
                is_foil=is_foil,
                language=language.value,
                price=current_price,
                currency=current_currency,
                price_market=current_foil_price,
            )
            db.add(snapshot)
            created += 1

    # For 30d range: create snapshots every 1-2 days to ensure good coverage
    # Create daily snapshots for days 8-30 (23 snapshots) to ensure comprehensive 30-day history
    for day in range(30, 7, -1):
        snapshot_date = now - timedelta(days=day)
        existing = await db.scalar(
            select(func.count()).select_from(PriceSnapshot).where(
                and_(
                    PriceSnapshot.card_id == card_id,
                    PriceSnapshot.marketplace_id == marketplace_id,
                    PriceSnapshot.time >= snapshot_date - timedelta(hours=12),
                    PriceSnapshot.time <= snapshot_date + timedelta(hours=12),
                )
            )
        ) or 0

        if existing == 0:
            snapshot = PriceSnapshot(
                time=snapshot_date,
                card_id=card_id,
                marketplace_id=marketplace_id,
                condition=condition.value,
                is_foil=is_foil,
                language=language.value,
                price=current_price,
                currency=current_currency,
                price_market=current_foil_price,
            )
            db.add(snapshot)
            created += 1

    # For 90d range: create snapshots every 5 days (12 more snapshots)
    for day in range(90, 30, -5):
        snapshot_date = now - timedelta(days=day)
        existing = await db.scalar(
            select(func.count()).select_from(PriceSnapshot).where(
                and_(
                    PriceSnapshot.card_id == card_id,
                    PriceSnapshot.marketplace_id == marketplace_id,
                    PriceSnapshot.time >= snapshot_date - timedelta(hours=12),
                    PriceSnapshot.time <= snapshot_date + timedelta(hours=12),
                )
            )
        ) or 0

        if existing == 0:
            snapshot = PriceSnapshot(
                time=snapshot_date,
                card_id=card_id,
                marketplace_id=marketplace_id,
                condition=condition.value,
                is_foil=is_foil,
                language=language.value,
                price=current_price,
                currency=current_currency,
                price_market=current_foil_price,
            )
            db.add(snapshot)
            created += 1

    if created > 0:
        await db.flush()
        logger.debug(
            "Created historical snapshots for instant charting",
            card_id=card_id,
            marketplace_id=marketplace_id,
            snapshots_created=created,
        )

    return created


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def collect_price_data(self, batch_size: int = 500) -> dict[str, Any]:
    """
    Collect price data from Scryfall in batches.

    Processes a limited number of cards per run to ensure tasks complete.
    Prioritizes inventory cards, then cards without recent data.

    Args:
        batch_size: Maximum cards to process per run (default 500).
                   With 5-min intervals, 500 cards/run processes ~144k cards/day.

    Returns:
        Summary of price collection results.
    """
    return run_async(_collect_price_data_async(batch_size))


async def _collect_price_data_async(batch_size: int = 500) -> dict[str, Any]:
    """
    Collect price data from Scryfall in batches.

    Strategy:
    - Always process ALL inventory cards first (user's cards are priority)
    - Then process up to batch_size additional cards without recent data
    - Ensures task completes in reasonable time (~2-3 minutes per run)
    """
    logger.info("Starting batched price data collection", batch_size=batch_size)
    
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
            
            # Calculate remaining budget after inventory cards
            remaining_budget = max(0, batch_size - len(inventory_cards))

            # PRIORITY 2: Get cards without recent data (within 24 hours)
            # Only fetch up to remaining_budget cards
            now = datetime.now(timezone.utc)
            stale_threshold = now - timedelta(hours=24)

            cards_without_data = []
            if remaining_budget > 0:
                cards_without_data_query = (
                    select(Card)
                    .outerjoin(
                        PriceSnapshot,
                        and_(
                            PriceSnapshot.card_id == Card.id,
                            PriceSnapshot.time >= stale_threshold
                        )
                    )
                    .where(
                        Card.id.notin_(inventory_card_ids) if inventory_card_ids else True,
                        PriceSnapshot.time.is_(None)  # No recent snapshots
                    )
                    .distinct()
                    .limit(remaining_budget)  # Only get what we can process
                )
                result = await db.execute(cards_without_data_query)
                cards_without_data = list(result.scalars().all())

            # PRIORITY 3: Fill remaining budget with cards that have older data
            remaining_after_stale = max(0, remaining_budget - len(cards_without_data))
            other_cards = []
            if remaining_after_stale > 0:
                cards_with_data_ids = {c.id for c in cards_without_data}
                exclude_ids = inventory_card_ids | cards_with_data_ids
                other_cards_query = (
                    select(Card)
                    .where(Card.id.notin_(exclude_ids) if exclude_ids else True)
                    .order_by(func.random())  # Random sampling for fair coverage
                    .limit(remaining_after_stale)
                )
                result = await db.execute(other_cards_query)
                other_cards = list(result.scalars().all())

            # Combine: inventory cards first, then stale, then random sample
            cards = inventory_cards + cards_without_data + other_cards
            logger.info(
                "Batched price collection",
                batch_size=batch_size,
                inventory=len(inventory_cards),
                stale=len(cards_without_data),
                random_sample=len(other_cards),
                total_this_run=len(cards),
            )
            
            results = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "scryfall_snapshots": 0,
                "cardtrader_snapshots": 0,
                "tcgplayer_snapshots": 0,
                "manapool_snapshots": 0,
                "mtgjson_snapshots": 0,
                "total_snapshots": 0,
                "backfilled_snapshots": 0,
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
            
            # Get or create marketplaces
            cardtrader_mp = await _get_or_create_cardtrader_marketplace(db)
            
            # Get adapters
            scryfall = ScryfallAdapter()
            from app.services.ingestion.adapters.cardtrader import CardTraderAdapter
            from app.services.ingestion.base import AdapterConfig
            cardtrader_config = AdapterConfig(
                base_url="https://api.cardtrader.com/api/v2",
                api_url="https://api.cardtrader.com/api/v2",
                api_key=settings.cardtrader_api_token,
                rate_limit_seconds=0.05,  # 200 requests per 10 seconds (per CardTrader API docs)
                timeout_seconds=30.0,
            )
            cardtrader = CardTraderAdapter(cardtrader_config)
            
            try:
                # Collect prices from Scryfall for all cards
                # Use fetch_all_marketplace_prices to get TCGPlayer, Cardmarket, MTGO prices separately
                logger.info("Collecting Scryfall price data", card_count=len(cards))
                
                for i, card in enumerate(cards):
                    try:
                        # Fetch all marketplace prices from Scryfall (TCGPlayer, Cardmarket, etc.)
                        all_prices = await scryfall.fetch_all_marketplace_prices(
                            card_name=card.name,
                            set_code=card.set_code,
                            collector_number=card.collector_number,
                            scryfall_id=card.scryfall_id,
                        )
                        
                        now = datetime.now(timezone.utc)
                        two_hours_ago = now - timedelta(hours=2)
                        
                        for price_data in all_prices:
                            if not price_data or price_data.price <= 0:
                                continue
                            
                            # Map currency to marketplace (same as data_seeding.py)
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
                            
                            # Check if we have a snapshot within the last 2 hours (to avoid too many duplicates)
                            recent_snapshot_query = select(PriceSnapshot).where(
                                and_(
                                    PriceSnapshot.card_id == card.id,
                                    PriceSnapshot.marketplace_id == marketplace.id,
                                    PriceSnapshot.time >= two_hours_ago,
                                )
                            ).order_by(PriceSnapshot.time.desc()).limit(1)
                            recent_result = await db.execute(recent_snapshot_query)
                            recent_snapshot = recent_result.scalar_one_or_none()
                            
                            # Always create a new snapshot for charting (unless we just created one in the last 2 hours)
                            # This ensures we have time-series data for charts
                            # Use upsert to prevent race conditions
                            if not recent_snapshot:
                                # Create non-foil price snapshot
                                await _upsert_price_snapshot(
                                    db=db,
                                    card_id=card.id,
                                    marketplace_id=marketplace.id,
                                    time=now,
                                    price=price_data.price,
                                    currency=price_data.currency,
                                    is_foil=False,
                                )
                                results["scryfall_snapshots"] += 1
                                results["total_snapshots"] += 1

                                # Create separate foil price snapshot if foil price exists
                                if price_data.price_foil and price_data.price_foil > 0:
                                    await _upsert_price_snapshot(
                                        db=db,
                                        card_id=card.id,
                                        marketplace_id=marketplace.id,
                                        time=now,
                                        price=price_data.price_foil,
                                        currency=price_data.currency,
                                        is_foil=True,
                                    )
                                    results["scryfall_snapshots"] += 1
                                    results["total_snapshots"] += 1

                                # Note: Historical data should come from MTGJSON, not synthetic backfill
                                # Chart endpoints use interpolation for gaps in real data
                            else:
                                # If we have a recent snapshot, only create a new one if price changed significantly
                                # This prevents duplicate snapshots while still capturing price changes
                                price_diff = abs(float(recent_snapshot.price) - float(price_data.price))
                                price_change_pct = (price_diff / float(recent_snapshot.price) * 100) if recent_snapshot.price and float(recent_snapshot.price) > 0 else 0

                                # Create new snapshot if price changed by more than 2% (lower threshold for better charting)
                                # Use upsert to prevent race conditions
                                if price_change_pct > 2.0:
                                    await _upsert_price_snapshot(
                                        db=db,
                                        card_id=card.id,
                                        marketplace_id=marketplace.id,
                                        time=now,
                                        price=price_data.price,
                                        currency=price_data.currency,
                                        is_foil=False,
                                    )
                                    results["scryfall_snapshots"] += 1
                                    results["total_snapshots"] += 1

                                    # Create separate foil snapshot if foil price exists
                                    if price_data.price_foil and price_data.price_foil > 0:
                                        await _upsert_price_snapshot(
                                            db=db,
                                            card_id=card.id,
                                            marketplace_id=marketplace.id,
                                            time=now,
                                            price=price_data.price_foil,
                                            currency=price_data.currency,
                                            is_foil=True,
                                        )
                                        results["scryfall_snapshots"] += 1
                                        results["total_snapshots"] += 1
                        
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
                
                # Collect prices from CardTrader (European market data)
                if settings.cardtrader_api_token:
                    logger.info("Collecting CardTrader price data", card_count=len(cards))
                    
                    for i, card in enumerate(cards):
                        try:
                            # Fetch price data from CardTrader
                            price_data = await cardtrader.fetch_price(
                                card_name=card.name,
                                set_code=card.set_code,
                                collector_number=card.collector_number,
                                scryfall_id=card.scryfall_id,
                            )
                            
                            if price_data and price_data.price > 0:
                                # For charting, we need multiple snapshots over time
                                # Check if we have a snapshot within the last 2 hours
                                now = datetime.now(timezone.utc)
                                two_hours_ago = now - timedelta(hours=2)
                                recent_snapshot_query = select(PriceSnapshot).where(
                                    and_(
                                        PriceSnapshot.card_id == card.id,
                                        PriceSnapshot.marketplace_id == cardtrader_mp.id,
                                        PriceSnapshot.time >= two_hours_ago,
                                    )
                                ).order_by(PriceSnapshot.time.desc()).limit(1)
                                recent_result = await db.execute(recent_snapshot_query)
                                recent_snapshot = recent_result.scalar_one_or_none()
                                
                                # Always create a new snapshot for charting (unless we just created one in the last 2 hours)
                                # Use upsert to prevent race conditions
                                if not recent_snapshot:
                                    # Create price snapshot using upsert
                                    await _upsert_price_snapshot(
                                        db=db,
                                        card_id=card.id,
                                        marketplace_id=cardtrader_mp.id,
                                        time=now,
                                        price=price_data.price,
                                        currency=price_data.currency,
                                        price_market=price_data.price_foil,  # Legacy: price_foil mapped to price_market
                                        price_low=price_data.price_low,
                                        price_high=price_data.price_high,
                                        num_listings=price_data.num_listings,
                                    )
                                    results["cardtrader_snapshots"] += 1
                                    results["total_snapshots"] += 1
                                    
                                    # Note: Historical data should come from MTGJSON, not synthetic backfill
                                    # Chart endpoints use interpolation for gaps in real data
                                else:
                                    # Create new snapshot if price changed by more than 2%
                                    # Use upsert to prevent race conditions
                                    price_diff = abs(float(recent_snapshot.price) - float(price_data.price))
                                    price_change_pct = (price_diff / float(recent_snapshot.price) * 100) if recent_snapshot.price and float(recent_snapshot.price) > 0 else 0
                                    
                                    if price_change_pct > 2.0:
                                        await _upsert_price_snapshot(
                                            db=db,
                                            card_id=card.id,
                                            marketplace_id=cardtrader_mp.id,
                                            time=now,
                                            price=price_data.price,
                                            currency=price_data.currency,
                                            price_market=price_data.price_foil,  # Legacy: price_foil mapped to price_market
                                            price_low=price_data.price_low,
                                            price_high=price_data.price_high,
                                            num_listings=price_data.num_listings,
                                        )
                                        results["cardtrader_snapshots"] += 1
                                        results["total_snapshots"] += 1
                                    
                                    # Flush periodically
                                    if results["total_snapshots"] % 100 == 0:
                                        await db.flush()
                        
                        except Exception as e:
                            # CardTrader errors are non-fatal (blueprint mapping may not exist)
                            # Log at info level for first few failures to help debug
                            if i < 5:
                                logger.info(
                                    "CardTrader price fetch failed",
                                    card_id=card.id,
                                    card_name=card.name,
                                    set_code=card.set_code,
                                    error=str(e),
                                    error_type=type(e).__name__
                                )
                            else:
                                logger.debug("CardTrader price fetch failed", card_id=card.id, error=str(e))
                            continue
                else:
                    logger.info("CardTrader API token not configured - skipping CardTrader collection")

                # Collect prices from TCGPlayer
                if settings.tcgplayer_api_key and settings.tcgplayer_api_secret:
                    from app.services.ingestion.adapters.tcgplayer import TCGPlayerAdapter
                    tcgplayer_config = AdapterConfig(
                        base_url="https://api.tcgplayer.com",
                        api_url="https://api.tcgplayer.com",
                        api_key=settings.tcgplayer_api_key,
                        api_secret=settings.tcgplayer_api_secret,
                        rate_limit_seconds=0.6,  # 100 requests per minute
                        timeout_seconds=30.0,
                    )
                    tcgplayer = TCGPlayerAdapter(tcgplayer_config)
                    tcgplayer_mp = await _get_or_create_tcgplayer_marketplace(db)
                    
                    logger.info("Collecting TCGPlayer price data", card_count=len(cards))
                    
                    for i, card in enumerate(cards):
                        try:
                            price_data = await tcgplayer.fetch_price(
                                card_name=card.name,
                                set_code=card.set_code,
                                collector_number=card.collector_number,
                                scryfall_id=card.scryfall_id,
                            )
                            
                            if price_data and price_data.price > 0:
                                now = datetime.now(timezone.utc)
                                two_hours_ago = now - timedelta(hours=2)
                                recent_snapshot_query = select(PriceSnapshot).where(
                                    and_(
                                        PriceSnapshot.card_id == card.id,
                                        PriceSnapshot.marketplace_id == tcgplayer_mp.id,
                                        PriceSnapshot.time >= two_hours_ago,
                                    )
                                ).order_by(PriceSnapshot.time.desc()).limit(1)
                                recent_result = await db.execute(recent_snapshot_query)
                                recent_snapshot = recent_result.scalar_one_or_none()
                                
                                if not recent_snapshot:
                                    await _upsert_price_snapshot(
                                        db=db,
                                        card_id=card.id,
                                        marketplace_id=tcgplayer_mp.id,
                                        time=now,
                                        price=price_data.price,
                                        currency=price_data.currency,
                                        price_market=price_data.price_foil,  # Legacy: price_foil mapped to price_market
                                        price_low=price_data.price_low,
                                        price_high=price_data.price_high,
                                        num_listings=price_data.num_listings,
                                    )
                                    results["tcgplayer_snapshots"] += 1
                                    results["total_snapshots"] += 1
                                else:
                                    price_diff = abs(float(recent_snapshot.price) - float(price_data.price))
                                    price_change_pct = (price_diff / float(recent_snapshot.price) * 100) if recent_snapshot.price and float(recent_snapshot.price) > 0 else 0
                                    
                                    if price_change_pct > 2.0:
                                        await _upsert_price_snapshot(
                                            db=db,
                                            card_id=card.id,
                                            marketplace_id=tcgplayer_mp.id,
                                            time=now,
                                            price=price_data.price,
                                            currency=price_data.currency,
                                            price_market=price_data.price_foil,  # Legacy: price_foil mapped to price_market
                                            price_low=price_data.price_low,
                                            price_high=price_data.price_high,
                                            num_listings=price_data.num_listings,
                                        )
                                        results["tcgplayer_snapshots"] += 1
                                        results["total_snapshots"] += 1
                        
                        except Exception as e:
                            if i < 5:
                                logger.info(
                                    "TCGPlayer price fetch failed",
                                    card_id=card.id,
                                    card_name=card.name,
                                    error=str(e),
                                )
                            else:
                                logger.debug("TCGPlayer price fetch failed", card_id=card.id, error=str(e))
                            continue
                    
                    await tcgplayer.close()
                else:
                    logger.info("TCGPlayer API credentials not configured - skipping TCGPlayer collection")

                # Collect prices from Manapool (European market bulk prices)
                if settings.manapool_api_token:
                    from app.services.ingestion.adapters.manapool import ManapoolAdapter
                    manapool = ManapoolAdapter()
                    manapool_mp = await _get_or_create_manapool_marketplace(db)

                    logger.info("Collecting Manapool bulk price data")

                    try:
                        # Fetch bulk prices (all cards in one request)
                        bulk_prices = await manapool.fetch_bulk_prices()
                        logger.info("Manapool bulk prices fetched", count=len(bulk_prices))

                        # Build a lookup from scryfall_id to card for fast matching
                        card_by_scryfall_id = {c.scryfall_id: c for c in cards if c.scryfall_id}

                        now = datetime.now(timezone.utc)
                        two_hours_ago = now - timedelta(hours=2)
                        manapool_snapshots = 0

                        for price_item in bulk_prices:
                            try:
                                scryfall_id = price_item.get("scryfall_id")
                                if not scryfall_id:
                                    continue

                                # Match to our card catalog
                                card = card_by_scryfall_id.get(scryfall_id)
                                if not card:
                                    continue

                                # Get price in EUR (convert from cents)
                                price_cents = price_item.get("price_cents") or price_item.get("price_cents_nm") or 0
                                if price_cents <= 0:
                                    continue

                                price_eur = price_cents / 100.0

                                # Get optional price variants
                                price_low = None
                                price_high = None
                                if price_item.get("price_cents_lp_plus"):
                                    price_low = price_item["price_cents_lp_plus"] / 100.0
                                if price_item.get("price_cents_nm"):
                                    price_high = price_item["price_cents_nm"] / 100.0

                                # Foil price
                                price_foil = None
                                if price_item.get("price_cents_foil"):
                                    price_foil = price_item["price_cents_foil"] / 100.0

                                # Check for recent snapshot
                                recent_snapshot_query = select(PriceSnapshot).where(
                                    and_(
                                        PriceSnapshot.card_id == card.id,
                                        PriceSnapshot.marketplace_id == manapool_mp.id,
                                        PriceSnapshot.time >= two_hours_ago,
                                    )
                                ).order_by(PriceSnapshot.time.desc()).limit(1)
                                recent_result = await db.execute(recent_snapshot_query)
                                recent_snapshot = recent_result.scalar_one_or_none()

                                if not recent_snapshot:
                                    # Create new snapshot
                                    await _upsert_price_snapshot(
                                        db=db,
                                        card_id=card.id,
                                        marketplace_id=manapool_mp.id,
                                        time=now,
                                        price=price_eur,
                                        currency="EUR",
                                        price_low=price_low,
                                        price_high=price_high,
                                        price_market=price_foil,
                                        num_listings=price_item.get("available_quantity"),
                                    )
                                    manapool_snapshots += 1
                                    results["total_snapshots"] += 1
                                else:
                                    # Create new snapshot if price changed by more than 2%
                                    price_diff = abs(float(recent_snapshot.price) - price_eur)
                                    price_change_pct = (price_diff / float(recent_snapshot.price) * 100) if recent_snapshot.price and float(recent_snapshot.price) > 0 else 0

                                    if price_change_pct > 2.0:
                                        await _upsert_price_snapshot(
                                            db=db,
                                            card_id=card.id,
                                            marketplace_id=manapool_mp.id,
                                            time=now,
                                            price=price_eur,
                                            currency="EUR",
                                            price_low=price_low,
                                            price_high=price_high,
                                            price_market=price_foil,
                                            num_listings=price_item.get("available_quantity"),
                                        )
                                        manapool_snapshots += 1
                                        results["total_snapshots"] += 1

                                # Flush periodically
                                if manapool_snapshots % 500 == 0 and manapool_snapshots > 0:
                                    await db.flush()
                                    logger.debug("Manapool progress", snapshots=manapool_snapshots)

                            except Exception as e:
                                # Individual price errors are non-fatal
                                continue

                        results["manapool_snapshots"] = manapool_snapshots
                        logger.info("Manapool price collection complete", snapshots=manapool_snapshots)

                    except Exception as e:
                        logger.warning("Manapool bulk price collection failed", error=str(e))
                        results["errors"].append(f"Manapool: {str(e)}")
                    finally:
                        await manapool.close()
                else:
                    logger.info("Manapool API token not configured - skipping Manapool collection")

                await db.commit()
                results["completed_at"] = datetime.now(timezone.utc).isoformat()
                
                logger.info(
                    "Price data collection completed",
                    cards_processed=results["cards_processed"],
                    scryfall_snapshots=results["scryfall_snapshots"],
                    cardtrader_snapshots=results.get("cardtrader_snapshots", 0),
                    tcgplayer_snapshots=results.get("tcgplayer_snapshots", 0),
                    manapool_snapshots=results.get("manapool_snapshots", 0),
                    backfilled_snapshots=results["backfilled_snapshots"],
                    total_snapshots=results["total_snapshots"],
                    errors_count=len(results["errors"]),
                )
                
                return results
            finally:
                await scryfall.close()
                if settings.cardtrader_api_token:
                    await cardtrader.close()
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


async def _get_or_create_cardtrader_marketplace(db: AsyncSession) -> Marketplace:
    """Get or create CardTrader marketplace entry."""
    query = select(Marketplace).where(Marketplace.slug == "cardtrader")
    result = await db.execute(query)
    mp = result.scalar_one_or_none()
    
    if not mp:
        mp = Marketplace(
            name="CardTrader",
            slug="cardtrader",
            base_url="https://www.cardtrader.com",
            api_url="https://api.cardtrader.com/api/v2",
            is_enabled=True,
            supports_api=True,
            default_currency="USD",  # Default to USD for USD listings tracking
            rate_limit_seconds=0.1,  # 10 requests per second
        )
        db.add(mp)
        await db.flush()
    
    return mp


async def _get_or_create_tcgplayer_marketplace(db: AsyncSession) -> Marketplace:
    """Get or create TCGPlayer marketplace entry."""
    query = select(Marketplace).where(Marketplace.slug == "tcgplayer")
    result = await db.execute(query)
    mp = result.scalar_one_or_none()

    if not mp:
        mp = Marketplace(
            name="TCGPlayer",
            slug="tcgplayer",
            base_url="https://www.tcgplayer.com",
            api_url="https://api.tcgplayer.com",
            is_enabled=True,
            supports_api=True,
            default_currency="USD",
            rate_limit_seconds=0.6,  # 100 requests per minute
        )
        db.add(mp)
        await db.flush()

    return mp


async def _get_or_create_manapool_marketplace(db: AsyncSession) -> Marketplace:
    """Get or create Manapool marketplace entry."""
    query = select(Marketplace).where(Marketplace.slug == "manapool")
    result = await db.execute(query)
    mp = result.scalar_one_or_none()

    if not mp:
        mp = Marketplace(
            name="Manapool",
            slug="manapool",
            base_url="https://manapool.com",
            api_url="https://manapool.com/api/v1",
            is_enabled=True,
            supports_api=True,
            default_currency="EUR",
            rate_limit_seconds=1.0,  # 60 requests per minute
        )
        db.add(mp)
        await db.flush()

    return mp


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def collect_inventory_prices(self) -> dict[str, Any]:
    """
    Collect prices specifically for cards in user inventories.
    
    This runs more frequently (every 2 minutes) than the general price collection
    to ensure inventory valuations are always up-to-date.
    
    Returns:
        Summary of inventory price collection results.
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
                "started_at": datetime.now(timezone.utc).isoformat(),
                "inventory_cards": len(cards),
                "snapshots_created": 0,
                "snapshots_updated": 0,
                "backfilled_snapshots": 0,
                "errors": [],
            }
            
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
            
            # Get adapters
            scryfall = ScryfallAdapter()
            
            # Get or create CardTrader marketplace if API token is available
            cardtrader_mp = None
            cardtrader = None
            if settings.cardtrader_api_token:
                from app.services.ingestion.adapters.cardtrader import CardTraderAdapter
                from app.services.ingestion.base import AdapterConfig
                cardtrader_config = AdapterConfig(
                    base_url="https://api.cardtrader.com/api/v2",
                    api_url="https://api.cardtrader.com/api/v2",
                    api_key=settings.cardtrader_api_token,
                    rate_limit_seconds=0.05,  # 200 requests per 10 seconds (per CardTrader API docs)
                    timeout_seconds=30.0,
                )
                cardtrader = CardTraderAdapter(cardtrader_config)
                cardtrader_mp = await _get_or_create_cardtrader_marketplace(db)
            
            try:
                for card in cards:
                    try:
                        # Fetch all marketplace prices from Scryfall (TCGPlayer, Cardmarket, etc.)
                        all_prices = await scryfall.fetch_all_marketplace_prices(
                            card_name=card.name,
                            set_code=card.set_code,
                            collector_number=card.collector_number,
                            scryfall_id=card.scryfall_id,
                        )
                        
                        now = datetime.now(timezone.utc)
                        two_hours_ago = now - timedelta(hours=2)
                        
                        for price_data in all_prices:
                            if not price_data or price_data.price <= 0:
                                continue
                            
                            # Map currency to marketplace (same as data_seeding.py)
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
                            
                            # Check for recent snapshot (within last 2 hours for inventory cards)
                            # Inventory cards are updated more frequently
                            recent_snapshot_query = select(PriceSnapshot).where(
                                and_(
                                    PriceSnapshot.card_id == card.id,
                                    PriceSnapshot.marketplace_id == marketplace.id,
                                    PriceSnapshot.time >= two_hours_ago,
                                )
                            ).order_by(PriceSnapshot.time.desc()).limit(1)
                            recent_result = await db.execute(recent_snapshot_query)
                            recent_snapshot = recent_result.scalar_one_or_none()
                            
                            if not recent_snapshot:
                                # Create new snapshot using upsert (prevents race conditions)
                                await _upsert_price_snapshot(
                                    db=db,
                                    card_id=card.id,
                                    marketplace_id=marketplace.id,
                                    time=now,
                                    price=price_data.price,
                                    currency=price_data.currency,
                                    price_market=price_data.price_foil,  # Legacy: price_foil mapped to price_market
                                )
                                results["snapshots_created"] += 1
                                
                                # Note: Historical data should come from MTGJSON, not synthetic backfill
                                # Chart endpoints use interpolation for gaps in real data
                            else:
                                # Always update inventory card prices (they change frequently)
                                # Use upsert to update with new timestamp
                                await _upsert_price_snapshot(
                                    db=db,
                                    card_id=card.id,
                                    marketplace_id=marketplace.id,
                                    time=now,
                                    price=price_data.price,
                                    currency=price_data.currency,
                                    price_market=price_data.price_foil,  # Legacy: price_foil mapped to price_market
                                )
                                results["snapshots_updated"] += 1
                        
                        # Collect prices from CardTrader (European market data) for inventory cards
                        if cardtrader and cardtrader_mp:
                            try:
                                # Fetch price data from CardTrader
                                price_data = await cardtrader.fetch_price(
                                    card_name=card.name,
                                    set_code=card.set_code,
                                    collector_number=card.collector_number,
                                    scryfall_id=card.scryfall_id,
                                )
                                
                                if price_data and price_data.price > 0:
                                    # Check for recent snapshot (within last 2 hours for inventory cards)
                                    recent_snapshot_query = select(PriceSnapshot).where(
                                        and_(
                                            PriceSnapshot.card_id == card.id,
                                            PriceSnapshot.marketplace_id == cardtrader_mp.id,
                                            PriceSnapshot.time >= two_hours_ago,
                                        )
                                    ).order_by(PriceSnapshot.time.desc()).limit(1)
                                    recent_result = await db.execute(recent_snapshot_query)
                                    recent_snapshot = recent_result.scalar_one_or_none()
                                    
                                    if not recent_snapshot:
                                        # Create new snapshot using upsert (prevents race conditions)
                                        await _upsert_price_snapshot(
                                            db=db,
                                            card_id=card.id,
                                            marketplace_id=cardtrader_mp.id,
                                            time=now,
                                            price=price_data.price,
                                            currency=price_data.currency,
                                            price_market=price_data.price_foil,  # Legacy: price_foil mapped to price_market
                                            price_low=price_data.price_low,
                                            price_high=price_data.price_high,
                                            num_listings=price_data.num_listings,
                                        )
                                        results["snapshots_created"] += 1
                                        
                                        # Note: Historical data should come from MTGJSON, not synthetic backfill
                                        # Chart endpoints use interpolation for gaps in real data
                                    else:
                                        # Update existing snapshot if price changed significantly
                                        # Use upsert to prevent race conditions
                                        price_diff = abs(float(recent_snapshot.price) - float(price_data.price))
                                        price_change_pct = (price_diff / float(recent_snapshot.price) * 100) if recent_snapshot.price and float(recent_snapshot.price) > 0 else 0
                                        
                                        if price_change_pct > 2.0:
                                            await _upsert_price_snapshot(
                                                db=db,
                                                card_id=card.id,
                                                marketplace_id=cardtrader_mp.id,
                                                time=now,
                                                price=price_data.price,
                                                currency=price_data.currency,
                                                price_market=price_data.price_foil,  # Legacy: price_foil mapped to price_market
                                                price_low=price_data.price_low,
                                                price_high=price_data.price_high,
                                                num_listings=price_data.num_listings,
                                            )
                                            results["snapshots_updated"] += 1
                            
                            except Exception as e:
                                # CardTrader errors are non-fatal (blueprint mapping may not exist)
                                logger.debug("CardTrader price fetch failed for inventory card", card_id=card.id, error=str(e))
                                # Don't add to errors list - CardTrader failures are expected for some cards
                    
                    except Exception as e:
                        error_msg = f"Card {card.id} ({card.name}): {str(e)}"
                        results["errors"].append(error_msg)
                        logger.warning("Failed to collect price for inventory card", card_id=card.id, error=str(e))
                        continue
                
                await db.commit()
                results["completed_at"] = datetime.now(timezone.utc).isoformat()
                
                logger.info(
                    "Inventory price collection completed",
                    cards=len(cards),
                    snapshots_created=results["snapshots_created"],
                    snapshots_updated=results["snapshots_updated"],
                    backfilled_snapshots=results["backfilled_snapshots"],
                )
                
                return results
            finally:
                await scryfall.close()
                if cardtrader:
                    await cardtrader.close()
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
                logger.error("Failed to sync card", scryfall_id=scryfall_id, error=str(e))
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
            # Helper to get or create marketplace (map MTGJSON prices to actual marketplaces)
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
                "started_at": datetime.now(timezone.utc).isoformat(),
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
                        
                        # Create price snapshots for each historical price (USD only)
                        # Map MTGJSON prices to actual marketplaces (TCGPlayer) based on currency
                        for price_data in historical_prices:
                            if not price_data or price_data.price <= 0:
                                continue
                            
                            # USD-only mode: Only process USD prices
                            if price_data.currency != "USD":
                                continue
                            
                            # Map currency to marketplace (USD only)
                            marketplace_map = {
                                "USD": ("tcgplayer", "TCGPlayer", "https://www.tcgplayer.com"),
                            }
                            
                            slug, name, base_url = marketplace_map.get(price_data.currency, (None, None, None))
                            if not slug:
                                continue
                            
                            # Get or create marketplace
                            marketplace = await get_or_create_marketplace(slug, name, base_url, price_data.currency)
                            
                            # Check if snapshot already exists for this timestamp and marketplace
                            existing_query = select(PriceSnapshot).where(
                                and_(
                                    PriceSnapshot.card_id == card.id,
                                    PriceSnapshot.marketplace_id == marketplace.id,
                                    PriceSnapshot.time == price_data.snapshot_time,
                                    PriceSnapshot.condition == CardCondition.NEAR_MINT.value,
                                    PriceSnapshot.is_foil == False,
                                    PriceSnapshot.language == CardLanguage.ENGLISH.value,
                                )
                            )
                            existing_result = await db.execute(existing_query)
                            existing = existing_result.scalar_one_or_none()

                            if existing:
                                # Update existing snapshot
                                existing.price = price_data.price
                                existing.currency = price_data.currency
                                existing.price_market = price_data.price_foil
                                results["snapshots_skipped"] += 1
                            else:
                                # Create new snapshot
                                snapshot = PriceSnapshot(
                                    time=price_data.snapshot_time,
                                    card_id=card.id,
                                    marketplace_id=marketplace.id,
                                    condition=CardCondition.NEAR_MINT.value,
                                    is_foil=False,
                                    language=CardLanguage.ENGLISH.value,
                                    price=price_data.price,
                                    currency=price_data.currency,
                                    price_market=price_data.price_foil,
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
                results["completed_at"] = datetime.now(timezone.utc).isoformat()
                
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
