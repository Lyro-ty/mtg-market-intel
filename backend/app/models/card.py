"""
Card model representing MTG cards from canonical sources.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.listing import Listing
    from app.models.price_snapshot import PriceSnapshot
    from app.models.metrics import MetricsCardsDaily
    from app.models.signal import Signal
    from app.models.recommendation import Recommendation
    from app.models.inventory import InventoryItem


class Card(Base):
    """
    Represents a Magic: The Gathering card.
    
    Uses Scryfall as the canonical source for card identity.
    """
    
    __tablename__ = "cards"
    
    # Override base id to not auto-increment (we use scryfall_id conceptually)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Canonical identifiers
    scryfall_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    oracle_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    
    # Card identity
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    set_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    set_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    collector_number: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Card characteristics
    rarity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mana_cost: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cmc: Mapped[Optional[float]] = mapped_column(nullable=True)
    type_line: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    oracle_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Card face info
    colors: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Stored as JSON string
    color_identity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Power/Toughness (for creatures)
    power: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    toughness: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    
    # Legality (stored as JSON)
    legalities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Media
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    image_url_small: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    image_url_large: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Timestamps
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True
    )
    
    # Relationships
    listings: Mapped[list["Listing"]] = relationship(
        "Listing", back_populates="card", cascade="all, delete-orphan"
    )
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        "PriceSnapshot", back_populates="card", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["MetricsCardsDaily"]] = relationship(
        "MetricsCardsDaily", back_populates="card", cascade="all, delete-orphan"
    )
    signals: Mapped[list["Signal"]] = relationship(
        "Signal", back_populates="card", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        "Recommendation", back_populates="card", cascade="all, delete-orphan"
    )
    inventory_items: Mapped[list["InventoryItem"]] = relationship(
        "InventoryItem", back_populates="card", cascade="all, delete-orphan"
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index("ix_cards_name_set", "name", "set_code"),
        Index("ix_cards_set_collector", "set_code", "collector_number"),
    )
    
    def __repr__(self) -> str:
        return f"<Card {self.name} ({self.set_code} #{self.collector_number})>"

