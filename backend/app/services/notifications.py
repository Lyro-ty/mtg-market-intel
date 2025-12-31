"""
Notification service for creating and managing notifications with deduplication.

Provides functions for:
- Creating notifications with automatic deduplication (24h window)
- Price alert notifications when targets are hit
- Milestone achievement notifications
- Unread count and breakdown retrieval
- Cleanup of expired notifications
"""
import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.notification import Notification, NotificationPriority, NotificationType

logger = structlog.get_logger()

# Deduplication window in hours
DEDUP_WINDOW_HOURS = 24


def generate_dedup_hash(
    user_id: int,
    type: str,
    card_id: Optional[int],
    title: str
) -> str:
    """
    Generate a deduplication hash for notification uniqueness.

    Creates a SHA-256 hash from the combination of user_id, notification type,
    card_id (if any), and title. This ensures that duplicate notifications
    with the same key components are not created within the dedup window.

    Args:
        user_id: The user's ID
        type: Notification type string
        card_id: Optional card ID for card-related notifications
        title: Notification title

    Returns:
        A 64-character hex string hash
    """
    key = f"{user_id}:{type}:{card_id or 'none'}:{title}"
    return hashlib.sha256(key.encode()).hexdigest()[:64]


async def create_notification(
    db: AsyncSession,
    user_id: int,
    type: NotificationType,
    title: str,
    message: str,
    priority: NotificationPriority = NotificationPriority.MEDIUM,
    card_id: Optional[int] = None,
    extra_data: Optional[dict] = None,
    expires_at: Optional[datetime] = None,
) -> Optional[Notification]:
    """
    Create a notification with deduplication.

    Generates a dedup_hash from (user_id, type, card_id, title). If a notification
    with the same hash exists from the last 24 hours, the new notification is
    skipped to prevent notification spam.

    Args:
        db: Async database session
        user_id: Target user's ID
        type: Type of notification (price_alert, milestone, etc.)
        title: Notification title (max 200 chars)
        message: Full notification message
        priority: Notification priority level (default: MEDIUM)
        card_id: Optional related card ID
        extra_data: Optional JSON extra data
        expires_at: Optional expiration datetime

    Returns:
        The created Notification object, or None if a duplicate exists
    """
    # Generate dedup hash
    dedup_hash = generate_dedup_hash(user_id, type.value, card_id, title)

    # Check for existing notification with same hash in dedup window
    dedup_cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_WINDOW_HOURS)

    existing_query = select(Notification).where(
        Notification.dedup_hash == dedup_hash,
        Notification.created_at >= dedup_cutoff,
    )
    result = await db.execute(existing_query)
    existing = result.scalar_one_or_none()

    if existing:
        logger.debug(
            "Skipping duplicate notification",
            user_id=user_id,
            type=type.value,
            title=title,
            dedup_hash=dedup_hash,
        )
        return None

    # Create new notification
    notification = Notification(
        user_id=user_id,
        type=type,
        priority=priority,
        title=title,
        message=message,
        card_id=card_id,
        extra_data=extra_data,
        expires_at=expires_at,
        dedup_hash=dedup_hash,
        read=False,
    )

    db.add(notification)
    await db.flush()
    await db.refresh(notification)

    logger.info(
        "Created notification",
        notification_id=notification.id,
        user_id=user_id,
        type=type.value,
        priority=priority.value,
        title=title,
    )

    return notification


async def create_price_alert(
    db: AsyncSession,
    user_id: int,
    card_id: int,
    card_name: str,
    current_price: Decimal,
    target_price: Decimal,
) -> Optional[Notification]:
    """
    Create a price alert notification when a target price is hit.

    Formats a user-friendly notification message indicating whether the
    card price dropped to or below their target.

    Args:
        db: Async database session
        user_id: Target user's ID
        card_id: Card that hit the target
        card_name: Name of the card for display
        current_price: Current market price
        target_price: User's target price

    Returns:
        The created Notification object, or None if duplicate
    """
    title = f"Price Alert: {card_name}"
    message = (
        f"{card_name} has reached your target price! "
        f"Current price: ${current_price:.2f} (Target: ${target_price:.2f})"
    )

    extra_data = {
        "card_name": card_name,
        "current_price": str(current_price),
        "target_price": str(target_price),
    }

    return await create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.PRICE_ALERT,
        title=title,
        message=message,
        priority=NotificationPriority.HIGH,
        card_id=card_id,
        extra_data=extra_data,
    )


async def create_milestone_notification(
    db: AsyncSession,
    user_id: int,
    milestone_type: str,
    milestone_name: str,
    threshold: int,
) -> Optional[Notification]:
    """
    Create a milestone achievement notification.

    Used to congratulate users on reaching collection milestones
    (e.g., 100 cards collected, $1000 collection value).

    Args:
        db: Async database session
        user_id: Target user's ID
        milestone_type: Type of milestone (e.g., "cards_collected", "collection_value")
        milestone_name: Human-readable milestone name
        threshold: The threshold value that was reached

    Returns:
        The created Notification object, or None if duplicate
    """
    title = f"Milestone Achieved: {milestone_name}"
    message = f"Congratulations! You've reached {threshold:,} for {milestone_name}!"

    extra_data = {
        "milestone_type": milestone_type,
        "milestone_name": milestone_name,
        "threshold": threshold,
    }

    return await create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.MILESTONE,
        title=title,
        message=message,
        priority=NotificationPriority.MEDIUM,
        extra_data=extra_data,
    )


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


async def get_unread_count(
    db: AsyncSession,
    user_id: int,
) -> tuple[int, dict[str, int]]:
    """
    Get the count of unread notifications and breakdown by type.

    Returns both the total unread count and a dictionary with counts
    per notification type for badge display purposes.

    Args:
        db: Async database session
        user_id: User's ID

    Returns:
        Tuple of (total_unread_count, breakdown_by_type_dict)
    """
    # Query for unread count by type
    query = (
        select(Notification.type, func.count(Notification.id))
        .where(
            Notification.user_id == user_id,
            Notification.read == False,  # noqa: E712 - SQLAlchemy needs == False
        )
        .group_by(Notification.type)
    )

    result = await db.execute(query)
    rows = result.all()

    # Build breakdown dict and calculate total
    breakdown: dict[str, int] = {}
    total = 0

    for notification_type, count in rows:
        # Handle both enum and string type values
        type_key = notification_type.value if hasattr(notification_type, 'value') else str(notification_type)
        breakdown[type_key] = count
        total += count

    logger.debug(
        "Retrieved unread notification count",
        user_id=user_id,
        total=total,
        breakdown=breakdown,
    )

    return total, breakdown


class NotificationService:
    """
    Service wrapper for notification functions.

    Provides a class-based interface for sending notifications.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        card_id: Optional[int] = None,
        extra_data: Optional[dict] = None,
    ) -> Optional[Notification]:
        """
        Send a notification to a user.

        Args:
            user_id: Target user's ID
            notification_type: Type string (converted to NotificationType enum)
            title: Notification title
            message: Notification message
            priority: Priority level (default: MEDIUM)
            card_id: Optional related card ID
            extra_data: Optional additional data

        Returns:
            The created Notification object, or None if duplicate
        """
        # Map string type to enum, default to SYSTEM if not recognized
        type_map = {
            "price_alert": NotificationType.PRICE_ALERT,
            "price_spike": NotificationType.PRICE_SPIKE,
            "price_drop": NotificationType.PRICE_DROP,
            "ban_change": NotificationType.BAN_CHANGE,
            "milestone": NotificationType.MILESTONE,
            "system": NotificationType.SYSTEM,
            "educational": NotificationType.EDUCATIONAL,
            "connection_request": NotificationType.SYSTEM,  # Map connection_request to SYSTEM
        }
        notification_type_enum = type_map.get(notification_type.lower(), NotificationType.SYSTEM)

        return await create_notification(
            db=self.db,
            user_id=user_id,
            type=notification_type_enum,
            title=title,
            message=message,
            priority=priority,
            card_id=card_id,
            extra_data=extra_data,
        )


async def cleanup_expired_notifications(
    db: AsyncSession,
) -> int:
    """
    Delete all expired notifications from the database.

    Notifications with an expires_at timestamp in the past are removed.
    This should be called periodically (e.g., via a scheduled task).

    Args:
        db: Async database session

    Returns:
        The number of notifications deleted
    """
    now = datetime.now(timezone.utc)

    # Delete expired notifications
    delete_query = delete(Notification).where(
        Notification.expires_at.isnot(None),
        Notification.expires_at < now,
    )

    result = await db.execute(delete_query)
    deleted_count = result.rowcount

    if deleted_count > 0:
        logger.info(
            "Cleaned up expired notifications",
            deleted_count=deleted_count,
        )

    return deleted_count
