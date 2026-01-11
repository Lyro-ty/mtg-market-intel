"""
Direct Messaging API endpoints.

Allows connected users to send messages to each other.
"""
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, and_, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User, Message
from app.api.routes.connections import check_connection, is_blocked
from app.schemas.connection import (
    MessageCreate,
    MessageResponse,
    ConversationSummary,
    ConversationListResponse,
    MessageListResponse,
)
from app.services.notifications import NotificationService

router = APIRouter(prefix="/messages", tags=["messages"])
logger = structlog.get_logger(__name__)


@router.post("/", response_model=MessageResponse, status_code=201)
async def send_message(
    message: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to a connected user.

    You must have an accepted connection to message someone.
    """
    if message.recipient_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot message yourself")

    # Verify recipient exists
    recipient = await db.get(User, message.recipient_id)
    if not recipient or not recipient.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify connection exists
    connected = await check_connection(db, current_user.id, message.recipient_id)
    if not connected:
        raise HTTPException(
            status_code=403,
            detail="Must have accepted connection to message"
        )

    # Check not blocked
    if await is_blocked(db, message.recipient_id, current_user.id):
        raise HTTPException(status_code=403, detail="Cannot message this user")

    msg = Message(
        sender_id=current_user.id,
        recipient_id=message.recipient_id,
        content=message.content,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    # Send notification
    try:
        notification_service = NotificationService(db)
        preview = message.content[:50] + "..." if len(message.content) > 50 else message.content
        await notification_service.send(
            user_id=message.recipient_id,
            notification_type="new_message",
            title="New Message",
            message=f"{current_user.display_name or current_user.username}: {preview}",
        )
    except Exception as e:
        logger.warning("Failed to send notification", error=str(e))

    logger.info(
        "Message sent",
        sender_id=current_user.id,
        recipient_id=message.recipient_id,
    )

    return MessageResponse(
        id=msg.id,
        sender_id=msg.sender_id,
        recipient_id=msg.recipient_id,
        content=msg.content,
        read_at=msg.read_at,
        created_at=msg.created_at,
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def get_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get list of conversations with last message.
    """
    query = text("""
        WITH conversation_partners AS (
            SELECT DISTINCT
                CASE
                    WHEN sender_id = :user_id THEN recipient_id
                    ELSE sender_id
                END as partner_id
            FROM messages
            WHERE sender_id = :user_id OR recipient_id = :user_id
        )
        SELECT
            u.id,
            u.username,
            u.display_name,
            u.avatar_url,
            m.content as last_message,
            m.created_at as last_message_at,
            (SELECT COUNT(*) FROM messages
             WHERE sender_id = u.id AND recipient_id = :user_id AND read_at IS NULL
            ) as unread_count
        FROM conversation_partners cp
        JOIN users u ON cp.partner_id = u.id
        JOIN LATERAL (
            SELECT content, created_at FROM messages
            WHERE (sender_id = :user_id AND recipient_id = u.id)
               OR (sender_id = u.id AND recipient_id = :user_id)
            ORDER BY created_at DESC LIMIT 1
        ) m ON true
        ORDER BY m.created_at DESC
    """)
    result = await db.execute(query, {"user_id": current_user.id})
    rows = result.all()

    return ConversationListResponse(
        conversations=[
            ConversationSummary(
                user_id=row[0],
                username=row[1],
                display_name=row[2],
                avatar_url=row[3],
                last_message=row[4],
                last_message_at=row[5],
                unread_count=row[6],
            )
            for row in rows
        ]
    )


@router.get("/with/{user_id}", response_model=MessageListResponse)
async def get_conversation(
    user_id: int,
    limit: int = Query(default=50, le=100),
    before_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get messages with a specific user.

    Messages are returned in reverse chronological order.
    Use before_id for pagination.
    """
    query = select(Message).where(
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == user_id),
            and_(Message.sender_id == user_id, Message.recipient_id == current_user.id),
        )
    ).order_by(Message.created_at.desc()).limit(limit + 1)

    if before_id:
        query = query.where(Message.id < before_id)

    result = await db.execute(query)
    messages = result.scalars().all()

    # Check if there are more
    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    # Mark messages as read
    await db.execute(
        update(Message)
        .where(Message.sender_id == user_id)
        .where(Message.recipient_id == current_user.id)
        .where(Message.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    await db.commit()

    return MessageListResponse(
        messages=[
            MessageResponse(
                id=msg.id,
                sender_id=msg.sender_id,
                recipient_id=msg.recipient_id,
                content=msg.content,
                read_at=msg.read_at,
                created_at=msg.created_at,
            )
            for msg in messages
        ],
        has_more=has_more,
    )


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get total unread message count.
    """
    result = await db.execute(
        text("SELECT COUNT(*) FROM messages WHERE recipient_id = :user_id AND read_at IS NULL"),
        {"user_id": current_user.id}
    )
    count = result.scalar() or 0
    return {"unread_count": count}


@router.post("/{message_id}/read")
async def mark_message_read(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark a specific message as read.
    """
    message = await db.get(Message, message_id)
    if not message or message.recipient_id != current_user.id:
        raise HTTPException(status_code=404, detail="Message not found")

    if not message.read_at:
        message.read_at = datetime.now(timezone.utc)
        await db.commit()

    return {"status": "read"}
