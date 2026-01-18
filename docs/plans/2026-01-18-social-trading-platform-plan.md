# Social Trading Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a profile-centric social trading platform with trading card-inspired profiles, achievements, trade chat, user directory, moderation, and real-time notifications.

**Architecture:** Profile cards are the central identity component displayed throughout the app. Achievements unlock frame tiers and boost discovery priority. Trade threads provide context-aware messaging. WebSocket powers real-time updates. Moderation uses a tiered approach (self-service → community → automated → admin).

**Tech Stack:** FastAPI + SQLAlchemy (backend), Next.js 14 + React Query + Tailwind (frontend), PostgreSQL, Redis, WebSocket (notifications)

**Design Doc:** `docs/plans/2026-01-18-social-trading-platform-design.md`

---

## Phase 1: Database Foundations

### Task 1.1: Create Achievement Tables Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_add_achievement_tables.py`

**Step 1: Generate migration file**

Run: `cd /root/mtg-market-intel/mtg-market-intel && docker compose exec backend alembic revision -m "add achievement tables"`

**Step 2: Write migration**

```python
"""add achievement tables

Revision ID: xxxx
Revises: [previous]
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = 'xxxx'
down_revision = '[previous]'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Achievement definitions
    op.create_table(
        'achievement_definitions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('icon', sa.String(100)),
        sa.Column('threshold', JSONB),
        sa.Column('discovery_points', sa.Integer(), default=0),
        sa.Column('frame_tier_unlock', sa.String(20)),
        sa.Column('rarity_percent', sa.Numeric(5, 2)),
        sa.Column('is_hidden', sa.Boolean(), default=False),
        sa.Column('is_seasonal', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # User achievements
    op.create_table(
        'user_achievements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('achievement_id', sa.Integer(), sa.ForeignKey('achievement_definitions.id'), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('progress', JSONB),
        sa.UniqueConstraint('user_id', 'achievement_id', name='uq_user_achievement'),
    )
    op.create_index('idx_user_achievements_user', 'user_achievements', ['user_id'])

    # User frames
    op.create_table(
        'user_frames',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('frame_tier', sa.String(20), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean(), default=False),
        sa.UniqueConstraint('user_id', 'frame_tier', name='uq_user_frame'),
    )


def downgrade() -> None:
    op.drop_table('user_frames')
    op.drop_index('idx_user_achievements_user')
    op.drop_table('user_achievements')
    op.drop_table('achievement_definitions')
```

**Step 3: Run migration**

Run: `docker compose exec backend alembic upgrade head`
Expected: Migration applies successfully

**Step 4: Verify tables exist**

Run: `docker compose exec db psql -U dualcaster_user -d dualcaster_deals -c "\dt *achievement*"`
Expected: Tables `achievement_definitions`, `user_achievements` listed

**Step 5: Commit**

```bash
git add backend/alembic/versions/*achievement*
git commit -m "db: add achievement and frame tables"
```

---

### Task 1.2: Create Trade Thread Tables Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_add_trade_thread_tables.py`

**Step 1: Generate migration file**

Run: `docker compose exec backend alembic revision -m "add trade thread tables"`

**Step 2: Write migration**

```python
"""add trade thread tables

Revision ID: xxxx
Revises: [previous]
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'xxxx'
down_revision = '[previous]'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Trade threads
    op.create_table(
        'trade_threads',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trade_proposal_id', sa.Integer(), sa.ForeignKey('trade_proposals.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('archived_at', sa.DateTime()),
        sa.Column('last_message_at', sa.DateTime()),
        sa.Column('message_count', sa.Integer(), default=0),
    )
    op.create_index('idx_trade_threads_proposal', 'trade_threads', ['trade_proposal_id'])

    # Trade thread messages
    op.create_table(
        'trade_thread_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('thread_id', sa.Integer(), sa.ForeignKey('trade_threads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text()),
        sa.Column('card_id', sa.Integer(), sa.ForeignKey('cards.id')),
        sa.Column('has_attachments', sa.Boolean(), default=False),
        sa.Column('reactions', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime()),
        sa.Column('reported_at', sa.DateTime()),
    )
    op.create_index('idx_trade_thread_messages_thread', 'trade_thread_messages', ['thread_id', 'created_at'])

    # Trade thread attachments
    op.create_table(
        'trade_thread_attachments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('message_id', sa.Integer(), sa.ForeignKey('trade_thread_messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_url', sa.String(500), nullable=False),
        sa.Column('file_type', sa.String(50)),
        sa.Column('file_size', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('purge_after', sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table('trade_thread_attachments')
    op.drop_index('idx_trade_thread_messages_thread')
    op.drop_table('trade_thread_messages')
    op.drop_index('idx_trade_threads_proposal')
    op.drop_table('trade_threads')
```

**Step 3: Run migration**

Run: `docker compose exec backend alembic upgrade head`

**Step 4: Commit**

```bash
git add backend/alembic/versions/*trade_thread*
git commit -m "db: add trade thread messaging tables"
```

---

### Task 1.3: Create Social Features Tables Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_add_social_features_tables.py`

**Step 1: Generate migration file**

Run: `docker compose exec backend alembic revision -m "add social features tables"`

**Step 2: Write migration**

```python
"""add social features tables

Revision ID: xxxx
Revises: [previous]
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = 'xxxx'
down_revision = '[previous]'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # User favorites
    op.create_table(
        'user_favorites',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('favorited_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('notify_on_listings', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'favorited_user_id', name='uq_user_favorite'),
    )
    op.create_index('idx_user_favorites_user', 'user_favorites', ['user_id'])

    # User notes (private)
    op.create_table(
        'user_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('user_id', 'target_user_id', name='uq_user_note'),
    )

    # User format specialties
    op.create_table(
        'user_format_specialties',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('format', sa.String(50), nullable=False),
        sa.UniqueConstraint('user_id', 'format', name='uq_user_format'),
    )
    op.create_index('idx_user_format_specialties_user', 'user_format_specialties', ['user_id'])

    # Profile views
    op.create_table(
        'profile_views',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('viewer_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('viewed_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_profile_views_viewed', 'profile_views', ['viewed_user_id', 'created_at'])

    # Notification preferences
    op.create_table(
        'notification_preferences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('preferences', JSONB, server_default='{}'),
        sa.Column('quiet_hours_enabled', sa.Boolean(), default=False),
        sa.Column('quiet_hours_start', sa.Time()),
        sa.Column('quiet_hours_end', sa.Time()),
        sa.Column('timezone', sa.String(50), default='UTC'),
    )


def downgrade() -> None:
    op.drop_table('notification_preferences')
    op.drop_index('idx_profile_views_viewed')
    op.drop_table('profile_views')
    op.drop_index('idx_user_format_specialties_user')
    op.drop_table('user_format_specialties')
    op.drop_table('user_notes')
    op.drop_index('idx_user_favorites_user')
    op.drop_table('user_favorites')
```

**Step 3: Run migration**

Run: `docker compose exec backend alembic upgrade head`

**Step 4: Commit**

```bash
git add backend/alembic/versions/*social_features*
git commit -m "db: add favorites, notes, formats, profile views tables"
```

---

### Task 1.4: Create Moderation Tables Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_add_moderation_tables.py`

**Step 1: Generate migration file**

Run: `docker compose exec backend alembic revision -m "add moderation tables"`

**Step 2: Write migration**

```python
"""add moderation tables

Revision ID: xxxx
Revises: [previous]
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = 'xxxx'
down_revision = '[previous]'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Moderation actions
    op.create_table(
        'moderation_actions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('moderator_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('target_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('reason', sa.Text()),
        sa.Column('duration_days', sa.Integer()),
        sa.Column('expires_at', sa.DateTime()),
        sa.Column('related_report_id', sa.Integer()),
        sa.Column('related_dispute_id', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_moderation_actions_target', 'moderation_actions', ['target_user_id', 'created_at'])

    # Moderation notes (internal)
    op.create_table(
        'moderation_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('moderator_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('target_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_moderation_notes_target', 'moderation_notes', ['target_user_id'])

    # Appeals
    op.create_table(
        'appeals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('moderation_action_id', sa.Integer(), sa.ForeignKey('moderation_actions.id'), nullable=False),
        sa.Column('appeal_text', sa.Text(), nullable=False),
        sa.Column('evidence_urls', ARRAY(sa.Text())),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('resolution_notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime()),
    )

    # Trade disputes
    op.create_table(
        'trade_disputes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trade_proposal_id', sa.Integer(), sa.ForeignKey('trade_proposals.id')),
        sa.Column('filed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('dispute_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('status', sa.String(20), default='open'),
        sa.Column('assigned_moderator_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('resolution', sa.String(50)),
        sa.Column('resolution_notes', sa.Text()),
        sa.Column('evidence_snapshot', JSONB),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime()),
    )
    op.create_index('idx_trade_disputes_status', 'trade_disputes', ['status', 'created_at'])


def downgrade() -> None:
    op.drop_index('idx_trade_disputes_status')
    op.drop_table('trade_disputes')
    op.drop_table('appeals')
    op.drop_index('idx_moderation_notes_target')
    op.drop_table('moderation_notes')
    op.drop_index('idx_moderation_actions_target')
    op.drop_table('moderation_actions')
```

**Step 3: Run migration**

Run: `docker compose exec backend alembic upgrade head`

**Step 4: Commit**

```bash
git add backend/alembic/versions/*moderation*
git commit -m "db: add moderation actions, notes, appeals, disputes tables"
```

---

### Task 1.5: Extend Users Table Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_extend_users_for_profiles.py`

**Step 1: Generate migration file**

Run: `docker compose exec backend alembic revision -m "extend users for profiles"`

**Step 2: Write migration**

```python
"""extend users for profiles

Revision ID: xxxx
Revises: [previous]
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa

revision = 'xxxx'
down_revision = '[previous]'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Profile card fields
    op.add_column('users', sa.Column('tagline', sa.String(50)))
    op.add_column('users', sa.Column('signature_card_id', sa.Integer(), sa.ForeignKey('cards.id')))
    op.add_column('users', sa.Column('card_type', sa.String(20)))
    op.add_column('users', sa.Column('card_type_changed_at', sa.DateTime()))

    # Location fields
    op.add_column('users', sa.Column('city', sa.String(100)))
    op.add_column('users', sa.Column('country', sa.String(100)))
    op.add_column('users', sa.Column('shipping_preference', sa.String(20)))

    # Frame and discovery
    op.add_column('users', sa.Column('active_frame_tier', sa.String(20), server_default='bronze'))
    op.add_column('users', sa.Column('discovery_score', sa.Integer(), server_default='100'))

    # Privacy settings
    op.add_column('users', sa.Column('show_in_directory', sa.Boolean(), server_default='true'))
    op.add_column('users', sa.Column('show_in_search', sa.Boolean(), server_default='true'))
    op.add_column('users', sa.Column('show_online_status', sa.Boolean(), server_default='true'))
    op.add_column('users', sa.Column('show_portfolio_tier', sa.Boolean(), server_default='true'))

    # Onboarding and activity
    op.add_column('users', sa.Column('onboarding_completed_at', sa.DateTime()))
    op.add_column('users', sa.Column('last_active_at', sa.DateTime()))

    # Indexes for directory
    op.create_index(
        'idx_users_discovery_directory',
        'users',
        ['discovery_score'],
        postgresql_where=sa.text('show_in_directory = true')
    )
    op.create_index('idx_users_location', 'users', ['country', 'city'])

    # Enable trigram extension for fuzzy search (may already exist)
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    op.create_index(
        'idx_users_search_trgm',
        'users',
        ['username', 'display_name'],
        postgresql_using='gin',
        postgresql_ops={'username': 'gin_trgm_ops', 'display_name': 'gin_trgm_ops'}
    )


def downgrade() -> None:
    op.drop_index('idx_users_search_trgm')
    op.drop_index('idx_users_location')
    op.drop_index('idx_users_discovery_directory')

    op.drop_column('users', 'last_active_at')
    op.drop_column('users', 'onboarding_completed_at')
    op.drop_column('users', 'show_portfolio_tier')
    op.drop_column('users', 'show_online_status')
    op.drop_column('users', 'show_in_search')
    op.drop_column('users', 'show_in_directory')
    op.drop_column('users', 'discovery_score')
    op.drop_column('users', 'active_frame_tier')
    op.drop_column('users', 'shipping_preference')
    op.drop_column('users', 'country')
    op.drop_column('users', 'city')
    op.drop_column('users', 'card_type_changed_at')
    op.drop_column('users', 'card_type')
    op.drop_column('users', 'signature_card_id')
    op.drop_column('users', 'tagline')
```

**Step 3: Run migration**

Run: `docker compose exec backend alembic upgrade head`

**Step 4: Verify columns added**

Run: `docker compose exec db psql -U dualcaster_user -d dualcaster_deals -c "\d users" | grep -E "(tagline|frame_tier|discovery)"`
Expected: New columns listed

**Step 5: Commit**

```bash
git add backend/alembic/versions/*extend_users*
git commit -m "db: extend users table with profile, location, privacy fields"
```

---

### Task 1.6: Extend Messages and Reports Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_extend_messages_reports.py`

**Step 1: Generate migration file**

Run: `docker compose exec backend alembic revision -m "extend messages and reports"`

**Step 2: Write migration**

```python
"""extend messages and reports

Revision ID: xxxx
Revises: [previous]
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'xxxx'
down_revision = '[previous]'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend messages for trade threads
    op.add_column('messages', sa.Column('trade_thread_id', sa.Integer(), sa.ForeignKey('trade_threads.id')))
    op.add_column('messages', sa.Column('has_attachments', sa.Boolean(), server_default='false'))
    op.add_column('messages', sa.Column('reactions', JSONB, server_default='{}'))
    op.add_column('messages', sa.Column('deleted_at', sa.DateTime()))
    op.add_column('messages', sa.Column('reported_at', sa.DateTime()))

    # Extend user_reports for moderation
    op.add_column('user_reports', sa.Column('report_type', sa.String(50)))
    op.add_column('user_reports', sa.Column('evidence_snapshot', JSONB))
    op.add_column('user_reports', sa.Column('resolution', sa.String(50)))
    op.add_column('user_reports', sa.Column('resolved_by', sa.Integer(), sa.ForeignKey('users.id')))
    op.add_column('user_reports', sa.Column('resolved_at', sa.DateTime()))
    op.add_column('user_reports', sa.Column('resolution_notes', sa.Text()))

    op.create_index('idx_user_reports_status', 'user_reports', ['resolution', 'created_at'])


def downgrade() -> None:
    op.drop_index('idx_user_reports_status')

    op.drop_column('user_reports', 'resolution_notes')
    op.drop_column('user_reports', 'resolved_at')
    op.drop_column('user_reports', 'resolved_by')
    op.drop_column('user_reports', 'resolution')
    op.drop_column('user_reports', 'evidence_snapshot')
    op.drop_column('user_reports', 'report_type')

    op.drop_column('messages', 'reported_at')
    op.drop_column('messages', 'deleted_at')
    op.drop_column('messages', 'reactions')
    op.drop_column('messages', 'has_attachments')
    op.drop_column('messages', 'trade_thread_id')
```

**Step 3: Run migration**

Run: `docker compose exec backend alembic upgrade head`

**Step 4: Commit**

```bash
git add backend/alembic/versions/*extend_messages*
git commit -m "db: extend messages and user_reports tables"
```

---

## Phase 2: Backend Models

### Task 2.1: Create Achievement Models

**Files:**
- Create: `backend/app/models/achievement.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Write achievement models**

```python
# backend/app/models/achievement.py
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class AchievementDefinition(Base):
    __tablename__ = "achievement_definitions"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(50), nullable=False, index=True)  # trade, reputation, portfolio, community, special
    icon = Column(String(100))
    threshold = Column(JSONB)  # {"trades": 10} or {"reviews": 5, "avg_rating": 4.0}
    discovery_points = Column(Integer, default=0)
    frame_tier_unlock = Column(String(20))  # bronze, silver, gold, platinum, legendary
    rarity_percent = Column(Numeric(5, 2))
    is_hidden = Column(Boolean, default=False)
    is_seasonal = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user_achievements = relationship("UserAchievement", back_populates="achievement")


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    achievement_id = Column(Integer, ForeignKey("achievement_definitions.id"), nullable=False)
    unlocked_at = Column(DateTime, server_default=func.now())
    progress = Column(JSONB)  # {"current": 7, "target": 10}

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    # Relationships
    user = relationship("User", back_populates="achievements")
    achievement = relationship("AchievementDefinition", back_populates="user_achievements")


class UserFrame(Base):
    __tablename__ = "user_frames"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    frame_tier = Column(String(20), nullable=False)  # bronze, silver, gold, platinum, legendary
    unlocked_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("user_id", "frame_tier", name="uq_user_frame"),
    )

    # Relationships
    user = relationship("User", back_populates="frames")
```

**Step 2: Update models __init__.py**

Add to `backend/app/models/__init__.py`:

```python
from app.models.achievement import AchievementDefinition, UserAchievement, UserFrame
```

**Step 3: Verify import works**

Run: `docker compose exec backend python -c "from app.models.achievement import AchievementDefinition, UserAchievement, UserFrame; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add backend/app/models/achievement.py backend/app/models/__init__.py
git commit -m "feat: add achievement SQLAlchemy models"
```

---

### Task 2.2: Create Trade Thread Models

**Files:**
- Create: `backend/app/models/trade_thread.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Write trade thread models**

```python
# backend/app/models/trade_thread.py
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class TradeThread(Base):
    __tablename__ = "trade_threads"

    id = Column(Integer, primary_key=True, index=True)
    trade_proposal_id = Column(Integer, ForeignKey("trade_proposals.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at = Column(DateTime, server_default=func.now())
    archived_at = Column(DateTime)
    last_message_at = Column(DateTime)
    message_count = Column(Integer, default=0)

    # Relationships
    trade_proposal = relationship("TradeProposal", back_populates="thread")
    messages = relationship("TradeThreadMessage", back_populates="thread", order_by="TradeThreadMessage.created_at")


class TradeThreadMessage(Base):
    __tablename__ = "trade_thread_messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("trade_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text)
    card_id = Column(Integer, ForeignKey("cards.id"))  # For card embeds
    has_attachments = Column(Boolean, default=False)
    reactions = Column(JSONB, server_default="{}")
    created_at = Column(DateTime, server_default=func.now())
    deleted_at = Column(DateTime)
    reported_at = Column(DateTime)

    # Relationships
    thread = relationship("TradeThread", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
    card = relationship("Card")
    attachments = relationship("TradeThreadAttachment", back_populates="message")


class TradeThreadAttachment(Base):
    __tablename__ = "trade_thread_attachments"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("trade_thread_messages.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    purge_after = Column(DateTime)

    # Relationships
    message = relationship("TradeThreadMessage", back_populates="attachments")
```

**Step 2: Update models __init__.py**

Add to `backend/app/models/__init__.py`:

```python
from app.models.trade_thread import TradeThread, TradeThreadMessage, TradeThreadAttachment
```

**Step 3: Update TradeProposal model to add thread relationship**

Add to `backend/app/models/trade.py` in the `TradeProposal` class:

```python
# Add to relationships section
thread = relationship("TradeThread", back_populates="trade_proposal", uselist=False)
```

**Step 4: Verify import works**

Run: `docker compose exec backend python -c "from app.models.trade_thread import TradeThread; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add backend/app/models/trade_thread.py backend/app/models/__init__.py backend/app/models/trade.py
git commit -m "feat: add trade thread SQLAlchemy models"
```

---

### Task 2.3: Create Social Feature Models

**Files:**
- Create: `backend/app/models/social.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Write social models**

```python
# backend/app/models/social.py
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Time, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class UserFavorite(Base):
    __tablename__ = "user_favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    favorited_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notify_on_listings = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "favorited_user_id", name="uq_user_favorite"),
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="favorites")
    favorited_user = relationship("User", foreign_keys=[favorited_user_id])


class UserNote(Base):
    __tablename__ = "user_notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "target_user_id", name="uq_user_note"),
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="notes")
    target_user = relationship("User", foreign_keys=[target_user_id])


class UserFormatSpecialty(Base):
    __tablename__ = "user_format_specialties"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    format = Column(String(50), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "format", name="uq_user_format"),
    )

    # Relationships
    user = relationship("User", back_populates="format_specialties")


class ProfileView(Base):
    __tablename__ = "profile_views"

    id = Column(Integer, primary_key=True, index=True)
    viewer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    viewed_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    viewer = relationship("User", foreign_keys=[viewer_id])
    viewed_user = relationship("User", foreign_keys=[viewed_user_id])


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    preferences = Column(JSONB, server_default="{}")
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(Time)
    quiet_hours_end = Column(Time)
    timezone = Column(String(50), default="UTC")

    # Relationships
    user = relationship("User", back_populates="notification_preferences")
```

**Step 2: Update models __init__.py**

Add to `backend/app/models/__init__.py`:

```python
from app.models.social import UserFavorite, UserNote, UserFormatSpecialty, ProfileView, NotificationPreference
```

**Step 3: Verify import works**

Run: `docker compose exec backend python -c "from app.models.social import UserFavorite, UserNote; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add backend/app/models/social.py backend/app/models/__init__.py
git commit -m "feat: add social feature SQLAlchemy models"
```

---

### Task 2.4: Create Moderation Models

**Files:**
- Create: `backend/app/models/moderation_enhanced.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Write moderation models**

```python
# backend/app/models/moderation_enhanced.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class ModerationAction(Base):
    __tablename__ = "moderation_actions"

    id = Column(Integer, primary_key=True, index=True)
    moderator_id = Column(Integer, ForeignKey("users.id"))
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # warn, restrict, suspend, ban, dismiss
    reason = Column(Text)
    duration_days = Column(Integer)
    expires_at = Column(DateTime)
    related_report_id = Column(Integer)
    related_dispute_id = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    moderator = relationship("User", foreign_keys=[moderator_id])
    target_user = relationship("User", foreign_keys=[target_user_id])
    appeal = relationship("Appeal", back_populates="moderation_action", uselist=False)


class ModerationNote(Base):
    __tablename__ = "moderation_notes"

    id = Column(Integer, primary_key=True, index=True)
    moderator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    moderator = relationship("User", foreign_keys=[moderator_id])
    target_user = relationship("User", foreign_keys=[target_user_id])


class Appeal(Base):
    __tablename__ = "appeals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    moderation_action_id = Column(Integer, ForeignKey("moderation_actions.id"), nullable=False)
    appeal_text = Column(Text, nullable=False)
    evidence_urls = Column(ARRAY(Text))
    status = Column(String(20), default="pending")  # pending, upheld, reduced, overturned
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    resolution_notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    moderation_action = relationship("ModerationAction", back_populates="appeal")


class TradeDispute(Base):
    __tablename__ = "trade_disputes"

    id = Column(Integer, primary_key=True, index=True)
    trade_proposal_id = Column(Integer, ForeignKey("trade_proposals.id"))
    filed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    dispute_type = Column(String(50), nullable=False)  # item_not_as_described, didnt_ship, other
    description = Column(Text)
    status = Column(String(20), default="open", index=True)  # open, evidence_requested, resolved
    assigned_moderator_id = Column(Integer, ForeignKey("users.id"))
    resolution = Column(String(50))  # buyer_wins, seller_wins, mutual_cancel, inconclusive
    resolution_notes = Column(Text)
    evidence_snapshot = Column(JSONB)
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime)

    # Relationships
    trade_proposal = relationship("TradeProposal")
    filer = relationship("User", foreign_keys=[filed_by])
    assigned_moderator = relationship("User", foreign_keys=[assigned_moderator_id])
```

**Step 2: Update models __init__.py**

Add to `backend/app/models/__init__.py`:

```python
from app.models.moderation_enhanced import ModerationAction, ModerationNote, Appeal, TradeDispute
```

**Step 3: Verify import works**

Run: `docker compose exec backend python -c "from app.models.moderation_enhanced import ModerationAction, TradeDispute; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add backend/app/models/moderation_enhanced.py backend/app/models/__init__.py
git commit -m "feat: add enhanced moderation SQLAlchemy models"
```

---

### Task 2.5: Update User Model with New Fields

**Files:**
- Modify: `backend/app/models/user.py`

**Step 1: Add new columns to User model**

Add to the `User` class in `backend/app/models/user.py`:

```python
# Profile card fields
tagline = Column(String(50))
signature_card_id = Column(Integer, ForeignKey("cards.id"))
card_type = Column(String(20))  # collector, trader, brewer, investor
card_type_changed_at = Column(DateTime)

# Location fields
city = Column(String(100))
country = Column(String(100))
shipping_preference = Column(String(20))  # local, domestic, international

# Frame and discovery
active_frame_tier = Column(String(20), default="bronze")
discovery_score = Column(Integer, default=100)

# Privacy settings
show_in_directory = Column(Boolean, default=True)
show_in_search = Column(Boolean, default=True)
show_online_status = Column(Boolean, default=True)
show_portfolio_tier = Column(Boolean, default=True)

# Onboarding and activity
onboarding_completed_at = Column(DateTime)
last_active_at = Column(DateTime)

# Relationships (add to existing relationships section)
signature_card = relationship("Card", foreign_keys=[signature_card_id])
achievements = relationship("UserAchievement", back_populates="user")
frames = relationship("UserFrame", back_populates="user")
favorites = relationship("UserFavorite", foreign_keys="UserFavorite.user_id", back_populates="user")
notes = relationship("UserNote", foreign_keys="UserNote.user_id", back_populates="user")
format_specialties = relationship("UserFormatSpecialty", back_populates="user")
notification_preferences = relationship("NotificationPreference", back_populates="user", uselist=False)
```

**Step 2: Verify model loads**

Run: `docker compose exec backend python -c "from app.models.user import User; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/models/user.py
git commit -m "feat: add profile fields to User model"
```

---

## Phase 3: Backend Schemas

### Task 3.1: Create Achievement Schemas

**Files:**
- Create: `backend/app/schemas/achievement.py`

**Step 1: Write achievement schemas**

```python
# backend/app/schemas/achievement.py
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class AchievementDefinitionBase(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    category: str
    icon: Optional[str] = None
    threshold: Optional[dict[str, Any]] = None
    discovery_points: int = 0
    frame_tier_unlock: Optional[str] = None
    is_hidden: bool = False


class AchievementDefinitionResponse(AchievementDefinitionBase):
    id: int
    rarity_percent: Optional[float] = None
    is_seasonal: bool = False

    class Config:
        from_attributes = True


class UserAchievementResponse(BaseModel):
    id: int
    achievement_id: int
    unlocked_at: datetime
    progress: Optional[dict[str, Any]] = None
    achievement: AchievementDefinitionResponse

    class Config:
        from_attributes = True


class AchievementProgressResponse(BaseModel):
    """Achievement definition with user's progress"""
    achievement: AchievementDefinitionResponse
    unlocked: bool
    unlocked_at: Optional[datetime] = None
    progress: Optional[dict[str, Any]] = None  # {"current": 7, "target": 10}


class AchievementsListResponse(BaseModel):
    achievements: list[AchievementProgressResponse]
    total_unlocked: int
    total_discovery_points: int


class FrameTier(BaseModel):
    tier: str  # bronze, silver, gold, platinum, legendary
    unlocked: bool
    unlocked_at: Optional[datetime] = None
    is_active: bool = False


class FramesResponse(BaseModel):
    frames: list[FrameTier]
    active_frame: str


class SetActiveFrameRequest(BaseModel):
    frame_tier: str
```

**Step 2: Verify import works**

Run: `docker compose exec backend python -c "from app.schemas.achievement import AchievementDefinitionResponse; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/schemas/achievement.py
git commit -m "feat: add achievement Pydantic schemas"
```

---

### Task 3.2: Create Trade Thread Schemas

**Files:**
- Create: `backend/app/schemas/trade_thread.py`

**Step 1: Write trade thread schemas**

```python
# backend/app/schemas/trade_thread.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TradeThreadAttachmentResponse(BaseModel):
    id: int
    file_url: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CardEmbedResponse(BaseModel):
    id: int
    name: str
    set_code: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[float] = None


class TradeThreadMessageResponse(BaseModel):
    id: int
    thread_id: int
    sender_id: int
    sender_username: str
    sender_display_name: Optional[str] = None
    sender_avatar_url: Optional[str] = None
    content: Optional[str] = None
    card: Optional[CardEmbedResponse] = None
    has_attachments: bool = False
    attachments: list[TradeThreadAttachmentResponse] = []
    reactions: dict[str, list[int]] = {}  # {"👍": [user_id, user_id]}
    created_at: datetime
    deleted_at: Optional[datetime] = None
    is_system_message: bool = False

    class Config:
        from_attributes = True


class TradeThreadResponse(BaseModel):
    id: int
    trade_proposal_id: int
    created_at: datetime
    archived_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    message_count: int = 0
    messages: list[TradeThreadMessageResponse] = []

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    content: Optional[str] = None
    card_id: Optional[int] = None


class AddReactionRequest(BaseModel):
    emoji: str


class TradeThreadSummary(BaseModel):
    """Compact trade info for chat header"""
    id: int
    status: str
    proposer_username: str
    recipient_username: str
    offer_card_count: int
    offer_value: float
    request_card_count: int
    request_value: float
    expires_at: Optional[datetime] = None
```

**Step 2: Commit**

```bash
git add backend/app/schemas/trade_thread.py
git commit -m "feat: add trade thread Pydantic schemas"
```

---

### Task 3.3: Create Directory Schemas

**Files:**
- Create: `backend/app/schemas/directory.py`

**Step 1: Write directory schemas**

```python
# backend/app/schemas/directory.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ProfileCardResponse(BaseModel):
    """The trading card-style profile"""
    id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    tagline: Optional[str] = None
    card_type: Optional[str] = None  # collector, trader, brewer, investor

    # Stats
    trade_count: int = 0
    reputation_score: Optional[float] = None
    reputation_count: int = 0
    success_rate: Optional[float] = None
    response_time_hours: Optional[float] = None

    # Frame and tier
    frame_tier: str = "bronze"

    # Location
    city: Optional[str] = None
    country: Optional[str] = None
    shipping_preference: Optional[str] = None

    # Status
    is_online: bool = False
    last_active_at: Optional[datetime] = None
    open_to_trades: bool = False

    # Verification
    email_verified: bool = False
    discord_linked: bool = False
    id_verified: bool = False

    # Badges (top achievements)
    badges: list[dict] = []  # [{"key": "trade_master", "icon": "...", "name": "..."}]

    # Formats
    formats: list[str] = []

    # Signature card
    signature_card: Optional[dict] = None  # {"id": 1, "name": "...", "image_url": "..."}

    # Member info
    member_since: datetime

    class Config:
        from_attributes = True


class ProfileCardBackResponse(BaseModel):
    """Extended info for card flip"""
    id: int

    # Extended stats
    total_trades: int = 0
    completed_trades: int = 0
    portfolio_tier: Optional[str] = None  # starter, growing, serious, dragon, legendary

    # Endorsements
    endorsement_counts: dict[str, int] = {}  # {"trustworthy": 5, "fair_trader": 3}

    # Recent activity
    recent_trades: list[dict] = []  # [{"date": ..., "with_user": ..., "value": ...}]
    recent_reviews: list[dict] = []

    # Mutual connections
    mutual_connections: list[dict] = []  # [{"id": 1, "username": "..."}]

    # All achievements
    achievements: list[dict] = []


class QuickTradePreviewResponse(BaseModel):
    """Hover preview for trade potential"""
    user_id: int
    cards_they_have_you_want: int = 0
    cards_they_have_you_want_value: float = 0.0
    cards_you_have_they_want: int = 0
    cards_you_have_they_want_value: float = 0.0
    is_mutual_match: bool = False


class DirectoryFilters(BaseModel):
    q: Optional[str] = None  # Search query
    sort: str = "discovery_score"  # discovery_score, reputation, trades, newest, best_match
    reputation_tier: Optional[list[str]] = None  # elite, trusted, established, new
    frame_tier: Optional[list[str]] = None
    card_type: Optional[list[str]] = None
    format: Optional[list[str]] = None
    shipping: Optional[list[str]] = None
    country: Optional[str] = None
    online_only: bool = False
    has_my_wants: bool = False
    wants_my_cards: bool = False
    user_type: Optional[str] = None  # all, traders, stores
    verified_only: bool = False


class DirectoryResponse(BaseModel):
    users: list[ProfileCardResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class SuggestedUserResponse(BaseModel):
    user: ProfileCardResponse
    reason: str  # "mutual_connection", "same_formats", "has_your_wants"
    mutual_connection_count: int = 0
    matching_formats: list[str] = []
    matching_cards: int = 0
```

**Step 2: Commit**

```bash
git add backend/app/schemas/directory.py
git commit -m "feat: add directory Pydantic schemas"
```

---

### Task 3.4: Create Favorites and Notes Schemas

**Files:**
- Create: `backend/app/schemas/favorites.py`

**Step 1: Write favorites schemas**

```python
# backend/app/schemas/favorites.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class FavoriteUserResponse(BaseModel):
    id: int
    favorited_user_id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    frame_tier: str = "bronze"
    notify_on_listings: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class FavoritesListResponse(BaseModel):
    favorites: list[FavoriteUserResponse]
    total: int


class AddFavoriteRequest(BaseModel):
    notify_on_listings: bool = False


class UserNoteResponse(BaseModel):
    id: int
    target_user_id: int
    username: str
    display_name: Optional[str] = None
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotesListResponse(BaseModel):
    notes: list[UserNoteResponse]
    total: int


class CreateNoteRequest(BaseModel):
    content: str


class UpdateNoteRequest(BaseModel):
    content: str
```

**Step 2: Commit**

```bash
git add backend/app/schemas/favorites.py
git commit -m "feat: add favorites and notes Pydantic schemas"
```

---

### Task 3.5: Create Moderation Schemas

**Files:**
- Create: `backend/app/schemas/moderation_enhanced.py`

**Step 1: Write moderation schemas**

```python
# backend/app/schemas/moderation_enhanced.py
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class ModerationQueueItem(BaseModel):
    id: int
    target_user_id: int
    target_username: str
    flag_level: str  # low, medium, high, critical
    flag_type: str  # user_report, auto_flag, appeal, dispute
    flag_reason: str
    report_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ModerationQueueResponse(BaseModel):
    items: list[ModerationQueueItem]
    total: int
    pending_count: int
    high_priority_count: int


class ModerationCaseDetail(BaseModel):
    id: int
    target_user_id: int
    target_user: dict  # Full profile info

    # Reports
    reports: list[dict] = []

    # Auto-flags
    auto_flags: list[dict] = []

    # History
    previous_actions: list[dict] = []
    mod_notes: list[dict] = []

    # Trade history
    trade_stats: dict = {}
    recent_trades: list[dict] = []

    # Messages (if reported)
    reported_messages: list[dict] = []


class TakeActionRequest(BaseModel):
    action: str  # dismiss, warn, restrict, suspend, ban, escalate
    reason: str
    duration_days: Optional[int] = None  # For restrict/suspend
    related_report_id: Optional[int] = None


class ModerationActionResponse(BaseModel):
    id: int
    action_type: str
    reason: str
    duration_days: Optional[int] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AppealResponse(BaseModel):
    id: int
    user_id: int
    username: str
    moderation_action: ModerationActionResponse
    appeal_text: str
    evidence_urls: list[str] = []
    status: str
    resolution_notes: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ResolveAppealRequest(BaseModel):
    resolution: str  # upheld, reduced, overturned
    notes: str


class TradeDisputeResponse(BaseModel):
    id: int
    trade_proposal_id: int
    filed_by: int
    filer_username: str
    dispute_type: str
    description: Optional[str] = None
    status: str
    assigned_moderator_id: Optional[int] = None
    resolution: Optional[str] = None
    resolution_notes: Optional[str] = None
    evidence_snapshot: Optional[dict] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FileDisputeRequest(BaseModel):
    trade_id: int
    dispute_type: str  # item_not_as_described, didnt_ship, other
    description: str


class ResolveDisputeRequest(BaseModel):
    resolution: str  # buyer_wins, seller_wins, mutual_cancel, inconclusive
    notes: str


class AddModNoteRequest(BaseModel):
    content: str
```

**Step 2: Commit**

```bash
git add backend/app/schemas/moderation_enhanced.py
git commit -m "feat: add enhanced moderation Pydantic schemas"
```

---

### Task 3.6: Create Notification Schemas

**Files:**
- Create: `backend/app/schemas/notification_enhanced.py`

**Step 1: Write notification schemas**

```python
# backend/app/schemas/notification_enhanced.py
from datetime import datetime, time
from typing import Optional, Any
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: int
    type: str  # trade_proposal, message, connection, achievement, etc.
    category: str  # trades, messages, social, discovery, achievements, system
    title: str
    body: str
    icon: Optional[str] = None
    action_url: Optional[str] = None
    metadata: dict[str, Any] = {}
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationsListResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int
    unread_count: int
    has_more: bool


class UnreadCountsResponse(BaseModel):
    total: int
    trades: int
    messages: int
    social: int
    discovery: int
    achievements: int
    system: int


class NotificationPreferencesResponse(BaseModel):
    trade_activity: str = "on"  # on, daily_digest, off
    messages: str = "on"
    social: str = "on"
    discovery: str = "daily_digest"
    price_alerts: str = "daily_digest"
    achievements: str = "on"
    listing_reminders: str = "weekly"

    quiet_hours_enabled: bool = False
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None
    timezone: str = "UTC"

    class Config:
        from_attributes = True


class UpdateNotificationPreferencesRequest(BaseModel):
    trade_activity: Optional[str] = None
    messages: Optional[str] = None
    social: Optional[str] = None
    discovery: Optional[str] = None
    price_alerts: Optional[str] = None
    achievements: Optional[str] = None
    listing_reminders: Optional[str] = None

    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None
    timezone: Optional[str] = None


class MarkReadRequest(BaseModel):
    notification_ids: list[int]


class MarkCategoryReadRequest(BaseModel):
    category: str
```

**Step 2: Commit**

```bash
git add backend/app/schemas/notification_enhanced.py
git commit -m "feat: add notification Pydantic schemas"
```

---

## Phase 4: Backend API Routes

### Task 4.1: Create Achievements API Route

**Files:**
- Create: `backend/app/api/routes/achievements.py`
- Modify: `backend/app/api/api.py`

**Step 1: Write the failing test**

Create `backend/tests/test_achievements.py`:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_achievements_unauthorized(client: AsyncClient):
    """Test that unauthenticated users can't access achievements"""
    response = await client.get("/api/achievements")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_achievements_authenticated(client: AsyncClient, auth_headers: dict):
    """Test that authenticated users can get achievements list"""
    response = await client.get("/api/achievements", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "achievements" in data
    assert "total_unlocked" in data
    assert "total_discovery_points" in data
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/test_achievements.py -v`
Expected: FAIL (route doesn't exist)

**Step 3: Write the achievements route**

```python
# backend/app/api/routes/achievements.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.api.deps import get_current_user, get_optional_current_user
from app.models.user import User
from app.models.achievement import AchievementDefinition, UserAchievement, UserFrame
from app.schemas.achievement import (
    AchievementsListResponse,
    AchievementProgressResponse,
    AchievementDefinitionResponse,
    FramesResponse,
    FrameTier,
    SetActiveFrameRequest,
)

router = APIRouter()

FRAME_TIERS = ["bronze", "silver", "gold", "platinum", "legendary"]


@router.get("", response_model=AchievementsListResponse)
async def get_achievements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all achievement definitions with current user's progress"""
    # Get all non-hidden achievements
    result = await db.execute(
        select(AchievementDefinition)
        .where(AchievementDefinition.is_hidden == False)
        .order_by(AchievementDefinition.category, AchievementDefinition.discovery_points)
    )
    definitions = result.scalars().all()

    # Get user's achievements
    user_achievements_result = await db.execute(
        select(UserAchievement)
        .where(UserAchievement.user_id == current_user.id)
    )
    user_achievements = {ua.achievement_id: ua for ua in user_achievements_result.scalars().all()}

    achievements = []
    total_unlocked = 0
    total_points = 0

    for defn in definitions:
        user_ach = user_achievements.get(defn.id)
        unlocked = user_ach is not None

        if unlocked:
            total_unlocked += 1
            total_points += defn.discovery_points or 0

        achievements.append(AchievementProgressResponse(
            achievement=AchievementDefinitionResponse.model_validate(defn),
            unlocked=unlocked,
            unlocked_at=user_ach.unlocked_at if user_ach else None,
            progress=user_ach.progress if user_ach else None,
        ))

    return AchievementsListResponse(
        achievements=achievements,
        total_unlocked=total_unlocked,
        total_discovery_points=total_points,
    )


@router.get("/users/{user_id}", response_model=AchievementsListResponse)
async def get_user_achievements(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_current_user),
):
    """Get achievements for a specific user (public unlocked only)"""
    # Get user's unlocked achievements
    result = await db.execute(
        select(UserAchievement)
        .options(selectinload(UserAchievement.achievement))
        .where(UserAchievement.user_id == user_id)
    )
    user_achievements = result.scalars().all()

    achievements = []
    total_points = 0

    for ua in user_achievements:
        if ua.achievement.is_hidden:
            continue
        total_points += ua.achievement.discovery_points or 0
        achievements.append(AchievementProgressResponse(
            achievement=AchievementDefinitionResponse.model_validate(ua.achievement),
            unlocked=True,
            unlocked_at=ua.unlocked_at,
            progress=None,  # Don't show progress to others
        ))

    return AchievementsListResponse(
        achievements=achievements,
        total_unlocked=len(achievements),
        total_discovery_points=total_points,
    )


@router.get("/frames", response_model=FramesResponse)
async def get_frames(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get available frames for current user"""
    # Get user's unlocked frames
    result = await db.execute(
        select(UserFrame).where(UserFrame.user_id == current_user.id)
    )
    user_frames = {uf.frame_tier: uf for uf in result.scalars().all()}

    # Bronze is always unlocked
    frames = []
    for tier in FRAME_TIERS:
        uf = user_frames.get(tier)
        frames.append(FrameTier(
            tier=tier,
            unlocked=tier == "bronze" or uf is not None,
            unlocked_at=uf.unlocked_at if uf else None,
            is_active=current_user.active_frame_tier == tier,
        ))

    return FramesResponse(
        frames=frames,
        active_frame=current_user.active_frame_tier or "bronze",
    )


@router.post("/frames/active")
async def set_active_frame(
    request: SetActiveFrameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set active frame tier"""
    if request.frame_tier not in FRAME_TIERS:
        raise HTTPException(status_code=400, detail="Invalid frame tier")

    # Check if frame is unlocked (bronze is always available)
    if request.frame_tier != "bronze":
        result = await db.execute(
            select(UserFrame).where(
                UserFrame.user_id == current_user.id,
                UserFrame.frame_tier == request.frame_tier,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Frame not unlocked")

    current_user.active_frame_tier = request.frame_tier
    await db.commit()

    return {"status": "ok", "active_frame": request.frame_tier}
```

**Step 4: Register route in api.py**

Add to `backend/app/api/api.py`:

```python
from app.api.routes import achievements

api_router.include_router(achievements.router, prefix="/achievements", tags=["achievements"])
```

**Step 5: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/test_achievements.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/api/routes/achievements.py backend/app/api/api.py backend/tests/test_achievements.py
git commit -m "feat: add achievements API endpoints"
```

---

### Task 4.2: Create Directory API Route

**Files:**
- Create: `backend/app/api/routes/directory.py`
- Modify: `backend/app/api/api.py`

**Step 1: Write the directory route**

```python
# backend/app/api/routes/directory.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, desc
from sqlalchemy.orm import selectinload
from typing import Optional

from app.db.session import get_db
from app.api.deps import get_current_user, get_optional_current_user
from app.models.user import User
from app.models.achievement import UserAchievement
from app.models.social import UserFavorite, UserFormatSpecialty
from app.models.reputation import UserReputation
from app.schemas.directory import (
    DirectoryResponse,
    ProfileCardResponse,
    QuickTradePreviewResponse,
    SuggestedUserResponse,
)

router = APIRouter()


def build_profile_card(user: User, reputation: Optional[UserReputation] = None) -> ProfileCardResponse:
    """Convert user model to profile card response"""
    return ProfileCardResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        tagline=user.tagline,
        card_type=user.card_type,
        trade_count=0,  # TODO: Calculate from trades
        reputation_score=reputation.average_rating if reputation else None,
        reputation_count=reputation.total_reviews if reputation else 0,
        success_rate=None,  # TODO: Calculate
        response_time_hours=None,  # TODO: Calculate
        frame_tier=user.active_frame_tier or "bronze",
        city=user.city if user.show_in_directory else None,
        country=user.country if user.show_in_directory else None,
        shipping_preference=user.shipping_preference,
        is_online=False,  # TODO: Implement presence
        last_active_at=user.last_active_at,
        open_to_trades=True,  # TODO: Check inventory
        email_verified=user.email_verified,
        discord_linked=user.discord_id is not None,
        id_verified=False,  # TODO: Implement
        badges=[],  # TODO: Get top achievements
        formats=[fs.format for fs in user.format_specialties] if user.format_specialties else [],
        signature_card=None,  # TODO: Get signature card
        member_since=user.created_at,
    )


@router.get("", response_model=DirectoryResponse)
async def get_directory(
    q: Optional[str] = None,
    sort: str = Query("discovery_score", enum=["discovery_score", "reputation", "trades", "newest", "best_match"]),
    reputation_tier: Optional[str] = None,
    frame_tier: Optional[str] = None,
    card_type: Optional[str] = None,
    format: Optional[str] = None,
    shipping: Optional[str] = None,
    country: Optional[str] = None,
    online_only: bool = False,
    verified_only: bool = False,
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Get paginated user directory with filters"""
    # Base query - only users who opted into directory
    query = select(User).where(
        User.show_in_directory == True,
        User.is_active == True,
    )

    # Search filter
    if q:
        search_filter = or_(
            User.username.ilike(f"%{q}%"),
            User.display_name.ilike(f"%{q}%"),
        )
        query = query.where(search_filter)

    # Frame tier filter
    if frame_tier:
        tiers = frame_tier.split(",")
        query = query.where(User.active_frame_tier.in_(tiers))

    # Card type filter
    if card_type:
        types = card_type.split(",")
        query = query.where(User.card_type.in_(types))

    # Country filter
    if country:
        query = query.where(User.country == country)

    # Shipping filter
    if shipping:
        prefs = shipping.split(",")
        query = query.where(User.shipping_preference.in_(prefs))

    # Format filter
    if format:
        formats = format.split(",")
        query = query.join(UserFormatSpecialty).where(UserFormatSpecialty.format.in_(formats))

    # Verified only
    if verified_only:
        query = query.where(User.email_verified == True)

    # Exclude current user
    if current_user:
        query = query.where(User.id != current_user.id)

    # Sorting
    if sort == "discovery_score":
        query = query.order_by(desc(User.discovery_score))
    elif sort == "newest":
        query = query.order_by(desc(User.created_at))
    else:
        query = query.order_by(desc(User.discovery_score))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    query = query.options(selectinload(User.format_specialties))

    result = await db.execute(query)
    users = result.scalars().all()

    # Get reputations
    user_ids = [u.id for u in users]
    if user_ids:
        rep_result = await db.execute(
            select(UserReputation).where(UserReputation.user_id.in_(user_ids))
        )
        reputations = {r.user_id: r for r in rep_result.scalars().all()}
    else:
        reputations = {}

    profile_cards = [
        build_profile_card(u, reputations.get(u.id))
        for u in users
    ]

    return DirectoryResponse(
        users=profile_cards,
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + limit) < total,
    )


@router.get("/search")
async def search_users(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Quick search for users by name"""
    query = select(User).where(
        User.show_in_search == True,
        User.is_active == True,
        or_(
            User.username.ilike(f"%{q}%"),
            User.display_name.ilike(f"%{q}%"),
        ),
    ).order_by(desc(User.discovery_score)).limit(limit)

    if current_user:
        query = query.where(User.id != current_user.id)

    result = await db.execute(query)
    users = result.scalars().all()

    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "avatar_url": u.avatar_url,
            "frame_tier": u.active_frame_tier,
        }
        for u in users
    ]


@router.get("/suggested", response_model=list[SuggestedUserResponse])
async def get_suggested_connections(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get suggested users to connect with"""
    # For now, return users with similar formats
    user_formats = [fs.format for fs in current_user.format_specialties] if current_user.format_specialties else []

    if not user_formats:
        # Fallback to top users by discovery score
        query = select(User).where(
            User.show_in_directory == True,
            User.is_active == True,
            User.id != current_user.id,
        ).order_by(desc(User.discovery_score)).limit(limit)
    else:
        query = select(User).join(UserFormatSpecialty).where(
            User.show_in_directory == True,
            User.is_active == True,
            User.id != current_user.id,
            UserFormatSpecialty.format.in_(user_formats),
        ).order_by(desc(User.discovery_score)).limit(limit)

    result = await db.execute(query.options(selectinload(User.format_specialties)))
    users = result.unique().scalars().all()

    return [
        SuggestedUserResponse(
            user=build_profile_card(u),
            reason="same_formats",
            matching_formats=[f for f in [fs.format for fs in u.format_specialties] if f in user_formats],
        )
        for u in users
    ]


@router.get("/recent")
async def get_recent_interactions(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get recently interacted users"""
    # TODO: Implement based on messages, trades, profile views
    return []


@router.get("/{user_id}/preview", response_model=QuickTradePreviewResponse)
async def get_trade_preview(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get quick trade preview with another user"""
    # TODO: Implement based on want lists and inventory
    return QuickTradePreviewResponse(
        user_id=user_id,
        cards_they_have_you_want=0,
        cards_they_have_you_want_value=0.0,
        cards_you_have_they_want=0,
        cards_you_have_they_want_value=0.0,
        is_mutual_match=False,
    )
```

**Step 2: Register route**

Add to `backend/app/api/api.py`:

```python
from app.api.routes import directory

api_router.include_router(directory.router, prefix="/directory", tags=["directory"])
```

**Step 3: Commit**

```bash
git add backend/app/api/routes/directory.py backend/app/api/api.py
git commit -m "feat: add user directory API endpoints"
```

---

### Task 4.3: Create Favorites API Route

**Files:**
- Create: `backend/app/api/routes/favorites.py`
- Modify: `backend/app/api/api.py`

**Step 1: Write the favorites route**

```python
# backend/app/api/routes/favorites.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.social import UserFavorite, UserNote
from app.schemas.favorites import (
    FavoritesListResponse,
    FavoriteUserResponse,
    AddFavoriteRequest,
    NotesListResponse,
    UserNoteResponse,
    CreateNoteRequest,
    UpdateNoteRequest,
)

router = APIRouter()


@router.get("", response_model=FavoritesListResponse)
async def get_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's favorited users"""
    result = await db.execute(
        select(UserFavorite)
        .options(selectinload(UserFavorite.favorited_user))
        .where(UserFavorite.user_id == current_user.id)
        .order_by(UserFavorite.created_at.desc())
    )
    favorites = result.scalars().all()

    return FavoritesListResponse(
        favorites=[
            FavoriteUserResponse(
                id=f.id,
                favorited_user_id=f.favorited_user_id,
                username=f.favorited_user.username,
                display_name=f.favorited_user.display_name,
                avatar_url=f.favorited_user.avatar_url,
                frame_tier=f.favorited_user.active_frame_tier or "bronze",
                notify_on_listings=f.notify_on_listings,
                created_at=f.created_at,
            )
            for f in favorites
        ],
        total=len(favorites),
    )


@router.post("/{user_id}")
async def add_favorite(
    user_id: int,
    request: AddFavoriteRequest = AddFavoriteRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add user to favorites"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot favorite yourself")

    # Check user exists
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already favorited
    existing = await db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.favorited_user_id == user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already favorited")

    favorite = UserFavorite(
        user_id=current_user.id,
        favorited_user_id=user_id,
        notify_on_listings=request.notify_on_listings,
    )
    db.add(favorite)
    await db.commit()

    return {"status": "ok"}


@router.delete("/{user_id}")
async def remove_favorite(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove user from favorites"""
    result = await db.execute(
        delete(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.favorited_user_id == user_id,
        )
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Favorite not found")

    return {"status": "ok"}


# Notes endpoints
@router.get("/notes", response_model=NotesListResponse)
async def get_notes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all private notes"""
    result = await db.execute(
        select(UserNote)
        .options(selectinload(UserNote.target_user))
        .where(UserNote.user_id == current_user.id)
        .order_by(UserNote.updated_at.desc())
    )
    notes = result.scalars().all()

    return NotesListResponse(
        notes=[
            UserNoteResponse(
                id=n.id,
                target_user_id=n.target_user_id,
                username=n.target_user.username,
                display_name=n.target_user.display_name,
                content=n.content,
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in notes
        ],
        total=len(notes),
    )


@router.get("/notes/{user_id}", response_model=UserNoteResponse)
async def get_note(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get note for specific user"""
    result = await db.execute(
        select(UserNote)
        .options(selectinload(UserNote.target_user))
        .where(
            UserNote.user_id == current_user.id,
            UserNote.target_user_id == user_id,
        )
    )
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    return UserNoteResponse(
        id=note.id,
        target_user_id=note.target_user_id,
        username=note.target_user.username,
        display_name=note.target_user.display_name,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.put("/notes/{user_id}", response_model=UserNoteResponse)
async def create_or_update_note(
    user_id: int,
    request: CreateNoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update note for a user"""
    # Check user exists
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Find existing or create
    result = await db.execute(
        select(UserNote).where(
            UserNote.user_id == current_user.id,
            UserNote.target_user_id == user_id,
        )
    )
    note = result.scalar_one_or_none()

    if note:
        note.content = request.content
    else:
        note = UserNote(
            user_id=current_user.id,
            target_user_id=user_id,
            content=request.content,
        )
        db.add(note)

    await db.commit()
    await db.refresh(note)

    return UserNoteResponse(
        id=note.id,
        target_user_id=note.target_user_id,
        username=target.username,
        display_name=target.display_name,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.delete("/notes/{user_id}")
async def delete_note(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete note for a user"""
    result = await db.execute(
        delete(UserNote).where(
            UserNote.user_id == current_user.id,
            UserNote.target_user_id == user_id,
        )
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Note not found")

    return {"status": "ok"}
```

**Step 2: Register route**

Add to `backend/app/api/api.py`:

```python
from app.api.routes import favorites

api_router.include_router(favorites.router, prefix="/favorites", tags=["favorites"])
```

**Step 3: Commit**

```bash
git add backend/app/api/routes/favorites.py backend/app/api/api.py
git commit -m "feat: add favorites and notes API endpoints"
```

---

## Phase 5-8: Remaining Implementation

Due to the extensive size of this implementation plan, the remaining phases are summarized below. Each task follows the same pattern: write failing test, implement, verify, commit.

### Phase 5: Trade Threads API
- **Task 5.1:** Create trade threads route (`/trades/{id}/thread`)
- **Task 5.2:** Add message sending with card embeds
- **Task 5.3:** Add photo attachment upload
- **Task 5.4:** Add reactions and deletion
- **Task 5.5:** Auto-create thread on trade proposal

### Phase 6: Moderation API
- **Task 6.1:** Create moderation queue route (`/admin/moderation/queue`)
- **Task 6.2:** Add case detail and action endpoints
- **Task 6.3:** Create appeals endpoints
- **Task 6.4:** Create trade disputes endpoints
- **Task 6.5:** Add moderator notes endpoints
- **Task 6.6:** Add auto-flag detection service

### Phase 7: Notifications API & WebSocket
- **Task 7.1:** Create notifications route
- **Task 7.2:** Add notification preferences endpoints
- **Task 7.3:** Implement WebSocket connection handler
- **Task 7.4:** Create notification service for sending
- **Task 7.5:** Integrate notifications with trade/message events

### Phase 8: Profile Enhancements
- **Task 8.1:** Extend profile endpoints with new fields
- **Task 8.2:** Add profile card export (PNG generation)
- **Task 8.3:** Add format specialties management
- **Task 8.4:** Create onboarding status endpoints

---

## Phase 9: Frontend - Profile Card Component

### Task 9.1: Create Profile Card Component

**Files:**
- Create: `frontend/src/components/social/ProfileCard.tsx`
- Create: `frontend/src/components/social/ProfileCardBack.tsx`
- Create: `frontend/src/components/social/FrameEffects.tsx`

**Step 1: Create base ProfileCard component**

```tsx
// frontend/src/components/social/ProfileCard.tsx
'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { ProfileCardBack } from './ProfileCardBack';
import { FrameEffects } from './FrameEffects';
import { Star, MessageCircle, ArrowRightLeft, UserPlus } from 'lucide-react';

interface ProfileCardProps {
  user: {
    id: number;
    username: string;
    displayName?: string;
    avatarUrl?: string;
    tagline?: string;
    cardType?: string;
    tradeCount: number;
    reputationScore?: number;
    reputationCount: number;
    frameTier: string;
    isOnline: boolean;
    badges: { key: string; icon: string; name: string }[];
    formats: string[];
    memberSince: string;
  };
  variant?: 'full' | 'standard' | 'compact';
  showActions?: boolean;
  onMessage?: () => void;
  onTrade?: () => void;
  onConnect?: () => void;
}

export function ProfileCard({
  user,
  variant = 'standard',
  showActions = true,
  onMessage,
  onTrade,
  onConnect,
}: ProfileCardProps) {
  const [isFlipped, setIsFlipped] = useState(false);

  const handleFlip = () => {
    if (variant !== 'compact') {
      setIsFlipped(!isFlipped);
    }
  };

  return (
    <div
      className={`
        relative perspective-1000
        ${variant === 'compact' ? 'w-48 h-24' : variant === 'standard' ? 'w-64 h-80' : 'w-80 h-96'}
      `}
    >
      <motion.div
        className="w-full h-full relative preserve-3d cursor-pointer"
        animate={{ rotateY: isFlipped ? 180 : 0 }}
        transition={{ duration: 0.6 }}
        onClick={handleFlip}
      >
        {/* Front */}
        <div className="absolute w-full h-full backface-hidden">
          <FrameEffects tier={user.frameTier}>
            <div className="p-4 h-full flex flex-col bg-gradient-to-b from-amber-50 to-amber-100 dark:from-gray-800 dark:to-gray-900">
              {/* Header */}
              <div className="flex items-center gap-2 mb-2">
                <div className="relative">
                  {user.avatarUrl ? (
                    <img
                      src={user.avatarUrl}
                      alt={user.username}
                      className="w-12 h-12 rounded-full border-2 border-amber-600"
                    />
                  ) : (
                    <div className="w-12 h-12 rounded-full bg-amber-600 flex items-center justify-center text-white font-bold">
                      {user.username[0].toUpperCase()}
                    </div>
                  )}
                  {user.isOnline && (
                    <div className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 rounded-full border-2 border-white" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-bold text-gray-900 dark:text-white truncate">
                    {user.displayName || user.username}
                  </h3>
                  <p className="text-xs text-gray-500">@{user.username}</p>
                </div>
                {user.cardType && (
                  <span className="text-xs px-2 py-0.5 bg-amber-200 dark:bg-amber-800 rounded-full">
                    {user.cardType}
                  </span>
                )}
              </div>

              {/* Tagline */}
              {user.tagline && (
                <p className="text-xs text-gray-600 dark:text-gray-400 italic mb-2 line-clamp-2">
                  "{user.tagline}"
                </p>
              )}

              {/* Stats */}
              <div className="flex items-center gap-4 text-sm mb-2">
                <div className="flex items-center gap-1">
                  <ArrowRightLeft className="w-4 h-4 text-amber-600" />
                  <span>{user.tradeCount}</span>
                </div>
                {user.reputationScore && (
                  <div className="flex items-center gap-1">
                    <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
                    <span>{user.reputationScore.toFixed(1)}</span>
                    <span className="text-gray-400">({user.reputationCount})</span>
                  </div>
                )}
              </div>

              {/* Badges */}
              {user.badges.length > 0 && (
                <div className="flex gap-1 mb-2">
                  {user.badges.slice(0, 4).map((badge) => (
                    <div
                      key={badge.key}
                      className="w-6 h-6 rounded bg-amber-200 dark:bg-amber-800 flex items-center justify-center"
                      title={badge.name}
                    >
                      <span className="text-xs">{badge.icon}</span>
                    </div>
                  ))}
                  {user.badges.length > 4 && (
                    <div className="w-6 h-6 rounded bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-xs">
                      +{user.badges.length - 4}
                    </div>
                  )}
                </div>
              )}

              {/* Formats */}
              {user.formats.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-2">
                  {user.formats.slice(0, 3).map((format) => (
                    <span
                      key={format}
                      className="text-xs px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded"
                    >
                      {format}
                    </span>
                  ))}
                </div>
              )}

              {/* Spacer */}
              <div className="flex-1" />

              {/* Actions */}
              {showActions && (
                <div className="flex gap-2 mt-2" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={onMessage}
                    className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded text-sm"
                  >
                    <MessageCircle className="w-4 h-4" />
                    Message
                  </button>
                  <button
                    onClick={onTrade}
                    className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded text-sm"
                  >
                    <ArrowRightLeft className="w-4 h-4" />
                    Trade
                  </button>
                </div>
              )}
            </div>
          </FrameEffects>
        </div>

        {/* Back */}
        <div className="absolute w-full h-full backface-hidden rotate-y-180">
          <ProfileCardBack userId={user.id} frameTier={user.frameTier} />
        </div>
      </motion.div>
    </div>
  );
}
```

**Step 2: Create FrameEffects component**

```tsx
// frontend/src/components/social/FrameEffects.tsx
'use client';

import { ReactNode } from 'react';
import { motion } from 'framer-motion';

interface FrameEffectsProps {
  tier: string;
  children: ReactNode;
}

const frameStyles: Record<string, string> = {
  bronze: 'border-amber-700 shadow-md',
  silver: 'border-gray-400 shadow-lg shadow-gray-300/50',
  gold: 'border-yellow-500 shadow-lg shadow-yellow-400/30',
  platinum: 'border-cyan-400 shadow-xl shadow-cyan-400/40',
  legendary: 'border-purple-500 shadow-2xl shadow-purple-500/50',
};

export function FrameEffects({ tier, children }: FrameEffectsProps) {
  const baseStyle = frameStyles[tier] || frameStyles.bronze;
  const isAnimated = tier === 'platinum' || tier === 'legendary';

  return (
    <motion.div
      className={`
        relative rounded-lg border-4 overflow-hidden h-full
        ${baseStyle}
      `}
      whileHover={
        tier !== 'bronze'
          ? {
              scale: 1.02,
              rotateY: 5,
              rotateX: 5,
            }
          : undefined
      }
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    >
      {/* Shimmer effect for higher tiers */}
      {isAnimated && (
        <div className="absolute inset-0 pointer-events-none">
          <motion.div
            className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
            animate={{
              x: ['-100%', '100%'],
            }}
            transition={{
              repeat: Infinity,
              duration: 3,
              ease: 'linear',
            }}
          />
        </div>
      )}

      {/* Particle effects for legendary */}
      {tier === 'legendary' && (
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          {[...Array(5)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-1 h-1 bg-purple-400 rounded-full"
              initial={{
                x: Math.random() * 100 + '%',
                y: '100%',
                opacity: 0,
              }}
              animate={{
                y: '-10%',
                opacity: [0, 1, 0],
              }}
              transition={{
                repeat: Infinity,
                duration: 2 + Math.random() * 2,
                delay: Math.random() * 2,
                ease: 'easeOut',
              }}
            />
          ))}
        </div>
      )}

      {children}
    </motion.div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/social/
git commit -m "feat: add ProfileCard and FrameEffects components"
```

---

## Phase 10-12: Remaining Frontend

### Phase 10: Directory Page
- **Task 10.1:** Create `/traders` page layout
- **Task 10.2:** Add search and filters
- **Task 10.3:** Add grid/list view toggle
- **Task 10.4:** Add favorites integration

### Phase 11: Trade Chat Integration
- **Task 11.1:** Create TradeThread component
- **Task 11.2:** Add photo upload
- **Task 11.3:** Add card embed picker
- **Task 11.4:** Integrate with existing messages page

### Phase 12: Admin Moderation Dashboard
- **Task 12.1:** Create `/admin/moderation` layout
- **Task 12.2:** Add moderation queue component
- **Task 12.3:** Add case detail view
- **Task 12.4:** Add dispute resolution UI

---

## Phase 13: Achievement Seeding

### Task 13.1: Seed Achievement Definitions

**Files:**
- Create: `backend/app/db/seeds/achievements.py`

**Step 1: Write seed script**

```python
# backend/app/db/seeds/achievements.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.achievement import AchievementDefinition

ACHIEVEMENT_DEFINITIONS = [
    # Trade Milestones
    {"key": "first_deal", "name": "First Deal", "description": "Complete your first trade", "category": "trade", "icon": "🤝", "threshold": {"trades": 1}, "discovery_points": 5, "frame_tier_unlock": None},
    {"key": "regular_trader", "name": "Regular Trader", "description": "Complete 10 trades", "category": "trade", "icon": "⚖️", "threshold": {"trades": 10}, "discovery_points": 15, "frame_tier_unlock": "silver"},
    {"key": "seasoned_dealer", "name": "Seasoned Dealer", "description": "Complete 50 trades", "category": "trade", "icon": "💰", "threshold": {"trades": 50}, "discovery_points": 30, "frame_tier_unlock": "gold"},
    {"key": "trade_master", "name": "Trade Master", "description": "Complete 100 trades", "category": "trade", "icon": "📜", "threshold": {"trades": 100}, "discovery_points": 50, "frame_tier_unlock": "platinum"},
    {"key": "market_legend", "name": "Market Legend", "description": "Complete 500 trades", "category": "trade", "icon": "👑", "threshold": {"trades": 500}, "discovery_points": 100, "frame_tier_unlock": "legendary"},

    # Reputation Tiers
    {"key": "newcomer", "name": "Newcomer", "description": "Start your trading journey", "category": "reputation", "icon": "🌱", "threshold": {"reviews": 0}, "discovery_points": 10, "frame_tier_unlock": None},
    {"key": "established", "name": "Established", "description": "5+ reviews with 4.0+ average", "category": "reputation", "icon": "🌳", "threshold": {"reviews": 5, "avg_rating": 4.0}, "discovery_points": 30, "frame_tier_unlock": "silver"},
    {"key": "trusted", "name": "Trusted", "description": "20+ reviews with 4.5+ average", "category": "reputation", "icon": "🌲", "threshold": {"reviews": 20, "avg_rating": 4.5}, "discovery_points": 60, "frame_tier_unlock": "gold"},
    {"key": "elite", "name": "Elite", "description": "50+ reviews with 4.7+ average", "category": "reputation", "icon": "🏛️", "threshold": {"reviews": 50, "avg_rating": 4.7}, "discovery_points": 100, "frame_tier_unlock": "platinum"},

    # Portfolio Value
    {"key": "starter_collection", "name": "Starter Collection", "description": "$100+ tracked portfolio", "category": "portfolio", "icon": "💎", "threshold": {"portfolio_value": 100}, "discovery_points": 5, "frame_tier_unlock": None},
    {"key": "growing_hoard", "name": "Growing Hoard", "description": "$1,000+ tracked portfolio", "category": "portfolio", "icon": "📦", "threshold": {"portfolio_value": 1000}, "discovery_points": 10, "frame_tier_unlock": "silver"},
    {"key": "serious_collector", "name": "Serious Collector", "description": "$10,000+ tracked portfolio", "category": "portfolio", "icon": "🏆", "threshold": {"portfolio_value": 10000}, "discovery_points": 20, "frame_tier_unlock": "gold"},
    {"key": "dragons_hoard", "name": "Dragon's Hoard", "description": "$50,000+ tracked portfolio", "category": "portfolio", "icon": "🐉", "threshold": {"portfolio_value": 50000}, "discovery_points": 35, "frame_tier_unlock": "platinum"},
    {"key": "legendary_vault", "name": "Legendary Vault", "description": "$100,000+ tracked portfolio", "category": "portfolio", "icon": "🏰", "threshold": {"portfolio_value": 100000}, "discovery_points": 50, "frame_tier_unlock": "legendary"},

    # Community Contribution
    {"key": "friendly", "name": "Friendly", "description": "Give 5 endorsements", "category": "community", "icon": "🤚", "threshold": {"endorsements_given": 5}, "discovery_points": 10, "frame_tier_unlock": None},
    {"key": "helpful", "name": "Helpful", "description": "Write 20 reviews", "category": "community", "icon": "✍️", "threshold": {"reviews_written": 20}, "discovery_points": 20, "frame_tier_unlock": None},
    {"key": "community_pillar", "name": "Community Pillar", "description": "Give 50+ endorsements", "category": "community", "icon": "🏛️", "threshold": {"endorsements_given": 50}, "discovery_points": 40, "frame_tier_unlock": "gold"},
    {"key": "veteran", "name": "Veteran", "description": "1 year member", "category": "community", "icon": "📅", "threshold": {"member_days": 365}, "discovery_points": 25, "frame_tier_unlock": None},

    # Special Achievements
    {"key": "negotiator", "name": "Negotiator", "description": "10 counter-offers accepted", "category": "special", "icon": "♟️", "threshold": {"counter_offers_accepted": 10}, "discovery_points": 25, "frame_tier_unlock": None},
    {"key": "big_deal", "name": "Big Deal", "description": "Single trade over $500", "category": "special", "icon": "💠", "threshold": {"single_trade_value": 500}, "discovery_points": 20, "frame_tier_unlock": None},
    {"key": "whale_trade", "name": "Whale Trade", "description": "Single trade over $2,000", "category": "special", "icon": "🐋", "threshold": {"single_trade_value": 2000}, "discovery_points": 40, "frame_tier_unlock": None},
    {"key": "perfect_record", "name": "Perfect Record", "description": "50+ trades with 100% success", "category": "special", "icon": "🛡️", "threshold": {"trades": 50, "success_rate": 100}, "discovery_points": 50, "frame_tier_unlock": "platinum"},
    {"key": "speed_dealer", "name": "Speed Dealer", "description": "10 trades completed within 24h", "category": "special", "icon": "⚡", "threshold": {"fast_trades": 10}, "discovery_points": 15, "frame_tier_unlock": None},

    # Hidden Achievements
    {"key": "night_owl", "name": "Night Owl", "description": "Complete a trade between 2-4 AM", "category": "special", "icon": "🦉", "threshold": {"night_trade": True}, "discovery_points": 10, "frame_tier_unlock": None, "is_hidden": True},
]


async def seed_achievements(db: AsyncSession):
    """Seed achievement definitions"""
    for ach_data in ACHIEVEMENT_DEFINITIONS:
        existing = await db.execute(
            select(AchievementDefinition).where(AchievementDefinition.key == ach_data["key"])
        )
        if not existing.scalar_one_or_none():
            achievement = AchievementDefinition(**ach_data)
            db.add(achievement)

    await db.commit()
    print(f"Seeded {len(ACHIEVEMENT_DEFINITIONS)} achievement definitions")
```

**Step 2: Add to seed command**

Update `backend/app/db/seed.py` to include:

```python
from app.db.seeds.achievements import seed_achievements

async def run_seeds(db: AsyncSession):
    # ... existing seeds ...
    await seed_achievements(db)
```

**Step 3: Run seed**

Run: `docker compose exec backend python -m app.db.seed`

**Step 4: Commit**

```bash
git add backend/app/db/seeds/achievements.py backend/app/db/seed.py
git commit -m "feat: seed achievement definitions"
```

---

## Completion Checklist

- [ ] Phase 1: Database migrations (6 tasks)
- [ ] Phase 2: Backend models (5 tasks)
- [ ] Phase 3: Backend schemas (6 tasks)
- [ ] Phase 4: Backend API routes (3+ tasks)
- [ ] Phase 5: Trade threads API (5 tasks)
- [ ] Phase 6: Moderation API (6 tasks)
- [ ] Phase 7: Notifications & WebSocket (5 tasks)
- [ ] Phase 8: Profile enhancements (4 tasks)
- [ ] Phase 9: Frontend ProfileCard (1 task)
- [ ] Phase 10: Directory page (4 tasks)
- [ ] Phase 11: Trade chat UI (4 tasks)
- [ ] Phase 12: Admin moderation UI (4 tasks)
- [ ] Phase 13: Achievement seeding (1 task)
- [ ] Generate TypeScript types: `make generate-types`
- [ ] Run full test suite: `make test`
- [ ] Manual testing of all features

---

## Notes for Implementer

1. **Run migrations in order** - Each migration depends on the previous
2. **Generate types after backend changes** - `make generate-types` keeps frontend in sync
3. **Test each phase** - Don't proceed until current phase tests pass
4. **Check CLAUDE.md** - Contains project patterns and conventions
5. **Reference design doc** - `docs/plans/2026-01-18-social-trading-platform-design.md` has full specs
