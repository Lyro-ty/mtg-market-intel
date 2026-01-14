# Implementation Prerequisites

This document covers everything needed **before** starting implementation of the platform phases.

---

## 1. Environment Variables by Phase

### Phase 0: Foundation

Add to `.env`:

```bash
# -----------------------------------------------------------------------------
# Discord OAuth (for account linking)
# -----------------------------------------------------------------------------
# 1. Go to https://discord.com/developers/applications
# 2. Create New Application → "Dualcaster Deals"
# 3. OAuth2 → Add Redirect: http://localhost:8000/api/oauth/discord/callback
# 4. Copy Client ID and Client Secret
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_REDIRECT_URI=http://localhost:8000/api/oauth/discord/callback

# -----------------------------------------------------------------------------
# Email Service (for notifications)
# -----------------------------------------------------------------------------
# Options: resend, sendgrid, smtp
# For development, leave empty to use console logging
EMAIL_PROVIDER=
EMAIL_FROM_ADDRESS=notifications@dualcasterdeals.com
EMAIL_FROM_NAME=Dualcaster Deals

# Resend (https://resend.com - free tier: 3000 emails/month)
RESEND_API_KEY=

# SendGrid (https://sendgrid.com)
SENDGRID_API_KEY=

# SMTP (generic)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_TLS=true
```

### Phase 1: Intelligence + Distribution

Add to `.env`:

```bash
# -----------------------------------------------------------------------------
# Discord Bot (separate from OAuth)
# -----------------------------------------------------------------------------
# 1. Same Discord application, go to "Bot" section
# 2. Click "Reset Token" to get bot token
# 3. Enable "Message Content Intent" under Privileged Gateway Intents
# 4. Generate invite URL with: bot, applications.commands scopes
DISCORD_BOT_TOKEN=
DISCORD_BOT_API_KEY=generate_a_random_32_char_string_here

# Bot invite URL (after creating):
# https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=2147485696&scope=bot%20applications.commands
```

### Phase 2: Social + Trust

No additional environment variables required.

### Phase 3: Transaction + Business

Add to `.env`:

```bash
# -----------------------------------------------------------------------------
# Stripe Connect (for escrow)
# -----------------------------------------------------------------------------
# 1. Go to https://dashboard.stripe.com/apikeys
# 2. Enable Connect in settings
# 3. Set up webhook endpoint: /api/webhooks/stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Platform fee percentage (e.g., 2.0 = 2%)
STRIPE_PLATFORM_FEE_PCT=2.0
```

---

## 2. Test Fixtures

The implementation plans use TDD. Add these fixtures to `backend/tests/conftest.py`:

```python
"""
Extended test fixtures for platform features.
Add this to the existing conftest.py
"""
import pytest_asyncio
from datetime import datetime, timezone
from decimal import Decimal

from app.models import User, Card, InventoryItem, WantListItem, HaveListItem
from app.services.auth import hash_password


# -----------------------------------------------------------------------------
# User Fixtures
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_user(db_session) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=hash_password("password123"),
        is_active=True,
        is_public=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_2(db_session) -> User:
    """Create a second test user for trading scenarios."""
    user = User(
        email="test2@example.com",
        username="testuser2",
        hashed_password=hash_password("password123"),
        is_active=True,
        is_public=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user) -> dict:
    """Get auth headers for test user."""
    from app.services.auth import create_access_token
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers_2(test_user_2) -> dict:
    """Get auth headers for second test user."""
    from app.services.auth import create_access_token
    token = create_access_token(test_user_2.id)
    return {"Authorization": f"Bearer {token}"}


# -----------------------------------------------------------------------------
# Card Fixtures
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_card(db_session) -> Card:
    """Create a test card."""
    card = Card(
        id=1,  # Fixed ID for testing
        name="Lightning Bolt",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="161",
        rarity="common",
        mana_cost="{R}",
        type_line="Instant",
        oracle_text="Lightning Bolt deals 3 damage to any target.",
        image_url="https://cards.scryfall.io/normal/front/example.jpg",
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest_asyncio.fixture
async def test_card_2(db_session) -> Card:
    """Create a second test card."""
    card = Card(
        id=2,
        name="Counterspell",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="54",
        rarity="uncommon",
        mana_cost="{U}{U}",
        type_line="Instant",
        oracle_text="Counter target spell.",
        image_url="https://cards.scryfall.io/normal/front/example2.jpg",
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


# -----------------------------------------------------------------------------
# Inventory Fixtures
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_inventory_item(db_session, test_user, test_card) -> dict:
    """Create a test inventory item."""
    item = InventoryItem(
        user_id=test_user.id,
        card_id=test_card.id,
        quantity=4,
        condition="NEAR_MINT",
        is_foil=False,
        acquisition_price=Decimal("5.00"),
        acquisition_date=datetime.now(timezone.utc),
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return {
        "id": item.id,
        "user_id": item.user_id,
        "card_id": item.card_id,
        "quantity": item.quantity,
        "condition": item.condition,
    }


# -----------------------------------------------------------------------------
# Have List Fixtures (Phase 1)
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_have_list_item(db_session, test_user, test_inventory_item) -> dict:
    """Create a test have list item."""
    from app.models import HaveListItem

    item = HaveListItem(
        user_id=test_user.id,
        inventory_item_id=test_inventory_item["id"],
        min_trade_value=Decimal("10.00"),
        trade_for_wants_only=False,
        notes="Looking for blue cards",
        is_active=True,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return {
        "id": item.id,
        "user_id": item.user_id,
        "inventory_item_id": item.inventory_item_id,
    }


# -----------------------------------------------------------------------------
# Want List Fixtures
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_want_list_item(db_session, test_user, test_card_2) -> dict:
    """Create a test want list item."""
    item = WantListItem(
        user_id=test_user.id,
        card_id=test_card_2.id,
        target_price=Decimal("3.00"),
        priority="high",
        alert_enabled=True,
        is_active=True,
        quantity=2,
        condition_min="LP",
        is_foil_required=False,
        language="EN",
        is_public=True,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return {
        "id": item.id,
        "user_id": item.user_id,
        "card_id": item.card_id,
    }


# -----------------------------------------------------------------------------
# Trade Fixtures (Phase 2)
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_trade_proposal(db_session, test_user, test_user_2, test_card, test_card_2) -> dict:
    """Create a test trade proposal."""
    from app.models import TradeProposal, TradeStatus

    proposal = TradeProposal(
        proposer_id=test_user.id,
        recipient_id=test_user_2.id,
        status=TradeStatus.PENDING,
        proposer_offers=[{
            "card_id": test_card.id,
            "card_name": test_card.name,
            "quantity": 1,
            "condition": "NM",
        }],
        proposer_offers_value=Decimal("50.00"),
        proposer_wants=[{
            "card_id": test_card_2.id,
            "card_name": test_card_2.name,
            "quantity": 1,
            "condition": "NM",
        }],
        proposer_wants_value=Decimal("45.00"),
        message="Want to trade?",
    )
    db_session.add(proposal)
    await db_session.commit()
    await db_session.refresh(proposal)
    return {
        "id": proposal.id,
        "proposer_id": proposal.proposer_id,
        "recipient_id": proposal.recipient_id,
    }


# -----------------------------------------------------------------------------
# Connected Account Fixtures
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_discord_account(db_session, test_user) -> dict:
    """Create a test Discord connected account."""
    from app.models import ConnectedAccount

    account = ConnectedAccount(
        user_id=test_user.id,
        provider="discord",
        provider_user_id="123456789012345678",
        provider_username="testuser#1234",
        provider_display_name="Test User",
        connected_at=datetime.now(timezone.utc),
        verified=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return {
        "id": account.id,
        "user_id": account.user_id,
        "provider_user_id": account.provider_user_id,
    }


# -----------------------------------------------------------------------------
# Reputation Fixtures (Phase 2)
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_user_reputation(db_session, test_user) -> dict:
    """Create a test reputation record."""
    from app.models import UserReputation

    rep = UserReputation(
        user_id=test_user.id,
        total_trades=15,
        total_reviews=12,
        average_rating=Decimal("4.50"),
        reputation_score=350,
        reputation_tier="silver",
        member_since=datetime.now(timezone.utc),
    )
    db_session.add(rep)
    await db_session.commit()
    await db_session.refresh(rep)
    return {
        "user_id": rep.user_id,
        "reputation_score": rep.reputation_score,
        "reputation_tier": rep.reputation_tier,
    }
```

---

## 3. Frontend Page Specifications

### Phase 0 New Pages

#### `/users/[username]` - Public Profile Page

```
┌─────────────────────────────────────────────────────┐
│ ┌────────┐  username                                │
│ │ Avatar │  @handle • Silver Tier ⭐⭐⭐            │
│ │  96px  │  📍 Seattle, WA • 50 mile trade radius  │
│ └────────┘  Member since Jan 2024                   │
│                                                      │
│ [Bio text here - max 500 chars]                     │
│                                                      │
│ ┌──────────────┬──────────────┬──────────────┐     │
│ │  15 Trades   │  4.5 Rating  │  120 Cards   │     │
│ └──────────────┴──────────────┴──────────────┘     │
│                                                      │
│ [Have List] [Want List] tabs                        │
│ ┌─────────────────────────────────────────────┐    │
│ │ Card grid showing public have/want lists    │    │
│ └─────────────────────────────────────────────┘    │
│                                                      │
│ [Message] [Propose Trade] buttons (if logged in)   │
└─────────────────────────────────────────────────────┘
```

**Data Requirements:**
- `GET /api/users/{username}` - Profile data
- `GET /api/users/{username}/have-list` - Public haves
- `GET /api/users/{username}/want-list` - Public wants
- `GET /api/users/{username}/reputation` - Reputation stats

#### `/settings` - Settings Page Extensions

Add tabs for:
- **Profile** - Bio, avatar, location
- **Privacy** - Visibility toggles
- **Connections** - Discord linking
- **Notifications** - Email/Discord preferences

### Phase 1 New Pages

#### `/matches` - Trade Matches Page

```
┌─────────────────────────────────────────────────────┐
│ Find Trade Matches                                   │
│                                                      │
│ Filters: [Local Only ☐] [Min Quality: 50 ▼]        │
│                                                      │
│ ┌─────────────────────────────────────────────┐    │
│ │ Match with @user2                    92% ★  │    │
│ │ ┌───────────────┬───────────────┐           │    │
│ │ │ You Get       │ They Get      │           │    │
│ │ │ - Card A      │ - Card X      │           │    │
│ │ │ - Card B      │ - Card Y      │           │    │
│ │ │ Value: $45    │ Value: $42    │           │    │
│ │ └───────────────┴───────────────┘           │    │
│ │ [View Profile] [Propose Trade]              │    │
│ └─────────────────────────────────────────────┘    │
│                                                      │
│ (more match cards...)                               │
└─────────────────────────────────────────────────────┘
```

**Data Requirements:**
- `GET /api/matches` - List matches for current user
- `GET /api/matches?local_only=true` - Local matches only

### Phase 2 New Pages

#### `/trades` - Trade Proposals Page

```
┌─────────────────────────────────────────────────────┐
│ My Trades                                            │
│                                                      │
│ [Incoming (3)] [Outgoing (1)] [Completed (12)]     │
│                                                      │
│ ┌─────────────────────────────────────────────┐    │
│ │ Trade #abc123 with @user2         PENDING   │    │
│ │ Created: 2 hours ago • Expires: 5 days      │    │
│ │                                              │    │
│ │ You offer: Card A, Card B ($45)             │    │
│ │ You get: Card X ($42)                       │    │
│ │                                              │    │
│ │ [Accept] [Decline] [Counter] [Message]      │    │
│ └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

#### `/messages` - Messaging Page

```
┌─────────────────────────────────────────────────────┐
│ Messages                                             │
│                                                      │
│ ┌──────────────┐ ┌────────────────────────────┐    │
│ │ Conversations│ │ @user2                      │    │
│ │              │ │ Re: Trade #abc123           │    │
│ │ @user2    ●  │ │                             │    │
│ │ @user3       │ │ ┌─────────────────────────┐│    │
│ │ @shop1       │ │ │ Chat messages here...   ││    │
│ │              │ │ │                         ││    │
│ │              │ │ │                         ││    │
│ │              │ │ └─────────────────────────┘│    │
│ │              │ │                             │    │
│ │              │ │ [Type message...] [Send]   │    │
│ └──────────────┘ └────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## 4. Discord Bot Deployment

### docker-compose.yml Addition

Add to `docker-compose.yml`:

```yaml
  discord-bot:
    build:
      context: ./discord-bot
      dockerfile: Dockerfile
    container_name: dualcaster-discord-bot
    depends_on:
      - backend
      - redis
    environment:
      - DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
      - DUALCASTER_API_URL=http://backend:8000/api
      - DUALCASTER_API_KEY=${DISCORD_BOT_API_KEY}
      - REDIS_URL=redis://redis:6379/0
      - LOG_LEVEL=INFO
    restart: unless-stopped
    networks:
      - dualcaster-network
```

### discord-bot/Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY bot/ ./bot/

# Run the bot
CMD ["python", "-m", "bot.main"]
```

### Bot Commands Reference

| Command | Description |
|---------|-------------|
| `/dd price <card>` | Look up card prices |
| `/dd want add <card>` | Add to want list |
| `/dd want list` | Show your want list |
| `/dd want remove <id>` | Remove from want list |
| `/dd have add <card>` | Add to have list |
| `/dd have list` | Show your have list |
| `/dd matches` | Find trade matches |
| `/dd matches server` | Matches within this server |
| `/dd link` | Link Discord to Dualcaster account |
| `/dd unlink` | Unlink account |
| `/dd help` | Show all commands |

---

## 5. API Type Generation Checklist

**After ANY backend schema change:**

```bash
# 1. Rebuild backend to get new OpenAPI spec
docker compose up -d --build backend

# 2. Wait for backend to be healthy
sleep 5

# 3. Generate TypeScript types
make generate-types

# 4. Check for type errors in frontend
cd frontend && npx tsc --noEmit

# 5. Fix any type mismatches
```

**Files that trigger type regeneration:**
- `backend/app/schemas/*.py` - Pydantic schemas
- `backend/app/api/routes/*.py` - Route response types
- `backend/app/models/*.py` - If exposed in schemas

---

## 6. Redis Caching Patterns

### Cache Keys

```
# Card prices (5 min TTL)
card:price:{card_id}

# User matches (1 hour TTL, invalidate on list change)
user:matches:{user_id}

# Reputation scores (1 hour TTL)
user:reputation:{user_id}

# Public profile (15 min TTL)
user:profile:{username}

# Session data (24 hour TTL)
session:{session_id}
```

### Cache Invalidation

```python
# When user updates have/want list:
await redis.delete(f"user:matches:{user_id}")

# When trade completes:
await redis.delete(f"user:reputation:{user_a_id}")
await redis.delete(f"user:reputation:{user_b_id}")

# When profile updates:
await redis.delete(f"user:profile:{username}")
```

### Cache Helper Module

Create `backend/app/core/cache.py`:

```python
"""Redis caching utilities."""
import json
from typing import Optional, Any, Callable, TypeVar
from functools import wraps
import redis.asyncio as redis

from app.core.config import settings

T = TypeVar('T')

_redis_pool = None


async def get_redis() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_pool


async def cache_get(key: str) -> Optional[Any]:
    """Get value from cache."""
    r = await get_redis()
    value = await r.get(key)
    return json.loads(value) if value else None


async def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """Set value in cache with TTL."""
    r = await get_redis()
    await r.setex(key, ttl_seconds, json.dumps(value, default=str))


async def cache_delete(key: str) -> None:
    """Delete key from cache."""
    r = await get_redis()
    await r.delete(key)


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching pattern."""
    r = await get_redis()
    keys = await r.keys(pattern)
    if keys:
        return await r.delete(*keys)
    return 0
```

---

## 7. WebSocket Integration (Phase 2)

### Backend WebSocket Endpoint

```python
# backend/app/api/routes/websocket.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.api.deps import get_current_user_ws

router = APIRouter()

# Connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)

    async def send_to_user(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                await connection.send_json(message)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str,
):
    user = await get_current_user_ws(token)
    if not user:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket, user.id)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle incoming messages (typing indicators, etc.)
            if data.get("type") == "typing":
                recipient_id = data.get("recipient_id")
                await manager.send_to_user(recipient_id, {
                    "type": "typing",
                    "sender_id": user.id,
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
```

### Frontend WebSocket Hook

```typescript
// frontend/src/hooks/useWebSocket.ts

import { useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';

export function useWebSocket(onMessage: (data: any) => void) {
  const { token } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!token) return;

    const ws = new WebSocket(`ws://localhost:8000/api/ws?token=${token}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage(data);
    };

    ws.onclose = () => {
      // Reconnect logic
      setTimeout(() => {
        // Attempt reconnect
      }, 3000);
    };

    return () => {
      ws.close();
    };
  }, [token, onMessage]);

  const send = useCallback((data: any) => {
    wsRef.current?.send(JSON.stringify(data));
  }, []);

  return { send };
}
```

---

## 8. Pre-Implementation Checklist

Before starting each phase:

### Phase 0
- [ ] Discord application created
- [ ] OAuth redirect URIs configured
- [ ] `.env` updated with Discord credentials
- [ ] Test fixtures added to conftest.py
- [ ] `make generate-types` works

### Phase 1
- [ ] Phase 0 complete and merged
- [ ] Discord bot application configured
- [ ] Bot token generated
- [ ] Bot Dockerfile created
- [ ] docker-compose updated with bot service

### Phase 2
- [ ] Phase 1 complete and merged
- [ ] WebSocket endpoint implemented
- [ ] Frontend WebSocket hook created
- [ ] Real-time messaging tested locally

### Phase 3
- [ ] Phase 2 complete and merged
- [ ] Stripe account created (test mode)
- [ ] Stripe Connect enabled
- [ ] Webhook endpoint configured

---

## Quick Reference: File Changes Per Phase

### Phase 0 Touches
- `backend/app/api/routes/` - 4 new files
- `backend/app/models/` - 3 new/modified files
- `backend/app/schemas/` - 2 new files
- `backend/alembic/versions/` - 4 migrations
- `frontend/src/app/(public)/` - 1 new page
- `frontend/src/app/(protected)/settings/` - modified
- `frontend/src/lib/` - 2 new files

### Phase 1 Touches
- `backend/app/api/routes/` - 2 new files
- `backend/app/models/` - 2 new files
- `backend/app/services/matching/` - new directory
- `backend/alembic/versions/` - 2 migrations
- `discord-bot/` - entire new directory
- `frontend/src/app/(protected)/matches/` - new page
- `docker-compose.yml` - add bot service

### Phase 2 Touches
- `backend/app/api/routes/` - 3 new files
- `backend/app/models/` - 5 new files
- `backend/app/services/reputation/` - new directory
- `backend/alembic/versions/` - 4 migrations
- `frontend/src/app/(protected)/trades/` - new page
- `frontend/src/app/(protected)/messages/` - new page
- `frontend/src/hooks/useWebSocket.ts` - new hook

### Phase 3 Touches
- `backend/app/api/routes/` - 3 new files
- `backend/app/models/` - 3 new files
- `backend/app/services/signals/` - new directory
- `backend/app/services/escrow/` - new directory
- `backend/alembic/versions/` - 3 migrations
- `frontend/src/app/(protected)/signals/` - new page
- `frontend/src/app/(protected)/stores/` - new page (LGS)
