"""
Optimized ingestion tasks with parallel adapter collection.

This module replaces the sequential adapter collection in ingestion.py
with parallel Celery tasks for each marketplace adapter.

Key optimizations:
1. Parallel adapter tasks via Celery Group
2. Bulk fetch recent snapshots (O(1) instead of O(n))
3. Redis cache-aside for snapshot timestamps
4. Batch upserts (500 records per statement)
"""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import structlog
from celery import group, shared_task
from redis.asyncio import Redis
from sqlalchemy import select, and_, func

from app.core.config import settings
from app.core.constants import CardCondition, CardLanguage
from app.models import Card, Marketplace, InventoryItem
from app.services.ingestion import ScryfallAdapter
from app.services.ingestion.base import AdapterConfig
from app.services.ingestion.cache import SnapshotCache
from app.services.ingestion.bulk_ops import (
    get_recent_snapshot_times,
    batch_upsert_snapshots,
)
from app.tasks.utils import create_task_session_maker, run_async

logger = structlog.get_logger()


# =============================================================================
# Marketplace ID Constants (looked up once and cached)
# =============================================================================

MARKETPLACE_SLUGS = {
    "tcgplayer": ("TCGPlayer", "https://www.tcgplayer.com", "USD"),
    "cardmarket": ("Cardmarket", "https://www.cardmarket.com", "EUR"),
    "cardtrader": ("CardTrader", "https://www.cardtrader.com", "EUR"),
    "manapool": ("Manapool", "https://www.manapool.com", "EUR"),
    "mtgo": ("MTGO", "https://www.mtgo.com", "TIX"),
}


# =============================================================================
# Coordinator Task
# =============================================================================

@shared_task(bind=True)
def dispatch_price_collection(self, batch_size: int = 500) -> dict[str, Any]:
    """
    Coordinator task that dispatches parallel adapter collection tasks.

    This replaces the sequential collect_price_data task with parallel execution.
    Each adapter runs as its own Celery task for maximum throughput.

    Args:
        batch_size: Maximum cards to process per adapter task

    Returns:
        Summary with dispatched task info
    """
    return run_async(_dispatch_price_collection_async(batch_size))


async def _dispatch_price_collection_async(batch_size: int) -> dict[str, Any]:
    """Get priority card IDs and dispatch parallel tasks."""
    session_maker, engine = create_task_session_maker()

    try:
        async with session_maker() as db:
            card_ids = await _get_priority_card_ids(db, batch_size)

        if not card_ids:
            return {"status": "no_cards", "dispatched": 0}

        # Build list of tasks to dispatch
        tasks = []

        # Always include Scryfall (primary source)
        tasks.append(collect_scryfall_prices.s(card_ids))

        # Include CardTrader if configured
        if settings.cardtrader_api_token:
            tasks.append(collect_cardtrader_prices.s(card_ids))

        # Include TCGPlayer if configured
        if settings.tcgplayer_api_key and settings.tcgplayer_api_secret:
            tasks.append(collect_tcgplayer_prices.s(card_ids))

        # Include Manapool if configured (uses bulk API)
        if settings.manapool_api_token:
            tasks.append(collect_manapool_prices.s())

        # Dispatch all tasks in parallel
        job = group(tasks)
        result = job.apply_async()

        return {
            "status": "dispatched",
            "card_count": len(card_ids),
            "tasks": [t.name for t in tasks],
            "group_id": str(result.id),
        }

    finally:
        await engine.dispose()


async def _get_priority_card_ids(db, batch_size: int) -> list[int]:
    """
    Get prioritized card IDs for collection.

    Priority order:
    1. Cards in user inventories (always)
    2. Cards without recent data (stale)
    3. Random sample (fair coverage)
    """
    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(hours=24)

    # Priority 1: Inventory cards
    inventory_query = (
        select(Card.id)
        .join(InventoryItem, InventoryItem.card_id == Card.id)
        .distinct()
    )
    result = await db.execute(inventory_query)
    inventory_ids = list(result.scalars().all())

    remaining = max(0, batch_size - len(inventory_ids))
    if remaining == 0:
        return inventory_ids

    # Priority 2: Stale cards (no recent snapshots)
    from app.models import PriceSnapshot

    stale_query = (
        select(Card.id)
        .outerjoin(
            PriceSnapshot,
            and_(
                PriceSnapshot.card_id == Card.id,
                PriceSnapshot.time >= stale_threshold,
            )
        )
        .where(
            Card.id.notin_(inventory_ids) if inventory_ids else True,
            PriceSnapshot.time.is_(None),
        )
        .distinct()
        .limit(remaining)
    )
    result = await db.execute(stale_query)
    stale_ids = list(result.scalars().all())

    remaining -= len(stale_ids)
    if remaining <= 0:
        return inventory_ids + stale_ids

    # Priority 3: Random sample
    exclude_ids = set(inventory_ids) | set(stale_ids)
    random_query = (
        select(Card.id)
        .where(Card.id.notin_(exclude_ids) if exclude_ids else True)
        .order_by(func.random())
        .limit(remaining)
    )
    result = await db.execute(random_query)
    random_ids = list(result.scalars().all())

    return inventory_ids + stale_ids + random_ids


# =============================================================================
# Per-Adapter Collection Tasks
# =============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def collect_scryfall_prices(self, card_ids: list[int]) -> dict[str, Any]:
    """
    Collect prices from Scryfall for given cards.

    Scryfall provides prices from TCGPlayer (USD), Cardmarket (EUR), and MTGO (TIX).
    """
    try:
        return run_async(_collect_scryfall_async(card_ids))
    except Exception as e:
        logger.exception("Scryfall collection failed", error=str(e))
        raise self.retry(exc=e)


async def _collect_scryfall_async(card_ids: list[int]) -> dict[str, Any]:
    """Collect Scryfall prices with optimized bulk operations."""
    session_maker, engine = create_task_session_maker()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    cache = SnapshotCache(redis)

    stats = {
        "adapter": "scryfall",
        "cards_checked": len(card_ids),
        "cards_fetched": 0,
        "snapshots_created": 0,
        "cache_hits": 0,
        "errors": [],
    }

    try:
        async with session_maker() as db:
            # Get marketplace IDs
            marketplace_map = await _get_or_create_marketplaces(db)
            tcgplayer_id = marketplace_map.get("tcgplayer")
            cardmarket_id = marketplace_map.get("cardmarket")
            mtgo_id = marketplace_map.get("mtgo")

            if not tcgplayer_id:
                return {**stats, "error": "TCGPlayer marketplace not found"}

            # Check Redis cache for recently updated cards
            recently_updated = await cache.get_recently_updated(card_ids, tcgplayer_id)
            stats["cache_hits"] = len(recently_updated)

            # Filter out cached cards
            remaining_ids = [cid for cid in card_ids if cid not in recently_updated]

            if not remaining_ids:
                return stats

            # Bulk fetch recent snapshots from DB for remaining cards
            threshold = datetime.now(timezone.utc) - timedelta(hours=2)
            db_recent = await get_recent_snapshot_times(
                db, remaining_ids, tcgplayer_id, threshold
            )

            # Cards that need API fetch
            cards_to_fetch = [cid for cid in remaining_ids if cid not in db_recent]

            if not cards_to_fetch:
                return stats

            # Load card details for API calls
            result = await db.execute(
                select(Card).where(Card.id.in_(cards_to_fetch))
            )
            cards = {c.id: c for c in result.scalars().all()}

            # Collect prices from Scryfall
            adapter = ScryfallAdapter()
            snapshots_to_insert = []
            now = datetime.now(timezone.utc)
            updated_card_ids = []

            for card_id in cards_to_fetch:
                card = cards.get(card_id)
                if not card:
                    continue

                try:
                    all_prices = await adapter.fetch_all_marketplace_prices(
                        card_name=card.name,
                        set_code=card.set_code,
                        collector_number=card.collector_number,
                        scryfall_id=card.scryfall_id,
                    )

                    for price_data in all_prices:
                        if not price_data or price_data.price <= 0:
                            continue

                        # Map currency to marketplace
                        mp_id = {
                            "USD": tcgplayer_id,
                            "EUR": cardmarket_id,
                            "TIX": mtgo_id,
                        }.get(price_data.currency)

                        if not mp_id:
                            continue

                        # Add non-foil snapshot
                        snapshots_to_insert.append({
                            "time": now,
                            "card_id": card_id,
                            "marketplace_id": mp_id,
                            "condition": CardCondition.NEAR_MINT.value,
                            "is_foil": False,
                            "language": CardLanguage.ENGLISH.value,
                            "price": price_data.price,
                            "currency": price_data.currency,
                            "source": "scryfall",
                        })

                        # Add foil snapshot if available
                        if price_data.price_foil and price_data.price_foil > 0:
                            snapshots_to_insert.append({
                                "time": now,
                                "card_id": card_id,
                                "marketplace_id": mp_id,
                                "condition": CardCondition.NEAR_MINT.value,
                                "is_foil": True,
                                "language": CardLanguage.ENGLISH.value,
                                "price": price_data.price_foil,
                                "currency": price_data.currency,
                                "source": "scryfall",
                            })

                    updated_card_ids.append(card_id)
                    stats["cards_fetched"] += 1

                except Exception as e:
                    stats["errors"].append(f"Card {card_id}: {str(e)}")
                    logger.debug("Scryfall fetch failed", card_id=card_id, error=str(e))

            # Batch upsert all snapshots
            if snapshots_to_insert:
                insert_stats = await batch_upsert_snapshots(db, snapshots_to_insert)
                stats["snapshots_created"] = insert_stats["inserted"]

            # Update Redis cache for successfully updated cards
            if updated_card_ids:
                await cache.mark_updated(updated_card_ids, tcgplayer_id)

        return stats

    except Exception as e:
        logger.exception("Scryfall collection error", error=str(e))
        return {**stats, "error": str(e)}

    finally:
        await redis.aclose()
        await engine.dispose()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def collect_cardtrader_prices(self, card_ids: list[int]) -> dict[str, Any]:
    """Collect prices from CardTrader for given cards."""
    try:
        return run_async(_collect_cardtrader_async(card_ids))
    except Exception as e:
        logger.exception("CardTrader collection failed", error=str(e))
        raise self.retry(exc=e)


async def _collect_cardtrader_async(card_ids: list[int]) -> dict[str, Any]:
    """Collect CardTrader prices with optimized bulk operations."""
    session_maker, engine = create_task_session_maker()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    cache = SnapshotCache(redis)

    stats = {
        "adapter": "cardtrader",
        "cards_checked": len(card_ids),
        "cards_fetched": 0,
        "snapshots_created": 0,
        "cache_hits": 0,
        "errors": [],
    }

    try:
        from app.services.ingestion.adapters.cardtrader import CardTraderAdapter

        async with session_maker() as db:
            # Get marketplace ID
            marketplace_map = await _get_or_create_marketplaces(db)
            cardtrader_id = marketplace_map.get("cardtrader")

            if not cardtrader_id:
                return {**stats, "error": "CardTrader marketplace not found"}

            # Check Redis cache
            recently_updated = await cache.get_recently_updated(card_ids, cardtrader_id)
            stats["cache_hits"] = len(recently_updated)

            remaining_ids = [cid for cid in card_ids if cid not in recently_updated]
            if not remaining_ids:
                return stats

            # Bulk fetch recent snapshots
            threshold = datetime.now(timezone.utc) - timedelta(hours=2)
            db_recent = await get_recent_snapshot_times(
                db, remaining_ids, cardtrader_id, threshold
            )

            cards_to_fetch = [cid for cid in remaining_ids if cid not in db_recent]
            if not cards_to_fetch:
                return stats

            # Load card details
            result = await db.execute(
                select(Card).where(Card.id.in_(cards_to_fetch))
            )
            cards = {c.id: c for c in result.scalars().all()}

            # Initialize adapter
            config = AdapterConfig(
                base_url="https://api.cardtrader.com/api/v2",
                api_url="https://api.cardtrader.com/api/v2",
                api_key=settings.cardtrader_api_token,
                rate_limit_seconds=0.05,
                timeout_seconds=30.0,
            )
            adapter = CardTraderAdapter(config)

            snapshots_to_insert = []
            now = datetime.now(timezone.utc)
            updated_card_ids = []

            for card_id in cards_to_fetch:
                card = cards.get(card_id)
                if not card:
                    continue

                try:
                    price_data = await adapter.fetch_price(
                        card_name=card.name,
                        set_code=card.set_code,
                        collector_number=card.collector_number,
                        scryfall_id=card.scryfall_id,
                    )

                    if price_data and price_data.price > 0:
                        snapshots_to_insert.append({
                            "time": now,
                            "card_id": card_id,
                            "marketplace_id": cardtrader_id,
                            "condition": CardCondition.NEAR_MINT.value,
                            "is_foil": False,
                            "language": CardLanguage.ENGLISH.value,
                            "price": price_data.price,
                            "price_low": price_data.price_low,
                            "price_high": price_data.price_high,
                            "currency": price_data.currency,
                            "num_listings": price_data.num_listings,
                            "source": "cardtrader",
                        })
                        updated_card_ids.append(card_id)
                        stats["cards_fetched"] += 1

                except Exception as e:
                    # CardTrader errors are common (card not found), log at debug
                    logger.debug("CardTrader fetch failed", card_id=card_id, error=str(e))

            # Batch upsert
            if snapshots_to_insert:
                insert_stats = await batch_upsert_snapshots(db, snapshots_to_insert)
                stats["snapshots_created"] = insert_stats["inserted"]

            # Update cache
            if updated_card_ids:
                await cache.mark_updated(updated_card_ids, cardtrader_id)

        return stats

    except Exception as e:
        logger.exception("CardTrader collection error", error=str(e))
        return {**stats, "error": str(e)}

    finally:
        await redis.aclose()
        await engine.dispose()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def collect_tcgplayer_prices(self, card_ids: list[int]) -> dict[str, Any]:
    """Collect prices from TCGPlayer API for given cards."""
    try:
        return run_async(_collect_tcgplayer_async(card_ids))
    except Exception as e:
        logger.exception("TCGPlayer collection failed", error=str(e))
        raise self.retry(exc=e)


async def _collect_tcgplayer_async(card_ids: list[int]) -> dict[str, Any]:
    """Collect TCGPlayer prices with optimized bulk operations."""
    session_maker, engine = create_task_session_maker()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    cache = SnapshotCache(redis)

    stats = {
        "adapter": "tcgplayer",
        "cards_checked": len(card_ids),
        "cards_fetched": 0,
        "snapshots_created": 0,
        "cache_hits": 0,
        "errors": [],
    }

    try:
        from app.services.ingestion.adapters.tcgplayer import TCGPlayerAdapter

        async with session_maker() as db:
            marketplace_map = await _get_or_create_marketplaces(db)
            tcgplayer_id = marketplace_map.get("tcgplayer")

            if not tcgplayer_id:
                return {**stats, "error": "TCGPlayer marketplace not found"}

            # Check cache
            recently_updated = await cache.get_recently_updated(card_ids, tcgplayer_id)
            stats["cache_hits"] = len(recently_updated)

            remaining_ids = [cid for cid in card_ids if cid not in recently_updated]
            if not remaining_ids:
                return stats

            # Bulk fetch recent snapshots
            threshold = datetime.now(timezone.utc) - timedelta(hours=2)
            db_recent = await get_recent_snapshot_times(
                db, remaining_ids, tcgplayer_id, threshold
            )

            cards_to_fetch = [cid for cid in remaining_ids if cid not in db_recent]
            if not cards_to_fetch:
                return stats

            # Load card details
            result = await db.execute(
                select(Card).where(Card.id.in_(cards_to_fetch))
            )
            cards = {c.id: c for c in result.scalars().all()}

            # Initialize adapter
            config = AdapterConfig(
                base_url="https://api.tcgplayer.com",
                api_url="https://api.tcgplayer.com/v1.39.0",
                api_key=settings.tcgplayer_api_key,
                api_secret=settings.tcgplayer_api_secret,
                rate_limit_seconds=0.6,  # 100 requests/min
                timeout_seconds=30.0,
            )
            adapter = TCGPlayerAdapter(config)

            snapshots_to_insert = []
            now = datetime.now(timezone.utc)
            updated_card_ids = []

            for card_id in cards_to_fetch:
                card = cards.get(card_id)
                if not card:
                    continue

                try:
                    price_data = await adapter.fetch_price(
                        card_name=card.name,
                        set_code=card.set_code,
                        collector_number=card.collector_number,
                        scryfall_id=card.scryfall_id,
                    )

                    if price_data and price_data.price > 0:
                        snapshots_to_insert.append({
                            "time": now,
                            "card_id": card_id,
                            "marketplace_id": tcgplayer_id,
                            "condition": CardCondition.NEAR_MINT.value,
                            "is_foil": False,
                            "language": CardLanguage.ENGLISH.value,
                            "price": price_data.price,
                            "price_low": price_data.price_low,
                            "price_mid": price_data.price_mid,
                            "price_high": price_data.price_high,
                            "price_market": price_data.price_market,
                            "currency": "USD",
                            "num_listings": price_data.num_listings,
                            "source": "tcgplayer",
                        })
                        updated_card_ids.append(card_id)
                        stats["cards_fetched"] += 1

                except Exception as e:
                    stats["errors"].append(f"Card {card_id}: {str(e)}")
                    logger.debug("TCGPlayer fetch failed", card_id=card_id, error=str(e))

            # Batch upsert
            if snapshots_to_insert:
                insert_stats = await batch_upsert_snapshots(db, snapshots_to_insert)
                stats["snapshots_created"] = insert_stats["inserted"]

            # Update cache
            if updated_card_ids:
                await cache.mark_updated(updated_card_ids, tcgplayer_id)

        return stats

    except Exception as e:
        logger.exception("TCGPlayer collection error", error=str(e))
        return {**stats, "error": str(e)}

    finally:
        await redis.aclose()
        await engine.dispose()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def collect_manapool_prices(self) -> dict[str, Any]:
    """
    Collect prices from Manapool bulk API.

    Manapool provides a bulk endpoint that returns all prices in one request,
    so we don't need card_ids - we fetch everything and match by Scryfall ID.
    """
    try:
        return run_async(_collect_manapool_async())
    except Exception as e:
        logger.exception("Manapool collection failed", error=str(e))
        raise self.retry(exc=e)


async def _collect_manapool_async() -> dict[str, Any]:
    """Collect Manapool prices using bulk API."""
    session_maker, engine = create_task_session_maker()

    stats = {
        "adapter": "manapool",
        "prices_fetched": 0,
        "snapshots_created": 0,
        "cards_matched": 0,
        "errors": [],
    }

    try:
        from app.services.ingestion.adapters.manapool import ManapoolAdapter

        async with session_maker() as db:
            marketplace_map = await _get_or_create_marketplaces(db)
            manapool_id = marketplace_map.get("manapool")

            if not manapool_id:
                return {**stats, "error": "Manapool marketplace not found"}

            # Initialize adapter
            config = AdapterConfig(
                base_url="https://api.manapool.com",
                api_url="https://api.manapool.com",
                api_key=settings.manapool_api_token,
                rate_limit_seconds=1.0,
                timeout_seconds=60.0,
            )
            adapter = ManapoolAdapter(config)

            # Fetch all prices in one request
            try:
                all_prices = await adapter.fetch_bulk_prices()
                stats["prices_fetched"] = len(all_prices)
            except Exception as e:
                return {**stats, "error": f"Bulk fetch failed: {str(e)}"}

            if not all_prices:
                return stats

            # Build Scryfall ID lookup
            scryfall_ids = [p.get("scryfall_id") for p in all_prices if p.get("scryfall_id")]
            if not scryfall_ids:
                return stats

            result = await db.execute(
                select(Card.id, Card.scryfall_id)
                .where(Card.scryfall_id.in_(scryfall_ids))
            )
            card_lookup = {row.scryfall_id: row.id for row in result}

            # Build snapshots
            snapshots_to_insert = []
            now = datetime.now(timezone.utc)

            for price_data in all_prices:
                scryfall_id = price_data.get("scryfall_id")
                card_id = card_lookup.get(scryfall_id)

                if not card_id:
                    continue

                price_cents = price_data.get("price", 0)
                if price_cents <= 0:
                    continue

                # Manapool prices are in cents
                price_euros = Decimal(price_cents) / 100

                snapshots_to_insert.append({
                    "time": now,
                    "card_id": card_id,
                    "marketplace_id": manapool_id,
                    "condition": CardCondition.NEAR_MINT.value,
                    "is_foil": False,
                    "language": CardLanguage.ENGLISH.value,
                    "price": price_euros,
                    "currency": "EUR",
                    "source": "manapool",
                })
                stats["cards_matched"] += 1

            # Batch upsert (larger batches for bulk data)
            if snapshots_to_insert:
                insert_stats = await batch_upsert_snapshots(
                    db, snapshots_to_insert, batch_size=1000
                )
                stats["snapshots_created"] = insert_stats["inserted"]

        return stats

    except Exception as e:
        logger.exception("Manapool collection error", error=str(e))
        return {**stats, "error": str(e)}

    finally:
        await engine.dispose()


# =============================================================================
# Helper Functions
# =============================================================================

async def _get_or_create_marketplaces(db) -> dict[str, int]:
    """
    Get or create marketplace records, returning {slug: id} mapping.

    Caches the lookup in the session for efficiency.
    """
    result = await db.execute(select(Marketplace))
    existing = {mp.slug: mp.id for mp in result.scalars().all()}

    for slug, (name, base_url, currency) in MARKETPLACE_SLUGS.items():
        if slug not in existing:
            mp = Marketplace(
                name=name,
                slug=slug,
                base_url=base_url,
                is_enabled=True,
                supports_api=True,
                default_currency=currency,
                rate_limit_seconds=1.0,
            )
            db.add(mp)
            await db.flush()
            existing[slug] = mp.id

    return existing


# =============================================================================
# Aggregation Task (Optional)
# =============================================================================

@shared_task
def aggregate_collection_results(results: list[dict]) -> dict[str, Any]:
    """
    Callback task to aggregate results from parallel collection tasks.

    Can be used with chord() if you need to wait for all tasks to complete.
    """
    total_fetched = sum(r.get("cards_fetched", 0) for r in results)
    total_snapshots = sum(r.get("snapshots_created", 0) for r in results)
    total_cache_hits = sum(r.get("cache_hits", 0) for r in results)

    errors = []
    for r in results:
        if r.get("error"):
            errors.append({"adapter": r.get("adapter"), "error": r.get("error")})
        errors.extend(r.get("errors", []))

    return {
        "total_cards_fetched": total_fetched,
        "total_snapshots_created": total_snapshots,
        "total_cache_hits": total_cache_hits,
        "adapters": {r.get("adapter"): r for r in results},
        "errors": errors[:50],  # Limit error list size
    }
