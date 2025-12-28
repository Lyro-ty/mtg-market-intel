# Collection, Want List & Insights API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build backend APIs to power Collection, Want List, and Insights frontend pages with real-time notifications and cached stats.

**Architecture:** New models (WantListItem, Notification, Set, CollectionStats, UserMilestone) with User extensions. REST API routes for CRUD operations. Celery tasks for background processing. Redis caching for unread counts.

**Tech Stack:** FastAPI, SQLAlchemy (async), Alembic, Celery, Redis, pytest

---

## Phase 1: Database Models & Migrations

### Task 1: Create WantListItem model

**Files:**
- Create: `backend/app/models/want_list.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Create the model file**

```python
# backend/app/models/want_list.py
"""Want list model for tracking cards users want to acquire."""
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.card import Card


class WantListItem(Base):
    """Card on user's want list with target price and alert settings."""

    __tablename__ = "want_list_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    target_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="want_list_items")
    card: Mapped["Card"] = relationship("Card", lazy="joined")

    __table_args__ = (
        Index("ix_want_list_user_card", "user_id", "card_id", unique=True),
        Index("ix_want_list_alert_enabled", "alert_enabled"),
    )

    def __repr__(self) -> str:
        return f"<WantListItem user={self.user_id} card={self.card_id} target=${self.target_price}>"
```

**Step 2: Add to models __init__.py**

Add import to `backend/app/models/__init__.py`:
```python
from app.models.want_list import WantListItem
```

And add to `__all__` list.

**Step 3: Commit**

```bash
git add backend/app/models/want_list.py backend/app/models/__init__.py
git commit -m "feat: add WantListItem model"
```

---

### Task 2: Create Notification model

**Files:**
- Create: `backend/app/models/notification.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Create the model file**

```python
# backend/app/models/notification.py
"""Unified notification model for all alert types."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Boolean, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.card import Card


class NotificationType(str, Enum):
    """Types of notifications."""
    PRICE_ALERT = "price_alert"
    TARGET_HIT = "target_hit"
    SPIKE_DETECTED = "spike_detected"
    OPPORTUNITY = "opportunity"
    MILESTONE = "milestone"
    EDUCATIONAL = "educational"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Notification(Base):
    """Unified notification for alerts, opportunities, and insights."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional card reference
    card_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True
    )

    # Flexible metadata (price, change %, action URL, etc.)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Read status
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Lifecycle
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Deduplication hash
    dedup_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")
    card: Mapped[Optional["Card"]] = relationship("Card", lazy="joined")

    __table_args__ = (
        Index("ix_notification_user_unread", "user_id", "read"),
        Index("ix_notification_user_type", "user_id", "type"),
        Index("ix_notification_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Notification {self.type} user={self.user_id} read={self.read}>"
```

**Step 2: Add to models __init__.py**

```python
from app.models.notification import Notification, NotificationType, NotificationPriority
```

**Step 3: Commit**

```bash
git add backend/app/models/notification.py backend/app/models/__init__.py
git commit -m "feat: add Notification model with types and priorities"
```

---

### Task 3: Create Set model

**Files:**
- Create: `backend/app/models/mtg_set.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Create the model file**

```python
# backend/app/models/mtg_set.py
"""MTG Set model for set metadata and card counts."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MTGSet(Base):
    """MTG Set metadata with cached card counts."""

    __tablename__ = "sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    set_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    released_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    card_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    icon_svg_uri: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<MTGSet {self.code} ({self.name}) cards={self.card_count}>"
```

**Step 2: Add to models __init__.py**

```python
from app.models.mtg_set import MTGSet
```

**Step 3: Commit**

```bash
git add backend/app/models/mtg_set.py backend/app/models/__init__.py
git commit -m "feat: add MTGSet model for set metadata"
```

---

### Task 4: Create CollectionStats model

**Files:**
- Create: `backend/app/models/collection_stats.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Create the model file**

```python
# backend/app/models/collection_stats.py
"""Cached collection statistics per user/set."""
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Boolean, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class CollectionStats(Base):
    """Cached per-user set completion statistics."""

    __tablename__ = "collection_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    set_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    owned_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    is_stale: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="collection_stats")

    __table_args__ = (
        Index("ix_collection_stats_user_set", "user_id", "set_code", unique=True),
    )

    def __repr__(self) -> str:
        return f"<CollectionStats user={self.user_id} set={self.set_code} {self.owned_count}/{self.total_count}>"
```

**Step 2: Add to models __init__.py**

```python
from app.models.collection_stats import CollectionStats
```

**Step 3: Commit**

```bash
git add backend/app/models/collection_stats.py backend/app/models/__init__.py
git commit -m "feat: add CollectionStats model for cached set completion"
```

---

### Task 5: Create UserMilestone model

**Files:**
- Create: `backend/app/models/milestone.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Create the model file**

```python
# backend/app/models/milestone.py
"""User milestone achievements for collection tracking."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class MilestoneType(str, Enum):
    """Types of collection milestones."""
    FIRST_RARE = "first_rare"
    FIRST_MYTHIC = "first_mythic"
    SET_25_PCT = "set_25_pct"
    SET_50_PCT = "set_50_pct"
    SET_75_PCT = "set_75_pct"
    SET_COMPLETE = "set_complete"
    MYTHIC_10 = "mythic_10"
    MYTHIC_25 = "mythic_25"
    VALUE_100 = "value_100"
    VALUE_500 = "value_500"
    VALUE_1000 = "value_1000"
    VALUE_5000 = "value_5000"


# Milestone display info
MILESTONE_INFO = {
    MilestoneType.FIRST_RARE: ("First Rare", "Collected your first rare card"),
    MilestoneType.FIRST_MYTHIC: ("First Mythic", "Collected your first mythic rare"),
    MilestoneType.SET_25_PCT: ("Set Starter", "Own 25% of any set"),
    MilestoneType.SET_50_PCT: ("Halfway There", "Own 50% of any set"),
    MilestoneType.SET_75_PCT: ("Almost Complete", "Own 75% of any set"),
    MilestoneType.SET_COMPLETE: ("Set Master", "Own 100% of a set"),
    MilestoneType.MYTHIC_10: ("Mythic Hunter", "Collect 10 mythic rares"),
    MilestoneType.MYTHIC_25: ("Mythic Collector", "Collect 25 mythic rares"),
    MilestoneType.VALUE_100: ("Starting Portfolio", "Portfolio value exceeds $100"),
    MilestoneType.VALUE_500: ("Growing Portfolio", "Portfolio value exceeds $500"),
    MilestoneType.VALUE_1000: ("Serious Collector", "Portfolio value exceeds $1,000"),
    MilestoneType.VALUE_5000: ("Elite Collector", "Portfolio value exceeds $5,000"),
}


class UserMilestone(Base):
    """Tracks collection achievement milestones."""

    __tablename__ = "user_milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    milestone_type: Mapped[str] = mapped_column(String(30), nullable=False)
    achieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Context (which set, which card triggered it, etc.)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="milestones")

    __table_args__ = (
        Index("ix_milestone_user_type", "user_id", "milestone_type", unique=True),
    )

    def __repr__(self) -> str:
        return f"<UserMilestone {self.milestone_type} user={self.user_id}>"
```

**Step 2: Add to models __init__.py**

```python
from app.models.milestone import UserMilestone, MilestoneType, MILESTONE_INFO
```

**Step 3: Commit**

```bash
git add backend/app/models/milestone.py backend/app/models/__init__.py
git commit -m "feat: add UserMilestone model for collection achievements"
```

---

### Task 6: Extend User model

**Files:**
- Modify: `backend/app/models/user.py`

**Step 1: Add notification preferences and relationships**

Add to imports:
```python
from sqlalchemy import Integer
```

Add after existing fields (before relationships):
```python
    # Notification preferences
    email_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    price_drop_threshold: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    digest_frequency: Mapped[str] = mapped_column(String(10), default="instant", nullable=False)
```

Add to TYPE_CHECKING block:
```python
    from app.models.want_list import WantListItem
    from app.models.notification import Notification
    from app.models.milestone import UserMilestone
    from app.models.collection_stats import CollectionStats
```

Add relationships:
```python
    want_list_items: Mapped[list["WantListItem"]] = relationship(
        "WantListItem", back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
    milestones: Mapped[list["UserMilestone"]] = relationship(
        "UserMilestone", back_populates="user", cascade="all, delete-orphan"
    )
    collection_stats: Mapped[list["CollectionStats"]] = relationship(
        "CollectionStats", back_populates="user", cascade="all, delete-orphan"
    )
```

**Step 2: Commit**

```bash
git add backend/app/models/user.py
git commit -m "feat: extend User model with notification prefs and new relationships"
```

---

### Task 7: Create Alembic migration

**Files:**
- Create: `backend/alembic/versions/20251228_001_add_wantlist_notifications.py`

**Step 1: Generate migration**

Run in worktree:
```bash
cd backend
alembic revision -m "add want_list notifications sets collection_stats milestones"
```

**Step 2: Edit migration file**

```python
"""add want_list notifications sets collection_stats milestones

Revision ID: [auto-generated]
Revises: [previous-head]
Create Date: 2025-12-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '20251228_001'
down_revision: Union[str, None] = None  # Will be set by alembic
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sets table
    op.create_table(
        'sets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(10), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('set_type', sa.String(50), nullable=True),
        sa.Column('released_at', sa.Date(), nullable=True),
        sa.Column('card_count', sa.Integer(), default=0, nullable=False),
        sa.Column('icon_svg_uri', sa.String(500), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Create want_list_items table
    op.create_table(
        'want_list_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('card_id', sa.Integer(), sa.ForeignKey('cards.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('target_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('priority', sa.String(10), default='medium', nullable=False),
        sa.Column('alert_enabled', sa.Boolean(), default=True, nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_want_list_user_card', 'want_list_items', ['user_id', 'card_id'], unique=True)
    op.create_index('ix_want_list_alert_enabled', 'want_list_items', ['alert_enabled'])

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('type', sa.String(30), nullable=False, index=True),
        sa.Column('priority', sa.String(10), default='medium', nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('card_id', sa.Integer(), sa.ForeignKey('cards.id', ondelete='SET NULL'), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('read', sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dedup_hash', sa.String(64), nullable=True, index=True),
    )
    op.create_index('ix_notification_user_unread', 'notifications', ['user_id', 'read'])
    op.create_index('ix_notification_user_type', 'notifications', ['user_id', 'type'])
    op.create_index('ix_notification_created', 'notifications', ['created_at'])

    # Create collection_stats table
    op.create_table(
        'collection_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('set_code', sa.String(10), nullable=False, index=True),
        sa.Column('owned_count', sa.Integer(), default=0, nullable=False),
        sa.Column('total_count', sa.Integer(), default=0, nullable=False),
        sa.Column('total_value', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('is_stale', sa.Boolean(), default=True, nullable=False, index=True),
        sa.Column('calculated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_collection_stats_user_set', 'collection_stats', ['user_id', 'set_code'], unique=True)

    # Create user_milestones table
    op.create_table(
        'user_milestones',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('milestone_type', sa.String(30), nullable=False),
        sa.Column('achieved_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
    )
    op.create_index('ix_milestone_user_type', 'user_milestones', ['user_id', 'milestone_type'], unique=True)

    # Add columns to users table
    op.add_column('users', sa.Column('email_alerts', sa.Boolean(), default=True, nullable=False, server_default='true'))
    op.add_column('users', sa.Column('price_drop_threshold', sa.Integer(), default=10, nullable=False, server_default='10'))
    op.add_column('users', sa.Column('digest_frequency', sa.String(10), default='instant', nullable=False, server_default='instant'))


def downgrade() -> None:
    # Remove columns from users table
    op.drop_column('users', 'digest_frequency')
    op.drop_column('users', 'price_drop_threshold')
    op.drop_column('users', 'email_alerts')

    # Drop tables
    op.drop_table('user_milestones')
    op.drop_table('collection_stats')
    op.drop_table('notifications')
    op.drop_table('want_list_items')
    op.drop_table('sets')
```

**Step 3: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat: add migration for want_list, notifications, sets, collection_stats, milestones"
```

---

## Phase 2: Pydantic Schemas

### Task 8: Create want list schemas

**Files:**
- Create: `backend/app/schemas/want_list.py`

**Step 1: Create schemas**

```python
# backend/app/schemas/want_list.py
"""Pydantic schemas for want list endpoints."""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class WantListItemCreate(BaseModel):
    """Request to add card to want list."""
    card_id: int
    target_price: Decimal
    priority: Literal["high", "medium", "low"] = "medium"
    alert_enabled: bool = True
    notes: Optional[str] = None


class WantListItemUpdate(BaseModel):
    """Request to update want list item."""
    target_price: Optional[Decimal] = None
    priority: Optional[Literal["high", "medium", "low"]] = None
    alert_enabled: Optional[bool] = None
    notes: Optional[str] = None


class WantListItemResponse(BaseModel):
    """Want list item with current price info."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    card_name: str
    set_code: str
    set_name: Optional[str]
    image_url: Optional[str]
    current_price: Optional[Decimal]
    target_price: Decimal
    priority: str
    alert_enabled: bool
    notes: Optional[str]
    added_date: datetime
    price_diff_pct: Optional[float]  # (current - target) / current * 100
    is_near_target: bool  # within 10%


class WantListResponse(BaseModel):
    """Paginated want list response."""
    items: list[WantListItemResponse]
    total: int
    near_target_count: int


class NearTargetResponse(BaseModel):
    """Cards near their target price."""
    items: list[WantListItemResponse]
    count: int
```

**Step 2: Commit**

```bash
git add backend/app/schemas/want_list.py
git commit -m "feat: add want list Pydantic schemas"
```

---

### Task 9: Create notification schemas

**Files:**
- Create: `backend/app/schemas/notification.py`

**Step 1: Create schemas**

```python
# backend/app/schemas/notification.py
"""Pydantic schemas for notification endpoints."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    """Single notification."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    priority: str
    title: str
    message: str
    card_name: Optional[str] = None
    set_code: Optional[str] = None
    current_price: Optional[Decimal] = None
    price_change: Optional[float] = None
    action: Optional[str] = None
    action_url: Optional[str] = None
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated notification list."""
    items: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Quick count for nav badge."""
    count: int
    by_type: dict[str, int]


class MarkAllReadResponse(BaseModel):
    """Result of mark all read operation."""
    updated_count: int
```

**Step 2: Commit**

```bash
git add backend/app/schemas/notification.py
git commit -m "feat: add notification Pydantic schemas"
```

---

### Task 10: Create collection schemas

**Files:**
- Create: `backend/app/schemas/collection.py`

**Step 1: Create schemas**

```python
# backend/app/schemas/collection.py
"""Pydantic schemas for collection endpoints."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SetProgress(BaseModel):
    """Single set completion progress."""
    code: str
    name: str
    owned: int
    total: int
    value: Decimal
    completion_pct: float
    icon_url: Optional[str] = None


class SetProgressResponse(BaseModel):
    """Set completion for all sets user has cards in."""
    sets: list[SetProgress]
    is_calculating: bool


class CollectionStatsResponse(BaseModel):
    """Aggregate collection statistics."""
    total_cards: int
    unique_cards: int
    sets_started: int
    sets_complete: int
    total_value: Decimal
    avg_completion_pct: float
    is_calculating: bool


class MilestoneResponse(BaseModel):
    """Single milestone with achievement status."""
    type: str
    title: str
    description: str
    achieved: bool
    achieved_at: Optional[datetime] = None
    metadata: Optional[dict] = None


class MilestonesResponse(BaseModel):
    """All milestones for user."""
    milestones: list[MilestoneResponse]
    achieved_count: int
    total_count: int


class RarityDistributionResponse(BaseModel):
    """Card counts by rarity."""
    mythic: int
    rare: int
    uncommon: int
    common: int


class RefreshResponse(BaseModel):
    """Result of stats refresh request."""
    message: str
    sets_queued: int
```

**Step 2: Commit**

```bash
git add backend/app/schemas/collection.py
git commit -m "feat: add collection Pydantic schemas"
```

---

### Task 11: Create sets schemas

**Files:**
- Create: `backend/app/schemas/sets.py`

**Step 1: Create schemas**

```python
# backend/app/schemas/sets.py
"""Pydantic schemas for sets endpoints."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SetResponse(BaseModel):
    """Basic set info."""
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    set_type: Optional[str] = None
    released_at: Optional[date] = None
    card_count: int
    icon_svg_uri: Optional[str] = None


class SetDetailResponse(SetResponse):
    """Detailed set info."""
    last_synced_at: datetime
```

**Step 2: Commit**

```bash
git add backend/app/schemas/sets.py
git commit -m "feat: add sets Pydantic schemas"
```

---

## Phase 3: API Routes

### Task 12: Create want list routes

**Files:**
- Create: `backend/app/api/routes/want_list.py`
- Modify: `backend/app/api/routes/__init__.py` (if exists) or `backend/app/main.py`

**Step 1: Create routes**

```python
# backend/app/api/routes/want_list.py
"""Want list API endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models import Card, WantListItem, PriceSnapshot
from app.schemas.want_list import (
    WantListItemCreate,
    WantListItemUpdate,
    WantListItemResponse,
    WantListResponse,
    NearTargetResponse,
)

router = APIRouter()


def _calculate_price_diff(current: float | None, target: float) -> tuple[float | None, bool]:
    """Calculate price difference percentage and near-target status."""
    if current is None or current == 0:
        return None, False
    diff_pct = ((current - target) / current) * 100
    is_near = (current - target) <= target * 0.1
    return diff_pct, is_near


@router.get("/", response_model=WantListResponse)
async def list_want_list(
    current_user: CurrentUser,
    priority: Optional[str] = None,
    sort_by: str = Query("priority", regex="^(priority|price|date)$"),
    db: AsyncSession = Depends(get_db),
):
    """List user's want list with current prices."""
    query = (
        select(WantListItem)
        .options(joinedload(WantListItem.card))
        .where(WantListItem.user_id == current_user.id)
    )

    if priority:
        query = query.where(WantListItem.priority == priority)

    result = await db.execute(query)
    items = result.scalars().all()

    # Get current prices for all cards
    card_ids = [item.card_id for item in items]
    price_query = (
        select(PriceSnapshot.card_id, func.max(PriceSnapshot.price).label("price"))
        .where(PriceSnapshot.card_id.in_(card_ids))
        .group_by(PriceSnapshot.card_id)
    )
    price_result = await db.execute(price_query)
    prices = {row.card_id: row.price for row in price_result}

    # Build response
    response_items = []
    near_target_count = 0

    for item in items:
        current_price = prices.get(item.card_id)
        price_diff_pct, is_near = _calculate_price_diff(current_price, float(item.target_price))
        if is_near:
            near_target_count += 1

        response_items.append(WantListItemResponse(
            id=item.id,
            card_id=item.card_id,
            card_name=item.card.name,
            set_code=item.card.set_code,
            set_name=item.card.set_name,
            image_url=item.card.image_url,
            current_price=current_price,
            target_price=item.target_price,
            priority=item.priority,
            alert_enabled=item.alert_enabled,
            notes=item.notes,
            added_date=item.created_at,
            price_diff_pct=price_diff_pct,
            is_near_target=is_near,
        ))

    # Sort
    if sort_by == "priority":
        priority_order = {"high": 0, "medium": 1, "low": 2}
        response_items.sort(key=lambda x: priority_order.get(x.priority, 1))
    elif sort_by == "price":
        response_items.sort(key=lambda x: x.current_price or 0, reverse=True)
    else:  # date
        response_items.sort(key=lambda x: x.added_date, reverse=True)

    return WantListResponse(
        items=response_items,
        total=len(response_items),
        near_target_count=near_target_count,
    )


@router.post("/", response_model=WantListItemResponse, status_code=201)
async def add_to_want_list(
    item: WantListItemCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Add card to want list."""
    # Check if card exists
    card = await db.get(Card, item.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check for duplicate
    existing = await db.execute(
        select(WantListItem).where(
            and_(
                WantListItem.user_id == current_user.id,
                WantListItem.card_id == item.card_id,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Card already in want list")

    # Create item
    db_item = WantListItem(
        user_id=current_user.id,
        card_id=item.card_id,
        target_price=item.target_price,
        priority=item.priority,
        alert_enabled=item.alert_enabled,
        notes=item.notes,
    )
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)

    # Get current price
    price_result = await db.execute(
        select(func.max(PriceSnapshot.price))
        .where(PriceSnapshot.card_id == item.card_id)
    )
    current_price = price_result.scalar()
    price_diff_pct, is_near = _calculate_price_diff(current_price, float(item.target_price))

    return WantListItemResponse(
        id=db_item.id,
        card_id=db_item.card_id,
        card_name=card.name,
        set_code=card.set_code,
        set_name=card.set_name,
        image_url=card.image_url,
        current_price=current_price,
        target_price=db_item.target_price,
        priority=db_item.priority,
        alert_enabled=db_item.alert_enabled,
        notes=db_item.notes,
        added_date=db_item.created_at,
        price_diff_pct=price_diff_pct,
        is_near_target=is_near,
    )


@router.patch("/{item_id}", response_model=WantListItemResponse)
async def update_want_list_item(
    item_id: int,
    update: WantListItemUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Update want list item."""
    result = await db.execute(
        select(WantListItem)
        .options(joinedload(WantListItem.card))
        .where(
            and_(
                WantListItem.id == item_id,
                WantListItem.user_id == current_user.id,
            )
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Want list item not found")

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)

    # Get current price
    price_result = await db.execute(
        select(func.max(PriceSnapshot.price))
        .where(PriceSnapshot.card_id == item.card_id)
    )
    current_price = price_result.scalar()
    price_diff_pct, is_near = _calculate_price_diff(current_price, float(item.target_price))

    return WantListItemResponse(
        id=item.id,
        card_id=item.card_id,
        card_name=item.card.name,
        set_code=item.card.set_code,
        set_name=item.card.set_name,
        image_url=item.card.image_url,
        current_price=current_price,
        target_price=item.target_price,
        priority=item.priority,
        alert_enabled=item.alert_enabled,
        notes=item.notes,
        added_date=item.created_at,
        price_diff_pct=price_diff_pct,
        is_near_target=is_near,
    )


@router.delete("/{item_id}", status_code=204)
async def remove_from_want_list(
    item_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Remove card from want list."""
    result = await db.execute(
        select(WantListItem).where(
            and_(
                WantListItem.id == item_id,
                WantListItem.user_id == current_user.id,
            )
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Want list item not found")

    await db.delete(item)
    await db.commit()


@router.get("/near-target", response_model=NearTargetResponse)
async def get_near_target(
    current_user: CurrentUser,
    threshold_pct: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get cards within X% of target price."""
    # Get all want list items with prices
    query = (
        select(WantListItem)
        .options(joinedload(WantListItem.card))
        .where(WantListItem.user_id == current_user.id)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    # Get current prices
    card_ids = [item.card_id for item in items]
    if not card_ids:
        return NearTargetResponse(items=[], count=0)

    price_query = (
        select(PriceSnapshot.card_id, func.max(PriceSnapshot.price).label("price"))
        .where(PriceSnapshot.card_id.in_(card_ids))
        .group_by(PriceSnapshot.card_id)
    )
    price_result = await db.execute(price_query)
    prices = {row.card_id: row.price for row in price_result}

    # Filter to near-target items
    near_items = []
    for item in items:
        current_price = prices.get(item.card_id)
        if current_price is None:
            continue

        target = float(item.target_price)
        threshold = target * (threshold_pct / 100)
        if (current_price - target) <= threshold:
            price_diff_pct, is_near = _calculate_price_diff(current_price, target)
            near_items.append(WantListItemResponse(
                id=item.id,
                card_id=item.card_id,
                card_name=item.card.name,
                set_code=item.card.set_code,
                set_name=item.card.set_name,
                image_url=item.card.image_url,
                current_price=current_price,
                target_price=item.target_price,
                priority=item.priority,
                alert_enabled=item.alert_enabled,
                notes=item.notes,
                added_date=item.created_at,
                price_diff_pct=price_diff_pct,
                is_near_target=is_near,
            ))

    return NearTargetResponse(items=near_items, count=len(near_items))
```

**Step 2: Register router in main.py**

Add to `backend/app/main.py`:
```python
from app.api.routes import want_list
app.include_router(want_list.router, prefix="/api/want-list", tags=["want-list"])
```

**Step 3: Commit**

```bash
git add backend/app/api/routes/want_list.py backend/app/main.py
git commit -m "feat: add want list API routes"
```

---

### Task 13: Create notification routes

**Files:**
- Create: `backend/app/api/routes/notifications.py`
- Modify: `backend/app/main.py`

**Step 1: Create routes**

```python
# backend/app/api/routes/notifications.py
"""Notification API endpoints."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models import Notification
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    UnreadCountResponse,
    MarkAllReadResponse,
)

router = APIRouter()


def _build_notification_response(notif: Notification) -> NotificationResponse:
    """Build response from notification model."""
    metadata = notif.metadata or {}
    return NotificationResponse(
        id=notif.id,
        type=notif.type,
        priority=notif.priority,
        title=notif.title,
        message=notif.message,
        card_name=notif.card.name if notif.card else None,
        set_code=notif.card.set_code if notif.card else None,
        current_price=metadata.get("current_price") or metadata.get("price"),
        price_change=metadata.get("change_pct") or metadata.get("price_change"),
        action=metadata.get("action"),
        action_url=metadata.get("action_url"),
        read=notif.read,
        created_at=notif.created_at,
    )


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    current_user: CurrentUser,
    type: Optional[str] = None,
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List notifications, newest first."""
    query = (
        select(Notification)
        .options(joinedload(Notification.card))
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )

    if type:
        query = query.where(Notification.type == type)
    if unread_only:
        query = query.where(Notification.read == False)

    # Get total count
    count_query = select(func.count()).select_from(
        query.with_only_columns(Notification.id).subquery()
    )
    total = await db.scalar(count_query) or 0

    # Get unread count
    unread_count = await db.scalar(
        select(func.count())
        .where(
            and_(
                Notification.user_id == current_user.id,
                Notification.read == False,
            )
        )
    ) or 0

    # Apply pagination
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    notifications = result.scalars().all()

    return NotificationListResponse(
        items=[_build_notification_response(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get unread notification count."""
    # Total unread
    total = await db.scalar(
        select(func.count())
        .where(
            and_(
                Notification.user_id == current_user.id,
                Notification.read == False,
            )
        )
    ) or 0

    # Count by type
    type_counts = await db.execute(
        select(Notification.type, func.count().label("count"))
        .where(
            and_(
                Notification.user_id == current_user.id,
                Notification.read == False,
            )
        )
        .group_by(Notification.type)
    )
    by_type = {row.type: row.count for row in type_counts}

    return UnreadCountResponse(count=total, by_type=by_type)


@router.patch("/{notification_id}/read", status_code=204)
async def mark_as_read(
    notification_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Mark single notification as read."""
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.read = True
    notif.read_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/mark-all-read", response_model=MarkAllReadResponse)
async def mark_all_read(
    current_user: CurrentUser,
    type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read."""
    query = (
        update(Notification)
        .where(
            and_(
                Notification.user_id == current_user.id,
                Notification.read == False,
            )
        )
        .values(read=True, read_at=datetime.now(timezone.utc))
    )

    if type:
        query = query.where(Notification.type == type)

    result = await db.execute(query)
    await db.commit()

    return MarkAllReadResponse(updated_count=result.rowcount)


@router.delete("/{notification_id}", status_code=204)
async def dismiss_notification(
    notification_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Permanently dismiss notification."""
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    await db.delete(notif)
    await db.commit()
```

**Step 2: Register router**

Add to `backend/app/main.py`:
```python
from app.api.routes import notifications
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
```

**Step 3: Commit**

```bash
git add backend/app/api/routes/notifications.py backend/app/main.py
git commit -m "feat: add notification API routes"
```

---

### Task 14: Create collection routes

**Files:**
- Create: `backend/app/api/routes/collection.py`
- Modify: `backend/app/main.py`

**Step 1: Create routes** (see design doc for full implementation)

**Step 2: Register router**

**Step 3: Commit**

```bash
git add backend/app/api/routes/collection.py backend/app/main.py
git commit -m "feat: add collection API routes"
```

---

### Task 15: Create sets routes

**Files:**
- Create: `backend/app/api/routes/sets.py`
- Modify: `backend/app/main.py`

**Step 1: Create routes**

```python
# backend/app/api/routes/sets.py
"""Sets API endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import MTGSet
from app.schemas.sets import SetResponse, SetDetailResponse

router = APIRouter()


@router.get("/", response_model=list[SetResponse])
async def list_sets(
    set_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all sets with card counts."""
    query = select(MTGSet).order_by(MTGSet.released_at.desc())

    if set_type:
        query = query.where(MTGSet.set_type == set_type)

    result = await db.execute(query)
    sets = result.scalars().all()

    return [SetResponse.model_validate(s) for s in sets]


@router.get("/{code}", response_model=SetDetailResponse)
async def get_set(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Get single set details."""
    result = await db.execute(
        select(MTGSet).where(MTGSet.code == code.lower())
    )
    mtg_set = result.scalar_one_or_none()

    if not mtg_set:
        raise HTTPException(status_code=404, detail="Set not found")

    return SetDetailResponse.model_validate(mtg_set)
```

**Step 2: Register router**

**Step 3: Commit**

```bash
git add backend/app/api/routes/sets.py backend/app/main.py
git commit -m "feat: add sets API routes"
```

---

## Phase 4: Tests

### Task 16: Create want list tests

**Files:**
- Create: `backend/tests/api/test_want_list.py`

**Step 1: Write tests**

```python
# backend/tests/api/test_want_list.py
"""Tests for want list API endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, User, WantListItem


@pytest.fixture
async def test_card(db_session: AsyncSession) -> Card:
    """Create a test card."""
    card = Card(
        scryfall_id="test-card-123",
        name="Force of Will",
        set_code="ALL",
        set_name="Alliances",
        collector_number="42",
        rarity="rare",
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest.fixture
async def auth_headers(client: AsyncClient, db_session: AsyncSession) -> dict:
    """Create user and return auth headers."""
    # Register user
    await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "testpass123",
    })

    # Login
    response = await client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestWantList:
    """Want list endpoint tests."""

    async def test_add_to_want_list(
        self, client: AsyncClient, auth_headers: dict, test_card: Card
    ):
        """Test adding card to want list."""
        response = await client.post(
            "/api/want-list/",
            headers=auth_headers,
            json={
                "card_id": test_card.id,
                "target_price": "50.00",
                "priority": "high",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["card_name"] == "Force of Will"
        assert data["target_price"] == "50.00"
        assert data["priority"] == "high"

    async def test_add_duplicate_returns_409(
        self, client: AsyncClient, auth_headers: dict, test_card: Card
    ):
        """Test adding same card twice returns conflict."""
        # Add first time
        await client.post(
            "/api/want-list/",
            headers=auth_headers,
            json={"card_id": test_card.id, "target_price": "50.00"},
        )

        # Add second time
        response = await client.post(
            "/api/want-list/",
            headers=auth_headers,
            json={"card_id": test_card.id, "target_price": "60.00"},
        )
        assert response.status_code == 409

    async def test_list_want_list(
        self, client: AsyncClient, auth_headers: dict, test_card: Card
    ):
        """Test listing want list."""
        # Add item
        await client.post(
            "/api/want-list/",
            headers=auth_headers,
            json={"card_id": test_card.id, "target_price": "50.00"},
        )

        response = await client.get("/api/want-list/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    async def test_update_want_list_item(
        self, client: AsyncClient, auth_headers: dict, test_card: Card
    ):
        """Test updating want list item."""
        # Add item
        create_response = await client.post(
            "/api/want-list/",
            headers=auth_headers,
            json={"card_id": test_card.id, "target_price": "50.00"},
        )
        item_id = create_response.json()["id"]

        # Update
        response = await client.patch(
            f"/api/want-list/{item_id}",
            headers=auth_headers,
            json={"target_price": "45.00", "priority": "medium"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["target_price"] == "45.00"
        assert data["priority"] == "medium"

    async def test_delete_want_list_item(
        self, client: AsyncClient, auth_headers: dict, test_card: Card
    ):
        """Test deleting want list item."""
        # Add item
        create_response = await client.post(
            "/api/want-list/",
            headers=auth_headers,
            json={"card_id": test_card.id, "target_price": "50.00"},
        )
        item_id = create_response.json()["id"]

        # Delete
        response = await client.delete(
            f"/api/want-list/{item_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

        # Verify gone
        list_response = await client.get("/api/want-list/", headers=auth_headers)
        assert list_response.json()["total"] == 0
```

**Step 2: Run tests**

```bash
cd backend && pytest tests/api/test_want_list.py -v
```

**Step 3: Commit**

```bash
git add backend/tests/api/test_want_list.py
git commit -m "test: add want list API tests"
```

---

### Task 17: Create notification tests

**Files:**
- Create: `backend/tests/api/test_notifications.py`

(Similar pattern to want list tests)

**Step 1: Write tests**
**Step 2: Run tests**
**Step 3: Commit**

---

## Phase 5: Celery Tasks

### Task 18: Create notification service

**Files:**
- Create: `backend/app/services/notifications.py`

**Step 1: Create service**

```python
# backend/app/services/notifications.py
"""Notification creation and management service."""
import hashlib
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, NotificationType, NotificationPriority


async def create_notification(
    db: AsyncSession,
    user_id: int,
    type: NotificationType,
    title: str,
    message: str,
    priority: NotificationPriority = NotificationPriority.MEDIUM,
    card_id: Optional[int] = None,
    metadata: Optional[dict] = None,
    deduplicate: bool = True,
) -> Notification:
    """Create notification with optional deduplication."""
    dedup_hash = None

    if deduplicate and card_id:
        # Generate dedup hash
        dedup_hash = hashlib.sha256(
            f"{user_id}:{type.value}:{card_id}:{date.today()}".encode()
        ).hexdigest()[:16]

        # Check for existing unread
        existing = await db.execute(
            select(Notification).where(
                and_(
                    Notification.dedup_hash == dedup_hash,
                    Notification.read == False,
                )
            )
        )
        if existing.scalar_one_or_none():
            # Update existing instead
            existing_notif = existing.scalar_one()
            existing_notif.created_at = datetime.now(timezone.utc)
            existing_notif.metadata = metadata
            return existing_notif

    notif = Notification(
        user_id=user_id,
        type=type.value,
        priority=priority.value,
        title=title,
        message=message,
        card_id=card_id,
        metadata=metadata,
        dedup_hash=dedup_hash,
    )
    db.add(notif)
    return notif


async def has_recent_notification(
    db: AsyncSession,
    user_id: int,
    card_id: int,
    hours: int = 24,
) -> bool:
    """Check if notification was sent recently for this card."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.card_id == card_id,
                Notification.created_at >= cutoff,
            )
        )
    )
    return result.scalar_one_or_none() is not None
```

**Step 2: Commit**

```bash
git add backend/app/services/notifications.py
git commit -m "feat: add notification service with deduplication"
```

---

### Task 19: Create want list price check task

**Files:**
- Create: `backend/app/tasks/want_list.py`
- Modify: `backend/app/tasks/celery_app.py`

(Implementation follows design doc)

---

### Task 20: Create collection stats task

**Files:**
- Create: `backend/app/tasks/collection.py`
- Modify: `backend/app/tasks/celery_app.py`

(Implementation follows design doc)

---

### Task 21: Create sets sync task

**Files:**
- Create: `backend/app/tasks/sets.py`
- Modify: `backend/app/tasks/celery_app.py`

(Implementation follows design doc)

---

## Phase 6: Frontend Integration

### Task 22: Update frontend want list page

**Files:**
- Modify: `frontend/src/app/(protected)/want-list/page.tsx`
- Modify: `frontend/src/lib/api.ts`

**Step 1: Add API functions to lib/api.ts**

```typescript
// Want List API
export async function getWantList(params?: { priority?: string; sort_by?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.priority) searchParams.set('priority', params.priority);
  if (params?.sort_by) searchParams.set('sort_by', params.sort_by);
  return fetchWithAuth(`/api/want-list/?${searchParams}`);
}

export async function addToWantList(data: {
  card_id: number;
  target_price: number;
  priority?: string;
  alert_enabled?: boolean;
  notes?: string;
}) {
  return fetchWithAuth('/api/want-list/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateWantListItem(id: number, data: {
  target_price?: number;
  priority?: string;
  alert_enabled?: boolean;
  notes?: string;
}) {
  return fetchWithAuth(`/api/want-list/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function removeFromWantList(id: number) {
  return fetchWithAuth(`/api/want-list/${id}`, { method: 'DELETE' });
}
```

**Step 2: Update page to use React Query**

Replace mock data with:
```typescript
const { data: wantList, isLoading } = useQuery({
  queryKey: ['want-list', filterPriority, sortBy],
  queryFn: () => getWantList({ priority: filterPriority, sort_by: sortBy }),
});
```

**Step 3: Commit**

---

### Task 23: Update frontend notifications

**Files:**
- Modify: `frontend/src/app/(protected)/insights/page.tsx`
- Modify: `frontend/src/lib/api.ts`

(Similar pattern)

---

### Task 24: Update frontend collection page

**Files:**
- Modify: `frontend/src/app/(protected)/collection/page.tsx`
- Modify: `frontend/src/lib/api.ts`

(Similar pattern)

---

## Phase 7: Final Verification

### Task 25: Run full test suite

```bash
make test-backend
```

### Task 26: Verify migrations

```bash
make migrate
```

### Task 27: Manual API testing

Test each endpoint with curl or API client.

### Task 28: Commit and push

```bash
git push origin feature/collection-wantlist-insights-api
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1-7 | Database models and migrations |
| 2 | 8-11 | Pydantic schemas |
| 3 | 12-15 | API routes |
| 4 | 16-17 | Tests |
| 5 | 18-21 | Celery tasks |
| 6 | 22-24 | Frontend integration |
| 7 | 25-28 | Verification |

**Total: 28 tasks**
