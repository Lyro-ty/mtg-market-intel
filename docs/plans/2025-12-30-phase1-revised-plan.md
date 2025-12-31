# Phase 1: Enhanced Intelligence + Discovery

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Best-in-class market intelligence, buylist tracking, user discovery

**Architecture:** New data adapters, enhanced signals, Discord bot, matching algorithm

**Tech Stack:** Python discord.py, Card Kingdom scraping, EDHREC API

**Tasks:** 14

---

## Task 1.1: Buylist Price Tracking

**Files:**
- Create: `backend/app/services/ingestion/adapters/cardkingdom_buylist.py`
- Create: `backend/alembic/versions/YYYYMMDD_add_buylist_prices.py`
- Test: `backend/tests/adapters/test_cardkingdom_buylist.py`

**Step 1: Design buylist schema**

Option A: Add fields to price_snapshots
```sql
ALTER TABLE price_snapshots ADD COLUMN buylist_price DECIMAL(10,2);
ALTER TABLE price_snapshots ADD COLUMN buylist_quantity INTEGER;
```

Option B: Separate table (recommended for clarity)
```sql
CREATE TABLE buylist_snapshots (
    time TIMESTAMPTZ NOT NULL,
    card_id INTEGER REFERENCES cards(id),
    marketplace VARCHAR(50) NOT NULL,  -- 'cardkingdom', 'channelfireball'
    condition VARCHAR(20) NOT NULL,
    is_foil BOOLEAN DEFAULT FALSE,
    price DECIMAL(10,2) NOT NULL,
    quantity INTEGER,  -- How many they're buying
    PRIMARY KEY (time, card_id, marketplace, condition, is_foil)
);
```

**Step 2: Implement Card Kingdom adapter**

```python
# backend/app/services/ingestion/adapters/cardkingdom_buylist.py
import httpx
from bs4 import BeautifulSoup
from app.services.ingestion.adapters.base import BaseAdapter

class CardKingdomBuylistAdapter(BaseAdapter):
    """
    Card Kingdom buylist scraper.

    Note: CK doesn't have a public API, so we scrape their buylist page.
    Respect rate limits and robots.txt.
    """

    BASE_URL = "https://www.cardkingdom.com"
    RATE_LIMIT_SECONDS = 2  # Be respectful

    async def get_buylist_price(self, card_name: str, set_code: str) -> dict | None:
        """Fetch buylist price for a specific card."""
        # Search their buylist
        search_url = f"{self.BASE_URL}/purchasing/search"
        params = {"filter[search]": f"{card_name} [{set_code}]"}

        async with httpx.AsyncClient() as client:
            response = await client.get(search_url, params=params)

        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        # Parse buylist prices from HTML
        # ... parsing logic

        return {
            "nm_price": nm_price,
            "lp_price": lp_price,
            "mp_price": mp_price,
            "nm_quantity": nm_qty,
        }

    async def collect_popular_buylists(self, card_ids: list[int]) -> list[dict]:
        """Batch collect buylist prices for popular cards."""
        results = []
        for card_id in card_ids:
            # Rate limiting
            await asyncio.sleep(self.RATE_LIMIT_SECONDS)

            card = await self.get_card(card_id)
            price_data = await self.get_buylist_price(card.name, card.set_code)

            if price_data:
                results.append({
                    "card_id": card_id,
                    "marketplace": "cardkingdom",
                    **price_data
                })

        return results
```

**Step 3: Create Celery task**

```python
# In backend/app/tasks/ingestion.py

@shared_task(name="collect_buylist_prices")
def collect_buylist_prices():
    """Collect buylist prices from Card Kingdom."""
    import asyncio
    asyncio.run(_collect_buylist_prices())

async def _collect_buylist_prices():
    adapter = CardKingdomBuylistAdapter()

    # Get high-value cards that are commonly bought
    async with async_session_maker() as db:
        result = await db.execute(
            select(Card.id)
            .join(PriceSnapshot)
            .where(PriceSnapshot.price >= 5.00)  # Only valuable cards
            .distinct()
            .limit(500)  # Batch size
        )
        card_ids = [r[0] for r in result.all()]

    buylist_data = await adapter.collect_popular_buylists(card_ids)

    async with async_session_maker() as db:
        for data in buylist_data:
            snapshot = BuylistSnapshot(
                time=datetime.now(timezone.utc),
                card_id=data["card_id"],
                marketplace=data["marketplace"],
                condition="NM",
                price=data["nm_price"],
                quantity=data.get("nm_quantity"),
            )
            db.add(snapshot)
        await db.commit()
```

**Step 4: Schedule task (daily - buylist changes slowly)**

```python
app.conf.beat_schedule["collect-buylist-prices"] = {
    "task": "collect_buylist_prices",
    "schedule": crontab(hour=6, minute=0),  # Daily at 6 AM
}
```

**Step 5: Commit**

```bash
git commit -m "feat: add Card Kingdom buylist price tracking"
```

---

## Task 1.2: Spread Analysis Dashboard

**Files:**
- Create: `backend/app/api/routes/spreads.py`
- Create: `frontend/src/app/(protected)/spreads/page.tsx`
- Test: `backend/tests/api/test_spreads.py`

**Step 1: Create spread API**

```python
# backend/app/api/routes/spreads.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db

router = APIRouter(prefix="/spreads", tags=["spreads"])

@router.get("/best-buylist-opportunities")
async def get_best_buylist_opportunities(
    limit: int = Query(default=20, le=100),
    min_spread_pct: float = Query(default=10.0),
    db: AsyncSession = Depends(get_db),
):
    """
    Find cards with largest buylist-to-retail spread.

    A high spread means you can buy low and sell to buylist high.
    """
    query = """
        SELECT
            c.id,
            c.name,
            c.set_code,
            ps.price as retail_price,
            bs.price as buylist_price,
            (ps.price - bs.price) as spread,
            ((ps.price - bs.price) / ps.price * 100) as spread_pct
        FROM cards c
        JOIN LATERAL (
            SELECT price FROM price_snapshots
            WHERE card_id = c.id
            ORDER BY time DESC LIMIT 1
        ) ps ON true
        JOIN LATERAL (
            SELECT price FROM buylist_snapshots
            WHERE card_id = c.id
            ORDER BY time DESC LIMIT 1
        ) bs ON true
        WHERE ((ps.price - bs.price) / ps.price * 100) >= :min_spread
        ORDER BY spread_pct DESC
        LIMIT :limit
    """
    result = await db.execute(text(query), {"min_spread": min_spread_pct, "limit": limit})
    return [dict(row._mapping) for row in result.all()]

@router.get("/arbitrage-opportunities")
async def get_arbitrage_opportunities(
    limit: int = Query(default=20),
    db: AsyncSession = Depends(get_db),
):
    """
    Find cards where cross-marketplace arbitrage is possible.

    Example: Buy on CardMarket for $10, sell on TCGPlayer for $15.
    """
    # Compare prices across marketplaces
    query = """
        WITH latest_prices AS (
            SELECT DISTINCT ON (card_id, marketplace_id)
                card_id,
                marketplace_id,
                price,
                time
            FROM price_snapshots
            ORDER BY card_id, marketplace_id, time DESC
        )
        SELECT
            c.name,
            c.set_code,
            low.marketplace_id as buy_marketplace,
            low.price as buy_price,
            high.marketplace_id as sell_marketplace,
            high.price as sell_price,
            (high.price - low.price) as profit,
            ((high.price - low.price) / low.price * 100) as profit_pct
        FROM cards c
        JOIN latest_prices low ON c.id = low.card_id
        JOIN latest_prices high ON c.id = high.card_id AND high.marketplace_id != low.marketplace_id
        WHERE high.price > low.price * 1.15  -- At least 15% profit
        ORDER BY (high.price - low.price) DESC
        LIMIT :limit
    """
    result = await db.execute(text(query), {"limit": limit})
    return [dict(row._mapping) for row in result.all()]
```

**Step 2: Create frontend page**

```tsx
// frontend/src/app/(protected)/spreads/page.tsx
'use client';
import { useQuery } from '@tanstack/react-query';

export default function SpreadsPage() {
  const { data: buylistOpps } = useQuery({
    queryKey: ['buylist-opportunities'],
    queryFn: () => fetchApi('/spreads/best-buylist-opportunities'),
  });

  const { data: arbitrageOpps } = useQuery({
    queryKey: ['arbitrage-opportunities'],
    queryFn: () => fetchApi('/spreads/arbitrage-opportunities'),
  });

  return (
    <div className="space-y-8">
      <section>
        <h2 className="text-xl font-bold mb-4">Best Buylist Opportunities</h2>
        <p className="text-muted-foreground mb-4">
          Cards with the highest spread between retail and buylist prices.
        </p>
        <table>...</table>
      </section>

      <section>
        <h2 className="text-xl font-bold mb-4">Cross-Market Arbitrage</h2>
        <p className="text-muted-foreground mb-4">
          Price differences between marketplaces that could be profitable.
        </p>
        <table>...</table>
      </section>
    </div>
  );
}
```

**Step 3: Commit**

```bash
git commit -m "feat: add spread analysis dashboard with buylist and arbitrage"
```

---

## Task 1.3: Format Legality History

**Files:**
- Create: `backend/alembic/versions/YYYYMMDD_add_legality_changes.py`
- Create: `backend/app/models/legality.py`
- Modify: `backend/app/tasks/ingestion.py`

**Step 1: Create legality_changes table**

```sql
CREATE TABLE legality_changes (
    id SERIAL PRIMARY KEY,
    card_id INTEGER REFERENCES cards(id),
    format VARCHAR(20) NOT NULL,  -- 'modern', 'standard', etc.
    old_status VARCHAR(20),       -- 'legal', 'banned', 'restricted', NULL (new)
    new_status VARCHAR(20) NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL,
    source VARCHAR(100),          -- 'wotc_announcement', 'scryfall_sync'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_legality_changes_card_id ON legality_changes(card_id);
CREATE INDEX ix_legality_changes_format ON legality_changes(format);
CREATE INDEX ix_legality_changes_changed_at ON legality_changes(changed_at);
```

**Step 2: Track changes during Scryfall sync**

```python
# In Scryfall import task
async def sync_legalities(db: AsyncSession, card: Card, scryfall_data: dict):
    """Compare and track legality changes."""
    current_legalities = json.loads(card.legalities) if card.legalities else {}
    new_legalities = scryfall_data.get("legalities", {})

    for format_name, new_status in new_legalities.items():
        old_status = current_legalities.get(format_name)

        if old_status != new_status:
            change = LegalityChange(
                card_id=card.id,
                format=format_name,
                old_status=old_status,
                new_status=new_status,
                changed_at=datetime.now(timezone.utc),
                source="scryfall_sync",
            )
            db.add(change)

            # Generate signal for bans
            if new_status == "banned" and old_status == "legal":
                signal = Signal(
                    card_id=card.id,
                    signal_type="BANNED",
                    value=-50.0,  # Expect 50% drop
                    metadata={"format": format_name}
                )
                db.add(signal)
```

**Step 3: API endpoint for ban history**

```python
@router.get("/cards/{card_id}/legality-history")
async def get_legality_history(card_id: int, db: AsyncSession = Depends(get_db)):
    """Get legality change history for a card."""
    result = await db.execute(
        select(LegalityChange)
        .where(LegalityChange.card_id == card_id)
        .order_by(LegalityChange.changed_at.desc())
    )
    return result.scalars().all()
```

**Step 4: Commit**

```bash
git commit -m "feat: track format legality changes with ban/unban signals"
```

---

## Task 1.4: Price Alert Enhancements

**Files:**
- Modify: `backend/app/models/want_list.py`
- Modify: `backend/app/api/routes/want_list.py`
- Modify: `backend/app/tasks/analytics.py`

**Step 1: Add advanced alert options to want_list_items**

```sql
ALTER TABLE want_list_items ADD COLUMN alert_on_spike BOOLEAN DEFAULT FALSE;
ALTER TABLE want_list_items ADD COLUMN alert_threshold_pct DECIMAL(5,2);  -- e.g., 15.00 = 15%
ALTER TABLE want_list_items ADD COLUMN alert_on_supply_low BOOLEAN DEFAULT FALSE;
```

**Step 2: Implement enhanced alerts**

```python
# In analytics task
async def check_enhanced_alerts(db: AsyncSession):
    """Check for advanced alert conditions."""

    # Get all want list items with enhanced alerts
    result = await db.execute(
        select(WantListItem)
        .where(WantListItem.alert_enabled == True)
        .options(joinedload(WantListItem.card))
    )
    items = result.scalars().all()

    notification_service = NotificationService(db)

    for item in items:
        card = item.card
        latest_price = await get_latest_price(db, card.id)
        price_24h_ago = await get_price_at(db, card.id, hours_ago=24)

        # Spike alert
        if item.alert_on_spike and price_24h_ago:
            change_pct = (latest_price - price_24h_ago) / price_24h_ago * 100
            if change_pct >= item.alert_threshold_pct:
                await notification_service.send(
                    user_id=item.user_id,
                    notification_type="price_spike",
                    title=f"{card.name} spiked {change_pct:.1f}%!",
                    message=f"Price went from ${price_24h_ago:.2f} to ${latest_price:.2f}",
                    card_id=card.id,
                    priority="high",
                )

        # Supply low alert
        if item.alert_on_supply_low:
            supply = await get_supply(db, card.id)
            if supply and supply < 20:
                await notification_service.send(
                    user_id=item.user_id,
                    notification_type="supply_low",
                    title=f"{card.name} - Low Supply Warning",
                    message=f"Only {supply} listings remaining on TCGPlayer",
                    card_id=card.id,
                )
```

**Step 3: Commit**

```bash
git commit -m "feat: enhanced price alerts (spike, supply low)"
```

---

## Task 1.5: Want List Intelligence Integration

**Files:**
- Modify: `backend/app/api/routes/want_list.py`
- Modify: `frontend/src/app/(protected)/want-list/page.tsx`

**Step 1: Add intelligence data to want list API response**

```python
class WantListItemWithIntelligence(BaseModel):
    """Want list item with market intelligence."""
    id: int
    card_id: int
    card_name: str
    target_price: Decimal | None
    # ... existing fields

    # Intelligence data
    current_price: Decimal
    price_vs_target: Decimal  # % above/below target
    price_trend_7d: Decimal   # % change
    meta_share: float | None  # % of decks in format
    reprint_risk: int | None  # 0-100
    supply_status: str        # 'normal', 'low', 'very_low'
    recommendation: str       # 'buy_now', 'wait', 'price_spiking'
```

**Step 2: Generate recommendations**

```python
def generate_recommendation(item: WantListItem, intelligence: dict) -> str:
    """Generate buy recommendation for want list item."""

    # Below target price? Buy now!
    if intelligence["current_price"] <= item.target_price:
        return "buy_now"

    # Price dropping? Wait
    if intelligence["price_trend_7d"] < -5:
        return "wait_dropping"

    # Low supply + rising? Might spike
    if intelligence["supply_status"] == "low" and intelligence["price_trend_7d"] > 5:
        return "buy_before_spike"

    # High reprint risk? Wait for reprint
    if intelligence["reprint_risk"] and intelligence["reprint_risk"] > 70:
        return "wait_reprint_likely"

    return "hold"
```

**Step 3: Frontend display**

```tsx
// Show intelligence on each want list item
<Card className="p-4">
  <div className="flex justify-between">
    <div>
      <h3>{item.card_name}</h3>
      <p className="text-sm text-muted-foreground">
        Target: ${item.target_price} | Current: ${item.current_price}
      </p>
    </div>
    <Badge variant={getRecommendationVariant(item.recommendation)}>
      {item.recommendation}
    </Badge>
  </div>
  <div className="mt-2 text-xs grid grid-cols-3 gap-2">
    <span>7d: {item.price_trend_7d}%</span>
    <span>Meta: {item.meta_share}%</span>
    <span>Supply: {item.supply_status}</span>
  </div>
</Card>
```

**Step 4: Commit**

```bash
git commit -m "feat: add market intelligence to want list items"
```

---

## Task 1.6-1.7: User Discovery

**Files:**
- Create: `backend/app/api/routes/discovery.py`
- Create: `backend/app/services/matching.py`

**Step 1: Matching algorithm**

```python
# backend/app/services/matching.py
async def find_users_with_my_wants(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> list[dict]:
    """Find users who have cards I want (that are available for trade)."""

    query = """
        SELECT
            u.id as user_id,
            u.username,
            u.display_name,
            u.location,
            COUNT(DISTINCT ii.card_id) as matching_cards,
            ARRAY_AGG(DISTINCT c.name) as card_names
        FROM users u
        JOIN inventory_items ii ON u.id = ii.user_id
        JOIN want_list_items wli ON ii.card_id = wli.card_id
        JOIN cards c ON ii.card_id = c.id
        WHERE wli.user_id = :user_id
          AND ii.available_for_trade = TRUE
          AND wli.is_active = TRUE
          AND u.id != :user_id
        GROUP BY u.id
        ORDER BY matching_cards DESC
        LIMIT :limit
    """
    result = await db.execute(text(query), {"user_id": user_id, "limit": limit})
    return [dict(row._mapping) for row in result.all()]

async def find_users_who_want_my_cards(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> list[dict]:
    """Find users who want cards I have available for trade."""

    query = """
        SELECT
            u.id as user_id,
            u.username,
            u.display_name,
            u.location,
            COUNT(DISTINCT wli.card_id) as matching_cards,
            ARRAY_AGG(DISTINCT c.name) as card_names
        FROM users u
        JOIN want_list_items wli ON u.id = wli.user_id
        JOIN inventory_items ii ON wli.card_id = ii.card_id
        JOIN cards c ON wli.card_id = c.id
        WHERE ii.user_id = :user_id
          AND ii.available_for_trade = TRUE
          AND wli.is_active = TRUE
          AND u.id != :user_id
        GROUP BY u.id
        ORDER BY matching_cards DESC
        LIMIT :limit
    """
    result = await db.execute(text(query), {"user_id": user_id, "limit": limit})
    return [dict(row._mapping) for row in result.all()]
```

**Step 2: Discovery API**

```python
# backend/app/api/routes/discovery.py
router = APIRouter(prefix="/discovery", tags=["discovery"])

@router.get("/users-with-my-wants")
async def get_users_with_my_wants(
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Find users who have cards I want."""
    return await find_users_with_my_wants(db, current_user.id, limit)

@router.get("/users-who-want-mine")
async def get_users_who_want_mine(
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Find users who want my available-for-trade cards."""
    return await find_users_who_want_my_cards(db, current_user.id, limit)
```

**Step 3: Commit**

```bash
git commit -m "feat: user discovery matching algorithm"
```

---

## Task 1.8: Public User Profiles

**Files:**
- Modify: `backend/app/api/routes/profiles.py`
- Create: `frontend/src/app/u/[hashid]/page.tsx`

**Step 1: Public profile endpoint**

```python
@router.get("/public/{hashid}", response_model=PublicProfileResponse)
async def get_public_profile(
    hashid: str,
    db: AsyncSession = Depends(get_db),
):
    """Get public profile by hashid (no auth required)."""
    user_id = decode_id(hashid)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Count available for trade
    trade_count = await db.scalar(
        select(func.count())
        .select_from(InventoryItem)
        .where(InventoryItem.user_id == user_id)
        .where(InventoryItem.available_for_trade == True)
    )

    return PublicProfileResponse(
        hashid=hashid,
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        location=user.location,  # City only, not address
        avatar_url=user.avatar_url,
        cards_for_trade=trade_count,
        member_since=user.created_at,
    )
```

**Step 2: Commit**

```bash
git commit -m "feat: public user profile pages"
```

---

## Task 1.9-1.11: Discord Bot (Abbreviated)

Create separate service in `discord-bot/` directory:
- `!price <card>` - Returns current price
- `!want add/list/remove` - Manage want list
- DM alerts when prices trigger

See `docs/plans/2025-12-30-implementation-prerequisites.md` for full Discord bot spec.

---

## Task 1.12: EDHREC Integration

**Files:**
- Create: `backend/app/services/edhrec.py`
- Modify: `backend/app/tasks/ingestion.py`

```python
# backend/app/services/edhrec.py
import httpx

class EDHRECClient:
    """Fetch Commander popularity data from EDHREC."""

    BASE_URL = "https://json.edhrec.com"

    async def get_top_commanders(self, limit: int = 100) -> list[dict]:
        """Get most popular commanders."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.BASE_URL}/top/commanders.json")
            data = response.json()
            return data["commanders"][:limit]

    async def get_card_data(self, card_name: str) -> dict | None:
        """Get EDHREC data for a specific card."""
        slug = card_name.lower().replace(" ", "-")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.BASE_URL}/cards/{slug}.json")
            if response.status_code == 200:
                return response.json()
        return None
```

**Step 2: Commit**

```bash
git commit -m "feat: EDHREC integration for Commander popularity"
```

---

## Phase 1 Completion Checklist

- [ ] Task 1.1: Buylist price tracking (Card Kingdom)
- [ ] Task 1.2: Spread analysis dashboard
- [ ] Task 1.3: Format legality history
- [ ] Task 1.4: Enhanced price alerts
- [ ] Task 1.5: Want list intelligence integration
- [ ] Task 1.6: Discovery - users with my wants
- [ ] Task 1.7: Discovery - users who want mine
- [ ] Task 1.8: Public user profiles
- [ ] Task 1.9: Discord bot - price lookups
- [ ] Task 1.10: Discord bot - want list management
- [ ] Task 1.11: Discord bot - alert notifications
- [ ] Task 1.12: EDHREC integration
- [ ] Task 1.13: Price prediction signals
- [ ] Task 1.14: Portfolio intelligence dashboard

**Success Criteria:**
- Buylist prices tracked for 500+ cards
- Users can discover each other via matching
- Discord bot responds to `!price` commands
- Want list shows intelligent recommendations
