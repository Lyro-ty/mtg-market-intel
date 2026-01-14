"""
User reputation and trading reviews models.

Enables trust-based trading by tracking:
- Reputation scores and tiers
- Trade reviews from completed trades
"""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ReputationTier(str, Enum):
    """Reputation tier based on review count and average rating."""
    NEW = "new"              # < 5 reviews
    ESTABLISHED = "established"  # 5-20 reviews, avg > 4.0
    TRUSTED = "trusted"      # 20-50 reviews, avg > 4.5
    ELITE = "elite"          # 50+ reviews, avg > 4.7


class UserReputation(Base):
    """
    Aggregated reputation data for a user.

    Tracks overall reputation metrics and tier.
    Recalculated after each new review.
    """

    __tablename__ = "user_reputation"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Aggregated metrics
    total_reviews: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    average_rating: Mapped[float] = mapped_column(
        Numeric(3, 2),
        default=0.0,
        nullable=False,
    )

    # Breakdown by rating
    five_star_count: Mapped[int] = mapped_column(Integer, default=0)
    four_star_count: Mapped[int] = mapped_column(Integer, default=0)
    three_star_count: Mapped[int] = mapped_column(Integer, default=0)
    two_star_count: Mapped[int] = mapped_column(Integer, default=0)
    one_star_count: Mapped[int] = mapped_column(Integer, default=0)

    # Calculated tier
    tier: Mapped[str] = mapped_column(
        SQLEnum(ReputationTier, native_enum=False, length=20),
        default=ReputationTier.NEW,
        nullable=False,
    )

    # Timestamps
    last_calculated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="reputation",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<UserReputation user_id={self.user_id} tier={self.tier} avg={self.average_rating}>"

    def calculate_tier(self) -> ReputationTier:
        """Calculate reputation tier based on reviews and rating."""
        if self.total_reviews < 5:
            return ReputationTier.NEW
        elif self.total_reviews < 20:
            if float(self.average_rating) >= 4.0:
                return ReputationTier.ESTABLISHED
            return ReputationTier.NEW
        elif self.total_reviews < 50:
            if float(self.average_rating) >= 4.5:
                return ReputationTier.TRUSTED
            elif float(self.average_rating) >= 4.0:
                return ReputationTier.ESTABLISHED
            return ReputationTier.NEW
        else:
            if float(self.average_rating) >= 4.7:
                return ReputationTier.ELITE
            elif float(self.average_rating) >= 4.5:
                return ReputationTier.TRUSTED
            elif float(self.average_rating) >= 4.0:
                return ReputationTier.ESTABLISHED
            return ReputationTier.NEW


class ReputationReview(Base):
    """
    Individual review from one user about another.

    Created after a trade is completed and both parties confirm.
    Each user can only leave one review per trade.
    """

    __tablename__ = "reputation_reviews"

    # Parties
    reviewer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional trade reference (for future trade proposal system)
    trade_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("trade_proposals.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Review content
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )  # 1-5 stars

    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Review metadata
    trade_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # "buy", "sell", "trade", "meetup"

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    reviewer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[reviewer_id],
        lazy="joined",
    )
    reviewee: Mapped["User"] = relationship(
        "User",
        foreign_keys=[reviewee_id],
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "reviewer_id",
            "reviewee_id",
            "trade_id",
            name="uq_review_per_trade",
        ),
    )

    def __repr__(self) -> str:
        return f"<ReputationReview reviewer={self.reviewer_id} reviewee={self.reviewee_id} rating={self.rating}>"
