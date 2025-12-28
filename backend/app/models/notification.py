"""Notification model for unified alert system."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.user import User


class NotificationType(str, Enum):
    """Types of notifications that can be sent to users."""

    PRICE_ALERT = "price_alert"      # Want list target hit
    PRICE_SPIKE = "price_spike"      # Card spiked in price
    PRICE_DROP = "price_drop"        # Card dropped in price
    MILESTONE = "milestone"          # Collection milestone achieved
    SYSTEM = "system"                # System announcements
    EDUCATIONAL = "educational"      # Tips and educational content


class NotificationPriority(str, Enum):
    """Priority levels for notifications."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Notification(Base):
    """User notification with support for various alert types."""

    __tablename__ = "notifications"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )
    priority: Mapped[NotificationPriority] = mapped_column(
        String(10),
        default=NotificationPriority.MEDIUM,
        nullable=False
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    card_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    dedup_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        unique=True,
        nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")
    card: Mapped[Optional["Card"]] = relationship("Card", lazy="joined")

    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "read"),
        Index("ix_notifications_user_type", "user_id", "type"),
        Index("ix_notifications_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Notification id={self.id} user={self.user_id} type={self.type} read={self.read}>"
