"""
Notification-related Pydantic schemas.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationPriority, NotificationType


class NotificationResponse(BaseModel):
    """Full notification response for API."""

    id: int
    user_id: int
    type: str  # NotificationType enum value
    priority: str  # NotificationPriority enum value
    title: str
    message: str
    card_id: Optional[int] = None
    extra_data: Optional[dict[str, Any]] = None
    read: bool
    read_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class NotificationUpdate(BaseModel):
    """Schema for marking notification as read."""

    read: bool


class NotificationList(BaseModel):
    """Paginated notification list response."""

    items: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Response for unread notification count endpoint."""

    count: int
    by_type: Optional[dict[str, int]] = None
