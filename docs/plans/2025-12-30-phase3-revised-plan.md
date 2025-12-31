# Phase 3: LGS Intelligence + Premium

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Provide value to LGS, monetize with subscriptions (NOT transactions)

**Architecture:** LGS profiles, demand aggregation, Stripe for subscriptions only

**Tech Stack:** Stripe Billing (not Connect), aggregate analytics

**Tasks:** 10

---

## What Changed From Original

| Original | Revised |
|----------|---------|
| Stripe Connect (escrow) | Stripe Billing (subscriptions only) |
| LGS as sellers | LGS as intelligence consumers |
| Transaction fees | Subscription revenue |
| Payment processing liability | Zero transaction liability |

**Key insight:** LGS don't need us to sell cards. They need to know what to stock.

---

## Database Schema

```sql
-- LGS profiles
CREATE TABLE lgs_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) UNIQUE NOT NULL,
    store_name VARCHAR(200) NOT NULL,
    description TEXT,
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(50),
    country VARCHAR(50) DEFAULT 'US',
    postal_code VARCHAR(20),
    website VARCHAR(500),
    phone VARCHAR(20),
    hours JSONB,  -- {"monday": "10:00-20:00", ...}
    services TEXT[],  -- ['singles', 'tournaments', 'buylist', 'grading']
    logo_url VARCHAR(500),
    verified_at TIMESTAMPTZ,
    verification_method VARCHAR(50),  -- 'manual', 'domain', 'phone'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_lgs_profiles_city ON lgs_profiles(city);
CREATE INDEX ix_lgs_profiles_verified ON lgs_profiles(verified_at) WHERE verified_at IS NOT NULL;

-- LGS events (tournaments, sales, etc.)
CREATE TABLE lgs_events (
    id SERIAL PRIMARY KEY,
    lgs_id INTEGER REFERENCES lgs_profiles(id) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    event_type VARCHAR(50),  -- 'tournament', 'sale', 'release', 'meetup'
    format VARCHAR(50),      -- 'modern', 'standard', 'commander', etc.
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    entry_fee DECIMAL(10,2),
    max_players INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_lgs_events_start ON lgs_events(start_time);
CREATE INDEX ix_lgs_events_lgs ON lgs_events(lgs_id);

-- Subscriptions (Stripe Billing)
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    stripe_customer_id VARCHAR(100),
    stripe_subscription_id VARCHAR(100) UNIQUE,
    tier VARCHAR(20) NOT NULL,  -- 'free', 'premium', 'lgs'
    status VARCHAR(20) NOT NULL,  -- 'active', 'canceled', 'past_due'
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    canceled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_subscriptions_user ON subscriptions(user_id);
CREATE INDEX ix_subscriptions_stripe ON subscriptions(stripe_subscription_id);
```

---

## Subscription Tiers

| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0 | 5 price alerts, 30-day history, basic matching |
| **Premium** | $5/mo | Unlimited alerts, 1-year history, advanced analytics, API access |
| **LGS** | $20/mo | Premium + demand data, event promotion, verified badge |

---

## Task 3.1: LGS Registration Flow

**Files:**
- Create: `backend/app/models/lgs.py`
- Create: `backend/app/api/routes/lgs.py`
- Create: `backend/app/schemas/lgs.py`
- Create: `frontend/src/app/(protected)/lgs/register/page.tsx`
- Test: `backend/tests/api/test_lgs.py`

**Step 1: Write failing tests**

```python
# backend/tests/api/test_lgs.py
@pytest.mark.asyncio
async def test_register_lgs(client: AsyncClient, auth_headers):
    """User can register their LGS."""
    response = await client.post(
        "/api/lgs/register",
        headers=auth_headers,
        json={
            "store_name": "Dragon's Lair Games",
            "address": "123 Main St",
            "city": "Seattle",
            "state": "WA",
            "website": "https://dragonslair.example.com",
            "services": ["singles", "tournaments"],
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["store_name"] == "Dragon's Lair Games"
    assert data["verified_at"] is None  # Not verified yet

@pytest.mark.asyncio
async def test_lgs_requires_unique_user(
    client: AsyncClient,
    auth_headers,
    lgs_profile,  # Existing LGS for this user
):
    """User can only have one LGS profile."""
    response = await client.post(
        "/api/lgs/register",
        headers=auth_headers,
        json={"store_name": "Another Store", "city": "Portland"}
    )
    assert response.status_code == 400
```

**Step 2: Implement LGS routes**

```python
# backend/app/api/routes/lgs.py
router = APIRouter(prefix="/lgs", tags=["lgs"])

@router.post("/register", response_model=LGSProfileResponse, status_code=201)
async def register_lgs(
    profile: LGSProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register a new LGS profile."""
    # Check if user already has LGS
    existing = await db.execute(
        select(LGSProfile).where(LGSProfile.user_id == current_user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already have an LGS profile")

    lgs = LGSProfile(
        user_id=current_user.id,
        store_name=profile.store_name,
        description=profile.description,
        address=profile.address,
        city=profile.city,
        state=profile.state,
        country=profile.country,
        postal_code=profile.postal_code,
        website=profile.website,
        phone=profile.phone,
        hours=profile.hours,
        services=profile.services,
    )
    db.add(lgs)
    await db.commit()
    await db.refresh(lgs)
    return lgs

@router.get("/nearby")
async def get_nearby_lgs(
    city: str | None = None,
    state: str | None = None,
    verified_only: bool = Query(default=True),
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Find LGS near a location."""
    query = select(LGSProfile)

    if verified_only:
        query = query.where(LGSProfile.verified_at.isnot(None))

    if city:
        query = query.where(LGSProfile.city.ilike(f"%{city}%"))
    if state:
        query = query.where(LGSProfile.state == state)

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{lgs_id}")
async def get_lgs_profile(
    lgs_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get LGS profile details."""
    lgs = await db.get(LGSProfile, lgs_id)
    if not lgs:
        raise HTTPException(status_code=404, detail="LGS not found")
    return lgs
```

**Step 3: Commit**

```bash
git commit -m "feat: LGS registration flow"
```

---

## Task 3.2: LGS Demand Dashboard

**Files:**
- Create: `backend/app/api/routes/lgs_analytics.py`
- Create: `frontend/src/app/(protected)/lgs/dashboard/page.tsx`

**Step 1: Aggregate demand by location**

```python
# backend/app/api/routes/lgs_analytics.py
router = APIRouter(prefix="/lgs/analytics", tags=["lgs-analytics"])

@router.get("/local-demand")
async def get_local_demand(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get most wanted cards in your area.
    Requires LGS subscription tier.
    """
    # Verify LGS subscription
    lgs = await get_user_lgs(db, current_user.id)
    if not lgs:
        raise HTTPException(status_code=403, detail="Requires LGS profile")

    subscription = await get_subscription(db, current_user.id)
    if not subscription or subscription.tier != "lgs":
        raise HTTPException(status_code=403, detail="Requires LGS subscription")

    # Aggregate want list data for users in same city
    query = """
        SELECT
            c.id,
            c.name,
            c.set_code,
            c.image_url,
            COUNT(DISTINCT wli.user_id) as demand_count,
            AVG(wli.target_price) as avg_target_price,
            ps.price as current_price
        FROM want_list_items wli
        JOIN cards c ON wli.card_id = c.id
        JOIN users u ON wli.user_id = u.id
        LEFT JOIN LATERAL (
            SELECT price FROM price_snapshots
            WHERE card_id = c.id
            ORDER BY time DESC LIMIT 1
        ) ps ON true
        WHERE u.location ILIKE :city_pattern
          AND wli.is_active = TRUE
        GROUP BY c.id, c.name, c.set_code, c.image_url, ps.price
        ORDER BY demand_count DESC
        LIMIT 50
    """
    result = await db.execute(
        text(query),
        {"city_pattern": f"%{lgs.city}%"}
    )
    return [dict(row._mapping) for row in result.all()]

@router.get("/available-nearby")
async def get_available_nearby(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get cards that local users have marked as available for trade.
    Helps LGS know what inventory is floating around locally.
    """
    lgs = await get_user_lgs(db, current_user.id)
    if not lgs:
        raise HTTPException(status_code=403, detail="Requires LGS profile")

    query = """
        SELECT
            c.id,
            c.name,
            c.set_code,
            COUNT(DISTINCT ii.user_id) as seller_count,
            SUM(ii.quantity) as total_quantity,
            ps.price as current_price
        FROM inventory_items ii
        JOIN cards c ON ii.card_id = c.id
        JOIN users u ON ii.user_id = u.id
        LEFT JOIN LATERAL (
            SELECT price FROM price_snapshots
            WHERE card_id = c.id
            ORDER BY time DESC LIMIT 1
        ) ps ON true
        WHERE u.location ILIKE :city_pattern
          AND ii.available_for_trade = TRUE
        GROUP BY c.id, c.name, c.set_code, ps.price
        ORDER BY total_quantity DESC
        LIMIT 50
    """
    result = await db.execute(text(query), {"city_pattern": f"%{lgs.city}%"})
    return [dict(row._mapping) for row in result.all()]
```

**Step 2: Create dashboard UI**

```tsx
// frontend/src/app/(protected)/lgs/dashboard/page.tsx
'use client';
import { useQuery } from '@tanstack/react-query';

export default function LGSDashboard() {
  const { data: demand } = useQuery({
    queryKey: ['lgs-demand'],
    queryFn: () => fetchApi('/lgs/analytics/local-demand'),
  });

  const { data: available } = useQuery({
    queryKey: ['lgs-available'],
    queryFn: () => fetchApi('/lgs/analytics/available-nearby'),
  });

  return (
    <div className="space-y-8">
      <section>
        <h2 className="text-2xl font-bold">Local Demand</h2>
        <p className="text-muted-foreground">
          Cards that players in your area are looking for
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
          {demand?.map((card) => (
            <Card key={card.id}>
              <CardHeader>
                <CardTitle>{card.name}</CardTitle>
                <CardDescription>{card.set_code}</CardDescription>
              </CardHeader>
              <CardContent>
                <p><strong>{card.demand_count}</strong> users want this</p>
                <p>Avg target: ${card.avg_target_price?.toFixed(2)}</p>
                <p>Current: ${card.current_price?.toFixed(2)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-bold">Available Locally</h2>
        <p className="text-muted-foreground">
          Cards local players have marked for trade (potential buylist targets)
        </p>
        {/* Similar grid */}
      </section>
    </div>
  );
}
```

**Step 3: Commit**

```bash
git commit -m "feat: LGS demand dashboard with local analytics"
```

---

## Task 3.3: LGS Buylist Intelligence

**Files:**
- Modify: `backend/app/api/routes/lgs_analytics.py`

```python
@router.get("/buylist-recommendations")
async def get_buylist_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Recommend buylist prices based on local demand and market data.
    """
    lgs = await get_user_lgs(db, current_user.id)
    require_lgs_subscription(current_user.id)

    query = """
        SELECT
            c.id,
            c.name,
            c.set_code,
            ps.price as market_price,
            bs.price as ck_buylist,
            local.demand_count,
            -- Recommended buylist: slightly above CK to be competitive
            COALESCE(bs.price * 1.05, ps.price * 0.5) as recommended_buylist
        FROM cards c
        LEFT JOIN LATERAL (
            SELECT price FROM price_snapshots
            WHERE card_id = c.id ORDER BY time DESC LIMIT 1
        ) ps ON true
        LEFT JOIN LATERAL (
            SELECT price FROM buylist_snapshots
            WHERE card_id = c.id AND marketplace = 'cardkingdom'
            ORDER BY time DESC LIMIT 1
        ) bs ON true
        LEFT JOIN LATERAL (
            SELECT COUNT(DISTINCT user_id) as demand_count
            FROM want_list_items wli
            JOIN users u ON wli.user_id = u.id
            WHERE wli.card_id = c.id
              AND u.location ILIKE :city_pattern
        ) local ON true
        WHERE local.demand_count > 0
        ORDER BY local.demand_count DESC
        LIMIT 50
    """
    result = await db.execute(text(query), {"city_pattern": f"%{lgs.city}%"})
    return [dict(row._mapping) for row in result.all()]
```

---

## Task 3.4: LGS Event Promotion

**Files:**
- Modify: `backend/app/api/routes/lgs.py`
- Create: `frontend/src/app/(protected)/lgs/events/page.tsx`

```python
@router.post("/{lgs_id}/events", status_code=201)
async def create_event(
    lgs_id: int,
    event: LGSEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an event for your LGS."""
    lgs = await db.get(LGSProfile, lgs_id)
    if not lgs or lgs.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your LGS")

    event = LGSEvent(
        lgs_id=lgs_id,
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        format=event.format,
        start_time=event.start_time,
        end_time=event.end_time,
        entry_fee=event.entry_fee,
        max_players=event.max_players,
    )
    db.add(event)
    await db.commit()
    return event

@router.get("/events/nearby")
async def get_nearby_events(
    city: str | None = None,
    format: str | None = None,
    days: int = Query(default=14, le=60),
    db: AsyncSession = Depends(get_db),
):
    """Get upcoming events near a location."""
    query = select(LGSEvent).join(LGSProfile).where(
        LGSEvent.start_time >= datetime.now(timezone.utc),
        LGSEvent.start_time <= datetime.now(timezone.utc) + timedelta(days=days),
    )

    if city:
        query = query.where(LGSProfile.city.ilike(f"%{city}%"))
    if format:
        query = query.where(LGSEvent.format == format)

    query = query.order_by(LGSEvent.start_time)
    result = await db.execute(query)
    return result.scalars().all()
```

---

## Task 3.5-3.7: Premium Tiers (Stripe Billing)

**Files:**
- Create: `backend/app/services/stripe_service.py`
- Create: `backend/app/api/routes/subscriptions.py`
- Create: `backend/app/api/routes/webhooks.py`

**Step 1: Stripe service**

```python
# backend/app/services/stripe_service.py
import stripe
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeService:
    PRICE_IDS = {
        "premium": "price_xxx",  # $5/month
        "lgs": "price_yyy",      # $20/month
    }

    async def create_checkout_session(
        self,
        user_id: int,
        tier: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create Stripe Checkout session for subscription."""
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{
                "price": self.PRICE_IDS[tier],
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": str(user_id)},
        )
        return session.url

    async def cancel_subscription(self, stripe_subscription_id: str):
        """Cancel a subscription."""
        stripe.Subscription.delete(stripe_subscription_id)

    async def handle_webhook(self, payload: bytes, sig_header: str) -> dict:
        """Process Stripe webhook event."""
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            user_id = int(session["metadata"]["user_id"])
            subscription_id = session["subscription"]
            # Create/update subscription record
            return {"action": "subscription_created", "user_id": user_id}

        elif event["type"] == "invoice.payment_failed":
            subscription_id = event["data"]["object"]["subscription"]
            # Mark subscription as past_due
            return {"action": "payment_failed", "subscription_id": subscription_id}

        elif event["type"] == "customer.subscription.deleted":
            subscription_id = event["data"]["object"]["id"]
            # Mark subscription as canceled
            return {"action": "subscription_canceled", "subscription_id": subscription_id}

        return {"action": "ignored"}
```

**Step 2: Subscription routes**

```python
# backend/app/api/routes/subscriptions.py
@router.post("/subscribe/{tier}")
async def subscribe(
    tier: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start subscription checkout."""
    if tier not in ["premium", "lgs"]:
        raise HTTPException(status_code=400, detail="Invalid tier")

    if tier == "lgs":
        # Verify LGS profile exists
        lgs = await get_user_lgs(db, current_user.id)
        if not lgs:
            raise HTTPException(
                status_code=400,
                detail="LGS subscription requires LGS profile"
            )

    stripe_service = StripeService()
    checkout_url = await stripe_service.create_checkout_session(
        user_id=current_user.id,
        tier=tier,
        success_url=f"{settings.FRONTEND_URL}/settings/subscription?success=true",
        cancel_url=f"{settings.FRONTEND_URL}/settings/subscription?canceled=true",
    )

    return {"checkout_url": checkout_url}

@router.get("/my-subscription")
async def get_my_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's subscription status."""
    sub = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .where(Subscription.status == "active")
    )
    subscription = sub.scalar_one_or_none()

    if not subscription:
        return {"tier": "free", "status": "none"}

    return {
        "tier": subscription.tier,
        "status": subscription.status,
        "current_period_end": subscription.current_period_end,
    }
```

**Step 3: Webhook handler**

```python
# backend/app/api/routes/webhooks.py
@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhooks."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    stripe_service = StripeService()
    result = await stripe_service.handle_webhook(payload, sig_header)

    # Update database based on event
    if result["action"] == "subscription_created":
        # Create subscription record
        pass
    elif result["action"] == "subscription_canceled":
        # Update subscription status
        pass

    return {"received": True}
```

---

## Task 3.8: Affiliate Link Integration

**Files:**
- Modify: `backend/app/api/routes/cards.py`
- Modify: `frontend/src/components/PriceDisplay.tsx`

```python
# When returning prices, include affiliate links
def get_affiliate_url(marketplace: str, card_name: str, set_code: str) -> str:
    """Generate affiliate URL for marketplace."""
    if marketplace == "tcgplayer":
        base = "https://www.tcgplayer.com/search/magic/product"
        params = f"?q={quote(card_name)}&setName={set_code}"
        affiliate_tag = settings.TCGPLAYER_AFFILIATE_ID
        return f"{base}{params}&partner={affiliate_tag}"
    elif marketplace == "cardmarket":
        # CardMarket uses referral cookies
        return f"https://www.cardmarket.com/en/Magic/Products/Search?searchString={quote(card_name)}&ref={settings.CARDMARKET_AFFILIATE_ID}"
    return None
```

```tsx
// frontend/src/components/PriceDisplay.tsx
<a
  href={price.affiliate_url}
  target="_blank"
  rel="noopener noreferrer"
  className="text-blue-500 hover:underline"
>
  ${price.amount.toFixed(2)} on {price.marketplace}
</a>
```

---

## Task 3.9-3.10: (Abbreviated)

**Task 3.9: LGS Subscription Tier**
- Verified badge on profile
- Access to demand analytics
- Event promotion features
- Priority support

**Task 3.10: API for Partners**
- Rate-limited public API
- Premium tier: 1000 requests/day
- LGS tier: 10,000 requests/day
- Documentation at `/api/docs`

---

## Phase 3 Completion Checklist

- [ ] Task 3.1: LGS registration flow
- [ ] Task 3.2: LGS demand dashboard
- [ ] Task 3.3: LGS buylist intelligence
- [ ] Task 3.4: LGS event promotion
- [ ] Task 3.5: Premium tier - more alerts
- [ ] Task 3.6: Premium tier - advanced analytics
- [ ] Task 3.7: Premium tier - portfolio reports
- [ ] Task 3.8: Affiliate link integration
- [ ] Task 3.9: LGS subscription tier
- [ ] Task 3.10: API for partners

**Success Criteria:**
- 10+ LGS registered
- Stripe subscriptions processing
- Affiliate links generating clicks
- Demand data accurate and valuable

---

## Revenue Projections

| Scenario | Users | Premium (5%) | LGS | Monthly |
|----------|-------|--------------|-----|---------|
| Launch | 1,000 | 50 @ $5 | 5 @ $20 | $350 |
| 6 months | 10,000 | 500 @ $5 | 50 @ $20 | $3,500 |
| 1 year | 50,000 | 2,500 @ $5 | 200 @ $20 | $16,500 |

Plus affiliate revenue (estimated 2-5% of GMV driven).

---

## Post-Phase 3: Future Considerations

- Mobile app (React Native)
- Trade meetup coordination
- Integration with TCGPlayer Direct
- AI-powered price predictions
- Collection insurance valuations
