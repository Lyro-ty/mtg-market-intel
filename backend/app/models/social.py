"""
Social feature models for enhanced user interactions.

Provides social functionality for the trading platform:
- UserFavorite: Users can favorite other traders for quick access
- UserNote: Private notes about other users
- UserFormatSpecialty: Tracks user expertise in specific MTG formats
- ProfileView: Analytics for profile visits
- NotificationPreference: User notification settings and quiet hours
"""
from datetime import time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserFavorite(Base):
    """
    Tracks when a user favorites another trader.

    Allows users to build a list of preferred trading partners
    with optional notifications when they post new listings.
    """

    __tablename__ = "user_favorites"

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    favorited_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Notification setting
    notify_on_listings: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="joined",
    )
    favorited_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[favorited_user_id],
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "favorited_user_id",
            name="uq_user_favorite",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserFavorite user_id={self.user_id} favorited_user_id={self.favorited_user_id}>"


class UserNote(Base):
    """
    Private notes a user can make about another trader.

    Notes are only visible to the user who created them,
    useful for remembering past trading experiences.
    """

    __tablename__ = "user_notes"

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Note content
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="joined",
    )
    target_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[target_user_id],
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "target_user_id",
            name="uq_user_note",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserNote user_id={self.user_id} target_user_id={self.target_user_id}>"


class UserFormatSpecialty(Base):
    """
    Tracks a user's expertise in specific MTG formats.

    Users can indicate which formats they specialize in
    (e.g., Commander, Modern, Standard) for discovery purposes.
    """

    __tablename__ = "user_format_specialties"

    # Foreign key
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Format name
    format: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Relationship
    user: Mapped["User"] = relationship(
        "User",
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "format",
            name="uq_user_format",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserFormatSpecialty user_id={self.user_id} format={self.format}>"


class ProfileView(Base):
    """
    Tracks when users view other users' profiles.

    Used for analytics and "who viewed your profile" features.
    The viewer can be null for anonymous views.
    """

    __tablename__ = "profile_views"

    # Foreign keys
    viewer_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    viewed_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    viewer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[viewer_id],
        lazy="joined",
    )
    viewed_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[viewed_user_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<ProfileView viewer_id={self.viewer_id} viewed_user_id={self.viewed_user_id}>"


class NotificationPreference(Base):
    """
    User notification preferences and quiet hours settings.

    Stores user preferences for different notification types
    and allows configuring quiet hours when notifications are muted.
    """

    __tablename__ = "notification_preferences"

    # Foreign key (one preference record per user)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Notification preferences as JSONB
    # Example: {"price_alerts": true, "trade_messages": true, "news": false}
    preferences: Mapped[dict] = mapped_column(
        JSONB,
        server_default="{}",
        nullable=False,
    )

    # Quiet hours configuration
    quiet_hours_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    quiet_hours_start: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    quiet_hours_end: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )

    # User timezone for quiet hours calculation
    timezone: Mapped[str] = mapped_column(
        String(50),
        default="UTC",
        nullable=False,
    )

    # Relationship
    user: Mapped["User"] = relationship(
        "User",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<NotificationPreference user_id={self.user_id} quiet_hours={self.quiet_hours_enabled}>"
