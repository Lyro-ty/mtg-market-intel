# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dualcaster Deals - MTG market intelligence platform for price tracking, analytics, and trading recommendations.

## Quick Reference

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/api/
- **API Docs**: http://localhost:8000/docs
- **Database**: PostgreSQL on port 5432

## Development Commands

```bash
# Start services
make up                  # Start all (detached)
make up-build            # Build + start
make down                # Stop all
make logs                # All logs
make logs-backend        # Backend only

# Database
make migrate             # Run Alembic migrations
make migrate-new         # Create new migration (prompts for message)
make seed                # Seed database
make import-scryfall     # Import ~30k cards
make import-scryfall-all # Import ~90k cards (all printings)
make db-shell            # psql shell

# Testing
make test                # All tests
make test-backend        # pytest -v
make test-frontend       # npm test

# Quality
make lint                # ruff + eslint
make format              # ruff format
make generate-types      # Generate TypeScript types from OpenAPI

# Manual task triggers
make trigger-scrape
make trigger-analytics
make trigger-recommendations
```

## Architecture

```
Frontend (Next.js 14 + TypeScript + Tailwind)
    ↓ REST API + JWT
Backend (FastAPI + SQLAlchemy)
    ↓
PostgreSQL + Redis (cache/broker)
    ↓
Celery Workers (ingestion, analytics, recommendations, news)
    ↓
Discord Bot (price alerts, slash commands)
```

**Key directories:**
- `backend/app/api/routes/` - REST endpoints (~30 route files)
- `backend/app/schemas/` - Pydantic request/response models
- `backend/app/models/` - SQLAlchemy ORM models
- `backend/app/services/` - Business logic (auth, ingestion, tournaments, pricing, notifications)
- `backend/app/tasks/` - Celery async tasks
- `backend/alembic/versions/` - Database migrations
- `frontend/src/app/` - Next.js App Router pages
- `frontend/src/components/` - React components (ornate theme, charts, inventory)
- `frontend/src/lib/api/` - Modular API client (split by domain)
- `frontend/src/types/index.ts` - TypeScript interfaces (re-exports from generated types)
- `frontend/src/types/api.generated.ts` - Auto-generated from OpenAPI (run `make generate-types`)
- `discord-bot/` - Discord bot with slash commands and price alerts
- `docs/plans/` - Design documents and implementation plans

**Data flow:**
1. Celery workers scrape marketplace APIs (TCGPlayer, CardTrader, Manapool)
2. Prices stored in `price_snapshots` and `buylist_snapshots` tables
3. Analytics task calculates metrics/signals hourly
4. Recommendations generated every 6 hours
5. News collected from RSS feeds and NewsAPI.ai
6. Tournament data synced from TopDeck.gg
7. Frontend fetches via REST API with JWT auth
8. Discord bot sends price alerts via DM

## Database

PostgreSQL with async SQLAlchemy (~40 tables). Key tables:

**Core Data:**
- `users` - JWT auth with bcrypt, Discord/Google OAuth linking
- `cards` - MTG card catalog (Scryfall data, ~98k cards)
- `mtg_sets` - Set metadata
- `price_snapshots` - Time-series price data
- `buylist_snapshots` - Buylist prices for spread analysis

**User Features:**
- `inventory_items` - User collections (scoped by user_id)
- `want_list_items` - Want lists with price alerts
- `portfolio_snapshots` - Daily portfolio value tracking
- `saved_searches` - Saved search filters
- `import_jobs` - Bulk import job tracking

**Analytics:**
- `metrics_cards_daily` - Daily card metrics (~143k rows)
- `signals` - Price/meta/supply signals (~900k rows)
- `recommendations` - Buy/sell/hold signals
- `card_meta_stats` - Meta game analysis
- `market_index_*` - Market index (30min, hourly, daily)
- `legality_changes` - Format legality tracking

**Social:**
- `connection_requests` - Friend connections
- `messages` - User messaging
- `user_endorsements` - Trust endorsements
- `blocked_users` / `user_reports` - Moderation
- `notifications` - In-app notifications

**External Data:**
- `tournaments` / `tournament_standings` / `decklists` - TopDeck.gg data
- `news_articles` / `card_news_mentions` - MTG news
- `discord_alert_queue` - Pending Discord notifications

**ML/Search:**
- `card_feature_vectors` / `listing_feature_vectors` - Embeddings for semantic search

Migrations run automatically on container start.

## Backend Patterns

- **Authentication**: JWT via `app/api/deps.py:get_current_user`
- **Async database**: Use `AsyncSession` from `app/db/session.py`
- **API routes**: FastAPI routers in `app/api/routes/`
- **Celery tasks**: Register in `app/tasks/celery_app.py`
- **Marketplace adapters**: Extend `BaseAdapter` in `app/services/ingestion/`

## Frontend Patterns

- **Auth**: `useAuth()` hook from `AuthContext`
- **API calls**: Use `lib/api.ts` which handles JWT tokens
- **Data fetching**: React Query for server state
- **Styling**: Tailwind CSS classes

## Running Individual Tests

```bash
# Backend - specific test file
docker compose exec backend pytest tests/test_auth.py -v

# Backend - specific test
docker compose exec backend pytest tests/test_auth.py::test_login -v

# Frontend - specific test
docker compose exec frontend npm test -- --testPathPattern="auth"
```

## Environment

Key env vars (see `.env.example` for complete list):

**Core:**
- `SECRET_KEY` - JWT signing (required in production)
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis for cache/broker

**Marketplace APIs:**
- `TCGPLAYER_API_KEY` / `TCGPLAYER_API_SECRET` - TCGPlayer affiliate API
- `CARDTRADER_API_TOKEN` - CardTrader API
- `MANAPOOL_API_TOKEN` - Manapool API
- `TOPDECK_API_KEY` - TopDeck.gg tournament data

**External Services:**
- `NEWSAPI_AI_KEY` - NewsAPI.ai for news aggregation
- `LLM_PROVIDER` - openai/anthropic for AI features
- `SENTRY_DSN` - Error tracking

**OAuth:**
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - Google OAuth
- `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` - Discord OAuth

**Discord Bot:**
- `DISCORD_BOT_TOKEN` - Bot token from Discord Developer Portal
- `DISCORD_BOT_API_KEY` - Internal API key for bot-backend communication
- `DISCORD_GUILD_ID` - Optional, for instant slash command sync

**Scheduling:**
- `SCRAPE_INTERVAL_MINUTES` - Default 30
- `ANALYTICS_INTERVAL_HOURS` - Default 1

## Scheduled Tasks

| Task | Frequency | Purpose |
|------|-----------|---------|
| Inventory scrape | 15 min | Prices for user cards |
| Full scrape | 30 min | All card prices |
| Analytics | 1 hour | Metrics calculation |
| Recommendations | 6 hours | Trading signals |
| News collection | 6 hours | RSS feeds + NewsAPI.ai |
| Tournament sync | 12 hours | TopDeck.gg tournament data |
| Portfolio snapshots | Daily | Track portfolio value history |
| Meta analysis | Daily | Commander meta signals |

## API Routes

Major route groups (see `backend/app/api/routes/`):

| Route | Purpose |
|-------|---------|
| `/auth` | Login, register, JWT refresh |
| `/oauth` | Google/Discord OAuth callbacks |
| `/cards` | Card search, details, price history |
| `/inventory` | CRUD, import/export, analytics |
| `/want-list` | Want list items with price alerts |
| `/recommendations` | Buy/sell/hold signals |
| `/market` | Market overview, top movers, index |
| `/spreads` | Spread analysis dashboard |
| `/news` | News articles, card mentions |
| `/tournaments` | Tournament data, decklists |
| `/profiles` | Public user profiles (hashid URLs) |
| `/connections` | Friend requests, connections |
| `/messages` | User-to-user messaging |
| `/notifications` | In-app notifications |
| `/discovery` | User matching algorithm |
| `/bot` | Discord bot API (price alerts) |

## Frontend Pages

Protected routes (require auth):
- `/dashboard` - Portfolio overview, charts
- `/inventory` - Collection management
- `/want-list` - Want list with alerts
- `/recommendations` - Trading signals
- `/insights` - Analytics dashboard
- `/spreads` - Spread analysis
- `/messages` - User messaging
- `/settings` - Account settings
- `/imports` - Bulk import jobs

Public routes:
- `/` - Landing page
- `/cards` - Card browser
- `/cards/[id]` - Card detail page
- `/market` - Market overview
- `/news` - MTG news feed
- `/tournaments` - Tournament browser
- `/u/[hashid]` - Public user profiles

## Common Gotchas

### Container Changes
Code changes require rebuilding the container, not just restarting:
```bash
docker compose up -d --build backend  # Rebuild backend
docker compose up -d --build frontend # Rebuild frontend
```

### TypeScript Type Generation
Frontend types are auto-generated from the backend's OpenAPI schema:

```bash
# Regenerate types after backend schema changes
make generate-types
```

This generates `frontend/src/types/api.generated.ts` from `http://localhost:8000/openapi.json`.
The `frontend/src/types/index.ts` file re-exports these with friendly aliases.

**After changing backend schemas:**
1. Run `make generate-types`
2. Run `npx tsc --noEmit` in frontend to catch type mismatches
3. Fix any frontend code using the old types

### Card IDs
Card IDs are preserved from Scryfall imports and do NOT start at 1.
When testing, query actual IDs:
```bash
docker compose exec db psql -U dualcaster_user -d dualcaster_deals -c "SELECT id, name FROM cards LIMIT 5;"
```

### API URL Structure
- Backend routes are mounted at `/api/` prefix
- Frontend uses `/api` proxy that rewrites to backend
- Direct backend: `http://localhost:8000/api/cards/123`
- Via frontend proxy: `http://localhost:3000/api/cards/123`

### Database Queries
Always use async patterns:
```python
from sqlalchemy import select
from app.db.session import get_db

async def get_card(db: AsyncSession, card_id: int):
    result = await db.execute(select(Card).where(Card.id == card_id))
    return result.scalar_one_or_none()
```

### MCP Server Setup
The MCP server allows Claude Code to query the database directly. Setup:

1. Copy `.mcp.json.example` to `.mcp.json`
2. Update paths and credentials in `.mcp.json`
3. The database URL format: `postgresql+asyncpg://user:password@localhost:5432/database`

Note: `.mcp.json` is gitignored (contains credentials and user-specific paths).

### Marketplace & External Integrations
| Service | Status | Notes |
|---------|--------|-------|
| Scryfall | ✅ Working | Public API, no key needed |
| TCGPlayer | ✅ Working | Requires API key (affiliate program) |
| CardTrader | ✅ Working | Requires API token |
| Manapool | ✅ Working | Requires API token |
| TopDeck.gg | ✅ Working | Tournament data, requires API key |
| NewsAPI.ai | ✅ Working | News aggregation, free tier available |
| Discord Bot | ✅ Working | Price alerts via DM |
| Google OAuth | ✅ Working | Social login |
| CardMarket | ❌ Blocked | Requires affiliation for API access |

### Discord Bot
The Discord bot runs as a separate container and provides:
- `/price <card>` - Look up current prices
- `/alert <card> <price>` - Set price alerts (via DM)
- `/portfolio` - Quick portfolio summary

**Setup:**
1. Create app at https://discord.com/developers/applications
2. Enable Bot + Message Content Intent
3. Add bot to server with `applications.commands` scope
4. Set `DISCORD_BOT_TOKEN` and `DISCORD_BOT_API_KEY`

**Sync commands:**
```bash
docker compose exec discord-bot python sync_commands.py
```

## Debugging Tips

1. **Check backend logs**: `docker compose logs backend --tail=100`
2. **Test API directly**: `curl http://localhost:8000/api/health`
3. **Database shell**: `make db-shell` then run SQL queries
4. **Frontend console**: Check browser DevTools for API errors

## Git Workflow

The project uses worktrees for feature development:
```bash
# List worktrees
git worktree list

# Worktrees are in .worktrees/ (gitignored)
```

---

## Feature Development Guide

### Recommended Workflow

For any non-trivial feature, use this workflow:

1. **Brainstorm first** → Use `superpowers:brainstorming` skill
2. **Create design doc** → Write to `docs/plans/YYYY-MM-DD-feature-name-design.md`
3. **Create implementation plan** → Use `superpowers:writing-plans` skill
4. **Execute with subagents** → Use `superpowers:subagent-driven-development` for parallel tasks
5. **Verify before completion** → Use `superpowers:verification-before-completion` skill

### Design Doc Format

```markdown
# Feature Name Design

**Date:** YYYY-MM-DD
**Status:** Draft | Approved | Implemented
**Author:** Claude + User

## Overview
Brief description of what we're building and why.

### Design Decisions
| Decision | Choice | Rationale |
|----------|--------|-----------|

## Database Models
SQLAlchemy model definitions with relationships.

## API Endpoints
FastAPI route specifications with request/response schemas.

## Frontend Components
React component hierarchy and data flow.

## Implementation Tasks
Numbered list of discrete tasks.
```

### Skills to Use

| Situation | Skill |
|-----------|-------|
| New feature request | `superpowers:brainstorming` |
| Planning implementation | `superpowers:writing-plans` |
| Multi-file changes | `superpowers:subagent-driven-development` |
| Bug investigation | `superpowers:systematic-debugging` |
| Before claiming "done" | `superpowers:verification-before-completion` |
| Writing tests first | `superpowers:test-driven-development` |
| Ready to merge | `superpowers:finishing-a-development-branch` |

### Component Patterns

**Backend API Route:**
```python
# backend/app/api/routes/feature.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.deps import get_current_user
from app.schemas.feature import FeatureResponse

router = APIRouter()

@router.get("/{id}", response_model=FeatureResponse)
async def get_feature(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # if auth required
):
    ...
```

**Backend Schema:**
```python
# backend/app/schemas/feature.py
from pydantic import BaseModel

class FeatureResponse(BaseModel):
    id: int  # Use 'id' not 'feature_id' for frontend compatibility
    name: str

    class Config:
        from_attributes = True
```

**Frontend Type (must match schema!):**
```typescript
// frontend/src/types/index.ts
export interface Feature {
  id: number;  // Match backend schema field names exactly
  name: string;
}
```

**Frontend API Function:**
```typescript
// frontend/src/lib/api.ts
export async function getFeature(id: number): Promise<Feature> {
  return fetchApi(`/feature/${id}`);
}
```

**Frontend Component:**
```tsx
// frontend/src/app/(protected)/feature/page.tsx
'use client';
import { useQuery } from '@tanstack/react-query';
import { getFeature } from '@/lib/api';

export default function FeaturePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['feature', id],
    queryFn: () => getFeature(id),
  });
  ...
}
```

### Testing Expectations

- Backend routes should have tests in `backend/tests/`
- Use pytest fixtures from `backend/tests/conftest.py`
- Run tests before committing: `make test-backend`

### Parallel Subagent Tasks

When implementing features with independent parts, dispatch subagents:

```
Always write individual implementation documents for each feature as we go
Good candidates for parallel execution:
- Backend API + Frontend page (after schema is defined)
- Multiple independent API endpoints
- Database migration + seed data
- Tests for different modules

NOT parallel (sequential dependencies):
- Schema → API route → Frontend type → Frontend component
- Migration → Model update → API changes
```

---

## Design Documents

See `docs/plans/` for 38+ design and implementation documents. Key ones:

**Architecture:**
- `2025-12-24-charting-architecture-overhaul-design.md` - TimescaleDB, Redis caching, WebSockets
- `2025-12-27-inventory-pricing-search-design.md` - Layered pricing, semantic search
- `2025-12-29-mcp-server-design.md` - MCP server for Claude Code integration

**Features:**
- `2025-12-28-collection-wantlist-insights-api-design.md` - Collection and want list APIs
- `2025-12-28-phase2-visual-overhaul-design.md` - MTG-themed visual identity
- `2025-12-30-discord-bot-design.md` - Discord bot with price alerts

**Implementation:**
- Most `-design.md` files have corresponding `-plan.md` files with task breakdowns
- Plans use numbered tasks suitable for `superpowers:subagent-driven-development`

---

## Known Issues & TODOs

- Frontend components should handle null/undefined from API gracefully
- Always check for null before calling `.toFixed()` or similar methods
- Discord bot uses v2 API with POST for tournament endpoints
- TopDeck.gg uses `last` parameter (days) not `start` date string
