"""
Trade proposal models for user-to-user trading.

Enables structured trade proposals between users with:
- Card lists on both sides
- Counter-proposals
- Status tracking
- Completion confirmation
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.user import User


class TradeStatus(str, Enum):
    """Status of a trade proposal."""
    PENDING = "pending"          # Awaiting response
    ACCEPTED = "accepted"        # Both parties agreed
    DECLINED = "declined"        # Rejected by recipient
    COUNTERED = "countered"      # Counter-proposal made
    EXPIRED = "expired"          # No response before expiry
    COMPLETED = "completed"      # Trade completed externally
    CANCELLED = "cancelled"      # Cancelled by proposer


class TradeSide(str, Enum):
    """Which side of the trade an item belongs to."""
    PROPOSER = "proposer"   # Items offered by proposer
    RECIPIENT = "recipient"  # Items requested from recipient


class TradeProposal(Base):
    """
    A trade proposal between two users.

    Tracks the full lifecycle from proposal to completion.
    """

    __tablename__ = "trade_proposals"

    # Parties
    proposer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        SQLEnum(TradeStatus, native_enum=False, length=20),
        default=TradeStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Optional message
    message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Counter-proposal reference
    parent_proposal_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("trade_proposals.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.utcnow() + timedelta(days=7),
        nullable=False,
    )

    # Completion tracking
    proposer_confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    recipient_confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Relationships
    proposer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[proposer_id],
        lazy="joined",
        overlaps="sent_trade_proposals",
    )
    recipient: Mapped["User"] = relationship(
        "User",
        foreign_keys=[recipient_id],
        lazy="joined",
        overlaps="received_trade_proposals",
    )
    items: Mapped[list["TradeProposalItem"]] = relationship(
        "TradeProposalItem",
        back_populates="proposal",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    parent_proposal: Mapped[Optional["TradeProposal"]] = relationship(
        "TradeProposal",
        remote_side="TradeProposal.id",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<TradeProposal id={self.id} {self.proposer_id}->{self.recipient_id} status={self.status}>"

    @property
    def is_expired(self) -> bool:
        """Check if the proposal has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def proposer_items(self) -> list["TradeProposalItem"]:
        """Get items offered by proposer."""
        return [i for i in self.items if i.side == TradeSide.PROPOSER]

    @property
    def recipient_items(self) -> list["TradeProposalItem"]:
        """Get items requested from recipient."""
        return [i for i in self.items if i.side == TradeSide.RECIPIENT]


class TradeProposalItem(Base):
    """
    An item in a trade proposal.

    Represents a specific card with quantity and condition.
    """

    __tablename__ = "trade_proposal_items"

    proposal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("trade_proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Which side of the trade
    side: Mapped[str] = mapped_column(
        SQLEnum(TradeSide, native_enum=False, length=20),
        nullable=False,
    )

    # Card details
    card_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    condition: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )  # NM, LP, MP, HP, DMG

    # Optional price reference at time of proposal
    price_at_proposal: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    # Relationships
    proposal: Mapped["TradeProposal"] = relationship(
        "TradeProposal",
        back_populates="items",
    )
    card: Mapped["Card"] = relationship(
        "Card",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<TradeProposalItem proposal={self.proposal_id} card={self.card_id} qty={self.quantity}>"
