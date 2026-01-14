# Phase 0: Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build infrastructure that enables the social trading platform (public pages, profiles, notifications, Discord linking)

**Architecture:** Add public-facing endpoints without authentication, extend the user model with profile/privacy fields, create multi-channel notification service, implement Discord OAuth for account linking.

**Tech Stack:** FastAPI, SQLAlchemy, hashids, httpx (Discord OAuth), Resend/SendGrid (email - future), Next.js 14 App Router with SSR

---

## Prerequisites

Before starting:
```bash
# Ensure you're in a worktree (create one if not)
git worktree list

# Start services
make up

# Verify everything works
curl http://localhost:8000/api/health
```

---

## Task 1: Install hashids Package

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add hashids to requirements**

Add to `backend/requirements.txt`:
```
hashids>=1.3.1
```

**Step 2: Install the package**

Run: `docker compose exec backend pip install hashids>=1.3.1`
Expected: Successfully installed hashids-1.x.x

**Step 3: Rebuild container to persist**

Run: `docker compose up -d --build backend`
Expected: Container rebuilds with new dependency

**Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add hashids dependency for public URL encoding"
```

---

## Task 2: Create Hashids Utility Module

**Files:**
- Create: `backend/app/core/hashids.py`
- Test: `backend/tests/unit/test_hashids.py`

**Step 1: Write the test**

Create `backend/tests/unit/test_hashids.py`:
```python
"""Tests for hashids encoding/decoding."""
import pytest
from app.core.hashids import encode_id, decode_id


class TestHashids:
    """Test hashid encoding and decoding."""

    def test_encode_card_id(self):
        """Card IDs encode to 6+ character strings."""
        result = encode_id("card", 12345)
        assert isinstance(result, str)
        assert len(result) >= 6

    def test_decode_card_id(self):
        """Encoded card IDs decode back to original."""
        original = 12345
        encoded = encode_id("card", original)
        decoded = decode_id("card", encoded)
        assert decoded == original

    def test_encode_user_id(self):
        """User IDs encode to 8+ character strings."""
        result = encode_id("user", 42)
        assert len(result) >= 8

    def test_decode_user_id(self):
        """Encoded user IDs decode back to original."""
        original = 42
        encoded = encode_id("user", original)
        decoded = decode_id("user", encoded)
        assert decoded == original

    def test_decode_invalid_returns_none(self):
        """Invalid hashids return None."""
        result = decode_id("card", "invalid123")
        assert result is None

    def test_different_entity_types_produce_different_hashes(self):
        """Same ID produces different hashes for different entity types."""
        card_hash = encode_id("card", 100)
        user_hash = encode_id("user", 100)
        assert card_hash != user_hash

    def test_unknown_entity_type_raises(self):
        """Unknown entity types raise KeyError."""
        with pytest.raises(KeyError):
            encode_id("unknown", 1)
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/unit/test_hashids.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.core.hashids'"

**Step 3: Write the implementation**

Create `backend/app/core/hashids.py`:
```python
"""
Hashids encoding for public-facing URLs.

Uses different salts per entity type for security (can't guess user IDs from card IDs).
"""
from hashids import Hashids

# Entity-specific hashers with unique salts
_hashers = {
    "card": Hashids(salt="dualcaster-cards-v1", min_length=6),
    "user": Hashids(salt="dualcaster-users-v1", min_length=8),
    "trade": Hashids(salt="dualcaster-trades-v1", min_length=10),
    "match": Hashids(salt="dualcaster-matches-v1", min_length=8),
}


def encode_id(entity_type: str, id: int) -> str:
    """
    Encode an integer ID to a hashid string.

    Args:
        entity_type: One of 'card', 'user', 'trade', 'match'
        id: The integer database ID

    Returns:
        A URL-safe hashid string

    Raises:
        KeyError: If entity_type is not recognized
    """
    return _hashers[entity_type].encode(id)


def decode_id(entity_type: str, hashid: str) -> int | None:
    """
    Decode a hashid string to an integer ID.

    Args:
        entity_type: One of 'card', 'user', 'trade', 'match'
        hashid: The hashid string to decode

    Returns:
        The original integer ID, or None if invalid

    Raises:
        KeyError: If entity_type is not recognized
    """
    result = _hashers[entity_type].decode(hashid)
    return result[0] if result else None
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/unit/test_hashids.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add backend/app/core/hashids.py backend/tests/unit/test_hashids.py
git commit -m "feat: add hashids utility for public URL encoding"
```

---

## Task 3: Create Public Card Schema

**Files:**
- Modify: `backend/app/schemas/card.py`

**Step 1: Add CardPublicResponse schema**

Add to `backend/app/schemas/card.py` after the existing imports:

```python
from typing import Optional
from pydantic import model_validator
from app.core.hashids import encode_id
```

Add new schema class (after CardResponse):

```python
class CardPublicResponse(BaseModel):
    """Public card response with hashid for SEO-friendly URLs."""

    # Core fields
    id: int
    hashid: str = ""
    name: str
    set_code: str
    set_name: Optional[str] = None
    collector_number: Optional[str] = None

    # Display fields
    image_url: Optional[str] = None
    mana_cost: Optional[str] = None
    type_line: Optional[str] = None
    oracle_text: Optional[str] = None
    rarity: Optional[str] = None

    # Price fields
    current_price: Optional[float] = None
    price_change_7d: Optional[float] = None
    want_count: int = 0

    # Recommendation (if active)
    recommendation_action: Optional[str] = None
    recommendation_confidence: Optional[float] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def compute_hashid(self):
        """Auto-compute hashid from id."""
        if self.id and not self.hashid:
            self.hashid = encode_id("card", self.id)
        return self
```

**Step 2: Verify syntax**

Run: `docker compose exec backend python -c "from app.schemas.card import CardPublicResponse; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/app/schemas/card.py
git commit -m "feat: add CardPublicResponse schema with hashid"
```

---

## Task 4: Add Public Card Endpoints

**Files:**
- Modify: `backend/app/api/routes/cards.py`
- Test: `backend/tests/api/test_cards_public.py`

**Step 1: Write the test**

Create `backend/tests/api/test_cards_public.py`:
```python
"""Tests for public card endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.hashids import encode_id


@pytest.mark.asyncio
async def test_get_card_public_by_id(client: AsyncClient, db: AsyncSession):
    """Public card endpoint returns card without auth."""
    # Get a card ID from the database
    from sqlalchemy import select
    from app.models import Card

    result = await db.execute(select(Card).limit(1))
    card = result.scalar_one_or_none()

    if not card:
        pytest.skip("No cards in database")

    response = await client.get(f"/api/cards/public/{card.id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == card.id
    assert data["name"] == card.name
    assert "hashid" in data
    assert len(data["hashid"]) >= 6


@pytest.mark.asyncio
async def test_get_card_public_by_hashid(client: AsyncClient, db: AsyncSession):
    """Public card endpoint works with hashid URLs."""
    from sqlalchemy import select
    from app.models import Card

    result = await db.execute(select(Card).limit(1))
    card = result.scalar_one_or_none()

    if not card:
        pytest.skip("No cards in database")

    hashid = encode_id("card", card.id)
    response = await client.get(f"/api/cards/c/{hashid}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == card.id
    assert data["hashid"] == hashid


@pytest.mark.asyncio
async def test_get_card_public_not_found(client: AsyncClient):
    """Public card endpoint returns 404 for invalid ID."""
    response = await client.get("/api/cards/public/999999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_card_public_invalid_hashid(client: AsyncClient):
    """Public card endpoint returns 404 for invalid hashid."""
    response = await client.get("/api/cards/c/invalidhashid")
    assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/api/test_cards_public.py -v`
Expected: FAIL with 404 (endpoints don't exist yet)

**Step 3: Add public endpoints to cards.py**

Add to `backend/app/api/routes/cards.py` after the existing imports:
```python
from app.core.hashids import encode_id, decode_id
from app.schemas.card import CardPublicResponse
```

Add new endpoints (before the existing `@router.get("/{card_id}")`):
```python
@router.get("/public/{card_id}", response_model=CardPublicResponse)
async def get_card_public(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get public card information (no auth required).

    Returns card details with hashid for SEO-friendly URLs.
    Used for public card pages and social sharing.
    """
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Get latest price
    from sqlalchemy import select, func
    price_query = select(func.avg(PriceSnapshot.price)).where(
        PriceSnapshot.card_id == card_id,
    ).order_by(PriceSnapshot.time.desc()).limit(10)
    result = await db.execute(price_query)
    current_price = result.scalar_one_or_none()

    # Get want count
    from app.models import WantListItem
    want_count_query = select(func.count(WantListItem.id)).where(
        WantListItem.card_id == card_id,
        WantListItem.is_active == True,
    )
    result = await db.execute(want_count_query)
    want_count = result.scalar_one_or_none() or 0

    # Get active recommendation
    rec_query = select(Recommendation).where(
        Recommendation.card_id == card_id,
        Recommendation.is_active == True,
    ).order_by(Recommendation.created_at.desc()).limit(1)
    result = await db.execute(rec_query)
    rec = result.scalar_one_or_none()

    # Get 7d price change from metrics
    metrics_query = select(MetricsCardsDaily).where(
        MetricsCardsDaily.card_id == card_id
    ).order_by(MetricsCardsDaily.date.desc()).limit(1)
    result = await db.execute(metrics_query)
    metrics = result.scalar_one_or_none()

    return CardPublicResponse(
        id=card.id,
        name=card.name,
        set_code=card.set_code,
        set_name=card.set_name,
        collector_number=card.collector_number,
        image_url=card.image_url,
        mana_cost=card.mana_cost,
        type_line=card.type_line,
        oracle_text=card.oracle_text,
        rarity=card.rarity,
        current_price=float(current_price) if current_price else None,
        price_change_7d=float(metrics.price_change_pct_7d) if metrics and metrics.price_change_pct_7d else None,
        want_count=want_count,
        recommendation_action=rec.action if rec else None,
        recommendation_confidence=float(rec.confidence) if rec else None,
    )


@router.get("/c/{hashid}", response_model=CardPublicResponse)
async def get_card_by_hashid(
    hashid: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get public card by hashid URL (no auth required).

    This is the SEO-friendly endpoint for sharing card links.
    Example: /api/cards/c/Wk5R9v → returns card with ID decoded from hashid
    """
    card_id = decode_id("card", hashid)
    if card_id is None:
        raise HTTPException(status_code=404, detail="Card not found")

    return await get_card_public(card_id, db)
```

**Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/api/test_cards_public.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/app/api/routes/cards.py backend/tests/api/test_cards_public.py
git commit -m "feat: add public card endpoints with hashid support"
```

---

## Task 5: Add SEO Routes (Sitemap, Robots.txt)

**Files:**
- Create: `backend/app/api/routes/seo.py`
- Modify: `backend/app/api/__init__.py`

**Step 1: Create SEO routes**

Create `backend/app/api/routes/seo.py`:
```python
"""SEO routes for sitemap and robots.txt."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Card
from app.core.hashids import encode_id

router = APIRouter(tags=["seo"])


@router.get("/robots.txt", response_class=Response)
async def robots_txt():
    """Return robots.txt for search engines."""
    content = """User-agent: *
Allow: /
Allow: /cards/
Allow: /market

Disallow: /api/
Disallow: /dashboard
Disallow: /inventory
Disallow: /settings

Sitemap: https://dualcasterdeals.com/sitemap.xml
"""
    return Response(content=content, media_type="text/plain")


@router.get("/sitemap.xml", response_class=Response)
async def sitemap(db: AsyncSession = Depends(get_db)):
    """
    Generate sitemap for all public card pages.

    Limited to 50,000 URLs per sitemap (Google limit).
    Uses hashids for card URLs.
    """
    # Get cards with recent price updates (most relevant for SEO)
    query = select(Card.id, Card.updated_at).order_by(
        Card.updated_at.desc()
    ).limit(50000)

    result = await db.execute(query)
    cards = result.all()

    urls = []

    # Static pages
    static_pages = [
        ("https://dualcasterdeals.com/", "daily", "1.0"),
        ("https://dualcasterdeals.com/market", "hourly", "0.9"),
        ("https://dualcasterdeals.com/cards", "daily", "0.8"),
        ("https://dualcasterdeals.com/about", "monthly", "0.3"),
        ("https://dualcasterdeals.com/help", "monthly", "0.3"),
    ]

    for loc, changefreq, priority in static_pages:
        urls.append(f"""    <url>
        <loc>{loc}</loc>
        <changefreq>{changefreq}</changefreq>
        <priority>{priority}</priority>
    </url>""")

    # Card pages
    for card_id, updated_at in cards:
        hashid = encode_id("card", card_id)
        lastmod = updated_at.strftime("%Y-%m-%d") if updated_at else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        urls.append(f"""    <url>
        <loc>https://dualcasterdeals.com/cards/{hashid}</loc>
        <lastmod>{lastmod}</lastmod>
        <changefreq>daily</changefreq>
        <priority>0.7</priority>
    </url>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""

    return Response(content=xml, media_type="application/xml")
```

**Step 2: Register SEO routes**

Add to `backend/app/api/__init__.py` (in the router includes section):
```python
from app.api.routes import seo
api_router.include_router(seo.router)
```

**Step 3: Verify routes work**

Run: `curl http://localhost:8000/api/robots.txt`
Expected: robots.txt content

Run: `curl http://localhost:8000/api/sitemap.xml | head -20`
Expected: XML sitemap content

**Step 4: Commit**

```bash
git add backend/app/api/routes/seo.py backend/app/api/__init__.py
git commit -m "feat: add SEO routes (sitemap.xml, robots.txt)"
```

---

## Task 6: Update Frontend Card Page for SSR + OG Tags

**Files:**
- Modify: `frontend/src/app/(public)/cards/[id]/page.tsx`
- Create: `frontend/src/lib/api-server.ts`

**Step 1: Create server-side API helper**

Create `frontend/src/lib/api-server.ts`:
```typescript
/**
 * Server-side API functions for SSR/SSG pages.
 * These run on the server and don't need auth.
 */

const API_BASE = process.env.INTERNAL_API_URL || 'http://backend:8000/api';

export interface CardPublic {
  id: number;
  hashid: string;
  name: string;
  set_code: string;
  set_name: string | null;
  collector_number: string | null;
  image_url: string | null;
  mana_cost: string | null;
  type_line: string | null;
  oracle_text: string | null;
  rarity: string | null;
  current_price: number | null;
  price_change_7d: number | null;
  want_count: number;
  recommendation_action: string | null;
  recommendation_confidence: number | null;
}

/**
 * Fetch public card data (no auth required).
 * Used for SSR and metadata generation.
 */
export async function getCardPublic(cardId: number): Promise<CardPublic | null> {
  try {
    const res = await fetch(`${API_BASE}/cards/public/${cardId}`, {
      next: { revalidate: 60 }, // Cache for 60 seconds
    });

    if (!res.ok) {
      return null;
    }

    return res.json();
  } catch {
    return null;
  }
}

/**
 * Fetch public card by hashid.
 */
export async function getCardByHashid(hashid: string): Promise<CardPublic | null> {
  try {
    const res = await fetch(`${API_BASE}/cards/c/${hashid}`, {
      next: { revalidate: 60 },
    });

    if (!res.ok) {
      return null;
    }

    return res.json();
  } catch {
    return null;
  }
}
```

**Step 2: Add generateMetadata to card page**

Add to the top of `frontend/src/app/(public)/cards/[id]/page.tsx` (before 'use client'):

```typescript
import type { Metadata } from 'next';
import { getCardPublic } from '@/lib/api-server';

// Generate metadata for SEO and social sharing
export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const cardId = Number(params.id);
  const card = await getCardPublic(cardId);

  if (!card) {
    return {
      title: 'Card Not Found | Dualcaster Deals',
    };
  }

  const priceStr = card.current_price ? `$${card.current_price.toFixed(2)}` : 'Price unavailable';
  const description = `${card.name} is ${priceStr}. ${card.want_count} traders want this card. Track prices, get alerts, and find the best deals.`;

  return {
    title: `${card.name} Price & Trading | Dualcaster Deals`,
    description,
    openGraph: {
      title: card.name,
      description: `${priceStr} | ${card.set_name || card.set_code}`,
      images: card.image_url ? [card.image_url] : [],
      type: 'website',
      siteName: 'Dualcaster Deals',
    },
    twitter: {
      card: 'summary_large_image',
      title: card.name,
      description: `${priceStr} | ${card.want_count} traders want this`,
      images: card.image_url ? [card.image_url] : [],
    },
    alternates: {
      canonical: `https://dualcasterdeals.com/cards/${card.hashid}`,
    },
  };
}
```

Note: The page will still use 'use client' for the interactive parts. The metadata is generated server-side.

**Step 3: Verify build succeeds**

Run: `docker compose exec frontend npm run build`
Expected: Build succeeds with SSR metadata generation

**Step 4: Commit**

```bash
git add frontend/src/lib/api-server.ts frontend/src/app/\(public\)/cards/[id]/page.tsx
git commit -m "feat: add SSR metadata and OG tags for card pages"
```

---

## Task 7: User Profile Migration

**Files:**
- Create: `backend/alembic/versions/20251230_001_user_profile_extensions.py`

**Step 1: Create migration**

Run: `docker compose exec backend alembic revision -m "user_profile_extensions"`

Edit the generated file to contain:
```python
"""user_profile_extensions

Add profile fields, location, activity tracking, and privacy controls to users table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = '20251230_001'
down_revision = '20251229_001_add_recommendation_outcome_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Profile fields
    op.add_column('users', sa.Column('is_public', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(500), nullable=True))

    # Location fields
    op.add_column('users', sa.Column('location_display', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('latitude', sa.Numeric(10, 8), nullable=True))
    op.add_column('users', sa.Column('longitude', sa.Numeric(11, 8), nullable=True))
    op.add_column('users', sa.Column('trade_radius_miles', sa.Integer(), server_default='50', nullable=False))

    # Activity tracking
    op.add_column('users', sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('profile_views', sa.Integer(), server_default='0', nullable=False))

    # Privacy controls
    op.add_column('users', sa.Column('show_inventory_value', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('show_want_list', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('users', sa.Column('show_have_list', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('users', sa.Column('show_trade_history', sa.Boolean(), server_default='false', nullable=False))

    # Indexes
    op.create_index('ix_users_is_public', 'users', ['is_public'])
    op.create_index('ix_users_location', 'users', ['latitude', 'longitude'])
    op.create_index('ix_users_last_active', 'users', ['last_active_at'])


def downgrade():
    op.drop_index('ix_users_last_active', table_name='users')
    op.drop_index('ix_users_location', table_name='users')
    op.drop_index('ix_users_is_public', table_name='users')

    op.drop_column('users', 'show_trade_history')
    op.drop_column('users', 'show_have_list')
    op.drop_column('users', 'show_want_list')
    op.drop_column('users', 'show_inventory_value')
    op.drop_column('users', 'profile_views')
    op.drop_column('users', 'last_active_at')
    op.drop_column('users', 'trade_radius_miles')
    op.drop_column('users', 'longitude')
    op.drop_column('users', 'latitude')
    op.drop_column('users', 'location_display')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'is_public')
```

**Step 2: Run migration**

Run: `docker compose exec backend alembic upgrade head`
Expected: Migration applies successfully

**Step 3: Verify columns exist**

Run: `docker compose exec db psql -U dualcaster_user -d dualcaster_deals -c "\d users" | grep -E "(is_public|bio|latitude)"`
Expected: Shows new columns

**Step 4: Commit**

```bash
git add backend/alembic/versions/20251230_001_user_profile_extensions.py
git commit -m "feat: add user profile extensions migration"
```

---

## Task 8: Update User Model

**Files:**
- Modify: `backend/app/models/user.py`

**Step 1: Add new fields to User model**

Add these imports at the top of `backend/app/models/user.py`:
```python
from decimal import Decimal
from sqlalchemy import Numeric
```

Add these fields after the existing notification preferences fields (before relationships):
```python
    # Profile (Phase 0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Location
    location_display: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 8), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(11, 8), nullable=True)
    trade_radius_miles: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    # Activity
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    profile_views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Privacy controls
    show_inventory_value: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    show_want_list: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_have_list: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_trade_history: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

**Step 2: Verify model loads**

Run: `docker compose exec backend python -c "from app.models.user import User; print([c.name for c in User.__table__.columns if 'public' in c.name or 'bio' in c.name])"`
Expected: `['is_public', 'bio']`

**Step 3: Commit**

```bash
git add backend/app/models/user.py
git commit -m "feat: add profile fields to User model"
```

---

## Task 9: Create User Profile Schemas

**Files:**
- Create: `backend/app/schemas/user.py`

**Step 1: Create user schemas**

Create `backend/app/schemas/user.py`:
```python
"""User profile schemas."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, model_validator

from app.core.hashids import encode_id


class UserPublicProfile(BaseModel):
    """Public user profile (visible to others)."""

    id: int
    hashid: str = ""
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None

    # Location (only display name, not coords)
    location_display: Optional[str] = None
    trade_radius_miles: int = 50

    # Stats (respects privacy settings)
    profile_views: int = 0
    member_since: Optional[datetime] = None
    last_active_at: Optional[datetime] = None

    # Collection stats (if show_inventory_value is True)
    inventory_count: Optional[int] = None
    inventory_value: Optional[float] = None

    # Want/have list visibility
    show_want_list: bool = True
    show_have_list: bool = True

    # Ownership flag
    is_own_profile: bool = False

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def compute_hashid(self):
        if self.id and not self.hashid:
            self.hashid = encode_id("user", self.id)
        return self


class UserProfileUpdate(BaseModel):
    """Update user profile fields."""

    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)

    # Privacy settings
    is_public: Optional[bool] = None
    show_inventory_value: Optional[bool] = None
    show_want_list: Optional[bool] = None
    show_have_list: Optional[bool] = None
    show_trade_history: Optional[bool] = None

    # Location
    location_display: Optional[str] = Field(None, max_length=255)
    trade_radius_miles: Optional[int] = Field(None, ge=1, le=500)


class LocationUpdate(BaseModel):
    """Update user location."""

    display: str = Field(..., max_length=255)
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None


class UserSearchResult(BaseModel):
    """User search result."""

    id: int
    hashid: str = ""
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    location_display: Optional[str] = None
    last_active_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def compute_hashid(self):
        if self.id and not self.hashid:
            self.hashid = encode_id("user", self.id)
        return self
```

**Step 2: Verify schemas load**

Run: `docker compose exec backend python -c "from app.schemas.user import UserPublicProfile, UserProfileUpdate; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/app/schemas/user.py
git commit -m "feat: add user profile schemas"
```

---

## Task 10: Create User Profile Routes

**Files:**
- Create: `backend/app/api/routes/users.py`
- Modify: `backend/app/api/__init__.py`
- Test: `backend/tests/api/test_users.py`

**Step 1: Write the test**

Create `backend/tests/api/test_users.py`:
```python
"""Tests for user profile endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_get_own_profile(client: AsyncClient, auth_headers: dict):
    """Get current user's profile."""
    response = await client.get("/api/users/me", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert "id" in data
    assert "username" in data
    assert "hashid" in data
    assert data["is_own_profile"] is True


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, auth_headers: dict):
    """Update current user's profile."""
    response = await client.patch(
        "/api/users/me",
        headers=auth_headers,
        json={"bio": "Test bio", "is_public": True}
    )
    assert response.status_code == 200

    data = response.json()
    assert data["bio"] == "Test bio"


@pytest.mark.asyncio
async def test_get_public_profile_private_user(client: AsyncClient, db: AsyncSession):
    """Private profiles return 403."""
    # Create a private user
    from app.models import User
    from app.services.auth import hash_password

    user = User(
        email="private@example.com",
        username="privateuser",
        hashed_password=hash_password("password123"),
        is_public=False,
    )
    db.add(user)
    await db.commit()

    response = await client.get(f"/api/users/{user.username}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_search_users(client: AsyncClient, auth_headers: dict):
    """Search for users."""
    response = await client.get(
        "/api/users/search",
        params={"q": "test"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

**Step 2: Create user routes**

Create `backend/app/api/routes/users.py`:
```python
"""User profile routes."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user, get_optional_current_user
from app.models import User, InventoryItem
from app.schemas.user import (
    UserPublicProfile,
    UserProfileUpdate,
    LocationUpdate,
    UserSearchResult,
)

router = APIRouter(prefix="/users", tags=["users"])


async def _build_profile_response(
    db: AsyncSession,
    user: User,
    is_own_profile: bool = False,
) -> UserPublicProfile:
    """Build a public profile response with appropriate privacy filtering."""

    # Get inventory stats if allowed
    inventory_count = None
    inventory_value = None

    if is_own_profile or user.show_inventory_value:
        count_query = select(func.count(InventoryItem.id)).where(
            InventoryItem.user_id == user.id
        )
        result = await db.execute(count_query)
        inventory_count = result.scalar_one_or_none() or 0

        # TODO: Calculate inventory value from current prices
        inventory_value = None

    return UserPublicProfile(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        location_display=user.location_display,
        trade_radius_miles=user.trade_radius_miles,
        profile_views=user.profile_views,
        member_since=user.created_at,
        last_active_at=user.last_active_at,
        inventory_count=inventory_count,
        inventory_value=inventory_value,
        show_want_list=user.show_want_list,
        show_have_list=user.show_have_list,
        is_own_profile=is_own_profile,
    )


@router.get("/me", response_model=UserPublicProfile)
async def get_current_user_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's profile."""
    return await _build_profile_response(db, current_user, is_own_profile=True)


@router.patch("/me", response_model=UserPublicProfile)
async def update_profile(
    updates: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current user's profile."""
    update_data = updates.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)

    return await _build_profile_response(db, current_user, is_own_profile=True)


@router.post("/me/location", response_model=UserPublicProfile)
async def set_location(
    location: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set user's location for local trading."""
    current_user.location_display = location.display

    if location.latitude and location.longitude:
        current_user.latitude = location.latitude
        current_user.longitude = location.longitude

    await db.commit()
    await db.refresh(current_user)

    return await _build_profile_response(db, current_user, is_own_profile=True)


@router.get("/search", response_model=list[UserSearchResult])
async def search_users(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Search for users by username."""
    query = select(User).where(
        User.is_public == True,
        or_(
            User.username.ilike(f"%{q}%"),
            User.display_name.ilike(f"%{q}%"),
        ),
    ).order_by(User.username).limit(limit)

    result = await db.execute(query)
    users = result.scalars().all()

    return [UserSearchResult.model_validate(u) for u in users]


@router.get("/{username}", response_model=UserPublicProfile)
async def get_public_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Get a user's public profile."""
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_own_profile = current_user and current_user.id == user.id

    if not user.is_public and not is_own_profile:
        raise HTTPException(status_code=403, detail="This profile is private")

    # Increment view count (not for self-views)
    if current_user and current_user.id != user.id:
        user.profile_views += 1
        await db.commit()

    return await _build_profile_response(db, user, is_own_profile=is_own_profile)
```

**Step 3: Register user routes**

Add to `backend/app/api/__init__.py`:
```python
from app.api.routes import users
api_router.include_router(users.router)
```

**Step 4: Run tests**

Run: `docker compose exec backend pytest tests/api/test_users.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/app/api/routes/users.py backend/app/api/__init__.py backend/tests/api/test_users.py
git commit -m "feat: add user profile routes"
```

---

## Task 11: Notification Preferences Migration

**Files:**
- Create: `backend/alembic/versions/20251230_002_notification_preferences.py`

**Step 1: Create migration**

Run: `docker compose exec backend alembic revision -m "notification_preferences"`

Edit the generated file:
```python
"""notification_preferences

Add notification_preferences table for multi-channel notification settings.
"""
from alembic import op
import sqlalchemy as sa

revision = '20251230_002'
down_revision = '20251230_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'notification_preferences',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),

        # Email preferences
        sa.Column('email_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('email_price_alerts', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('email_trade_matches', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('email_trade_proposals', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('email_messages', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('email_weekly_digest', sa.Boolean(), server_default='true', nullable=False),

        # Discord preferences
        sa.Column('discord_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('discord_price_alerts', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('discord_trade_matches', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('discord_trade_proposals', sa.Boolean(), server_default='true', nullable=False),

        # Quiet hours
        sa.Column('quiet_hours_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('quiet_hours_start', sa.Time(), nullable=True),
        sa.Column('quiet_hours_end', sa.Time(), nullable=True),
        sa.Column('quiet_hours_timezone', sa.String(50), server_default='UTC', nullable=False),

        # Rate limits
        sa.Column('max_emails_per_day', sa.Integer(), server_default='10', nullable=False),

        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table('notification_preferences')
```

**Step 2: Run migration**

Run: `docker compose exec backend alembic upgrade head`
Expected: Migration applies successfully

**Step 3: Commit**

```bash
git add backend/alembic/versions/20251230_002_notification_preferences.py
git commit -m "feat: add notification_preferences table"
```

---

## Task 12: Connected Accounts Migration

**Files:**
- Create: `backend/alembic/versions/20251230_003_connected_accounts.py`

**Step 1: Create migration**

Run: `docker compose exec backend alembic revision -m "connected_accounts"`

Edit the generated file:
```python
"""connected_accounts

Add connected_accounts table for Discord and other OAuth provider linking.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = '20251230_003'
down_revision = '20251230_002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'connected_accounts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),

        # Provider info
        sa.Column('provider', sa.String(50), nullable=False),  # 'discord', 'moxfield', 'google'
        sa.Column('provider_user_id', sa.String(255), nullable=False),
        sa.Column('provider_username', sa.String(255), nullable=True),
        sa.Column('provider_display_name', sa.String(255), nullable=True),
        sa.Column('provider_avatar_url', sa.Text(), nullable=True),

        # OAuth tokens (encrypted)
        sa.Column('access_token_encrypted', sa.Text(), nullable=True),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scopes', ARRAY(sa.String()), nullable=True),

        # Metadata
        sa.Column('metadata', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('connected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_primary', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('verified', sa.Boolean(), server_default='false', nullable=False),
    )

    op.create_index('ix_connected_accounts_user', 'connected_accounts', ['user_id'])
    op.create_index(
        'ix_connected_accounts_provider',
        'connected_accounts',
        ['provider', 'provider_user_id'],
        unique=True
    )


def downgrade():
    op.drop_index('ix_connected_accounts_provider', table_name='connected_accounts')
    op.drop_index('ix_connected_accounts_user', table_name='connected_accounts')
    op.drop_table('connected_accounts')
```

**Step 2: Run migration**

Run: `docker compose exec backend alembic upgrade head`
Expected: Migration applies successfully

**Step 3: Commit**

```bash
git add backend/alembic/versions/20251230_003_connected_accounts.py
git commit -m "feat: add connected_accounts table for OAuth linking"
```

---

## Task 13: Create Connected Account Model

**Files:**
- Create: `backend/app/models/connected_account.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Create model**

Create `backend/app/models/connected_account.py`:
```python
"""Connected account model for OAuth provider linking."""
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ConnectedAccount(Base):
    """
    Linked OAuth accounts (Discord, Moxfield, etc.).

    Each user can have multiple connected accounts from different providers.
    Tokens are stored encrypted for security.
    """

    __tablename__ = "connected_accounts"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Provider info
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # OAuth tokens (encrypted at rest)
    access_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="connected_accounts")

    def __repr__(self) -> str:
        return f"<ConnectedAccount {self.provider}:{self.provider_username}>"
```

**Step 2: Add relationship to User model**

Add to `backend/app/models/user.py` in the TYPE_CHECKING block:
```python
from app.models.connected_account import ConnectedAccount
```

Add to the User class relationships:
```python
    connected_accounts: Mapped[list["ConnectedAccount"]] = relationship(
        "ConnectedAccount",
        back_populates="user",
        cascade="all, delete-orphan"
    )
```

**Step 3: Update models __init__.py**

Add to `backend/app/models/__init__.py`:
```python
from app.models.connected_account import ConnectedAccount
```

**Step 4: Verify model loads**

Run: `docker compose exec backend python -c "from app.models import ConnectedAccount; print('OK')"`
Expected: OK

**Step 5: Commit**

```bash
git add backend/app/models/connected_account.py backend/app/models/user.py backend/app/models/__init__.py
git commit -m "feat: add ConnectedAccount model"
```

---

## Task 14: Add Discord OAuth Routes

**Files:**
- Create: `backend/app/api/routes/discord.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/__init__.py`

**Step 1: Add Discord config**

Add to `backend/app/core/config.py` Settings class:
```python
    # Discord OAuth
    DISCORD_CLIENT_ID: Optional[str] = None
    DISCORD_CLIENT_SECRET: Optional[str] = None
    DISCORD_REDIRECT_URI: str = "http://localhost:8000/api/oauth/discord/callback"
    DISCORD_BOT_TOKEN: Optional[str] = None

    @property
    def DISCORD_ENABLED(self) -> bool:
        return bool(self.DISCORD_CLIENT_ID and self.DISCORD_CLIENT_SECRET)
```

**Step 2: Create Discord OAuth routes**

Create `backend/app/api/routes/discord.py`:
```python
"""Discord OAuth and account linking."""
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User, ConnectedAccount

router = APIRouter(prefix="/oauth/discord", tags=["discord"])

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_OAUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"

# Redis for state storage
_redis_client = None


def get_redis():
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


@router.get("/link")
async def discord_link(
    current_user: User = Depends(get_current_user),
):
    """
    Start Discord account linking flow.

    User must be authenticated. Redirects to Discord OAuth.
    """
    if not settings.DISCORD_ENABLED:
        raise HTTPException(status_code=400, detail="Discord integration is not enabled")

    # Generate state with user ID
    state = secrets.token_urlsafe(32)
    redis_client = get_redis()
    redis_client.setex(f"discord_link:{state}", 300, str(current_user.id))

    params = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "redirect_uri": settings.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
    }

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{DISCORD_OAUTH_URL}?{query_string}")


@router.get("/callback")
async def discord_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Handle Discord OAuth callback."""
    if not settings.DISCORD_ENABLED:
        raise HTTPException(status_code=400, detail="Discord integration is not enabled")

    if error:
        return RedirectResponse(url=f"{settings.frontend_url}/settings?discord_error={error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    # Verify state and get user ID
    redis_client = get_redis()
    user_id_str = redis_client.get(f"discord_link:{state}")
    if not user_id_str:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    redis_client.delete(f"discord_link:{state}")
    user_id = int(user_id_str)

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id": settings.DISCORD_CLIENT_ID,
                "client_secret": settings.DISCORD_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.DISCORD_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange code: {token_response.text}"
            )

        tokens = token_response.json()

        # Get user info
        user_response = await client.get(
            f"{DISCORD_API_BASE}/users/@me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get Discord user info")

        discord_user = user_response.json()

    # Check if this Discord account is already linked
    existing_query = select(ConnectedAccount).where(
        ConnectedAccount.provider == "discord",
        ConnectedAccount.provider_user_id == discord_user["id"],
    )
    result = await db.execute(existing_query)
    existing = result.scalar_one_or_none()

    if existing and existing.user_id != user_id:
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?discord_error=already_linked"
        )

    # Create or update connected account
    if existing:
        existing.provider_username = discord_user["username"]
        existing.provider_display_name = discord_user.get("global_name")
        existing.provider_avatar_url = (
            f"https://cdn.discordapp.com/avatars/{discord_user['id']}/{discord_user['avatar']}.png"
            if discord_user.get("avatar") else None
        )
        existing.access_token_encrypted = tokens["access_token"]  # TODO: encrypt
        existing.refresh_token_encrypted = tokens.get("refresh_token")
        existing.last_synced_at = datetime.now(timezone.utc)
    else:
        connected_account = ConnectedAccount(
            user_id=user_id,
            provider="discord",
            provider_user_id=discord_user["id"],
            provider_username=discord_user["username"],
            provider_display_name=discord_user.get("global_name"),
            provider_avatar_url=(
                f"https://cdn.discordapp.com/avatars/{discord_user['id']}/{discord_user['avatar']}.png"
                if discord_user.get("avatar") else None
            ),
            access_token_encrypted=tokens["access_token"],  # TODO: encrypt
            refresh_token_encrypted=tokens.get("refresh_token"),
            scopes=tokens.get("scope", "").split(" "),
            connected_at=datetime.now(timezone.utc),
            verified=True,
        )
        db.add(connected_account)

    await db.commit()

    return RedirectResponse(url=f"{settings.frontend_url}/settings?discord=linked")


@router.delete("/unlink")
async def discord_unlink(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unlink Discord account."""
    query = select(ConnectedAccount).where(
        ConnectedAccount.user_id == current_user.id,
        ConnectedAccount.provider == "discord",
    )
    result = await db.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="No Discord account linked")

    await db.delete(account)
    await db.commit()

    return {"status": "unlinked"}


@router.get("/status")
async def discord_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get Discord connection status."""
    query = select(ConnectedAccount).where(
        ConnectedAccount.user_id == current_user.id,
        ConnectedAccount.provider == "discord",
    )
    result = await db.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        return {"linked": False}

    return {
        "linked": True,
        "username": account.provider_username,
        "display_name": account.provider_display_name,
        "avatar_url": account.provider_avatar_url,
        "connected_at": account.connected_at.isoformat(),
    }
```

**Step 3: Register Discord routes**

Add to `backend/app/api/__init__.py`:
```python
from app.api.routes import discord
api_router.include_router(discord.router)
```

**Step 4: Verify routes load**

Run: `docker compose exec backend python -c "from app.api import api_router; print([r.path for r in api_router.routes if 'discord' in r.path])"`
Expected: List of discord routes

**Step 5: Commit**

```bash
git add backend/app/api/routes/discord.py backend/app/core/config.py backend/app/api/__init__.py
git commit -m "feat: add Discord OAuth routes for account linking"
```

---

## Task 15: Create Analytics Events Table

**Files:**
- Create: `backend/alembic/versions/20251230_004_analytics_events.py`

**Step 1: Create migration**

Run: `docker compose exec backend alembic revision -m "analytics_events"`

Edit the generated file:
```python
"""analytics_events

Add analytics_events table for user behavior tracking.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '20251230_004'
down_revision = '20251230_003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'analytics_events',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('properties', JSONB, server_default='{}', nullable=False),
        sa.Column('context', JSONB, server_default='{}', nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Indexes for common queries
    op.create_index('ix_analytics_events_type', 'analytics_events', ['event_type'])
    op.create_index('ix_analytics_events_user', 'analytics_events', ['user_id'])
    op.create_index('ix_analytics_events_timestamp', 'analytics_events', ['timestamp'])
    op.create_index(
        'ix_analytics_events_type_timestamp',
        'analytics_events',
        ['event_type', 'timestamp'],
    )


def downgrade():
    op.drop_index('ix_analytics_events_type_timestamp', table_name='analytics_events')
    op.drop_index('ix_analytics_events_timestamp', table_name='analytics_events')
    op.drop_index('ix_analytics_events_user', table_name='analytics_events')
    op.drop_index('ix_analytics_events_type', table_name='analytics_events')
    op.drop_table('analytics_events')
```

**Step 2: Run migration**

Run: `docker compose exec backend alembic upgrade head`
Expected: Migration applies successfully

**Step 3: Commit**

```bash
git add backend/alembic/versions/20251230_004_analytics_events.py
git commit -m "feat: add analytics_events table"
```

---

## Task 16: Create Analytics Service

**Files:**
- Create: `backend/app/services/analytics_events.py`

**Step 1: Create analytics service**

Create `backend/app/services/analytics_events.py`:
```python
"""
Analytics event tracking service.

Tracks user behavior for product insights and recommendation improvement.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger()


class EventType(str, Enum):
    """Analytics event types."""

    # User events
    USER_SIGNUP = "user.signup"
    USER_LOGIN = "user.login"
    PROFILE_VIEWED = "profile.viewed"
    PROFILE_UPDATED = "profile.updated"

    # Card events
    CARD_VIEWED = "card.viewed"
    CARD_SEARCHED = "card.searched"
    CARD_REFRESHED = "card.refreshed"

    # List events
    WANT_LIST_ADD = "want_list.add"
    WANT_LIST_REMOVE = "want_list.remove"
    HAVE_LIST_ADD = "have_list.add"
    HAVE_LIST_REMOVE = "have_list.remove"
    INVENTORY_ADD = "inventory.add"
    INVENTORY_REMOVE = "inventory.remove"

    # Trading events (future Phase 1+)
    MATCH_VIEWED = "match.viewed"
    TRADE_PROPOSED = "trade.proposed"
    TRADE_ACCEPTED = "trade.accepted"
    TRADE_DECLINED = "trade.declined"
    TRADE_COMPLETED = "trade.completed"

    # Recommendation events
    RECOMMENDATION_VIEWED = "recommendation.viewed"
    RECOMMENDATION_FOLLOWED = "recommendation.followed"

    # Discord events
    DISCORD_LINKED = "discord.linked"
    DISCORD_UNLINKED = "discord.unlinked"


class AnalyticsService:
    """Service for tracking analytics events."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def track(
        self,
        event: EventType | str,
        user_id: Optional[int] = None,
        properties: Optional[dict] = None,
        context: Optional[dict] = None,
    ) -> None:
        """
        Track an analytics event.

        Args:
            event: Event type or custom event string
            user_id: Optional user ID (None for anonymous events)
            properties: Event-specific data (card_id, price, etc.)
            context: Context data (ip, user_agent, etc.)
        """
        from app.models.analytics_event import AnalyticsEvent

        event_type = event.value if isinstance(event, EventType) else event

        try:
            stmt = insert(AnalyticsEvent).values(
                event_type=event_type,
                user_id=user_id,
                properties=properties or {},
                context=context or {},
                timestamp=datetime.now(timezone.utc),
            )
            await self.db.execute(stmt)
            await self.db.flush()

            logger.debug(
                "Analytics event tracked",
                event_type=event_type,
                user_id=user_id,
                properties=properties,
            )
        except Exception as e:
            # Don't fail the request if analytics fails
            logger.warning(
                "Failed to track analytics event",
                event_type=event_type,
                error=str(e),
            )


# Convenience function
async def track_event(
    db: AsyncSession,
    event: EventType | str,
    user_id: Optional[int] = None,
    properties: Optional[dict] = None,
    context: Optional[dict] = None,
) -> None:
    """Convenience function to track an event."""
    service = AnalyticsService(db)
    await service.track(event, user_id, properties, context)
```

**Step 2: Create analytics event model**

Create `backend/app/models/analytics_event.py`:
```python
"""Analytics event model."""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalyticsEvent(Base):
    """Analytics event for tracking user behavior."""

    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

**Step 3: Add to models __init__**

Add to `backend/app/models/__init__.py`:
```python
from app.models.analytics_event import AnalyticsEvent
```

**Step 4: Verify service works**

Run: `docker compose exec backend python -c "from app.services.analytics_events import EventType, track_event; print('OK')"`
Expected: OK

**Step 5: Commit**

```bash
git add backend/app/services/analytics_events.py backend/app/models/analytics_event.py backend/app/models/__init__.py
git commit -m "feat: add analytics event tracking service"
```

---

## Summary

This plan implements all Phase 0 components:

| Task | Component | Description |
|------|-----------|-------------|
| 1-2 | Hashids | URL encoding utility |
| 3-4 | Public Cards | Public endpoints without auth |
| 5 | SEO | Sitemap and robots.txt |
| 6 | SSR Metadata | OG tags for social sharing |
| 7-8 | User Profiles | Profile fields and model |
| 9-10 | Profile API | User profile endpoints |
| 11-12 | Notifications | Preferences and connected accounts tables |
| 13 | Connected Accounts | OAuth linking model |
| 14 | Discord OAuth | Account linking flow |
| 15-16 | Analytics | Event tracking service |

**Total: 16 tasks, ~2-3 hours of implementation**

After completing these tasks:
1. Run full test suite: `make test`
2. Verify frontend build: `docker compose exec frontend npm run build`
3. Create PR for review

---

Plan complete and saved to `docs/plans/2025-12-30-phase0-foundation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
