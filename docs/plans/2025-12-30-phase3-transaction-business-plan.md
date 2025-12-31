# Phase 3: Transaction + Business Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete trade flow with optional escrow, LGS tools, and user-generated signals

**Architecture:** Payment escrow via Stripe Connect (optional), LGS business accounts with inventory sync, user-generated signals with progressive visibility unlocks.

**Tech Stack:** FastAPI, SQLAlchemy, Stripe Connect API, Celery (inventory sync), WebSocket (live pricing)

**Prerequisites:** Phase 2 must be complete (trade proposals, messaging, reputation)

---

## Overview

Phase 3 has 3 major components:

| Component | Tasks | Description |
|-----------|-------|-------------|
| 3.1 User-Generated Signals | 1-10 | Users create and share trading signals |
| 3.2 LGS Dashboard | 11-18 | Business accounts and tools |
| 3.3 Payment Escrow | 19-24 | Optional Stripe Connect escrow |

---

## Task 1: User Signals Migration

**Files:**
- Create: `backend/alembic/versions/20260201_001_user_signals.py`

**Step 1: Create migration**

```python
"""user_signals

Add user-generated signal fields to recommendations table.
"""
from alembic import op
import sqlalchemy as sa

revision = '20260201_001'
down_revision = '20260101_004'  # After Phase 2
branch_labels = None
depends_on = None


def upgrade():
    # Add user-generated signal fields to recommendations
    op.add_column('recommendations',
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True)
    )
    op.add_column('recommendations',
        sa.Column('is_user_generated', sa.Boolean(), server_default='false', nullable=False)
    )
    op.add_column('recommendations',
        sa.Column('is_public', sa.Boolean(), server_default='true', nullable=False)
    )
    op.add_column('recommendations',
        sa.Column('follower_count', sa.Integer(), server_default='0', nullable=False)
    )
    op.add_column('recommendations',
        sa.Column('user_rationale', sa.Text(), nullable=True)
    )
    op.add_column('recommendations',
        sa.Column('user_target_price', sa.Numeric(10, 2), nullable=True)
    )
    op.add_column('recommendations',
        sa.Column('user_target_date', sa.DateTime(timezone=True), nullable=True)
    )

    # Signal followers table
    op.create_table(
        'signal_followers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('recommendation_id', sa.Integer(), sa.ForeignKey('recommendations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('followed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('acted_on', sa.Boolean(), server_default='false'),
        sa.Column('acted_at', sa.DateTime(timezone=True)),
        sa.Column('outcome_evaluated', sa.Boolean(), server_default='false'),
        sa.Column('outcome_profit_pct', sa.Numeric(10, 2)),

        sa.UniqueConstraint('recommendation_id', 'user_id'),
    )

    op.create_index('ix_recommendations_user', 'recommendations', ['created_by_user_id'])
    op.create_index('ix_signal_followers_user', 'signal_followers', ['user_id'])


def downgrade():
    op.drop_index('ix_signal_followers_user', table_name='signal_followers')
    op.drop_index('ix_recommendations_user', table_name='recommendations')
    op.drop_table('signal_followers')
    op.drop_column('recommendations', 'user_target_date')
    op.drop_column('recommendations', 'user_target_price')
    op.drop_column('recommendations', 'user_rationale')
    op.drop_column('recommendations', 'follower_count')
    op.drop_column('recommendations', 'is_public')
    op.drop_column('recommendations', 'is_user_generated')
    op.drop_column('recommendations', 'created_by_user_id')
```

**Step 2: Run migration and commit**

---

## Task 2: Update Recommendation Model

**Files:**
- Modify: `backend/app/models/recommendation.py`

**Step 1: Add user signal fields**

Add to Recommendation model:
```python
    # User-generated signal fields (Phase 3)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    is_user_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    follower_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    user_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_target_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    user_target_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    created_by: Mapped[Optional["User"]] = relationship("User", back_populates="signals_created")
    followers: Mapped[list["SignalFollower"]] = relationship(
        "SignalFollower", back_populates="recommendation", cascade="all, delete-orphan"
    )
```

**Step 2: Create SignalFollower model**

Create `backend/app/models/signal_follower.py`:
```python
"""Signal follower model."""
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.recommendation import Recommendation


class SignalFollower(Base):
    """Tracks users following a signal."""

    __tablename__ = "signal_followers"
    __table_args__ = (
        UniqueConstraint('recommendation_id', 'user_id'),
    )

    recommendation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    followed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    acted_on: Mapped[bool] = mapped_column(Boolean, default=False)
    acted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    outcome_evaluated: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome_profit_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # Relationships
    recommendation: Mapped["Recommendation"] = relationship(
        "Recommendation", back_populates="followers"
    )
    user: Mapped["User"] = relationship("User", back_populates="signals_followed")
```

---

## Task 3: Signal Visibility Service

**Files:**
- Create: `backend/app/services/signals/visibility.py`

**Step 1: Create visibility service**

```python
"""Signal visibility and unlock logic."""
from enum import Enum
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserReputation, Recommendation


class SignalVisibility(str, Enum):
    """Signal visibility levels."""
    PRIVATE = "private"       # Only creator sees
    FOLLOWERS = "followers"   # Only followers see
    PUBLIC = "public"         # Everyone sees


class VisibilityUnlocks:
    """Thresholds for visibility unlocks."""

    # Reputation tier required to create public signals
    PUBLIC_SIGNAL_TIER = "silver"  # 300+ reputation

    # Minimum trades for private signals
    MIN_TRADES_PRIVATE = 5

    # Minimum accuracy for featured signals
    FEATURED_ACCURACY = 0.65


class SignalVisibilityService:
    """Manage signal visibility based on user reputation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def can_create_signal(self, user_id: int) -> tuple[bool, str]:
        """Check if user can create signals at all."""
        rep = await self._get_reputation(user_id)

        if not rep or rep.total_trades < VisibilityUnlocks.MIN_TRADES_PRIVATE:
            return False, f"Complete at least {VisibilityUnlocks.MIN_TRADES_PRIVATE} trades first"

        return True, "ok"

    async def can_create_public_signal(self, user_id: int) -> tuple[bool, str]:
        """Check if user can create public signals."""
        rep = await self._get_reputation(user_id)

        if not rep:
            return False, "Build reputation first"

        tier_order = ["new", "bronze", "silver", "gold", "platinum", "diamond"]
        user_tier_idx = tier_order.index(rep.reputation_tier)
        required_tier_idx = tier_order.index(VisibilityUnlocks.PUBLIC_SIGNAL_TIER)

        if user_tier_idx < required_tier_idx:
            return False, f"Reach {VisibilityUnlocks.PUBLIC_SIGNAL_TIER} tier to create public signals"

        return True, "ok"

    async def get_max_visibility(self, user_id: int) -> SignalVisibility:
        """Get maximum visibility level user can use."""
        can_public, _ = await self.can_create_public_signal(user_id)
        if can_public:
            return SignalVisibility.PUBLIC

        can_create, _ = await self.can_create_signal(user_id)
        if can_create:
            return SignalVisibility.FOLLOWERS

        return SignalVisibility.PRIVATE

    async def is_featured_eligible(self, user_id: int) -> bool:
        """Check if user's signals can be featured."""
        rep = await self._get_reputation(user_id)

        if not rep or rep.reputation_tier not in ["gold", "platinum", "diamond"]:
            return False

        if not rep.signal_accuracy_pct:
            return False

        return float(rep.signal_accuracy_pct) >= VisibilityUnlocks.FEATURED_ACCURACY * 100

    async def _get_reputation(self, user_id: int) -> Optional[UserReputation]:
        """Get user's reputation record."""
        from app.models import UserReputation
        result = await self.db.execute(
            select(UserReputation).where(UserReputation.user_id == user_id)
        )
        return result.scalar_one_or_none()
```

---

## Task 4-10: User Signal API

Implement endpoints for:
- `POST /signals` - Create user signal
- `GET /signals` - List public signals
- `GET /signals/mine` - List user's own signals
- `GET /signals/{id}` - Get signal details
- `POST /signals/{id}/follow` - Follow a signal
- `DELETE /signals/{id}/follow` - Unfollow
- `GET /signals/leaderboard` - Top signal creators

---

## Task 11: LGS Account Type Migration

**Files:**
- Create: `backend/alembic/versions/20260201_002_lgs_accounts.py`

**Step 1: Create migration**

```python
"""lgs_accounts

Add LGS (Local Game Store) account type and business features.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '20260201_002'
down_revision = '20260201_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add account type to users
    op.add_column('users',
        sa.Column('account_type', sa.String(20), server_default='personal', nullable=False)
    )
    op.add_column('users',
        sa.Column('business_name', sa.String(255), nullable=True)
    )
    op.add_column('users',
        sa.Column('business_verified', sa.Boolean(), server_default='false', nullable=False)
    )

    # LGS details table
    op.create_table(
        'lgs_profiles',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),

        # Store info
        sa.Column('store_name', sa.String(255), nullable=False),
        sa.Column('store_address', sa.Text()),
        sa.Column('store_city', sa.String(100)),
        sa.Column('store_state', sa.String(50)),
        sa.Column('store_postal', sa.String(20)),
        sa.Column('store_country', sa.String(2), server_default='US'),
        sa.Column('store_phone', sa.String(20)),
        sa.Column('store_website', sa.String(500)),

        # Location
        sa.Column('latitude', sa.Numeric(10, 8)),
        sa.Column('longitude', sa.Numeric(11, 8)),

        # Features
        sa.Column('offers_buylist', sa.Boolean(), server_default='false'),
        sa.Column('offers_trades', sa.Boolean(), server_default='true'),
        sa.Column('offers_events', sa.Boolean(), server_default='false'),
        sa.Column('trade_in_bonus_pct', sa.Numeric(5, 2), server_default='0'),

        # Inventory sync
        sa.Column('inventory_sync_provider', sa.String(50)),  # tcgplayer, crystal_commerce, etc.
        sa.Column('inventory_sync_config', JSONB, server_default='{}'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True)),
        sa.Column('sync_status', sa.String(20)),

        # Hours (JSON: {"monday": {"open": "10:00", "close": "21:00"}, ...})
        sa.Column('hours', JSONB, server_default='{}'),

        # Settings
        sa.Column('auto_price_adjustment', sa.Boolean(), server_default='true'),
        sa.Column('price_adjustment_pct', sa.Numeric(5, 2), server_default='0'),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index('ix_lgs_location', 'lgs_profiles', ['latitude', 'longitude'])
    op.create_index('ix_users_account_type', 'users', ['account_type'])


def downgrade():
    op.drop_index('ix_users_account_type', table_name='users')
    op.drop_index('ix_lgs_location', table_name='lgs_profiles')
    op.drop_table('lgs_profiles')
    op.drop_column('users', 'business_verified')
    op.drop_column('users', 'business_name')
    op.drop_column('users', 'account_type')
```

---

## Task 12: LGS Profile Model

**Files:**
- Create: `backend/app/models/lgs_profile.py`

**Step 1: Create model**

```python
"""LGS (Local Game Store) profile model."""
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class LGSProfile(Base):
    """Local Game Store business profile."""

    __tablename__ = "lgs_profiles"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )

    # Store info
    store_name: Mapped[str] = mapped_column(String(255), nullable=False)
    store_address: Mapped[Optional[str]] = mapped_column(Text)
    store_city: Mapped[Optional[str]] = mapped_column(String(100))
    store_state: Mapped[Optional[str]] = mapped_column(String(50))
    store_postal: Mapped[Optional[str]] = mapped_column(String(20))
    store_country: Mapped[str] = mapped_column(String(2), default="US")
    store_phone: Mapped[Optional[str]] = mapped_column(String(20))
    store_website: Mapped[Optional[str]] = mapped_column(String(500))

    # Location
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 8))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(11, 8))

    # Features
    offers_buylist: Mapped[bool] = mapped_column(Boolean, default=False)
    offers_trades: Mapped[bool] = mapped_column(Boolean, default=True)
    offers_events: Mapped[bool] = mapped_column(Boolean, default=False)
    trade_in_bonus_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)

    # Inventory sync
    inventory_sync_provider: Mapped[Optional[str]] = mapped_column(String(50))
    inventory_sync_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sync_status: Mapped[Optional[str]] = mapped_column(String(20))

    # Hours
    hours: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Settings
    auto_price_adjustment: Mapped[bool] = mapped_column(Boolean, default=True)
    price_adjustment_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="lgs_profile")

    def __repr__(self) -> str:
        return f"<LGSProfile {self.store_name}>"
```

---

## Task 13-18: LGS API and Dashboard

Implement:
- LGS registration and verification flow
- Store profile management API
- Inventory sync service (TCGPlayer, Crystal Commerce)
- Smart buylist pricing based on demand
- Local customer matching
- Store finder for users

---

## Task 19: Escrow Tables Migration

**Files:**
- Create: `backend/alembic/versions/20260201_003_escrow.py`

**Step 1: Create migration**

```python
"""escrow

Add escrow tables for secure high-value trades.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

revision = '20260201_003'
down_revision = '20260201_002'
branch_labels = None
depends_on = None


def upgrade():
    # Escrow status enum
    op.execute("""
        CREATE TYPE escrow_status AS ENUM (
            'pending_payment', 'payment_received', 'items_shipped',
            'items_received', 'disputed', 'released', 'refunded', 'cancelled'
        )
    """)

    escrow_status = ENUM(
        'pending_payment', 'payment_received', 'items_shipped',
        'items_received', 'disputed', 'released', 'refunded', 'cancelled',
        name='escrow_status', create_type=False
    )

    op.create_table(
        'escrow_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trade_id', sa.Integer(), sa.ForeignKey('completed_trades.id'), nullable=False),

        # Parties
        sa.Column('payer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('payee_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),

        # Amounts
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('fee_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('total_charged', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), server_default='USD'),

        # Stripe
        sa.Column('stripe_payment_intent_id', sa.String(255)),
        sa.Column('stripe_transfer_id', sa.String(255)),

        # Status
        sa.Column('status', escrow_status, server_default='pending_payment'),

        # Shipping
        sa.Column('payer_tracking', sa.String(255)),
        sa.Column('payee_tracking', sa.String(255)),
        sa.Column('payer_shipped_at', sa.DateTime(timezone=True)),
        sa.Column('payee_shipped_at', sa.DateTime(timezone=True)),
        sa.Column('payer_received_at', sa.DateTime(timezone=True)),
        sa.Column('payee_received_at', sa.DateTime(timezone=True)),

        # Dispute
        sa.Column('dispute_reason', sa.Text()),
        sa.Column('dispute_opened_at', sa.DateTime(timezone=True)),
        sa.Column('dispute_resolved_at', sa.DateTime(timezone=True)),
        sa.Column('dispute_resolution', sa.Text()),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('released_at', sa.DateTime(timezone=True)),
        sa.Column('expires_at', sa.DateTime(timezone=True)),

        sa.UniqueConstraint('trade_id'),
    )

    # User Stripe Connect accounts
    op.create_table(
        'stripe_connect_accounts',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('stripe_account_id', sa.String(255), nullable=False, unique=True),
        sa.Column('account_status', sa.String(50)),
        sa.Column('charges_enabled', sa.Boolean(), server_default='false'),
        sa.Column('payouts_enabled', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table('stripe_connect_accounts')
    op.drop_table('escrow_transactions')
    op.execute("DROP TYPE escrow_status")
```

---

## Task 20-24: Escrow System

Implement:
- Stripe Connect account onboarding
- Escrow creation for high-value trades
- Payment processing
- Shipping confirmation flow
- Release/refund logic
- Dispute handling

---

## Summary

Phase 3 implements:

| Component | Tasks | Key Deliverables |
|-----------|-------|------------------|
| User Signals | 1-10 | Signal creation with visibility tiers |
| LGS Dashboard | 11-18 | Business accounts, inventory sync |
| Payment Escrow | 19-24 | Stripe Connect integration |

**Total: 24 tasks**

After Phase 3:
- Users can create and share trading signals
- LGS can register and sync inventory
- High-value trades can use escrow
- Platform is complete!

---

## Future Considerations

Post-Phase 3 features to consider:
- Mobile app (React Native)
- Push notifications
- Event management for LGS
- Advanced analytics for stores
- API for third-party integrations
- Affiliate program
- Premium subscriptions

---

Plan complete. All phases documented.
