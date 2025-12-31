"""
Connection Request API endpoints.

Handles user-to-user connection requests for trading.
"""
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User, ConnectionRequest, BlockedUser
from app.schemas.connection import (
    ConnectionRequestCreate,
    ConnectionRequestResponse,
    ConnectionRequestListResponse,
    ConnectionRequestorInfo,
)
from app.services.notifications import NotificationService

router = APIRouter(prefix="/connections", tags=["connections"])
logger = structlog.get_logger(__name__)


async def check_connection(
    db: AsyncSession,
    user_id_1: int,
    user_id_2: int,
) -> bool:
    """Check if two users have an accepted connection."""
    result = await db.execute(
        select(ConnectionRequest).where(
            or_(
                and_(
                    ConnectionRequest.requester_id == user_id_1,
                    ConnectionRequest.recipient_id == user_id_2,
                ),
                and_(
                    ConnectionRequest.requester_id == user_id_2,
                    ConnectionRequest.recipient_id == user_id_1,
                ),
            ),
            ConnectionRequest.status == "accepted",
        )
    )
    return result.scalar_one_or_none() is not None


async def is_blocked(
    db: AsyncSession,
    blocker_id: int,
    blocked_id: int,
) -> bool:
    """Check if blocker has blocked blocked_id."""
    result = await db.execute(
        select(BlockedUser).where(
            BlockedUser.blocker_id == blocker_id,
            BlockedUser.blocked_id == blocked_id,
        )
    )
    return result.scalar_one_or_none() is not None


def _user_to_info(user: User) -> ConnectionRequestorInfo:
    """Convert User to ConnectionRequestorInfo."""
    return ConnectionRequestorInfo(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        location=user.location,
    )


@router.post("/request", response_model=ConnectionRequestResponse, status_code=201)
async def send_connection_request(
    request: ConnectionRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a connection request to another user.

    You can optionally include a message and reference specific cards.
    """
    if request.recipient_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot connect with yourself")

    # Check if recipient exists
    recipient = await db.get(User, request.recipient_id)
    if not recipient or not recipient.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if blocked
    if await is_blocked(db, request.recipient_id, current_user.id):
        raise HTTPException(status_code=403, detail="Cannot send request to this user")

    # Check for existing pending request from me
    existing = await db.execute(
        select(ConnectionRequest).where(
            ConnectionRequest.requester_id == current_user.id,
            ConnectionRequest.recipient_id == request.recipient_id,
            ConnectionRequest.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Request already pending")

    # Check if already connected
    if await check_connection(db, current_user.id, request.recipient_id):
        raise HTTPException(status_code=400, detail="Already connected")

    connection = ConnectionRequest(
        requester_id=current_user.id,
        recipient_id=request.recipient_id,
        message=request.message,
        card_ids=request.card_ids,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)

    # Send notification
    try:
        notification_service = NotificationService(db)
        await notification_service.send(
            user_id=request.recipient_id,
            notification_type="connection_request",
            title="New Connection Request",
            message=f"{current_user.display_name or current_user.username} wants to connect!",
        )
    except Exception as e:
        logger.warning("Failed to send notification", error=str(e))

    logger.info(
        "Connection request sent",
        requester_id=current_user.id,
        recipient_id=request.recipient_id,
    )

    return ConnectionRequestResponse(
        id=connection.id,
        requester_id=connection.requester_id,
        recipient_id=connection.recipient_id,
        message=connection.message,
        card_ids=connection.card_ids,
        status=connection.status,
        created_at=connection.created_at,
        expires_at=connection.expires_at,
        requester=_user_to_info(current_user),
    )


@router.get("/pending", response_model=ConnectionRequestListResponse)
async def get_pending_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get pending connection requests sent to the current user.
    """
    result = await db.execute(
        select(ConnectionRequest)
        .where(ConnectionRequest.recipient_id == current_user.id)
        .where(ConnectionRequest.status == "pending")
        .options(selectinload(ConnectionRequest.requester))
        .order_by(ConnectionRequest.created_at.desc())
    )
    requests = result.scalars().all()

    return ConnectionRequestListResponse(
        requests=[
            ConnectionRequestResponse(
                id=req.id,
                requester_id=req.requester_id,
                recipient_id=req.recipient_id,
                message=req.message,
                card_ids=req.card_ids,
                status=req.status,
                created_at=req.created_at,
                expires_at=req.expires_at,
                requester=_user_to_info(req.requester) if req.requester else None,
            )
            for req in requests
        ],
        total=len(requests),
    )


@router.get("/sent", response_model=ConnectionRequestListResponse)
async def get_sent_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get connection requests sent by the current user.
    """
    result = await db.execute(
        select(ConnectionRequest)
        .where(ConnectionRequest.requester_id == current_user.id)
        .options(selectinload(ConnectionRequest.recipient))
        .order_by(ConnectionRequest.created_at.desc())
    )
    requests = result.scalars().all()

    return ConnectionRequestListResponse(
        requests=[
            ConnectionRequestResponse(
                id=req.id,
                requester_id=req.requester_id,
                recipient_id=req.recipient_id,
                message=req.message,
                card_ids=req.card_ids,
                status=req.status,
                created_at=req.created_at,
                expires_at=req.expires_at,
                responded_at=req.responded_at,
                recipient=_user_to_info(req.recipient) if req.recipient else None,
            )
            for req in requests
        ],
        total=len(requests),
    )


@router.get("/list")
async def get_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get list of accepted connections (users you can message).
    """
    result = await db.execute(
        select(ConnectionRequest)
        .where(
            or_(
                ConnectionRequest.requester_id == current_user.id,
                ConnectionRequest.recipient_id == current_user.id,
            ),
            ConnectionRequest.status == "accepted",
        )
        .options(
            selectinload(ConnectionRequest.requester),
            selectinload(ConnectionRequest.recipient),
        )
        .order_by(ConnectionRequest.responded_at.desc())
    )
    connections = result.scalars().all()

    # Build list of connected users
    connected_users = []
    for conn in connections:
        other_user = conn.recipient if conn.requester_id == current_user.id else conn.requester
        if other_user:
            connected_users.append({
                "connection_id": conn.id,
                "user": _user_to_info(other_user).model_dump(),
                "connected_since": conn.responded_at,
            })

    return {
        "connections": connected_users,
        "total": len(connected_users),
    }


@router.post("/{request_id}/accept")
async def accept_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accept a connection request.
    """
    request = await db.get(ConnectionRequest, request_id)
    if not request or request.recipient_id != current_user.id:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Request already handled")

    request.status = "accepted"
    request.responded_at = datetime.now(timezone.utc)
    await db.commit()

    # Notify requester
    try:
        notification_service = NotificationService(db)
        await notification_service.send(
            user_id=request.requester_id,
            notification_type="connection_accepted",
            title="Connection Accepted!",
            message=f"{current_user.display_name or current_user.username} accepted your connection request",
        )
    except Exception as e:
        logger.warning("Failed to send notification", error=str(e))

    logger.info(
        "Connection request accepted",
        request_id=request_id,
        acceptor_id=current_user.id,
    )

    return {"status": "accepted", "message": "Connection accepted"}


@router.post("/{request_id}/decline")
async def decline_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Decline a connection request.
    """
    request = await db.get(ConnectionRequest, request_id)
    if not request or request.recipient_id != current_user.id:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Request already handled")

    request.status = "declined"
    request.responded_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(
        "Connection request declined",
        request_id=request_id,
        decliner_id=current_user.id,
    )

    return {"status": "declined", "message": "Connection declined"}


@router.delete("/{connection_id}")
async def remove_connection(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove an existing connection.
    """
    connection = await db.get(ConnectionRequest, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.requester_id != current_user.id and connection.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your connection")

    if connection.status != "accepted":
        raise HTTPException(status_code=400, detail="Not an active connection")

    await db.delete(connection)
    await db.commit()

    logger.info(
        "Connection removed",
        connection_id=connection_id,
        remover_id=current_user.id,
    )

    return {"status": "removed", "message": "Connection removed"}


@router.get("/check/{user_id}")
async def check_connection_status(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check connection status with another user.
    """
    if user_id == current_user.id:
        return {"status": "self"}

    # Check for accepted connection
    result = await db.execute(
        select(ConnectionRequest).where(
            or_(
                and_(
                    ConnectionRequest.requester_id == current_user.id,
                    ConnectionRequest.recipient_id == user_id,
                ),
                and_(
                    ConnectionRequest.requester_id == user_id,
                    ConnectionRequest.recipient_id == current_user.id,
                ),
            )
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        return {"status": "none", "can_request": True}

    if connection.status == "accepted":
        return {"status": "connected", "connection_id": connection.id}

    if connection.status == "pending":
        if connection.requester_id == current_user.id:
            return {"status": "pending_sent", "request_id": connection.id}
        else:
            return {"status": "pending_received", "request_id": connection.id}

    if connection.status == "declined":
        # Allow re-request after decline
        return {"status": "declined", "can_request": True}

    return {"status": connection.status}
