"""
Enhanced Notifications API with category-based organization and WebSocket support.

Provides:
- Paginated notification listing with category filtering
- Unread counts by category
- Mark read operations (single, multiple, by category)
- Notification preferences management
- WebSocket endpoint for real-time notifications

All endpoints require authentication.
"""
import asyncio
from collections import defaultdict
from datetime import datetime, time as dt_time, timezone
from typing import Annotated, Optional

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from redis.asyncio import Redis
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import settings
from app.db.session import get_db, async_session_maker
from app.models.notification import Notification, NotificationType
from app.models.social import NotificationPreference
from app.models.user import User
from app.schemas.notification_enhanced import (
    MarkReadRequest,
    NotificationPreferencesResponse,
    NotificationResponse,
    NotificationsListResponse,
    UnreadCountsResponse,
    UpdateNotificationPreferencesRequest,
)
from app.services.auth import decode_access_token
from app.services.notification_service import (
    NOTIFICATION_TYPE_CATEGORIES,
    get_category_for_type,
    get_icon_for_type,
)

router = APIRouter()
logger = structlog.get_logger()


# =============================================================================
# Helper Functions
# =============================================================================

def _get_notification_type(notification: Notification) -> str:
    """Get the original notification type from extra_data or enum."""
    extra = notification.extra_data or {}
    # Check if we stored the original type in extra_data
    if "notification_type" in extra:
        return extra["notification_type"]
    # Fall back to the enum type
    if isinstance(notification.type, NotificationType):
        return notification.type.value
    return str(notification.type)


def _notification_to_response(notification: Notification) -> NotificationResponse:
    """Convert a Notification model to NotificationResponse schema."""
    notification_type = _get_notification_type(notification)
    extra = notification.extra_data or {}

    return NotificationResponse(
        id=notification.id,
        type=notification_type,
        category=get_category_for_type(notification_type),
        title=notification.title,
        body=notification.message,
        icon=get_icon_for_type(notification_type),
        action_url=extra.get("action_url"),
        metadata={k: v for k, v in extra.items() if k not in ("action_url", "notification_type")},
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


def _get_types_for_category(category: str) -> list[str]:
    """Get all notification types that belong to a category."""
    return [
        type_str for type_str, cat in NOTIFICATION_TYPE_CATEGORIES.items()
        if cat == category
    ]


# =============================================================================
# Notification List Endpoint
# =============================================================================

@router.get("", response_model=NotificationsListResponse)
async def list_notifications(
    current_user: CurrentUser,
    category: Optional[str] = Query(
        None,
        description="Filter by category (trades, messages, social, discovery, achievements, system)"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> NotificationsListResponse:
    """
    Get paginated notifications for the current user.

    Notifications are ordered by creation date (newest first) and exclude expired ones.
    Optionally filter by category.
    """
    now = datetime.now(timezone.utc)
    offset = (page - 1) * limit

    # Build base query - exclude expired notifications
    base_conditions = [
        Notification.user_id == current_user.id,
        or_(
            Notification.expires_at.is_(None),
            Notification.expires_at > now,
        ),
    ]

    # Apply category filter if provided
    if category:
        valid_categories = {"trades", "messages", "social", "discovery", "achievements", "system"}
        if category not in valid_categories:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category. Valid categories: {', '.join(sorted(valid_categories))}"
            )
        # Get notification types for this category
        # Note: We need to filter in Python since category is computed from type
        pass  # We'll filter in post-processing

    # Build query
    query = select(Notification).where(and_(*base_conditions))
    query = query.order_by(Notification.created_at.desc())

    # Get all matching notifications (we'll filter by category in memory)
    result = await db.execute(query)
    all_notifications = list(result.scalars().all())

    # Filter by category if specified
    if category:
        filtered_notifications = [
            n for n in all_notifications
            if get_category_for_type(_get_notification_type(n)) == category
        ]
    else:
        filtered_notifications = all_notifications

    # Calculate totals
    total = len(filtered_notifications)
    unread_count = sum(1 for n in filtered_notifications if not n.read)
    has_more = offset + limit < total

    # Apply pagination
    paginated = filtered_notifications[offset:offset + limit]

    # Convert to response
    notifications = [_notification_to_response(n) for n in paginated]

    return NotificationsListResponse(
        notifications=notifications,
        total=total,
        unread_count=unread_count,
        has_more=has_more,
    )


# =============================================================================
# Unread Counts Endpoint
# =============================================================================

@router.get("/unread/counts", response_model=UnreadCountsResponse)
async def get_unread_counts(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> UnreadCountsResponse:
    """
    Get unread notification counts by category.

    Returns counts for each category: trades, messages, social, discovery, achievements, system.
    """
    now = datetime.now(timezone.utc)

    # Get all unread, non-expired notifications
    query = select(Notification).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.read == False,
            or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > now,
            ),
        )
    )

    result = await db.execute(query)
    notifications = result.scalars().all()

    # Count by category
    category_counts: dict[str, int] = defaultdict(int)
    for notification in notifications:
        notification_type = _get_notification_type(notification)
        category = get_category_for_type(notification_type)
        category_counts[category] += 1

    total = sum(category_counts.values())

    return UnreadCountsResponse(
        total=total,
        trades=category_counts.get("trades", 0),
        messages=category_counts.get("messages", 0),
        social=category_counts.get("social", 0),
        discovery=category_counts.get("discovery", 0),
        achievements=category_counts.get("achievements", 0),
        system=category_counts.get("system", 0),
    )


# =============================================================================
# Mark Read Endpoints
# =============================================================================

@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Mark a single notification as read.

    Returns the updated notification status.
    """
    query = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    if not notification.read:
        notification.read = True
        notification.read_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(
            "Notification marked as read",
            notification_id=notification_id,
            user_id=current_user.id,
        )

    return {"success": True, "notification_id": notification_id}


@router.post("/read")
async def mark_multiple_read(
    request: MarkReadRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Mark multiple notifications as read.

    Returns the count of notifications that were marked as read.
    """
    if not request.notification_ids:
        return {"success": True, "marked_count": 0}

    now = datetime.now(timezone.utc)

    # Update all matching unread notifications for this user
    stmt = (
        update(Notification)
        .where(
            and_(
                Notification.id.in_(request.notification_ids),
                Notification.user_id == current_user.id,
                Notification.read == False,
            )
        )
        .values(read=True, read_at=now)
    )

    result = await db.execute(stmt)
    await db.commit()

    marked_count = result.rowcount

    logger.info(
        "Multiple notifications marked as read",
        notification_ids=request.notification_ids,
        marked_count=marked_count,
        user_id=current_user.id,
    )

    return {"success": True, "marked_count": marked_count}


@router.post("/category/{category}/read")
async def mark_category_read(
    category: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Mark all notifications in a category as read.

    Valid categories: trades, messages, social, discovery, achievements, system.
    Returns the count of notifications that were marked as read.
    """
    valid_categories = {"trades", "messages", "social", "discovery", "achievements", "system"}
    if category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Valid categories: {', '.join(sorted(valid_categories))}"
        )

    now = datetime.now(timezone.utc)

    # Get all unread notifications for this user
    query = select(Notification).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.read == False,
        )
    )
    result = await db.execute(query)
    notifications = result.scalars().all()

    # Filter by category and mark as read
    marked_count = 0
    for notification in notifications:
        notification_type = _get_notification_type(notification)
        if get_category_for_type(notification_type) == category:
            notification.read = True
            notification.read_at = now
            marked_count += 1

    await db.commit()

    logger.info(
        "Category notifications marked as read",
        category=category,
        marked_count=marked_count,
        user_id=current_user.id,
    )

    return {"success": True, "category": category, "marked_count": marked_count}


# =============================================================================
# Notification Preferences Endpoints
# =============================================================================

DEFAULT_PREFERENCES = {
    "trade_activity": "on",
    "messages": "on",
    "social": "on",
    "discovery": "daily_digest",
    "price_alerts": "daily_digest",
    "achievements": "on",
    "listing_reminders": "weekly",
}


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """
    Get the current user's notification preferences.

    Creates default preferences if none exist.
    """
    query = select(NotificationPreference).where(
        NotificationPreference.user_id == current_user.id
    )
    result = await db.execute(query)
    pref = result.scalar_one_or_none()

    if not pref:
        # Create default preferences
        pref = NotificationPreference(
            user_id=current_user.id,
            preferences=DEFAULT_PREFERENCES,
            quiet_hours_enabled=False,
            timezone="UTC",
        )
        db.add(pref)
        await db.commit()
        await db.refresh(pref)

        logger.info(
            "Created default notification preferences",
            user_id=current_user.id,
        )

    # Merge stored preferences with defaults
    prefs = {**DEFAULT_PREFERENCES, **(pref.preferences or {})}

    return NotificationPreferencesResponse(
        trade_activity=prefs.get("trade_activity", "on"),
        messages=prefs.get("messages", "on"),
        social=prefs.get("social", "on"),
        discovery=prefs.get("discovery", "daily_digest"),
        price_alerts=prefs.get("price_alerts", "daily_digest"),
        achievements=prefs.get("achievements", "on"),
        listing_reminders=prefs.get("listing_reminders", "weekly"),
        quiet_hours_enabled=pref.quiet_hours_enabled,
        quiet_hours_start=pref.quiet_hours_start,
        quiet_hours_end=pref.quiet_hours_end,
        timezone=pref.timezone,
    )


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    request: UpdateNotificationPreferencesRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """
    Update the current user's notification preferences.

    Supports partial updates - only provided fields are updated.
    """
    # Validate preference values
    valid_values = {"on", "off", "daily_digest", "weekly"}
    for field in ["trade_activity", "messages", "social", "discovery", "price_alerts", "achievements", "listing_reminders"]:
        value = getattr(request, field, None)
        if value is not None and value not in valid_values:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid value for {field}. Valid values: {', '.join(sorted(valid_values))}"
            )

    # Get or create preferences
    query = select(NotificationPreference).where(
        NotificationPreference.user_id == current_user.id
    )
    result = await db.execute(query)
    pref = result.scalar_one_or_none()

    if not pref:
        pref = NotificationPreference(
            user_id=current_user.id,
            preferences=DEFAULT_PREFERENCES.copy(),
            quiet_hours_enabled=False,
            timezone="UTC",
        )
        db.add(pref)

    # Update preference values
    prefs = pref.preferences.copy() if pref.preferences else DEFAULT_PREFERENCES.copy()

    for field in ["trade_activity", "messages", "social", "discovery", "price_alerts", "achievements", "listing_reminders"]:
        value = getattr(request, field, None)
        if value is not None:
            prefs[field] = value

    pref.preferences = prefs

    # Update quiet hours settings
    if request.quiet_hours_enabled is not None:
        pref.quiet_hours_enabled = request.quiet_hours_enabled
    if request.quiet_hours_start is not None:
        pref.quiet_hours_start = request.quiet_hours_start
    if request.quiet_hours_end is not None:
        pref.quiet_hours_end = request.quiet_hours_end
    if request.timezone is not None:
        pref.timezone = request.timezone

    await db.commit()
    await db.refresh(pref)

    logger.info(
        "Updated notification preferences",
        user_id=current_user.id,
        preferences=pref.preferences,
    )

    return NotificationPreferencesResponse(
        trade_activity=prefs.get("trade_activity", "on"),
        messages=prefs.get("messages", "on"),
        social=prefs.get("social", "on"),
        discovery=prefs.get("discovery", "daily_digest"),
        price_alerts=prefs.get("price_alerts", "daily_digest"),
        achievements=prefs.get("achievements", "on"),
        listing_reminders=prefs.get("listing_reminders", "weekly"),
        quiet_hours_enabled=pref.quiet_hours_enabled,
        quiet_hours_start=pref.quiet_hours_start,
        quiet_hours_end=pref.quiet_hours_end,
        timezone=pref.timezone,
    )


# =============================================================================
# WebSocket Endpoint for Real-Time Notifications
# =============================================================================

# In-memory tracking of active WebSocket connections per user
# In production, this would be managed via Redis for multi-instance support
_active_connections: dict[int, set[WebSocket]] = defaultdict(set)
_connection_lock = asyncio.Lock()


async def _authenticate_websocket(token: str, db: AsyncSession) -> Optional[User]:
    """Authenticate a WebSocket connection via JWT token."""
    if not token:
        return None

    try:
        payload = decode_access_token(token)
        if not payload:
            return None

        user_id = int(payload.sub)
        user = await db.get(User, user_id)

        if user and user.is_active:
            return user
    except Exception as e:
        logger.debug("WebSocket auth failed", error=str(e))

    return None


@router.websocket("/ws")
async def notifications_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time notification streaming.

    Connect with JWT token as query parameter: /ws?token=<jwt_token>

    The WebSocket will:
    1. Authenticate the user via the JWT token
    2. Subscribe to the user's notification channel on Redis
    3. Forward any notifications received to the client
    4. Handle disconnection gracefully

    Client can send ping messages to keep the connection alive:
    {"type": "ping"}

    Server will respond with:
    {"type": "pong", "timestamp": "..."}
    """
    # Authenticate - create our own session for WebSocket
    user = None
    if token:
        try:
            async with async_session_maker() as db:
                user = await _authenticate_websocket(token, db)
        except Exception as e:
            logger.debug("WebSocket auth error", error=str(e))

    if not user:
        await websocket.close(code=4001, reason="Authentication required")
        return

    # Accept connection
    await websocket.accept()

    # Track connection
    async with _connection_lock:
        _active_connections[user.id].add(websocket)

    logger.info(
        "WebSocket notification connection opened",
        user_id=user.id,
        connection_count=len(_active_connections[user.id]),
    )

    # Create Redis client and pub/sub subscription
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    channel = f"channel:notifications:user:{user.id}"

    try:
        await pubsub.subscribe(channel)

        # Create tasks for receiving from client and Redis
        async def receive_from_client():
            """Handle messages from the WebSocket client."""
            try:
                while True:
                    data = await websocket.receive_json()
                    msg_type = data.get("type")

                    if msg_type == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
            except WebSocketDisconnect:
                raise
            except Exception as e:
                logger.debug("WebSocket receive error", error=str(e))
                raise WebSocketDisconnect()

        async def receive_from_redis():
            """Forward notifications from Redis to the WebSocket client."""
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            import json
                            data = json.loads(message["data"])
                            await websocket.send_json(data)
                        except Exception as e:
                            logger.warning("Failed to forward notification", error=str(e))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug("Redis receive error", error=str(e))
                raise

        # Run both tasks concurrently
        client_task = asyncio.create_task(receive_from_client())
        redis_task = asyncio.create_task(receive_from_redis())

        try:
            # Wait for either task to complete (usually disconnect)
            done, pending = await asyncio.wait(
                [client_task, redis_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except asyncio.CancelledError:
            client_task.cancel()
            redis_task.cancel()
            raise

    except WebSocketDisconnect:
        logger.info("WebSocket notification connection closed", user_id=user.id)
    except Exception as e:
        logger.error("WebSocket error", user_id=user.id, error=str(e))
    finally:
        # Cleanup
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await redis.close()

        async with _connection_lock:
            _active_connections[user.id].discard(websocket)
            if not _active_connections[user.id]:
                del _active_connections[user.id]

        logger.info(
            "WebSocket notification connection cleaned up",
            user_id=user.id,
        )
