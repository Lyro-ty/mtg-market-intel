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
Celery Workers (ingestion, analytics, recommendations)
```

**Key directories:**
- `backend/app/api/routes/` - REST endpoints
- `backend/app/schemas/` - Pydantic request/response models
- `backend/app/models/` - SQLAlchemy ORM models
- `backend/app/services/` - Business logic (auth, ingestion, agents, llm)
- `backend/app/tasks/` - Celery async tasks
- `backend/alembic/versions/` - Database migrations
- `frontend/src/app/` - Next.js App Router pages
- `frontend/src/components/` - React components
- `frontend/src/lib/api.ts` - API client functions
- `frontend/src/types/index.ts` - TypeScript interfaces (re-exports from generated types)
- `frontend/src/types/api.generated.ts` - Auto-generated from OpenAPI (run `make generate-types`)
- `docs/plans/` - Design documents and implementation plans

**Data flow:**
1. Celery workers scrape marketplace APIs (TCGPlayer, CardTrader, Manapool)
2. Prices stored in `price_snapshots` table
3. Analytics task calculates metrics/signals hourly
4. Recommendations generated every 6 hours
5. Frontend fetches via REST API with JWT auth

## Database

PostgreSQL with async SQLAlchemy. Key tables:
- `users` - JWT auth with bcrypt
- `cards` - MTG card catalog (Scryfall data)
- `price_snapshots` - Time-series price data
- `inventory_items` - User collections (scoped by user_id)
- `metrics` / `signals` - Analytics data
- `recommendations` - Buy/sell/hold signals

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

Key env vars (see `.env.example`):
- `SECRET_KEY` - JWT signing (required in production)
- `LLM_PROVIDER` - openai/anthropic/mock
- `SCRAPE_INTERVAL_MINUTES` - Default 30
- `ANALYTICS_INTERVAL_HOURS` - Default 1

## Scheduled Tasks

| Task | Frequency | Purpose |
|------|-----------|---------|
| Inventory scrape | 15 min | Prices for user cards |
| Full scrape | 30 min | All card prices |
| Analytics | 1 hour | Metrics calculation |
| Recommendations | 6 hours | Trading signals |

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
Good candidates for parallel execution:
- Backend API + Frontend page (after schema is defined)
- Multiple independent API endpoints
- Database migration + seed data
- Tests for different modules

NOT parallel (sequential dependencies):
- Schema → API route → Frontend type → Frontend component
- Migration → Model update → API changes
```
