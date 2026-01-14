# Discord Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Discord bot that provides MTG price lookups, want list management, and price alert notifications for Dualcaster Deals users.

**Architecture:** Separate Python service using discord.py, communicates with backend via REST API with service token auth. Users link accounts via Discord OAuth.

**Tech Stack:** Python 3.12, discord.py, httpx, FastAPI (backend additions), Docker

---

## Phase 1: Backend Infrastructure

### Task 1.1: Add Discord Fields to User Model

**Files:**
- Modify: `backend/app/models/user.py:62-64`
- Create: `backend/alembic/versions/20251231_add_discord_fields.py`

**Step 1: Update User model**

Add after `discord_id` field (line 62):

```python
discord_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, unique=True, index=True)
discord_username: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
discord_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

**Step 2: Create migration**

```bash
cd backend && alembic revision -m "add discord username and alerts enabled"
```

**Step 3: Write migration content**

```python
"""add discord username and alerts enabled

Revision ID: 20251231_discord
Revises: <previous>
Create Date: 2025-12-31
"""
from alembic import op
import sqlalchemy as sa

revision = '20251231_discord'
down_revision = None  # Will be set by alembic
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('users', sa.Column('discord_username', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('discord_alerts_enabled', sa.Boolean(), nullable=False, server_default='true'))

def downgrade() -> None:
    op.drop_column('users', 'discord_alerts_enabled')
    op.drop_column('users', 'discord_username')
```

**Step 4: Run migration**

```bash
docker compose exec backend alembic upgrade head
```

**Step 5: Commit**

```bash
git add backend/app/models/user.py backend/alembic/versions/
git commit -m "feat: add discord_username and discord_alerts_enabled to users"
```

---

### Task 1.2: Add Discord OAuth Config

**Files:**
- Modify: `backend/app/core/config.py:31-34`
- Modify: `.env.example`

**Step 1: Add Discord settings to config.py after Google OAuth settings**

```python
# Discord OAuth settings
DISCORD_CLIENT_ID: str = ""
DISCORD_CLIENT_SECRET: str = ""
DISCORD_REDIRECT_URI: str = "http://localhost:8000/api/auth/discord/callback"
DISCORD_BOT_TOKEN: str = ""
BOT_SERVICE_TOKEN: str = ""  # For bot-to-backend auth
```

**Step 2: Add to .env.example**

```bash
# Discord OAuth
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_REDIRECT_URI=http://localhost:8000/api/auth/discord/callback
DISCORD_BOT_TOKEN=

# Bot Service Token (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
BOT_SERVICE_TOKEN=
```

**Step 3: Commit**

```bash
git add backend/app/core/config.py .env.example
git commit -m "feat: add Discord OAuth config settings"
```

---

### Task 1.3: Discord OAuth Endpoints

**Files:**
- Modify: `backend/app/api/routes/oauth.py`

**Step 1: Add Discord OAuth endpoints after Google routes**

```python
# Discord OAuth endpoints

@router.get("/discord/authorize")
async def discord_authorize(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get Discord OAuth URL for account linking (requires auth)."""
    if not settings.DISCORD_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Discord OAuth not configured")

    # Generate state with user ID embedded
    state = secrets.token_urlsafe(32)
    redis_client = get_redis()
    redis_client.setex(f"discord_oauth:{state}", 300, str(current_user.id))

    params = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "redirect_uri": settings.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
        "state": state,
    }

    auth_url = "https://discord.com/oauth2/authorize"
    query_string = "&".join(f"{k}={v}" for k, v in params.items())

    return {"url": f"{auth_url}?{query_string}"}


@router.get("/discord/callback")
async def discord_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Handle Discord OAuth callback and link account."""
    if error:
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?discord_error={error}",
            status_code=302,
        )

    if not code or not state:
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?discord_error=missing_params",
            status_code=302,
        )

    # Get user ID from state
    redis_client = get_redis()
    user_id_str = redis_client.get(f"discord_oauth:{state}")
    if not user_id_str:
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?discord_error=invalid_state",
            status_code=302,
        )

    redis_client.delete(f"discord_oauth:{state}")
    user_id = int(user_id_str)

    # Exchange code for token
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://discord.com/api/oauth2/token",
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
                return RedirectResponse(
                    url=f"{settings.frontend_url}/settings?discord_error=token_exchange_failed",
                    status_code=302,
                )

            tokens = token_response.json()

            # Get Discord user info
            user_response = await client.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )

            if user_response.status_code != 200:
                return RedirectResponse(
                    url=f"{settings.frontend_url}/settings?discord_error=user_info_failed",
                    status_code=302,
                )

            discord_user = user_response.json()

    except httpx.RequestError:
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?discord_error=request_failed",
            status_code=302,
        )

    discord_id = discord_user["id"]
    discord_username = f"{discord_user['username']}"

    # Check if Discord account already linked to another user
    result = await db.execute(
        select(User).where(User.discord_id == discord_id, User.id != user_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?discord_error=already_linked",
            status_code=302,
        )

    # Link Discord to user
    user = await db.get(User, user_id)
    if user:
        user.discord_id = discord_id
        user.discord_username = discord_username
        await db.commit()

    return RedirectResponse(
        url=f"{settings.frontend_url}/settings?discord_linked=true",
        status_code=302,
    )


@router.delete("/discord/unlink")
async def discord_unlink(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unlink Discord account."""
    if not current_user.discord_id:
        raise HTTPException(status_code=400, detail="No Discord account linked")

    current_user.discord_id = None
    current_user.discord_username = None
    await db.commit()

    return {"status": "unlinked", "message": "Discord account unlinked"}
```

**Step 2: Add import at top**

```python
from app.api.deps import get_current_user
```

**Step 3: Commit**

```bash
git add backend/app/api/routes/oauth.py
git commit -m "feat: add Discord OAuth endpoints for account linking"
```

---

### Task 1.4: Bot Authentication Middleware

**Files:**
- Create: `backend/app/api/deps_bot.py`

**Step 1: Create bot auth dependency**

```python
"""Bot authentication dependencies."""
from fastapi import HTTPException, Request

from app.core.config import settings


async def verify_bot_token(request: Request) -> None:
    """
    Verify bot service token from X-Bot-Token header.

    Raises HTTPException 401 if token is missing or invalid.
    """
    token = request.headers.get("X-Bot-Token")

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Bot-Token header"
        )

    if token != settings.BOT_SERVICE_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid bot token"
        )
```

**Step 2: Commit**

```bash
git add backend/app/api/deps_bot.py
git commit -m "feat: add bot authentication middleware"
```

---

### Task 1.5: Bot API Routes - User Lookup

**Files:**
- Create: `backend/app/api/routes/bot.py`
- Create: `backend/app/schemas/bot.py`
- Modify: `backend/app/api/__init__.py`

**Step 1: Create bot schemas**

```python
"""Bot API schemas."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class BotUserResponse(BaseModel):
    """User info for bot."""
    id: int
    username: str
    display_name: Optional[str]
    discord_alerts_enabled: bool

    class Config:
        from_attributes = True


class BotPortfolioResponse(BaseModel):
    """Portfolio summary for bot."""
    total_value: Decimal
    total_cost: Decimal
    total_gain: Decimal
    gain_percent: float
    card_count: int
    top_card_name: Optional[str]
    top_card_value: Optional[Decimal]


class BotWantListItem(BaseModel):
    """Want list item for bot."""
    card_id: int
    card_name: str
    set_code: str
    target_price: Decimal
    current_price: Optional[Decimal]
    alert_enabled: bool
    hit: bool  # Current price <= target


class BotCardPrice(BaseModel):
    """Card price data for bot."""
    card_id: int
    name: str
    set_code: str
    set_name: str
    image_url: Optional[str]
    price: Optional[Decimal]
    price_change_7d: Optional[float]
    buylist_price: Optional[Decimal]
    meta_share: Optional[float]
    color_identity: Optional[str]


class BotCardSearchResult(BaseModel):
    """Card search results for bot."""
    cards: list[BotCardPrice]
    suggestions: list[str]


class BotMoversResponse(BaseModel):
    """Top movers for bot."""
    gainers: list[BotCardPrice]
    losers: list[BotCardPrice]


class BotTraderInfo(BaseModel):
    """Trader info for bot."""
    user_id: int
    username: str
    display_name: Optional[str]
    quantity: int


class BotPendingAlert(BaseModel):
    """Pending alert for delivery."""
    id: int
    discord_id: str
    card_name: str
    current_price: Decimal
    target_price: Decimal
    alert_type: str  # price_drop, spike, etc.


class BotWantListCreate(BaseModel):
    """Create want list item."""
    card_id: int
    target_price: Decimal


class BotAlertCreate(BaseModel):
    """Create alert."""
    card_id: int
    target_price: Decimal


class BotPreferencesUpdate(BaseModel):
    """Update preferences."""
    discord_alerts_enabled: Optional[bool] = None
```

**Step 2: Create bot routes**

```python
"""Bot API routes for Discord bot integration."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps_bot import verify_bot_token
from app.db.session import get_db
from app.models import User, Card, InventoryItem, WantListItem, PriceSnapshot
from app.schemas.bot import (
    BotUserResponse,
    BotPortfolioResponse,
    BotWantListItem,
    BotCardPrice,
    BotCardSearchResult,
    BotMoversResponse,
    BotTraderInfo,
    BotPendingAlert,
    BotWantListCreate,
    BotAlertCreate,
    BotPreferencesUpdate,
)

router = APIRouter(
    prefix="/bot",
    tags=["Bot"],
    dependencies=[Depends(verify_bot_token)]
)
logger = structlog.get_logger(__name__)


async def get_user_by_discord(db: AsyncSession, discord_id: str) -> User:
    """Get user by Discord ID or raise 404."""
    result = await db.execute(
        select(User).where(User.discord_id == discord_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not linked")
    return user


@router.get("/user/{discord_id}", response_model=BotUserResponse)
async def get_user(
    discord_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get user by Discord ID."""
    user = await get_user_by_discord(db, discord_id)
    return BotUserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        discord_alerts_enabled=user.discord_alerts_enabled,
    )


@router.get("/user/{discord_id}/portfolio", response_model=BotPortfolioResponse)
async def get_portfolio(
    discord_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get portfolio summary for Discord user."""
    user = await get_user_by_discord(db, discord_id)

    # Get inventory with current prices
    result = await db.execute(
        select(InventoryItem)
        .where(InventoryItem.user_id == user.id)
        .options(selectinload(InventoryItem.card))
    )
    items = result.scalars().all()

    if not items:
        return BotPortfolioResponse(
            total_value=Decimal("0"),
            total_cost=Decimal("0"),
            total_gain=Decimal("0"),
            gain_percent=0.0,
            card_count=0,
            top_card_name=None,
            top_card_value=None,
        )

    total_value = Decimal("0")
    total_cost = Decimal("0")
    top_card = None
    top_value = Decimal("0")

    for item in items:
        cost = (item.acquisition_price or Decimal("0")) * item.quantity
        total_cost += cost

        # Get current price (simplified - would use price cache in production)
        if item.card and item.card.price:
            value = item.card.price * item.quantity
            total_value += value
            if value > top_value:
                top_value = value
                top_card = item.card

    total_gain = total_value - total_cost
    gain_percent = float(total_gain / total_cost * 100) if total_cost > 0 else 0.0

    return BotPortfolioResponse(
        total_value=total_value,
        total_cost=total_cost,
        total_gain=total_gain,
        gain_percent=gain_percent,
        card_count=len(items),
        top_card_name=top_card.name if top_card else None,
        top_card_value=top_value if top_card else None,
    )


@router.get("/user/{discord_id}/want-list", response_model=list[BotWantListItem])
async def get_want_list(
    discord_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get want list for Discord user."""
    user = await get_user_by_discord(db, discord_id)

    result = await db.execute(
        select(WantListItem)
        .where(WantListItem.user_id == user.id)
        .options(selectinload(WantListItem.card))
    )
    items = result.scalars().all()

    return [
        BotWantListItem(
            card_id=item.card_id,
            card_name=item.card.name,
            set_code=item.card.set_code,
            target_price=item.target_price,
            current_price=item.card.price,
            alert_enabled=item.alert_enabled,
            hit=item.card.price <= item.target_price if item.card.price else False,
        )
        for item in items
    ]


@router.post("/user/{discord_id}/want-list", response_model=BotWantListItem)
async def add_to_want_list(
    discord_id: str,
    body: BotWantListCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add card to want list."""
    user = await get_user_by_discord(db, discord_id)

    # Check card exists
    card = await db.get(Card, body.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check not already on list
    result = await db.execute(
        select(WantListItem).where(
            WantListItem.user_id == user.id,
            WantListItem.card_id == body.card_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Card already on want list")

    item = WantListItem(
        user_id=user.id,
        card_id=body.card_id,
        target_price=body.target_price,
        alert_enabled=True,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return BotWantListItem(
        card_id=item.card_id,
        card_name=card.name,
        set_code=card.set_code,
        target_price=item.target_price,
        current_price=card.price,
        alert_enabled=item.alert_enabled,
        hit=card.price <= item.target_price if card.price else False,
    )


@router.delete("/user/{discord_id}/want-list/{card_id}")
async def remove_from_want_list(
    discord_id: str,
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove card from want list."""
    user = await get_user_by_discord(db, discord_id)

    result = await db.execute(
        select(WantListItem).where(
            WantListItem.user_id == user.id,
            WantListItem.card_id == card_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Card not on want list")

    await db.delete(item)
    await db.commit()

    return {"status": "removed"}


@router.patch("/user/{discord_id}/preferences")
async def update_preferences(
    discord_id: str,
    body: BotPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update user preferences (mute/unmute alerts)."""
    user = await get_user_by_discord(db, discord_id)

    if body.discord_alerts_enabled is not None:
        user.discord_alerts_enabled = body.discord_alerts_enabled

    await db.commit()

    return {
        "discord_alerts_enabled": user.discord_alerts_enabled,
    }


@router.get("/cards/search", response_model=BotCardSearchResult)
async def search_cards(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, le=25),
    db: AsyncSession = Depends(get_db),
):
    """Fuzzy search cards with suggestions."""
    # Simple ILIKE search - could use trigram similarity for better fuzzy matching
    result = await db.execute(
        select(Card)
        .where(Card.name.ilike(f"%{q}%"))
        .order_by(Card.name)
        .limit(limit)
    )
    cards = result.scalars().all()

    card_prices = [
        BotCardPrice(
            card_id=card.id,
            name=card.name,
            set_code=card.set_code,
            set_name=card.set_name or "",
            image_url=card.image_url,
            price=card.price,
            price_change_7d=None,  # Would calculate from snapshots
            buylist_price=None,
            meta_share=card.meta_score,
            color_identity=card.color_identity,
        )
        for card in cards
    ]

    # Generate suggestions if no exact matches
    suggestions = []
    if not cards:
        # Could use Levenshtein distance here
        suggestions = []

    return BotCardSearchResult(cards=card_prices, suggestions=suggestions)


@router.get("/card-price/{card_id}", response_model=BotCardPrice)
async def get_card_price(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all price data for a card in one call."""
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    return BotCardPrice(
        card_id=card.id,
        name=card.name,
        set_code=card.set_code,
        set_name=card.set_name or "",
        image_url=card.image_url,
        price=card.price,
        price_change_7d=None,  # Would calculate from snapshots
        buylist_price=None,
        meta_share=card.meta_score,
        color_identity=card.color_identity,
    )


@router.get("/movers", response_model=BotMoversResponse)
async def get_movers(
    limit: int = Query(5, le=10),
    db: AsyncSession = Depends(get_db),
):
    """Get top gainers and losers."""
    # Simplified - would use actual price change calculations
    result = await db.execute(
        select(Card)
        .where(Card.price.isnot(None))
        .order_by(Card.price.desc())
        .limit(limit)
    )
    gainers = result.scalars().all()

    result = await db.execute(
        select(Card)
        .where(Card.price.isnot(None))
        .order_by(Card.price.asc())
        .limit(limit)
    )
    losers = result.scalars().all()

    def to_bot_card(card: Card) -> BotCardPrice:
        return BotCardPrice(
            card_id=card.id,
            name=card.name,
            set_code=card.set_code,
            set_name=card.set_name or "",
            image_url=card.image_url,
            price=card.price,
            price_change_7d=None,
            buylist_price=None,
            meta_share=card.meta_score,
            color_identity=card.color_identity,
        )

    return BotMoversResponse(
        gainers=[to_bot_card(c) for c in gainers],
        losers=[to_bot_card(c) for c in losers],
    )


@router.get("/find-traders/{card_id}", response_model=list[BotTraderInfo])
async def find_traders(
    card_id: int,
    limit: int = Query(10, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Find users with card marked for trade."""
    result = await db.execute(
        select(InventoryItem, User)
        .join(User, InventoryItem.user_id == User.id)
        .where(
            InventoryItem.card_id == card_id,
            InventoryItem.for_trade == True,
            User.is_active == True,
        )
        .limit(limit)
    )
    rows = result.all()

    return [
        BotTraderInfo(
            user_id=user.id,
            username=user.username,
            display_name=user.display_name,
            quantity=item.quantity,
        )
        for item, user in rows
    ]
```

**Step 3: Register bot routes in `backend/app/api/__init__.py`**

Add import:
```python
from app.api.routes import bot
```

Add router:
```python
api_router.include_router(bot.router)
```

**Step 4: Commit**

```bash
git add backend/app/api/routes/bot.py backend/app/schemas/bot.py backend/app/api/__init__.py
git commit -m "feat: add bot API routes for Discord integration"
```

---

### Task 1.6: Alert Queue Table

**Files:**
- Create: `backend/app/models/discord_alert.py`
- Create: `backend/alembic/versions/20251231_add_discord_alert_queue.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Create model**

```python
"""Discord alert queue model for tracking alert delivery."""
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DiscordAlertQueue(Base):
    """Queue for Discord alert delivery with retry logic."""

    __tablename__ = "discord_alert_queue"

    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    discord_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Delivery tracking
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Status
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    notification = relationship("Notification")

    __table_args__ = (
        Index(
            "ix_alert_queue_pending",
            "next_attempt_at",
            postgresql_where="delivered_at IS NULL AND failed_at IS NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<DiscordAlertQueue {self.id} discord={self.discord_id}>"
```

**Step 2: Create migration**

```python
"""add discord alert queue

Revision ID: 20251231_alerts
Revises: 20251231_discord
Create Date: 2025-12-31
"""
from alembic import op
import sqlalchemy as sa

revision = '20251231_alerts'
down_revision = '20251231_discord'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'discord_alert_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('notification_id', sa.Integer(), nullable=False),
        sa.Column('discord_id', sa.String(20), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_discord_alert_queue_discord_id', 'discord_alert_queue', ['discord_id'])
    op.create_index('ix_discord_alert_queue_notification_id', 'discord_alert_queue', ['notification_id'])
    op.create_index('ix_discord_alert_queue_next_attempt', 'discord_alert_queue', ['next_attempt_at'])

def downgrade() -> None:
    op.drop_table('discord_alert_queue')
```

**Step 3: Add to models/__init__.py**

```python
from app.models.discord_alert import DiscordAlertQueue
```

**Step 4: Commit**

```bash
git add backend/app/models/discord_alert.py backend/alembic/versions/ backend/app/models/__init__.py
git commit -m "feat: add discord alert queue table"
```

---

### Task 1.7: Pending Alerts Endpoint

**Files:**
- Modify: `backend/app/api/routes/bot.py`

**Step 1: Add pending alerts and delivery endpoints**

```python
@router.get("/pending-alerts", response_model=list[BotPendingAlert])
async def get_pending_alerts(
    since: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get alerts that need delivery since timestamp."""
    from app.models.discord_alert import DiscordAlertQueue
    from app.models.notification import Notification

    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(DiscordAlertQueue, Notification)
        .join(Notification, DiscordAlertQueue.notification_id == Notification.id)
        .where(
            DiscordAlertQueue.delivered_at.is_(None),
            DiscordAlertQueue.failed_at.is_(None),
            or_(
                DiscordAlertQueue.next_attempt_at.is_(None),
                DiscordAlertQueue.next_attempt_at <= now,
            ),
        )
        .limit(100)
    )
    rows = result.all()

    alerts = []
    for queue_item, notification in rows:
        extra = notification.extra_data or {}
        alerts.append(BotPendingAlert(
            id=queue_item.id,
            discord_id=queue_item.discord_id,
            card_name=extra.get("card_name", "Unknown"),
            current_price=Decimal(extra.get("current_price", "0")),
            target_price=Decimal(extra.get("target_price", "0")),
            alert_type=notification.type.value if hasattr(notification.type, 'value') else str(notification.type),
        ))

    return alerts


@router.post("/alerts/{queue_id}/delivered")
async def mark_alert_delivered(
    queue_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Mark alert as delivered."""
    from app.models.discord_alert import DiscordAlertQueue

    item = await db.get(DiscordAlertQueue, queue_id)
    if not item:
        raise HTTPException(status_code=404, detail="Alert not found")

    item.delivered_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "delivered"}


@router.post("/alerts/{queue_id}/failed")
async def mark_alert_failed(
    queue_id: int,
    error: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Mark alert delivery as failed with retry logic."""
    from app.models.discord_alert import DiscordAlertQueue
    from datetime import timedelta

    RETRY_DELAYS = [0, 300, 900]  # Immediate, 5min, 15min

    item = await db.get(DiscordAlertQueue, queue_id)
    if not item:
        raise HTTPException(status_code=404, detail="Alert not found")

    item.attempts += 1
    item.last_attempt_at = datetime.now(timezone.utc)
    item.error_message = error

    if item.attempts >= item.max_attempts:
        item.failed_at = datetime.now(timezone.utc)
    else:
        delay = RETRY_DELAYS[min(item.attempts, len(RETRY_DELAYS) - 1)]
        item.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

    await db.commit()

    return {
        "status": "retry_scheduled" if not item.failed_at else "permanently_failed",
        "attempts": item.attempts,
    }
```

**Step 2: Commit**

```bash
git add backend/app/api/routes/bot.py
git commit -m "feat: add pending alerts and delivery status endpoints"
```

---

## Phase 2: Discord Bot Service

### Task 2.1: Bot Directory Structure

**Files:**
- Create: `discord-bot/` directory structure

**Step 1: Create directory structure**

```bash
mkdir -p discord-bot/bot/cogs discord-bot/bot/utils
touch discord-bot/bot/__init__.py
touch discord-bot/bot/cogs/__init__.py
touch discord-bot/bot/utils/__init__.py
```

**Step 2: Create requirements.txt**

```
discord.py>=2.3.0
httpx>=0.25.0
python-dotenv>=1.0.0
structlog>=23.0.0
```

**Step 3: Create .env.example**

```bash
# Discord
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_APPLICATION_ID=your_app_id_here

# Backend API
API_URL=http://backend:8000/api
BOT_SERVICE_TOKEN=your_service_token_here

# Bot config
COMMAND_PREFIX=!
EMBED_COLOR=0x7C3AED
```

**Step 4: Commit**

```bash
git add discord-bot/
git commit -m "feat: create discord bot directory structure"
```

---

### Task 2.2: Bot Config and API Client

**Files:**
- Create: `discord-bot/bot/config.py`
- Create: `discord-bot/bot/api_client.py`

**Step 1: Create config**

```python
"""Bot configuration from environment."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Bot configuration."""

    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
    DISCORD_APPLICATION_ID = os.getenv("DISCORD_APPLICATION_ID", "")

    API_URL = os.getenv("API_URL", "http://backend:8000/api")
    BOT_SERVICE_TOKEN = os.getenv("BOT_SERVICE_TOKEN", "")

    COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
    EMBED_COLOR = int(os.getenv("EMBED_COLOR", "0x7C3AED"), 16)

    SITE_URL = os.getenv("SITE_URL", "https://dualcasterdeals.com")


config = Config()
```

**Step 2: Create API client**

```python
"""HTTP client for backend API."""
from datetime import datetime
from typing import Optional, Any
import httpx
import structlog

from .config import config

logger = structlog.get_logger(__name__)


class APIClient:
    """HTTP client for backend API calls."""

    def __init__(self):
        self.base_url = config.API_URL
        self.headers = {"X-Bot-Token": config.BOT_SERVICE_TOKEN}

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> Optional[dict]:
        """Make HTTP request to backend."""
        url = f"{self.base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method,
                    url,
                    headers=self.headers,
                    **kwargs
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("API request failed", url=url, status=e.response.status_code)
            raise
        except httpx.RequestError as e:
            logger.error("API request error", url=url, error=str(e))
            raise

    async def get_user(self, discord_id: str) -> Optional[dict]:
        """Get user by Discord ID."""
        return await self._request("GET", f"/bot/user/{discord_id}")

    async def get_portfolio(self, discord_id: str) -> Optional[dict]:
        """Get portfolio summary."""
        return await self._request("GET", f"/bot/user/{discord_id}/portfolio")

    async def get_want_list(self, discord_id: str) -> list:
        """Get want list."""
        result = await self._request("GET", f"/bot/user/{discord_id}/want-list")
        return result or []

    async def add_to_want_list(
        self,
        discord_id: str,
        card_id: int,
        target_price: float
    ) -> Optional[dict]:
        """Add card to want list."""
        return await self._request(
            "POST",
            f"/bot/user/{discord_id}/want-list",
            json={"card_id": card_id, "target_price": target_price}
        )

    async def remove_from_want_list(self, discord_id: str, card_id: int) -> bool:
        """Remove card from want list."""
        try:
            await self._request("DELETE", f"/bot/user/{discord_id}/want-list/{card_id}")
            return True
        except:
            return False

    async def search_cards(self, query: str, limit: int = 10) -> dict:
        """Search cards."""
        result = await self._request(
            "GET",
            "/bot/cards/search",
            params={"q": query, "limit": limit}
        )
        return result or {"cards": [], "suggestions": []}

    async def get_card_price(self, card_id: int) -> Optional[dict]:
        """Get card price data."""
        return await self._request("GET", f"/bot/card-price/{card_id}")

    async def get_movers(self, limit: int = 5) -> dict:
        """Get top movers."""
        result = await self._request("GET", "/bot/movers", params={"limit": limit})
        return result or {"gainers": [], "losers": []}

    async def find_traders(self, card_id: int, limit: int = 10) -> list:
        """Find traders with card."""
        result = await self._request(
            "GET",
            f"/bot/find-traders/{card_id}",
            params={"limit": limit}
        )
        return result or []

    async def get_pending_alerts(self, since: datetime) -> list:
        """Get pending alerts."""
        result = await self._request(
            "GET",
            "/bot/pending-alerts",
            params={"since": since.isoformat()}
        )
        return result or []

    async def mark_alert_delivered(self, queue_id: int) -> bool:
        """Mark alert as delivered."""
        try:
            await self._request("POST", f"/bot/alerts/{queue_id}/delivered")
            return True
        except:
            return False

    async def mark_alert_failed(self, queue_id: int, error: str) -> dict:
        """Mark alert as failed."""
        return await self._request(
            "POST",
            f"/bot/alerts/{queue_id}/failed",
            params={"error": error}
        )

    async def update_preferences(
        self,
        discord_id: str,
        discord_alerts_enabled: bool
    ) -> Optional[dict]:
        """Update user preferences."""
        return await self._request(
            "PATCH",
            f"/bot/user/{discord_id}/preferences",
            json={"discord_alerts_enabled": discord_alerts_enabled}
        )


# Global client instance
api = APIClient()
```

**Step 3: Commit**

```bash
git add discord-bot/bot/config.py discord-bot/bot/api_client.py
git commit -m "feat: add bot config and API client"
```

---

### Task 2.3: Bot Main Entry Point

**Files:**
- Create: `discord-bot/bot/main.py`

**Step 1: Create main bot file**

```python
"""Discord bot main entry point."""
import asyncio
import discord
from discord.ext import commands
import structlog

from .config import config

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger(__name__)


class DualcasterBot(commands.Bot):
    """Main bot class."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix=config.COMMAND_PREFIX,
            intents=intents,
            help_command=None,  # We'll implement custom help
        )

    async def setup_hook(self):
        """Load cogs on startup."""
        cogs = [
            "bot.cogs.general",
            "bot.cogs.price",
            "bot.cogs.market",
            "bot.cogs.portfolio",
            "bot.cogs.wantlist",
            "bot.cogs.alerts",
            "bot.cogs.discovery",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")

        # Sync slash commands
        if config.DISCORD_APPLICATION_ID:
            try:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands")
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(
            "Bot is ready",
            user=str(self.user),
            guilds=len(self.guilds),
        )

    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Global error handler."""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Slow down! Try again in {error.retry_after:.0f}s")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: `{error.param.name}`")
        elif isinstance(error, commands.CommandNotFound):
            pass  # Ignore unknown commands
        else:
            logger.error("Command error", command=ctx.command, error=str(error))
            await ctx.send("⚠️ Something went wrong. Please try again later.")


def main():
    """Run the bot."""
    if not config.DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not set")
        return

    bot = DualcasterBot()
    bot.run(config.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add discord-bot/bot/main.py
git commit -m "feat: add bot main entry point"
```

---

### Task 2.4: Embed Builders

**Files:**
- Create: `discord-bot/bot/embeds.py`

**Step 1: Create embed builder utilities**

```python
"""Discord embed builders."""
import discord
from decimal import Decimal
from typing import Optional

from .config import config

# Color constants based on MTG colors
COLORS = {
    "W": 0xF8F6D8,  # White
    "U": 0x0E68AB,  # Blue
    "B": 0x150B00,  # Black
    "R": 0xD3202A,  # Red
    "G": 0x00733E,  # Green
    "default": config.EMBED_COLOR,
    "success": 0x2ECC71,
    "error": 0xE74C3C,
    "warning": 0xF39C12,
}


def get_color_for_card(color_identity: Optional[str]) -> int:
    """Get embed color based on card color identity."""
    if not color_identity:
        return COLORS["default"]

    # Single color
    if len(color_identity) == 1:
        return COLORS.get(color_identity, COLORS["default"])

    # Multicolor - use default purple
    return COLORS["default"]


def format_price_change(change: Optional[float]) -> str:
    """Format price change with emoji."""
    if change is None:
        return "—"

    emoji = "📈" if change >= 0 else "📉"
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.1f}% {emoji}"


def card_price_embed(card: dict) -> discord.Embed:
    """Build embed for card price display."""
    color = get_color_for_card(card.get("color_identity"))

    embed = discord.Embed(
        title=card["name"],
        url=f"{config.SITE_URL}/cards/{card['card_id']}",
        color=color,
    )

    if card.get("image_url"):
        embed.set_thumbnail(url=card["image_url"])

    embed.add_field(
        name="Set",
        value=f"{card.get('set_name', card['set_code'])} ({card['set_code']})",
        inline=True,
    )

    price = card.get("price")
    if price:
        embed.add_field(
            name="Price",
            value=f"${price:.2f}",
            inline=True,
        )

    change = card.get("price_change_7d")
    embed.add_field(
        name="7d Change",
        value=format_price_change(change),
        inline=True,
    )

    if card.get("buylist_price"):
        embed.add_field(
            name="Buylist",
            value=f"${card['buylist_price']:.2f}",
            inline=True,
        )

    if card.get("meta_share"):
        embed.add_field(
            name="Meta Share",
            value=f"{card['meta_share']:.1f}%",
            inline=True,
        )

    embed.set_footer(
        text="Dualcaster Deals",
        icon_url=f"{config.SITE_URL}/favicon.ico",
    )

    return embed


def portfolio_embed(portfolio: dict) -> discord.Embed:
    """Build embed for portfolio summary."""
    gain = portfolio["total_gain"]
    color = COLORS["success"] if gain >= 0 else COLORS["error"]

    embed = discord.Embed(
        title="📊 Your Portfolio",
        color=color,
    )

    embed.add_field(
        name="Total Value",
        value=f"${portfolio['total_value']:.2f}",
        inline=True,
    )

    sign = "+" if gain >= 0 else ""
    embed.add_field(
        name="Gain/Loss",
        value=f"{sign}${gain:.2f} ({sign}{portfolio['gain_percent']:.1f}%)",
        inline=True,
    )

    embed.add_field(
        name="Cards",
        value=str(portfolio["card_count"]),
        inline=True,
    )

    if portfolio.get("top_card_name"):
        embed.add_field(
            name="Top Card",
            value=f"{portfolio['top_card_name']} (${portfolio['top_card_value']:.2f})",
            inline=False,
        )

    embed.set_footer(text=f"View full portfolio at {config.SITE_URL}/portfolio")

    return embed


def want_list_embed(items: list) -> discord.Embed:
    """Build embed for want list."""
    embed = discord.Embed(
        title=f"📝 Your Want List ({len(items)} cards)",
        color=COLORS["default"],
    )

    if not items:
        embed.description = "Your want list is empty.\nUse `!want add <card> <price>` to add cards."
        return embed

    lines = []
    for i, item in enumerate(items[:10], 1):  # Max 10 items
        status = "✅" if item["hit"] else "⏳"
        hit_text = " — *HIT!*" if item["hit"] else ""
        current = f"${item['current_price']:.2f}" if item["current_price"] else "?"

        lines.append(
            f"{status} **{item['card_name']}** — "
            f"Target: ${item['target_price']:.2f} (Current: {current}){hit_text}"
        )

    embed.description = "\n".join(lines)

    if len(items) > 10:
        embed.set_footer(text=f"...and {len(items) - 10} more. View all at {config.SITE_URL}/want-list")
    else:
        embed.set_footer(text=f"Manage at {config.SITE_URL}/want-list")

    return embed


def movers_embed(movers: dict) -> discord.Embed:
    """Build embed for top movers."""
    embed = discord.Embed(
        title="📊 Market Movers",
        color=COLORS["default"],
    )

    # Gainers
    if movers.get("gainers"):
        lines = []
        for card in movers["gainers"][:5]:
            change = format_price_change(card.get("price_change_7d"))
            lines.append(f"**{card['name']}** ${card.get('price', 0):.2f} {change}")
        embed.add_field(name="📈 Top Gainers", value="\n".join(lines) or "None", inline=False)

    # Losers
    if movers.get("losers"):
        lines = []
        for card in movers["losers"][:5]:
            change = format_price_change(card.get("price_change_7d"))
            lines.append(f"**{card['name']}** ${card.get('price', 0):.2f} {change}")
        embed.add_field(name="📉 Top Losers", value="\n".join(lines) or "None", inline=False)

    return embed


def alert_embed(alert: dict) -> discord.Embed:
    """Build embed for price alert notification."""
    embed = discord.Embed(
        title=f"🔔 Price Alert: {alert['card_name']}",
        color=COLORS["success"],
    )

    embed.add_field(
        name="Current Price",
        value=f"${alert['current_price']:.2f}",
        inline=True,
    )

    embed.add_field(
        name="Your Target",
        value=f"${alert['target_price']:.2f}",
        inline=True,
    )

    embed.set_footer(text=f"View at {config.SITE_URL}")

    return embed


def error_embed(message: str, suggestion: Optional[str] = None) -> discord.Embed:
    """Build error embed."""
    embed = discord.Embed(
        title="❌ Error",
        description=message,
        color=COLORS["error"],
    )

    if suggestion:
        embed.add_field(name="Suggestion", value=suggestion, inline=False)

    return embed


def success_embed(message: str) -> discord.Embed:
    """Build success embed."""
    return discord.Embed(
        title="✅ Success",
        description=message,
        color=COLORS["success"],
    )


def link_required_embed() -> discord.Embed:
    """Build embed for unlinked users."""
    return discord.Embed(
        title="❌ Account Not Linked",
        description=f"Visit **{config.SITE_URL}/settings** to connect your Discord account.",
        color=COLORS["warning"],
    )
```

**Step 2: Commit**

```bash
git add discord-bot/bot/embeds.py
git commit -m "feat: add discord embed builders"
```

---

### Task 2.5: General Commands Cog

**Files:**
- Create: `discord-bot/bot/cogs/general.py`

**Step 1: Create general commands**

```python
"""General bot commands: help, ping, link, status."""
import discord
from discord.ext import commands

from ..api_client import api
from ..config import config
from ..embeds import error_embed, success_embed, link_required_embed


class GeneralCog(commands.Cog, name="General"):
    """General bot commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context, command_name: str = None):
        """Show help for commands."""
        embed = discord.Embed(
            title="Dualcaster Deals Bot",
            description="MTG market intelligence at your fingertips!",
            color=config.EMBED_COLOR,
        )

        if command_name:
            # Help for specific command
            cmd = self.bot.get_command(command_name)
            if cmd:
                embed.add_field(
                    name=f"!{cmd.name}",
                    value=cmd.help or "No description",
                    inline=False,
                )
            else:
                embed.description = f"Command `{command_name}` not found."
        else:
            # General help
            embed.add_field(
                name="📈 Price & Market",
                value=(
                    "`!price <card>` - Get card price\n"
                    "`!movers` - Top gainers/losers\n"
                    "`!spread <card>` - Buy/sell spread\n"
                    "`!history <card>` - Price history"
                ),
                inline=False,
            )

            embed.add_field(
                name="📊 Portfolio",
                value=(
                    "`!portfolio` - Your collection value\n"
                    "`!mygainers` - Your top movers"
                ),
                inline=False,
            )

            embed.add_field(
                name="📝 Want List",
                value=(
                    "`!want add <card> [price]` - Add card\n"
                    "`!want list` - Show want list\n"
                    "`!want remove <card>` - Remove card\n"
                    "`!alert <card> <price>` - Set price alert"
                ),
                inline=False,
            )

            embed.add_field(
                name="🔍 Discovery",
                value=(
                    "`!find <card>` - Find traders\n"
                    "`!profile` - Your profile link"
                ),
                inline=False,
            )

            embed.add_field(
                name="⚙️ General",
                value=(
                    "`!link` - Link your account\n"
                    "`!status` - Check link status\n"
                    "`!mute` / `!unmute` - Toggle alerts\n"
                    "`!ping` - Bot latency"
                ),
                inline=False,
            )

            embed.set_footer(text=f"Use !help <command> for details | {config.SITE_URL}")

        await ctx.send(embed=embed)

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        """Check bot latency."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"🏓 Pong! Latency: {latency}ms")

    @commands.command(name="link")
    async def link(self, ctx: commands.Context):
        """Get instructions to link Discord account."""
        embed = discord.Embed(
            title="🔗 Link Your Discord Account",
            description=(
                f"1. Visit **{config.SITE_URL}/settings**\n"
                f"2. Click **Link Discord**\n"
                f"3. Authorize the connection\n\n"
                "Once linked, you can use portfolio and want list commands!"
            ),
            color=config.EMBED_COLOR,
        )
        await ctx.send(embed=embed)

    @commands.command(name="status")
    async def status(self, ctx: commands.Context):
        """Check if your account is linked."""
        try:
            user = await api.get_user(str(ctx.author.id))

            if user:
                embed = discord.Embed(
                    title="✅ Account Linked",
                    color=0x2ECC71,
                )
                embed.add_field(name="Username", value=user["username"], inline=True)
                embed.add_field(
                    name="Discord Alerts",
                    value="Enabled" if user["discord_alerts_enabled"] else "Muted",
                    inline=True,
                )
                embed.set_footer(text=f"Manage at {config.SITE_URL}/settings")
            else:
                embed = link_required_embed()

            await ctx.send(embed=embed)

        except Exception:
            await ctx.send(embed=link_required_embed())

    @commands.command(name="mute")
    async def mute(self, ctx: commands.Context):
        """Mute Discord DM alerts."""
        try:
            result = await api.update_preferences(str(ctx.author.id), discord_alerts_enabled=False)
            if result:
                await ctx.send(embed=success_embed("Discord alerts muted. You'll still see alerts on the website."))
            else:
                await ctx.send(embed=link_required_embed())
        except Exception:
            await ctx.send(embed=error_embed("Failed to update preferences."))

    @commands.command(name="unmute")
    async def unmute(self, ctx: commands.Context):
        """Unmute Discord DM alerts."""
        try:
            result = await api.update_preferences(str(ctx.author.id), discord_alerts_enabled=True)
            if result:
                await ctx.send(embed=success_embed("Discord alerts enabled. You'll receive price alerts via DM."))
            else:
                await ctx.send(embed=link_required_embed())
        except Exception:
            await ctx.send(embed=error_embed("Failed to update preferences."))


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCog(bot))
```

**Step 2: Commit**

```bash
git add discord-bot/bot/cogs/general.py
git commit -m "feat: add general commands cog (help, ping, link, status)"
```

---

### Task 2.6: Price Commands Cog

**Files:**
- Create: `discord-bot/bot/cogs/price.py`

**Step 1: Create price commands**

```python
"""Price lookup commands."""
import re
import discord
from discord.ext import commands

from ..api_client import api
from ..config import config
from ..embeds import card_price_embed, error_embed


class PriceCog(commands.Cog, name="Price"):
    """Card price lookup commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def parse_query(self, query: str) -> tuple[str, str | None, bool]:
        """
        Parse card query for name, set code, and foil flag.

        Examples:
            "lightning bolt" -> ("lightning bolt", None, False)
            "lightning bolt [2X2]" -> ("lightning bolt", "2X2", False)
            "lightning bolt foil" -> ("lightning bolt", None, True)
            "ragavan cheapest" -> ("ragavan", "cheapest", False)
        """
        foil = False
        set_code = None

        # Check for foil flag
        if query.lower().endswith(" foil"):
            foil = True
            query = query[:-5].strip()

        # Check for set code in brackets
        match = re.search(r"\[([A-Z0-9]+)\]", query, re.IGNORECASE)
        if match:
            set_code = match.group(1).upper()
            query = re.sub(r"\s*\[[A-Z0-9]+\]\s*", " ", query, flags=re.IGNORECASE).strip()

        # Check for "cheapest" keyword
        if query.lower().endswith(" cheapest"):
            set_code = "cheapest"
            query = query[:-9].strip()

        return query, set_code, foil

    @commands.command(name="price")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def price(self, ctx: commands.Context, *, query: str):
        """
        Get card price.

        Usage:
            !price lightning bolt
            !price lightning bolt [2X2]
            !price ragavan cheapest
            !price mana crypt foil
        """
        card_name, set_code, foil = self.parse_query(query)

        async with ctx.typing():
            try:
                results = await api.search_cards(card_name, limit=10)
                cards = results.get("cards", [])

                if not cards:
                    suggestions = results.get("suggestions", [])
                    if suggestions:
                        await ctx.send(embed=error_embed(
                            f"Card not found: `{card_name}`",
                            f"Did you mean **{suggestions[0]}**?"
                        ))
                    else:
                        await ctx.send(embed=error_embed(f"Card not found: `{card_name}`"))
                    return

                # If set code specified, filter
                if set_code and set_code != "cheapest":
                    filtered = [c for c in cards if c["set_code"].upper() == set_code]
                    if filtered:
                        cards = filtered

                # If "cheapest", sort by price
                if set_code == "cheapest":
                    cards = sorted(cards, key=lambda c: c.get("price") or 999999)

                # If multiple results and no specific set requested
                if len(cards) > 1 and not set_code:
                    embed = discord.Embed(
                        title=f"⚡ Multiple printings found for \"{card_name}\"",
                        color=config.EMBED_COLOR,
                    )

                    lines = []
                    for i, card in enumerate(cards[:5], 1):
                        price = f"${card['price']:.2f}" if card.get("price") else "?"
                        lines.append(
                            f"{i}. **{card.get('set_name', card['set_code'])}** "
                            f"({card['set_code']}) — {price}"
                        )

                    embed.description = "\n".join(lines)
                    embed.set_footer(
                        text=f"Use: !price {card_name} [SET_CODE] or !price {card_name} cheapest"
                    )

                    await ctx.send(embed=embed)
                    return

                # Single result - show price
                card = cards[0]
                await ctx.send(embed=card_price_embed(card))

            except Exception as e:
                await ctx.send(embed=error_embed("Failed to fetch price. Try again later."))

    @commands.command(name="history")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def history(self, ctx: commands.Context, *, card_name: str):
        """Show 30-day price history for a card."""
        async with ctx.typing():
            try:
                results = await api.search_cards(card_name, limit=1)
                cards = results.get("cards", [])

                if not cards:
                    await ctx.send(embed=error_embed(f"Card not found: `{card_name}`"))
                    return

                card = cards[0]

                # For now, just show current price with note about history
                embed = discord.Embed(
                    title=f"📈 Price History: {card['name']}",
                    color=config.EMBED_COLOR,
                )

                if card.get("image_url"):
                    embed.set_thumbnail(url=card["image_url"])

                price = card.get("price")
                if price:
                    embed.add_field(name="Current Price", value=f"${price:.2f}", inline=True)

                embed.set_footer(text=f"View full chart at {config.SITE_URL}/cards/{card['card_id']}")

                await ctx.send(embed=embed)

            except Exception:
                await ctx.send(embed=error_embed("Failed to fetch history."))

    @commands.command(name="spread")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def spread(self, ctx: commands.Context, *, card_name: str):
        """Show buy/sell spread for arbitrage opportunities."""
        async with ctx.typing():
            try:
                results = await api.search_cards(card_name, limit=1)
                cards = results.get("cards", [])

                if not cards:
                    await ctx.send(embed=error_embed(f"Card not found: `{card_name}`"))
                    return

                card = cards[0]

                embed = discord.Embed(
                    title=f"📊 Spread: {card['name']}",
                    color=config.EMBED_COLOR,
                )

                buy_price = card.get("price")
                sell_price = card.get("buylist_price")

                if buy_price:
                    embed.add_field(name="Buy (TCGPlayer)", value=f"${buy_price:.2f}", inline=True)

                if sell_price:
                    embed.add_field(name="Sell (Buylist)", value=f"${sell_price:.2f}", inline=True)

                    if buy_price:
                        spread = (buy_price - sell_price) / buy_price * 100
                        embed.add_field(name="Spread", value=f"{spread:.1f}%", inline=True)
                else:
                    embed.add_field(name="Buylist", value="Not available", inline=True)

                await ctx.send(embed=embed)

            except Exception:
                await ctx.send(embed=error_embed("Failed to fetch spread."))

    @commands.command(name="buylist")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def buylist(self, ctx: commands.Context, *, card_name: str):
        """Show buylist prices."""
        # For now, same as spread but focused on buylist
        await self.spread(ctx, card_name=card_name)


async def setup(bot: commands.Bot):
    await bot.add_cog(PriceCog(bot))
```

**Step 2: Commit**

```bash
git add discord-bot/bot/cogs/price.py
git commit -m "feat: add price commands cog"
```

---

This plan continues with more cogs (market, portfolio, wantlist, alerts, discovery), Dockerfile, docker-compose changes, etc. Due to length, I'll summarize the remaining tasks:

### Remaining Tasks (Summary)

**Phase 2 continued:**
- Task 2.7: Market Cog (`!movers`, `!meta`, `!staples`)
- Task 2.8: Portfolio Cog (`!portfolio`, `!mygainers`)
- Task 2.9: Want List Cog (`!want add/list/remove`, `!alert`, `!alerts`)
- Task 2.10: Alerts Cog (delivery loop)
- Task 2.11: Discovery Cog (`!find`, `!profile`)

**Phase 3: Deployment:**
- Task 3.1: Dockerfile
- Task 3.2: Docker Compose integration
- Task 3.3: Slash commands setup

---

## Progress Checklist

- [ ] Task 1.1: Add Discord fields to User model
- [ ] Task 1.2: Add Discord OAuth config
- [ ] Task 1.3: Discord OAuth endpoints
- [ ] Task 1.4: Bot authentication middleware
- [ ] Task 1.5: Bot API routes
- [ ] Task 1.6: Alert queue table
- [ ] Task 1.7: Pending alerts endpoint
- [ ] Task 2.1: Bot directory structure
- [ ] Task 2.2: Config and API client
- [ ] Task 2.3: Main entry point
- [ ] Task 2.4: Embed builders
- [ ] Task 2.5: General commands cog
- [ ] Task 2.6: Price commands cog
- [ ] Task 2.7: Market cog
- [ ] Task 2.8: Portfolio cog
- [ ] Task 2.9: Want list cog
- [ ] Task 2.10: Alerts cog
- [ ] Task 2.11: Discovery cog
- [ ] Task 3.1: Dockerfile
- [ ] Task 3.2: Docker Compose
- [ ] Task 3.3: Slash commands
