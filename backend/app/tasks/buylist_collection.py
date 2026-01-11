"""
Buylist price collection task.

Collects buylist prices from vendors like Card Kingdom.
Runs daily at 6 AM since buylist prices change slowly.
"""
from datetime import datetime, timezone
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select, and_

from app.models import Card, PriceSnapshot, InventoryItem, BuylistSnapshot
from app.services.ingestion.adapters.cardkingdom_buylist import CardKingdomBuylistAdapter
from app.tasks.utils import create_task_session_maker, run_async

logger = structlog.get_logger()


@shared_task(bind=True, max_retries=2, default_retry_delay=600)
def collect_buylist_prices(self, batch_size: int = 200) -> dict[str, Any]:
    """
    Collect buylist prices from Card Kingdom.

    Prioritizes:
    1. Cards in user inventories (helps users know selling prices)
    2. High-value cards ($5+) that are commonly bought

    Args:
        batch_size: Maximum cards to process per run.
                   With 2-second rate limit, 200 cards takes ~7 minutes.

    Returns:
        Summary of buylist collection results.
    """
    return run_async(_collect_buylist_prices_async(batch_size))


async def _collect_buylist_prices_async(batch_size: int = 200) -> dict[str, Any]:
    """Async implementation of buylist price collection."""
    logger.info("Starting buylist price collection", batch_size=batch_size)

    session_maker, engine = create_task_session_maker()
    adapter = CardKingdomBuylistAdapter()

    stats = {
        "cards_processed": 0,
        "prices_collected": 0,
        "errors": 0,
        "inventory_cards": 0,
        "high_value_cards": 0,
    }

    try:
        async with session_maker() as db:
            # PRIORITY 1: Cards in user inventories
            inventory_query = (
                select(Card.id, Card.name, Card.set_code)
                .join(InventoryItem, InventoryItem.card_id == Card.id)
                .distinct()
                .limit(batch_size // 2)  # Half the budget for inventory
            )
            result = await db.execute(inventory_query)
            inventory_cards = list(result.all())
            stats["inventory_cards"] = len(inventory_cards)

            inventory_card_ids = {c.id for c in inventory_cards}

            # PRIORITY 2: High-value cards ($5+) not in inventory
            remaining_budget = batch_size - len(inventory_cards)
            high_value_cards = []

            if remaining_budget > 0:
                # Get cards with recent price snapshots >= $5
                high_value_query = (
                    select(Card.id, Card.name, Card.set_code)
                    .join(
                        PriceSnapshot,
                        and_(
                            PriceSnapshot.card_id == Card.id,
                            PriceSnapshot.price >= 5.0,
                        )
                    )
                    .where(Card.id.notin_(inventory_card_ids) if inventory_card_ids else True)
                    .distinct()
                    .limit(remaining_budget)
                )
                result = await db.execute(high_value_query)
                high_value_cards = list(result.all())
                stats["high_value_cards"] = len(high_value_cards)

            # Combine all cards to process
            cards_to_process = list(inventory_cards) + list(high_value_cards)
            logger.info(
                "Cards selected for buylist collection",
                total=len(cards_to_process),
                inventory=len(inventory_cards),
                high_value=len(high_value_cards),
            )

            # Commit after query phase to release transaction before API calls
            await db.commit()

            # Collect buylist prices
            now = datetime.now(timezone.utc)

            for card_id, card_name, set_code in cards_to_process:
                try:
                    prices = await adapter.get_buylist_prices(card_name, set_code)

                    for price_data in prices:
                        if price_data.price <= 0:
                            continue

                        # Create buylist snapshot
                        snapshot = BuylistSnapshot(
                            time=now,
                            card_id=card_id,
                            vendor=price_data.vendor,
                            condition=price_data.condition,
                            is_foil=price_data.is_foil,
                            price=price_data.price,
                            credit_price=price_data.credit_price,
                            quantity=price_data.quantity,
                        )
                        db.add(snapshot)
                        stats["prices_collected"] += 1

                    stats["cards_processed"] += 1

                    # Commit in batches of 50
                    if stats["cards_processed"] % 50 == 0:
                        await db.commit()
                        logger.debug(
                            "Buylist batch committed",
                            processed=stats["cards_processed"],
                            collected=stats["prices_collected"],
                        )

                except Exception as e:
                    logger.warning(
                        "Error collecting buylist for card",
                        card_id=card_id,
                        card_name=card_name,
                        error=str(e),
                    )
                    stats["errors"] += 1

            # Final commit
            await db.commit()

    except Exception as e:
        logger.error("Buylist collection failed", error=str(e))
        raise

    finally:
        await adapter.close()
        await engine.dispose()

    logger.info("Buylist collection complete", **stats)
    return stats


@shared_task(bind=True)
def collect_buylist_for_card(self, card_id: int) -> dict[str, Any]:
    """
    Collect buylist prices for a specific card.

    Used for on-demand buylist lookup when viewing a card.
    """
    return run_async(_collect_buylist_for_card_async(card_id))


async def _collect_buylist_for_card_async(card_id: int) -> dict[str, Any]:
    """Collect buylist prices for a single card."""
    session_maker, engine = create_task_session_maker()
    adapter = CardKingdomBuylistAdapter()

    try:
        async with session_maker() as db:
            # Get card info
            result = await db.execute(
                select(Card.name, Card.set_code).where(Card.id == card_id)
            )
            card = result.first()

            if not card:
                return {"error": "Card not found", "card_id": card_id}

            card_name, set_code = card

            # Collect buylist prices
            prices = await adapter.get_buylist_prices(card_name, set_code)

            now = datetime.now(timezone.utc)
            saved = 0

            for price_data in prices:
                if price_data.price <= 0:
                    continue

                snapshot = BuylistSnapshot(
                    time=now,
                    card_id=card_id,
                    vendor=price_data.vendor,
                    condition=price_data.condition,
                    is_foil=price_data.is_foil,
                    price=price_data.price,
                    credit_price=price_data.credit_price,
                    quantity=price_data.quantity,
                )
                db.add(snapshot)
                saved += 1

            await db.commit()

            return {
                "card_id": card_id,
                "card_name": card_name,
                "prices_saved": saved,
            }

    finally:
        await adapter.close()
        await engine.dispose()
