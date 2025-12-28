"""
Want list price check task.

Periodically checks all want list items with alerts enabled
and creates notifications when target prices are hit.
"""
from decimal import Decimal
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.models import WantListItem, PriceSnapshot
from app.services.notifications import create_price_alert
from app.tasks.utils import create_task_session_maker, run_async

logger = structlog.get_logger()


@shared_task(name="check_want_list_prices")
def check_want_list_prices() -> dict[str, Any]:
    """
    Check all want list items with alert_enabled=True.

    For each item where current_price <= target_price:
    - Create a price alert notification (using notification service)
    - Only notify once per 24h (handled by deduplication in notification service)

    Runs every 15 minutes via celery beat.

    Returns:
        Summary dict with items_checked and alerts_created counts.
    """
    return run_async(_check_want_list_prices_async())


async def _check_want_list_prices_async() -> dict[str, Any]:
    """Async implementation of want list price check."""
    logger.info("Starting want list price check")

    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Get all want list items with alerts enabled
            query = (
                select(WantListItem)
                .options(joinedload(WantListItem.card))
                .where(WantListItem.alert_enabled == True)  # noqa: E712
            )
            result = await db.execute(query)
            want_list_items = result.scalars().unique().all()

            items_checked = 0
            alerts_created = 0

            for item in want_list_items:
                items_checked += 1

                # Get the latest price snapshot for this card
                # Using subquery to get most recent price
                latest_price_query = (
                    select(PriceSnapshot.price)
                    .where(PriceSnapshot.card_id == item.card_id)
                    .order_by(PriceSnapshot.time.desc())
                    .limit(1)
                )
                price_result = await db.execute(latest_price_query)
                current_price_row = price_result.scalar_one_or_none()

                if current_price_row is None:
                    # No price data available for this card
                    logger.debug(
                        "No price data for want list card",
                        card_id=item.card_id,
                        user_id=item.user_id,
                    )
                    continue

                current_price = Decimal(str(current_price_row))

                # Check if current price is at or below target
                if current_price <= item.target_price:
                    # Get card name for notification
                    card_name = item.card.name if item.card else f"Card #{item.card_id}"

                    notification = await create_price_alert(
                        db=db,
                        user_id=item.user_id,
                        card_id=item.card_id,
                        card_name=card_name,
                        current_price=current_price,
                        target_price=item.target_price,
                    )

                    if notification:
                        alerts_created += 1
                        logger.info(
                            "Created price alert notification",
                            user_id=item.user_id,
                            card_id=item.card_id,
                            card_name=card_name,
                            current_price=str(current_price),
                            target_price=str(item.target_price),
                        )

            # Commit all notifications
            await db.commit()

            summary = {
                "items_checked": items_checked,
                "alerts_created": alerts_created,
            }

            logger.info(
                "Want list price check completed",
                **summary,
            )

            return summary
    finally:
        await engine.dispose()
