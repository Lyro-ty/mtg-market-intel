# Phase 2: Social + Trust Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable trading through proposals, messaging, and reputation - building trust at scale

**Architecture:** Trade proposal workflow with counter-offers, real-time messaging with conversations, reputation system with review aggregation, outcome tracking bridge to recommendation accuracy.

**Tech Stack:** FastAPI, SQLAlchemy, WebSocket (messaging), Celery (reputation recalculation), Redis (presence/typing indicators)

**Prerequisites:** Phase 1 must be complete (have/want lists, matching algorithm)

---

## Overview

Phase 2 has 4 major components:

| Component | Tasks | Description |
|-----------|-------|-------------|
| 2.1 Trade Proposals | 1-10 | Proposal workflow with status tracking |
| 2.2 Messaging | 11-18 | Conversations and real-time messaging |
| 2.3 Reputation | 19-26 | Reviews, scoring, and tiers |
| 2.4 Outcome Bridge | 27-30 | Connect recommendations to reputation |

---

## Task 1: Trade Status Enum Migration

**Files:**
- Create: `backend/alembic/versions/20260101_001_trade_status_enum.py`

**Step 1: Create migration**

```python
"""trade_status_enum

Create trade status enum type.
"""
from alembic import op

revision = '20260101_001'
down_revision = '20251231_002'  # After Phase 1
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TYPE trade_status AS ENUM (
            'draft', 'pending', 'viewed', 'accepted',
            'declined', 'countered', 'expired', 'cancelled', 'completed'
        )
    """)


def downgrade():
    op.execute("DROP TYPE trade_status")
```

**Step 2: Run migration**

Run: `docker compose exec backend alembic upgrade head`

**Step 3: Commit**

```bash
git add backend/alembic/versions/20260101_001_trade_status_enum.py
git commit -m "feat: add trade_status enum type"
```

---

## Task 2: Trade Proposals Migration

**Files:**
- Create: `backend/alembic/versions/20260101_002_trade_proposals.py`

**Step 1: Create migration**

```python
"""trade_proposals

Create trade_proposals table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

revision = '20260101_002'
down_revision = '20260101_001'
branch_labels = None
depends_on = None

trade_status = ENUM(
    'draft', 'pending', 'viewed', 'accepted',
    'declined', 'countered', 'expired', 'cancelled', 'completed',
    name='trade_status',
    create_type=False
)


def upgrade():
    op.create_table(
        'trade_proposals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('proposer_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipient_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', trade_status, server_default='pending', nullable=False),

        # What's being offered
        sa.Column('proposer_offers', sa.JSON(), nullable=False),
        sa.Column('proposer_offers_value', sa.Numeric(10, 2)),
        sa.Column('proposer_wants', sa.JSON(), nullable=False),
        sa.Column('proposer_wants_value', sa.Numeric(10, 2)),

        # Cash adjustments
        sa.Column('proposer_adds_cash', sa.Numeric(10, 2), server_default='0'),
        sa.Column('recipient_adds_cash', sa.Numeric(10, 2), server_default='0'),

        # Communication
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('decline_reason', sa.Text(), nullable=True),

        # Counter offers
        sa.Column('parent_proposal_id', sa.Integer(), sa.ForeignKey('trade_proposals.id'), nullable=True),
        sa.Column('counter_count', sa.Integer(), server_default='0'),

        # Completion
        sa.Column('completion_method', sa.String(50), nullable=True),
        sa.Column('completion_notes', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('viewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),

        sa.CheckConstraint('proposer_id != recipient_id', name='different_users'),
    )

    op.create_index('ix_proposals_proposer', 'trade_proposals', ['proposer_id', 'status'])
    op.create_index('ix_proposals_recipient', 'trade_proposals', ['recipient_id', 'status'])


def downgrade():
    op.drop_index('ix_proposals_recipient', table_name='trade_proposals')
    op.drop_index('ix_proposals_proposer', table_name='trade_proposals')
    op.drop_table('trade_proposals')
```

**Step 2: Run migration and commit**

---

## Task 3: Trade Proposal Model

**Files:**
- Create: `backend/app/models/trade_proposal.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Create model**

```python
"""Trade proposal model."""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text,
    Enum as SAEnum, JSON, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class TradeStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    VIEWED = "viewed"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    COUNTERED = "countered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class TradeProposal(Base):
    """Trade proposal between two users."""

    __tablename__ = "trade_proposals"
    __table_args__ = (
        CheckConstraint('proposer_id != recipient_id', name='different_users'),
    )

    proposer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[TradeStatus] = mapped_column(
        SAEnum(TradeStatus, name="trade_status", create_type=False),
        default=TradeStatus.PENDING,
        nullable=False,
    )

    # What's being offered (JSON arrays of card details)
    proposer_offers: Mapped[list] = mapped_column(JSON, nullable=False)
    proposer_offers_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    proposer_wants: Mapped[list] = mapped_column(JSON, nullable=False)
    proposer_wants_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # Cash adjustments
    proposer_adds_cash: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    recipient_adds_cash: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    # Communication
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decline_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Counter offers
    parent_proposal_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("trade_proposals.id"), nullable=True
    )
    counter_count: Mapped[int] = mapped_column(Integer, default=0)

    # Completion
    completion_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    completion_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    proposer: Mapped["User"] = relationship(
        "User", foreign_keys=[proposer_id], back_populates="proposals_sent"
    )
    recipient: Mapped["User"] = relationship(
        "User", foreign_keys=[recipient_id], back_populates="proposals_received"
    )
    parent_proposal: Mapped[Optional["TradeProposal"]] = relationship(
        "TradeProposal", remote_side="TradeProposal.id", back_populates="counter_proposals"
    )
    counter_proposals: Mapped[list["TradeProposal"]] = relationship(
        "TradeProposal", back_populates="parent_proposal"
    )

    def __repr__(self) -> str:
        return f"<TradeProposal {self.id} {self.proposer_id}->{self.recipient_id} {self.status}>"
```

**Step 2: Add relationships to User model and export**

---

## Task 4-10: Trade Proposal API

Implement endpoints for:
- `GET /trades` - List user's trades
- `GET /trades/incoming` - Pending proposals received
- `GET /trades/outgoing` - Proposals sent
- `POST /trades` - Create proposal
- `GET /trades/{id}` - Get proposal details
- `PATCH /trades/{id}` - Update status (accept/decline/counter)
- `POST /trades/{id}/complete` - Mark as completed
- `DELETE /trades/{id}` - Cancel proposal

Each task follows TDD pattern with tests first.

---

## Task 11: Conversations Migration

**Files:**
- Create: `backend/alembic/versions/20260101_003_conversations.py`

**Step 1: Create migration**

```python
"""conversations

Create conversations and messages tables.
"""
from alembic import op
import sqlalchemy as sa

revision = '20260101_003'
down_revision = '20260101_002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_a_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_b_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trade_proposal_id', sa.Integer(), sa.ForeignKey('trade_proposals.id'), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True)),
        sa.Column('last_message_preview', sa.String(255)),
        sa.Column('user_a_last_read_at', sa.DateTime(timezone=True)),
        sa.Column('user_b_last_read_at', sa.DateTime(timezone=True)),
        sa.Column('user_a_archived', sa.Boolean(), server_default='false'),
        sa.Column('user_b_archived', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),

        sa.CheckConstraint('user_a_id < user_b_id', name='ordered_users'),
        sa.UniqueConstraint('user_a_id', 'user_b_id'),
    )

    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('conversation_id', sa.Integer(), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('attachment_type', sa.String(20), nullable=True),
        sa.Column('attachment_id', sa.Integer(), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index('ix_messages_conversation', 'messages', ['conversation_id', 'created_at'])
    op.create_index('ix_conversations_users', 'conversations', ['user_a_id', 'user_b_id'])


def downgrade():
    op.drop_index('ix_conversations_users', table_name='conversations')
    op.drop_index('ix_messages_conversation', table_name='messages')
    op.drop_table('messages')
    op.drop_table('conversations')
```

---

## Task 12-18: Messaging System

Implement:
- Conversation and Message models
- Conversation API endpoints
- Message API endpoints
- WebSocket for real-time messaging
- Read receipts and typing indicators
- Message attachments (card links, trade proposals)

---

## Task 19: Reputation Tables Migration

**Files:**
- Create: `backend/alembic/versions/20260101_004_reputation.py`

**Step 1: Create migration**

```python
"""reputation

Create completed_trades, trade_reviews, and user_reputation tables.
"""
from alembic import op
import sqlalchemy as sa

revision = '20260101_004'
down_revision = '20260101_003'
branch_labels = None
depends_on = None


def upgrade():
    # Completed trades record
    op.create_table(
        'completed_trades',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('proposal_id', sa.Integer(), sa.ForeignKey('trade_proposals.id')),
        sa.Column('user_a_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('user_a_username', sa.String(255)),
        sa.Column('user_b_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('user_b_username', sa.String(255)),
        sa.Column('user_a_gave', sa.JSON(), nullable=False),
        sa.Column('user_a_gave_value', sa.Numeric(10, 2)),
        sa.Column('user_b_gave', sa.JSON(), nullable=False),
        sa.Column('user_b_gave_value', sa.Numeric(10, 2)),
        sa.Column('cash_from_a', sa.Numeric(10, 2), server_default='0'),
        sa.Column('cash_from_b', sa.Numeric(10, 2), server_default='0'),
        sa.Column('total_trade_value', sa.Numeric(10, 2)),
        sa.Column('completion_method', sa.String(50)),
        sa.Column('proposed_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('user_a_confirmed', sa.Boolean(), server_default='false'),
        sa.Column('user_b_confirmed', sa.Boolean(), server_default='false'),
        sa.Column('notes', sa.Text(), nullable=True),
    )

    # Trade reviews
    op.create_table(
        'trade_reviews',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trade_id', sa.Integer(), sa.ForeignKey('completed_trades.id'), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reviewee_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('overall_rating', sa.Integer(), nullable=False),
        sa.Column('communication_rating', sa.Integer(), nullable=True),
        sa.Column('packaging_rating', sa.Integer(), nullable=True),
        sa.Column('accuracy_rating', sa.Integer(), nullable=True),
        sa.Column('speed_rating', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('is_hidden', sa.Boolean(), server_default='false'),
        sa.Column('hidden_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),

        sa.UniqueConstraint('trade_id', 'reviewer_id'),
        sa.CheckConstraint('overall_rating BETWEEN 1 AND 5', name='valid_overall'),
    )

    # Aggregated reputation
    op.create_table(
        'user_reputation',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),

        # Trade counts
        sa.Column('total_trades', sa.Integer(), server_default='0'),
        sa.Column('trades_as_proposer', sa.Integer(), server_default='0'),
        sa.Column('trades_as_recipient', sa.Integer(), server_default='0'),

        # Values
        sa.Column('total_trade_value', sa.Numeric(12, 2), server_default='0'),
        sa.Column('average_trade_value', sa.Numeric(10, 2)),
        sa.Column('largest_trade_value', sa.Numeric(10, 2)),

        # Reviews
        sa.Column('total_reviews', sa.Integer(), server_default='0'),
        sa.Column('average_rating', sa.Numeric(3, 2)),
        sa.Column('communication_avg', sa.Numeric(3, 2)),
        sa.Column('packaging_avg', sa.Numeric(3, 2)),
        sa.Column('accuracy_avg', sa.Numeric(3, 2)),
        sa.Column('speed_avg', sa.Numeric(3, 2)),
        sa.Column('positive_reviews', sa.Integer(), server_default='0'),
        sa.Column('neutral_reviews', sa.Integer(), server_default='0'),
        sa.Column('negative_reviews', sa.Integer(), server_default='0'),

        # Computed score
        sa.Column('reputation_score', sa.Integer(), server_default='0'),
        sa.Column('reputation_tier', sa.String(20), server_default="'new'"),

        # Signal following
        sa.Column('signals_followed', sa.Integer(), server_default='0'),
        sa.Column('signals_profitable', sa.Integer(), server_default='0'),
        sa.Column('signal_accuracy_pct', sa.Numeric(5, 2)),

        # Negative events
        sa.Column('cancelled_trades', sa.Integer(), server_default='0'),
        sa.Column('disputes_involved', sa.Integer(), server_default='0'),
        sa.Column('blocks_received', sa.Integer(), server_default='0'),

        # Activity
        sa.Column('member_since', sa.DateTime(timezone=True)),
        sa.Column('first_trade_at', sa.DateTime(timezone=True)),
        sa.Column('last_trade_at', sa.DateTime(timezone=True)),

        # Streaks
        sa.Column('current_positive_streak', sa.Integer(), server_default='0'),
        sa.Column('longest_positive_streak', sa.Integer(), server_default='0'),

        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('user_reputation')
    op.drop_table('trade_reviews')
    op.drop_table('completed_trades')
```

---

## Task 20-26: Reputation System

Implement:
- CompletedTrade, TradeReview, UserReputation models
- Review submission API
- Reputation calculation service
- Reputation display endpoints
- Tier badges and unlocks
- Decay calculation for inactive users

---

## Task 27-30: Outcome Bridge

**Files:**
- Create: `backend/app/models/recommendation_action.py`
- Create: `backend/app/services/reputation/signal_bridge.py`

Connect recommendation outcomes to user reputation:
- Track when users follow recommendations (explicit or implicit)
- Evaluate outcomes when recommendations are closed
- Update user signal stats in reputation
- Award bonus reputation for profitable signal follows

---

## Summary

Phase 2 implements:

| Component | Tasks | Key Deliverables |
|-----------|-------|------------------|
| Trade Proposals | 1-10 | Full proposal workflow |
| Messaging | 11-18 | Real-time conversations |
| Reputation | 19-26 | Reviews and scoring |
| Outcome Bridge | 27-30 | Connect signals to reputation |

**Total: 30 tasks**

After Phase 2:
- Users can propose, negotiate, and complete trades
- Real-time messaging between traders
- Reputation system with reviews and tiers
- Signal following tracked for reputation

---

Plan complete. Ready for Phase 3.
