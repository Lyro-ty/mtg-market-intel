"""
PriceSnapshot model for historical price tracking.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.marketplace import Marketplace


class PriceSnapshot(Base):
    """
    Historical price snapshot for a card on a specific marketplace.
    
    Used for building price history charts and trend analysis.
    """
    
    __tablename__ = "price_snapshots"
    
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
    
    # Snapshot time
    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    
    # Price data
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    
    # Price variants (if available)
    price_foil: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Market data (aggregated if available)
    min_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    max_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    avg_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    median_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Volume indicators
    num_listings: Mapped[Optional[int]] = mapped_column(nullable=True)
    total_quantity: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    # Relationships
    card: Mapped["Card"] = relationship("Card", back_populates="price_snapshots")
    marketplace: Mapped["Marketplace"] = relationship("Marketplace", back_populates="price_snapshots")
    
    # Indexes for efficient time-series queries
    __table_args__ = (
        Index("ix_snapshots_card_time", "card_id", "snapshot_time"),
        Index("ix_snapshots_market_time", "marketplace_id", "snapshot_time"),
        Index("ix_snapshots_card_market_time", "card_id", "marketplace_id", "snapshot_time"),
    )
    
    def __repr__(self) -> str:
        return f"<PriceSnapshot {self.card_id}@{self.marketplace_id}: {self.price} at {self.snapshot_time}>"

