"""
Pricing tasks for automated price data collection.

This module provides three main Celery tasks:
1. bulk_refresh - Downloads Scryfall bulk data and updates all card prices (every 12 hours)
2. inventory_refresh - Refreshes prices for cards in user inventories (every 4 hours)
3. condition_refresh - Fetches TCGPlayer condition prices for high-value cards (every 6 hours)
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select, and_, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import CardCondition, CardLanguage
from app.models import Card, InventoryItem, PriceSnapshot, Marketplace
from app.services.ingestion import ScryfallAdapter
from app.services.pricing import BulkPriceImporter, ConditionPricer, InventoryValuator
from app.tasks.utils import create_task_session_maker, run_async

logger = structlog.get_logger()

# Constants for rate limiting and thresholds
SCRYFALL_RATE_LIMIT_SECONDS = 0.1  # 100ms between requests per Scryfall guidelines
TCGPLAYER_PRICE_THRESHOLD = 5.00  # Use TCGPlayer API for cards above this price
BULK_DATA_STALE_HOURS = 12  # Consider bulk data stale after this many hours


@shared_task(
    bind=True,
    name="app.tasks.pricing.bulk_refresh",
    max_retries=2,
    default_retry_delay=600,
    autoretry_for=(Exception,),
)
def bulk_refresh(self) -> dict[str, Any]:
    """
    Download Scryfall bulk data and update all card prices.

    Runs every 12 hours or on startup if data is stale.
    Uses BulkPriceImporter to efficiently process ~30k+ cards.
    Triggers inventory valuation update after completion.

    Returns:
        Summary of import results including cards_updated, snapshots_created, errors.
    """
    return run_async(_bulk_refresh_async())


async def _bulk_refresh_async() -> dict[str, Any]:
    """Async implementation of bulk price refresh."""
    logger.info("Starting bulk price refresh from Scryfall")

    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            results = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "cards_updated": 0,
                "snapshots_created": 0,
                "errors": 0,
                "inventory_updated": False,
            }

            try:
                # Check if bulk data is stale
                stale_threshold = datetime.now(timezone.utc) - timedelta(hours=BULK_DATA_STALE_HOURS)

                # Check last bulk import time from price snapshots
                last_bulk_query = (
                    select(func.max(PriceSnapshot.time))
                    .where(PriceSnapshot.source == "bulk")
                )
                result = await db.execute(last_bulk_query)
                last_bulk_time = result.scalar_one_or_none()

                if last_bulk_time and last_bulk_time > stale_threshold:
                    logger.info(
                        "Bulk data is still fresh, skipping refresh",
                        last_bulk_time=last_bulk_time.isoformat(),
                        stale_threshold=stale_threshold.isoformat(),
                    )
                    results["skipped"] = True
                    results["reason"] = "Data still fresh"
                    results["last_bulk_time"] = last_bulk_time.isoformat()
                    return results

                # Import bulk data
                importer = BulkPriceImporter()

                def progress_callback(stats: dict[str, int]) -> None:
                    logger.debug(
                        "Bulk import progress",
                        cards_updated=stats.get("cards_updated", 0),
                        snapshots_created=stats.get("snapshots_created", 0),
                    )

                import_stats = await importer.import_prices(db, progress_callback)

                results["cards_updated"] = import_stats.get("cards_updated", 0)
                results["snapshots_created"] = import_stats.get("snapshots_created", 0)
                results["errors"] = import_stats.get("errors", 0)

                # Trigger inventory valuation update
                try:
                    await _update_inventory_valuations(db)
                    results["inventory_updated"] = True
                except Exception as e:
                    logger.warning("Failed to update inventory valuations", error=str(e))
                    results["inventory_update_error"] = str(e)

                await db.commit()

                logger.info(
                    "Bulk price refresh completed",
                    cards_updated=results["cards_updated"],
                    snapshots_created=results["snapshots_created"],
                    errors=results["errors"],
                )

            except Exception as e:
                logger.error("Bulk price refresh failed", error=str(e))
                results["error"] = str(e)
                raise

            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            return results

    finally:
        await engine.dispose()


async def _update_inventory_valuations(db: AsyncSession) -> None:
    """Update current_value for all inventory items based on latest prices."""
    valuator = InventoryValuator()

    # Get all inventory items
    inventory_query = select(InventoryItem)
    result = await db.execute(inventory_query)
    inventory_items = result.scalars().all()

    if not inventory_items:
        return

    # Build a single query to get the latest price for each (card_id, is_foil) combination
    # using a window function to rank prices by time

    # Subquery to get the latest price per (card_id, is_foil) combination
    latest_prices_subquery = (
        select(
            PriceSnapshot.card_id,
            PriceSnapshot.is_foil,
            PriceSnapshot.price,
            func.row_number().over(
                partition_by=[PriceSnapshot.card_id, PriceSnapshot.is_foil],
                order_by=PriceSnapshot.time.desc()
            ).label("rn")
        )
    ).subquery()

    # Get only the latest prices (row_number = 1)
    latest_prices_query = (
        select(
            latest_prices_subquery.c.card_id,
            latest_prices_subquery.c.is_foil,
            latest_prices_subquery.c.price,
        )
        .where(latest_prices_subquery.c.rn == 1)
    )

    result = await db.execute(latest_prices_query)
    latest_prices = result.all()

    # Build a lookup dict: (card_id, is_foil) -> price
    price_lookup: dict[tuple[int, bool], float] = {
        (row.card_id, row.is_foil): float(row.price)
        for row in latest_prices
    }

    now = datetime.now(timezone.utc)
    updated_count = 0

    for item in inventory_items:
        latest_price = price_lookup.get((item.card_id, item.is_foil))

        if latest_price:
            # Calculate value using condition multiplier
            item.current_value = valuator.calculate_item_value(
                base_price=latest_price,
                condition=item.condition,
                quantity=item.quantity,
                is_foil=item.is_foil,
            )
            item.last_valued_at = now

            # Calculate value change percentage if we have acquisition price
            if item.acquisition_price and float(item.acquisition_price) > 0:
                per_card_current = item.current_value / item.quantity
                per_card_acquisition = float(item.acquisition_price)
                item.value_change_pct = ((per_card_current - per_card_acquisition) / per_card_acquisition) * 100

            updated_count += 1

    await db.flush()
    logger.debug("Updated inventory valuations", items_updated=updated_count)


@shared_task(
    bind=True,
    name="app.tasks.pricing.inventory_refresh",
    max_retries=3,
    default_retry_delay=300,
    autoretry_for=(Exception,),
)
def inventory_refresh(self) -> dict[str, Any]:
    """
    Refresh prices for cards in user inventories using Scryfall API.

    Runs every 4 hours. Only updates cards that are in at least one inventory.
    Respects Scryfall rate limit (100ms between requests).

    Returns:
        Summary of refresh results.
    """
    return run_async(_inventory_refresh_async())


async def _inventory_refresh_async() -> dict[str, Any]:
    """Async implementation of inventory price refresh."""
    logger.info("Starting inventory price refresh")

    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            results = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "cards_refreshed": 0,
                "api_calls": 0,
                "snapshots_created": 0,
                "errors": [],
            }

            # Get distinct cards that are in at least one inventory
            inventory_cards_query = (
                select(Card)
                .join(InventoryItem, InventoryItem.card_id == Card.id)
                .distinct()
            )
            result = await db.execute(inventory_cards_query)
            cards = list(result.scalars().all())

            if not cards:
                logger.info("No inventory cards to refresh")
                results["status"] = "no_inventory"
                return results

            logger.info("Refreshing prices for inventory cards", count=len(cards))

            # Get or create marketplace
            marketplace = await _get_or_create_marketplace(db, "tcgplayer", "TCGPlayer", "https://www.tcgplayer.com", "USD")

            # Initialize Scryfall adapter
            scryfall = ScryfallAdapter()

            try:
                for card in cards:
                    try:
                        # Fetch price from Scryfall
                        all_prices = await scryfall.fetch_all_marketplace_prices(
                            card_name=card.name,
                            set_code=card.set_code,
                            collector_number=card.collector_number,
                            scryfall_id=card.scryfall_id,
                        )
                        results["api_calls"] += 1

                        now = datetime.now(timezone.utc)

                        for price_data in all_prices:
                            if not price_data or price_data.price <= 0:
                                continue

                            # Only process USD prices for inventory
                            if price_data.currency != "USD":
                                continue

                            # Create non-foil snapshot
                            snapshot = PriceSnapshot(
                                time=now,
                                card_id=card.id,
                                marketplace_id=marketplace.id,
                                condition=CardCondition.NEAR_MINT.value,
                                is_foil=False,
                                language=CardLanguage.ENGLISH.value,
                                price=price_data.price,
                                currency=price_data.currency,
                                source="api",
                            )
                            db.add(snapshot)
                            results["snapshots_created"] += 1

                            # Create foil snapshot if available
                            if price_data.price_foil and price_data.price_foil > 0:
                                foil_snapshot = PriceSnapshot(
                                    time=now,
                                    card_id=card.id,
                                    marketplace_id=marketplace.id,
                                    condition=CardCondition.NEAR_MINT.value,
                                    is_foil=True,
                                    language=CardLanguage.ENGLISH.value,
                                    price=price_data.price_foil,
                                    currency=price_data.currency,
                                    source="api",
                                )
                                db.add(foil_snapshot)
                                results["snapshots_created"] += 1

                        results["cards_refreshed"] += 1

                        # Respect rate limit
                        await asyncio.sleep(SCRYFALL_RATE_LIMIT_SECONDS)

                        # Commit every 50 cards to release transaction during rate limiting
                        # This prevents "idle in transaction" while waiting for API rate limits
                        if results["cards_refreshed"] % 50 == 0:
                            await db.commit()
                            logger.debug(
                                "Inventory refresh progress - committed batch",
                                cards_refreshed=results["cards_refreshed"],
                                total=len(cards),
                                snapshots=results["snapshots_created"],
                            )

                    except Exception as e:
                        error_msg = f"Card {card.id} ({card.name}): {str(e)}"
                        results["errors"].append(error_msg)
                        logger.warning("Failed to refresh card price", card_id=card.id, error=str(e))

                # Update inventory valuations after price refresh
                await _update_inventory_valuations(db)

                await db.commit()

            finally:
                await scryfall.close()

            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(
                "Inventory price refresh completed",
                cards_refreshed=results["cards_refreshed"],
                snapshots_created=results["snapshots_created"],
                errors_count=len(results["errors"]),
            )

            return results

    finally:
        await engine.dispose()


@shared_task(
    bind=True,
    name="app.tasks.pricing.condition_refresh",
    max_retries=2,
    default_retry_delay=600,
    autoretry_for=(Exception,),
)
def condition_refresh(self) -> dict[str, Any]:
    """
    Fetch TCGPlayer condition prices for high-value inventory cards.

    Runs every 6 hours. Uses TCGPlayer API for cards >$5, multipliers for cheaper cards.
    Uses ConditionPricer service to handle both API calls and multiplier calculations.

    Returns:
        Summary of condition price updates.
    """
    return run_async(_condition_refresh_async())


async def _condition_refresh_async() -> dict[str, Any]:
    """Async implementation of condition price refresh."""
    logger.info("Starting condition price refresh for high-value cards")

    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            results = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "cards_processed": 0,
                "tcgplayer_calls": 0,
                "multiplier_fallbacks": 0,
                "snapshots_created": 0,
                "errors": [],
            }

            # Get high-value inventory cards (>$5 NM price)
            # Join with latest price snapshot to filter by value
            subquery = (
                select(
                    PriceSnapshot.card_id,
                    func.max(PriceSnapshot.time).label("latest_time")
                )
                .where(PriceSnapshot.condition == CardCondition.NEAR_MINT.value)
                .where(PriceSnapshot.is_foil == False)
                .group_by(PriceSnapshot.card_id)
            ).subquery()

            high_value_query = (
                select(Card, PriceSnapshot.price)
                .join(InventoryItem, InventoryItem.card_id == Card.id)
                .join(
                    subquery,
                    subquery.c.card_id == Card.id
                )
                .join(
                    PriceSnapshot,
                    and_(
                        PriceSnapshot.card_id == subquery.c.card_id,
                        PriceSnapshot.time == subquery.c.latest_time,
                    )
                )
                .where(PriceSnapshot.price >= TCGPLAYER_PRICE_THRESHOLD)
                .distinct()
            )

            result = await db.execute(high_value_query)
            high_value_cards = result.all()

            if not high_value_cards:
                logger.info("No high-value inventory cards to process")
                results["status"] = "no_high_value_cards"
                return results

            logger.info("Processing condition prices for high-value cards", count=len(high_value_cards))

            # Initialize condition pricer
            tcgplayer_api_key = None
            if settings.tcgplayer_api_key and settings.tcgplayer_api_secret:
                tcgplayer_api_key = f"{settings.tcgplayer_api_key}:{settings.tcgplayer_api_secret}"

            pricer = ConditionPricer(tcgplayer_api_key=tcgplayer_api_key)

            # Get marketplace
            marketplace = await _get_or_create_marketplace(db, "tcgplayer", "TCGPlayer", "https://www.tcgplayer.com", "USD")

            now = datetime.now(timezone.utc)

            for card, nm_price in high_value_cards:
                try:
                    # Get TCGPlayer product ID if available (from card metadata)
                    tcgplayer_product_id = getattr(card, 'tcgplayer_product_id', None)

                    # Get condition prices
                    condition_prices = await pricer.get_prices_for_card(
                        nm_price=float(nm_price),
                        tcgplayer_product_id=tcgplayer_product_id,
                    )

                    if pricer.should_use_tcgplayer(float(nm_price)) and tcgplayer_product_id:
                        results["tcgplayer_calls"] += 1
                    else:
                        results["multiplier_fallbacks"] += 1

                    # Create price snapshots for each condition
                    for condition_name, price in condition_prices.items():
                        if price <= 0:
                            continue

                        snapshot = PriceSnapshot(
                            time=now,
                            card_id=card.id,
                            marketplace_id=marketplace.id,
                            condition=condition_name,
                            is_foil=False,
                            language=CardLanguage.ENGLISH.value,
                            price=price,
                            currency="USD",
                            source="condition_api" if pricer.should_use_tcgplayer(float(nm_price)) else "condition_multiplier",
                        )
                        db.add(snapshot)
                        results["snapshots_created"] += 1

                    results["cards_processed"] += 1

                    # Commit every 25 cards to release transaction during API calls
                    # This prevents "idle in transaction" while waiting for external APIs
                    if results["cards_processed"] % 25 == 0:
                        await db.commit()
                        logger.debug(
                            "Condition refresh progress - committed batch",
                            cards_processed=results["cards_processed"],
                            total=len(high_value_cards),
                            snapshots=results["snapshots_created"],
                        )

                except Exception as e:
                    error_msg = f"Card {card.id} ({card.name}): {str(e)}"
                    results["errors"].append(error_msg)
                    logger.warning("Failed to get condition prices", card_id=card.id, error=str(e))

            await db.commit()  # Final commit for remaining items

            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(
                "Condition price refresh completed",
                cards_processed=results["cards_processed"],
                tcgplayer_calls=results["tcgplayer_calls"],
                multiplier_fallbacks=results["multiplier_fallbacks"],
                snapshots_created=results["snapshots_created"],
            )

            return results

    finally:
        await engine.dispose()


async def _get_or_create_marketplace(
    db: AsyncSession,
    slug: str,
    name: str,
    base_url: str,
    currency: str
) -> Marketplace:
    """Get or create a marketplace by slug."""
    query = select(Marketplace).where(Marketplace.slug == slug)
    result = await db.execute(query)
    marketplace = result.scalar_one_or_none()

    if not marketplace:
        marketplace = Marketplace(
            slug=slug,
            name=name,
            base_url=base_url,
            is_enabled=True,
            default_currency=currency,
        )
        db.add(marketplace)
        await db.flush()

    return marketplace
