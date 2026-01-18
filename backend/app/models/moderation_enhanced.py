"""
Enhanced moderation models for admin and dispute resolution.

Provides:
- ModerationAction: Track moderator actions (warn, restrict, suspend, ban)
- ModerationNote: Private notes about users
- Appeal: User appeals for moderation actions
- TradeDispute: Dispute resolution for trades
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.trade import TradeProposal
    from app.models.user import User


class ModerationAction(Base):
    """
    Record of a moderation action taken against a user.

    Actions include warnings, restrictions, suspensions, and bans.
    Each action can be appealed by the target user.
    """

    __tablename__ = "moderation_actions"

    # Who took the action
    moderator_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Who was actioned
    target_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Type of action: warn, restrict, suspend, ban, dismiss
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Reason for the action
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Duration for temporary actions
    duration_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # When the action expires (for temporary actions)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Optional link to related report
    related_report_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("user_reports.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Optional link to related dispute
    related_dispute_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("trade_disputes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    moderator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[moderator_id],
        lazy="joined",
    )
    target_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[target_user_id],
        lazy="joined",
    )
    appeal: Mapped[Optional["Appeal"]] = relationship(
        "Appeal",
        back_populates="moderation_action",
        uselist=False,
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_moderation_actions_target_active", "target_user_id", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<ModerationAction id={self.id} type={self.action_type} target={self.target_user_id}>"

    @property
    def is_active(self) -> bool:
        """Check if the action is still in effect."""
        if self.expires_at is None:
            # Permanent action
            return True
        return datetime.utcnow() < self.expires_at.replace(tzinfo=None)


class ModerationNote(Base):
    """
    Private notes from moderators about users.

    Visible only to moderators, used for tracking behavior patterns
    and documenting interactions.
    """

    __tablename__ = "moderation_notes"

    # Who wrote the note
    moderator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # About whom
    target_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Note content
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Relationships
    moderator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[moderator_id],
        lazy="joined",
    )
    target_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[target_user_id],
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_moderation_notes_target", "target_user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ModerationNote id={self.id} mod={self.moderator_id} target={self.target_user_id}>"


class Appeal(Base):
    """
    User appeal of a moderation action.

    Users can appeal warnings, restrictions, suspensions, and bans.
    Appeals are reviewed by moderators and can be upheld, reduced, or overturned.
    """

    __tablename__ = "appeals"

    # Who is appealing
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Which action is being appealed
    moderation_action_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("moderation_actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Appeal content
    appeal_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Supporting evidence URLs
    evidence_urls: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )

    # Status: pending, upheld, reduced, overturned
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
    )

    # Who reviewed the appeal
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Resolution notes from reviewer
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # When appeal was resolved
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="joined",
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reviewed_by],
        lazy="joined",
    )
    moderation_action: Mapped["ModerationAction"] = relationship(
        "ModerationAction",
        back_populates="appeal",
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_appeals_status", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Appeal id={self.id} user={self.user_id} action={self.moderation_action_id} status={self.status}>"


class TradeDispute(Base):
    """
    Dispute filed for a trade issue.

    Allows users to request moderator intervention when trades go wrong.
    Supports evidence collection and moderator resolution.
    """

    __tablename__ = "trade_disputes"

    # Which trade is disputed (nullable for disputes without proposals)
    trade_proposal_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("trade_proposals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Who filed the dispute
    filed_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Type of dispute: item_not_as_described, didnt_ship, other
    dispute_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Description of the issue
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Status: open, evidence_requested, resolved
    status: Mapped[str] = mapped_column(
        String(20),
        default="open",
        nullable=False,
        index=True,
    )

    # Assigned moderator
    assigned_moderator_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Resolution: buyer_wins, seller_wins, mutual_cancel, inconclusive
    resolution: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Resolution notes from moderator
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Snapshot of trade data at dispute time
    evidence_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # When dispute was resolved
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    trade_proposal: Mapped[Optional["TradeProposal"]] = relationship(
        "TradeProposal",
        lazy="joined",
    )
    filer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[filed_by],
        lazy="joined",
    )
    assigned_moderator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_moderator_id],
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_trade_disputes_status_filed", "status", "filed_by"),
        Index("ix_trade_disputes_assigned", "assigned_moderator_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<TradeDispute id={self.id} type={self.dispute_type} status={self.status}>"
