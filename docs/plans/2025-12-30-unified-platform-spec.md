# Dualcaster Deals: Unified Platform Specification

**Date:** 2025-12-30
**Status:** Draft
**Scope:** Complete platform vision integrating intelligence, social trading, and business tools
**Supersedes:** `2025-12-30-social-trading-spec.md`, `2025-12-29-recommendation-outcome-tracking-design.md`

---

## Executive Summary

Transform Dualcaster Deals from a price tracking tool into **the premier intelligence and trading platform for Magic: The Gathering**.

**The Vision:** Bloomberg Terminal meets Robinhood meets Discord for MTG.

### What We're Building

| Layer | Purpose | Key Features |
|-------|---------|--------------|
| **Intelligence** | Make traders smarter | Price tracking, signals, predictions, outcome tracking |
| **Discovery** | Connect supply and demand | Have/want lists, matching, search |
| **Transaction** | Facilitate trades | Proposals, messaging, completion flow |
| **Trust** | Enable confidence | Reputation, reviews, verification |
| **Community** | Distribution + stickiness | Discord integration, LGS network |
| **Business** | Serve shops | Inventory sync, smart buylist, local matching |

### Strategic Positioning

| Competitor | Their Moat | Their Gap | Our Play |
|------------|-----------|-----------|----------|
| TCGPlayer | Transactions, trust | 12% fees, no community | Better prices, social layer |
| MTGGoldfish | Content, SEO | Static, no trading | Actionable intelligence |
| Cardsphere | Trading focus | Tiny community, clunky UX | Modern UX, bigger network |
| Moxfield | Deck building, UX | No trading, no prices | Trading layer on top |
| Discord | Community, real-time | Manual, no tracking | Automate + track |

**Our Moat:** Outcome tracking creates ground truth data. Network effects from the social graph. Discord presence in hundreds of servers.

---

## Design Decisions Log

Decisions made during spec development:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ID type | Keep integers | Zero migration, use hashids for public URLs |
| Public URL encoding | Hashids | Reversible, no enumeration, professional appearance |
| Want list | Extend existing table | One source of truth, existing alerts still work |
| Want list pricing | Separate fields | `target_price` (alerts) vs `max_trade_value` (trading) |
| Have list | Linked to inventory | Condition inherited, auto-remove when sold, can't list cards you don't own |
| Condition matching | Quality score penalty | Surface near-matches ranked lower, let users filter strictly if preferred |
| Signal tracking | Both implicit + explicit | Explicit (clicked "follow") = 2x weight, implicit (bought during signal) = 0.5x |
| User-generated signals | Progressive unlock | Private-only at start, unlock public at reputation threshold |
| Reputation negative events | Include with decay | Failed trades, blocks, disputes reduce score; old negatives fade |
| Distribution strategy | Discord-first | Meet users where they are, website for depth |

---

## Architecture Overview

### System Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                         │
├────────────────────┬────────────────────┬───────────────────────────────────┤
│    Web App         │    Mobile (PWA)    │         Discord Bot               │
│    Next.js 14      │    Same codebase   │         discord.py                │
└────────────────────┴────────────────────┴───────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                     │
│                         FastAPI + JWT Auth                                   │
│                                                                              │
│  /api/v1/                                                                    │
│  ├── auth/          Authentication + OAuth                                   │
│  ├── users/         Profiles, settings, connections                         │
│  ├── cards/         Card data, prices, recommendations                       │
│  ├── inventory/     User collections                                         │
│  ├── want-list/     Want list management                                     │
│  ├── have-list/     Have list management                                     │
│  ├── matches/       Trade matching                                           │
│  ├── trades/        Trade proposals, messaging                               │
│  ├── reputation/    Reviews, scores                                          │
│  ├── discord/       Bot-specific endpoints                                   │
│  └── business/      LGS tools (future)                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
┌──────────────────────┐ ┌──────────────────┐ ┌──────────────────────────────┐
│     PostgreSQL       │ │      Redis       │ │          Celery              │
│                      │ │                  │ │                              │
│ • Users + profiles   │ │ • Session cache  │ │ • Price ingestion            │
│ • Cards + prices     │ │ • Rate limiting  │ │ • Match computation          │
│ • Inventory          │ │ • Match cache    │ │ • Outcome evaluation         │
│ • Want/have lists    │ │ • Real-time pub  │ │ • Notification delivery      │
│ • Trades + messages  │ │                  │ │ • Reputation recalc          │
│ • Reputation         │ │                  │ │                              │
└──────────────────────┘ └──────────────────┘ └──────────────────────────────┘
```

### Data Flow: Trade Matching

```
User updates have/want list
            │
            ▼
┌──────────────────────────────────────────────────────────────┐
│  INVALIDATION                                                 │
│  Mark existing matches involving this user as stale          │
└──────────────────────────────────────────────────────────────┘
            │
            ▼ (async, via Celery)
┌──────────────────────────────────────────────────────────────┐
│  MATCHING ENGINE                                              │
│                                                               │
│  1. Get user's want list (cards, conditions, max values)     │
│  2. Find users with matching have list items                 │
│  3. Filter: is_public=true, not blocked, active recently     │
│  4. For each candidate:                                      │
│     a. Check reverse match (do they want what I have?)       │
│     b. Calculate value balance                               │
│     c. Apply condition/language penalties                    │
│     d. Apply trust bonus (verified, high reputation)         │
│     e. Apply locality bonus (same server, nearby)            │
│     f. Compute final quality score (0-100)                   │
│  5. Store top 50 matches per user                            │
└──────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────┐
│  NOTIFICATION                                                 │
│  If new high-quality match (>70), notify via preferred channel│
└──────────────────────────────────────────────────────────────┘
```

---

## Phase 0: Foundation

**Timeline:** 4-6 weeks
**Goal:** Infrastructure that enables everything else
**Theme:** "Make the invisible visible"

### 0.1 Public Content Infrastructure

**Problem:** The app requires login for everything. Zero SEO, zero shareability.

**Solution:** Public card pages, Open Graph tags, sitemap.

#### Database Changes

None required.

#### API Changes

```python
# backend/app/api/routes/cards.py

# EXISTING (requires auth):
@router.get("/{card_id}", response_model=CardResponse)
async def get_card(card_id: int, current_user: User = Depends(get_current_user)):
    ...

# NEW (public):
@router.get("/public/{card_id}", response_model=CardPublicResponse)
async def get_card_public(card_id: int, db: AsyncSession = Depends(get_db)):
    """Public card page - no auth required."""
    card = await card_repo.get_by_id(db, card_id)
    if not card:
        raise HTTPException(404, "Card not found")

    # Get latest price, recommendation, want count
    price = await price_repo.get_latest(db, card_id)
    recommendation = await rec_repo.get_active_for_card(db, card_id)
    want_count = await want_list_repo.count_wanting(db, card_id)

    return CardPublicResponse(
        card=card,
        current_price=price,
        recommendation=recommendation,
        want_count=want_count,
        # Outcome stats if recommendation exists
        recommendation_accuracy=recommendation.accuracy_score_end if recommendation else None
    )


# NEW: Public hashid-based endpoint
@router.get("/c/{hashid}", response_model=CardPublicResponse)
async def get_card_by_hashid(hashid: str, db: AsyncSession = Depends(get_db)):
    """Public card page by hashid URL."""
    card_id = decode_hashid(hashid)
    return await get_card_public(card_id, db)
```

#### Frontend Changes

```typescript
// frontend/src/app/cards/[id]/page.tsx

// This page should be:
// 1. Server-side rendered (for SEO)
// 2. No auth required
// 3. Include Open Graph meta tags

export async function generateMetadata({ params }): Promise<Metadata> {
  const card = await getCardPublic(params.id);

  return {
    title: `${card.name} Price & Trading | Dualcaster Deals`,
    description: `${card.name} is $${card.currentPrice}. ${card.wantCount} traders want this card.`,
    openGraph: {
      title: card.name,
      description: `$${card.currentPrice} | ${card.setName}`,
      images: [card.imageUrl],
      type: 'website',
    },
    twitter: {
      card: 'summary_large_image',
      title: card.name,
      description: `$${card.currentPrice} | ${card.wantCount} traders want this`,
      images: [card.imageUrl],
    },
  };
}
```

#### Sitemap Generation

```python
# backend/app/api/routes/seo.py

@router.get("/sitemap.xml", response_class=Response)
async def sitemap(db: AsyncSession = Depends(get_db)):
    """Generate sitemap for all public card pages."""
    cards = await card_repo.get_all_with_prices(db, limit=50000)

    urls = []
    for card in cards:
        urls.append(f"""
        <url>
            <loc>https://dualcasterdeals.com/cards/{card.id}</loc>
            <lastmod>{card.updated_at.isoformat()}</lastmod>
            <changefreq>daily</changefreq>
            <priority>0.8</priority>
        </url>
        """)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        {''.join(urls)}
    </urlset>
    """
    return Response(content=xml, media_type="application/xml")
```

### 0.2 Hashids Integration

**Problem:** Sequential integer IDs leak business intelligence and look unprofessional.

**Solution:** Encode IDs for public-facing URLs.

#### Implementation

```python
# backend/app/core/hashids.py

from hashids import Hashids

# Different salts for different entity types (security)
_hashers = {
    'card': Hashids(salt='dualcaster-cards-v1', min_length=6),
    'user': Hashids(salt='dualcaster-users-v1', min_length=8),
    'trade': Hashids(salt='dualcaster-trades-v1', min_length=10),
    'match': Hashids(salt='dualcaster-matches-v1', min_length=8),
}

def encode_id(entity_type: str, id: int) -> str:
    """Encode an integer ID to a hashid string."""
    return _hashers[entity_type].encode(id)

def decode_id(entity_type: str, hashid: str) -> int | None:
    """Decode a hashid string to an integer ID."""
    result = _hashers[entity_type].decode(hashid)
    return result[0] if result else None


# Usage in schemas - auto-encode on serialization
class CardPublicResponse(BaseModel):
    id: int
    hashid: str = ""
    name: str
    # ...

    @model_validator(mode='after')
    def compute_hashid(self):
        self.hashid = encode_id('card', self.id)
        return self
```

### 0.3 User Profile Extensions

**Problem:** Users can't see each other. No public presence.

**Solution:** Extend user model with profile fields and privacy controls.

#### Database Migration

```python
# alembic/versions/YYYYMMDD_001_user_profile_extensions.py

def upgrade():
    # Profile fields
    op.add_column('users', sa.Column('is_public', sa.Boolean(), default=False))
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(500), nullable=True))

    # Location
    op.add_column('users', sa.Column('location_display', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('latitude', sa.Numeric(10, 8), nullable=True))
    op.add_column('users', sa.Column('longitude', sa.Numeric(11, 8), nullable=True))
    op.add_column('users', sa.Column('trade_radius_miles', sa.Integer(), default=50))

    # Activity
    op.add_column('users', sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('profile_views', sa.Integer(), default=0))

    # Privacy granularity
    op.add_column('users', sa.Column('show_inventory_value', sa.Boolean(), default=False))
    op.add_column('users', sa.Column('show_want_list', sa.Boolean(), default=True))
    op.add_column('users', sa.Column('show_have_list', sa.Boolean(), default=True))
    op.add_column('users', sa.Column('show_trade_history', sa.Boolean(), default=False))

    # Indexes
    op.create_index('ix_users_is_public', 'users', ['is_public'])
    op.create_index('ix_users_location', 'users', ['latitude', 'longitude'])
    op.create_index('ix_users_last_active', 'users', ['last_active_at'])
```

#### Model Update

```python
# backend/app/models/user.py

class User(Base):
    __tablename__ = "users"

    # ... existing fields ...

    # Profile
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Location
    location_display: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 8), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(11, 8), nullable=True)
    trade_radius_miles: Mapped[int] = mapped_column(Integer, default=50)

    # Activity
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    profile_views: Mapped[int] = mapped_column(Integer, default=0)

    # Privacy
    show_inventory_value: Mapped[bool] = mapped_column(Boolean, default=False)
    show_want_list: Mapped[bool] = mapped_column(Boolean, default=True)
    show_have_list: Mapped[bool] = mapped_column(Boolean, default=True)
    show_trade_history: Mapped[bool] = mapped_column(Boolean, default=False)
```

#### API Endpoints

```python
# backend/app/api/routes/users.py

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/{username}", response_model=UserPublicProfile)
async def get_public_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Get a user's public profile."""
    user = await user_repo.get_by_username(db, username)
    if not user:
        raise HTTPException(404, "User not found")

    if not user.is_public and (not current_user or current_user.id != user.id):
        raise HTTPException(403, "This profile is private")

    # Increment view count (not for self-views)
    if current_user and current_user.id != user.id:
        await user_repo.increment_profile_views(db, user.id)

    return UserPublicProfile.from_user(user, is_own_profile=(current_user and current_user.id == user.id))


@router.patch("/me", response_model=UserPublicProfile)
async def update_profile(
    updates: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update current user's profile."""
    user = await user_repo.update(db, current_user.id, updates.model_dump(exclude_unset=True))
    return UserPublicProfile.from_user(user, is_own_profile=True)


@router.post("/me/location", response_model=UserPublicProfile)
async def set_location(
    location: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set user's location for local trading."""
    # Geocode if only display name provided
    if location.display and not location.latitude:
        coords = await geocode_service.geocode(location.display)
        location.latitude = coords.lat
        location.longitude = coords.lng

    user = await user_repo.update(db, current_user.id, {
        'location_display': location.display,
        'latitude': location.latitude,
        'longitude': location.longitude,
    })
    return UserPublicProfile.from_user(user, is_own_profile=True)


@router.get("/search", response_model=list[UserSearchResult])
async def search_users(
    q: str = Query(min_length=2),
    nearby: bool = False,
    miles: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Search for users by username or location."""
    if nearby and current_user and current_user.latitude:
        users = await user_repo.search_nearby(
            db,
            lat=current_user.latitude,
            lng=current_user.longitude,
            miles=miles,
            query=q
        )
    else:
        users = await user_repo.search_by_username(db, q, limit=20)

    return [UserSearchResult.from_user(u) for u in users]
```

### 0.4 Notification Infrastructure

**Problem:** Can't reach users outside the app.

**Solution:** Unified notification service with multiple channels.

#### Database Tables

```python
# alembic/versions/YYYYMMDD_002_notification_preferences.py

def upgrade():
    op.create_table(
        'notification_preferences',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),

        # Email
        sa.Column('email_enabled', sa.Boolean(), default=True),
        sa.Column('email_price_alerts', sa.Boolean(), default=True),
        sa.Column('email_trade_matches', sa.Boolean(), default=True),
        sa.Column('email_trade_proposals', sa.Boolean(), default=True),
        sa.Column('email_messages', sa.Boolean(), default=True),
        sa.Column('email_weekly_digest', sa.Boolean(), default=True),

        # Discord
        sa.Column('discord_enabled', sa.Boolean(), default=True),
        sa.Column('discord_price_alerts', sa.Boolean(), default=True),
        sa.Column('discord_trade_matches', sa.Boolean(), default=True),
        sa.Column('discord_trade_proposals', sa.Boolean(), default=True),

        # Quiet hours
        sa.Column('quiet_hours_enabled', sa.Boolean(), default=False),
        sa.Column('quiet_hours_start', sa.Time(), nullable=True),
        sa.Column('quiet_hours_end', sa.Time(), nullable=True),
        sa.Column('quiet_hours_timezone', sa.String(50), default='UTC'),

        # Rate limits
        sa.Column('max_emails_per_day', sa.Integer(), default=10),

        sa.Column('updated_at', sa.DateTime(timezone=True), default=func.now()),
    )
```

#### Notification Service

```python
# backend/app/services/notifications/service.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional

class NotificationType(str, Enum):
    PRICE_ALERT = "price_alert"
    TRADE_MATCH = "trade_match"
    TRADE_PROPOSAL = "trade_proposal"
    TRADE_ACCEPTED = "trade_accepted"
    MESSAGE = "message"
    RECOMMENDATION = "recommendation"
    OUTCOME_EVALUATED = "outcome_evaluated"

class NotificationChannel(str, Enum):
    EMAIL = "email"
    DISCORD_DM = "discord_dm"
    DISCORD_WEBHOOK = "discord_webhook"
    PUSH = "push"  # Future

@dataclass
class NotificationPayload:
    type: NotificationType
    user_id: int
    title: str
    body: str
    data: dict
    url: Optional[str] = None

class NotificationService:
    def __init__(self, db: AsyncSession, email_client, discord_client):
        self.db = db
        self.email = email_client
        self.discord = discord_client

    async def send(self, payload: NotificationPayload) -> dict[NotificationChannel, bool]:
        """Send notification through all enabled channels."""
        prefs = await self._get_preferences(payload.user_id)
        results = {}

        # Check quiet hours
        if self._in_quiet_hours(prefs):
            # Queue for later
            await self._queue_for_later(payload, prefs)
            return {NotificationChannel.EMAIL: False, NotificationChannel.DISCORD_DM: False}

        # Email
        if self._should_send_email(prefs, payload.type):
            results[NotificationChannel.EMAIL] = await self._send_email(payload)

        # Discord DM
        if self._should_send_discord(prefs, payload.type):
            results[NotificationChannel.DISCORD_DM] = await self._send_discord_dm(payload)

        # Record notification
        await self._record_notification(payload, results)

        return results

    def _should_send_email(self, prefs, notification_type: NotificationType) -> bool:
        if not prefs.email_enabled:
            return False

        mapping = {
            NotificationType.PRICE_ALERT: prefs.email_price_alerts,
            NotificationType.TRADE_MATCH: prefs.email_trade_matches,
            NotificationType.TRADE_PROPOSAL: prefs.email_trade_proposals,
            NotificationType.MESSAGE: prefs.email_messages,
        }
        return mapping.get(notification_type, True)

    async def _send_email(self, payload: NotificationPayload) -> bool:
        user = await user_repo.get_by_id(self.db, payload.user_id)
        try:
            await self.email.send(
                to=user.email,
                subject=payload.title,
                template=f"notifications/{payload.type.value}.html",
                context={"payload": payload, "user": user}
            )
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False

    async def _send_discord_dm(self, payload: NotificationPayload) -> bool:
        # Get linked Discord account
        discord_account = await connected_accounts_repo.get_discord(self.db, payload.user_id)
        if not discord_account:
            return False

        try:
            await self.discord.send_dm(
                user_id=discord_account.provider_user_id,
                embed=self._build_discord_embed(payload)
            )
            return True
        except Exception as e:
            logger.error(f"Discord DM failed: {e}")
            return False
```

### 0.5 Analytics Instrumentation

**Problem:** No visibility into user behavior.

**Solution:** Event tracking for key actions.

```python
# backend/app/services/analytics.py

from enum import Enum
from datetime import datetime

class EventType(str, Enum):
    # User events
    USER_SIGNUP = "user.signup"
    USER_LOGIN = "user.login"
    PROFILE_VIEWED = "profile.viewed"
    PROFILE_UPDATED = "profile.updated"

    # Card events
    CARD_VIEWED = "card.viewed"
    CARD_SEARCHED = "card.searched"

    # List events
    WANT_LIST_ADD = "want_list.add"
    WANT_LIST_REMOVE = "want_list.remove"
    HAVE_LIST_ADD = "have_list.add"
    HAVE_LIST_REMOVE = "have_list.remove"

    # Trading events
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
    DISCORD_COMMAND = "discord.command"

class AnalyticsService:
    async def track(
        self,
        event: EventType,
        user_id: Optional[int] = None,
        properties: dict = None,
        context: dict = None
    ):
        """Track an analytics event."""
        event_data = {
            "event": event.value,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "properties": properties or {},
            "context": context or {},
        }

        # Store locally for now, can integrate with Mixpanel/Amplitude later
        await self._store_event(event_data)

        # Update aggregates
        await self._update_aggregates(event, user_id, properties)
```

### 0.6 Discord Account Linking

**Problem:** OAuth exists but linking isn't complete.

**Solution:** Full bidirectional link between Discord and Dualcaster accounts.

#### Database Table

```python
# alembic/versions/YYYYMMDD_003_connected_accounts.py

def upgrade():
    op.create_table(
        'connected_accounts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),  # 'discord', 'moxfield', 'google'
        sa.Column('provider_user_id', sa.String(255), nullable=False),
        sa.Column('provider_username', sa.String(255), nullable=True),
        sa.Column('provider_display_name', sa.String(255), nullable=True),
        sa.Column('provider_avatar_url', sa.Text(), nullable=True),
        sa.Column('access_token_encrypted', sa.Text(), nullable=True),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scopes', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('metadata', sa.JSON(), default={}),
        sa.Column('connected_at', sa.DateTime(timezone=True), default=func.now()),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_primary', sa.Boolean(), default=False),
        sa.Column('verified', sa.Boolean(), default=False),
    )

    op.create_index('ix_connected_accounts_user', 'connected_accounts', ['user_id'])
    op.create_index('ix_connected_accounts_provider', 'connected_accounts', ['provider', 'provider_user_id'], unique=True)
```

---

## Phase 1: Intelligence + Distribution

**Timeline:** 6-8 weeks (after Phase 0)
**Goal:** Best-in-class price intelligence distributed via Discord
**Theme:** "Meet users where they are"

### 1.1 Have List (Linked to Inventory)

#### Database Table

```python
# alembic/versions/YYYYMMDD_004_have_list.py

def upgrade():
    op.create_table(
        'have_list_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), sa.ForeignKey('inventory_items.id', ondelete='CASCADE'), nullable=False),

        # Trading preferences
        sa.Column('min_trade_value', sa.Numeric(10, 2), nullable=True),
        sa.Column('trade_for_wants_only', sa.Boolean(), default=False),
        sa.Column('notes', sa.Text(), nullable=True),

        # Status
        sa.Column('is_active', sa.Boolean(), default=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), default=func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), default=func.now(), onupdate=func.now()),
    )

    op.create_index('ix_have_list_user_active', 'have_list_items', ['user_id', 'is_active'])
    op.create_index('ix_have_list_inventory', 'have_list_items', ['inventory_item_id'], unique=True)
```

#### Model

```python
# backend/app/models/have_list.py

class HaveListItem(Base):
    """Card from inventory marked as available for trade."""

    __tablename__ = "have_list_items"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False)

    # Trading preferences
    min_trade_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    trade_for_wants_only: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="have_list_items")
    inventory_item: Mapped["InventoryItem"] = relationship("InventoryItem", back_populates="have_list_item")

    # Computed properties (from inventory)
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
```

### 1.2 Want List Extensions

#### Database Migration

```python
# alembic/versions/YYYYMMDD_005_want_list_extensions.py

def upgrade():
    # Trading-specific fields
    op.add_column('want_list_items', sa.Column('quantity', sa.Integer(), default=1))
    op.add_column('want_list_items', sa.Column('condition_min', sa.String(20), default='LP'))
    op.add_column('want_list_items', sa.Column('is_foil_required', sa.Boolean(), default=False))
    op.add_column('want_list_items', sa.Column('language', sa.String(10), default='EN'))
    op.add_column('want_list_items', sa.Column('max_trade_value', sa.Numeric(10, 2), nullable=True))

    # Visibility for trading
    op.add_column('want_list_items', sa.Column('is_public', sa.Boolean(), default=True))
```

### 1.3 Discord Bot Foundation

#### Bot Structure

```
discord-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py                     # Entry point
│   ├── config.py                   # Environment config
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── client.py               # HTTP client to Dualcaster API
│   │   └── models.py               # Response models
│   │
│   ├── cogs/
│   │   ├── __init__.py
│   │   ├── account.py              # /dd link, /dd unlink
│   │   ├── prices.py               # /dd price <card>
│   │   ├── wants.py                # /dd want add/remove/list
│   │   ├── haves.py                # /dd have add/remove/list
│   │   ├── matches.py              # /dd match, /dd match server
│   │   └── help.py                 # /dd help
│   │
│   ├── ui/
│   │   ├── embeds.py               # Rich embed builders
│   │   ├── views.py                # Button/select menus
│   │   └── pagination.py           # Paginated responses
│   │
│   └── tasks/
│       ├── price_alerts.py         # Background price monitoring
│       └── match_notifications.py  # New match alerts
│
├── Dockerfile
├── requirements.txt
└── docker-compose.yml
```

#### Core Commands

```python
# discord-bot/bot/cogs/prices.py

class PricesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = DualcasterAPI()

    @app_commands.command(name="price", description="Get card prices")
    @app_commands.describe(card="Card name to look up")
    async def price(self, interaction: discord.Interaction, card: str):
        await interaction.response.defer()

        # Search for card
        results = await self.api.search_cards(card, limit=5)

        if not results:
            await interaction.followup.send(f"No cards found matching '{card}'")
            return

        if len(results) == 1:
            # Single result - show full details
            card_data = await self.api.get_card(results[0].id)
            embed = self.build_price_embed(card_data)
            view = PriceActionsView(card_data)
            await interaction.followup.send(embed=embed, view=view)
        else:
            # Multiple results - show picker
            view = CardPickerView(results, callback=self._show_price)
            await interaction.followup.send("Multiple cards found:", view=view)

    def build_price_embed(self, card: CardData) -> discord.Embed:
        embed = discord.Embed(
            title=card.name,
            url=f"https://dualcasterdeals.com/cards/{card.hashid}",
            color=self.get_rarity_color(card.rarity)
        )

        embed.set_thumbnail(url=card.image_url)

        # Prices
        embed.add_field(
            name="Prices",
            value=f"**TCGPlayer:** ${card.price_tcg:.2f}\n"
                  f"**Card Kingdom:** ${card.price_ck:.2f}\n"
                  f"**Trend:** {card.trend_emoji} {card.trend_pct:+.1f}% (7d)",
            inline=True
        )

        # Recommendation if exists
        if card.recommendation:
            rec = card.recommendation
            acc_str = f" ({rec.accuracy_score_end*100:.0f}% accurate)" if rec.accuracy_score_end else ""
            embed.add_field(
                name=f"{rec.action} Signal",
                value=f"Confidence: {rec.confidence*100:.0f}%{acc_str}\n"
                      f"Target: ${rec.target_price:.2f}",
                inline=True
            )

        # Want count
        if card.want_count > 0:
            embed.add_field(
                name="Demand",
                value=f"{card.want_count} traders want this",
                inline=True
            )

        embed.set_footer(text="Dualcaster Deals")

        return embed


class PriceActionsView(discord.ui.View):
    def __init__(self, card: CardData):
        super().__init__(timeout=300)
        self.card = card

    @discord.ui.button(label="Add to Want List", style=discord.ButtonStyle.primary, emoji="📋")
    async def add_to_wants(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is linked
        user = await api.get_user_by_discord(interaction.user.id)
        if not user:
            await interaction.response.send_message(
                "Link your account first with `/dd link`",
                ephemeral=True
            )
            return

        await api.add_to_want_list(user.id, self.card.id)
        await interaction.response.send_message(
            f"Added **{self.card.name}** to your want list!",
            ephemeral=True
        )

    @discord.ui.button(label="Set Price Alert", style=discord.ButtonStyle.secondary, emoji="🔔")
    async def set_alert(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PriceAlertModal(self.card)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="View on Web", style=discord.ButtonStyle.link, url="")
    async def view_web(self, interaction: discord.Interaction, button: discord.ui.Button):
        # URL is set dynamically
        pass

    def __init__(self, card: CardData):
        super().__init__(timeout=300)
        self.card = card
        # Set the URL for the link button
        self.children[2].url = f"https://dualcasterdeals.com/cards/{card.hashid}"
```

#### Bot API Endpoints

```python
# backend/app/api/routes/discord.py

router = APIRouter(prefix="/discord", tags=["discord"])

# Bot authentication via API key (not user JWT)
async def verify_bot_token(authorization: str = Header(...)):
    if authorization != f"Bot {settings.DISCORD_BOT_API_KEY}":
        raise HTTPException(401, "Invalid bot token")

@router.get("/user/{discord_id}", response_model=UserBotResponse)
async def get_user_by_discord(
    discord_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_bot_token)
):
    """Look up Dualcaster user by Discord ID."""
    account = await connected_accounts_repo.get_by_provider(db, "discord", discord_id)
    if not account:
        raise HTTPException(404, "User not linked")

    user = await user_repo.get_by_id(db, account.user_id)
    return UserBotResponse.from_user(user)


@router.post("/user/{discord_id}/want-list", response_model=WantListItemResponse)
async def add_to_want_list_by_discord(
    discord_id: str,
    item: WantListItemCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_bot_token)
):
    """Add card to want list via Discord."""
    account = await connected_accounts_repo.get_by_provider(db, "discord", discord_id)
    if not account:
        raise HTTPException(404, "User not linked")

    want_item = await want_list_repo.create(db, account.user_id, item)
    return WantListItemResponse.from_model(want_item)


@router.get("/guild/{guild_id}/matches", response_model=list[MatchResponse])
async def get_server_matches(
    guild_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_bot_token)
):
    """Find trade matches among users in a Discord server."""
    # Get all linked users in this server
    members = await discord_guild_members_repo.get_linked_members(db, guild_id)
    user_ids = [m.user_id for m in members if m.user_id]

    if len(user_ids) < 2:
        return []

    # Find matches between these users
    matches = await matching_service.find_matches_between_users(db, user_ids)

    return [MatchResponse.from_match(m) for m in matches]
```

### 1.4 Matching Algorithm

```python
# backend/app/services/matching/engine.py

from dataclasses import dataclass
from typing import Optional
from decimal import Decimal

# Condition ranking for quality score calculation
CONDITION_RANK = {
    'NM': 5, 'LP': 4, 'MP': 3, 'HP': 2, 'DMG': 1
}

@dataclass
class MatchCandidate:
    user_id: int
    username: str
    cards_they_have_i_want: list[dict]
    cards_i_have_they_want: list[dict]
    my_value: Decimal
    their_value: Decimal
    quality_score: int  # 0-100
    distance_miles: Optional[float]
    is_local: bool
    shared_servers: list[str]  # Discord server names

@dataclass
class QualityFactors:
    value_balance: int      # 0-40 points
    total_value: int        # 0-20 points
    card_variety: int       # 0-15 points
    condition_match: int    # 0-10 points (-penalty for mismatches)
    trust_bonus: int        # 0-10 points
    locality_bonus: int     # 0-5 points

class MatchingEngine:
    def __init__(self, db: AsyncSession, price_service: PriceService):
        self.db = db
        self.prices = price_service

    async def find_matches_for_user(
        self,
        user_id: int,
        min_quality: int = 30,
        max_results: int = 50,
        local_only: bool = False,
        server_only: Optional[str] = None  # Discord guild ID
    ) -> list[MatchCandidate]:
        """Find trade matches for a user."""

        # Get user's lists
        user = await user_repo.get_by_id(self.db, user_id)
        my_wants = await want_list_repo.get_public_for_user(self.db, user_id)
        my_haves = await have_list_repo.get_active_for_user(self.db, user_id)

        if not my_wants or not my_haves:
            return []

        my_want_card_ids = {w.card_id for w in my_wants}
        my_have_card_ids = {h.inventory_item.card_id for h in my_haves}

        # Find candidates who have what I want
        candidates = await self._find_candidates_with_cards(my_want_card_ids, user_id)

        # Filter by server if specified
        if server_only:
            server_user_ids = await self._get_server_user_ids(server_only)
            candidates = [c for c in candidates if c.user_id in server_user_ids]

        # Filter by location if specified
        if local_only and user.latitude:
            candidates = await self._filter_by_distance(candidates, user, user.trade_radius_miles)

        matches = []
        for candidate in candidates:
            match = await self._evaluate_match(
                user, my_wants, my_haves,
                candidate
            )
            if match and match.quality_score >= min_quality:
                matches.append(match)

        # Sort by quality
        matches.sort(key=lambda m: m.quality_score, reverse=True)

        return matches[:max_results]

    async def _evaluate_match(
        self,
        user: User,
        my_wants: list[WantListItem],
        my_haves: list[HaveListItem],
        candidate: User
    ) -> Optional[MatchCandidate]:
        """Evaluate match quality between two users."""

        # Get candidate's lists
        their_wants = await want_list_repo.get_public_for_user(self.db, candidate.id)
        their_haves = await have_list_repo.get_active_for_user(self.db, candidate.id)

        # What can I get from them?
        cards_for_me = []
        for their_have in their_haves:
            matching_want = self._find_matching_want(their_have, my_wants)
            if matching_want:
                price = await self.prices.get_price(their_have.inventory_item.card_id)
                cards_for_me.append({
                    'card_id': their_have.inventory_item.card_id,
                    'card_name': their_have.card.name,
                    'condition': their_have.condition,
                    'is_foil': their_have.is_foil,
                    'value': price,
                    'condition_gap': self._condition_gap(their_have.condition, matching_want.condition_min),
                })

        if not cards_for_me:
            return None  # One-way match, skip for now

        # What can they get from me?
        cards_for_them = []
        for my_have in my_haves:
            matching_want = self._find_matching_want(my_have, their_wants)
            if matching_want:
                price = await self.prices.get_price(my_have.inventory_item.card_id)
                cards_for_them.append({
                    'card_id': my_have.inventory_item.card_id,
                    'card_name': my_have.card.name,
                    'condition': my_have.condition,
                    'is_foil': my_have.is_foil,
                    'value': price,
                    'condition_gap': self._condition_gap(my_have.condition, matching_want.condition_min),
                })

        if not cards_for_them:
            return None  # One-way match

        # Calculate values
        my_value = sum(c['value'] for c in cards_for_me)
        their_value = sum(c['value'] for c in cards_for_them)

        # Calculate quality score
        factors = self._calculate_quality_factors(
            my_value, their_value,
            cards_for_me, cards_for_them,
            user, candidate
        )
        quality_score = sum([
            factors.value_balance,
            factors.total_value,
            factors.card_variety,
            factors.condition_match,
            factors.trust_bonus,
            factors.locality_bonus,
        ])

        # Distance calculation
        distance = None
        is_local = False
        if user.latitude and candidate.latitude:
            distance = self._haversine_distance(
                user.latitude, user.longitude,
                candidate.latitude, candidate.longitude
            )
            is_local = distance <= user.trade_radius_miles

        # Shared Discord servers
        shared_servers = await self._get_shared_servers(user.id, candidate.id)

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
            shared_servers=shared_servers,
        )

    def _calculate_quality_factors(
        self,
        my_value: Decimal,
        their_value: Decimal,
        cards_for_me: list,
        cards_for_them: list,
        user: User,
        candidate: User,
    ) -> QualityFactors:
        """Calculate individual quality score components."""

        # Value balance: 40 points max, 1.0 ratio = full points
        if my_value == 0 or their_value == 0:
            value_balance = 0
        else:
            ratio = min(my_value, their_value) / max(my_value, their_value)
            value_balance = int(ratio * 40)

        # Total value: 20 points max, logarithmic scale
        total = float(my_value + their_value)
        # $50 = 10 points, $200 = 15 points, $500+ = 20 points
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

        # Condition match: 10 points max, -5 per grade below minimum
        condition_penalties = sum(c['condition_gap'] * 5 for c in cards_for_me if c['condition_gap'] < 0)
        condition_penalties += sum(c['condition_gap'] * 5 for c in cards_for_them if c['condition_gap'] < 0)
        condition_match = max(-10, min(10, 10 + condition_penalties))

        # Trust bonus: 10 points max based on reputation
        # (Placeholder - will be implemented with reputation system)
        trust_bonus = 0

        # Locality bonus: 5 points if in same area or server
        locality_bonus = 0
        # Will be calculated based on shared servers / distance

        return QualityFactors(
            value_balance=value_balance,
            total_value=total_value,
            card_variety=card_variety,
            condition_match=condition_match,
            trust_bonus=trust_bonus,
            locality_bonus=locality_bonus,
        )

    def _condition_gap(self, have_condition: str, want_min: str) -> int:
        """Calculate gap between have condition and want minimum. Negative = below minimum."""
        have_rank = CONDITION_RANK.get(have_condition, 3)
        want_rank = CONDITION_RANK.get(want_min, 3)
        return have_rank - want_rank

    def _find_matching_want(self, have: HaveListItem, wants: list[WantListItem]) -> Optional[WantListItem]:
        """Find a want list entry that matches a have list item."""
        for want in wants:
            if want.card_id != have.inventory_item.card_id:
                continue

            # Check foil requirement
            if want.is_foil_required and not have.is_foil:
                continue

            # Check language
            if want.language != 'ANY' and want.language != have.inventory_item.language:
                continue

            # Condition is checked but not filtered here (affects quality score instead)
            return want

        return None
```

---

## Phase 2: Social + Trust

**Timeline:** 6-8 weeks (after Phase 1)
**Goal:** Trade proposals, messaging, reputation system
**Theme:** "Trust at scale"

### 2.1 Trade Proposals

#### Database Tables

```python
# alembic/versions/YYYYMMDD_006_trading_tables.py

def upgrade():
    # Trade proposal status enum
    op.execute("""
        CREATE TYPE trade_status AS ENUM (
            'draft', 'pending', 'viewed', 'accepted',
            'declined', 'countered', 'expired', 'cancelled', 'completed'
        )
    """)

    op.create_table(
        'trade_proposals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('proposer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('recipient_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.Enum('draft', 'pending', 'viewed', 'accepted', 'declined',
                                     'countered', 'expired', 'cancelled', 'completed',
                                     name='trade_status'), default='pending'),

        # What's being offered (JSON arrays of card details)
        sa.Column('proposer_offers', sa.JSON(), nullable=False),
        sa.Column('proposer_offers_value', sa.Numeric(10, 2)),
        sa.Column('proposer_wants', sa.JSON(), nullable=False),
        sa.Column('proposer_wants_value', sa.Numeric(10, 2)),

        # Cash adjustments
        sa.Column('proposer_adds_cash', sa.Numeric(10, 2), default=0),
        sa.Column('recipient_adds_cash', sa.Numeric(10, 2), default=0),

        # Communication
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('decline_reason', sa.Text(), nullable=True),

        # Counter offers
        sa.Column('parent_proposal_id', sa.Integer(), sa.ForeignKey('trade_proposals.id'), nullable=True),
        sa.Column('counter_count', sa.Integer(), default=0),

        # Completion
        sa.Column('completion_method', sa.String(50), nullable=True),
        sa.Column('completion_notes', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), default=func.now()),
        sa.Column('viewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),

        sa.CheckConstraint('proposer_id != recipient_id', name='different_users'),
    )

    op.create_index('ix_proposals_proposer', 'trade_proposals', ['proposer_id', 'status'])
    op.create_index('ix_proposals_recipient', 'trade_proposals', ['recipient_id', 'status'])
    op.create_index('ix_proposals_pending', 'trade_proposals', ['recipient_id'],
                    postgresql_where=text("status IN ('pending', 'viewed')"))
```

### 2.2 Messaging System

```python
# alembic/versions/YYYYMMDD_007_messaging.py

def upgrade():
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_a_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('user_b_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('trade_proposal_id', sa.Integer(), sa.ForeignKey('trade_proposals.id'), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True)),
        sa.Column('last_message_preview', sa.String(255)),
        sa.Column('user_a_last_read_at', sa.DateTime(timezone=True)),
        sa.Column('user_b_last_read_at', sa.DateTime(timezone=True)),
        sa.Column('user_a_archived', sa.Boolean(), default=False),
        sa.Column('user_b_archived', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), default=func.now()),

        # Ensure user_a_id < user_b_id for uniqueness
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
        sa.Column('created_at', sa.DateTime(timezone=True), default=func.now()),
    )

    op.create_index('ix_messages_conversation', 'messages', ['conversation_id', 'created_at'])
```

### 2.3 Reputation System

#### Database Tables

```python
# alembic/versions/YYYYMMDD_008_reputation.py

def upgrade():
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
        sa.Column('cash_from_a', sa.Numeric(10, 2), default=0),
        sa.Column('cash_from_b', sa.Numeric(10, 2), default=0),
        sa.Column('total_trade_value', sa.Numeric(10, 2)),
        sa.Column('completion_method', sa.String(50)),
        sa.Column('proposed_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True), default=func.now()),
        sa.Column('user_a_confirmed', sa.Boolean(), default=False),
        sa.Column('user_b_confirmed', sa.Boolean(), default=False),
        sa.Column('notes', sa.Text(), nullable=True),
    )

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
        sa.Column('is_hidden', sa.Boolean(), default=False),
        sa.Column('hidden_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), default=func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),

        sa.UniqueConstraint('trade_id', 'reviewer_id'),
        sa.CheckConstraint('overall_rating BETWEEN 1 AND 5', name='valid_overall'),
        sa.CheckConstraint('communication_rating IS NULL OR communication_rating BETWEEN 1 AND 5', name='valid_comm'),
        sa.CheckConstraint('packaging_rating IS NULL OR packaging_rating BETWEEN 1 AND 5', name='valid_pack'),
        sa.CheckConstraint('accuracy_rating IS NULL OR accuracy_rating BETWEEN 1 AND 5', name='valid_acc'),
        sa.CheckConstraint('speed_rating IS NULL OR speed_rating BETWEEN 1 AND 5', name='valid_speed'),
    )

    op.create_table(
        'user_reputation',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),

        # Trade counts
        sa.Column('total_trades', sa.Integer(), default=0),
        sa.Column('trades_as_proposer', sa.Integer(), default=0),
        sa.Column('trades_as_recipient', sa.Integer(), default=0),

        # Values
        sa.Column('total_trade_value', sa.Numeric(12, 2), default=0),
        sa.Column('average_trade_value', sa.Numeric(10, 2), default=0),
        sa.Column('largest_trade_value', sa.Numeric(10, 2), default=0),

        # Reviews
        sa.Column('total_reviews', sa.Integer(), default=0),
        sa.Column('average_rating', sa.Numeric(3, 2), nullable=True),
        sa.Column('communication_avg', sa.Numeric(3, 2), nullable=True),
        sa.Column('packaging_avg', sa.Numeric(3, 2), nullable=True),
        sa.Column('accuracy_avg', sa.Numeric(3, 2), nullable=True),
        sa.Column('speed_avg', sa.Numeric(3, 2), nullable=True),
        sa.Column('positive_reviews', sa.Integer(), default=0),
        sa.Column('neutral_reviews', sa.Integer(), default=0),
        sa.Column('negative_reviews', sa.Integer(), default=0),

        # Computed score
        sa.Column('reputation_score', sa.Integer(), default=0),
        sa.Column('reputation_tier', sa.String(20), default='new'),

        # Signal following (bridge to outcome tracking)
        sa.Column('signals_followed', sa.Integer(), default=0),
        sa.Column('signals_profitable', sa.Integer(), default=0),
        sa.Column('signal_accuracy_pct', sa.Numeric(5, 2), nullable=True),

        # Negative events
        sa.Column('cancelled_trades', sa.Integer(), default=0),
        sa.Column('disputes_involved', sa.Integer(), default=0),
        sa.Column('blocks_received', sa.Integer(), default=0),

        # Activity
        sa.Column('member_since', sa.DateTime(timezone=True)),
        sa.Column('first_trade_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_trade_at', sa.DateTime(timezone=True), nullable=True),

        # Streaks
        sa.Column('current_positive_streak', sa.Integer(), default=0),
        sa.Column('longest_positive_streak', sa.Integer(), default=0),

        sa.Column('updated_at', sa.DateTime(timezone=True), default=func.now()),
    )
```

#### Reputation Calculation

```python
# backend/app/services/reputation/calculator.py

from enum import Enum

class ReputationTier(str, Enum):
    NEW = "new"           # 0-99
    BRONZE = "bronze"     # 100-299
    SILVER = "silver"     # 300-599
    GOLD = "gold"         # 600-899
    PLATINUM = "platinum" # 900-1199
    DIAMOND = "diamond"   # 1200+

class ReputationCalculator:
    """Calculate and update user reputation scores."""

    # Tier thresholds
    TIER_THRESHOLDS = {
        ReputationTier.NEW: 0,
        ReputationTier.BRONZE: 100,
        ReputationTier.SILVER: 300,
        ReputationTier.GOLD: 600,
        ReputationTier.PLATINUM: 900,
        ReputationTier.DIAMOND: 1200,
    }

    async def recalculate(self, db: AsyncSession, user_id: int) -> UserReputation:
        """Full reputation recalculation for a user."""
        rep = await self._get_or_create_reputation(db, user_id)

        # Base score from trades
        trade_score = self._calculate_trade_score(rep)

        # Review score
        review_score = self._calculate_review_score(rep)

        # Signal following score (bridge to outcome tracking)
        signal_score = self._calculate_signal_score(rep)

        # Negative events penalty
        negative_penalty = self._calculate_negative_penalty(rep)

        # Activity decay (inactive users lose reputation slowly)
        decay_multiplier = self._calculate_decay_multiplier(rep.last_trade_at)

        # Verification bonus
        verification_bonus = await self._calculate_verification_bonus(db, user_id)

        # Final score
        raw_score = trade_score + review_score + signal_score - negative_penalty + verification_bonus
        final_score = int(raw_score * decay_multiplier)
        final_score = max(0, final_score)  # Floor at 0

        # Determine tier
        tier = self._get_tier(final_score)

        # Update
        rep.reputation_score = final_score
        rep.reputation_tier = tier.value
        rep.updated_at = datetime.utcnow()

        await db.commit()
        return rep

    def _calculate_trade_score(self, rep: UserReputation) -> int:
        """Score from completed trades."""
        # Points per trade, diminishing returns
        # First 10 trades: 10 points each = 100
        # 11-50 trades: 5 points each = 200
        # 51+ trades: 2 points each

        trades = rep.total_trades
        if trades <= 10:
            return trades * 10
        elif trades <= 50:
            return 100 + (trades - 10) * 5
        else:
            return 300 + (trades - 50) * 2

    def _calculate_review_score(self, rep: UserReputation) -> int:
        """Score from reviews received."""
        if not rep.average_rating or rep.total_reviews == 0:
            return 0

        # Base: (rating - 2.5) * 20 * sqrt(reviews)
        # 5.0 rating with 100 reviews = 50 * 10 = 500 points
        # 3.0 rating with 100 reviews = 10 * 10 = 100 points

        rating_factor = (float(rep.average_rating) - 2.5) * 20
        volume_factor = min(10, rep.total_reviews ** 0.5)  # Cap at sqrt(100)

        return int(rating_factor * volume_factor)

    def _calculate_signal_score(self, rep: UserReputation) -> int:
        """Bonus for following recommendations profitably."""
        if not rep.signals_followed or rep.signals_followed < 5:
            return 0

        # Accuracy bonus: up to 100 points
        accuracy = rep.signals_profitable / rep.signals_followed
        return int(accuracy * 100)

    def _calculate_negative_penalty(self, rep: UserReputation) -> int:
        """Penalty for negative events."""
        penalty = 0
        penalty += rep.cancelled_trades * 20
        penalty += rep.disputes_involved * 50
        penalty += rep.blocks_received * 10
        return penalty

    def _calculate_decay_multiplier(self, last_trade_at: Optional[datetime]) -> float:
        """Decay multiplier for inactive users."""
        if not last_trade_at:
            return 1.0

        months_inactive = (datetime.utcnow() - last_trade_at).days / 30
        if months_inactive < 1:
            return 1.0

        # 5% decay per month of inactivity, minimum 50%
        return max(0.5, 0.95 ** months_inactive)

    async def _calculate_verification_bonus(self, db: AsyncSession, user_id: int) -> int:
        """Bonus for verified identity."""
        user = await user_repo.get_by_id(db, user_id)
        connected = await connected_accounts_repo.get_all_for_user(db, user_id)

        bonus = 0

        # Email verified
        if user.is_verified:
            bonus += 10

        # Discord linked
        if any(c.provider == 'discord' for c in connected):
            bonus += 20

        # Multiple platforms
        if len(connected) >= 2:
            bonus += 20

        # Phone verified (future)
        # LGS vouched (future)

        return bonus

    def _get_tier(self, score: int) -> ReputationTier:
        """Determine tier from score."""
        for tier in reversed(list(ReputationTier)):
            if score >= self.TIER_THRESHOLDS[tier]:
                return tier
        return ReputationTier.NEW
```

### 2.4 Outcome → Reputation Bridge

```python
# backend/app/models/recommendation_action.py

class RecommendationAction(Base):
    """Tracks when users act on recommendations (implicit or explicit)."""

    __tablename__ = "recommendation_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id", ondelete="CASCADE"))

    tracking_type: Mapped[str] = mapped_column(String(20))  # "explicit" or "implicit"
    acted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # Filled when outcome is evaluated
    user_profit_pct: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    outcome_accuracy: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    recommendation: Mapped["Recommendation"] = relationship("Recommendation")


# Service to bridge recommendations to reputation
class SignalReputationService:
    async def record_explicit_follow(self, db: AsyncSession, user_id: int, recommendation_id: int):
        """User explicitly clicked 'Follow this signal'."""
        action = RecommendationAction(
            user_id=user_id,
            recommendation_id=recommendation_id,
            tracking_type="explicit",
        )
        db.add(action)
        await db.commit()

    async def detect_implicit_follow(self, db: AsyncSession, user_id: int, card_id: int):
        """User added card to inventory while a BUY signal was active."""
        recommendation = await rec_repo.get_active_buy_for_card(db, card_id)
        if not recommendation:
            return

        # Check if already recorded
        existing = await self._get_existing_action(db, user_id, recommendation.id)
        if existing:
            return

        action = RecommendationAction(
            user_id=user_id,
            recommendation_id=recommendation.id,
            tracking_type="implicit",
        )
        db.add(action)
        await db.commit()

    async def evaluate_user_outcomes(self, db: AsyncSession):
        """Batch job: evaluate outcomes for user signal follows."""
        # Find actions without outcomes where recommendation is evaluated
        actions = await db.execute(
            select(RecommendationAction)
            .join(Recommendation)
            .where(
                RecommendationAction.user_profit_pct.is_(None),
                Recommendation.outcome_evaluated_at.isnot(None)
            )
        )

        for action in actions.scalars():
            rec = action.recommendation

            # Copy outcome from recommendation
            action.outcome_accuracy = rec.accuracy_score_end
            action.user_profit_pct = rec.actual_profit_pct_end

            # Update user reputation stats
            await self._update_user_signal_stats(db, action.user_id, action)

        await db.commit()

    async def _update_user_signal_stats(self, db: AsyncSession, user_id: int, action: RecommendationAction):
        """Update user's signal following stats."""
        rep = await reputation_repo.get_or_create(db, user_id)

        rep.signals_followed += 1
        if action.user_profit_pct and action.user_profit_pct > 0:
            rep.signals_profitable += 1

        rep.signal_accuracy_pct = (rep.signals_profitable / rep.signals_followed) * 100
```

---

## Phase 3: Transaction + Business

**Timeline:** 8-10 weeks (after Phase 2)
**Goal:** Complete trade flow, LGS tools
**Theme:** "The whole package"

### 3.1 Payment Escrow (Optional)

```python
# Future: Integration with Stripe Connect for escrow
# This is complex and may be Phase 4

class EscrowService:
    """
    Optional escrow for high-value trades.

    Flow:
    1. Both parties agree to use escrow
    2. Buyer sends payment to Dualcaster (Stripe)
    3. Both parties ship cards
    4. Both confirm receipt
    5. Dualcaster releases funds to seller

    Fee: 2% of transaction value
    """
    pass
```

### 3.2 LGS Dashboard

```python
# Future: Separate business tier with:
# - Inventory sync (Crystal Commerce, BinderPOS, TCGPlayer Pro)
# - Smart buylist pricing
# - Local customer matching
# - Event management
```

### 3.3 User-Generated Signals

```python
# alembic/versions/YYYYMMDD_009_user_signals.py

def upgrade():
    # Add user-generated signal fields to recommendations
    op.add_column('recommendations', sa.Column('created_by_user_id', sa.Integer(),
                                                sa.ForeignKey('users.id'), nullable=True))
    op.add_column('recommendations', sa.Column('is_user_generated', sa.Boolean(), default=False))
    op.add_column('recommendations', sa.Column('is_public', sa.Boolean(), default=True))
    op.add_column('recommendations', sa.Column('follower_count', sa.Integer(), default=0))

    op.create_index('ix_recommendations_user', 'recommendations', ['created_by_user_id'])
```

---

## Cross-Cutting Concerns

### Security

| Concern | Implementation |
|---------|----------------|
| Authentication | JWT with refresh tokens, OAuth for social |
| Authorization | User can only modify own resources |
| Rate limiting | Redis-based, per-endpoint limits |
| Input validation | Pydantic schemas with strict types |
| SQL injection | SQLAlchemy ORM, parameterized queries |
| XSS | React escapes by default, CSP headers |
| CSRF | SameSite cookies, CSRF tokens for forms |
| Secrets | Environment variables, never in code |

### Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| API P50 latency | < 50ms | Prometheus |
| API P95 latency | < 200ms | Prometheus |
| Page load (FCP) | < 1.5s | Lighthouse |
| Page load (LCP) | < 2.5s | Lighthouse |
| Match computation | < 500ms | Custom timing |
| Price update lag | < 60s | Delta tracking |

### Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                      CACHING LAYERS                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Browser Cache (static assets)                               │
│  └── 1 year for hashed files, 1 hour for HTML               │
│                                                              │
│  CDN Cache (Cloudflare)                                      │
│  └── Public card pages: 1 hour                              │
│  └── Card images: 1 day                                     │
│                                                              │
│  Redis Cache (application)                                   │
│  └── Card prices: 5 minutes                                 │
│  └── User matches: 1 hour (invalidate on list change)       │
│  └── Reputation scores: 1 hour                              │
│  └── Session data: 24 hours                                 │
│                                                              │
│  Database (source of truth)                                  │
│  └── All persistent data                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Error Handling

```python
# Consistent error response format
class APIError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

# Error codes
class ErrorCode:
    # Auth
    INVALID_CREDENTIALS = "auth.invalid_credentials"
    TOKEN_EXPIRED = "auth.token_expired"
    ACCOUNT_LOCKED = "auth.account_locked"

    # User
    USER_NOT_FOUND = "user.not_found"
    PROFILE_PRIVATE = "user.profile_private"

    # Trading
    MATCH_NOT_FOUND = "match.not_found"
    TRADE_EXPIRED = "trade.expired"
    CANNOT_TRADE_SELF = "trade.cannot_trade_self"
    BLOCKED_USER = "trade.blocked_user"

    # Cards
    CARD_NOT_FOUND = "card.not_found"
    INSUFFICIENT_INVENTORY = "inventory.insufficient"
```

---

## Success Metrics & Milestones

### Phase 0 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Public card pages indexed | 10,000+ | Google Search Console |
| Organic search traffic | 1,000 visits/month | Analytics |
| Email delivery rate | > 95% | Email provider |
| Discord accounts linked | 100+ | Database |

### Phase 1 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Discord servers with bot | 10+ | Bot metrics |
| Users with have lists | 500+ | Database |
| Daily active bot users | 100+ | Bot metrics |
| Matches generated | 1,000+/day | Database |

### Phase 2 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Trade proposals sent | 500+/month | Database |
| Trade completion rate | > 60% | Database |
| Average review rating | > 4.0 | Database |
| Verified users (email+Discord) | 50%+ | Database |

### Phase 3 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| LGS accounts | 10+ | Database |
| Monthly trade value | $50,000+ | Database |
| User retention (30-day) | > 40% | Analytics |
| Net Promoter Score | > 50 | Survey |

---

## Implementation Checklist

### Phase 0 Tasks

- [ ] Public card pages (no auth)
- [ ] Open Graph meta tags
- [ ] Sitemap generation
- [ ] Hashids integration
- [ ] User profile extensions (migration)
- [ ] User profile API endpoints
- [ ] User search endpoint
- [ ] Privacy settings UI
- [ ] Connected accounts table
- [ ] Discord OAuth completion
- [ ] Notification preferences table
- [ ] Email sending verification
- [ ] Analytics event tracking
- [ ] Public profile page (frontend)
- [ ] Settings pages (frontend)

### Phase 1 Tasks

- [ ] Have list model and migration
- [ ] Have list API endpoints
- [ ] Have list UI (add from inventory)
- [ ] Want list extensions (migration)
- [ ] Want list extensions (API)
- [ ] Discord bot scaffold
- [ ] Bot: /dd price command
- [ ] Bot: /dd want add command
- [ ] Bot: /dd have add command
- [ ] Bot: /dd link command
- [ ] Bot: account linking flow
- [ ] Matching algorithm core
- [ ] Match caching
- [ ] Server-level matching
- [ ] Match notification delivery
- [ ] Match discovery page (frontend)

### Phase 2 Tasks

- [ ] Trade proposals table
- [ ] Trade proposals API
- [ ] Messaging tables
- [ ] Messaging API
- [ ] Completed trades table
- [ ] Trade reviews table
- [ ] User reputation table
- [ ] Reputation calculator
- [ ] Recommendation action tracking
- [ ] Outcome → reputation bridge
- [ ] Trade proposal UI
- [ ] Messaging UI
- [ ] Reputation display components
- [ ] Review submission UI

### Phase 3 Tasks

- [ ] User-generated signals
- [ ] Signal publicity controls
- [ ] LGS account type
- [ ] Inventory sync (TCGPlayer)
- [ ] Smart buylist pricing
- [ ] Local customer matching
- [ ] Mobile app (optional)
- [ ] Escrow integration (optional)

---

## Appendix: API Endpoint Summary

### Public (No Auth)

```
GET  /api/v1/cards/public/{id}
GET  /api/v1/cards/c/{hashid}
GET  /api/v1/users/{username}
GET  /api/v1/users/{username}/have-list
GET  /api/v1/users/{username}/want-list
GET  /api/v1/sitemap.xml
```

### Authenticated

```
# Users
PATCH /api/v1/users/me
POST  /api/v1/users/me/location
GET   /api/v1/users/search

# Want List
GET   /api/v1/want-list
POST  /api/v1/want-list
PATCH /api/v1/want-list/{id}
DELETE /api/v1/want-list/{id}

# Have List
GET   /api/v1/have-list
POST  /api/v1/have-list
PATCH /api/v1/have-list/{id}
DELETE /api/v1/have-list/{id}

# Matching
GET   /api/v1/matches
GET   /api/v1/matches/local
GET   /api/v1/matches/with/{username}
POST  /api/v1/matches/refresh

# Trading
GET   /api/v1/trades
GET   /api/v1/trades/incoming
GET   /api/v1/trades/outgoing
POST  /api/v1/trades
GET   /api/v1/trades/{id}
PATCH /api/v1/trades/{id}
POST  /api/v1/trades/{id}/complete
DELETE /api/v1/trades/{id}

# Messaging
GET   /api/v1/messages
GET   /api/v1/messages/{username}
POST  /api/v1/messages/{username}
PATCH /api/v1/messages/conversations/{id}/read

# Reputation
GET   /api/v1/users/{username}/reputation
GET   /api/v1/users/{username}/reviews
POST  /api/v1/trades/{id}/review

# Connections
GET   /api/v1/connections
POST  /api/v1/connections/discord/initiate
DELETE /api/v1/connections/{provider}

# Notifications
GET   /api/v1/notifications/preferences
PATCH /api/v1/notifications/preferences
```

### Discord Bot (Bot Token Auth)

```
GET   /api/v1/discord/user/{discord_id}
POST  /api/v1/discord/user/{discord_id}/want-list
POST  /api/v1/discord/user/{discord_id}/have-list
GET   /api/v1/discord/user/{discord_id}/matches
GET   /api/v1/discord/price/{card_name}
GET   /api/v1/discord/guild/{guild_id}/matches
POST  /api/v1/discord/guild/{guild_id}/link
```

---

*This specification is the north star for Dualcaster Deals. Implementation details will evolve, but the vision remains: become the premier intelligence and trading platform for Magic: The Gathering.*
