"""
Enhanced notification service for social trading features.

Provides centralized notification creation with:
- Category-based classification
- Real-time WebSocket delivery via Redis pub/sub
- Support for various notification types (trades, messages, social, etc.)
"""
import json
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notification import Notification, NotificationPriority, NotificationType

logger = structlog.get_logger()


# =============================================================================
# Notification Type to Category Mapping
# =============================================================================

# Maps notification types to their categories for organization and filtering
NOTIFICATION_TYPE_CATEGORIES: dict[str, str] = {
    # Trades category
    "trade_proposal": "trades",
    "trade_accepted": "trades",
    "trade_declined": "trades",
    "trade_countered": "trades",
    "trade_completed": "trades",
    "trade_cancelled": "trades",
    "trade_expired": "trades",

    # Messages category
    "message_received": "messages",
    "thread_message": "messages",

    # Social category
    "connection_request": "social",
    "connection_accepted": "social",
    "endorsement_received": "social",
    "profile_view": "social",
    "favorite_added": "social",

    # Discovery category
    "suggested_trader": "discovery",
    "want_list_match": "discovery",
    "compatible_inventory": "discovery",

    # Achievements category
    "achievement_unlocked": "achievements",
    "frame_unlocked": "achievements",
    "badge_earned": "achievements",
    "milestone": "achievements",

    # System category
    "system_announcement": "system",
    "account_update": "system",
    "system": "system",
    "educational": "system",

    # Price alerts (mapped to system for now, but could be separate)
    "price_alert": "system",
    "price_spike": "system",
    "price_drop": "system",
    "ban_change": "system",
}

# Default category icons for UI display
CATEGORY_ICONS: dict[str, str] = {
    "trades": "exchange",
    "messages": "mail",
    "social": "users",
    "discovery": "search",
    "achievements": "trophy",
    "system": "bell",
}


def get_category_for_type(notification_type: str) -> str:
    """
    Get the category for a given notification type.

    Args:
        notification_type: The notification type string

    Returns:
        Category string (trades, messages, social, discovery, achievements, system)
    """
    return NOTIFICATION_TYPE_CATEGORIES.get(notification_type, "system")


def get_icon_for_type(notification_type: str) -> str:
    """
    Get the icon name for a given notification type.

    Args:
        notification_type: The notification type string

    Returns:
        Icon name string for UI display
    """
    category = get_category_for_type(notification_type)
    return CATEGORY_ICONS.get(category, "bell")


# =============================================================================
# Notification Service Class
# =============================================================================

class NotificationService:
    """
    Service for creating and managing enhanced notifications.

    Provides:
    - Notification creation with category classification
    - Real-time delivery via Redis pub/sub
    - Type-to-category mapping
    """

    def __init__(self, db: AsyncSession, redis: Optional[Redis] = None):
        """
        Initialize the notification service.

        Args:
            db: AsyncSession for database operations
            redis: Optional Redis client for real-time delivery
        """
        self.db = db
        self._redis = redis

    async def get_redis(self) -> Redis:
        """Get or create Redis client for pub/sub."""
        if self._redis is None:
            self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def create_notification(
        self,
        user_id: int,
        type: str,
        title: str,
        body: str,
        action_url: Optional[str] = None,
        metadata: Optional[dict] = None,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        card_id: Optional[int] = None,
        expires_at: Optional[datetime] = None,
        send_realtime: bool = True,
    ) -> Notification:
        """
        Create a notification and optionally send it in real-time.

        Args:
            user_id: Target user's ID
            type: Notification type string (e.g., 'trade_proposal', 'message_received')
            title: Short notification title
            body: Full notification message
            action_url: Optional URL for notification click action
            metadata: Optional JSON metadata
            priority: Notification priority level
            card_id: Optional related card ID
            expires_at: Optional expiration datetime
            send_realtime: Whether to push via WebSocket (default True)

        Returns:
            The created Notification object
        """
        # Map custom type to NotificationType enum
        # For types that don't exist in the enum, use SYSTEM
        type_enum = self._map_type_to_enum(type)

        # Build extra_data from metadata and action_url
        extra_data = metadata.copy() if metadata else {}
        if action_url:
            extra_data["action_url"] = action_url
        extra_data["notification_type"] = type  # Store original type for category mapping

        # Create the notification
        notification = Notification(
            user_id=user_id,
            type=type_enum,
            priority=priority,
            title=title,
            message=body,
            card_id=card_id,
            extra_data=extra_data if extra_data else None,
            expires_at=expires_at,
            read=False,
        )

        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)

        logger.info(
            "Created notification",
            notification_id=notification.id,
            user_id=user_id,
            type=type,
            category=get_category_for_type(type),
            title=title,
        )

        # Send real-time notification if requested
        if send_realtime:
            await self.send_realtime(user_id, self._notification_to_dict(notification, type))

        return notification

    def _map_type_to_enum(self, type_str: str) -> NotificationType:
        """Map a type string to NotificationType enum."""
        # Direct enum matches
        type_map = {
            "price_alert": NotificationType.PRICE_ALERT,
            "price_spike": NotificationType.PRICE_SPIKE,
            "price_drop": NotificationType.PRICE_DROP,
            "ban_change": NotificationType.BAN_CHANGE,
            "milestone": NotificationType.MILESTONE,
            "system": NotificationType.SYSTEM,
            "educational": NotificationType.EDUCATIONAL,
        }
        return type_map.get(type_str.lower(), NotificationType.SYSTEM)

    def _notification_to_dict(self, notification: Notification, original_type: str) -> dict:
        """Convert notification to dict for real-time delivery."""
        extra = notification.extra_data or {}
        return {
            "id": notification.id,
            "type": original_type,
            "category": get_category_for_type(original_type),
            "title": notification.title,
            "body": notification.message,
            "icon": get_icon_for_type(original_type),
            "action_url": extra.get("action_url"),
            "metadata": {k: v for k, v in extra.items() if k not in ("action_url", "notification_type")},
            "read_at": None,
            "created_at": notification.created_at.isoformat() if notification.created_at else datetime.now(timezone.utc).isoformat(),
        }

    async def send_realtime(self, user_id: int, notification: dict) -> bool:
        """
        Send a notification via Redis pub/sub for real-time delivery.

        Args:
            user_id: Target user's ID
            notification: Notification data dict

        Returns:
            True if published successfully
        """
        try:
            redis = await self.get_redis()
            channel = f"channel:notifications:user:{user_id}"

            message = {
                "type": "notification",
                "notification_type": notification.get("type", "system"),
                **notification,
            }

            await redis.publish(channel, json.dumps(message))

            logger.debug(
                "Published real-time notification",
                user_id=user_id,
                channel=channel,
                notification_type=notification.get("type"),
            )

            return True
        except Exception as e:
            logger.warning(
                "Failed to send real-time notification",
                user_id=user_id,
                error=str(e),
            )
            return False

    @staticmethod
    def get_category_for_type(notification_type: str) -> str:
        """Static method to get category for a notification type."""
        return get_category_for_type(notification_type)


# =============================================================================
# Helper Functions for Common Notification Types
# =============================================================================

async def create_trade_notification(
    db: AsyncSession,
    user_id: int,
    trade_id: int,
    notification_type: str,
    title: str,
    body: str,
    initiator_username: str,
    redis: Optional[Redis] = None,
) -> Notification:
    """
    Create a trade-related notification.

    Args:
        db: Database session
        user_id: Target user's ID
        trade_id: Related trade ID
        notification_type: One of trade_proposal, trade_accepted, etc.
        title: Notification title
        body: Notification body
        initiator_username: Username of the person who triggered the action
        redis: Optional Redis client for real-time

    Returns:
        Created Notification
    """
    service = NotificationService(db, redis)
    return await service.create_notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        body=body,
        action_url=f"/trades/{trade_id}",
        metadata={
            "trade_id": trade_id,
            "initiator_username": initiator_username,
        },
        priority=NotificationPriority.HIGH,
    )


async def create_message_notification(
    db: AsyncSession,
    user_id: int,
    thread_id: int,
    sender_username: str,
    message_preview: str,
    redis: Optional[Redis] = None,
) -> Notification:
    """
    Create a message notification.

    Args:
        db: Database session
        user_id: Target user's ID
        thread_id: Message thread ID
        sender_username: Username of the sender
        message_preview: Preview of the message content
        redis: Optional Redis client for real-time

    Returns:
        Created Notification
    """
    service = NotificationService(db, redis)
    return await service.create_notification(
        user_id=user_id,
        type="message_received",
        title=f"New message from {sender_username}",
        body=message_preview[:100] + ("..." if len(message_preview) > 100 else ""),
        action_url=f"/messages/{thread_id}",
        metadata={
            "thread_id": thread_id,
            "sender_username": sender_username,
        },
    )


async def create_social_notification(
    db: AsyncSession,
    user_id: int,
    notification_type: str,
    from_user_id: int,
    from_username: str,
    title: str,
    body: str,
    redis: Optional[Redis] = None,
) -> Notification:
    """
    Create a social interaction notification (connection, endorsement, etc.).

    Args:
        db: Database session
        user_id: Target user's ID
        notification_type: One of connection_request, endorsement_received, etc.
        from_user_id: ID of the user who triggered the action
        from_username: Username of the user who triggered the action
        title: Notification title
        body: Notification body
        redis: Optional Redis client for real-time

    Returns:
        Created Notification
    """
    service = NotificationService(db, redis)
    return await service.create_notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        body=body,
        action_url=f"/u/{from_user_id}",  # Link to user profile
        metadata={
            "from_user_id": from_user_id,
            "from_username": from_username,
        },
    )


async def create_achievement_notification(
    db: AsyncSession,
    user_id: int,
    achievement_name: str,
    achievement_description: str,
    achievement_id: Optional[int] = None,
    redis: Optional[Redis] = None,
) -> Notification:
    """
    Create an achievement unlocked notification.

    Args:
        db: Database session
        user_id: Target user's ID
        achievement_name: Name of the achievement
        achievement_description: Description of what was achieved
        achievement_id: Optional achievement ID for linking
        redis: Optional Redis client for real-time

    Returns:
        Created Notification
    """
    service = NotificationService(db, redis)
    return await service.create_notification(
        user_id=user_id,
        type="achievement_unlocked",
        title=f"Achievement Unlocked: {achievement_name}",
        body=achievement_description,
        action_url="/achievements" if achievement_id else None,
        metadata={
            "achievement_name": achievement_name,
            "achievement_id": achievement_id,
        } if achievement_id else {"achievement_name": achievement_name},
    )
