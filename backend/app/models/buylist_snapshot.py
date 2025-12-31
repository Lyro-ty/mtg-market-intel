"""
BuylistSnapshot model for tracking vendor buylist prices.

Buylist prices are what vendors will pay to purchase cards from sellers.
This differs from retail prices (what vendors charge to sell cards).
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card


class BuylistSnapshot(Base):
    """
    Buylist price snapshot for a card from a vendor.

    Buylist prices represent what vendors will pay to purchase cards.
    Key vendors: Card Kingdom, ChannelFireball, Star City Games.

    Attributes:
        id: Primary key
        time: Timestamp of the snapshot
        card_id: Foreign key to the card
        vendor: Vendor name ('cardkingdom', 'channelfireball', 'starcitygames')
        condition: Card condition ('NM', 'LP', 'MP', 'HP')
        is_foil: Whether this is for foil copies
        price: Buylist price the vendor will pay
        quantity: How many copies the vendor is buying (None = unlimited)
        credit_price: Store credit price if different (usually 25-30% higher)
    """

    __tablename__ = "buylist_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    vendor: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    condition: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="NM",
    )

    is_foil: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    price: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    quantity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    credit_price: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Relationships
    card: Mapped["Card"] = relationship("Card", back_populates="buylist_snapshots")

    def __repr__(self) -> str:
        return (
            f"<BuylistSnapshot {self.vendor} buying {self.card_id} "
            f"{self.condition} {'Foil' if self.is_foil else ''}: "
            f"${self.price} at {self.time}>"
        )

    @property
    def spread_vs_retail(self) -> float | None:
        """
        Calculate spread between buylist and retail price.
        Requires card relationship to be loaded with current price.
        """
        if hasattr(self.card, 'current_price') and self.card.current_price:
            return self.card.current_price - self.price
        return None
