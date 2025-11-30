"""
Inventory model for user-owned card collections.
"""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card


class InventoryCondition(str, Enum):
    """Card condition grades."""
    MINT = "MINT"
    NEAR_MINT = "NEAR_MINT"
    LIGHTLY_PLAYED = "LIGHTLY_PLAYED"
    MODERATELY_PLAYED = "MODERATELY_PLAYED"
    HEAVILY_PLAYED = "HEAVILY_PLAYED"
    DAMAGED = "DAMAGED"


class InventoryItem(Base):
    """
    Represents a card in the user's inventory.
    
    Tracks acquisition details and current valuation.
    """
    
    __tablename__ = "inventory_items"
    
    # Foreign key to card
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Quantity and condition
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)
    condition: Mapped[str] = mapped_column(
        String(30), 
        default=InventoryCondition.NEAR_MINT.value,
        nullable=False
    )
    is_foil: Mapped[bool] = mapped_column(default=False, nullable=False)
    language: Mapped[str] = mapped_column(String(50), default="English", nullable=False)
    
    # Acquisition details
    acquisition_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    acquisition_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    acquisition_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acquisition_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Current valuation (updated by analytics)
    current_value: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    value_change_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    last_valued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # User notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Import tracking
    import_batch_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    import_raw_line: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    card: Mapped["Card"] = relationship("Card", back_populates="inventory_items")
    
    # Indexes
    __table_args__ = (
        Index("ix_inventory_card_condition", "card_id", "condition"),
        Index("ix_inventory_acquisition_date", "acquisition_date"),
        Index("ix_inventory_value", "current_value"),
        Index("ix_inventory_value_change", "value_change_pct"),
    )
    
    def __repr__(self) -> str:
        return f"<InventoryItem card={self.card_id} qty={self.quantity} cond={self.condition}>"
    
    @property
    def profit_loss(self) -> Optional[float]:
        """Calculate profit/loss based on acquisition price and current value."""
        if self.acquisition_price and self.current_value:
            return (float(self.current_value) - float(self.acquisition_price)) * self.quantity
        return None
    
    @property
    def profit_loss_pct(self) -> Optional[float]:
        """Calculate profit/loss percentage."""
        if self.acquisition_price and self.current_value and float(self.acquisition_price) > 0:
            return ((float(self.current_value) - float(self.acquisition_price)) / float(self.acquisition_price)) * 100
        return None


class InventoryRecommendation(Base):
    """
    Aggressive trading recommendations specific to inventory items.
    
    Uses lower thresholds and more aggressive analysis than market-wide recommendations.
    """
    
    __tablename__ = "inventory_recommendations"
    
    # Foreign keys
    inventory_item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Recommendation details
    action: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    urgency: Mapped[str] = mapped_column(String(20), default="NORMAL", nullable=False)  # LOW, NORMAL, HIGH, CRITICAL
    
    # Confidence and timing
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    horizon_days: Mapped[int] = mapped_column(default=3, nullable=False)  # Shorter horizon for inventory
    
    # Price targets
    target_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    current_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    potential_profit_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    
    # ROI from acquisition
    roi_from_acquisition: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    
    # Rationale
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Suggested marketplace
    suggested_marketplace: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    suggested_listing_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Validity
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    
    # Relationships
    inventory_item: Mapped["InventoryItem"] = relationship("InventoryItem")
    card: Mapped["Card"] = relationship("Card")
    
    # Indexes
    __table_args__ = (
        Index("ix_inv_rec_item_action", "inventory_item_id", "action"),
        Index("ix_inv_rec_urgency", "urgency"),
        Index("ix_inv_rec_active", "is_active"),
        Index("ix_inv_rec_confidence", "confidence"),
    )
    
    def __repr__(self) -> str:
        return f"<InventoryRecommendation {self.action} item={self.inventory_item_id} (urgency={self.urgency})>"
