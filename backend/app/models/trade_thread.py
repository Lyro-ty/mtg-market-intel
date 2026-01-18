"""
Trade thread models for in-trade messaging.

Provides messaging system for trade negotiations:
- TradeThread: Container for messages linked to a trade proposal
- TradeThreadMessage: Individual messages with card embeds and reactions
- TradeThreadAttachment: File attachments for messages (e.g., card photos)
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.trade import TradeProposal
    from app.models.user import User


class TradeThread(Base):
    """
    A message thread associated with a trade proposal.

    Each trade proposal can have exactly one thread for negotiation
    and communication between the trading parties.
    """

    __tablename__ = "trade_threads"

    # Link to trade proposal (one-to-one)
    trade_proposal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("trade_proposals.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Thread metadata
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Relationships
    trade_proposal: Mapped["TradeProposal"] = relationship(
        "TradeProposal",
        back_populates="thread",
        lazy="joined",
    )
    messages: Mapped[list["TradeThreadMessage"]] = relationship(
        "TradeThreadMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="TradeThreadMessage.created_at",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TradeThread id={self.id} proposal={self.trade_proposal_id} messages={self.message_count}>"


class TradeThreadMessage(Base):
    """
    A single message in a trade thread.

    Supports text content, card embeds, file attachments, and emoji reactions.
    """

    __tablename__ = "trade_thread_messages"

    # Thread reference
    thread_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("trade_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Sender
    sender_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # Message content
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Optional card embed
    card_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("cards.id"),
        nullable=True,
    )

    # Attachment tracking
    has_attachments: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Emoji reactions as JSONB
    # Format: {"emoji": [user_id1, user_id2], "emoji2": [user_id3]}
    reactions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        server_default="{}",
        nullable=True,
    )

    # Soft delete timestamp
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Report tracking
    reported_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    thread: Mapped["TradeThread"] = relationship(
        "TradeThread",
        back_populates="messages",
    )
    sender: Mapped["User"] = relationship(
        "User",
        lazy="joined",
    )
    card: Mapped[Optional["Card"]] = relationship(
        "Card",
        lazy="joined",
    )
    attachments: Mapped[list["TradeThreadAttachment"]] = relationship(
        "TradeThreadAttachment",
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TradeThreadMessage id={self.id} thread={self.thread_id} sender={self.sender_id}>"


class TradeThreadAttachment(Base):
    """
    A file attachment on a trade thread message.

    Used for sharing images of cards, condition photos, etc.
    """

    __tablename__ = "trade_thread_attachments"

    # Message reference
    message_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("trade_thread_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # File details
    file_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    file_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # e.g., "image/jpeg", "image/png"
    file_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )  # Size in bytes

    # Auto-purge timestamp (for cleanup of old attachments)
    purge_after: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship
    message: Mapped["TradeThreadMessage"] = relationship(
        "TradeThreadMessage",
        back_populates="attachments",
    )

    def __repr__(self) -> str:
        return f"<TradeThreadAttachment id={self.id} message={self.message_id} type={self.file_type}>"
