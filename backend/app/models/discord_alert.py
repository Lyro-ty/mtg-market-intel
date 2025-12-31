"""Discord alert queue model for pending bot notifications."""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.user import User


class DiscordAlertQueue(Base):
    """
    Queue for Discord alerts pending delivery.

    When notifications are created for users with linked Discord accounts,
    they are also added here. The Discord bot polls for pending alerts
    and marks them as delivered after sending.
    """

    __tablename__ = "discord_alert_queue"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("notifications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    card_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Alert content (copied from notification for resilience)
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Delivery status
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="joined")
    card: Mapped[Optional["Card"]] = relationship("Card", lazy="joined")

    __table_args__ = (
        Index("ix_discord_alert_queue_pending", "delivered", "created_at"),
        Index("ix_discord_alert_queue_user_pending", "user_id", "delivered"),
    )

    def __repr__(self) -> str:
        status = "delivered" if self.delivered else "pending"
        return f"<DiscordAlert id={self.id} user={self.user_id} type={self.alert_type} {status}>"
