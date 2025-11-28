"""
Listing model representing individual card listings on marketplaces.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.marketplace import Marketplace


class Listing(Base):
    """
    Represents a specific listing of a card on a marketplace.
    
    Captures current availability and pricing.
    """
    
    __tablename__ = "listings"
    
    # Foreign keys
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    marketplace_id: Mapped[int] = mapped_column(
        ForeignKey("marketplaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Listing details
    condition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    language: Mapped[str] = mapped_column(String(50), default="English", nullable=False)
    is_foil: Mapped[bool] = mapped_column(default=False, nullable=False)
    
    # Pricing
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    
    # Availability
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)
    
    # Seller info (if available)
    seller_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    seller_rating: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    # External reference
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    listing_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Timestamps
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    card: Mapped["Card"] = relationship("Card", back_populates="listings")
    marketplace: Mapped["Marketplace"] = relationship("Marketplace", back_populates="listings")
    
    # Indexes
    __table_args__ = (
        Index("ix_listings_card_marketplace", "card_id", "marketplace_id"),
        Index("ix_listings_price", "price"),
        Index("ix_listings_last_seen", "last_seen_at"),
    )
    
    def __repr__(self) -> str:
        return f"<Listing {self.card_id}@{self.marketplace_id}: {self.price} {self.currency}>"

