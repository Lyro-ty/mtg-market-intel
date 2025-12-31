# Phase 0: Foundation + Intelligence Infrastructure

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish public identity, notifications, and fix critical empty data tables

**Architecture:** Hashids for public URLs, enhanced user profiles, activate notification system, populate tournament/news data

**Tech Stack:** Python hashids, FastAPI, PostgreSQL, Celery, TopDeck.gg API

**Tasks:** 12 (reduced from 16)

---

## Task 0.1: Hashids Setup

**Files:**
- Create: `backend/app/core/hashids.py`
- Test: `backend/tests/core/test_hashids.py`

**Step 1: Write failing tests**

```python
# backend/tests/core/test_hashids.py
import pytest
from app.core.hashids import encode_id, decode_id, encode_card_id, decode_card_id

def test_encode_decode_roundtrip():
    """Encoding then decoding returns original ID."""
    original_id = 12345
    encoded = encode_id(original_id)
    decoded = decode_id(encoded)
    assert decoded == original_id

def test_encode_produces_string():
    """Encoded ID is a non-empty string."""
    encoded = encode_id(1)
    assert isinstance(encoded, str)
    assert len(encoded) >= 6  # Minimum length for obfuscation

def test_decode_invalid_returns_none():
    """Invalid hashid returns None, not error."""
    result = decode_id("invalid_hashid_xyz")
    assert result is None

def test_card_id_uses_different_salt():
    """Card IDs use different salt than user IDs."""
    card_encoded = encode_card_id(100)
    user_encoded = encode_id(100)
    assert card_encoded != user_encoded

def test_decode_wrong_type_returns_none():
    """Decoding card hash as user hash returns None."""
    card_hash = encode_card_id(100)
    result = decode_id(card_hash)  # Using user decoder
    assert result is None
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/core/test_hashids.py -v
# Expected: ModuleNotFoundError: No module named 'app.core.hashids'
```

**Step 3: Install dependency and implement**

```bash
pip install hashids
echo "hashids>=1.3.1" >> backend/requirements.txt
```

```python
# backend/app/core/hashids.py
"""
Hashids encoding for public-facing URLs.

Uses different salts for different entity types to prevent
cross-type decoding attacks.
"""
from hashids import Hashids
from app.core.config import settings

# Minimum length for obfuscation
MIN_LENGTH = 8

# Different hashids instances for different entity types
_user_hasher = Hashids(salt=f"{settings.SECRET_KEY}_users", min_length=MIN_LENGTH)
_card_hasher = Hashids(salt=f"{settings.SECRET_KEY}_cards", min_length=MIN_LENGTH)
_generic_hasher = Hashids(salt=settings.SECRET_KEY, min_length=MIN_LENGTH)


def encode_id(id: int) -> str:
    """Encode a generic ID (users, etc.)."""
    return _user_hasher.encode(id)


def decode_id(hashid: str) -> int | None:
    """Decode a generic hashid. Returns None if invalid."""
    try:
        result = _user_hasher.decode(hashid)
        return result[0] if result else None
    except Exception:
        return None


def encode_card_id(id: int) -> str:
    """Encode a card ID."""
    return _card_hasher.encode(id)


def decode_card_id(hashid: str) -> int | None:
    """Decode a card hashid. Returns None if invalid."""
    try:
        result = _card_hasher.decode(hashid)
        return result[0] if result else None
    except Exception:
        return None
```

**Step 4: Run test to verify it passes**

```bash
pytest backend/tests/core/test_hashids.py -v
# Expected: All tests pass
```

**Step 5: Commit**

```bash
git add backend/app/core/hashids.py backend/tests/core/test_hashids.py backend/requirements.txt
git commit -m "feat: add hashids encoding for public URLs"
```

---

## Task 0.2: Public Card Endpoints

**Files:**
- Modify: `backend/app/api/routes/cards.py`
- Test: `backend/tests/api/test_public_cards.py`

**Step 1: Write failing tests**

```python
# backend/tests/api/test_public_cards.py
import pytest
from httpx import AsyncClient
from app.core.hashids import encode_card_id

@pytest.mark.asyncio
async def test_get_card_by_hashid(client: AsyncClient, test_card):
    """Public endpoint returns card by hashid without auth."""
    hashid = encode_card_id(test_card.id)
    response = await client.get(f"/api/cards/public/{hashid}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_card.name
    assert data["hashid"] == hashid
    assert "id" not in data  # Don't expose internal ID

@pytest.mark.asyncio
async def test_get_card_invalid_hashid(client: AsyncClient):
    """Invalid hashid returns 404."""
    response = await client.get("/api/cards/public/invalid_hash_xyz")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_card_prices_public(client: AsyncClient, test_card):
    """Price history accessible without auth."""
    hashid = encode_card_id(test_card.id)
    response = await client.get(f"/api/cards/public/{hashid}/prices")
    assert response.status_code == 200
```

**Step 2: Implement public endpoints**

```python
# In backend/app/api/routes/cards.py - add these endpoints

from app.core.hashids import encode_card_id, decode_card_id

@router.get("/public/{hashid}", response_model=CardPublicResponse)
async def get_card_public(
    hashid: str,
    db: AsyncSession = Depends(get_db),
):
    """Get card by hashid (public, no auth required)."""
    card_id = decode_card_id(hashid)
    if card_id is None:
        raise HTTPException(status_code=404, detail="Card not found")

    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    return CardPublicResponse(
        hashid=hashid,
        name=card.name,
        set_code=card.set_code,
        set_name=card.set_name,
        # ... other public fields, NO internal id
    )

@router.get("/public/{hashid}/prices")
async def get_card_prices_public(
    hashid: str,
    days: int = Query(default=30, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get price history (public, no auth required)."""
    card_id = decode_card_id(hashid)
    if card_id is None:
        raise HTTPException(status_code=404, detail="Card not found")
    # ... existing price logic
```

**Step 3: Create CardPublicResponse schema**

```python
# In backend/app/schemas/card.py

class CardPublicResponse(BaseModel):
    """Public card response - no internal ID exposed."""
    hashid: str
    name: str
    set_code: str
    set_name: str | None
    collector_number: str
    rarity: str | None
    mana_cost: str | None
    type_line: str | None
    oracle_text: str | None
    image_url: str | None
    # Pricing summary
    current_price: Decimal | None
    price_change_24h: Decimal | None
    price_change_7d: Decimal | None

    class Config:
        from_attributes = True
```

**Step 4: Run tests**

```bash
pytest backend/tests/api/test_public_cards.py -v
```

**Step 5: Commit**

```bash
git add backend/app/api/routes/cards.py backend/app/schemas/card.py backend/tests/api/test_public_cards.py
git commit -m "feat: add public card endpoints with hashid URLs"
```

---

## Task 0.3: User Profile Fields Migration

**Files:**
- Create: `backend/alembic/versions/YYYYMMDD_add_user_profile_fields.py`
- Modify: `backend/app/models/user.py`
- Test: `backend/tests/models/test_user.py`

**Step 1: Create migration**

```bash
cd backend && alembic revision -m "add user profile fields"
```

```python
# backend/alembic/versions/YYYYMMDD_add_user_profile_fields.py
def upgrade():
    op.add_column('users', sa.Column('avatar_url', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('location', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('discord_id', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True))

    # Index for Discord ID lookups
    op.create_index('ix_users_discord_id', 'users', ['discord_id'], unique=True)

def downgrade():
    op.drop_index('ix_users_discord_id')
    op.drop_column('users', 'last_active_at')
    op.drop_column('users', 'discord_id')
    op.drop_column('users', 'location')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'avatar_url')
```

**Step 2: Update User model**

```python
# In backend/app/models/user.py - add fields
avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
bio: Mapped[str | None] = mapped_column(Text, nullable=True)
location: Mapped[str | None] = mapped_column(String(100), nullable=True)
discord_id: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True, index=True)
last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**Step 3: Run migration**

```bash
alembic upgrade head
```

**Step 4: Commit**

```bash
git add backend/alembic/versions/*_add_user_profile_fields.py backend/app/models/user.py
git commit -m "feat: add user profile fields (avatar, bio, location, discord)"
```

---

## Task 0.4: Profile API Endpoints

**Files:**
- Create: `backend/app/api/routes/profiles.py`
- Modify: `backend/app/api/__init__.py`
- Test: `backend/tests/api/test_profiles.py`

**Step 1: Write failing tests**

```python
# backend/tests/api/test_profiles.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_own_profile(client: AsyncClient, auth_headers, test_user):
    """Authenticated user can get their own profile."""
    response = await client.get("/api/profile/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["username"] == test_user.username

@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, auth_headers):
    """User can update their profile."""
    response = await client.patch(
        "/api/profile/me",
        headers=auth_headers,
        json={
            "bio": "MTG collector since 2010",
            "location": "Seattle, WA",
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["bio"] == "MTG collector since 2010"
    assert data["location"] == "Seattle, WA"

@pytest.mark.asyncio
async def test_bio_length_limit(client: AsyncClient, auth_headers):
    """Bio is limited to 500 characters."""
    response = await client.patch(
        "/api/profile/me",
        headers=auth_headers,
        json={"bio": "x" * 501}
    )
    assert response.status_code == 422
```

**Step 2: Implement profile routes**

```python
# backend/app/api/routes/profiles.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User
from app.schemas.profile import ProfileResponse, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """Get current user's profile."""
    return current_user

@router.patch("/me", response_model=ProfileResponse)
async def update_my_profile(
    profile_update: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current user's profile."""
    for field, value in profile_update.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)
    return current_user
```

**Step 3: Create schemas**

```python
# backend/app/schemas/profile.py
from pydantic import BaseModel, Field

class ProfileUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=500)
    location: str | None = Field(None, max_length=100)
    avatar_url: str | None = Field(None, max_length=500)

class ProfileResponse(BaseModel):
    id: int
    email: str
    username: str
    display_name: str | None
    bio: str | None
    location: str | None
    avatar_url: str | None
    discord_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True
```

**Step 4: Run tests and commit**

```bash
pytest backend/tests/api/test_profiles.py -v
git add backend/app/api/routes/profiles.py backend/app/schemas/profile.py backend/tests/api/test_profiles.py
git commit -m "feat: add profile API endpoints"
```

---

## Task 0.5: Available-for-Trade Flag

**Files:**
- Create: `backend/alembic/versions/YYYYMMDD_add_available_for_trade.py`
- Modify: `backend/app/models/inventory.py`
- Modify: `backend/app/api/routes/inventory.py`
- Test: `backend/tests/api/test_inventory_trade_flag.py`

**Step 1: Create migration**

```python
def upgrade():
    op.add_column('inventory_items',
        sa.Column('available_for_trade', sa.Boolean(),
                  server_default='false', nullable=False))

def downgrade():
    op.drop_column('inventory_items', 'available_for_trade')
```

**Step 2: Update model and API**

```python
# In InventoryItem model
available_for_trade: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

# In inventory routes - add filter
@router.get("/", response_model=list[InventoryItemResponse])
async def list_inventory(
    available_for_trade: bool | None = Query(None),
    # ... existing params
):
    query = select(InventoryItem).where(InventoryItem.user_id == current_user.id)
    if available_for_trade is not None:
        query = query.where(InventoryItem.available_for_trade == available_for_trade)
    # ...
```

**Step 3: Commit**

```bash
git commit -m "feat: add available_for_trade flag to inventory items"
```

---

## Task 0.6: Notification System Activation

**Files:**
- Create: `backend/app/services/notifications.py`
- Modify: `backend/app/api/routes/notifications.py`
- Test: `backend/tests/services/test_notifications.py`

**Step 1: Create NotificationService**

```python
# backend/app/services/notifications.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Notification, User

class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def send(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        card_id: int | None = None,
        priority: str = "medium",
        extra_data: dict | None = None,
    ) -> Notification:
        """Create and store a notification."""
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            card_id=card_id,
            priority=priority,
            extra_data=extra_data,
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def send_price_alert(
        self,
        user_id: int,
        card_name: str,
        card_id: int,
        old_price: Decimal,
        new_price: Decimal,
    ):
        """Send price drop/spike notification."""
        change_pct = ((new_price - old_price) / old_price * 100)
        direction = "dropped" if change_pct < 0 else "spiked"

        return await self.send(
            user_id=user_id,
            notification_type="price_alert",
            title=f"{card_name} {direction} {abs(change_pct):.1f}%",
            message=f"Price changed from ${old_price:.2f} to ${new_price:.2f}",
            card_id=card_id,
            priority="high" if abs(change_pct) > 20 else "medium",
        )
```

**Step 2: Hook into price alerts task**

```python
# In analytics task, when price threshold crossed:
notification_service = NotificationService(db)
await notification_service.send_price_alert(
    user_id=want_list_item.user_id,
    card_name=card.name,
    card_id=card.id,
    old_price=old_price,
    new_price=new_price,
)
```

**Step 3: Commit**

```bash
git commit -m "feat: implement NotificationService with price alerts"
```

---

## Task 0.7: Tournament Data Collection (FIX EMPTY TABLE)

**Files:**
- Modify: `backend/app/services/tournaments/topdeck_client.py`
- Create: `backend/app/tasks/tournaments.py`
- Modify: `backend/app/tasks/celery_app.py`
- Test: `backend/tests/tasks/test_tournaments.py`

**This is CRITICAL - tournaments table has 0 rows!**

**Step 1: Verify TopDeck client works**

```python
# Test the existing client
from app.services.tournaments.topdeck_client import TopDeckClient

async def test_fetch():
    client = TopDeckClient()
    tournaments = await client.get_tournaments(format="Modern", days=7)
    print(f"Found {len(tournaments)} tournaments")
```

**Step 2: Create Celery task**

```python
# backend/app/tasks/tournaments.py
from celery import shared_task
from app.services.tournaments.topdeck_client import TopDeckClient
from app.models import Tournament, TournamentStanding
from app.db.session import async_session_maker

@shared_task(name="collect_tournament_data")
def collect_tournament_data():
    """Collect tournament data from TopDeck.gg."""
    import asyncio
    asyncio.run(_collect_tournament_data())

async def _collect_tournament_data():
    client = TopDeckClient()

    formats = ["Modern", "Pioneer", "Standard", "Legacy", "Pauper"]

    async with async_session_maker() as db:
        for format_name in formats:
            tournaments = await client.get_tournaments(format=format_name, days=7)

            for t in tournaments:
                # Check if exists
                existing = await db.execute(
                    select(Tournament).where(Tournament.external_id == t["id"])
                )
                if existing.scalar_one_or_none():
                    continue

                tournament = Tournament(
                    external_id=t["id"],
                    name=t["name"],
                    format=format_name,
                    date=t["date"],
                    player_count=t.get("players"),
                    source="topdeck",
                )
                db.add(tournament)
                await db.flush()

                # Add standings if available
                for standing in t.get("standings", []):
                    ts = TournamentStanding(
                        tournament_id=tournament.id,
                        rank=standing["rank"],
                        player_name=standing["player"],
                        deck_name=standing.get("deck"),
                        deck_cards=standing.get("cards"),  # JSON
                    )
                    db.add(ts)

        await db.commit()
```

**Step 3: Add to Celery beat schedule**

```python
# In celery_app.py
app.conf.beat_schedule["collect-tournament-data"] = {
    "task": "collect_tournament_data",
    "schedule": crontab(hour="*/4"),  # Every 4 hours
}
```

**Step 4: Run manually to verify**

```bash
docker compose exec worker celery -A app.tasks.celery_app call collect_tournament_data
# Verify: SELECT COUNT(*) FROM tournaments;
```

**Step 5: Commit**

```bash
git commit -m "feat: add tournament data collection task (fixes empty table)"
```

---

## Task 0.8: Meta Analysis Signals

**Files:**
- Modify: `backend/app/tasks/analytics.py`
- Create: `backend/app/services/meta_analysis.py`

**Step 1: Calculate meta share per card**

```python
# backend/app/services/meta_analysis.py
async def calculate_meta_share(db: AsyncSession, format: str) -> dict[int, float]:
    """Calculate what % of decks each card appears in for a format."""

    # Get recent tournament standings with deck data
    result = await db.execute(
        select(TournamentStanding)
        .join(Tournament)
        .where(Tournament.format == format)
        .where(Tournament.date >= datetime.now() - timedelta(days=30))
    )
    standings = result.scalars().all()

    total_decks = len(standings)
    card_appearances = defaultdict(int)

    for standing in standings:
        if standing.deck_cards:
            for card_id in standing.deck_cards:
                card_appearances[card_id] += 1

    return {
        card_id: count / total_decks * 100
        for card_id, count in card_appearances.items()
    }
```

**Step 2: Generate META_SPIKE signals**

```python
# When meta share increases significantly
if new_meta_share > old_meta_share * 1.5:  # 50% increase
    signal = Signal(
        card_id=card_id,
        signal_type="META_SPIKE",
        value=new_meta_share,
        metadata={"format": format, "old_share": old_meta_share}
    )
```

**Step 3: Commit**

```bash
git commit -m "feat: add meta analysis signals from tournament data"
```

---

## Task 0.9-0.12: (Abbreviated for space)

**Task 0.9: News Collection**
- Implement RSS fetcher for MTGGoldfish
- Store in news_articles table
- Link card mentions to card_news_mentions

**Task 0.10: Reprint Risk Fields**
- Add first_printed_at, reprint_count, last_reprinted_at to cards
- Calculate reprint_risk_score based on frequency and time since last reprint

**Task 0.11: Supply Signal Enhancement**
- Verify num_listings populated in adapters
- Add SUPPLY_LOW and SUPPLY_VELOCITY signal types

**Task 0.12: Cross-Market Arbitrage**
- Compare prices across marketplaces
- Calculate after-fees profit
- Generate ARBITRAGE_OPPORTUNITY signals

---

## Phase 0 Completion Checklist

- [ ] Task 0.1: Hashids encoding utility
- [ ] Task 0.2: Public card endpoints with hashids
- [ ] Task 0.3: User profile fields migration
- [ ] Task 0.4: Profile API endpoints
- [ ] Task 0.5: Available-for-trade flag
- [ ] Task 0.6: Notification service activation
- [ ] Task 0.7: Tournament data collection (FIX EMPTY!)
- [ ] Task 0.8: Meta analysis signals
- [ ] Task 0.9: News collection
- [ ] Task 0.10: Reprint risk fields
- [ ] Task 0.11: Supply signal enhancement
- [ ] Task 0.12: Cross-market arbitrage signals

**Success Criteria:**
- `SELECT COUNT(*) FROM tournaments` > 500
- `SELECT COUNT(*) FROM news_articles` > 50
- Public card pages accessible without auth
- Notifications appearing when price alerts trigger
