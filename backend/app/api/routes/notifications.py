"""
Notification API endpoints.

All notification endpoints require authentication and filter data by the current user.
"""
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models import Notification, NotificationType
from app.schemas.notification import (
    NotificationList,
    NotificationResponse,
    NotificationUpdate,
    UnreadCountResponse,
)

router = APIRouter()
logger = structlog.get_logger()


@router.get("", response_model=NotificationList)
async def list_notifications(
    current_user: CurrentUser,
    unread_only: bool = Query(False, description="Only return unread notifications"),
    type: Optional[str] = Query(None, description="Filter by notification type"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
) -> NotificationList:
    """
    List user's notifications with optional filtering.

    Returns notifications ordered by creation date (newest first).
    """
    # Build base query filtered by current user
    query = select(Notification).where(Notification.user_id == current_user.id)

    # Apply filters
    if unread_only:
        query = query.where(Notification.read == False)

    if type:
        # Validate notification type
        try:
            NotificationType(type)
            query = query.where(Notification.type == type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid notification type: {type}. Valid types: {[t.value for t in NotificationType]}"
            )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Get unread count
    unread_query = select(func.count(Notification.id)).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.read == False
        )
    )
    unread_count = await db.scalar(unread_query) or 0

    # Apply ordering and pagination
    query = query.order_by(Notification.created_at.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    notifications = result.scalars().all()

    items = [
        NotificationResponse(
            id=n.id,
            user_id=n.user_id,
            type=n.type.value if isinstance(n.type, NotificationType) else n.type,
            priority=n.priority.value if hasattr(n.priority, 'value') else n.priority,
            title=n.title,
            message=n.message,
            card_id=n.card_id,
            metadata=n.metadata,
            read=n.read,
            read_at=n.read_at,
            created_at=n.created_at,
            expires_at=n.expires_at,
        )
        for n in notifications
    ]

    return NotificationList(
        items=items,
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    """
    Get unread notification count with breakdown by type.
    """
    # Get total unread count
    total_query = select(func.count(Notification.id)).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.read == False
        )
    )
    count = await db.scalar(total_query) or 0

    # Get count by type
    type_query = select(
        Notification.type,
        func.count(Notification.id).label("count")
    ).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.read == False
        )
    ).group_by(Notification.type)

    result = await db.execute(type_query)
    by_type = {
        row.type.value if isinstance(row.type, NotificationType) else row.type: row.count
        for row in result.all()
    }

    return UnreadCountResponse(
        count=count,
        by_type=by_type if by_type else None,
    )


@router.patch("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: int,
    updates: NotificationUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """
    Mark a notification as read or unread.

    Only the notification owner can update their notifications.
    """
    # Get the notification
    query = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    # Update the notification
    notification.read = updates.read
    if updates.read:
        notification.read_at = datetime.now(timezone.utc)
    else:
        notification.read_at = None

    await db.commit()
    await db.refresh(notification)

    logger.info(
        "Notification updated",
        notification_id=notification_id,
        read=updates.read,
        user_id=current_user.id,
    )

    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        type=notification.type.value if isinstance(notification.type, NotificationType) else notification.type,
        priority=notification.priority.value if hasattr(notification.priority, 'value') else notification.priority,
        title=notification.title,
        message=notification.message,
        card_id=notification.card_id,
        metadata=notification.metadata,
        read=notification.read,
        read_at=notification.read_at,
        created_at=notification.created_at,
        expires_at=notification.expires_at,
    )


@router.post("/mark-all-read")
async def mark_all_read(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Mark all notifications as read for the current user.

    Returns the count of notifications that were marked as read.
    """
    now = datetime.now(timezone.utc)

    # Update all unread notifications for this user
    stmt = (
        update(Notification)
        .where(
            and_(
                Notification.user_id == current_user.id,
                Notification.read == False
            )
        )
        .values(read=True, read_at=now)
    )

    result = await db.execute(stmt)
    await db.commit()

    marked_count = result.rowcount

    logger.info(
        "All notifications marked as read",
        user_id=current_user.id,
        marked_count=marked_count,
    )

    return {"marked_count": marked_count}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Delete a notification.

    Only the notification owner can delete their notifications.
    """
    # Get the notification
    query = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    await db.delete(notification)
    await db.commit()

    logger.info(
        "Notification deleted",
        notification_id=notification_id,
        user_id=current_user.id,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
