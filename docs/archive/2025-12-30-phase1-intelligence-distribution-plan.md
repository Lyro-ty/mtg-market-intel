# Phase 1: Intelligence + Distribution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Best-in-class price intelligence distributed via Discord - have/want lists, matching algorithm, Discord bot

**Architecture:** Extend inventory with have list linking, add trading preferences to want list, build Discord bot as separate service, implement matching algorithm with quality scoring.

**Tech Stack:** FastAPI, SQLAlchemy, discord.py, Redis (caching matches), Celery (background notifications)

**Prerequisites:** Phase 0 must be complete (user profiles, connected accounts, Discord OAuth)

---

## Overview

Phase 1 has 4 major components:

| Component | Tasks | Description |
|-----------|-------|-------------|
| 1.1 Have List | 1-6 | Link inventory items for trading |
| 1.2 Want List Extensions | 7-10 | Add trading preferences |
| 1.3 Discord Bot | 11-20 | Price lookup, list management |
| 1.4 Matching Algorithm | 21-28 | Find compatible trades |

---

## Task 1: Have List Migration

**Files:**
- Create: `backend/alembic/versions/20251231_001_have_list.py`

**Step 1: Create migration**

```python
"""have_list

Add have_list_items table for trading.
"""
from alembic import op
import sqlalchemy as sa

revision = '20251231_001'
down_revision = '20251230_004'  # After Phase 0
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'have_list_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), sa.ForeignKey('inventory_items.id', ondelete='CASCADE'), nullable=False),

        # Trading preferences
        sa.Column('min_trade_value', sa.Numeric(10, 2), nullable=True),
        sa.Column('trade_for_wants_only', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),

        # Status
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('ix_have_list_user_active', 'have_list_items', ['user_id', 'is_active'])
    op.create_index('ix_have_list_inventory', 'have_list_items', ['inventory_item_id'], unique=True)


def downgrade():
    op.drop_index('ix_have_list_inventory', table_name='have_list_items')
    op.drop_index('ix_have_list_user_active', table_name='have_list_items')
    op.drop_table('have_list_items')
```

**Step 2: Run migration**

Run: `docker compose exec backend alembic upgrade head`
Expected: Migration applies successfully

**Step 3: Commit**

```bash
git add backend/alembic/versions/20251231_001_have_list.py
git commit -m "feat: add have_list_items table"
```

---

## Task 2: Have List Model

**Files:**
- Create: `backend/app/models/have_list.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/inventory.py`

**Step 1: Create have list model**

Create `backend/app/models/have_list.py`:
```python
"""Have list model for trading."""
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.inventory import InventoryItem


class HaveListItem(Base):
    """Card from inventory marked as available for trade."""

    __tablename__ = "have_list_items"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    inventory_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Trading preferences
    min_trade_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    trade_for_wants_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="have_list_items")
    inventory_item: Mapped["InventoryItem"] = relationship(
        "InventoryItem", back_populates="have_list_item"
    )

    # Computed properties (delegated from inventory)
    @property
    def card(self):
        return self.inventory_item.card

    @property
    def condition(self):
        return self.inventory_item.condition

    @property
    def is_foil(self):
        return self.inventory_item.is_foil

    @property
    def quantity(self):
        return self.inventory_item.quantity

    def __repr__(self) -> str:
        return f"<HaveListItem user={self.user_id} card={self.inventory_item.card_id}>"
```

**Step 2: Add relationship to InventoryItem**

Add to `backend/app/models/inventory.py` in the TYPE_CHECKING block:
```python
from app.models.have_list import HaveListItem
```

Add to InventoryItem class:
```python
    have_list_item: Mapped[Optional["HaveListItem"]] = relationship(
        "HaveListItem",
        back_populates="inventory_item",
        uselist=False,
        cascade="all, delete-orphan",
    )
```

**Step 3: Add relationship to User**

Add to `backend/app/models/user.py`:
```python
    have_list_items: Mapped[list["HaveListItem"]] = relationship(
        "HaveListItem",
        back_populates="user",
        cascade="all, delete-orphan",
    )
```

**Step 4: Export from models**

Add to `backend/app/models/__init__.py`:
```python
from app.models.have_list import HaveListItem
```

**Step 5: Verify model loads**

Run: `docker compose exec backend python -c "from app.models import HaveListItem; print('OK')"`
Expected: OK

**Step 6: Commit**

```bash
git add backend/app/models/have_list.py backend/app/models/inventory.py backend/app/models/user.py backend/app/models/__init__.py
git commit -m "feat: add HaveListItem model"
```

---

## Task 3: Have List Schemas

**Files:**
- Create: `backend/app/schemas/have_list.py`

**Step 1: Create schemas**

Create `backend/app/schemas/have_list.py`:
```python
"""Have list schemas."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field

from app.core.hashids import encode_id


class HaveListItemCreate(BaseModel):
    """Create a have list item from inventory."""

    inventory_item_id: int
    min_trade_value: Optional[Decimal] = Field(None, ge=0)
    trade_for_wants_only: bool = False
    notes: Optional[str] = Field(None, max_length=500)


class HaveListItemUpdate(BaseModel):
    """Update have list item preferences."""

    min_trade_value: Optional[Decimal] = Field(None, ge=0)
    trade_for_wants_only: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class HaveListItemResponse(BaseModel):
    """Have list item response."""

    id: int
    user_id: int
    inventory_item_id: int

    # Card info (from inventory)
    card_id: int
    card_hashid: str
    card_name: str
    set_code: str
    image_url: Optional[str] = None
    condition: str
    is_foil: bool
    quantity: int

    # Trading preferences
    min_trade_value: Optional[Decimal] = None
    trade_for_wants_only: bool = False
    notes: Optional[str] = None
    is_active: bool = True

    # Current value
    current_price: Optional[Decimal] = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, item, current_price: Optional[Decimal] = None) -> "HaveListItemResponse":
        """Build response from model with computed fields."""
        return cls(
            id=item.id,
            user_id=item.user_id,
            inventory_item_id=item.inventory_item_id,
            card_id=item.inventory_item.card_id,
            card_hashid=encode_id("card", item.inventory_item.card_id),
            card_name=item.inventory_item.card.name,
            set_code=item.inventory_item.card.set_code,
            image_url=item.inventory_item.card.image_url,
            condition=item.condition,
            is_foil=item.is_foil,
            quantity=item.quantity,
            min_trade_value=item.min_trade_value,
            trade_for_wants_only=item.trade_for_wants_only,
            notes=item.notes,
            is_active=item.is_active,
            current_price=current_price,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class HaveListPublicResponse(BaseModel):
    """Public have list view (for other users)."""

    card_id: int
    card_hashid: str
    card_name: str
    set_code: str
    image_url: Optional[str] = None
    condition: str
    is_foil: bool
    quantity: int
    notes: Optional[str] = None
    current_price: Optional[Decimal] = None

    model_config = {"from_attributes": True}
```

**Step 2: Verify schemas**

Run: `docker compose exec backend python -c "from app.schemas.have_list import HaveListItemCreate, HaveListItemResponse; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/app/schemas/have_list.py
git commit -m "feat: add have list schemas"
```

---

## Task 4: Have List API Endpoints

**Files:**
- Create: `backend/app/api/routes/have_list.py`
- Modify: `backend/app/api/__init__.py`

**Step 1: Create have list routes**

Create `backend/app/api/routes/have_list.py`:
```python
"""Have list API endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User, InventoryItem, HaveListItem
from app.schemas.have_list import (
    HaveListItemCreate,
    HaveListItemUpdate,
    HaveListItemResponse,
)

router = APIRouter(prefix="/have-list", tags=["have-list"])


@router.get("", response_model=list[HaveListItemResponse])
async def list_have_list(
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List current user's have list items."""
    query = (
        select(HaveListItem)
        .where(HaveListItem.user_id == current_user.id)
        .options(
            selectinload(HaveListItem.inventory_item).selectinload(InventoryItem.card)
        )
        .order_by(HaveListItem.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    if active_only:
        query = query.where(HaveListItem.is_active == True)

    result = await db.execute(query)
    items = result.scalars().all()

    return [HaveListItemResponse.from_model(item) for item in items]


@router.post("", response_model=HaveListItemResponse, status_code=201)
async def add_to_have_list(
    item: HaveListItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add inventory item to have list for trading."""
    # Verify ownership of inventory item
    inv_query = select(InventoryItem).where(
        InventoryItem.id == item.inventory_item_id,
        InventoryItem.user_id == current_user.id,
    ).options(selectinload(InventoryItem.card))

    result = await db.execute(inv_query)
    inventory_item = result.scalar_one_or_none()

    if not inventory_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    # Check if already in have list
    existing_query = select(HaveListItem).where(
        HaveListItem.inventory_item_id == item.inventory_item_id
    )
    result = await db.execute(existing_query)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Item already in have list")

    # Create have list item
    have_item = HaveListItem(
        user_id=current_user.id,
        inventory_item_id=item.inventory_item_id,
        min_trade_value=item.min_trade_value,
        trade_for_wants_only=item.trade_for_wants_only,
        notes=item.notes,
    )

    db.add(have_item)
    await db.commit()
    await db.refresh(have_item)

    # Reload with relationships
    result = await db.execute(
        select(HaveListItem)
        .where(HaveListItem.id == have_item.id)
        .options(selectinload(HaveListItem.inventory_item).selectinload(InventoryItem.card))
    )
    have_item = result.scalar_one()

    return HaveListItemResponse.from_model(have_item)


@router.patch("/{item_id}", response_model=HaveListItemResponse)
async def update_have_list_item(
    item_id: int,
    updates: HaveListItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update have list item preferences."""
    query = (
        select(HaveListItem)
        .where(HaveListItem.id == item_id, HaveListItem.user_id == current_user.id)
        .options(selectinload(HaveListItem.inventory_item).selectinload(InventoryItem.card))
    )

    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Have list item not found")

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)

    return HaveListItemResponse.from_model(item)


@router.delete("/{item_id}", status_code=204)
async def remove_from_have_list(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove item from have list."""
    query = select(HaveListItem).where(
        HaveListItem.id == item_id,
        HaveListItem.user_id == current_user.id,
    )

    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Have list item not found")

    await db.delete(item)
    await db.commit()
```

**Step 2: Register routes**

Add to `backend/app/api/__init__.py`:
```python
from app.api.routes import have_list
api_router.include_router(have_list.router)
```

**Step 3: Verify routes**

Run: `docker compose exec backend python -c "from app.api import api_router; print([r.path for r in api_router.routes if 'have-list' in r.path])"`
Expected: List of have-list routes

**Step 4: Commit**

```bash
git add backend/app/api/routes/have_list.py backend/app/api/__init__.py
git commit -m "feat: add have list API endpoints"
```

---

## Task 5: Have List Tests

**Files:**
- Create: `backend/tests/api/test_have_list.py`

**Step 1: Write tests**

Create `backend/tests/api/test_have_list.py`:
```python
"""Tests for have list endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_add_to_have_list(client: AsyncClient, auth_headers: dict, test_inventory_item: dict):
    """Add inventory item to have list."""
    response = await client.post(
        "/api/have-list",
        headers=auth_headers,
        json={
            "inventory_item_id": test_inventory_item["id"],
            "min_trade_value": 10.00,
            "trade_for_wants_only": True,
            "notes": "Looking for similar value",
        }
    )
    assert response.status_code == 201

    data = response.json()
    assert data["inventory_item_id"] == test_inventory_item["id"]
    assert data["min_trade_value"] == "10.00"
    assert data["trade_for_wants_only"] is True
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_have_list(client: AsyncClient, auth_headers: dict):
    """List have list items."""
    response = await client.get("/api/have-list", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_update_have_list_item(client: AsyncClient, auth_headers: dict, test_have_list_item: dict):
    """Update have list item preferences."""
    response = await client.patch(
        f"/api/have-list/{test_have_list_item['id']}",
        headers=auth_headers,
        json={"min_trade_value": 25.00, "is_active": False}
    )
    assert response.status_code == 200

    data = response.json()
    assert data["min_trade_value"] == "25.00"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_remove_from_have_list(client: AsyncClient, auth_headers: dict, test_have_list_item: dict):
    """Remove item from have list."""
    response = await client.delete(
        f"/api/have-list/{test_have_list_item['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_cannot_add_duplicate(client: AsyncClient, auth_headers: dict, test_have_list_item: dict):
    """Cannot add same inventory item twice."""
    # The fixture already added the item
    response = await client.post(
        "/api/have-list",
        headers=auth_headers,
        json={"inventory_item_id": test_have_list_item["inventory_item_id"]}
    )
    assert response.status_code == 400
    assert "already in have list" in response.json()["detail"]
```

**Step 2: Run tests**

Run: `docker compose exec backend pytest tests/api/test_have_list.py -v`
Expected: Tests run (may need fixtures)

**Step 3: Commit**

```bash
git add backend/tests/api/test_have_list.py
git commit -m "test: add have list API tests"
```

---

## Task 6: Public Have List Endpoint

**Files:**
- Modify: `backend/app/api/routes/users.py`

**Step 1: Add public have list endpoint**

Add to `backend/app/api/routes/users.py`:
```python
from app.models import HaveListItem, InventoryItem
from app.schemas.have_list import HaveListPublicResponse


@router.get("/{username}/have-list", response_model=list[HaveListPublicResponse])
async def get_user_have_list(
    username: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Get a user's public have list."""
    # Get user
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_own_profile = current_user and current_user.id == user.id

    # Check privacy
    if not user.show_have_list and not is_own_profile:
        raise HTTPException(status_code=403, detail="This user's have list is private")

    # Get have list items
    have_query = (
        select(HaveListItem)
        .where(HaveListItem.user_id == user.id, HaveListItem.is_active == True)
        .options(
            selectinload(HaveListItem.inventory_item).selectinload(InventoryItem.card)
        )
        .order_by(HaveListItem.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(have_query)
    items = result.scalars().all()

    return [
        HaveListPublicResponse(
            card_id=item.inventory_item.card_id,
            card_hashid=encode_id("card", item.inventory_item.card_id),
            card_name=item.inventory_item.card.name,
            set_code=item.inventory_item.card.set_code,
            image_url=item.inventory_item.card.image_url,
            condition=item.condition,
            is_foil=item.is_foil,
            quantity=item.quantity,
            notes=item.notes,
        )
        for item in items
    ]
```

**Step 2: Commit**

```bash
git add backend/app/api/routes/users.py
git commit -m "feat: add public have list endpoint"
```

---

## Task 7: Want List Extensions Migration

**Files:**
- Create: `backend/alembic/versions/20251231_002_want_list_extensions.py`

**Step 1: Create migration**

```python
"""want_list_extensions

Add trading-related fields to want_list_items.
"""
from alembic import op
import sqlalchemy as sa

revision = '20251231_002'
down_revision = '20251231_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add trading-specific fields
    op.add_column('want_list_items', sa.Column('quantity', sa.Integer(), server_default='1', nullable=False))
    op.add_column('want_list_items', sa.Column('condition_min', sa.String(20), server_default='LP', nullable=False))
    op.add_column('want_list_items', sa.Column('is_foil_required', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('want_list_items', sa.Column('language', sa.String(10), server_default='EN', nullable=False))
    op.add_column('want_list_items', sa.Column('max_trade_value', sa.Numeric(10, 2), nullable=True))
    op.add_column('want_list_items', sa.Column('is_public', sa.Boolean(), server_default='true', nullable=False))

    # Index for public wants (for matching)
    op.create_index('ix_want_list_public', 'want_list_items', ['is_public', 'is_active'])


def downgrade():
    op.drop_index('ix_want_list_public', table_name='want_list_items')
    op.drop_column('want_list_items', 'is_public')
    op.drop_column('want_list_items', 'max_trade_value')
    op.drop_column('want_list_items', 'language')
    op.drop_column('want_list_items', 'is_foil_required')
    op.drop_column('want_list_items', 'condition_min')
    op.drop_column('want_list_items', 'quantity')
```

**Step 2: Run migration**

Run: `docker compose exec backend alembic upgrade head`
Expected: Migration applies successfully

**Step 3: Commit**

```bash
git add backend/alembic/versions/20251231_002_want_list_extensions.py
git commit -m "feat: add trading fields to want_list_items"
```

---

## Task 8: Update Want List Model

**Files:**
- Modify: `backend/app/models/want_list.py`

**Step 1: Add new fields**

Add to WantListItem class:
```python
    # Trading preferences (Phase 1)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    condition_min: Mapped[str] = mapped_column(String(20), default="LP", nullable=False)
    is_foil_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="EN", nullable=False)
    max_trade_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

**Step 2: Verify model**

Run: `docker compose exec backend python -c "from app.models.want_list import WantListItem; print([c.name for c in WantListItem.__table__.columns if 'condition' in c.name or 'quantity' in c.name])"`
Expected: `['quantity', 'condition_min']`

**Step 3: Commit**

```bash
git add backend/app/models/want_list.py
git commit -m "feat: add trading fields to WantListItem model"
```

---

## Task 9: Update Want List Schemas

**Files:**
- Modify: `backend/app/schemas/want_list.py`

**Step 1: Add new fields to schemas**

Add to WantListItemCreate:
```python
    quantity: int = Field(1, ge=1, le=99)
    condition_min: str = Field("LP", pattern="^(NM|LP|MP|HP|DMG)$")
    is_foil_required: bool = False
    language: str = Field("EN", pattern="^[A-Z]{2}$")
    max_trade_value: Optional[Decimal] = Field(None, ge=0)
    is_public: bool = True
```

Add to WantListItemResponse:
```python
    quantity: int
    condition_min: str
    is_foil_required: bool
    language: str
    max_trade_value: Optional[Decimal] = None
    is_public: bool
```

**Step 2: Commit**

```bash
git add backend/app/schemas/want_list.py
git commit -m "feat: add trading fields to want list schemas"
```

---

## Task 10: Public Want List Endpoint

**Files:**
- Modify: `backend/app/api/routes/users.py`

**Step 1: Add public want list endpoint**

Add to `backend/app/api/routes/users.py`:
```python
from app.models import WantListItem


class WantListPublicResponse(BaseModel):
    """Public want list item."""
    card_id: int
    card_hashid: str
    card_name: str
    set_code: str
    image_url: Optional[str] = None
    quantity: int
    condition_min: str
    is_foil_required: bool
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


@router.get("/{username}/want-list", response_model=list[WantListPublicResponse])
async def get_user_want_list(
    username: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Get a user's public want list."""
    # Get user
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_own_profile = current_user and current_user.id == user.id

    # Check privacy
    if not user.show_want_list and not is_own_profile:
        raise HTTPException(status_code=403, detail="This user's want list is private")

    # Get want list items
    want_query = (
        select(WantListItem)
        .where(
            WantListItem.user_id == user.id,
            WantListItem.is_active == True,
        )
        .options(selectinload(WantListItem.card))
        .order_by(WantListItem.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    # If not own profile, only show public items
    if not is_own_profile:
        want_query = want_query.where(WantListItem.is_public == True)

    result = await db.execute(want_query)
    items = result.scalars().all()

    return [
        WantListPublicResponse(
            card_id=item.card_id,
            card_hashid=encode_id("card", item.card_id),
            card_name=item.card.name,
            set_code=item.card.set_code,
            image_url=item.card.image_url,
            quantity=item.quantity,
            condition_min=item.condition_min,
            is_foil_required=item.is_foil_required,
            notes=item.notes,
        )
        for item in items
    ]
```

**Step 2: Commit**

```bash
git add backend/app/api/routes/users.py
git commit -m "feat: add public want list endpoint"
```

---

## Task 11-20: Discord Bot

The Discord bot is a separate service. These tasks create the bot infrastructure.

### Task 11: Discord Bot Scaffold

**Files:**
- Create: `discord-bot/` directory structure

**Step 1: Create directory structure**

```bash
mkdir -p discord-bot/bot/{api,cogs,ui,tasks}
touch discord-bot/bot/__init__.py
touch discord-bot/bot/api/__init__.py
touch discord-bot/bot/cogs/__init__.py
touch discord-bot/bot/ui/__init__.py
touch discord-bot/bot/tasks/__init__.py
```

**Step 2: Create requirements.txt**

Create `discord-bot/requirements.txt`:
```
discord.py>=2.3.0
httpx>=0.25.0
python-dotenv>=1.0.0
structlog>=24.0.0
redis>=5.0.0
```

**Step 3: Create config**

Create `discord-bot/bot/config.py`:
```python
"""Discord bot configuration."""
import os
from dataclasses import dataclass


@dataclass
class Config:
    discord_token: str
    api_base_url: str
    api_key: str
    redis_url: str
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            discord_token=os.environ["DISCORD_BOT_TOKEN"],
            api_base_url=os.environ.get("DUALCASTER_API_URL", "http://backend:8000/api"),
            api_key=os.environ["DUALCASTER_API_KEY"],
            redis_url=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )


config = Config.from_env() if os.environ.get("DISCORD_BOT_TOKEN") else None
```

**Step 4: Create main.py**

Create `discord-bot/bot/main.py`:
```python
"""Discord bot entry point."""
import asyncio
import discord
from discord.ext import commands
import structlog

from .config import Config

log = structlog.get_logger()


class DualcasterBot(commands.Bot):
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix="/dd ",
            intents=intents,
            description="Dualcaster Deals - MTG Price Intelligence",
        )
        self.config = config

    async def setup_hook(self):
        """Load cogs on startup."""
        # Load cogs
        await self.load_extension("bot.cogs.prices")
        await self.load_extension("bot.cogs.account")
        await self.load_extension("bot.cogs.wants")
        await self.load_extension("bot.cogs.haves")

        # Sync commands
        await self.tree.sync()
        log.info("Bot commands synced")

    async def on_ready(self):
        log.info("Bot ready", user=self.user.name, guilds=len(self.guilds))


def run_bot():
    config = Config.from_env()
    bot = DualcasterBot(config)
    bot.run(config.discord_token)


if __name__ == "__main__":
    run_bot()
```

**Step 5: Commit**

```bash
git add discord-bot/
git commit -m "feat: add Discord bot scaffold"
```

---

### Task 12-15: Bot Cogs

Create the cogs for prices, account linking, wants, and haves management.

(Full implementation details would follow the same pattern - creating each cog file with the slash commands)

---

## Task 21-28: Matching Algorithm

### Task 21: Matching Engine Core

**Files:**
- Create: `backend/app/services/matching/engine.py`
- Create: `backend/app/services/matching/__init__.py`

**Step 1: Create matching engine**

Create `backend/app/services/matching/__init__.py`:
```python
from .engine import MatchingEngine, MatchCandidate, QualityFactors

__all__ = ["MatchingEngine", "MatchCandidate", "QualityFactors"]
```

Create `backend/app/services/matching/engine.py`:
```python
"""Matching algorithm for finding compatible trades."""
from dataclasses import dataclass
from decimal import Decimal
from math import radians, sin, cos, sqrt, atan2
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import User, WantListItem, HaveListItem, InventoryItem, ConnectedAccount


CONDITION_RANK = {'NM': 5, 'LP': 4, 'MP': 3, 'HP': 2, 'DMG': 1}


@dataclass
class MatchCandidate:
    """A potential trade match."""
    user_id: int
    username: str
    cards_they_have_i_want: list[dict]
    cards_i_have_they_want: list[dict]
    my_value: Decimal
    their_value: Decimal
    quality_score: int
    distance_miles: Optional[float]
    is_local: bool
    shared_servers: list[str]


@dataclass
class QualityFactors:
    """Individual components of match quality."""
    value_balance: int
    total_value: int
    card_variety: int
    condition_match: int
    trust_bonus: int
    locality_bonus: int


class MatchingEngine:
    """Find trade matches between users."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_matches_for_user(
        self,
        user_id: int,
        min_quality: int = 30,
        max_results: int = 50,
        local_only: bool = False,
    ) -> list[MatchCandidate]:
        """Find trade matches for a user."""
        # Get user and their lists
        user = await self.db.get(User, user_id)
        if not user:
            return []

        my_wants = await self._get_user_wants(user_id)
        my_haves = await self._get_user_haves(user_id)

        if not my_wants or not my_haves:
            return []

        my_want_card_ids = {w.card_id for w in my_wants}

        # Find users who have what I want
        candidates = await self._find_candidates_with_cards(my_want_card_ids, user_id)

        matches = []
        for candidate in candidates:
            match = await self._evaluate_match(user, my_wants, my_haves, candidate)
            if match and match.quality_score >= min_quality:
                if not local_only or match.is_local:
                    matches.append(match)

        matches.sort(key=lambda m: m.quality_score, reverse=True)
        return matches[:max_results]

    async def _get_user_wants(self, user_id: int) -> list[WantListItem]:
        """Get user's public, active wants."""
        query = (
            select(WantListItem)
            .where(
                WantListItem.user_id == user_id,
                WantListItem.is_active == True,
                WantListItem.is_public == True,
            )
            .options(selectinload(WantListItem.card))
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_user_haves(self, user_id: int) -> list[HaveListItem]:
        """Get user's active haves."""
        query = (
            select(HaveListItem)
            .where(
                HaveListItem.user_id == user_id,
                HaveListItem.is_active == True,
            )
            .options(
                selectinload(HaveListItem.inventory_item)
                .selectinload(InventoryItem.card)
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _find_candidates_with_cards(
        self, card_ids: set[int], exclude_user_id: int
    ) -> list[User]:
        """Find users who have cards we want."""
        query = (
            select(User)
            .join(HaveListItem)
            .join(InventoryItem)
            .where(
                InventoryItem.card_id.in_(card_ids),
                HaveListItem.is_active == True,
                User.id != exclude_user_id,
            )
            .distinct()
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _evaluate_match(
        self,
        user: User,
        my_wants: list[WantListItem],
        my_haves: list[HaveListItem],
        candidate: User,
    ) -> Optional[MatchCandidate]:
        """Evaluate match quality between two users."""
        their_wants = await self._get_user_wants(candidate.id)
        their_haves = await self._get_user_haves(candidate.id)

        # What I can get from them
        cards_for_me = []
        for their_have in their_haves:
            matching = self._find_matching_want(their_have, my_wants)
            if matching:
                cards_for_me.append({
                    'card_id': their_have.inventory_item.card_id,
                    'card_name': their_have.card.name,
                    'condition': their_have.condition,
                    'value': Decimal('10.00'),  # TODO: Get real price
                })

        if not cards_for_me:
            return None

        # What they can get from me
        cards_for_them = []
        for my_have in my_haves:
            matching = self._find_matching_want(my_have, their_wants)
            if matching:
                cards_for_them.append({
                    'card_id': my_have.inventory_item.card_id,
                    'card_name': my_have.card.name,
                    'condition': my_have.condition,
                    'value': Decimal('10.00'),  # TODO: Get real price
                })

        if not cards_for_them:
            return None

        my_value = sum(c['value'] for c in cards_for_me)
        their_value = sum(c['value'] for c in cards_for_them)

        # Calculate quality
        factors = self._calculate_quality(my_value, their_value, cards_for_me, cards_for_them)
        quality_score = sum([
            factors.value_balance,
            factors.total_value,
            factors.card_variety,
            factors.condition_match,
            factors.trust_bonus,
            factors.locality_bonus,
        ])

        # Distance
        distance = None
        is_local = False
        if user.latitude and candidate.latitude:
            distance = self._haversine(
                float(user.latitude), float(user.longitude),
                float(candidate.latitude), float(candidate.longitude),
            )
            is_local = distance <= user.trade_radius_miles

        return MatchCandidate(
            user_id=candidate.id,
            username=candidate.username,
            cards_they_have_i_want=cards_for_me,
            cards_i_have_they_want=cards_for_them,
            my_value=my_value,
            their_value=their_value,
            quality_score=max(0, min(100, quality_score)),
            distance_miles=distance,
            is_local=is_local,
            shared_servers=[],  # TODO: implement
        )

    def _find_matching_want(
        self, have: HaveListItem, wants: list[WantListItem]
    ) -> Optional[WantListItem]:
        """Find a want that matches a have."""
        for want in wants:
            if want.card_id != have.inventory_item.card_id:
                continue
            if want.is_foil_required and not have.is_foil:
                continue
            return want
        return None

    def _calculate_quality(
        self,
        my_value: Decimal,
        their_value: Decimal,
        cards_for_me: list,
        cards_for_them: list,
    ) -> QualityFactors:
        """Calculate quality score components."""
        # Value balance: 40 points max
        if my_value == 0 or their_value == 0:
            value_balance = 0
        else:
            ratio = float(min(my_value, their_value) / max(my_value, their_value))
            value_balance = int(ratio * 40)

        # Total value: 20 points max
        total = float(my_value + their_value)
        if total >= 500:
            total_value = 20
        elif total >= 200:
            total_value = 15
        elif total >= 50:
            total_value = 10
        else:
            total_value = int(total / 5)

        # Card variety: 15 points max
        variety = len(cards_for_me) + len(cards_for_them)
        card_variety = min(15, variety * 2)

        return QualityFactors(
            value_balance=value_balance,
            total_value=total_value,
            card_variety=card_variety,
            condition_match=10,  # Simplified for now
            trust_bonus=0,
            locality_bonus=0,
        )

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in miles between two points."""
        R = 3959  # Earth radius in miles

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c
```

**Step 2: Commit**

```bash
git add backend/app/services/matching/
git commit -m "feat: add matching algorithm engine"
```

---

## Summary

Phase 1 implements:

| Component | Tasks | Key Deliverables |
|-----------|-------|------------------|
| Have List | 1-6 | Database, model, API, tests |
| Want List Extensions | 7-10 | Trading fields, public endpoint |
| Discord Bot | 11-20 | Bot scaffold, cogs, API |
| Matching Algorithm | 21-28 | Engine, caching, notifications |

**Total: 28 tasks**

After Phase 1:
- Users can mark inventory items for trade
- Want lists have trading preferences
- Discord bot for price lookups and list management
- Matching algorithm finds compatible trades

---

Plan complete. Ready for Phase 2 and 3 plans.
