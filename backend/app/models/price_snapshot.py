"""
PriceSnapshot model for TimescaleDB hypertable.

This model represents price data stored in a TimescaleDB hypertable
with support for condition, language, and foil tracking.

Note: The actual table is created and managed via Alembic migrations
as a TimescaleDB hypertable. This SQLAlchemy model provides ORM
access but does not define the hypertable structure.
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM

from app.db.base import Base
from app.core.constants import CardCondition, CardLanguage

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.marketplace import Marketplace


# Create PostgreSQL ENUM types
# Note: These are created in migration 011_enable_timescaledb
card_condition_enum = ENUM(
    'MINT', 'NEAR_MINT', 'LIGHTLY_PLAYED',
    'MODERATELY_PLAYED', 'HEAVILY_PLAYED', 'DAMAGED',
    name='card_condition',
    create_type=False,  # Type is created in migration
)

card_language_enum = ENUM(
    'English', 'Japanese', 'German', 'French', 'Italian',
    'Spanish', 'Portuguese', 'Korean', 'Chinese Simplified',
    'Chinese Traditional', 'Russian', 'Phyrexian',
    name='card_language',
    create_type=False,  # Type is created in migration
)


class HypertableBase(DeclarativeBase):
    """
    Base class for TimescaleDB hypertable models.

    Unlike the standard Base class, this does NOT include an auto-incrementing
    'id' column, as hypertables use composite primary keys with time as the
    partition key.

    Uses the same registry as Base so relationships work across models.
    """
    # Share the same registry as Base so relationships work
    registry = Base.registry


class PriceSnapshot(HypertableBase):
    """
    Price snapshot for a card variant on a marketplace.

    This model maps to the price_snapshots hypertable which stores
    time-series price data with full variant tracking (condition,
    language, foil status).

    Key Features:
    - Stored in TimescaleDB hypertable with 7-day chunks
    - Automatic compression after 7 days
    - 2-year retention policy
    - Continuous aggregates for efficient analytics

    Attributes:
        time: Timestamp of the snapshot (hypertable partition key)
        card_id: Foreign key to the card
        marketplace_id: Foreign key to the marketplace
        condition: Card condition (MINT, NEAR_MINT, etc.)
        is_foil: Whether this is a foil variant
        language: Card language
        price: Current price
        price_low: Low price tier
        price_mid: Mid price tier
        price_high: High price tier
        price_market: Market price (if available)
        currency: Currency code (USD, EUR)
        num_listings: Number of listings at this price
        total_quantity: Total quantity available
    """

    __tablename__ = "price_snapshots"

    # Time column (hypertable partition key)
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
    )

    # Foreign keys
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    marketplace_id: Mapped[int] = mapped_column(
        ForeignKey("marketplaces.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    # Card variant identifiers
    condition: Mapped[str] = mapped_column(
        card_condition_enum,
        primary_key=True,
        nullable=False,
        default=CardCondition.NEAR_MINT.value,
    )
    is_foil: Mapped[bool] = mapped_column(
        Boolean,
        primary_key=True,
        nullable=False,
        default=False,
    )
    language: Mapped[str] = mapped_column(
        card_language_enum,
        primary_key=True,
        nullable=False,
        default=CardLanguage.ENGLISH.value,
    )

    # Price tiers
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price_low: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_mid: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_high: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_market: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Volume indicators
    num_listings: Mapped[int | None] = mapped_column(nullable=True)
    total_quantity: Mapped[int | None] = mapped_column(nullable=True)

    # Source tracking: 'bulk', 'api', 'tcgplayer', 'calculated'
    source: Mapped[str] = mapped_column(String(20), default='bulk', nullable=False)

    # Relationships
    card: Mapped["Card"] = relationship("Card", back_populates="price_snapshots")
    marketplace: Mapped["Marketplace"] = relationship("Marketplace", back_populates="price_snapshots")

    def __repr__(self) -> str:
        return (
            f"<PriceSnapshot {self.card_id}@{self.marketplace_id} "
            f"{self.condition} {'Foil' if self.is_foil else 'Regular'}: "
            f"{self.price} {self.currency} at {self.time}>"
        )

    @property
    def condition_enum(self) -> CardCondition:
        """Get the condition as an enum."""
        return CardCondition(self.condition)

    @property
    def language_enum(self) -> CardLanguage:
        """Get the language as an enum."""
        return CardLanguage(self.language)
