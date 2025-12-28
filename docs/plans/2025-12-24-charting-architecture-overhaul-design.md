# Charting Architecture Overhaul Design

**Date:** 2025-12-24
**Status:** Approved
**Scope:** Full overhaul including TimescaleDB, Redis caching, WebSocket real-time, Clean Architecture refactor, and frontend optimizations

---

## Table of Contents

1. [Overview](#overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Docker Infrastructure](#docker-infrastructure)
4. [Data Model Design](#data-model-design)
5. [TimescaleDB Schema](#timescaledb-schema)
6. [Data Ingestion Pipeline](#data-ingestion-pipeline)
7. [Redis Caching Layer](#redis-caching-layer)
8. [WebSocket Real-Time Layer](#websocket-real-time-layer)
9. [Clean Architecture Refactor](#clean-architecture-refactor)
10. [Frontend Optimizations](#frontend-optimizations)
11. [Error Handling & Resilience](#error-handling--resilience)
12. [Observability](#observability)
13. [Testing Strategy](#testing-strategy)
14. [CI/CD Pipeline](#cicd-pipeline)
15. [Implementation Order](#implementation-order)
16. [Additional System Integrations](#additional-system-integrations)

---

## Overview

### Goals

- Replace PostgreSQL time-series queries with TimescaleDB hypertables and continuous aggregates
- Implement Redis caching to replace process-local in-memory cache
- Add WebSocket support for full real-time dashboard updates
- Refactor backend to Clean Architecture (routes → use cases → repositories)
- Optimize frontend with memoization and WebSocket integration
- Track card prices by condition, language, and foil status
- Proper multi-currency support (USD/EUR separated, no mixing)
- Integrate Scryfall bulk data for comprehensive historical coverage
- Fresh database build (no legacy data migration required)
- Remove mock data from production endpoints (keep mock adapter for testing)

### Non-Goals

- GraphQL migration (future consideration)
- Mobile app support
- Multi-region deployment
- Currency conversion (display in native currency only)
- Preserving existing database data (fresh start)

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

## Docker Infrastructure

### Updated docker-compose.yml

Replace the PostgreSQL image with TimescaleDB and add configuration for the new architecture:

```yaml
services:
  # TimescaleDB (replaces postgres:16-alpine)
  db:
    image: timescale/timescaledb:latest-pg16
    container_name: ${COMPOSE_PROJECT_NAME:-dualcaster}-db
    restart: ${RESTART_POLICY:-always}
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - dualcaster-network
    # Recommended: tune for time-series workloads
    command:
      - "postgres"
      - "-c"
      - "shared_preload_libraries=timescaledb"
      - "-c"
      - "timescaledb.telemetry_level=off"
      - "-c"
      - "max_connections=100"
      - "-c"
      - "shared_buffers=256MB"
      - "-c"
      - "effective_cache_size=768MB"
      - "-c"
      - "work_mem=16MB"

  # Redis (enhanced configuration)
  redis:
    image: redis:7-alpine
    container_name: ${COMPOSE_PROJECT_NAME:-dualcaster}-redis
    restart: ${RESTART_POLICY:-always}
    volumes:
      - redis_data:/data
    command:
      - "redis-server"
      - "--appendonly"
      - "yes"                    # Enable AOF persistence
      - "--maxmemory"
      - "256mb"
      - "--maxmemory-policy"
      - "allkeys-lru"            # Evict least recently used keys
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - dualcaster-network
```

### Fresh Database Setup

Since we're starting fresh, the setup process is:

```bash
# 1. Stop existing services and remove volumes
docker compose down -v

# 2. Pull new TimescaleDB image
docker compose pull db

# 3. Start fresh
docker compose up -d

# 4. Run migrations (creates hypertables, aggregates, etc.)
make migrate

# 5. Seed initial data from Scryfall
make import-scryfall-all
```

---

## Data Model Design

### Model Decisions

The new architecture consolidates price tracking into a single hypertable with full variant support:

| Old Model | New Design | Rationale |
|-----------|------------|-----------|
| `PriceSnapshot` (aggregated, no condition) | `price_snapshots` hypertable (with condition/language) | Full variant tracking enables per-condition charts |
| `Listing` (individual listings) | **Remove** | Listings were for current availability; we now track snapshots only |
| `Card` | Keep unchanged | Core card catalog from Scryfall |
| `Marketplace` | Keep unchanged | Marketplace definitions |
| `InventoryItem` | Keep unchanged | User collections |

### Why Remove Listings?

The `Listing` model tracked individual marketplace listings (seller, quantity, URL). For charting:
- We don't need individual listing granularity
- Aggregated snapshots per (card, marketplace, condition, language, foil) are sufficient
- Reduces storage significantly
- Simplifies queries

If individual listing tracking is needed later, it can be a separate feature.

### Condition Code Standardization

All adapters and database use consistent condition codes:

```python
# backend/app/core/constants.py
from enum import Enum

class CardCondition(str, Enum):
    MINT = "MINT"
    NEAR_MINT = "NEAR_MINT"
    LIGHTLY_PLAYED = "LIGHTLY_PLAYED"
    MODERATELY_PLAYED = "MODERATELY_PLAYED"
    HEAVILY_PLAYED = "HEAVILY_PLAYED"
    DAMAGED = "DAMAGED"

# Mapping from external sources
CONDITION_ALIASES = {
    # TCGPlayer
    "Near Mint": CardCondition.NEAR_MINT,
    "Lightly Played": CardCondition.LIGHTLY_PLAYED,
    "Moderately Played": CardCondition.MODERATELY_PLAYED,
    "Heavily Played": CardCondition.HEAVILY_PLAYED,
    "Damaged": CardCondition.DAMAGED,
    # CardTrader / Cardmarket style
    "NM": CardCondition.NEAR_MINT,
    "LP": CardCondition.LIGHTLY_PLAYED,
    "MP": CardCondition.MODERATELY_PLAYED,
    "HP": CardCondition.HEAVILY_PLAYED,
    "DMG": CardCondition.DAMAGED,
    # Scryfall (doesn't have condition, default)
    None: CardCondition.NEAR_MINT,
}

def normalize_condition(condition: str | None) -> CardCondition:
    """Normalize any condition string to standard enum."""
    if condition is None:
        return CardCondition.NEAR_MINT
    return CONDITION_ALIASES.get(condition, CardCondition.NEAR_MINT)
```

### Language Standardization

```python
class CardLanguage(str, Enum):
    ENGLISH = "English"
    JAPANESE = "Japanese"
    GERMAN = "German"
    FRENCH = "French"
    ITALIAN = "Italian"
    SPANISH = "Spanish"
    PORTUGUESE = "Portuguese"
    KOREAN = "Korean"
    CHINESE_SIMPLIFIED = "Chinese Simplified"
    CHINESE_TRADITIONAL = "Chinese Traditional"
    RUSSIAN = "Russian"
    PHYREXIAN = "Phyrexian"

LANGUAGE_ALIASES = {
    "EN": CardLanguage.ENGLISH,
    "JA": CardLanguage.JAPANESE,
    "DE": CardLanguage.GERMAN,
    "FR": CardLanguage.FRENCH,
    "IT": CardLanguage.ITALIAN,
    "ES": CardLanguage.SPANISH,
    "PT": CardLanguage.PORTUGUESE,
    "KO": CardLanguage.KOREAN,
    "ZHS": CardLanguage.CHINESE_SIMPLIFIED,
    "ZHT": CardLanguage.CHINESE_TRADITIONAL,
    "RU": CardLanguage.RUSSIAN,
    "PH": CardLanguage.PHYREXIAN,
    # Full names map to themselves
    **{lang.value: lang for lang in CardLanguage},
}
```

### Currency Separation Strategy

Currencies are **never mixed** in aggregations. Each marketplace has a primary currency:

| Marketplace | Currency | Region |
|-------------|----------|--------|
| TCGPlayer | USD | North America |
| CardTrader | EUR | Europe |
| Cardmarket | EUR | Europe |
| Manapool | USD | North America |

**Market Index by Currency:**

```sql
-- USD Market Index (TCGPlayer, Manapool)
SELECT * FROM market_index_hourly WHERE currency = 'USD';

-- EUR Market Index (CardTrader, Cardmarket)
SELECT * FROM market_index_hourly WHERE currency = 'EUR';
```

**Frontend Currency Selection:**

```typescript
// User preference stored in localStorage/context
const [currency, setCurrency] = useState<'USD' | 'EUR'>('USD');

// Fetch appropriate index
const { data } = useMarketIndex({ currency, period: '7d' });
```

**No Conversion:** We display prices in their native currency. Users see USD or EUR, not converted values. This ensures accuracy.

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

### Backfill Strategy

After creating continuous aggregates, backfill historical data:

```sql
-- Backfill continuous aggregates with existing data
CALL refresh_continuous_aggregate('market_index_30min', NULL, NULL);
CALL refresh_continuous_aggregate('market_index_hourly', NULL, NULL);
CALL refresh_continuous_aggregate('market_index_daily', NULL, NULL);
CALL refresh_continuous_aggregate('card_prices_hourly', NULL, NULL);
```

---

## Data Ingestion Pipeline

### Overview

The data ingestion pipeline collects price data from multiple sources and stores it in the `price_snapshots` hypertable. Each source provides different data:

| Source | Data Type | Frequency | Currency | Condition Support |
|--------|-----------|-----------|----------|-------------------|
| Scryfall Bulk | Historical prices | Daily download | USD | No (default NM) |
| Scryfall API | Current prices | Every 30 min | USD | No (default NM) |
| CardTrader API | Live listings | Every 30 min | EUR | Yes |
| MTGJSON | Historical archive | Weekly | USD | No (default NM) |

### Scryfall Bulk Data Integration

**Priority: High** - This provides comprehensive historical coverage.

```python
# backend/app/services/ingestion/scryfall_bulk.py

import httpx
from datetime import datetime, timedelta

BULK_DATA_URL = "https://api.scryfall.com/bulk-data"

class ScryfallBulkIngester:
    """Downloads and processes Scryfall bulk data files."""

    async def get_bulk_download_url(self, bulk_type: str = "default_cards") -> str:
        """Get the current download URL for bulk data."""
        async with httpx.AsyncClient() as client:
            response = await client.get(BULK_DATA_URL)
            data = response.json()
            for item in data["data"]:
                if item["type"] == bulk_type:
                    return item["download_uri"]
        raise ValueError(f"Bulk type {bulk_type} not found")

    async def download_and_process(self, db: AsyncSession) -> int:
        """Download bulk data and insert price snapshots."""
        url = await self.get_bulk_download_url()

        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url) as response:
                # Stream large file to avoid memory issues
                cards_processed = 0
                batch = []

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    card = json.loads(line)

                    # Extract price data
                    if card.get("prices"):
                        snapshot = self._create_snapshot(card)
                        if snapshot:
                            batch.append(snapshot)

                    if len(batch) >= 1000:
                        await self._insert_batch(db, batch)
                        cards_processed += len(batch)
                        batch = []

                if batch:
                    await self._insert_batch(db, batch)
                    cards_processed += len(batch)

                return cards_processed

    def _create_snapshot(self, card: dict) -> dict | None:
        """Create a price snapshot from Scryfall card data."""
        prices = card.get("prices", {})

        # USD prices
        usd_price = prices.get("usd")
        usd_foil = prices.get("usd_foil")

        if not usd_price and not usd_foil:
            return None

        return {
            "scryfall_id": card["id"],
            "name": card["name"],
            "set_code": card["set"],
            "collector_number": card["collector_number"],
            "price": float(usd_price) if usd_price else None,
            "price_foil": float(usd_foil) if usd_foil else None,
            "currency": "USD",
            "condition": "NEAR_MINT",  # Scryfall doesn't track condition
            "language": "English",
            "time": datetime.utcnow(),
        }
```

### Adapter Output Standardization

All adapters output a consistent `PriceData` format:

```python
# backend/app/services/ingestion/base.py

from dataclasses import dataclass
from datetime import datetime
from app.core.constants import CardCondition, CardLanguage

@dataclass
class PriceData:
    """Standardized price data from any adapter."""
    card_id: int
    marketplace_id: int
    time: datetime
    price: float
    currency: str
    condition: CardCondition = CardCondition.NEAR_MINT
    language: CardLanguage = CardLanguage.ENGLISH
    is_foil: bool = False
    price_low: float | None = None
    price_mid: float | None = None
    price_high: float | None = None
    price_market: float | None = None
    num_listings: int | None = None
    total_quantity: int | None = None

    def to_snapshot_dict(self) -> dict:
        """Convert to dict for database insertion."""
        return {
            "card_id": self.card_id,
            "marketplace_id": self.marketplace_id,
            "time": self.time,
            "price": self.price,
            "currency": self.currency,
            "condition": self.condition.value,
            "language": self.language.value,
            "is_foil": self.is_foil,
            "price_low": self.price_low,
            "price_mid": self.price_mid,
            "price_high": self.price_high,
            "price_market": self.price_market,
            "num_listings": self.num_listings,
            "total_quantity": self.total_quantity,
        }
```

### Celery Task Updates

```python
# backend/app/tasks/ingestion.py

from app.services.ingestion.scryfall_bulk import ScryfallBulkIngester
from app.repositories.price_repo import PriceRepository
from app.repositories.cache_repo import CacheRepository

@celery_app.task(queue="ingestion")
async def collect_prices():
    """Collect prices from all active marketplaces."""
    async with get_db_session() as db:
        redis = await get_redis()
        price_repo = PriceRepository(db)
        cache_repo = CacheRepository(redis)

        adapters = get_active_adapters()
        all_prices: list[PriceData] = []

        for adapter in adapters:
            try:
                prices = await adapter.fetch_prices()
                all_prices.extend(prices)
            except Exception as e:
                logger.error(f"Adapter {adapter.name} failed: {e}")

        # Batch insert all prices
        if all_prices:
            await price_repo.insert_batch(all_prices)

            # Invalidate cache
            await cache_repo.invalidate_market()

            # Publish to WebSocket
            await publish_price_update(redis, {
                "type": "prices_updated",
                "count": len(all_prices),
                "marketplaces": list(set(p.marketplace_id for p in all_prices)),
            })

        return {"inserted": len(all_prices)}

@celery_app.task(queue="ingestion")
async def ingest_scryfall_bulk():
    """Daily task to download and process Scryfall bulk data."""
    async with get_db_session() as db:
        ingester = ScryfallBulkIngester()
        count = await ingester.download_and_process(db)
        logger.info(f"Processed {count} cards from Scryfall bulk data")
        return {"processed": count}
```

### Celery Beat Schedule

```python
# backend/app/tasks/celery_app.py

celery_app.conf.beat_schedule = {
    "collect-prices": {
        "task": "app.tasks.ingestion.collect_prices",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
    "ingest-scryfall-bulk": {
        "task": "app.tasks.ingestion.ingest_scryfall_bulk",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    "refresh-analytics": {
        "task": "app.tasks.analytics.calculate_metrics",
        "schedule": crontab(minute=0),  # Every hour
    },
}
```

---

## Alembic + TimescaleDB Migrations

### Migration Structure

TimescaleDB-specific operations require raw SQL in Alembic migrations:

```python
# backend/alembic/versions/001_initial_timescaledb.py

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None

def upgrade():
    # Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # Create enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE card_condition AS ENUM (
                'MINT', 'NEAR_MINT', 'LIGHTLY_PLAYED',
                'MODERATELY_PLAYED', 'HEAVILY_PLAYED', 'DAMAGED'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE card_language AS ENUM (
                'English', 'Japanese', 'German', 'French', 'Italian',
                'Spanish', 'Portuguese', 'Korean', 'Chinese Simplified',
                'Chinese Traditional', 'Russian', 'Phyrexian'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create price_snapshots table
    op.execute("""
        CREATE TABLE price_snapshots (
            time TIMESTAMPTZ NOT NULL,
            card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
            marketplace_id INTEGER NOT NULL REFERENCES marketplaces(id) ON DELETE CASCADE,
            condition card_condition NOT NULL DEFAULT 'NEAR_MINT',
            is_foil BOOLEAN NOT NULL DEFAULT FALSE,
            language card_language NOT NULL DEFAULT 'English',
            price NUMERIC(10,2) NOT NULL,
            price_low NUMERIC(10,2),
            price_mid NUMERIC(10,2),
            price_high NUMERIC(10,2),
            price_market NUMERIC(10,2),
            currency VARCHAR(3) NOT NULL DEFAULT 'USD',
            num_listings INTEGER,
            total_quantity INTEGER,
            UNIQUE (time, card_id, marketplace_id, condition, is_foil, language)
        );
    """)

    # Convert to hypertable
    op.execute("""
        SELECT create_hypertable('price_snapshots', 'time',
            chunk_time_interval => INTERVAL '7 days'
        );
    """)

    # Create indexes
    op.execute("CREATE INDEX ix_snapshots_card_time ON price_snapshots (card_id, time DESC)")
    op.execute("CREATE INDEX ix_snapshots_currency_time ON price_snapshots (currency, time DESC)")
    # ... other indexes ...

def downgrade():
    op.execute("DROP TABLE IF EXISTS price_snapshots CASCADE")
    op.execute("DROP TYPE IF EXISTS card_condition")
    op.execute("DROP TYPE IF EXISTS card_language")
```

### Continuous Aggregates Migration

```python
# backend/alembic/versions/002_continuous_aggregates.py

def upgrade():
    # 30-minute market index
    op.execute("""
        CREATE MATERIALIZED VIEW market_index_30min
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('30 minutes', time) AS bucket,
            currency,
            AVG(price) AS avg_price,
            COUNT(DISTINCT card_id) AS card_count,
            SUM(price * COALESCE(total_quantity, num_listings, 1)) AS volume
        FROM price_snapshots
        WHERE price > 0
        GROUP BY bucket, currency
        WITH NO DATA;
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('market_index_30min',
            start_offset => INTERVAL '2 hours',
            end_offset => INTERVAL '30 minutes',
            schedule_interval => INTERVAL '30 minutes'
        );
    """)

    # ... similar for hourly, daily aggregates ...

def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS market_index_30min CASCADE")
    # ... other views ...
```

### Handling Continuous Aggregate Lag

Continuous aggregates have an `end_offset` that creates a gap in recent data. To get real-time charts:

```python
# backend/app/repositories/market_repo.py

class MarketRepository:
    async def get_market_index(
        self,
        currency: str,
        period: str,
        condition: str | None = None,
    ) -> list[dict]:
        """Get market index with real-time data for recent period."""

        # Determine which aggregate to use
        if period == "7d":
            aggregate_table = "market_index_30min"
            bucket_interval = "30 minutes"
            lag_threshold = timedelta(minutes=30)
        elif period in ("30d", "90d"):
            aggregate_table = "market_index_hourly"
            bucket_interval = "1 hour"
            lag_threshold = timedelta(hours=1)
        else:  # 1y
            aggregate_table = "market_index_daily"
            bucket_interval = "1 day"
            lag_threshold = timedelta(days=1)

        now = datetime.utcnow()
        period_start = now - PERIOD_DELTAS[period]

        # Query aggregate for historical data
        aggregate_query = f"""
            SELECT bucket, avg_price, card_count, volume
            FROM {aggregate_table}
            WHERE currency = :currency
              AND bucket >= :start
              AND bucket < :lag_cutoff
            ORDER BY bucket
        """

        # Query raw table for recent data (within lag threshold)
        realtime_query = f"""
            SELECT
                time_bucket('{bucket_interval}', time) AS bucket,
                AVG(price) AS avg_price,
                COUNT(DISTINCT card_id) AS card_count,
                SUM(price * COALESCE(total_quantity, num_listings, 1)) AS volume
            FROM price_snapshots
            WHERE currency = :currency
              AND time >= :lag_cutoff
            GROUP BY bucket
            ORDER BY bucket
        """

        lag_cutoff = now - lag_threshold

        # Execute both queries
        aggregate_result = await self.db.execute(
            text(aggregate_query),
            {"currency": currency, "start": period_start, "lag_cutoff": lag_cutoff}
        )
        realtime_result = await self.db.execute(
            text(realtime_query),
            {"currency": currency, "lag_cutoff": lag_cutoff}
        )

        # Combine results
        return [dict(row) for row in aggregate_result] + [dict(row) for row in realtime_result]
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

### Cache Invalidation Strategy

Cache invalidation occurs at specific points in the data pipeline:

| Event | Keys Invalidated | Trigger Point |
|-------|------------------|---------------|
| Price collection completes | `cache:market:*`, `cache:card:{id}:*` | Celery task `collect_prices` |
| Card data updated | `cache:card:{id}:*` | Card update endpoint |
| Manual refresh requested | Specific key pattern | Admin endpoint |

```python
class CacheInvalidator:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern. Returns count deleted."""
        keys = []
        async for key in self.redis.scan_iter(match=f"cache:{pattern}"):
            keys.append(key)
        if keys:
            return await self.redis.delete(*keys)
        return 0

    async def invalidate_card(self, card_id: int) -> None:
        await self.invalidate_pattern(f"card:{card_id}:*")

    async def invalidate_market(self) -> None:
        await self.invalidate_pattern("market:*")

    async def invalidate_all(self) -> None:
        await self.invalidate_pattern("*")
```

**Race Condition Prevention:**

Use cache versioning to prevent stale data from being written after invalidation:

```python
async def set_with_version(self, key: str, value: Any, version: int) -> bool:
    """Only set if version matches current. Returns success."""
    current_version = await self.redis.get(f"{key}:version")
    if current_version and int(current_version) > version:
        return False  # Stale write, ignore
    pipe = self.redis.pipeline()
    pipe.setex(key, self.default_ttl, json.dumps(value))
    pipe.set(f"{key}:version", version)
    await pipe.execute()
    return True
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

### Authentication & Authorization

WebSocket connections support both authenticated and anonymous access:

| Channel | Auth Required | Access Level |
|---------|---------------|--------------|
| `market` | No | Public market data |
| `card` | No | Public card prices |
| `alerts` | Yes (JWT) | User's personal alerts |
| `inventory` | Yes (JWT) | User's inventory updates |

**Connection Authentication Flow:**

```python
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(None),
):
    await websocket.accept()

    # Optional authentication
    user_id = None
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("sub")
        except jwt.InvalidTokenError:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            # Don't disconnect - allow anonymous access

    connection = Connection(websocket=websocket, user_id=user_id)
    manager.register(connection)

    try:
        async for message in websocket.iter_json():
            await handle_message(connection, message)
    except WebSocketDisconnect:
        manager.unregister(connection)
```

**Subscription Authorization:**

```python
async def handle_subscribe(connection: Connection, channel: str, params: dict):
    # Public channels - no auth needed
    if channel in ("market", "card"):
        await manager.subscribe(connection, channel, params.get("card_id"))
        return

    # Protected channels - require auth
    if not connection.user_id:
        await connection.send({"type": "error", "message": "Authentication required"})
        return

    if channel == "alerts":
        await manager.subscribe(connection, f"alerts:user:{connection.user_id}")
    elif channel == "inventory":
        await manager.subscribe(connection, f"inventory:user:{connection.user_id}")
```

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

### Existing Services Migration

Current `services/` directory maps to new architecture:

| Current Location | New Location | Notes |
|-----------------|--------------|-------|
| `services/auth.py` | `use_cases/auth/` | Split into login, register, refresh use cases |
| `services/ingestion/adapters/` | `services/ingestion/adapters/` | **Keep as-is** - adapters are infrastructure |
| `services/ingestion/scryfall.py` | `services/ingestion/` | **Keep as-is** - external service integration |
| `services/ingestion/registry.py` | `services/ingestion/` | **Keep as-is** |
| `services/agents/analytics.py` | `use_cases/analytics/` | Business logic moves to use cases |
| `services/agents/recommendation.py` | `use_cases/recommendations/` | Business logic moves to use cases |
| `services/agents/normalization.py` | `core/normalization.py` | Utility functions move to core |
| `services/llm/` | `services/llm/` | **Keep as-is** - external service clients |
| `services/vectorization/` | `services/vectorization/` | **Keep as-is** - external service integration |

**Key Principle:** The `services/` directory is for **external integrations** (APIs, LLMs, vector stores). Business logic moves to `use_cases/`. Data access moves to `repositories/`.

### Updated Directory Structure

```
backend/app/
├── api/
│   ├── deps.py                    # Dependency injection
│   └── routes/                    # HTTP endpoints (~50-100 LOC each)
│
├── use_cases/                     # Business logic
│   ├── cards/
│   ├── market/
│   ├── inventory/
│   ├── auth/
│   ├── analytics/                 # From services/agents/analytics.py
│   └── recommendations/           # From services/agents/recommendation.py
│
├── repositories/                  # Data access
│   ├── card_repo.py
│   ├── price_repo.py
│   ├── market_repo.py
│   ├── inventory_repo.py
│   └── cache_repo.py
│
├── services/                      # External integrations (KEEP)
│   ├── ingestion/                 # Marketplace adapters
│   │   ├── adapters/
│   │   ├── scryfall.py
│   │   ├── scryfall_bulk.py       # NEW
│   │   └── registry.py
│   ├── llm/                       # LLM clients
│   └── vectorization/             # Embedding service
│
├── models/                        # SQLAlchemy models
├── schemas/                       # Pydantic DTOs
├── core/                          # Config, constants, utilities
│   ├── config.py
│   ├── security.py
│   ├── constants.py               # CardCondition, CardLanguage enums
│   └── normalization.py           # From services/agents/normalization.py
│
└── tasks/                         # Celery tasks
```

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

**WebSocket Context Provider:**

```typescript
// frontend/src/contexts/WebSocketContext.tsx

import { createContext, useContext, useEffect, useRef, useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

interface WebSocketContextType {
  subscribe: (channel: string, params?: Record<string, unknown>) => void;
  unsubscribe: (channel: string) => void;
  isConnected: boolean;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const subscriptionsRef = useRef<Set<string>>(new Set());

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      setIsConnected(true);
      // Resubscribe to all channels
      subscriptionsRef.current.forEach(channel => {
        wsRef.current?.send(JSON.stringify({ action: 'subscribe', channel }));
      });
    };

    wsRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      handleMessage(message);
    };

    wsRef.current.onclose = () => {
      setIsConnected(false);
      // Reconnect with exponential backoff
      setTimeout(connect, 3000);
    };
  }, []);

  const handleMessage = useCallback((message: any) => {
    switch (message.type) {
      case 'market_update':
        // Update React Query cache directly
        queryClient.setQueryData(
          ['market', 'index', { currency: message.data.currency }],
          (old: any) => {
            if (!old) return old;
            // Append new data point, remove oldest if needed
            const newPoints = [...old.points, message.data.point];
            if (newPoints.length > 1000) newPoints.shift();
            return { ...old, points: newPoints };
          }
        );
        break;

      case 'card_price_update':
        queryClient.setQueryData(
          ['card', message.data.card_id, 'history'],
          (old: any) => {
            if (!old) return old;
            return { ...old, latestPrice: message.data.price };
          }
        );
        // Also invalidate to trigger refetch for full data
        queryClient.invalidateQueries({
          queryKey: ['card', message.data.card_id],
          refetchType: 'none', // Don't refetch immediately
        });
        break;

      case 'prices_updated':
        // Bulk update notification - invalidate market queries
        queryClient.invalidateQueries({
          queryKey: ['market'],
          refetchType: 'active', // Refetch active queries
        });
        break;
    }
  }, [queryClient]);

  const subscribe = useCallback((channel: string, params?: Record<string, unknown>) => {
    subscriptionsRef.current.add(channel);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'subscribe', channel, ...params }));
    }
  }, []);

  const unsubscribe = useCallback((channel: string) => {
    subscriptionsRef.current.delete(channel);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'unsubscribe', channel }));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  return (
    <WebSocketContext.Provider value={{ subscribe, unsubscribe, isConnected }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) throw new Error('useWebSocket must be used within WebSocketProvider');
  return context;
};
```

**Hook with WebSocket Integration:**

```typescript
// frontend/src/hooks/useMarketIndex.ts

export function useMarketIndex(params: MarketIndexParams) {
  const { subscribe, unsubscribe, isConnected } = useWebSocket();

  useEffect(() => {
    subscribe('market');
    return () => unsubscribe('market');
  }, [subscribe, unsubscribe]);

  return useQuery({
    queryKey: ['market', 'index', params],
    queryFn: () => fetchMarketIndex(params),
    staleTime: 1000 * 60 * 5,        // 5 minutes
    gcTime: 1000 * 60 * 30,          // 30 minutes
    refetchOnWindowFocus: false,     // WebSocket handles updates
    refetchInterval: isConnected ? false : 1000 * 60, // Fallback polling if WS disconnected
  });
}
```

**Currency Preference Hook:**

```typescript
// frontend/src/hooks/useCurrency.ts

export function useCurrency() {
  const [currency, setCurrency] = useState<'USD' | 'EUR'>(() => {
    if (typeof window !== 'undefined') {
      return (localStorage.getItem('currency') as 'USD' | 'EUR') || 'USD';
    }
    return 'USD';
  });

  const updateCurrency = useCallback((newCurrency: 'USD' | 'EUR') => {
    setCurrency(newCurrency);
    localStorage.setItem('currency', newCurrency);
  }, []);

  return { currency, setCurrency: updateCurrency };
}
```

### Chart Performance

- `isAnimationActive={false}` for live updates
- `connectNulls={true}` instead of server-side interpolation
- Smaller API responses (no interpolated points)

---

## Error Handling & Resilience

### Redis Unavailability

When Redis is unavailable, the system degrades gracefully:

```python
class ResilientCacheRepository(CacheRepository):
    async def get_or_compute(
        self,
        key_parts: tuple[str, ...],
        compute_fn: Callable[[], Any],
        ttl: timedelta | None = None,
    ) -> Any:
        try:
            cached = await self.get(*key_parts)
            if cached is not None:
                return cached
        except RedisError as e:
            logger.warning(f"Redis unavailable, falling back to compute: {e}")
            # Fall through to compute

        result = await compute_fn()

        try:
            await self.set(*key_parts, value=result, ttl=ttl)
        except RedisError as e:
            logger.warning(f"Failed to cache result: {e}")

        return result
```

### WebSocket Error Handling

| Scenario | Behavior |
|----------|----------|
| Redis Pub/Sub disconnects | Auto-reconnect with exponential backoff (1s, 2s, 4s, max 30s) |
| Client sends invalid JSON | Send error message, keep connection open |
| Client sends unknown action | Send error message, keep connection open |
| Server-side exception | Log error, send generic error to client, keep connection |
| Heartbeat timeout (60s) | Close connection, client reconnects |

```python
class ConnectionManager:
    async def handle_redis_disconnect(self):
        backoff = 1
        while True:
            try:
                await self.connect_redis()
                await self.resubscribe_all()
                logger.info("Redis reconnected")
                break
            except RedisError:
                logger.warning(f"Redis reconnect failed, retry in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
```

### Database Connection Errors

- Use connection pooling with health checks
- Retry transient errors (connection reset, timeout) up to 3 times
- Circuit breaker pattern for sustained failures

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(OperationalError),
)
async def execute_with_retry(session: AsyncSession, stmt):
    return await session.execute(stmt)
```

---

## Observability

### Metrics (Prometheus)

```python
# Cache metrics
cache_hits = Counter("cache_hits_total", "Cache hits", ["key_prefix"])
cache_misses = Counter("cache_misses_total", "Cache misses", ["key_prefix"])
cache_latency = Histogram("cache_latency_seconds", "Cache operation latency")

# WebSocket metrics
ws_connections = Gauge("websocket_connections", "Active WebSocket connections")
ws_subscriptions = Gauge("websocket_subscriptions", "Active subscriptions", ["channel"])
ws_messages_sent = Counter("websocket_messages_sent_total", "Messages sent", ["type"])

# Database metrics
db_query_latency = Histogram("db_query_latency_seconds", "Query latency", ["query_type"])
continuous_aggregate_lag = Gauge("timescale_aggregate_lag_seconds", "Aggregate refresh lag", ["aggregate"])
```

### Logging Strategy

| Level | Usage |
|-------|-------|
| ERROR | Exceptions, failed operations that affect users |
| WARNING | Redis unavailable, retry attempts, degraded operation |
| INFO | Request start/end, cache hits/misses, WebSocket connects/disconnects |
| DEBUG | Query details, message payloads (redacted), timing breakdowns |

**Structured logging format:**

```python
logger.info(
    "Price collection completed",
    extra={
        "marketplace": "tcgplayer",
        "cards_updated": 1523,
        "duration_seconds": 45.2,
        "cache_invalidated": True,
    }
)
```

### Health Checks

```python
@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    checks = {}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {e}"

    # Redis
    try:
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {e}"

    # TimescaleDB aggregates
    try:
        result = await db.execute(text("""
            SELECT hypertable_name, last_run_started_at
            FROM timescaledb_information.continuous_aggregate_stats
        """))
        for row in result:
            lag = datetime.utcnow() - row.last_run_started_at
            if lag > timedelta(hours=2):
                checks[f"aggregate_{row.hypertable_name}"] = f"stale: {lag}"
            else:
                checks[f"aggregate_{row.hypertable_name}"] = "healthy"
    except Exception as e:
        checks["aggregates"] = f"error: {e}"

    status = "healthy" if all("unhealthy" not in v and "stale" not in v for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
```

### Alerting Rules

| Metric | Threshold | Action |
|--------|-----------|--------|
| `cache_misses / cache_hits` | > 0.5 for 5min | Check cache TTL, invalidation frequency |
| `websocket_connections` | Drop > 50% in 1min | Check server health, network |
| `continuous_aggregate_lag` | > 2 hours | Check TimescaleDB worker, disk space |
| `db_query_latency{p99}` | > 5s | Check slow query log, indexes |

---

## Testing Strategy

### Unit Tests

```python
# Test use cases with mocked repositories
class TestGetCardHistory:
    async def test_returns_cached_data(self):
        cache_repo = Mock(spec=CacheRepository)
        cache_repo.get.return_value = [{"time": "...", "price": 10.0}]

        use_case = GetCardHistory(cache_repo=cache_repo, price_repo=Mock())
        result = await use_case.execute(card_id=123, period="30d")

        assert result == [{"time": "...", "price": 10.0}]
        cache_repo.get.assert_called_once()

    async def test_computes_when_cache_miss(self):
        cache_repo = Mock(spec=CacheRepository)
        cache_repo.get.return_value = None
        price_repo = Mock(spec=PriceRepository)
        price_repo.get_history.return_value = [...]

        use_case = GetCardHistory(cache_repo=cache_repo, price_repo=price_repo)
        result = await use_case.execute(card_id=123, period="30d")

        price_repo.get_history.assert_called_once()
        cache_repo.set.assert_called_once()
```

### Integration Tests

```python
# Test against real TimescaleDB (Docker)
@pytest.fixture
async def timescale_db():
    """Spin up TimescaleDB container for integration tests."""
    async with create_test_database() as db:
        await run_migrations(db)
        yield db

class TestContinuousAggregates:
    async def test_market_index_aggregates_correctly(self, timescale_db):
        # Insert test data
        await insert_price_snapshots(timescale_db, [
            {"time": now - hours(2), "card_id": 1, "price": 10.0},
            {"time": now - hours(1), "card_id": 1, "price": 12.0},
            {"time": now, "card_id": 1, "price": 11.0},
        ])

        # Force aggregate refresh
        await timescale_db.execute(
            "CALL refresh_continuous_aggregate('market_index_hourly', NULL, NULL)"
        )

        # Query aggregate
        result = await timescale_db.execute("""
            SELECT bucket, avg_price FROM market_index_hourly
            ORDER BY bucket
        """)
        rows = result.fetchall()

        assert len(rows) == 3
        assert rows[0].avg_price == 10.0
```

### WebSocket Tests

```python
@pytest.fixture
async def ws_client():
    async with TestClient(app) as client:
        async with client.websocket_connect("/ws") as ws:
            yield ws

class TestWebSocket:
    async def test_subscribe_market(self, ws_client):
        await ws_client.send_json({"action": "subscribe", "channel": "market"})
        response = await ws_client.receive_json()
        assert response["type"] == "subscribed"
        assert response["channel"] == "market"

    async def test_requires_auth_for_alerts(self, ws_client):
        await ws_client.send_json({"action": "subscribe", "channel": "alerts"})
        response = await ws_client.receive_json()
        assert response["type"] == "error"
        assert "Authentication required" in response["message"]

    async def test_receives_price_updates(self, ws_client, redis):
        await ws_client.send_json({"action": "subscribe", "channel": "card", "card_id": 123})
        await ws_client.receive_json()  # subscribed confirmation

        # Simulate price update from Celery
        await redis.publish("channel:prices:card:123", json.dumps({"price": 15.0}))

        response = await asyncio.wait_for(ws_client.receive_json(), timeout=2.0)
        assert response["type"] == "card_price_update"
        assert response["data"]["price"] == 15.0
```

### Load Tests

```python
# locustfile.py
from locust import HttpUser, task, between

class MarketUser(HttpUser):
    wait_time = between(1, 3)

    @task(10)
    def get_market_index(self):
        self.client.get("/api/market/index?period=7d&currency=USD")

    @task(5)
    def get_card_history(self):
        card_id = random.randint(1, 10000)
        self.client.get(f"/api/cards/{card_id}/history?period=30d")

    @task(1)
    def search_cards(self):
        self.client.get("/api/cards/search?q=lightning+bolt")
```

### Test Coverage Requirements

| Component | Minimum Coverage |
|-----------|-----------------|
| Use Cases | 90% |
| Repositories | 80% |
| API Routes | 70% |
| WebSocket handlers | 80% |

---

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml

name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install ruff
          cd backend && pip install -e ".[dev]"
      - name: Run linters
        run: make lint

  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: timescale/timescaledb:latest-pg16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -e ".[dev]"

      - name: Run migrations
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test
          REDIS_URL: redis://localhost:6379/0
        run: |
          cd backend
          alembic upgrade head

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test
          REDIS_URL: redis://localhost:6379/0
          SECRET_KEY: test-secret-key
        run: |
          cd backend
          pytest -v --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: backend/coverage.xml

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: Run tests
        run: cd frontend && npm test -- --coverage

      - name: Build
        run: cd frontend && npm run build

  integration-tests:
    runs-on: ubuntu-latest
    needs: [test-backend, test-frontend]
    steps:
      - uses: actions/checkout@v4

      - name: Start services
        run: docker compose up -d --build

      - name: Wait for services
        run: |
          timeout 120 bash -c 'until curl -s http://localhost:8000/api/health | grep -q healthy; do sleep 5; done'

      - name: Run integration tests
        run: |
          docker compose exec -T backend pytest tests/integration/ -v

      - name: Collect logs on failure
        if: failure()
        run: docker compose logs

      - name: Stop services
        if: always()
        run: docker compose down -v
```

### WebSocket Testing in CI

```python
# backend/tests/integration/test_websocket.py

import pytest
import asyncio
from httpx import AsyncClient
from httpx_ws import aconnect_ws

@pytest.mark.asyncio
async def test_websocket_market_subscription(app_client: AsyncClient):
    """Test WebSocket market subscription in CI environment."""
    async with aconnect_ws("ws://localhost:8000/ws", app_client) as ws:
        # Subscribe to market channel
        await ws.send_json({"action": "subscribe", "channel": "market"})

        # Wait for subscription confirmation
        message = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
        assert message["type"] == "subscribed"
        assert message["channel"] == "market"

@pytest.mark.asyncio
async def test_websocket_reconnection(app_client: AsyncClient):
    """Test that WebSocket reconnection works."""
    async with aconnect_ws("ws://localhost:8000/ws", app_client) as ws:
        await ws.send_json({"action": "subscribe", "channel": "market"})
        await ws.receive_json()  # subscription confirmation

        # Send ping
        await ws.send_json({"action": "ping"})
        pong = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
        assert pong["type"] == "pong"
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v8.56.0
    hooks:
      - id: eslint
        files: \.[jt]sx?$
        types: [file]
        additional_dependencies:
          - eslint@8.56.0
          - typescript@5.3.3

  - repo: local
    hooks:
      - id: pytest-check
        name: pytest quick check
        entry: bash -c 'cd backend && pytest tests/unit/ -q --tb=no'
        language: system
        pass_filenames: false
        always_run: true
```

---

## Implementation Order

### Phase 1: Infrastructure Setup (Day 1)
1. Update `docker-compose.yml` with TimescaleDB image
2. Create `backend/app/core/constants.py` with enums
3. Create Alembic migration for TimescaleDB schema
4. Run `docker compose down -v && docker compose up -d`
5. Verify TimescaleDB is working: `make db-shell` then `\dx` shows timescaledb

### Phase 2: Data Layer (Days 2-3)
6. Create `repositories/price_repo.py` with insert/query methods
7. Create `repositories/card_repo.py`
8. Create `repositories/market_repo.py` with aggregate lag handling
9. Create `repositories/cache_repo.py` with Redis operations
10. Update `models/price_snapshot.py` to match new schema
11. Remove `models/listing.py` and related code

### Phase 3: Ingestion Pipeline (Days 4-5)
12. Create `services/ingestion/scryfall_bulk.py`
13. Update all adapters to use `PriceData` dataclass
14. Add condition/language normalization to adapters
15. Update Celery tasks to use new repositories
16. Add WebSocket publish calls to price collection task
17. Test: `make trigger-scrape` and verify data in DB

### Phase 4: Use Cases & Routes (Days 6-8)
18. Create `use_cases/market/get_market_index.py`
19. Create `use_cases/market/get_market_overview.py`
20. Create `use_cases/cards/get_card_history.py`
21. Refactor `api/routes/market.py` to use use cases (~80 LOC)
22. Refactor `api/routes/cards.py` to use use cases (~100 LOC)
23. Remove old SimpleCache usage

### Phase 5: WebSocket Layer (Days 9-10)
24. Create `api/routes/websocket.py` with ConnectionManager
25. Add Redis Pub/Sub bridge
26. Add authentication for protected channels
27. Test: Connect via browser console, subscribe, verify messages

### Phase 6: Frontend (Days 11-13)
28. Create `contexts/WebSocketContext.tsx`
29. Create `hooks/useWebSocket.ts`
30. Create `hooks/useCurrency.ts`
31. Update `hooks/useMarketIndex.ts` with WebSocket integration
32. Add currency toggle to dashboard
33. Add condition filter to card detail page
34. Update chart components with memoization

### Phase 7: Testing & Polish (Days 14-15)
35. Write unit tests for use cases (90% coverage target)
36. Write integration tests for WebSocket
37. Remove all mock data from production endpoints
38. Remove old interpolation code
39. Update CI/CD workflow
40. Run full test suite: `make test`

### Phase 8: Deployment & Verification
41. Deploy to staging environment
42. Run Scryfall bulk import: `make import-scryfall-all`
43. Verify charts show real data
44. Monitor for 24 hours
45. Deploy to production

---

## Additional System Integrations

This section covers existing features that need to be integrated into the new architecture.

### 1. LLM/AI System Integration

**Current State:** OpenAI/Anthropic clients with in-memory caching for market explanations and recommendation rationales.

**Migration Plan:**

```
services/llm/                     # KEEP as external integration
├── base.py                       # Abstract client
├── openai_client.py
├── anthropic_client.py
├── cache.py                      # → Move to Redis!
└── enhanced_prompts.py

use_cases/
├── market/
│   └── get_market_explanation.py  # NEW: Uses LLM + market data
└── cards/
    └── get_card_insight.py        # NEW: Uses LLM + signals
```

**Upgrades:**
- Move LLM response cache from in-memory to Redis for persistence across restarts
- Add `cache:llm:explanation:{card_id}:{hash}` key pattern
- TTL: 1 hour for explanations (they're contextual to current prices)

```python
# use_cases/market/get_market_explanation.py
class GetMarketExplanation:
    def __init__(
        self,
        cache_repo: CacheRepository,
        price_repo: PriceRepository,
        llm_client: LLMClient,
    ):
        self.cache_repo = cache_repo
        self.price_repo = price_repo
        self.llm_client = llm_client

    async def execute(self, card_id: int, period: str) -> str:
        cache_key = ("llm", "explanation", str(card_id), period)

        return await self.cache_repo.get_or_compute(
            cache_key,
            compute_fn=lambda: self._generate_explanation(card_id, period),
            ttl=timedelta(hours=1),
        )

    async def _generate_explanation(self, card_id: int, period: str) -> str:
        history = await self.price_repo.get_history(card_id, period)
        signals = await self.price_repo.get_signals(card_id)
        return await self.llm_client.explain_market_movement(history, signals)
```

---

### 2. Vectorization/Embeddings System

**Current State:** SentenceTransformer embeddings for cards + one-hot encoded features stored in `CardFeatureVector` and `ListingFeatureVector`.

**Migration Plan:**

| Model | Action | Rationale |
|-------|--------|-----------|
| `CardFeatureVector` | **Keep** | Card embeddings are valuable for similarity search |
| `ListingFeatureVector` | **Remove** | Depends on Listing model we're removing |

**Schema Update:**

```python
# models/card_feature_vector.py - KEEP unchanged
class CardFeatureVector(Base):
    __tablename__ = "card_feature_vectors"

    card_id = Column(Integer, ForeignKey("cards.id"), primary_key=True)
    embedding = Column(ARRAY(Float))  # 384-dim SentenceTransformer
    one_hot_features = Column(JSONB)  # colors, types, keywords
    updated_at = Column(DateTime)
```

**Future Enhancement:** If ML on price data is needed, create `PricePatternVector` that embeds price movement patterns:

```python
# Future: models/price_pattern_vector.py
class PricePatternVector(Base):
    __tablename__ = "price_pattern_vectors"

    card_id = Column(Integer, ForeignKey("cards.id"))
    pattern_type = Column(String)  # "spike", "decline", "stable"
    embedding = Column(ARRAY(Float))
    time_window = Column(String)  # "7d", "30d"
```

---

### 3. Recommendation System (Two-Tier)

**Current State:**
- `RecommendationAgent` - Market-wide opportunities (arbitrage, undervalued cards)
- `InventoryRecommendationAgent` - Aggressive, inventory-specific recommendations

**Migration Plan:**

```
use_cases/recommendations/
├── generate_market_recommendations.py
│   # Uses: PriceRepository, MarketRepository, CacheRepository
│   # Implements: RecommendationAgent logic
│
├── generate_inventory_recommendations.py
│   # Uses: InventoryRepository, PriceRepository
│   # Implements: InventoryRecommendationAgent logic
│
└── get_recommendations.py
    # Fetches existing recommendations with filters
```

**Implementation:**

```python
# use_cases/recommendations/generate_market_recommendations.py
class GenerateMarketRecommendations:
    def __init__(
        self,
        price_repo: PriceRepository,
        market_repo: MarketRepository,
        recommendation_repo: RecommendationRepository,
        cache_repo: CacheRepository,
        redis: Redis,
    ):
        self.price_repo = price_repo
        self.market_repo = market_repo
        self.recommendation_repo = recommendation_repo
        self.cache_repo = cache_repo
        self.redis = redis

    async def execute(self) -> list[Recommendation]:
        # Query TimescaleDB aggregates for signal detection
        signals = await self.market_repo.get_momentum_signals(
            threshold=0.1,  # 10% price movement
            period="24h",
        )

        spread_opps = await self.market_repo.get_spread_opportunities(
            min_spread_pct=0.15,  # 15% spread between marketplaces
        )

        recommendations = []
        for signal in signals:
            rec = self._create_recommendation(signal)
            recommendations.append(rec)

        for opp in spread_opps:
            rec = self._create_arbitrage_recommendation(opp)
            recommendations.append(rec)

        # Save to database
        await self.recommendation_repo.bulk_insert(recommendations)

        # Invalidate cache
        await self.cache_repo.invalidate_pattern("recommendations:*")

        # Publish WebSocket update
        await self.redis.publish("channel:recommendations", json.dumps({
            "type": "recommendations_updated",
            "count": len(recommendations),
        }))

        return recommendations
```

**Celery Task Update:**

```python
# tasks/recommendations.py
@celery_app.task(queue="analytics")
async def generate_recommendations():
    async with get_db_session() as db:
        redis = await get_redis()

        use_case = GenerateMarketRecommendations(
            price_repo=PriceRepository(db),
            market_repo=MarketRepository(db),
            recommendation_repo=RecommendationRepository(db),
            cache_repo=CacheRepository(redis),
            redis=redis,
        )

        recommendations = await use_case.execute()
        return {"generated": len(recommendations)}
```

---

### 4. Signals & Metrics System

**Current State:**
- `Metric` model - Daily price aggregates per card
- `Signal` model - Momentum, volatility, spread, trend signals
- `AnalyticsAgent` computes these in Python

**Migration Plan:** Replace Python metric computation with TimescaleDB aggregate queries for dramatic performance improvement.

**TimescaleDB Aggregate Queries:**

```sql
-- Replace Python metric computation with this SQL
-- Metrics from hourly aggregates
SELECT
    card_id,
    AVG(avg_price) as avg_price,
    MIN(min_price) as min_price,
    MAX(max_price) as max_price,
    STDDEV(avg_price) as volatility,
    (LAST(avg_price, bucket) - FIRST(avg_price, bucket)) / NULLIF(FIRST(avg_price, bucket), 0) as change_pct
FROM card_prices_hourly
WHERE bucket >= NOW() - INTERVAL '7 days'
GROUP BY card_id;

-- Momentum signals
SELECT
    card_id,
    (LAST(avg_price, bucket) - FIRST(avg_price, bucket)) / NULLIF(FIRST(avg_price, bucket), 0) as momentum_7d
FROM card_prices_hourly
WHERE bucket >= NOW() - INTERVAL '7 days'
GROUP BY card_id
HAVING ABS((LAST(avg_price, bucket) - FIRST(avg_price, bucket)) / NULLIF(FIRST(avg_price, bucket), 0)) > 0.1;
```

**Repository Implementation:**

```python
# repositories/signal_repo.py
class SignalRepository:
    async def get_momentum_signals(
        self,
        period: str = "7d",
        threshold: float = 0.1,
    ) -> list[dict]:
        """Get cards with significant price momentum using TimescaleDB aggregates."""
        query = text("""
            SELECT
                card_id,
                currency,
                FIRST(avg_price, bucket) as price_start,
                LAST(avg_price, bucket) as price_end,
                (LAST(avg_price, bucket) - FIRST(avg_price, bucket)) /
                    NULLIF(FIRST(avg_price, bucket), 0) as momentum
            FROM card_prices_hourly
            WHERE bucket >= NOW() - :interval
            GROUP BY card_id, currency
            HAVING ABS((LAST(avg_price, bucket) - FIRST(avg_price, bucket)) /
                       NULLIF(FIRST(avg_price, bucket), 0)) > :threshold
            ORDER BY ABS(momentum) DESC
            LIMIT 100
        """)

        result = await self.db.execute(query, {
            "interval": PERIOD_INTERVALS[period],
            "threshold": threshold,
        })
        return [dict(row) for row in result]

    async def get_volatility_signals(
        self,
        period: str = "7d",
        min_volatility: float = 0.2,
    ) -> list[dict]:
        """Get cards with high price volatility."""
        query = text("""
            SELECT
                card_id,
                currency,
                AVG(avg_price) as avg_price,
                STDDEV(avg_price) as volatility,
                STDDEV(avg_price) / NULLIF(AVG(avg_price), 0) as volatility_pct
            FROM card_prices_hourly
            WHERE bucket >= NOW() - :interval
            GROUP BY card_id, currency
            HAVING STDDEV(avg_price) / NULLIF(AVG(avg_price), 0) > :min_volatility
            ORDER BY volatility_pct DESC
            LIMIT 100
        """)

        result = await self.db.execute(query, {
            "interval": PERIOD_INTERVALS[period],
            "min_volatility": min_volatility,
        })
        return [dict(row) for row in result]
```

**Keep Signal Model** but populate from aggregate queries instead of Python computation:

```python
# models/signal.py - KEEP, update how it's populated
class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("cards.id"))
    signal_type = Column(String)  # "momentum", "volatility", "spread", "trend"
    value = Column(Float)
    direction = Column(String)  # "up", "down", "neutral"
    strength = Column(Float)  # 0.0 to 1.0
    currency = Column(String(3))
    created_at = Column(DateTime)
```

---

### 5. Tournament & News System

**Current State:** Models exist (`Tournament`, `Decklist`, `NewsArticle`, `CardNewsMention`) but appear to be placeholder/future features.

**Decision:** **Defer to future phase** - These are independent of price data and need no changes for this overhaul.

**Keep unchanged:**
- `models/tournament.py`
- `models/decklist.py`
- `models/news.py`

**Future integration notes:**
- When implemented, tournament data could feed into recommendations (e.g., "card seeing tournament play")
- News mentions could trigger signal generation
- Both should use the new repository pattern when implemented

---

### 6. User Settings System

**Current State:** `AppSettings` key-value store for per-user configuration.

**Migration Plan:** Move to repository pattern for consistency.

```python
# repositories/settings_repo.py
class SettingsRepository:
    def __init__(self, db: AsyncSession, cache: CacheRepository):
        self.db = db
        self.cache = cache

    async def get(self, user_id: int, key: str, default: Any = None) -> Any:
        cache_key = ("settings", str(user_id), key)

        cached = await self.cache.get(*cache_key)
        if cached is not None:
            return cached

        result = await self.db.execute(
            select(AppSettings).where(
                AppSettings.user_id == user_id,
                AppSettings.key == key,
            )
        )
        setting = result.scalar_one_or_none()

        value = setting.value if setting else default
        await self.cache.set(*cache_key, value=value, ttl=timedelta(hours=1))
        return value

    async def set(self, user_id: int, key: str, value: Any) -> None:
        # Upsert setting
        stmt = insert(AppSettings).values(
            user_id=user_id,
            key=key,
            value=value,
        ).on_conflict_do_update(
            index_elements=["user_id", "key"],
            set_={"value": value, "updated_at": datetime.utcnow()},
        )
        await self.db.execute(stmt)
        await self.db.commit()

        # Invalidate cache
        await self.cache.invalidate_pattern(f"settings:{user_id}:*")
```

---

### 7. Inventory Advanced Features

**Current State:** 800+ line `inventory.py` routes with:
- Import system (CSV, plaintext parsing)
- Weighted portfolio index
- Export to multiple formats
- Valuation summaries

**Migration Plan:**

```
use_cases/inventory/
├── import_cards.py           # CSV/plaintext parsing
├── export_cards.py           # Multi-format export (CSV, JSON, TXT)
├── get_valuation_summary.py  # Portfolio stats (total value, gains/losses)
├── get_portfolio_index.py    # Weighted market index for user's collection
├── sync_prices.py            # Update current values from latest snapshots
├── add_to_inventory.py       # Single card add
├── remove_from_inventory.py  # Single card remove
└── update_inventory_item.py  # Update quantity/condition
```

**Implementation Example:**

```python
# use_cases/inventory/get_valuation_summary.py
class GetValuationSummary:
    def __init__(
        self,
        inventory_repo: InventoryRepository,
        price_repo: PriceRepository,
        cache_repo: CacheRepository,
    ):
        self.inventory_repo = inventory_repo
        self.price_repo = price_repo
        self.cache_repo = cache_repo

    async def execute(self, user_id: int, currency: str = "USD") -> dict:
        cache_key = ("inventory", "valuation", str(user_id), currency)

        return await self.cache_repo.get_or_compute(
            cache_key,
            compute_fn=lambda: self._compute_valuation(user_id, currency),
            ttl=timedelta(minutes=5),
        )

    async def _compute_valuation(self, user_id: int, currency: str) -> dict:
        items = await self.inventory_repo.get_user_inventory(user_id)

        total_value = 0
        total_cost = 0
        by_condition = defaultdict(float)

        for item in items:
            current_price = await self.price_repo.get_latest_price(
                card_id=item.card_id,
                condition=item.condition,
                currency=currency,
            )

            item_value = current_price * item.quantity
            total_value += item_value
            total_cost += (item.purchase_price or 0) * item.quantity
            by_condition[item.condition] += item_value

        return {
            "total_value": total_value,
            "total_cost": total_cost,
            "unrealized_gain": total_value - total_cost,
            "gain_pct": (total_value - total_cost) / total_cost if total_cost > 0 else 0,
            "by_condition": dict(by_condition),
            "item_count": len(items),
            "currency": currency,
        }
```

**Portfolio Index with TimescaleDB:**

```python
# use_cases/inventory/get_portfolio_index.py
class GetPortfolioIndex:
    """Calculate weighted price index for user's inventory over time."""

    async def execute(
        self,
        user_id: int,
        period: str = "30d",
        currency: str = "USD",
    ) -> list[dict]:
        # Get user's inventory with quantities (weights)
        items = await self.inventory_repo.get_user_inventory(user_id)
        card_ids = [item.card_id for item in items]
        weights = {item.card_id: item.quantity for item in items}

        # Query TimescaleDB for price history of owned cards
        query = text("""
            SELECT
                bucket,
                card_id,
                avg_price
            FROM card_prices_hourly
            WHERE card_id = ANY(:card_ids)
              AND currency = :currency
              AND bucket >= NOW() - :interval
            ORDER BY bucket
        """)

        result = await self.db.execute(query, {
            "card_ids": card_ids,
            "currency": currency,
            "interval": PERIOD_INTERVALS[period],
        })

        # Calculate weighted index per bucket
        buckets = defaultdict(lambda: {"value": 0, "weight": 0})
        for row in result:
            weight = weights.get(row.card_id, 1)
            buckets[row.bucket]["value"] += row.avg_price * weight
            buckets[row.bucket]["weight"] += weight

        return [
            {
                "time": bucket,
                "index_value": data["value"] / data["weight"] if data["weight"] > 0 else 0,
            }
            for bucket, data in sorted(buckets.items())
        ]
```

---

### 8. Dashboard System

**Current State:** Summary endpoints with in-memory caching.

**Migration Plan:**

```
use_cases/dashboard/
├── get_dashboard_summary.py   # Top gainers/losers, spread opportunities
├── get_quick_stats.py         # Card counts, recommendation counts
└── get_activity_feed.py       # Recent price changes, new recommendations
```

**Implementation:**

```python
# use_cases/dashboard/get_dashboard_summary.py
class GetDashboardSummary:
    def __init__(
        self,
        market_repo: MarketRepository,
        recommendation_repo: RecommendationRepository,
        cache_repo: CacheRepository,
    ):
        self.market_repo = market_repo
        self.recommendation_repo = recommendation_repo
        self.cache_repo = cache_repo

    async def execute(self, currency: str = "USD") -> dict:
        cache_key = ("dashboard", "summary", currency)

        return await self.cache_repo.get_or_compute(
            cache_key,
            compute_fn=lambda: self._compute_summary(currency),
            ttl=timedelta(minutes=5),
        )

    async def _compute_summary(self, currency: str) -> dict:
        # Parallel queries using asyncio.gather
        top_gainers, top_losers, spread_opps, rec_count = await asyncio.gather(
            self.market_repo.get_top_movers(currency, direction="up", limit=5),
            self.market_repo.get_top_movers(currency, direction="down", limit=5),
            self.market_repo.get_spread_opportunities(currency, limit=5),
            self.recommendation_repo.count_active(),
        )

        return {
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "spread_opportunities": spread_opps,
            "active_recommendations": rec_count,
            "currency": currency,
            "generated_at": datetime.utcnow().isoformat(),
        }
```

**WebSocket Dashboard Updates:**

Add dashboard to WebSocket subscription channels:

```python
# In websocket.py handle_message
case "dashboard":
    await manager.subscribe(connection, f"channel:dashboard:{params.get('currency', 'USD')}")
```

Publish updates when data changes:

```python
# In recommendation generation task
await redis.publish(f"channel:dashboard:{currency}", json.dumps({
    "type": "dashboard_update",
    "section": "recommendations",
}))
```

---

### Integration Timeline Update

Add these to the implementation phases:

**Phase 4 (Days 6-8):** Add to use case creation:
- `use_cases/dashboard/get_dashboard_summary.py`
- `use_cases/dashboard/get_quick_stats.py`
- `use_cases/inventory/get_valuation_summary.py`
- `use_cases/inventory/get_portfolio_index.py`

**Phase 5 (Days 9-10):** Add WebSocket channels:
- `channel:dashboard:{currency}` for dashboard updates
- `channel:inventory:user:{id}` for inventory updates
- `channel:recommendations` for new recommendation alerts

**Phase 6 (Days 11-13):** Frontend updates:
- Dashboard WebSocket integration
- Inventory valuation display
- Portfolio index chart

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| TimescaleDB over ClickHouse | Easier migration (PostgreSQL extension), familiar SQL |
| Weekly chunk interval | Balance between query performance and chunk count |
| 5-minute cache TTL | Prices update every 30 min; 5 min is fresh enough |
| Single /ws endpoint | Simpler than multiple endpoints; subscriptions handle routing |
| No mock data in production | Real data only; errors show proper error states; keep mock adapter for tests |
| Clean Architecture | Testability, maintainability, clear separation |
| Fresh database | Simplifies migration, no legacy data concerns, clean schema from start |
| Remove Listing model | Individual listing tracking unnecessary for charting; aggregates sufficient |
| Separate currency indices | Never mix USD/EUR; display in native currency only for accuracy |
| Keep services/ for externals | Adapters, LLM clients, vectorization are infrastructure, not business logic |
| Condition as enum | Consistent across all adapters with normalization mapping |
| Scryfall bulk daily | Comprehensive historical coverage without API rate limits |
| Aggregate + realtime union | Handles TimescaleDB continuous aggregate lag transparently |
| React Query + WebSocket | Cache updates via WebSocket, fallback to polling if disconnected |
| Keep CardFeatureVector | Card embeddings valuable for similarity search; remove ListingFeatureVector |
| LLM cache to Redis | Persistence across restarts; 1-hour TTL for price-contextual explanations |
| SQL-based signals | Replace Python metric computation with TimescaleDB aggregates for performance |
| Defer Tournament/News | Independent of price data; no changes needed; implement when data sources ready |
| Settings via repository | Consistent pattern with Redis cache layer for user preferences |
| Inventory use cases | Break 800+ line route file into focused use cases for maintainability |
| Dashboard WebSocket channel | Real-time updates when recommendations or market data changes |
