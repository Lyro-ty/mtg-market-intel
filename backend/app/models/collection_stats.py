"""Collection stats model for caching user collection metrics."""
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class CollectionStats(Base):
    """Cached statistics for a user's collection for performance optimization."""

    __tablename__ = "collection_stats"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # Collection totals
    total_cards: Mapped[int] = mapped_column(default=0, nullable=False)
    total_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False
    )
    unique_cards: Mapped[int] = mapped_column(default=0, nullable=False)

    # Set completion tracking
    sets_started: Mapped[int] = mapped_column(default=0, nullable=False)
    sets_completed: Mapped[int] = mapped_column(default=0, nullable=False)
    top_set_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    top_set_completion: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True
    )

    # Cache management
    is_stale: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_calculated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="collection_stats")

    def __repr__(self) -> str:
        return f"<CollectionStats user={self.user_id} cards={self.total_cards} value=${self.total_value}>"
