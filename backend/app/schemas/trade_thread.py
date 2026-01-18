"""
Trade thread messaging Pydantic schemas.

Schemas for trade thread conversations, messages, reactions, and attachments.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TradeThreadAttachmentResponse(BaseModel):
    """Schema for trade thread attachment response."""
    id: int
    file_url: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CardEmbedResponse(BaseModel):
    """Schema for embedded card info in messages."""
    id: int
    name: str
    set_code: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[float] = None


class TradeThreadMessageResponse(BaseModel):
    """Schema for trade thread message response."""
    id: int
    thread_id: int
    sender_id: int
    sender_username: str
    sender_display_name: Optional[str] = None
    sender_avatar_url: Optional[str] = None
    content: Optional[str] = None
    card: Optional[CardEmbedResponse] = None
    has_attachments: bool = False
    attachments: list[TradeThreadAttachmentResponse] = []
    reactions: dict[str, list[int]] = {}  # {"thumbs_up": [user_id, user_id]}
    created_at: datetime
    deleted_at: Optional[datetime] = None
    is_system_message: bool = False

    class Config:
        from_attributes = True


class TradeThreadResponse(BaseModel):
    """Schema for trade thread response."""
    id: int
    trade_proposal_id: int
    created_at: datetime
    archived_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    message_count: int = 0
    messages: list[TradeThreadMessageResponse] = []

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    """Schema for sending a message in a trade thread."""
    content: Optional[str] = None
    card_id: Optional[int] = None


class AddReactionRequest(BaseModel):
    """Schema for adding a reaction to a message."""
    emoji: str


class TradeThreadSummary(BaseModel):
    """Compact trade info for chat header."""
    id: int
    status: str
    proposer_username: str
    recipient_username: str
    offer_card_count: int
    offer_value: float
    request_card_count: int
    request_value: float
    expires_at: Optional[datetime] = None
