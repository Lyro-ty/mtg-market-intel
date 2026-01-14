# Dualcaster Deals Roadmap

**Last Updated:** 2026-01-13

This is the single source of truth for remaining work. See `CURRENT-STATE.md` for what's already implemented.

---

## Vision

**Dualcaster Deals = Bloomberg Terminal + LinkedIn for MTG**

The platform:
1. **Tracks** prices across all major marketplaces (4 sources)
2. **Analyzes** market trends, meta shifts, and trading opportunities
3. **Connects** buyers, sellers, and local game stores for discovery

**Core Principle:** Facilitate introductions, NOT transactions. Revenue from subscriptions + affiliate links.

---

## Phase Overview

| Phase | Focus | Status | Priority |
|-------|-------|--------|----------|
| Intelligence | Data gaps, signals, analysis | Next | HIGH |
| Public Access | Hashids, public endpoints | Pending | MEDIUM |
| Monetization | Stripe, tiers, API access | Future | LOW |

---

## Phase: Intelligence Enhancement

**Goal:** Fill data gaps and enhance signal generation

### Task I-1: Tournament Data Verification
**Priority:** HIGH
**Files:** `backend/app/tasks/tournaments.py`

Verify tournaments table is populated. If empty:
- Check TopDeck.gg API integration
- Fix task scheduling
- Backfill historical data

**Verification:**
```sql
SELECT COUNT(*) FROM tournaments;  -- Should be > 500
SELECT MAX(date) FROM tournaments; -- Should be recent
```

### Task I-2: News Collection Verification
**Priority:** HIGH
**Files:** `backend/app/tasks/news.py`

Verify news_articles table is populated. If empty:
- Check RSS feed configuration
- Check NewsAPI.ai integration
- Verify card mention extraction

**Verification:**
```sql
SELECT COUNT(*) FROM news_articles;  -- Should be > 50
SELECT MAX(published_at) FROM news_articles; -- Should be recent
```

### Task I-3: Meta Analysis Signals
**Priority:** HIGH
**Files:** `backend/app/services/meta_analysis.py`, `backend/app/tasks/analytics.py`

Create META_SPIKE signals from tournament data:
- Calculate meta share per card per format
- Detect significant changes (>50% increase)
- Generate signals for trending cards

### Task I-4: Arbitrage Signals
**Priority:** MEDIUM
**Files:** `backend/app/tasks/arbitrage_signals.py`

Cross-market price comparison:
- Compare prices across TCGPlayer, CardTrader, Manapool
- Calculate after-fees profit potential
- Generate ARBITRAGE_OPPORTUNITY signals for >10% spreads

### Task I-5: Reprint Risk Scoring
**Priority:** MEDIUM
**Files:** Migration + `backend/app/models/card.py`

Add reprint tracking:
- `first_printed_at` - Original print date
- `reprint_count` - Number of reprints
- `last_reprinted_at` - Most recent reprint
- `reprint_risk_score` - Calculated risk (0-100)

### Task I-6: Buylist Price Tracking
**Priority:** LOW
**Files:** `backend/app/services/ingestion/card_kingdom.py`

Add Card Kingdom buylist adapter:
- Scrape buylist prices
- Store in buylist_snapshots
- Calculate spreads vs retail

---

## Phase: Public Access

**Goal:** Enable sharing without authentication

### Task P-1: Hashids Encoding
**Priority:** MEDIUM
**Files:** `backend/app/core/hashids.py`, tests

Create hashids utility:
- Encode/decode user IDs
- Encode/decode card IDs
- Different salts per entity type

### Task P-2: Public Card Endpoints
**Priority:** MEDIUM
**Files:** `backend/app/api/routes/cards.py`

Add public endpoints:
- `GET /cards/public/{hashid}` - Card details without auth
- `GET /cards/public/{hashid}/prices` - Price history without auth
- No internal IDs in response

### Task P-3: Public User Profiles
**Priority:** LOW
**Files:** `backend/app/api/routes/profiles.py`, `frontend/src/app/u/[hashid]/page.tsx`

Public profile viewing:
- `/u/{hashid}` route
- Display bio, location, endorsements
- Show public inventory (if opted in)

---

## Phase: Monetization

**Goal:** Revenue through subscriptions and affiliate links

### Task M-1: Stripe Integration
**Priority:** LOW
**Files:** `backend/app/services/stripe.py`, webhooks

Stripe Billing setup:
- Configure Stripe API keys
- Create subscription products
- Implement webhook handlers

### Task M-2: Subscription Tiers
**Priority:** LOW
**Files:** Migration, middleware

Tier limits:
| Tier | Price | Price Alerts | History | API Access |
|------|-------|--------------|---------|------------|
| Free | $0 | 5 | 30 days | No |
| Premium | $5/mo | Unlimited | 1 year | Yes |
| LGS | $20/mo | Unlimited | 1 year | Priority |

### Task M-3: Affiliate Links
**Priority:** LOW
**Files:** `frontend/src/components/AffiliateLink.tsx`

TCGPlayer/CardMarket affiliate integration:
- Generate affiliate URLs
- Track click-throughs
- Revenue attribution

---

## Development Experience Tasks

### Task D-1: Development Skills
**Priority:** HIGH
**Files:** `.claude/skills/`

Create project-specific skills for Claude Code:
- `mtg-intel:api-development`
- `mtg-intel:frontend-development`
- `mtg-intel:celery-tasks`
- `mtg-intel:database-changes`
- `mtg-intel:discord-bot`

### Task D-2: MCP Server Enhancements
**Priority:** MEDIUM
**Files:** `backend/mcp_server/tools/`

Add validation tools:
- `get_implementation_status`
- `list_missing_tests`
- `get_schema_differences`
- `analyze_dead_letter_queue`

### Task D-3: Backend Agents
**Priority:** MEDIUM
**Files:** `backend/app/services/agents/`

Create validation agents:
- ImplementationValidator
- CodeQualityAgent
- DataIntegrityAgent

### Task D-4: Discord Bot Dev Cogs
**Priority:** LOW
**Files:** `discord-bot/bot/cogs/`

Add development cogs:
- `/status` - System health
- `/trigger-task` - Manual task triggers
- `/clear-cache` - Cache invalidation

---

## Completed Work (Reference)

These are documented here for context but are DONE:

- Core price tracking (4 marketplaces)
- Analytics engine (900K+ signals)
- Recommendation system (2K+ active)
- User authentication (JWT + OAuth)
- Inventory & want list management
- Social features (connections, messaging, endorsements)
- Trading posts (LGS registration, quotes, events)
- Discord bot (7 cogs, alert delivery)
- WebSocket real-time updates
- Architecture remediation (security, performance, reliability)

---

## Implementation Notes

### Parallel Work Opportunities
These can be worked on simultaneously:
- Intelligence tasks (I-1 through I-6) are independent
- Public access tasks depend on P-1 (Hashids) first
- Development tasks (D-1 through D-4) are independent

### Dependencies
```
P-1 (Hashids) → P-2 (Public Cards) → P-3 (Public Profiles)
M-1 (Stripe) → M-2 (Tiers)
I-1 (Tournaments) → I-3 (Meta Signals)
```

### Testing Requirements
Each task should include:
- Unit tests for new functions
- Integration tests for new endpoints
- Update to CURRENT-STATE.md on completion

---

## Archive

Detailed phase plans are preserved in `docs/archive/`:
- `2025-12-30-phase0-revised-plan.md`
- `2025-12-30-phase1-revised-plan.md`
- `2025-12-30-phase2-revised-plan.md`
- `2025-12-30-phase3-revised-plan.md`
- `2025-12-30-revised-platform-vision.md`

These contain detailed task breakdowns if more granular planning is needed.
