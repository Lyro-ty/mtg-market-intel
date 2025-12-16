# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dualcaster Deals - MTG market intelligence platform for price tracking, analytics, and trading recommendations.

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
- `backend/app/models/` - SQLAlchemy ORM models
- `backend/app/services/` - Business logic (auth, ingestion, agents, llm)
- `backend/app/tasks/` - Celery async tasks
- `backend/alembic/versions/` - Database migrations
- `frontend/src/app/` - Next.js App Router pages
- `frontend/src/components/` - React components
- `frontend/src/contexts/AuthContext.tsx` - Auth state management

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
