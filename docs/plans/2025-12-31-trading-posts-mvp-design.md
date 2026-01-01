# Trading Posts MVP Design

**Date:** 2025-12-31
**Status:** Approved
**Author:** Claude + User

## Overview

MVP Trading Posts enables local game stores to receive trade-in leads and promote their events, while users can get instant quotes and find nearby stores.

### Core Positioning

Trading Posts are LGS partners on the Dualcaster Deals platform. They receive warm leads (trade-in quotes) from users who want to sell cards, and can promote events to drive foot traffic. No transaction processing — deals happen in-store.

### Core Features

1. **Trade-in Estimator** — Users build a quote, compare store offers, submit to preferred store(s)
2. **Store Profiles** — Hours, location, services, branding
3. **Event Promotion** — Tournaments, sales, releases
4. **Light Verification** — Email required, verified badge for extra trust

### What's NOT in MVP

- Demand dashboard (Phase 2 — premium feature)
- Buylist intelligence / recommendations
- Inventory sync with TCGPlayer/Crystal Commerce
- Payment processing
- Customer tracking / CRM
- Direct messaging (beyond quotes)

### Success Criteria

- 10+ stores registered within 30 days
- 50+ quote submissions within 60 days
- At least 1 store converts a quote to an in-store sale

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Trade-in flow | Lead generation | Store gets notification with full list, can accept/counter/decline |
| Card entry methods | All three (inventory, manual, bulk import) | Flexibility for different user preferences |
| Pricing model | Store-specific margins | Stores set % of market they pay, creates competition |
| Store response options | Accept/Counter/Decline | Flexible without over-complicating |
| User quote flow | Quote first, then shop | Build quote → compare offers → submit to winner(s) |
| Store notifications | Email for MVP | Universal, reliable, no extra setup |
| Verification | Light (email required, badge optional) | Low friction to start, trust incentive for full verification |

---

## Data Model

```sql
-- Store profiles
CREATE TABLE trading_posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) UNIQUE NOT NULL,
    store_name VARCHAR(200) NOT NULL,
    description TEXT,
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(50),
    country VARCHAR(50) DEFAULT 'US',
    postal_code VARCHAR(20),
    phone VARCHAR(20),
    website VARCHAR(500),
    hours JSONB,  -- {"monday": "10:00-20:00", ...}
    services TEXT[],  -- ['singles', 'tournaments', 'buylist', 'grading']
    logo_url VARCHAR(500),
    buylist_margin DECIMAL(3,2) DEFAULT 0.50,  -- 50% of market price
    email_verified_at TIMESTAMPTZ,
    verified_at TIMESTAMPTZ,  -- Full verification (badge)
    verification_method VARCHAR(50),  -- 'manual', 'business_license', 'phone'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_trading_posts_city ON trading_posts(city);
CREATE INDEX ix_trading_posts_state ON trading_posts(state);
CREATE INDEX ix_trading_posts_verified ON trading_posts(email_verified_at)
    WHERE email_verified_at IS NOT NULL;

-- Trade-in quotes
CREATE TABLE trade_quotes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',  -- draft, submitted, completed, expired
    total_market_value DECIMAL(10,2),  -- Sum of market prices
    item_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_trade_quotes_user ON trade_quotes(user_id);
CREATE INDEX ix_trade_quotes_status ON trade_quotes(status);

-- Items in a quote
CREATE TABLE trade_quote_items (
    id SERIAL PRIMARY KEY,
    quote_id INTEGER REFERENCES trade_quotes(id) ON DELETE CASCADE,
    card_id INTEGER REFERENCES cards(id) NOT NULL,
    quantity INTEGER DEFAULT 1,
    condition VARCHAR(20) DEFAULT 'NM',  -- NM, LP, MP, HP, DMG
    market_price DECIMAL(10,2) NOT NULL,  -- Snapshot at time of addition
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(quote_id, card_id, condition)
);

CREATE INDEX ix_trade_quote_items_quote ON trade_quote_items(quote_id);

-- Quote submissions to stores
CREATE TABLE trade_quote_submissions (
    id SERIAL PRIMARY KEY,
    quote_id INTEGER REFERENCES trade_quotes(id) ON DELETE CASCADE,
    trading_post_id INTEGER REFERENCES trading_posts(id) NOT NULL,
    offer_amount DECIMAL(10,2) NOT NULL,  -- Based on store margin at submission time
    status VARCHAR(20) DEFAULT 'pending',  -- pending, accepted, countered, declined, user_accepted, user_declined
    counter_amount DECIMAL(10,2),  -- If store countered
    counter_note TEXT,  -- Reason for counter
    store_responded_at TIMESTAMPTZ,
    user_responded_at TIMESTAMPTZ,  -- If responding to counter
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(quote_id, trading_post_id)
);

CREATE INDEX ix_trade_quote_submissions_quote ON trade_quote_submissions(quote_id);
CREATE INDEX ix_trade_quote_submissions_store ON trade_quote_submissions(trading_post_id);
CREATE INDEX ix_trade_quote_submissions_status ON trade_quote_submissions(status);

-- Store events
CREATE TABLE trading_post_events (
    id SERIAL PRIMARY KEY,
    trading_post_id INTEGER REFERENCES trading_posts(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    event_type VARCHAR(50) NOT NULL,  -- tournament, sale, release, meetup
    format VARCHAR(50),  -- modern, standard, commander, pioneer, legacy, vintage, pauper
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    entry_fee DECIMAL(10,2),
    max_players INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_trading_post_events_store ON trading_post_events(trading_post_id);
CREATE INDEX ix_trading_post_events_start ON trading_post_events(start_time);
CREATE INDEX ix_trading_post_events_type ON trading_post_events(event_type);
```

---

## User Flows

### Flow 1: Store Registration

```
User clicks "Claim Your Trading Post"
  → Fills form (name, address, hours, services, margin)
  → Submits → Email verification sent
  → Clicks verification link → Store goes live
  → Optional: Complete full verification for verified badge
```

### Flow 2: Trade-in Quote (User)

```
User clicks "Get a Quote" or "Sell Cards"
  → Option A: Select from existing inventory (marks cards for sale)
  → Option B: Search and add cards manually
  → Option C: Bulk import CSV/list
  → Adds cards with quantity + condition
  → Sees total market value
  → Clicks "Find Offers"
  → Sees nearby stores with their offer amounts (sorted by offer)
  → Selects one or more stores → Submits
  → Gets email when store responds
```

### Flow 3: Quote Response (Store)

```
Store gets email: "New quote submission - $142 in cards"
  → Clicks link → Views full card list with conditions
  → Reviews cards
  → Option A: Accept → User notified, brings cards in
  → Option B: Counter → Enters new amount + note → User decides
  → Option C: Decline → User notified
```

### Flow 4: Counter Response (User)

```
User gets email: "Store X countered your quote"
  → Clicks link → Sees counter amount + note
  → Option A: Accept counter → Store notified
  → Option B: Decline counter → Store notified, can submit elsewhere
```

### Flow 5: Event Creation (Store)

```
Store dashboard → "Create Event"
  → Fills form (title, type, format, date, entry fee, max players)
  → Submits → Event visible on store profile + nearby events feed
```

### Flow 6: Find Nearby Stores/Events (User)

```
User browses "Trading Posts" or "Events"
  → Filters by city/state or uses location
  → Sees list of stores with profiles
  → Clicks store → Sees profile, upcoming events, "Get Quote" button
```

---

## API Endpoints

### Trading Posts

```
POST   /api/trading-posts/register         — Create store profile
GET    /api/trading-posts/me               — Get own store profile
PUT    /api/trading-posts/me               — Update profile (including margin)
GET    /api/trading-posts/nearby           — List stores by location (?city=&state=)
GET    /api/trading-posts/:id              — Public store profile
POST   /api/trading-posts/verify-email     — Resend verification email
POST   /api/trading-posts/confirm-email    — Confirm email with token
```

### Trade Quotes

```
POST   /api/quotes                         — Create draft quote
GET    /api/quotes/:id                     — Get quote details with items
POST   /api/quotes/:id/items               — Add card to quote
PUT    /api/quotes/:id/items/:itemId       — Update quantity/condition
DELETE /api/quotes/:id/items/:itemId       — Remove card from quote
POST   /api/quotes/:id/import              — Bulk import cards to quote
GET    /api/quotes/:id/offers              — Preview offers from nearby stores
POST   /api/quotes/:id/submit              — Submit to selected store(s)
GET    /api/quotes/my                      — User's quotes (drafts + submitted)
```

### Quote Submissions (User side)

```
GET    /api/quotes/submissions/my                  — User's submitted quotes + statuses
POST   /api/quotes/submissions/:id/accept-counter  — Accept a counter-offer
POST   /api/quotes/submissions/:id/decline-counter — Decline a counter-offer
```

### Quote Submissions (Store side)

```
GET    /api/trading-posts/me/submissions           — Incoming quote submissions
GET    /api/trading-posts/me/submissions/:id       — Submission detail with card list
POST   /api/trading-posts/me/submissions/:id/accept
POST   /api/trading-posts/me/submissions/:id/counter  — Body: {amount, note}
POST   /api/trading-posts/me/submissions/:id/decline
```

### Events

```
POST   /api/trading-posts/me/events        — Create event
GET    /api/trading-posts/me/events        — List own events
PUT    /api/trading-posts/me/events/:id    — Update event
DELETE /api/trading-posts/me/events/:id    — Delete event
GET    /api/events/nearby                  — Public event discovery (?city=&state=&format=&days=)
GET    /api/trading-posts/:id/events       — Events for specific store
```

### Stats (existing - already updated)

```
GET    /api/stats                          — Includes trading_posts count
```

---

## Frontend Pages

### New Pages

| Route | Purpose | Auth |
|-------|---------|------|
| `/trading-posts` | Browse nearby stores | Public |
| `/trading-posts/[id]` | Store profile + events | Public |
| `/trading-posts/register` | Claim your store | Required |
| `/trading-posts/dashboard` | Store owner dashboard | Required + Store owner |
| `/trading-posts/dashboard/submissions` | Incoming quote submissions | Required + Store owner |
| `/trading-posts/dashboard/events` | Manage events | Required + Store owner |
| `/events` | Browse nearby events | Public |
| `/sell` | Start a trade-in quote | Required |
| `/sell/[quoteId]` | Build/edit quote | Required |
| `/sell/[quoteId]/offers` | Compare store offers + submit | Required |
| `/sell/history` | User's past quotes + statuses | Required |

### Updates to Existing

- Landing page: Trading Posts count now live (done)
- User dropdown: Add "My Trading Post" link if registered
- User settings: Trading Post management section

---

## Email Templates

| Email | Trigger | Recipient |
|-------|---------|-----------|
| `trading-post-verify` | Store registration | Store owner |
| `quote-submitted` | User submits quote | Store |
| `quote-accepted` | Store accepts | User |
| `quote-countered` | Store counters | User |
| `quote-declined` | Store declines | User |
| `counter-accepted` | User accepts counter | Store |
| `counter-declined` | User declines counter | Store |

---

## Implementation Tasks

| # | Task | Effort | Dependencies |
|---|------|--------|--------------|
| 1 | Database migration: all new tables | S | — |
| 2 | Backend models (SQLAlchemy) | S | 1 |
| 3 | Backend schemas (Pydantic) | S | 2 |
| 4 | Trading post registration + profile CRUD | M | 3 |
| 5 | Email verification flow | S | 4 |
| 6 | Trade quote creation + item management | M | 3 |
| 7 | Bulk import into quotes | M | 6, existing import infra |
| 8 | Offer preview endpoint | M | 6 |
| 9 | Quote submission + email to stores | M | 6, 5 |
| 10 | Store submission management (accept/counter/decline) | M | 9 |
| 11 | User counter response endpoints | S | 10 |
| 12 | Event CRUD for stores | S | 4 |
| 13 | Nearby stores + events discovery | S | 4, 12 |
| 14 | Frontend: `/trading-posts` browse + profile | M | 4, 13 |
| 15 | Frontend: `/trading-posts/register` | M | 4, 5 |
| 16 | Frontend: Store dashboard + submissions | M | 10 |
| 17 | Frontend: `/sell` quote builder | L | 6, 7 |
| 18 | Frontend: `/sell/[id]/offers` + submit | M | 8, 9 |
| 19 | Frontend: `/sell/history` | S | 11 |
| 20 | Frontend: Events pages | S | 12, 13 |
| 21 | Email templates | S | 9, 10, 11 |

**Effort Key:** XS = hours, S = 1 day, M = 2-3 days, L = 4-5 days

**Estimated Total:** 3-4 weeks

---

## Verification Badge Criteria (Phase 2)

For stores wanting the verified badge:

- Business license upload + manual review
- Phone verification (Twilio)
- Domain email verification (@storename.com)
- Physical address verification (postcard with code)

Badge provides:
- "Verified Trading Post" indicator on profile
- Higher ranking in search results
- Trust signal for users submitting quotes

---

## Future Enhancements (Post-MVP)

1. **Demand Dashboard** — What cards do local users want? (premium feature)
2. **Buylist Intelligence** — Recommended pricing based on demand
3. **Direct Messaging** — "Do you have X?" inquiries
4. **Inventory Sync** — TCGPlayer/Crystal Commerce integration
5. **Push Notifications** — Mobile alerts for stores
6. **Customer Tracking** — CRM-lite for repeat customers
7. **Foot Traffic Notifications** — Alert users when nearby store has their want list cards
