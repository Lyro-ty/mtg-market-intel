# Charting Architecture Overhaul Design

**Date:** 2024-12-24
**Status:** Approved
**Scope:** Full overhaul including TimescaleDB, Redis caching, WebSocket real-time, Clean Architecture refactor, and frontend optimizations

---

## Table of Contents

1. [Overview](#overview)
2. [High-Level Architecture](#high-level-architecture)
3. [TimescaleDB Schema](#timescaledb-schema)
4. [Redis Caching Layer](#redis-caching-layer)
5. [WebSocket Real-Time Layer](#websocket-real-time-layer)
6. [Clean Architecture Refactor](#clean-architecture-refactor)
7. [Frontend Optimizations](#frontend-optimizations)
8. [Implementation Order](#implementation-order)

---

## Overview

### Goals

- Replace PostgreSQL time-series queries with TimescaleDB hypertables and continuous aggregates
- Implement Redis caching to replace process-local in-memory cache
- Add WebSocket support for full real-time dashboard updates
- Refactor backend to Clean Architecture (routes → use cases → repositories)
- Optimize frontend with memoization and WebSocket integration
- Track card prices by condition, language, and foil status
- Remove all mock data from the codebase

### Non-Goals

- GraphQL migration (future consideration)
- Mobile app support
- Multi-region deployment

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Next.js)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────┐ │
│  │  Charts     │  │  Dashboard  │  │  WebSocket Manager              │ │
│  │  (useMemo)  │  │  Components │  │  - Reconnect logic              │ │
│  └──────┬──────┘  └──────┬──────┘  │  - State sync                   │ │
│         │                │         └────────────────┬────────────────┘ │
└─────────┼────────────────┼──────────────────────────┼──────────────────┘
          │ REST           │ REST                     │ WebSocket
          ▼                ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           BACKEND (FastAPI)                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        API Layer (routes/)                       │   │
│  │  cards.py │ market.py │ inventory.py │ websocket.py (~50-100 LOC)│   │
│  └─────────────────────────────┬───────────────────────────────────┘   │
│  ┌─────────────────────────────┼───────────────────────────────────┐   │
│  │                     Use Cases (use_cases/)                       │   │
│  │  get_card_history │ get_market_index │ refresh_card_data         │   │
│  └─────────────────────────────┬───────────────────────────────────┘   │
│  ┌─────────────────────────────┼───────────────────────────────────┐   │
│  │                   Repositories (repositories/)                   │   │
│  │  price_repo │ card_repo │ market_repo │ cache_repo (Redis)       │   │
│  └─────────────────────────────┬───────────────────────────────────┘   │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│  TimescaleDB     │  │      Redis       │  │    WebSocket Broker      │
│  - hypertables   │  │  - Query cache   │  │    (Redis Pub/Sub)       │
│  - continuous    │  │  - Session store │  │  - Price updates channel │
│    aggregates    │  │  - Rate limiting │  │  - Market updates channel│
└──────────────────┘  └──────────────────┘  └──────────────────────────┘
```

---

## TimescaleDB Schema

### Enums

```sql
CREATE TYPE card_condition AS ENUM (
    'MINT',
    'NEAR_MINT',
    'LIGHTLY_PLAYED',
    'MODERATELY_PLAYED',
    'HEAVILY_PLAYED',
    'DAMAGED'
);

CREATE TYPE card_language AS ENUM (
    'English',
    'Japanese',
    'German',
    'French',
    'Italian',
    'Spanish',
    'Portuguese',
    'Korean',
    'Chinese Simplified',
    'Chinese Traditional',
    'Russian',
    'Phyrexian'
);
```

### Main Hypertable

```sql
CREATE TABLE price_snapshots (
    time           TIMESTAMPTZ NOT NULL,
    card_id        INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    marketplace_id INTEGER NOT NULL REFERENCES marketplaces(id) ON DELETE CASCADE,

    -- Card variant identifiers
    condition      card_condition NOT NULL DEFAULT 'NEAR_MINT',
    is_foil        BOOLEAN NOT NULL DEFAULT FALSE,
    language       card_language NOT NULL DEFAULT 'English',

    -- Price tiers
    price          NUMERIC(10,2) NOT NULL,
    price_low      NUMERIC(10,2),
    price_mid      NUMERIC(10,2),
    price_high     NUMERIC(10,2),
    price_market   NUMERIC(10,2),
    currency       VARCHAR(3) NOT NULL DEFAULT 'USD',

    -- Volume indicators
    num_listings   INTEGER,
    total_quantity INTEGER,

    UNIQUE (time, card_id, marketplace_id, condition, is_foil, language)
);

SELECT create_hypertable('price_snapshots', 'time', chunk_time_interval => INTERVAL '7 days');
```

### Indexes

```sql
CREATE INDEX ix_snapshots_card_time ON price_snapshots (card_id, time DESC);
CREATE INDEX ix_snapshots_card_condition ON price_snapshots (card_id, condition, time DESC);
CREATE INDEX ix_snapshots_card_language ON price_snapshots (card_id, language, time DESC);
CREATE INDEX ix_snapshots_card_foil ON price_snapshots (card_id, is_foil, time DESC);
CREATE INDEX ix_snapshots_currency_time ON price_snapshots (currency, time DESC);
CREATE INDEX ix_snapshots_marketplace_time ON price_snapshots (marketplace_id, time DESC);
```

### Continuous Aggregates

```sql
-- 30-minute buckets for 7d charts
CREATE MATERIALIZED VIEW market_index_30min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('30 minutes', time) AS bucket,
    currency,
    condition,
    is_foil,
    language,
    AVG(price) AS avg_price,
    AVG(price_market) AS avg_market_price,
    MIN(price_low) AS min_price,
    MAX(price_high) AS max_price,
    COUNT(DISTINCT card_id) AS card_count,
    SUM(num_listings) AS total_listings,
    SUM(total_quantity) AS total_quantity,
    SUM(price * COALESCE(total_quantity, num_listings, 1)) AS volume
FROM price_snapshots
WHERE price > 0
GROUP BY bucket, currency, condition, is_foil, language;

SELECT add_continuous_aggregate_policy('market_index_30min',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '30 minutes',
    schedule_interval => INTERVAL '30 minutes'
);

-- Hourly buckets for 30d/90d charts
CREATE MATERIALIZED VIEW market_index_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    currency,
    condition,
    is_foil,
    language,
    AVG(price) AS avg_price,
    AVG(price_market) AS avg_market_price,
    MIN(price_low) AS min_price,
    MAX(price_high) AS max_price,
    COUNT(DISTINCT card_id) AS card_count,
    SUM(num_listings) AS total_listings,
    SUM(total_quantity) AS total_quantity,
    SUM(price * COALESCE(total_quantity, num_listings, 1)) AS volume
FROM price_snapshots
WHERE price > 0
GROUP BY bucket, currency, condition, is_foil, language;

SELECT add_continuous_aggregate_policy('market_index_hourly',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour'
);

-- Daily buckets for 1y charts
CREATE MATERIALIZED VIEW market_index_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    currency,
    condition,
    is_foil,
    language,
    AVG(price) AS avg_price,
    AVG(price_market) AS avg_market_price,
    MIN(price_low) AS min_price,
    MAX(price_high) AS max_price,
    COUNT(DISTINCT card_id) AS card_count,
    SUM(num_listings) AS total_listings,
    SUM(total_quantity) AS total_quantity,
    SUM(price * COALESCE(total_quantity, num_listings, 1)) AS volume
FROM price_snapshots
WHERE price > 0
GROUP BY bucket, currency, condition, is_foil, language;

SELECT add_continuous_aggregate_policy('market_index_daily',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day'
);

-- Per-card aggregates
CREATE MATERIALIZED VIEW card_prices_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    card_id,
    marketplace_id,
    condition,
    is_foil,
    language,
    currency,
    AVG(price) AS avg_price,
    AVG(price_market) AS avg_market_price,
    MIN(price_low) AS min_price,
    MAX(price_high) AS max_price,
    SUM(num_listings) AS total_listings,
    SUM(total_quantity) AS total_quantity
FROM price_snapshots
WHERE price > 0
GROUP BY bucket, card_id, marketplace_id, condition, is_foil, language, currency;

SELECT add_continuous_aggregate_policy('card_prices_hourly',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour'
);
```

### Storage Optimization

```sql
SELECT add_compression_policy('price_snapshots', INTERVAL '7 days');
SELECT add_retention_policy('price_snapshots', INTERVAL '2 years');
```

---

## Redis Caching Layer

### Key Structure

```
QUERY CACHE (5-minute TTL)
├── cache:market:overview                    → JSON (dashboard stats)
├── cache:market:index:7d:USD:NEAR_MINT      → JSON (chart points)
├── cache:market:index:30d:USD:all           → JSON (chart points)
├── cache:card:123:history:30d:NM:en         → JSON (price history)
└── cache:card:123:detail                    → JSON (card + prices)

REAL-TIME PRICE STREAM (Pub/Sub)
├── channel:prices:card:123                  → Live price updates
├── channel:prices:market                    → Market-wide updates
└── channel:alerts:user:456                  → User price alerts

RATE LIMITING (sliding window)
├── ratelimit:ip:192.168.1.1:history         → Counter + TTL
└── ratelimit:user:456:refresh               → Counter + TTL
```

### Cache Repository

```python
class CacheRepository:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.default_ttl = timedelta(minutes=5)

    def _key(self, *parts: str) -> str:
        return "cache:" + ":".join(parts)

    async def get(self, *key_parts: str) -> Any | None:
        key = self._key(*key_parts)
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def set(self, *key_parts: str, value: Any, ttl: timedelta | None = None) -> None:
        key = self._key(*key_parts)
        await self.redis.setex(key, ttl or self.default_ttl, json.dumps(value, default=str))

    async def get_or_compute(
        self,
        key_parts: tuple[str, ...],
        compute_fn: Callable[[], Any],
        ttl: timedelta | None = None,
    ) -> Any:
        cached = await self.get(*key_parts)
        if cached is not None:
            return cached
        result = await compute_fn()
        await self.set(*key_parts, value=result, ttl=ttl)
        return result
```

---

## WebSocket Real-Time Layer

### Architecture

```
CELERY WORKER                        BACKEND (FastAPI)
┌─────────────────┐                  ┌─────────────────────────────┐
│ collect_prices  │   Redis Pub/Sub  │  WebSocket Manager          │
│ 1. Scrape APIs  │ ───────────────► │  Connection Registry        │
│ 2. Save to DB   │                  │  Subscription Router        │
│ 3. Publish      │                  └──────────────┬──────────────┘
└─────────────────┘                                 │ WebSocket
                                                    ▼
                                              FRONTEND
```

### Subscription Protocol

Client sends:
```json
{"action": "subscribe", "channel": "market"}
{"action": "subscribe", "channel": "card", "card_id": 123}
{"action": "subscribe", "channel": "alerts", "token": "jwt..."}
{"action": "ping"}
```

Server sends:
```json
{"type": "subscribed", "channel": "market"}
{"type": "market_update", "data": {...}}
{"type": "card_price_update", "data": {"card_id": 123, "price_data": {...}}}
{"type": "price_alert", "data": {...}}
{"type": "pong"}
```

### Connection Manager

- Track connections by subscription type
- Handle disconnects gracefully
- Bridge Redis Pub/Sub to WebSocket clients
- 30-second heartbeat to keep connections alive
- Auto-reconnect on client side

---

## Clean Architecture Refactor

### Directory Structure

```
backend/app/
├── api/
│   ├── deps.py                    # Dependency injection
│   └── routes/
│       ├── cards.py               # ~100 lines (was 1,484)
│       ├── market.py              # ~80 lines (was 1,316)
│       ├── inventory.py           # ~60 lines
│       ├── auth.py                # ~50 lines
│       └── websocket.py           # ~80 lines
│
├── use_cases/
│   ├── cards/
│   │   ├── get_card_history.py
│   │   ├── get_card_detail.py
│   │   ├── search_cards.py
│   │   └── refresh_card_prices.py
│   ├── market/
│   │   ├── get_market_index.py
│   │   ├── get_market_overview.py
│   │   ├── get_top_movers.py
│   │   └── get_volume_by_format.py
│   └── inventory/
│       ├── add_to_inventory.py
│       ├── get_inventory_value.py
│       └── sync_inventory_prices.py
│
├── repositories/
│   ├── card_repo.py
│   ├── price_repo.py
│   ├── market_repo.py
│   ├── inventory_repo.py
│   ├── cache_repo.py
│   └── marketplace_repo.py
│
├── models/                        # SQLAlchemy (unchanged)
├── schemas/                       # Pydantic DTOs
└── core/                          # Config, security
```

### Layer Responsibilities

| Layer | Responsibility | Forbidden |
|-------|----------------|-----------|
| API (routes) | HTTP handling, validation, auth | Business logic, SQL |
| Use Cases | Business logic, caching decisions | HTTP concepts, raw SQL |
| Repositories | Data access, queries | Business logic |
| Domain (models) | Entity definitions | Dependencies on other layers |

---

## Frontend Optimizations

### Memoization

```typescript
export const PriceChart = memo(function PriceChart({ data }: Props) {
  const seriesKeys = useMemo(
    () => Array.from(new Set(data.map((d) => d.marketplace))),
    [data]
  );

  const chartData = useMemo(() => {
    // Transform data for Recharts
  }, [data]);

  return <LineChart data={chartData}>...</LineChart>;
});
```

### WebSocket Integration

```typescript
export function useMarketIndex(params: MarketIndexParams) {
  const { subscribe } = useWebSocket();

  useEffect(() => {
    subscribe('market');
  }, [subscribe]);

  return useQuery({
    queryKey: ['market', 'index', params],
    queryFn: () => fetchMarketIndex(params),
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,  // WebSocket handles updates
  });
}
```

### Chart Performance

- `isAnimationActive={false}` for live updates
- `connectNulls={true}` instead of server-side interpolation
- Smaller API responses (no interpolated points)

---

## Implementation Order

### Phase 1: Database Layer
1. Add TimescaleDB extension to Docker setup
2. Create migration for new schema (drop and recreate price_snapshots)
3. Create continuous aggregates
4. Update models and adapters for new fields (condition, language, price_market)

### Phase 2: Caching Layer
5. Implement Redis CacheRepository
6. Implement RateLimiter
7. Replace SimpleCache usage with CacheRepository
8. Add cache invalidation on price collection

### Phase 3: Backend Refactor
9. Create repositories (card_repo, price_repo, market_repo)
10. Create use cases for card endpoints
11. Create use cases for market endpoints
12. Refactor routes to use dependency injection
13. Remove mock data and interpolation code

### Phase 4: WebSocket Layer
14. Implement ConnectionManager
15. Implement WebSocket endpoint
16. Implement PricePublisher
17. Update Celery tasks to publish price updates

### Phase 5: Frontend
18. Implement useWebSocket hook
19. Update React Query hooks with WebSocket integration
20. Add memoization to chart components
21. Add condition/language filter UI
22. Remove mock data handling

### Phase 6: Cleanup
23. Remove old SimpleCache
24. Remove interpolation utilities
25. Remove isMockData flags
26. Update tests

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| TimescaleDB over ClickHouse | Easier migration (PostgreSQL extension), familiar SQL |
| Weekly chunk interval | Balance between query performance and chunk count |
| 5-minute cache TTL | Prices update every 30 min; 5 min is fresh enough |
| Single /ws endpoint | Simpler than multiple endpoints; subscriptions handle routing |
| No mock data | Real data only; errors show proper error states |
| Clean Architecture | Testability, maintainability, clear separation |
