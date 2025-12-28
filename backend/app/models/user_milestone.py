"""UserMilestone model for tracking collection achievements."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class MilestoneType(str, Enum):
    """Types of milestones users can achieve."""

    CARDS_OWNED = "cards_owned"           # Total cards milestone (100, 500, 1000, etc.)
    COLLECTION_VALUE = "collection_value" # Value milestones ($100, $500, $1000, etc.)
    SET_COMPLETION = "set_completion"     # Completed a set
    UNIQUE_CARDS = "unique_cards"         # Unique cards milestones
    FIRST_CARD = "first_card"             # First card added
    SETS_STARTED = "sets_started"         # Number of sets started


class UserMilestone(Base):
    """Tracks collection milestones achieved by users."""

    __tablename__ = "user_milestones"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    type: Mapped[MilestoneType] = mapped_column(
        String(30),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    threshold: Mapped[int] = mapped_column(default=0, nullable=False)
    achieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="milestones")

    __table_args__ = (
        Index("ix_user_milestones_user_type", "user_id", "type"),
        UniqueConstraint("user_id", "type", "threshold", name="uq_user_milestones_user_type_threshold"),
    )

    def __repr__(self) -> str:
        return f"<UserMilestone id={self.id} user={self.user_id} type={self.type} threshold={self.threshold}>"
