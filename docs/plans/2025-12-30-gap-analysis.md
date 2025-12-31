# System Gap Analysis: Current State vs. Platform Spec

**Date:** 2025-12-30
**Assessment Method:** MCP tools + codebase analysis
**Status:** Current state fully assessed

---

## Executive Summary

The platform is in **excellent health** with a solid foundation. The core price tracking, analytics, and recommendation engine are production-ready. However, **all social/trading features from Phases 0-3 are missing** - this is expected as they haven't been implemented yet.

| Category | Status | Notes |
|----------|--------|-------|
| Infrastructure | ✅ Excellent | 6 containers, 0 errors, fresh data |
| Database | ✅ Healthy | 34 tables, 98K cards, migrations current |
| Price Data | ✅ Fresh | 4 marketplaces, updated 10 min ago |
| Redis Cache | ✅ Active | 4MB used, 53% hit rate |
| Phase 0 Features | ❌ Not Started | 0/16 tasks complete |
| Phase 1 Features | ❌ Not Started | 0/28 tasks complete |
| Phase 2 Features | ❌ Not Started | 0/30 tasks complete |
| Phase 3 Features | ❌ Not Started | 0/24 tasks complete |

---

## Current System State

### Infrastructure Health

```
┌─────────────────────────────────────────────────────────────┐
│ CONTAINERS (6/6 Running)                                    │
├─────────────────────────────────────────────────────────────┤
│ ✅ backend    - FastAPI server                              │
│ ✅ frontend   - Next.js app                                 │
│ ✅ db         - PostgreSQL                                  │
│ ✅ redis      - Cache + Celery broker                       │
│ ✅ worker     - Celery worker                               │
│ ✅ scheduler  - Celery beat                                 │
└─────────────────────────────────────────────────────────────┘
```

### Database Statistics

| Table | Row Count | Status |
|-------|-----------|--------|
| cards | 98,579 | ✅ Full catalog |
| signals | 898,287 | ✅ Rich analytics |
| price_snapshots | ~500K+ | ✅ Time-series data |
| recommendations | 2,329 | ✅ Active |
| users | 1 | ⚠️ Only test user |
| notifications | 0 | ⚠️ Empty (no triggers yet) |
| want_list_items | 0 | ⚠️ No user data |
| inventory_items | 0 | ⚠️ No user data |

### Data Freshness

| Marketplace | Last Update | 24h Snapshots |
|-------------|-------------|---------------|
| Manapool | 10 min ago | 438 |
| TCGPlayer | 18 min ago | 1,846 |
| MTGO | 27 min ago | 661 |
| Cardmarket | 27 min ago | 1,435 |

### Celery Tasks (All Running)

| Task | Schedule | Status |
|------|----------|--------|
| collect_price_data | Every 30 min | ✅ |
| collect_inventory_prices | Every 15 min | ✅ |
| run_analytics | Every 1 hour | ✅ |
| generate_recommendations | Every 6 hours | ✅ |
| import_scryfall_cards | On demand | ✅ |

---

## Gap Analysis by Phase

### Phase 0: Foundation (16 tasks)

#### Missing Database Tables

| Table | Purpose | Priority |
|-------|---------|----------|
| `connected_accounts` | Discord/platform OAuth linking | HIGH |
| `notification_preferences` | Granular notification settings | MEDIUM |

#### Missing User Fields

Current `users` table has basic auth fields. Missing:

```sql
-- Need to add via migration:
avatar_url VARCHAR(500)           -- Profile picture URL
bio TEXT                          -- User bio (max 500 chars)
location VARCHAR(100)             -- City/region for local trades
trade_count INTEGER DEFAULT 0     -- Completed trades counter
reputation_score DECIMAL(3,2)     -- 0.00-5.00 rating
discord_id VARCHAR(20)            -- Discord snowflake ID
last_active_at TIMESTAMPTZ        -- For "online" status
```

#### Missing want_list_items Field

```sql
-- Need to add:
is_active BOOLEAN DEFAULT TRUE    -- Soft delete without losing data
```

#### Missing Services

| Service | Description | Files to Create |
|---------|-------------|-----------------|
| Hashids | Encode IDs for public URLs | `backend/app/core/hashids.py` |
| Discord OAuth | Link Discord accounts | `backend/app/api/routes/oauth.py` |
| Email Service | Send notifications | `backend/app/services/email/` |
| Public Profiles | View other users | `backend/app/api/routes/profiles.py` |

#### Missing Frontend Pages

| Page | Route | Purpose |
|------|-------|---------|
| Public Profile | `/u/:hashid` | View user's public info |
| Profile Settings | `/settings/profile` | Edit bio, avatar, location |
| Notification Settings | `/settings/notifications` | Configure alerts |

---

### Phase 1: Intelligence + Distribution (28 tasks)

#### Missing Database Tables

| Table | Purpose | Priority |
|-------|---------|----------|
| `have_list_items` | Cards available for trade | HIGH |

**Schema needed:**
```sql
CREATE TABLE have_list_items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    card_id INTEGER REFERENCES cards(id),
    quantity INTEGER DEFAULT 1,
    condition VARCHAR(20) NOT NULL,
    is_foil BOOLEAN DEFAULT FALSE,
    language VARCHAR(10) DEFAULT 'en',
    asking_price DECIMAL(10,2),
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Missing want_list_items Fields

```sql
-- Need to add:
quantity INTEGER DEFAULT 1
min_condition VARCHAR(20)
preferred_conditions JSONB          -- ["NM", "LP"]
max_price DECIMAL(10,2)
```

#### Missing Services

| Service | Description | Complexity |
|---------|-------------|------------|
| Discord Bot | Separate Python process | HIGH |
| Matching Algorithm | Find compatible trades | MEDIUM |
| Bot API Gateway | Secure bot-to-backend | MEDIUM |

---

### Phase 2: Social + Trust (30 tasks)

#### Missing Database Tables (6 new tables)

```sql
-- Trade Proposals
CREATE TABLE trade_proposals (
    id SERIAL PRIMARY KEY,
    hashid VARCHAR(12) UNIQUE,
    proposer_id INTEGER REFERENCES users(id),
    recipient_id INTEGER REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'pending',
    proposer_value DECIMAL(10,2),
    recipient_value DECIMAL(10,2),
    message TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE trade_proposal_items (
    id SERIAL PRIMARY KEY,
    proposal_id INTEGER REFERENCES trade_proposals(id),
    side VARCHAR(10),  -- 'proposer' or 'recipient'
    card_id INTEGER REFERENCES cards(id),
    quantity INTEGER DEFAULT 1,
    condition VARCHAR(20),
    is_foil BOOLEAN DEFAULT FALSE
);

-- Messaging
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER REFERENCES users(id),
    recipient_id INTEGER REFERENCES users(id),
    trade_proposal_id INTEGER REFERENCES trade_proposals(id),
    content TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE message_reads (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id),
    user_id INTEGER REFERENCES users(id),
    read_at TIMESTAMPTZ DEFAULT NOW()
);

-- Reputation
CREATE TABLE user_reputation (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) UNIQUE,
    total_reviews INTEGER DEFAULT 0,
    average_rating DECIMAL(3,2),
    tier VARCHAR(20) DEFAULT 'new',
    last_calculated_at TIMESTAMPTZ
);

CREATE TABLE reputation_reviews (
    id SERIAL PRIMARY KEY,
    reviewer_id INTEGER REFERENCES users(id),
    reviewee_id INTEGER REFERENCES users(id),
    trade_proposal_id INTEGER REFERENCES trade_proposals(id),
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Missing Services

| Service | Description | Complexity |
|---------|-------------|------------|
| WebSocket Server | Real-time messaging | HIGH |
| Reputation Calculator | Tier assignment + decay | MEDIUM |
| Trade Workflow | State machine for proposals | MEDIUM |

---

### Phase 3: Transaction + Business (24 tasks)

#### Missing Database Tables

```sql
CREATE TABLE user_signals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    card_id INTEGER REFERENCES cards(id),
    signal_type VARCHAR(20),  -- 'buying', 'selling', 'watching'
    price_target DECIMAL(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE lgs_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) UNIQUE,
    store_name VARCHAR(200),
    address TEXT,
    verified_at TIMESTAMPTZ,
    commission_rate DECIMAL(4,2)
);

CREATE TABLE escrow_transactions (
    id SERIAL PRIMARY KEY,
    trade_proposal_id INTEGER REFERENCES trade_proposals(id),
    stripe_payment_intent_id VARCHAR(100),
    amount DECIMAL(10,2),
    status VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Missing Services

| Service | Description | Complexity |
|---------|-------------|------------|
| Stripe Connect | Escrow payments | HIGH |
| LGS Verification | Store identity check | MEDIUM |
| Signal Aggregation | Market sentiment | LOW |

---

## Environment Variables Status

### Currently Configured ✅

```bash
# Database, Redis, API basics - all working
DATABASE_URL, REDIS_URL, SECRET_KEY, CORS_ORIGINS
# Marketplace APIs
TCGPLAYER_API_KEY, CARDTRADER_API_TOKEN, MANAPOOL_API_TOKEN
# LLM
OPENAI_API_KEY, ANTHROPIC_API_KEY
```

### Needs Configuration for Phase 0+

```bash
# Discord (Phase 0-1)
DISCORD_CLIENT_ID=          # ❌ Not set
DISCORD_CLIENT_SECRET=      # ❌ Not set
DISCORD_BOT_TOKEN=          # ❌ Not set (Phase 1)

# Email (Phase 0)
EMAIL_PROVIDER=console      # ⚠️ Dev mode only
RESEND_API_KEY=             # ❌ Not set

# Stripe (Phase 3)
STRIPE_SECRET_KEY=          # ❌ Not set
STRIPE_PUBLISHABLE_KEY=     # ❌ Not set
```

---

## Recommended Implementation Order

Based on dependencies and value delivery:

### Week 1-2: Phase 0 Foundation
1. **Task 0.1-0.3**: Hashids + public card endpoints (unblocks sharing)
2. **Task 0.4-0.6**: User profile fields + settings page
3. **Task 0.7-0.9**: Notification system (already has table!)

### Week 3-4: Phase 0 Completion + Phase 1 Start
4. **Task 0.10-0.12**: Discord OAuth (unblocks Phase 1 bot)
5. **Task 0.13-0.16**: Analytics + cleanup
6. **Task 1.1-1.5**: Have list basics

### Week 5-6: Phase 1 Core
7. **Task 1.6-1.10**: Want list extensions
8. **Task 1.11-1.16**: Discord bot MVP

### Week 7-8: Phase 1 Completion + Phase 2 Start
9. **Task 1.17-1.28**: Matching algorithm
10. **Task 2.1-2.8**: Trade proposals

### Week 9-12: Phase 2 Social
11. **Task 2.9-2.18**: Messaging system
12. **Task 2.19-2.30**: Reputation system

### Week 13-16: Phase 3 Business
13. **Task 3.1-3.24**: Signals, LGS, Escrow

---

## Critical Path Items

These items block multiple downstream features:

| Item | Blocks | Priority |
|------|--------|----------|
| Hashids setup | All public URLs | CRITICAL |
| Discord OAuth | Bot, social features | HIGH |
| User profile fields migration | Profiles, reputation | HIGH |
| have_list_items table | All trading features | HIGH |
| WebSocket infrastructure | Real-time messaging | MEDIUM |

---

## What's Working Well

1. **Price data pipeline** - 4 marketplaces, fresh data, no errors
2. **Analytics engine** - 898K signals generated
3. **Recommendation system** - 2,329 active recommendations
4. **Card catalog** - 98K cards with semantic fields
5. **Infrastructure** - All containers stable, Redis healthy
6. **Test fixtures** - conftest.py ready for TDD

---

## Immediate Next Steps

1. **Start Phase 0 Task 0.1**: Install hashids, create encoding utility
2. **Run first migration**: Add user profile fields
3. **Create connected_accounts table**: For Discord OAuth prep
4. **Set up Discord Developer App**: Get client ID/secret

The foundation is solid. Time to build the social layer.
