"""Saved search model for storing user search queries."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class SearchAlertFrequency(str, Enum):
    """How often to check for new matches."""
    NEVER = "never"
    DAILY = "daily"
    WEEKLY = "weekly"


class SavedSearch(Base):
    """Stores user's saved search queries."""

    __tablename__ = "saved_searches"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Search details
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    query: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Filters stored as JSON
    # Format: {"set_code": "ONE", "rarity": "mythic", "min_price": 10, "max_price": 100}
    filters: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Alert settings
    alert_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alert_frequency: Mapped[SearchAlertFrequency] = mapped_column(
        String(20),
        default=SearchAlertFrequency.NEVER,
        nullable=False
    )
    price_alert_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Tracking
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    last_result_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="saved_searches")

    __table_args__ = (
        Index("ix_saved_searches_user_name", "user_id", "name", unique=True),
    )

    def __repr__(self) -> str:
        return f"<SavedSearch id={self.id} name={self.name}>"
