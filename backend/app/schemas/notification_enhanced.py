"""
Enhanced notification schemas for social trading features.

These schemas support category-based notifications, preferences,
and quiet hours for the enhanced notification system.
"""
from datetime import datetime, time
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    """Full notification response for enhanced notification API."""

    id: int
    type: str  # trade_proposal, message, connection, achievement, etc.
    category: str  # trades, messages, social, discovery, achievements, system
    title: str
    body: str
    icon: Optional[str] = None
    action_url: Optional[str] = None
    metadata: dict[str, Any] = {}
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationsListResponse(BaseModel):
    """Paginated list of notifications with metadata."""

    notifications: list[NotificationResponse]
    total: int
    unread_count: int
    has_more: bool


class UnreadCountsResponse(BaseModel):
    """Unread notification counts by category."""

    total: int
    trades: int
    messages: int
    social: int
    discovery: int
    achievements: int
    system: int


class NotificationPreferencesResponse(BaseModel):
    """User notification preferences with quiet hours support."""

    trade_activity: str = "on"  # on, daily_digest, off
    messages: str = "on"
    social: str = "on"
    discovery: str = "daily_digest"
    price_alerts: str = "daily_digest"
    achievements: str = "on"
    listing_reminders: str = "weekly"

    quiet_hours_enabled: bool = False
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None
    timezone: str = "UTC"

    model_config = ConfigDict(from_attributes=True)


class UpdateNotificationPreferencesRequest(BaseModel):
    """Request to update notification preferences."""

    trade_activity: Optional[str] = None
    messages: Optional[str] = None
    social: Optional[str] = None
    discovery: Optional[str] = None
    price_alerts: Optional[str] = None
    achievements: Optional[str] = None
    listing_reminders: Optional[str] = None

    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None
    timezone: Optional[str] = None


class MarkReadRequest(BaseModel):
    """Request to mark specific notifications as read."""

    notification_ids: list[int]


class MarkCategoryReadRequest(BaseModel):
    """Request to mark all notifications in a category as read."""

    category: str
