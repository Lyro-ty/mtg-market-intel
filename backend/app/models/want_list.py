"""Want list model for tracking cards users want to acquire."""
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.card import Card


class WantListItem(Base):
    """Card on user's want list with target price and alert settings."""

    __tablename__ = "want_list_items"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    target_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Enhanced alert options
    alert_on_spike: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alert_threshold_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Price change threshold % to trigger spike alert (e.g., 15.00 = 15%)"
    )
    alert_on_supply_low: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alert_on_price_drop: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Alert when price drops below target"
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="want_list_items")
    card: Mapped["Card"] = relationship("Card", lazy="joined")

    __table_args__ = (
        Index("ix_want_list_user_card", "user_id", "card_id", unique=True),
        Index("ix_want_list_alert_enabled", "alert_enabled"),
    )

    def __repr__(self) -> str:
        return f"<WantListItem user={self.user_id} card={self.card_id} target=${self.target_price}>"
