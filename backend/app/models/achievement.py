"""
Achievement system models.

Provides gamification through achievements:
- AchievementDefinition: Template for achievements
- UserAchievement: Tracks user progress and unlocks
- UserFrame: Profile frame unlocks based on achievements
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class AchievementDefinition(Base):
    """
    Template for an achievement that users can unlock.

    Achievements are defined by admins and tracked per-user.
    Supports threshold-based unlocking with JSONB for flexible criteria.
    """

    __tablename__ = "achievement_definitions"

    # Unique identifier for programmatic access
    key: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    # Display information
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Categorization
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # trade, reputation, portfolio, community, special

    # Visual elements
    icon: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Unlock criteria (flexible JSONB)
    # Examples:
    # {"trades": 10} - Complete 10 trades
    # {"reviews": 5, "avg_rating": 4.0} - Get 5 reviews with avg >= 4.0
    # {"portfolio_value": 10000} - Reach $10,000 portfolio value
    threshold: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Rewards
    discovery_points: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Frame unlock tier (if any)
    frame_tier_unlock: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )  # bronze, silver, gold, platinum, legendary

    # Rarity percentage (e.g., 5.50 = 5.5% of users have this)
    rarity_percent: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    # Visibility
    is_hidden: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Seasonal achievements (reset periodically)
    is_seasonal: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    user_achievements: Mapped[list["UserAchievement"]] = relationship(
        "UserAchievement",
        back_populates="achievement",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AchievementDefinition key={self.key} name={self.name}>"


class UserAchievement(Base):
    """
    Tracks a user's progress toward or completion of an achievement.

    Links users to achievement definitions with progress tracking.
    """

    __tablename__ = "user_achievements"

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    achievement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("achievement_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Unlock timestamp (null if not yet unlocked)
    unlocked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Progress tracking
    # Example: {"current": 7, "target": 10}
    progress: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="achievements",
        lazy="joined",
    )
    achievement: Mapped["AchievementDefinition"] = relationship(
        "AchievementDefinition",
        back_populates="user_achievements",
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "achievement_id",
            name="uq_user_achievement",
        ),
    )

    def __repr__(self) -> str:
        status = "unlocked" if self.unlocked_at else "in_progress"
        return f"<UserAchievement user_id={self.user_id} achievement_id={self.achievement_id} status={status}>"


class UserFrame(Base):
    """
    Tracks profile frame unlocks for a user.

    Frames are visual enhancements unlocked through achievements.
    """

    __tablename__ = "user_frames"

    # Foreign key
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Frame tier
    frame_tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # bronze, silver, gold, platinum, legendary

    # Unlock timestamp
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Active status (only one frame active at a time per user)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="frames",
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "frame_tier",
            name="uq_user_frame",
        ),
    )

    def __repr__(self) -> str:
        active = "active" if self.is_active else "inactive"
        return f"<UserFrame user_id={self.user_id} tier={self.frame_tier} {active}>"
