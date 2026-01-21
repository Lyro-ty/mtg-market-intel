"""
Trade thread messaging API routes.

Endpoints for in-trade communication:
- GET /trades/{trade_id}/thread - Get or create thread for a trade
- GET /trades/{trade_id}/thread/summary - Get trade summary for chat header
- POST /trades/{trade_id}/thread/messages - Send a message
- POST /trades/{trade_id}/thread/messages/{message_id}/attachments - Upload attachment
- POST /trades/{trade_id}/thread/messages/{message_id}/reactions - Add reaction
- DELETE /trades/{trade_id}/thread/messages/{message_id}/reactions/{emoji} - Remove reaction
- DELETE /trades/{trade_id}/thread/messages/{message_id} - Soft delete message
"""
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User, Card
from app.models.trade import TradeProposal, TradeSide
from app.models.trade_thread import TradeThread, TradeThreadMessage, TradeThreadAttachment
from app.schemas.trade_thread import (
    TradeThreadResponse,
    TradeThreadMessageResponse,
    TradeThreadAttachmentResponse,
    CardEmbedResponse,
    SendMessageRequest,
    AddReactionRequest,
    TradeThreadSummary,
)

router = APIRouter(prefix="/trades/{trade_id}/thread", tags=["Trade Threads"])
logger = structlog.get_logger(__name__)

# Constants
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


# =============================================================================
# Helper Functions
# =============================================================================


async def get_trade_or_404(db: AsyncSession, trade_id: int) -> TradeProposal:
    """
    Get a trade proposal by ID or raise 404.

    Eagerly loads related entities for complete data.
    """
    query = (
        select(TradeProposal)
        .options(
            selectinload(TradeProposal.proposer),
            selectinload(TradeProposal.recipient),
            selectinload(TradeProposal.items),
            selectinload(TradeProposal.thread).selectinload(TradeThread.messages),
        )
        .where(TradeProposal.id == trade_id)
    )
    result = await db.execute(query)
    trade = result.scalar_one_or_none()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade proposal not found")

    return trade


def verify_trade_participant(trade: TradeProposal, user_id: int) -> None:
    """
    Verify that the user is a participant in the trade.

    Raises 403 if user is not the proposer or recipient.
    """
    if user_id not in (trade.proposer_id, trade.recipient_id):
        raise HTTPException(
            status_code=403,
            detail="You are not a participant in this trade"
        )


async def get_or_create_thread(db: AsyncSession, trade: TradeProposal) -> TradeThread:
    """
    Get the existing thread for a trade or create a new one.

    Returns the thread with messages loaded.
    """
    if trade.thread:
        return trade.thread

    # Create new thread
    thread = TradeThread(
        trade_proposal_id=trade.id,
        message_count=0,
    )
    db.add(thread)
    await db.flush()

    # Reload with relationships
    query = (
        select(TradeThread)
        .options(selectinload(TradeThread.messages))
        .where(TradeThread.id == thread.id)
    )
    result = await db.execute(query)
    return result.scalar_one()


def build_card_embed(card: Optional[Card]) -> Optional[CardEmbedResponse]:
    """Build a card embed response from a Card model."""
    if not card:
        return None

    return CardEmbedResponse(
        id=card.id,
        name=card.name,
        set_code=card.set_code,
        image_url=card.image_url,
        price=None,  # Could fetch latest price if needed
    )


def build_message_response(message: TradeThreadMessage) -> TradeThreadMessageResponse:
    """Convert a TradeThreadMessage model to response schema."""
    return TradeThreadMessageResponse(
        id=message.id,
        thread_id=message.thread_id,
        sender_id=message.sender_id,
        sender_username=message.sender.username if message.sender else "Unknown",
        sender_display_name=message.sender.display_name if message.sender else None,
        sender_avatar_url=message.sender.avatar_url if message.sender else None,
        content=message.content,
        card=build_card_embed(message.card),
        has_attachments=message.has_attachments,
        attachments=[
            TradeThreadAttachmentResponse(
                id=att.id,
                file_url=att.file_url,
                file_type=att.file_type,
                file_size=att.file_size,
                created_at=att.created_at,
            )
            for att in (message.attachments or [])
        ],
        reactions=message.reactions or {},
        created_at=message.created_at,
        deleted_at=message.deleted_at,
        is_system_message=False,
    )


def build_thread_response(thread: TradeThread) -> TradeThreadResponse:
    """Convert a TradeThread model to response schema."""
    return TradeThreadResponse(
        id=thread.id,
        trade_proposal_id=thread.trade_proposal_id,
        created_at=thread.created_at,
        archived_at=thread.archived_at,
        last_message_at=thread.last_message_at,
        message_count=thread.message_count,
        messages=[
            build_message_response(msg)
            for msg in (thread.messages or [])
            if msg.deleted_at is None  # Exclude soft-deleted messages from list
        ],
    )


async def get_message_or_404(
    db: AsyncSession,
    thread_id: int,
    message_id: int,
) -> TradeThreadMessage:
    """Get a message by ID within a thread, or raise 404."""
    query = (
        select(TradeThreadMessage)
        .options(
            selectinload(TradeThreadMessage.sender),
            selectinload(TradeThreadMessage.card),
            selectinload(TradeThreadMessage.attachments),
        )
        .where(
            TradeThreadMessage.id == message_id,
            TradeThreadMessage.thread_id == thread_id,
        )
    )
    result = await db.execute(query)
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    return message


# =============================================================================
# Task 5.1: Basic Thread Endpoints
# =============================================================================


@router.get("", response_model=TradeThreadResponse)
async def get_thread(
    trade_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get or create a thread for a trade proposal.

    Returns the complete thread with all messages.
    Auto-creates the thread if it doesn't exist.
    User must be proposer or recipient of the trade.
    """
    trade = await get_trade_or_404(db, trade_id)
    verify_trade_participant(trade, current_user.id)

    thread = await get_or_create_thread(db, trade)
    await db.commit()

    logger.info(
        "Thread retrieved",
        trade_id=trade_id,
        thread_id=thread.id,
        user_id=current_user.id,
    )

    return build_thread_response(thread)


@router.get("/summary", response_model=TradeThreadSummary)
async def get_thread_summary(
    trade_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get compact trade info for the chat header.

    Returns summary information about the trade including
    parties, item counts, and values.
    """
    trade = await get_trade_or_404(db, trade_id)
    verify_trade_participant(trade, current_user.id)

    # Calculate offer and request totals
    proposer_items = [i for i in trade.items if i.side == TradeSide.PROPOSER]
    recipient_items = [i for i in trade.items if i.side == TradeSide.RECIPIENT]

    offer_value = sum(
        float(i.price_at_proposal or 0) * i.quantity
        for i in proposer_items
    )
    request_value = sum(
        float(i.price_at_proposal or 0) * i.quantity
        for i in recipient_items
    )

    return TradeThreadSummary(
        id=trade.id,
        status=trade.status.value if hasattr(trade.status, 'value') else str(trade.status),
        proposer_username=trade.proposer.username,
        recipient_username=trade.recipient.username,
        offer_card_count=sum(i.quantity for i in proposer_items),
        offer_value=offer_value,
        request_card_count=sum(i.quantity for i in recipient_items),
        request_value=request_value,
        expires_at=trade.expires_at,
    )


# =============================================================================
# Task 5.2: Message Sending with Card Embeds
# =============================================================================


@router.post("/messages", response_model=TradeThreadMessageResponse, status_code=201)
async def send_message(
    trade_id: int,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message in the trade thread.

    Either content or card_id must be provided.
    When card_id is provided, includes card info in the response.
    Updates thread's last_message_at and message_count.
    """
    # Validate request - must have content or card_id
    if not request.content and not request.card_id:
        raise HTTPException(
            status_code=400,
            detail="Either content or card_id must be provided"
        )

    trade = await get_trade_or_404(db, trade_id)
    verify_trade_participant(trade, current_user.id)

    # Get or create thread
    thread = await get_or_create_thread(db, trade)

    # Verify card exists if provided
    card = None
    if request.card_id:
        card = await db.get(Card, request.card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

    # Create message
    message = TradeThreadMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        content=request.content,
        card_id=request.card_id,
        has_attachments=False,
        reactions={},
    )
    db.add(message)

    # Update thread metadata
    thread.last_message_at = datetime.now(timezone.utc)
    thread.message_count += 1

    await db.flush()

    # Reload message with relationships
    query = (
        select(TradeThreadMessage)
        .options(
            selectinload(TradeThreadMessage.sender),
            selectinload(TradeThreadMessage.card),
            selectinload(TradeThreadMessage.attachments),
        )
        .where(TradeThreadMessage.id == message.id)
    )
    result = await db.execute(query)
    message = result.scalar_one()

    await db.commit()

    logger.info(
        "Message sent in trade thread",
        trade_id=trade_id,
        thread_id=thread.id,
        message_id=message.id,
        sender_id=current_user.id,
        has_card=request.card_id is not None,
    )

    return build_message_response(message)


# =============================================================================
# Task 5.3: Photo Attachment Upload
# =============================================================================


@router.post(
    "/messages/{message_id}/attachments",
    response_model=TradeThreadAttachmentResponse,
    status_code=201,
)
async def upload_attachment(
    trade_id: int,
    message_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an attachment to a message.

    Only accepts image files (jpeg, png, gif, webp).
    Maximum file size is 5MB.
    User must be the sender of the message.
    """
    trade = await get_trade_or_404(db, trade_id)
    verify_trade_participant(trade, current_user.id)

    # Get thread
    if not trade.thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Get message
    message = await get_message_or_404(db, trade.thread.id, message_id)

    # Verify sender
    if message.sender_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only add attachments to your own messages"
        )

    # Check if message is deleted
    if message.deleted_at:
        raise HTTPException(
            status_code=400,
            detail="Cannot add attachments to deleted messages"
        )

    # Validate file type
    content_type = file.content_type
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_IMAGE_TYPES)}"
        )

    # Read and validate file size
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )

    # TODO: Implement actual file storage (S3, local, etc.)
    # For now, we'll use a placeholder URL
    # In production, upload to storage service and get real URL
    file_url = f"/uploads/trade_threads/{trade_id}/{message_id}/{file.filename}"

    # Create attachment record
    attachment = TradeThreadAttachment(
        message_id=message_id,
        file_url=file_url,
        file_type=content_type,
        file_size=file_size,
    )
    db.add(attachment)

    # Update message has_attachments flag
    message.has_attachments = True

    await db.commit()
    await db.refresh(attachment)

    logger.info(
        "Attachment uploaded to trade thread message",
        trade_id=trade_id,
        message_id=message_id,
        attachment_id=attachment.id,
        file_type=content_type,
        file_size=file_size,
    )

    return TradeThreadAttachmentResponse(
        id=attachment.id,
        file_url=attachment.file_url,
        file_type=attachment.file_type,
        file_size=attachment.file_size,
        created_at=attachment.created_at,
    )


# =============================================================================
# Task 5.4: Reactions and Deletion
# =============================================================================


@router.post("/messages/{message_id}/reactions", status_code=200)
async def add_reaction(
    trade_id: int,
    message_id: int,
    request: AddReactionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add or toggle a reaction on a message.

    If the user has already reacted with the same emoji, the reaction is removed.
    Reactions are stored as JSONB: {"emoji": [user_id1, user_id2]}
    """
    trade = await get_trade_or_404(db, trade_id)
    verify_trade_participant(trade, current_user.id)

    if not trade.thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    message = await get_message_or_404(db, trade.thread.id, message_id)

    # Check if message is deleted
    if message.deleted_at:
        raise HTTPException(
            status_code=400,
            detail="Cannot react to deleted messages"
        )

    # Initialize reactions dict if None
    reactions = message.reactions or {}
    emoji = request.emoji

    # Toggle reaction
    if emoji in reactions:
        user_ids = reactions[emoji]
        if current_user.id in user_ids:
            # Remove reaction
            user_ids.remove(current_user.id)
            if not user_ids:
                del reactions[emoji]
            action = "removed"
        else:
            # Add reaction
            user_ids.append(current_user.id)
            action = "added"
    else:
        # New emoji - add reaction
        reactions[emoji] = [current_user.id]
        action = "added"

    # Update message reactions
    message.reactions = reactions
    # Force SQLAlchemy to detect the change
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(message, "reactions")

    await db.commit()

    logger.info(
        f"Reaction {action}",
        trade_id=trade_id,
        message_id=message_id,
        emoji=emoji,
        user_id=current_user.id,
    )

    return {"status": action, "emoji": emoji, "reactions": reactions}


@router.delete("/messages/{message_id}/reactions/{emoji}", status_code=200)
async def remove_reaction(
    trade_id: int,
    message_id: int,
    emoji: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove a specific reaction from a message.

    Removes the current user from the emoji's user list.
    """
    trade = await get_trade_or_404(db, trade_id)
    verify_trade_participant(trade, current_user.id)

    if not trade.thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    message = await get_message_or_404(db, trade.thread.id, message_id)

    reactions = message.reactions or {}

    if emoji not in reactions or current_user.id not in reactions[emoji]:
        raise HTTPException(
            status_code=404,
            detail="Reaction not found"
        )

    # Remove user from emoji's list
    reactions[emoji].remove(current_user.id)
    if not reactions[emoji]:
        del reactions[emoji]

    message.reactions = reactions
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(message, "reactions")

    await db.commit()

    logger.info(
        "Reaction removed",
        trade_id=trade_id,
        message_id=message_id,
        emoji=emoji,
        user_id=current_user.id,
    )

    return {"status": "removed", "emoji": emoji, "reactions": reactions}


@router.delete("/messages/{message_id}", status_code=200)
async def delete_message(
    trade_id: int,
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Soft delete a message.

    Sets the deleted_at timestamp rather than actually deleting.
    Only the message sender can delete their own messages.
    """
    trade = await get_trade_or_404(db, trade_id)
    verify_trade_participant(trade, current_user.id)

    if not trade.thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    message = await get_message_or_404(db, trade.thread.id, message_id)

    # Verify sender
    if message.sender_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own messages"
        )

    # Check if already deleted
    if message.deleted_at:
        raise HTTPException(
            status_code=400,
            detail="Message is already deleted"
        )

    # Soft delete
    message.deleted_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(
        "Message soft deleted",
        trade_id=trade_id,
        message_id=message_id,
        user_id=current_user.id,
    )

    return {"status": "deleted", "message_id": message_id}
