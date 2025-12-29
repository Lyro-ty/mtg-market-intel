"""Portfolio snapshot model for tracking collection value over time."""
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class PortfolioSnapshot(Base):
    """Tracks daily snapshots of user's portfolio value."""

    __tablename__ = "portfolio_snapshots"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Snapshot timestamp (should be one per day per user)
    snapshot_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    # Portfolio metrics
    total_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Value changes
    value_change_1d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_change_7d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_change_30d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_change_pct_1d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_change_pct_7d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_change_pct_30d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Breakdown by category (stored as JSON for flexibility)
    # Format: {"foil": 1234.56, "non_foil": 5678.90, "by_set": {"ONE": 100, "MOM": 200}}
    breakdown: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Top gainers/losers for the day (card_id -> change data)
    top_gainers: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    top_losers: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="portfolio_snapshots")

    __table_args__ = (
        Index("ix_portfolio_snapshots_user_date", "user_id", "snapshot_date", unique=True),
    )

    def __repr__(self) -> str:
        return f"<PortfolioSnapshot user={self.user_id} date={self.snapshot_date} value={self.total_value}>"
