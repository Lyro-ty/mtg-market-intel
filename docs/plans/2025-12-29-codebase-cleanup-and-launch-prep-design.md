# Codebase Cleanup & Launch Prep Design

**Date:** 2025-12-29
**Status:** ⏳ Partially Implemented (Core items done: Manapool adapter, WelcomeModal, Sentry, dead code removal. Remaining: PWA, UptimeRobot, mobile polish)
**Scope:** Fix broken systems, remove dead code, finish near-complete features, prepare for advertising

---

## Executive Summary

Transform Dualcaster Deals from "working prototype with cruft" to "polished product ready for advertising" in 4 weeks.

**Current state:** Early users (shop owner, collectors) giving positive feedback on price tracking and inventory value. Codebase has accumulated dead features, broken integrations, and over-engineering.

**Goal:** Clean foundation that's mobile-friendly, monitored, and generating TCGPlayer affiliate revenue.

---

## Strategic Context

### Origin Story
Started as multi-source price aggregator (TCGPlayer, CardMarket, Manapool). Evolved into inventory + recommendations platform. Original multi-source vision partially unfulfilled (adapters incomplete).

### Core Value Proposition (Phase 1)
- **Shop owners:** Check prices, track inventory value
- **Collectors:** Avoid bad decisions, track collection
- **Hobbyists:** Find cards for decks

### Revenue Model
TCGPlayer affiliate links on Want List and Card pages. User clicks to buy → kickback.

---

## Current Issues (18 Total)

### Broken (3)
| Issue | Impact | Location |
|-------|--------|----------|
| `asyncio.run()` in Celery tasks | Resource leaks, performance | `backend/app/tasks/*.py` via `run_async()` |
| `.mcp.json` broken env var syntax | MCP server can't connect to DB | `.mcp.json:12` |
| Inconsistent credentials | Silent deployment failures | `.env.example`, `.mcp.json`, `config.py` |

### Dead Weight (9)
| Issue | Why Remove | Location |
|-------|------------|----------|
| CardMarket env vars | No API access without affiliation | `config.py:74-77` |
| NewsArticle/CardNewsMention models | Never implemented, no user request | `models/news.py` |
| ListingFeatureVector | Only CardFeatureVector is used | `models/feature_vector.py:98-147` |
| LOCAL_LLM env vars | Never implemented | `config.py:62-63` |
| Empty script files | 0 bytes, never implemented | `scripts/bulk_seed_*.py` (2 files) |
| Unused frontend debounce() | Using useDebouncedValue hook | `frontend/src/lib/utils.ts:152` |
| Duplicate _parse_setting_value() | Same function in 2 places | `routes/settings.py:40`, `tasks/recommendations.py:67` |
| Duplicate parse_plaintext_line() | Two versions in same file | `routes/inventory.py:98,172` |
| Silent `pass` exception handlers | Hide bugs, make debugging impossible | 9 locations across codebase |

### To Build (2)
| Feature | Status | Effort |
|---------|--------|--------|
| Manapool adapter | Never built (API available, have token) | 4-8 hours |
| WelcomeModal | Built but not wired up | 2-3 hours |

**Manapool API Details:**
- Server: `https://manapool.com/api/v1`
- Auth: `X-ManaPool-Access-Token` header (token in .env as `MANAPOOL_ACCESS_TOKEN`)
- Key endpoints:
  - `GET /prices/singles` - All in-stock singles prices (bulk)
  - `POST /card_info` - Lookup up to 100 cards by name
  - `GET /inventory/listings` - Marketplace listings

### Over-Engineered (5) - Defer
| Issue | Status | Why Defer |
|-------|--------|-----------|
| LLM factory with lru_cache | Works | Low impact |
| Custom in-memory cache | Works | Redis swap can wait |
| 1100-line api.ts monolith | Works | Split when adding features |
| Over-defensive session handling | Works | Only fix if causing bugs |
| Silent `pass` exception handling | Works but hides bugs | Add logging incrementally |

---

## Decisions

### Build vs. Remove

| Item | Decision | Rationale |
|------|----------|-----------|
| CardMarket adapter | **Remove config** | No API access without affiliation (no adapter exists) |
| Manapool adapter | **Build** | API available, have token, adds third price source |
| News models | **Remove** | No implementation, no user request |
| ListingFeatureVector | **Remove** | CardFeatureVector sufficient |
| WelcomeModal | **Wire up** | Already built, onboarding matters |
| Empty scripts | **Remove** | 0 bytes, cluttering codebase |
| Error response builders | **Keep** | Actually used in market.py (original analysis was wrong) |
| Native mobile app | **Defer** | PWA + responsive first, zero fees |

### Technology Choices

| Choice | Decision | Rationale |
|--------|----------|-----------|
| Mobile strategy | PWA + responsive CSS | 4-6 hours vs 4-8 weeks for native |
| Error tracking | Sentry (free tier) | Know when things break before users tell you |
| Uptime monitoring | UptimeRobot (free) | Get texted when site is down |

---

## Implementation Plan

### Week 1: Fix Broken + Mobile Audit

**Tier 1a: Critical Fixes (Day 1-2)**

1. Fix Celery async pattern
   - Remove `run_async()` wrapper
   - Use Celery 5.1+ native async OR run sync
   - Test all tasks still work
   - Effort: 2-3 hours

2. Fix `.mcp.json` credentials
   - Replace `${POSTGRES_PASSWORD}` with actual connection method
   - Test MCP server connects
   - Effort: 15 minutes

3. Standardize credentials
   - Single source of truth in `.env`
   - Update all references
   - Document in CLAUDE.md
   - Effort: 1 hour

**Tier 1b: Mobile Audit (Day 3-5)**

4. Audit responsive breakpoints
   - Test all pages at 375px, 768px, 1024px
   - List broken layouts
   - Effort: 2 hours

5. Fix critical mobile breaks
   - Navigation, cards list, inventory table
   - Effort: 4-8 hours depending on findings

### Week 2: Remove Dead Weight

**Tier 2a: Model Cleanup (Day 1-2)**

6. Remove NewsArticle/CardNewsMention
   - Delete `models/news.py`
   - Remove from `models/__init__.py`
   - Check for orphan migrations
   - Effort: 30 minutes

7. Remove ListingFeatureVector
   - Keep CardFeatureVector only
   - Update any imports
   - Effort: 20 minutes

**Tier 2b: Config Cleanup (Day 2-3)**

8. Remove CardMarket config
   - Delete `cardmarket_*` env vars from config.py (lines 74-77)
   - Document in CLAUDE.md: "CardMarket requires affiliation - not implemented"
   - Effort: 15 minutes

9. Remove unused env vars
   - `local_llm_url`, `local_llm_model` (lines 62-63)
   - Effort: 10 minutes

10. Delete empty script files
    - `backend/app/scripts/bulk_seed_all_sources.py` (0 bytes)
    - `backend/app/scripts/bulk_seed_mtgjson_prices.py` (0 bytes)
    - Effort: 5 minutes

**Tier 2c: Code Cleanup (Day 3-5)**

11. Remove unused frontend debounce
    - Delete from `utils.ts:152`
    - Effort: 5 minutes

12. Consolidate `_parse_setting_value()`
    - Move to `app/core/utils.py` or similar shared location
    - Import in `routes/settings.py` and `tasks/recommendations.py`
    - Effort: 20 minutes

13. Consolidate `parse_plaintext_line()` functions
    - Merge `parse_plaintext_line()` (line 172) into `parse_plaintext_line_enhanced()` (line 98)
    - Add optional `db` parameter, make sync version work without DB
    - Effort: 30 minutes

14. Add logging to silent `pass` exception handlers
    - Locations to fix:
      - `backend/app/db/session.py:107-108`
      - `backend/app/api/routes/cards.py:951-952, 1087-1088, 1336-1337, 1353-1354, 1369-1370, 1380-1381`
      - `backend/app/api/routes/health.py:29-30`
      - `backend/app/tasks/data_seeding.py:285-286`
    - Add `logger.debug()` or `logger.warning()` with context
    - Effort: 1 hour

### Week 3: Build Features + Revenue

**Tier 3a: Manapool Adapter (Day 1-3)**

15. Build Manapool marketplace adapter
    - Create `backend/app/services/ingestion/adapters/manapool.py`
    - Implement `MarketplaceAdapter` interface
    - Auth: `X-ManaPool-Access-Token: REDACTED_MANAPOOL_TOKEN`
    - Endpoints to implement:
      - `GET /prices/singles` for bulk price sync
      - `POST /card_info` for individual card lookup
    - Add to adapter registry
    - Add MANAPOOL_ACCESS_TOKEN to config.py and .env
    - Test with real API calls
    - Effort: 4-8 hours

**Tier 3b: Onboarding (Day 3-4)**

16. Wire up WelcomeModal
    - Show on first login (check localStorage or user.has_seen_welcome flag)
    - Guide user to key features: Inventory, Cards, Recommendations
    - Add "Don't show again" option
    - Effort: 2-3 hours

**Tier 3c: Revenue (Day 4-5)**

17. TCGPlayer affiliate links
    - Add affiliate parameter to TCGPlayer URLs
    - Place on Card Detail page ("Buy on TCGPlayer" button)
    - Place on Want List items
    - Track clicks for analytics (optional)
    - Effort: 4-6 hours

**Tier 3d: PWA Setup (Day 5)**

18. Configure PWA
    - Add `manifest.json` with app name, icons, theme color
    - Add service worker for offline capability (basic caching)
    - Add install prompt banner
    - Test "Add to Home Screen" on iOS and Android
    - Effort: 4-6 hours

### Week 4: Polish + Monitoring

**Tier 4a: Monitoring (Day 1-2)**

19. Set up Sentry
    - Create free account at sentry.io
    - Add to backend (FastAPI integration via `sentry-sdk[fastapi]`)
    - Add to frontend (Next.js integration via `@sentry/nextjs`)
    - Test error capture with intentional error
    - Effort: 2-3 hours

20. Set up UptimeRobot
    - Create free account at uptimerobot.com
    - Monitor `/api/health` endpoint (5-minute interval)
    - Configure SMS/email alerts for downtime
    - Effort: 30 minutes

**Tier 4b: Error State Polish (Day 2-4)**

21. Audit and fix error states
    - Check all API error handling in frontend
    - Replace blank states with helpful messages
    - Add retry buttons where appropriate
    - Test with network disconnected
    - Effort: 4-6 hours

**Tier 4c: Core Path Tests (Day 4-5)**

22. Add critical path tests
    - Inventory valuation calculation
    - Price fetching and aggregation
    - Manapool adapter (new)
    - Recommendation generation (basic)
    - Effort: 4-6 hours

---

## Deferred Items (Month 2+)

| Item | Trigger to Revisit |
|------|-------------------|
| Split api.ts into modules | When adding new API domain |
| Replace custom cache with Redis | When scaling/performance issues |
| Simplify LLM factory | When adding new providers |
| Refactor session handling | If causing actual bugs |
| Native mobile app | If users specifically request App Store |
| Comprehensive recommendation tests | Alongside outcome tracking improvements |

---

## Success Criteria

### Week 4 Complete When:
- [ ] Zero known broken functionality
- [ ] Mobile responsive on all core pages
- [ ] WelcomeModal guides new users
- [ ] TCGPlayer affiliate links generating clicks
- [ ] PWA installable from browser
- [ ] Sentry catching errors automatically
- [ ] UptimeRobot alerting on downtime
- [ ] Core paths have test coverage

### Ready to Advertise When:
- [ ] Above criteria met
- [ ] 1 week of stable operation
- [ ] Shop owner confirms mobile works at LGS
- [ ] Error rate in Sentry < 1%

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Manapool API more broken than expected | Timebox to 4 hours, skip if blocked |
| Mobile audit reveals massive issues | Prioritize navigation + inventory only |
| Celery fix causes regressions | Run full test suite, test each task manually |
| PWA service worker caching issues | Start with minimal cache strategy |

---

## Appendix: Files to Delete/Modify

```
# Files to DELETE
backend/app/models/news.py                           # Unused model
backend/app/scripts/bulk_seed_all_sources.py         # Empty (0 bytes)
backend/app/scripts/bulk_seed_mtgjson_prices.py      # Empty (0 bytes)

# Config lines to REMOVE (in backend/app/core/config.py)
Lines 62-63: local_llm_url, local_llm_model          # Never implemented
Lines 74-77: cardmarket_* (4 vars)                   # No API access

# Functions to DELETE
frontend/src/lib/utils.ts:152 - debounce()           # Unused, using hook instead

# Models to MODIFY
backend/app/models/feature_vector.py:
  - Remove ListingFeatureVector class (lines 98-147)
  - Keep CardFeatureVector

# Functions to CONSOLIDATE (not delete)
backend/app/api/routes/settings.py:40 - _parse_setting_value()
backend/app/tasks/recommendations.py:67 - _parse_setting_value()
  → Move to shared location, import in both

backend/app/api/routes/inventory.py:98 - parse_plaintext_line_enhanced()
backend/app/api/routes/inventory.py:172 - parse_plaintext_line()
  → Merge into single function with optional db parameter

# Exception handlers to ADD LOGGING (not delete)
backend/app/db/session.py:107-108
backend/app/api/routes/cards.py:951-952, 1087-1088, 1336-1337, 1353-1354, 1369-1370, 1380-1381
backend/app/api/routes/health.py:29-30
backend/app/tasks/data_seeding.py:285-286
```

**NOTE:** Error response builders in `error_handling.py` are USED - do NOT delete.

---

## Appendix: Mobile Breakpoints to Test

| Breakpoint | Device | Priority |
|------------|--------|----------|
| 375px | iPhone SE/Mini | High |
| 390px | iPhone 14 | High |
| 768px | iPad Portrait | Medium |
| 1024px | iPad Landscape | Medium |
| 1280px+ | Desktop | Already works |

**Pages to prioritize:**
1. Navigation (hamburger menu?)
2. Cards list/search
3. Inventory table
4. Card detail
5. Dashboard

---

## Appendix: Security Notes

**Manapool API Token:** Should be stored in:
- `.env` as `MANAPOOL_ACCESS_TOKEN`
- Never committed to git
- Added to `.env.example` as placeholder: `MANAPOOL_ACCESS_TOKEN=your_token_here`

---

## Task Summary

| Week | Tasks | Total Effort |
|------|-------|--------------|
| Week 1 | 5 tasks (Critical fixes + Mobile) | ~8-14 hours |
| Week 2 | 9 tasks (Dead weight removal) | ~3-4 hours |
| Week 3 | 4 tasks (Build features + Revenue) | ~14-23 hours |
| Week 4 | 4 tasks (Polish + Monitoring) | ~11-16 hours |
| **Total** | **22 tasks** | **~36-57 hours** |

At 30+ hours/week, this is achievable in 4 weeks with buffer for unexpected issues.

---
