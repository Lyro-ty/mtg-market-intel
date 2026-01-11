"""
Trading Post models for LGS (Local Game Store) features.

Trading Posts are verified stores that can:
- Receive trade-in quote submissions from users
- Set their buylist margin (% of market price they pay)
- Create and promote events (tournaments, sales, releases)
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.user import User


class QuoteStatus(str, Enum):
    """Status of a trade quote."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    EXPIRED = "expired"


class SubmissionStatus(str, Enum):
    """Status of a quote submission to a store."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    COUNTERED = "countered"
    DECLINED = "declined"
    USER_ACCEPTED = "user_accepted"  # User accepted counter
    USER_DECLINED = "user_declined"  # User declined counter


class EventType(str, Enum):
    """Type of trading post event."""
    TOURNAMENT = "tournament"
    SALE = "sale"
    RELEASE = "release"
    MEETUP = "meetup"


class TradingPost(Base):
    """
    A verified Local Game Store (LGS) on the platform.

    Trading Posts can receive trade-in quotes from users and promote events.
    Each user can only have one Trading Post profile.
    """
    __tablename__ = "trading_posts"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    store_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Location
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    country: Mapped[str] = mapped_column(String(50), default="US", nullable=False)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Contact
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Store details
    hours: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {"monday": "10:00-20:00", ...}
    services: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # ['singles', 'tournaments', 'buylist']
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Buylist settings
    buylist_margin: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.50"),  # 50% of market price
        nullable=False
    )

    # Verification
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'manual', 'business_license', 'phone'

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="trading_post")
    events: Mapped[List["TradingPostEvent"]] = relationship(
        "TradingPostEvent",
        back_populates="trading_post",
        cascade="all, delete-orphan"
    )
    submissions: Mapped[List["TradeQuoteSubmission"]] = relationship(
        "TradeQuoteSubmission",
        back_populates="trading_post",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TradingPost {self.store_name} ({self.city}, {self.state})>"

    @property
    def is_verified(self) -> bool:
        """Check if store has full verification badge."""
        return self.verified_at is not None

    @property
    def is_email_verified(self) -> bool:
        """Check if store email is verified (required to go live)."""
        return self.email_verified_at is not None


class TradeQuote(Base):
    """
    A trade-in quote created by a user.

    Users can add cards to a quote, then submit it to one or more Trading Posts.
    """
    __tablename__ = "trade_quotes"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=QuoteStatus.DRAFT.value,
        nullable=False,
        index=True
    )
    total_market_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="trade_quotes")
    items: Mapped[List["TradeQuoteItem"]] = relationship(
        "TradeQuoteItem",
        back_populates="quote",
        cascade="all, delete-orphan"
    )
    submissions: Mapped[List["TradeQuoteSubmission"]] = relationship(
        "TradeQuoteSubmission",
        back_populates="quote",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TradeQuote {self.id} ({self.status}, ${self.total_market_value})>"

    def recalculate_totals(self) -> None:
        """Recalculate total_market_value and item_count from items."""
        self.item_count = sum(item.quantity for item in self.items)
        self.total_market_value = sum(
            item.market_price * item.quantity for item in self.items
        )


class TradeQuoteItem(Base):
    """
    An item (card) within a trade quote.

    Stores the market price at time of addition as a snapshot.
    """
    __tablename__ = "trade_quote_items"

    quote_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("trade_quotes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    card_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    condition: Mapped[str] = mapped_column(String(20), default="NM", nullable=False)
    market_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Relationships
    quote: Mapped["TradeQuote"] = relationship("TradeQuote", back_populates="items")
    card: Mapped["Card"] = relationship("Card")

    def __repr__(self) -> str:
        return f"<TradeQuoteItem {self.card_id} x{self.quantity} ({self.condition})>"


class TradeQuoteSubmission(Base):
    """
    A submission of a trade quote to a specific Trading Post.

    Tracks the offer amount (based on store margin) and the store's response.
    """
    __tablename__ = "trade_quote_submissions"

    quote_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("trade_quotes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    trading_post_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("trading_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    offer_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default=SubmissionStatus.PENDING.value,
        nullable=False,
        index=True
    )
    counter_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    counter_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    store_responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    user_responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    quote: Mapped["TradeQuote"] = relationship("TradeQuote", back_populates="submissions")
    trading_post: Mapped["TradingPost"] = relationship("TradingPost", back_populates="submissions")

    def __repr__(self) -> str:
        return f"<TradeQuoteSubmission {self.id} (${self.offer_amount}, {self.status})>"


class TradingPostEvent(Base):
    """
    An event hosted by a Trading Post.

    Events can be tournaments, sales, releases, or meetups.
    """
    __tablename__ = "trading_post_events"

    trading_post_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("trading_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    format: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # modern, standard, commander, etc.
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    entry_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    max_players: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    trading_post: Mapped["TradingPost"] = relationship("TradingPost", back_populates="events")

    def __repr__(self) -> str:
        return f"<TradingPostEvent {self.title} ({self.event_type}, {self.start_time})>"
