# Architecture Overhaul Implementation Summary

**Date:** 2025-12-25
**Author:** Claude (AI Assistant)
**Status:** In Progress (Alignment Review Completed)

## Overview

This document summarizes all changes made during the comprehensive architecture overhaul of the MTG Market Intel application. The overhaul focused on:

1. Migrating to TimescaleDB for time-series price data
2. Implementing a Redis caching layer
3. Adding WebSocket real-time updates
4. Refactoring to Clean Architecture with repositories
5. Integrating 8 components that were previously left out of the design

---

## Phase 1: Infrastructure Setup

### 1.1 Docker Compose Updates (`docker-compose.yml`)

**Changed:** PostgreSQL image from `postgres:16-alpine` to `timescale/timescaledb:latest-pg16`

**Added:** TimescaleDB-optimized PostgreSQL settings:
```yaml
db:
  image: timescale/timescaledb:latest-pg16
  command:
    - "postgres"
    - "-c"
    - "shared_preload_libraries=timescaledb"
    - "-c"
    - "timescaledb.telemetry_level=off"
    - "-c"
    - "max_connections=200"
    - "-c"
    - "shared_buffers=256MB"
    - "-c"
    - "work_mem=64MB"
    - "-c"
    - "maintenance_work_mem=128MB"
    - "-c"
    - "effective_cache_size=1GB"
    - "-c"
    - "random_page_cost=1.1"
```

**Added:** Redis persistence and memory management settings.

### 1.2 Constants Module (`backend/app/core/constants.py`) - NEW FILE

Created centralized enums and normalization functions:

- `CardCondition` enum: MINT, NEAR_MINT, LIGHTLY_PLAYED, MODERATELY_PLAYED, HEAVILY_PLAYED, DAMAGED
- `CardLanguage` enum: ENGLISH, JAPANESE, GERMAN, FRENCH, ITALIAN, SPANISH, PORTUGUESE, KOREAN, RUSSIAN, CHINESE_SIMPLIFIED, CHINESE_TRADITIONAL
- `CONDITION_ALIASES`: Maps marketplace-specific condition strings to standard enum values
- `LANGUAGE_ALIASES`: Maps language strings to standard enum values
- `normalize_condition()`: Function to normalize any condition string
- `normalize_language()`: Function to normalize any language string
- `PERIOD_INTERVALS`: TimescaleDB interval mappings for 24h, 7d, 30d, 90d, 1y
- `get_currency_for_marketplace()`: Returns default currency for each marketplace

### 1.3 Database Migrations

#### Migration 1: Enable TimescaleDB (`20241225_000001_011_enable_timescaledb.py`)
- Enables TimescaleDB extension
- Creates `card_condition` PostgreSQL ENUM type
- Creates `card_language` PostgreSQL ENUM type

#### Migration 2: Price Snapshots Hypertable (`20241225_000002_012_price_snapshots_hypertable.py`)
- Transforms `price_snapshots` table to TimescaleDB hypertable with 7-day chunks
- Adds new columns: `condition`, `is_foil`, `language`
- Changes to composite primary key: `(time, card_id, marketplace_id, condition, is_foil, language)`
- Removes the `id` column (hypertables use composite keys)
- Creates optimized indexes
- Sets up compression policy (compress chunks older than 7 days)
- Sets up retention policy (drop data older than 2 years)

#### Migration 3: Continuous Aggregates (`20241225_000003_013_continuous_aggregates.py`)
Creates four continuous aggregates for pre-computed analytics:

1. **market_index_30min**: 30-minute market index buckets
2. **market_index_hourly**: 1-hour market index buckets
3. **market_index_daily**: 1-day market index buckets
4. **card_prices_hourly**: Per-card hourly price aggregates

Each aggregate includes:
- `time_bucket` for the period
- `avg_price`, `min_price`, `max_price`
- `total_volume` (sum of quantities)
- `unique_cards` (count of distinct cards)
- `total_snapshots` (count of data points)
- Automatic refresh policies

---

## Phase 2: Data Layer - Repositories

### 2.1 Repository Pattern (`backend/app/repositories/`)

Created a complete repository layer for data access abstraction:

#### Base Repository (`base.py`)
Generic `BaseRepository[ModelType]` with standard CRUD operations:
- `get_by_id()`, `get_all()`, `find_one_by()`, `find_by()`
- `count()`, `exists()`
- `create()`, `update()`, `delete()`
- `bulk_create()`, `bulk_delete()`

#### Price Repository (`price_repo.py`)
TimescaleDB-specific operations for price data:
- `insert_snapshot()`: Insert single price snapshot
- `insert_batch()`: Bulk insert with conflict handling
- `get_card_history()`: Query time-series data with bucketing
- `get_latest_price()`: Get most recent price for a card
- `get_price_change()`: Calculate price change over period

#### Cache Repository (`cache_repo.py`)
Redis caching layer with get-or-compute pattern:
- `get()`, `set()`, `delete()`
- `get_or_compute()`: Cache-aside pattern with TTL
- `invalidate_pattern()`: Pattern-based cache invalidation
- `invalidate_card()`, `invalidate_market()`: Domain-specific invalidation

#### Market Repository (`market_repo.py`)
Aggregate market data from continuous aggregates:
- `get_market_index()`: Fetch market index with real-time data union
- `get_market_overview()`: Market summary statistics
- `get_top_movers()`: Gainers and losers
- `get_spread_opportunities()`: Arbitrage opportunities

#### Signal Repository (`signal_repo.py`)
SQL-based signal detection using TimescaleDB functions:
- `get_momentum_signals()`: Price momentum detection
- `get_volatility_signals()`: Volatility spike detection
- `get_trend_signals()`: Trend reversal detection
Uses TimescaleDB `FIRST()`, `LAST()`, `STDDEV()` functions

#### Card Repository (`card_repo.py`)
Extended `BaseRepository[Card]`:
- `search()`: Full-text card search
- `get_by_scryfall_id()`: Lookup by Scryfall ID
- `get_by_name()`: Lookup by name and set
- `get_sets()`: List all sets
- `upsert()`: Insert or update card data

#### Inventory Repository (`inventory_repo.py`)
User collection management:
- `get_user_inventory()`: Paginated user inventory
- `add_item()`, `remove_item()`: Collection modifications
- `get_portfolio_value()`: Total portfolio valuation
- `get_purchase_stats()`: Acquisition statistics

#### Recommendation Repository (`recommendation_repo.py`)
Trading recommendations:
- `create_recommendation()`: Create new recommendation
- `get_active()`: Fetch active recommendations
- `count_active()`: Count by action type
- `bulk_insert()`: Batch insert recommendations

#### Settings Repository (`settings_repo.py`)
User preferences with Redis caching:
- `get()`, `set()`, `delete()`: Key-value operations
- `get_all()`: All user settings
- Convenience methods: `get_preferred_currency()`, `get_enabled_marketplaces()`, etc.

### 2.2 Model Updates

#### PriceSnapshot Model (`models/price_snapshot.py`)
- Changed to composite primary key: `(time, card_id, marketplace_id, condition, is_foil, language)`
- Removed `id` column
- Added `condition` column (PostgreSQL ENUM)
- Added `is_foil` column (Boolean)
- Added `language` column (PostgreSQL ENUM)

#### Models __init__ (`models/__init__.py`)
- Removed `Listing` import (model deprecated)
- Removed `ListingFeatureVector` import (class removed)

#### FeatureVector Model (`models/feature_vector.py`)
- Removed `ListingFeatureVector` class entirely
- Updated docstring to reflect removal

---

## Phase 3: Ingestion Pipeline

### 3.1 Ingestion Base Updates (`services/ingestion/base.py`)

#### New PriceData Dataclass
Standardized format for database insertion:
```python
@dataclass
class PriceData:
    card_id: int
    marketplace_id: int
    price: float
    currency: str
    time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    condition: CardCondition = CardCondition.NEAR_MINT
    is_foil: bool = False
    language: CardLanguage = CardLanguage.ENGLISH
    price_low: float | None = None
    price_mid: float | None = None
    price_high: float | None = None
    price_market: float | None = None
    num_listings: int | None = None
    total_quantity: int | None = None
```

#### MarketplaceAdapter Updates
- Updated `normalize_condition()` to use centralized constants
- Updated `normalize_language()` to use centralized constants
- Added `get_default_currency()` method
- Added `to_price_data()` helper for converting CardPrice to PriceData

### 3.2 Ingestion __init__ Updates (`services/ingestion/__init__.py`)
- Added `PriceData` to exports

---

## Phase 4: Use Cases & Routes

*Note: The design document outlines use cases, but the primary implementation focused on the repository layer which provides the foundation for use cases.*

---

## Phase 5: WebSocket Layer

### 5.1 WebSocket Route (`backend/app/api/routes/websocket.py`) - NEW FILE

Complete WebSocket implementation with:

#### ConnectionManager Class
- Connection tracking per channel
- Redis Pub/Sub integration for cross-worker messaging
- Automatic cleanup on disconnect
- JWT authentication for protected channels

**Methods:**
- `connect()`: Accept new WebSocket connection
- `disconnect()`: Handle disconnection and cleanup
- `subscribe()`: Subscribe to a channel
- `unsubscribe()`: Unsubscribe from a channel
- `broadcast()`: Send message to all channel subscribers
- `start_redis_listener()`: Start Redis Pub/Sub listener
- `stop_redis_listener()`: Stop Redis listener

#### Available Channels
- `channel:market:{currency}` - Market index updates
- `channel:card:{card_id}` - Individual card price updates
- `channel:dashboard:{currency}` - Dashboard notifications
- `channel:inventory:user:{user_id}` - Inventory updates (auth required)
- `channel:recommendations` - New recommendation alerts

#### Helper Functions for Publishing
- `publish_market_update()`: Publish market data to Redis
- `publish_card_update()`: Publish card price updates
- `publish_dashboard_update()`: Publish dashboard section updates
- `publish_recommendation_update()`: Publish new recommendations
- `publish_inventory_update()`: Publish inventory changes

### 5.2 API Router Update (`api/__init__.py`)
- Added `websocket` router import
- Registered WebSocket router with API

---

## Phase 6: Frontend

### 6.1 WebSocket Types (`frontend/src/types/index.ts`)

Added WebSocket-related types:
- `WebSocketChannelType`: Union of channel type strings
- `WebSocketMessage`: Base message interface
- `WebSocketSubscription`: Subscription configuration
- `MarketUpdateMessage`: Market index update message
- `CardUpdateMessage`: Card price update message
- `DashboardUpdateMessage`: Dashboard section update message
- `InventoryUpdateMessage`: Inventory change message
- `RecommendationsUpdateMessage`: Recommendation update message

### 6.2 WebSocket Context (`frontend/src/contexts/WebSocketContext.tsx`) - NEW FILE

React context for WebSocket management:

**Features:**
- Automatic connection with JWT token
- Reconnection logic with exponential backoff
- Channel subscription management
- Ping/pong keepalive
- Last message caching per channel

**Exports:**
- `WebSocketProvider`: Context provider component
- `useWebSocketContext()`: Hook to access context

### 6.3 WebSocket Hooks (`frontend/src/hooks/useWebSocket.ts`) - NEW FILE

Custom hooks for WebSocket subscriptions:

- `useWebSocket<T>()`: Generic channel subscription hook
- `useMarketUpdates()`: Subscribe to market index updates
- `useCardUpdates()`: Subscribe to card price updates
- `useDashboardUpdates()`: Subscribe to dashboard updates
- `useInventoryUpdates()`: Subscribe to inventory updates (auth)
- `useRecommendationUpdates()`: Subscribe to recommendations
- `useWebSocketStatus()`: Get connection status

### 6.4 Currency Hook (`frontend/src/hooks/useCurrency.ts`) - NEW FILE

Currency preference management:
- Persists to localStorage
- Provides formatting utilities
- Supports USD and EUR

**Returns:**
- `currency`: Current currency
- `setCurrency()`: Update preference
- `formatPrice()`: Format amount in currency
- `formatChange()`: Format percentage change
- `getSymbol()`: Get currency symbol

### 6.5 Hooks Index (`frontend/src/hooks/index.ts`) - NEW FILE

Exports all custom hooks from a single entry point.

### 6.6 Providers Update (`frontend/src/app/providers.tsx`)

- Added `WebSocketProvider` import
- Wrapped children with `WebSocketProvider` inside `AuthProvider`

---

## Files Created

| File | Description |
|------|-------------|
| `backend/app/core/constants.py` | Centralized enums and normalization |
| `backend/alembic/versions/20241225_000001_011_enable_timescaledb.py` | Enable TimescaleDB migration |
| `backend/alembic/versions/20241225_000002_012_price_snapshots_hypertable.py` | Hypertable migration |
| `backend/alembic/versions/20241225_000003_013_continuous_aggregates.py` | Continuous aggregates migration |
| `backend/app/repositories/__init__.py` | Repository exports |
| `backend/app/repositories/base.py` | Generic base repository |
| `backend/app/repositories/price_repo.py` | Price data repository |
| `backend/app/repositories/cache_repo.py` | Redis cache repository |
| `backend/app/repositories/market_repo.py` | Market data repository |
| `backend/app/repositories/card_repo.py` | Card repository |
| `backend/app/repositories/signal_repo.py` | Signal detection repository |
| `backend/app/repositories/inventory_repo.py` | Inventory repository |
| `backend/app/repositories/recommendation_repo.py` | Recommendation repository |
| `backend/app/repositories/settings_repo.py` | Settings repository |
| `backend/app/api/routes/websocket.py` | WebSocket endpoint |
| `frontend/src/contexts/WebSocketContext.tsx` | WebSocket React context |
| `frontend/src/hooks/useWebSocket.ts` | WebSocket hooks |
| `frontend/src/hooks/useCurrency.ts` | Currency management hook |
| `frontend/src/hooks/index.ts` | Hooks export index |

## Files Modified

| File | Changes |
|------|---------|
| `docker-compose.yml` | TimescaleDB image and settings |
| `backend/app/models/price_snapshot.py` | Composite PK, new columns |
| `backend/app/models/__init__.py` | Removed deprecated imports |
| `backend/app/models/feature_vector.py` | Removed ListingFeatureVector |
| `backend/app/services/ingestion/base.py` | Added PriceData, updated normalization |
| `backend/app/services/ingestion/__init__.py` | Export PriceData |
| `backend/app/api/__init__.py` | Added websocket router |
| `frontend/src/types/index.ts` | Added WebSocket types |
| `frontend/src/app/providers.tsx` | Added WebSocketProvider |

---

## Next Steps

To complete the overhaul, the following work remains:

1. **Update Celery Tasks**: Modify ingestion tasks to use `PriceRepository` instead of direct ORM operations
2. **Update API Routes**: Refactor routes to use repository pattern via use cases
3. **Run Migrations**: Execute the three new Alembic migrations
4. **Integration Testing**: Test WebSocket connections and real-time updates
5. **Performance Testing**: Validate TimescaleDB query performance
6. **Documentation**: Update API documentation for WebSocket endpoints

---

## Architecture Diagram

```
                                    Frontend (Next.js)
                                         |
                        +----------------+----------------+
                        |                                 |
                   REST API                          WebSocket
                        |                                 |
                        v                                 v
                   FastAPI Routes               ConnectionManager
                        |                                 |
                        v                                 v
                    Use Cases <------------------- Redis Pub/Sub
                        |                                 ^
                        v                                 |
                   Repositories                    Celery Workers
                        |                                 |
            +-----------+-----------+                     |
            |           |           |                     |
            v           v           v                     |
      TimescaleDB    Redis      External ----------------+
      (prices)      (cache)      APIs
```

---

## Verification

All created Python files pass syntax validation:
```
app/core/constants.py: OK
app/repositories/*.py: OK
app/api/routes/websocket.py: OK
alembic/versions/20241225*.py: OK
```

---

## Alignment Review & Fixes (Post-Implementation)

An alignment review was conducted to ensure all components work correctly together. The following issues were identified and fixed:

### Issues Found & Fixed

#### 1. PriceSnapshot Model Inheritance Conflict
**Problem:** `PriceSnapshot` inherited from `Base` which defines `id`, `created_at`, `updated_at` columns. This conflicted with the hypertable's composite primary key design.

**Fix:** Created `HypertableBase` class in `models/price_snapshot.py` that doesn't include default columns. `PriceSnapshot` now inherits from `HypertableBase` instead of `Base`.

#### 2. Card Model Still Referenced Listing
**Problem:** `Card` model still had `from app.models.listing import Listing` and a `listings` relationship.

**Fix:** Removed `Listing` import and `listings` relationship from `models/card.py`.

#### 3. Constants Not Exported from core/__init__.py
**Problem:** The constants module was created but not exported from the core package.

**Fix:** Added exports for `CardCondition`, `CardLanguage`, `normalize_condition`, `normalize_language`, `PERIOD_INTERVALS`, `get_currency_for_marketplace` to `core/__init__.py`.

#### 4. Ingestion Tasks Used Old Schema Columns
**Problem:** `tasks/ingestion.py` referenced old column names (`snapshot_time`, `price_foil`, `min_price`, `max_price`) and imported `Listing`.

**Fix:**
- Removed `Listing` import
- Added `CardCondition`, `CardLanguage` imports
- Updated `_upsert_price_snapshot()` to use new schema:
  - `snapshot_time` → `time`
  - `price_foil` → `price_market` (legacy mapping)
  - `min_price` → `price_low`
  - `max_price` → `price_high`
  - Added `condition`, `is_foil`, `language` parameters
- Updated `_backfill_historical_snapshots_for_charting()` with new schema
- Updated all `_upsert_price_snapshot()` calls throughout the file

#### 5. Multiple Files Referenced Old Schema Columns
**Problem:** 11 files still referenced `PriceSnapshot.snapshot_time` instead of `PriceSnapshot.time`.

**Files Updated:**
- `app/api/routes/cards.py`
- `app/api/routes/dashboard.py`
- `app/api/routes/inventory.py`
- `app/api/routes/market.py`
- `app/core/data_freshness.py`
- `app/services/agents/analytics.py`
- `app/tasks/data_seeding.py`
- `app/scripts/diagnose_chart_data.py`
- `app/scripts/export_training_data.py`
- `app/scripts/generate_demo_price_history.py`
- `app/scripts/seed_mtgjson_historical.py`

**Fix:** Used sed to replace `PriceSnapshot.snapshot_time` with `PriceSnapshot.time` and `PriceSnapshot.price_foil` with `PriceSnapshot.price_market`.

### Remaining Work

The following files still require manual review and updates:

1. **`app/tasks/data_seeding.py`** - Contains direct `PriceSnapshot()` creations that need to include new required columns (`condition`, `is_foil`, `language`)

2. **`app/scripts/export_training_data.py`** - References `snapshot.snapshot_time` and `snapshot.price_foil` as attribute access (not column references) - needs ORM-level updates

3. **`app/scripts/generate_demo_price_history.py`** - May contain direct PriceSnapshot creations

4. **`app/scripts/seed_mtgjson_historical.py`** - May contain old schema references

### Schema Change Summary

| Old Column | New Column | Notes |
|------------|------------|-------|
| `snapshot_time` | `time` | Hypertable partition key |
| `price_foil` | `price_market` | Legacy mapping; foil variants now tracked via `is_foil=True` |
| `min_price` | `price_low` | Renamed for consistency |
| `max_price` | `price_high` | Renamed for consistency |
| (new) | `condition` | Card condition enum (NEAR_MINT, etc.) |
| (new) | `is_foil` | Boolean flag for foil variants |
| (new) | `language` | Card language enum (ENGLISH, etc.) |

### Important: Foil Price Handling Change

**Old behavior:** `price_foil` was a separate column storing the foil price alongside the regular price.

**New behavior:** Foil variants are stored as separate rows with `is_foil=True`. Each (card_id, marketplace_id, time, condition, is_foil, language) combination is a unique record.

This means queries that previously checked `price_foil` should now:
1. Query for `is_foil=True` to get foil prices
2. Query for `is_foil=False` to get non-foil prices

### Post-Migration Testing Checklist

- [ ] Run migrations: `make migrate`
- [ ] Verify hypertable creation: Check `SELECT * FROM timescaledb_information.hypertables`
- [ ] Test price ingestion: Run `make trigger-scrape` and verify data
- [ ] Test WebSocket: Connect to `/api/ws` and subscribe to channels
- [ ] Test API routes: Verify `/api/market/index`, `/api/cards/{id}/prices` work
- [ ] Run tests: `make test-backend`

---

*This implementation follows the design outlined in `2025-12-24-charting-architecture-overhaul-design.md` and prepares the codebase for the remaining integration work.*
