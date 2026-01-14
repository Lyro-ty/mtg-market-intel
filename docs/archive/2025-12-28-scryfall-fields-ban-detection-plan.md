# Scryfall Fields & Ban Detection Implementation Plan

**Status:** ✅ Implemented (2025-12-28)

**Goal:** Add missing Scryfall fields (edhrec_rank, reserved_list, keywords, flavor_text) to the import script and implement ban/legality change detection with notifications.

**Architecture:** Update the Scryfall bulk import to extract 4 additional fields. Add a BAN_CHANGE notification type and create a detection mechanism that compares legalities before/after sync, notifying users who own affected cards.

**Tech Stack:** Python, SQLAlchemy, PostgreSQL, Celery

---

## Task 1: Add Missing Fields to Scryfall Import

**Files:**
- Modify: `backend/app/scripts/import_scryfall.py:104-137` (parse_card_data function)
- Modify: `backend/app/scripts/import_scryfall.py:261-284` (upsert statement)

**Step 1: Update parse_card_data to extract new fields**

Add these fields to the return dict in `parse_card_data()` (after line 136):

```python
def parse_card_data(card: dict) -> dict:
    """Parse Scryfall card data into database model format."""
    # Handle double-faced cards
    image_uris = card.get("image_uris", {})
    if not image_uris and card.get("card_faces"):
        image_uris = card["card_faces"][0].get("image_uris", {})

    # Parse colors
    colors = card.get("colors", [])
    color_identity = card.get("color_identity", [])
    legalities = card.get("legalities", {})
    keywords = card.get("keywords", [])

    return {
        "scryfall_id": card.get("id"),
        "oracle_id": card.get("oracle_id"),
        "name": card.get("name", "")[:255],
        "set_code": card.get("set", "").upper(),
        "set_name": card.get("set_name"),
        "collector_number": card.get("collector_number", "")[:20],
        "rarity": card.get("rarity"),
        "mana_cost": card.get("mana_cost"),
        "cmc": card.get("cmc"),
        "type_line": card.get("type_line"),
        "oracle_text": card.get("oracle_text"),
        "colors": json.dumps(colors) if colors else None,
        "color_identity": json.dumps(color_identity) if color_identity else None,
        "power": card.get("power"),
        "toughness": card.get("toughness"),
        "legalities": json.dumps(legalities) if legalities else None,
        "image_url": image_uris.get("normal"),
        "image_url_small": image_uris.get("small"),
        "image_url_large": image_uris.get("large") or image_uris.get("png"),
        "released_at": parse_released_at(card.get("released_at")),
        # New fields
        "edhrec_rank": card.get("edhrec_rank"),
        "reserved_list": card.get("reserved", False),
        "keywords": json.dumps(keywords) if keywords else None,
        "flavor_text": card.get("flavor_text"),
    }
```

**Step 2: Update the upsert on_conflict_do_update**

Find the `on_conflict_do_update` block (around line 263-282) and add the new fields:

```python
stmt = stmt.on_conflict_do_update(
    index_elements=["scryfall_id"],
    set_={
        "name": stmt.excluded.name,
        "set_name": stmt.excluded.set_name,
        "rarity": stmt.excluded.rarity,
        "mana_cost": stmt.excluded.mana_cost,
        "cmc": stmt.excluded.cmc,
        "type_line": stmt.excluded.type_line,
        "oracle_text": stmt.excluded.oracle_text,
        "colors": stmt.excluded.colors,
        "color_identity": stmt.excluded.color_identity,
        "power": stmt.excluded.power,
        "toughness": stmt.excluded.toughness,
        "legalities": stmt.excluded.legalities,
        "image_url": stmt.excluded.image_url,
        "image_url_small": stmt.excluded.image_url_small,
        "image_url_large": stmt.excluded.image_url_large,
        # New fields
        "edhrec_rank": stmt.excluded.edhrec_rank,
        "reserved_list": stmt.excluded.reserved_list,
        "keywords": stmt.excluded.keywords,
        "flavor_text": stmt.excluded.flavor_text,
        "updated_at": func.now(),
    },
)
```

**Step 3: Verify syntax**

Run: `python3 -m py_compile backend/app/scripts/import_scryfall.py`
Expected: No output (successful compilation)

**Step 4: Commit**

```bash
git add backend/app/scripts/import_scryfall.py
git commit -m "feat: add edhrec_rank, reserved_list, keywords, flavor_text to Scryfall import"
```

---

## Task 2: Add BAN_CHANGE Notification Type

**Files:**
- Modify: `backend/app/models/notification.py:16-24` (NotificationType enum)

**Step 1: Add BAN_CHANGE to NotificationType enum**

```python
class NotificationType(str, Enum):
    """Types of notifications that can be sent to users."""

    PRICE_ALERT = "price_alert"      # Want list target hit
    PRICE_SPIKE = "price_spike"      # Card spiked in price
    PRICE_DROP = "price_drop"        # Card dropped in price
    BAN_CHANGE = "ban_change"        # Card banned/unbanned in a format
    MILESTONE = "milestone"          # Collection milestone achieved
    SYSTEM = "system"                # System announcements
    EDUCATIONAL = "educational"      # Tips and educational content
```

**Step 2: Verify syntax**

Run: `python3 -m py_compile backend/app/models/notification.py`
Expected: No output

**Step 3: Commit**

```bash
git add backend/app/models/notification.py
git commit -m "feat: add BAN_CHANGE notification type"
```

---

## Task 3: Add Ban Change Notification Helper

**Files:**
- Modify: `backend/app/services/notifications.py` (add new function after create_milestone_notification)

**Step 1: Add create_ban_change_notification function**

Add after line 228 (after create_milestone_notification):

```python
async def create_ban_change_notification(
    db: AsyncSession,
    user_id: int,
    card_id: int,
    card_name: str,
    format_name: str,
    old_status: str,
    new_status: str,
) -> Optional[Notification]:
    """
    Create a ban/unban notification when a card's legality changes.

    Args:
        db: Async database session
        user_id: Target user's ID
        card_id: Card that changed
        card_name: Name of the card
        format_name: Format where legality changed (e.g., "modern", "commander")
        old_status: Previous legality status
        new_status: New legality status

    Returns:
        The created Notification object, or None if duplicate
    """
    # Determine if this is a ban, unban, or restriction change
    if new_status == "banned":
        action = "BANNED"
        priority = NotificationPriority.URGENT
    elif old_status == "banned" and new_status == "legal":
        action = "UNBANNED"
        priority = NotificationPriority.HIGH
    elif new_status == "restricted":
        action = "RESTRICTED"
        priority = NotificationPriority.HIGH
    else:
        action = f"changed from {old_status} to {new_status}"
        priority = NotificationPriority.MEDIUM

    title = f"{card_name} {action} in {format_name.title()}"
    message = (
        f"{card_name} has been {action.lower()} in {format_name.title()}. "
        f"Previous status: {old_status}, New status: {new_status}."
    )

    extra_data = {
        "card_name": card_name,
        "format": format_name,
        "old_status": old_status,
        "new_status": new_status,
    }

    return await create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.BAN_CHANGE,
        title=title,
        message=message,
        priority=priority,
        card_id=card_id,
        extra_data=extra_data,
    )
```

**Step 2: Verify syntax**

Run: `python3 -m py_compile backend/app/services/notifications.py`
Expected: No output

**Step 3: Commit**

```bash
git add backend/app/services/notifications.py
git commit -m "feat: add create_ban_change_notification helper"
```

---

## Task 4: Create Ban Detection Task

**Files:**
- Create: `backend/app/tasks/ban_detection.py`

**Step 1: Create the ban detection task file**

```python
"""
Ban/legality change detection task.

Compares card legalities before and after sync to detect bans, unbans,
and restriction changes. Notifies users who own affected cards.
"""
import json
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
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
```

**Step 2: Register the task in celery_app**

Add import to `backend/app/tasks/__init__.py` if it exists, or ensure the task is discoverable.

**Step 3: Verify syntax**

Run: `python3 -m py_compile backend/app/tasks/ban_detection.py`
Expected: No output

**Step 4: Commit**

```bash
git add backend/app/tasks/ban_detection.py
git commit -m "feat: add ban/legality change detection task"
```

---

## Task 5: Run Scryfall Import to Populate New Fields

**Step 1: Rebuild backend container**

```bash
docker compose up -d --build backend
```

**Step 2: Run the Scryfall import**

```bash
docker compose exec backend python -m app.scripts.import_scryfall --type default_cards
```

Expected: Import completes with ~30k cards processed

**Step 3: Verify new fields are populated**

```bash
docker compose exec db psql -U dualcaster_user -d dualcaster_deals -c "
SELECT name, edhrec_rank, reserved_list,
       keywords IS NOT NULL as has_keywords,
       flavor_text IS NOT NULL as has_flavor
FROM cards
WHERE edhrec_rank IS NOT NULL
ORDER BY edhrec_rank
LIMIT 5;
"
```

Expected: Shows cards with EDHREC ranks (Sol Ring should be rank 1)

**Step 4: Commit any changes and push**

```bash
git add -A
git commit -m "chore: verify Scryfall import with new fields"
git push origin main
```

---

## Summary

After completing all tasks:

1. **New fields populated:** edhrec_rank, reserved_list, keywords, flavor_text
2. **Ban detection ready:** BAN_CHANGE notification type and detection task
3. **Usage:** Before Scryfall sync, call `capture_legalities_before_sync()`, then after sync call `detect_ban_changes.delay(old_legalities_json)`

Future enhancement: Integrate ban detection into the scheduled Scryfall sync task automatically.
