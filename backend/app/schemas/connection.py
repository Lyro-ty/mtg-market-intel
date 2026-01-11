"""
Connection and messaging schemas for API request/response validation.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============ Connection Request Schemas ============

class ConnectionRequestCreate(BaseModel):
    """Schema for creating a connection request."""
    recipient_id: int
    message: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional message to include with the request"
    )
    card_ids: Optional[list[int]] = Field(
        default=None,
        max_length=100,
        description="Optional card IDs to reference in the request (max 100)"
    )


class ConnectionRequestorInfo(BaseModel):
    """Brief info about the requester/recipient."""
    id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None

    class Config:
        from_attributes = True


class ConnectionRequestResponse(BaseModel):
    """Response schema for a connection request."""
    id: int
    requester_id: int
    recipient_id: int
    message: Optional[str] = None
    card_ids: Optional[list[int]] = None
    status: str
    created_at: datetime
    expires_at: datetime
    responded_at: Optional[datetime] = None

    # Optionally populated user info
    requester: Optional[ConnectionRequestorInfo] = None
    recipient: Optional[ConnectionRequestorInfo] = None

    class Config:
        from_attributes = True


class ConnectionRequestListResponse(BaseModel):
    """List of connection requests."""
    requests: list[ConnectionRequestResponse]
    total: int


# ============ Message Schemas ============

class MessageCreate(BaseModel):
    """Schema for creating a message."""
    recipient_id: int
    content: str = Field(..., min_length=1, max_length=2000)


class MessageResponse(BaseModel):
    """Response schema for a message."""
    id: int
    sender_id: int
    recipient_id: int
    content: str
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationSummary(BaseModel):
    """Summary of a conversation with another user."""
    user_id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    last_message: str
    last_message_at: datetime
    unread_count: int


class ConversationListResponse(BaseModel):
    """List of conversations."""
    conversations: list[ConversationSummary]


class MessageListResponse(BaseModel):
    """Paginated message list."""
    messages: list[MessageResponse]
    has_more: bool


# ============ Endorsement Schemas ============

class EndorsementCreate(BaseModel):
    """Schema for creating an endorsement."""
    endorsement_type: str = Field(
        ...,
        description="Type: trustworthy, knowledgeable, responsive, fair_trader"
    )
    comment: Optional[str] = Field(default=None, max_length=500)


class EndorsementResponse(BaseModel):
    """Response schema for an endorsement."""
    id: int
    endorser_id: int
    endorsed_id: int
    endorsement_type: str
    comment: Optional[str] = None
    created_at: datetime

    endorser: Optional[ConnectionRequestorInfo] = None

    class Config:
        from_attributes = True


class EndorsementSummary(BaseModel):
    """Summary of endorsements for a user."""
    trustworthy: int = 0
    knowledgeable: int = 0
    responsive: int = 0
    fair_trader: int = 0
    total: int = 0


# ============ Moderation Schemas ============

class BlockUserCreate(BaseModel):
    """Schema for blocking a user."""
    reason: Optional[str] = Field(default=None, max_length=500)


class ReportUserCreate(BaseModel):
    """Schema for reporting a user."""
    reason: str = Field(..., max_length=100)
    details: Optional[str] = Field(default=None, max_length=2000)


class BlockedUserResponse(BaseModel):
    """Response for a blocked user."""
    id: int
    blocked_id: int
    blocked_username: str
    reason: Optional[str] = None
    created_at: datetime
