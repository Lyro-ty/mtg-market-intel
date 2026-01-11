"""
Ban/legality change detection task.

Compares card legalities before and after sync to detect bans, unbans,
and restriction changes. Notifies users who own affected cards.
"""
import json

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.card import Card
from app.models.inventory import InventoryItem
from app.services.notifications import create_ban_change_notification
from app.tasks.celery_app import celery_app

logger = structlog.get_logger()

# Formats we care about for ban notifications
TRACKED_FORMATS = [
    "standard",
    "pioneer",
    "modern",
    "legacy",
    "vintage",
    "commander",
    "pauper",
    "brawl",
]


async def _detect_legality_changes(
    db: AsyncSession,
    old_legalities: dict[int, dict],
    new_legalities: dict[int, dict],
) -> list[dict]:
    """
    Compare old and new legalities to find changes.

    Returns list of dicts with card_id, card_name, format, old_status, new_status.
    """
    changes = []

    for card_id, new_legal in new_legalities.items():
        old_legal = old_legalities.get(card_id, {})

        if not old_legal:
            continue  # New card, skip

        # Get card name for notifications
        card = await db.get(Card, card_id)
        if not card:
            continue

        for format_name in TRACKED_FORMATS:
            old_status = old_legal.get(format_name, "not_legal")
            new_status = new_legal.get(format_name, "not_legal")

            if old_status != new_status:
                # Only notify for significant changes
                if new_status in ("banned", "restricted") or old_status == "banned":
                    changes.append({
                        "card_id": card_id,
                        "card_name": card.name,
                        "format": format_name,
                        "old_status": old_status,
                        "new_status": new_status,
                    })
                    logger.info(
                        "Legality change detected",
                        card_name=card.name,
                        format=format_name,
                        old_status=old_status,
                        new_status=new_status,
                    )

    return changes


async def _notify_affected_users(
    db: AsyncSession,
    changes: list[dict],
) -> int:
    """
    Notify users who own cards with legality changes.

    Returns count of notifications sent.
    """
    notification_count = 0

    for change in changes:
        # Find users who own this card
        result = await db.execute(
            select(InventoryItem.user_id).where(
                InventoryItem.card_id == change["card_id"]
            ).distinct()
        )
        user_ids = [row[0] for row in result.all()]

        for user_id in user_ids:
            notification = await create_ban_change_notification(
                db=db,
                user_id=user_id,
                card_id=change["card_id"],
                card_name=change["card_name"],
                format_name=change["format"],
                old_status=change["old_status"],
                new_status=change["new_status"],
            )
            if notification:
                notification_count += 1

        await db.commit()

    return notification_count


@celery_app.task(name="detect_ban_changes")
def detect_ban_changes(old_legalities_json: str) -> dict:
    """
    Detect ban/legality changes and notify affected users.

    Args:
        old_legalities_json: JSON string of {card_id: legalities_dict}
                            captured before sync

    Returns:
        Dict with changes_found and notifications_sent counts
    """
    import asyncio

    async def _run():
        old_legalities = json.loads(old_legalities_json)
        # Convert string keys back to int
        old_legalities = {int(k): v for k, v in old_legalities.items()}

        async with async_session_maker() as db:
            # Get current legalities for cards we're tracking
            result = await db.execute(
                select(Card.id, Card.legalities).where(
                    Card.id.in_(list(old_legalities.keys()))
                )
            )

            new_legalities = {}
            for card_id, legalities_str in result.all():
                if legalities_str:
                    try:
                        new_legalities[card_id] = json.loads(legalities_str)
                    except json.JSONDecodeError:
                        continue

            # Find changes
            changes = await _detect_legality_changes(db, old_legalities, new_legalities)

            if not changes:
                logger.info("No legality changes detected")
                return {"changes_found": 0, "notifications_sent": 0}

            # Notify users
            notifications_sent = await _notify_affected_users(db, changes)

            logger.info(
                "Ban detection complete",
                changes_found=len(changes),
                notifications_sent=notifications_sent,
            )

            return {
                "changes_found": len(changes),
                "notifications_sent": notifications_sent,
            }

    return asyncio.run(_run())


async def capture_legalities_before_sync() -> str:
    """
    Capture current legalities for all cards before sync.

    Call this before running Scryfall import, then pass the result
    to detect_ban_changes after import completes.

    Returns:
        JSON string of {card_id: legalities_dict}
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(Card.id, Card.legalities).where(
                Card.legalities.isnot(None)
            )
        )

        legalities = {}
        for card_id, legalities_str in result.all():
            if legalities_str:
                try:
                    legalities[card_id] = json.loads(legalities_str)
                except json.JSONDecodeError:
                    continue

        return json.dumps(legalities)
