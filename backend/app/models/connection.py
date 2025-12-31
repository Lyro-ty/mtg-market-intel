"""
Connection and messaging models for user-to-user communication.
"""
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    ARRAY,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ConnectionRequest(Base, TimestampMixin):
    """
    Connection requests between users.

    Users must have an accepted connection before they can message each other.
    """
    __tablename__ = "connection_requests"

    requester_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional context for the request
    card_ids: Mapped[Optional[list[int]]] = mapped_column(
        ARRAY(Integer),
        nullable=True,
    )
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status: pending, accepted, declined, expired
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
    )

    responded_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc) + timedelta(days=7),
        nullable=False,
    )

    # Relationships
    requester: Mapped["User"] = relationship(
        "User",
        foreign_keys=[requester_id],
        back_populates="sent_connection_requests",
    )
    recipient: Mapped["User"] = relationship(
        "User",
        foreign_keys=[recipient_id],
        back_populates="received_connection_requests",
    )

    __table_args__ = (
        Index("ix_connection_requests_recipient_status", "recipient_id", "status"),
        # One pending request per pair (allows re-request after decline)
    )

    def __repr__(self) -> str:
        return f"<ConnectionRequest {self.requester_id} -> {self.recipient_id} ({self.status})>"


class Message(Base):
    """
    Direct messages between connected users.
    """
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    sender: Mapped["User"] = relationship(
        "User",
        foreign_keys=[sender_id],
        back_populates="sent_messages",
    )
    recipient: Mapped["User"] = relationship(
        "User",
        foreign_keys=[recipient_id],
        back_populates="received_messages",
    )

    __table_args__ = (
        Index("ix_messages_recipient_read", "recipient_id", "read_at"),
        Index(
            "ix_messages_conversation",
            func.least("sender_id", "recipient_id"),
            func.greatest("sender_id", "recipient_id"),
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<Message {self.sender_id} -> {self.recipient_id}>"


class UserEndorsement(Base):
    """
    Community endorsements for users.

    Not trade-based - any connected user can endorse another.
    """
    __tablename__ = "user_endorsements"

    id: Mapped[int] = mapped_column(primary_key=True)

    endorser_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    endorsed_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Types: trustworthy, knowledgeable, responsive, fair_trader
    endorsement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    endorser: Mapped["User"] = relationship(
        "User",
        foreign_keys=[endorser_id],
        back_populates="given_endorsements",
    )
    endorsed: Mapped["User"] = relationship(
        "User",
        foreign_keys=[endorsed_id],
        back_populates="received_endorsements",
    )

    __table_args__ = (
        Index("ix_endorsements_endorsed", "endorsed_id"),
        # One endorsement per type per pair
        Index(
            "uq_endorsement_type",
            "endorser_id",
            "endorsed_id",
            "endorsement_type",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<Endorsement {self.endorser_id} -> {self.endorsed_id}: {self.endorsement_type}>"


class BlockedUser(Base):
    """
    Blocked users - prevents messaging and connection requests.
    """
    __tablename__ = "blocked_users"

    id: Mapped[int] = mapped_column(primary_key=True)

    blocker_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    blocked_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("uq_blocked_pair", "blocker_id", "blocked_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<BlockedUser {self.blocker_id} blocked {self.blocked_id}>"


class UserReport(Base):
    """
    User reports for admin review.
    """
    __tablename__ = "user_reports"

    id: Mapped[int] = mapped_column(primary_key=True)

    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reported_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status: pending, reviewed, resolved, dismissed
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<UserReport {self.reporter_id} reported {self.reported_id}: {self.reason}>"
