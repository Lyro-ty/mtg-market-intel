# Ingestion System Optimization Design

**Date:** 2026-01-02
**Status:** Approved
**Author:** Claude + User

## Overview

Optimize the ingestion system for faster database updates by implementing bulk operations, Redis caching, parallel adapter tasks, and PostgreSQL COPY for bulk imports.

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Task interface changes | Refactor (not backward-compatible) | Cleaner architecture, test as we go |
| Parallel adapter strategy | Celery Group | True parallelism, fault isolation per adapter |
| Redis caching strategy | Cache-aside with TTL | Simpler, graceful degradation if Redis down |
| Batch size | 500 default | Balance between memory and DB round-trips |

## Current vs New Architecture

### Current Flow
```
collect_price_data()
  → Scryfall (sequential)
  → CardTrader (sequential)
  → TCGPlayer (sequential)
  → Manapool (sequential)
  → Per-card DB checks + per-row inserts
```

### New Flow
```
dispatch_price_collection()
  → Celery Group:
      ├── collect_scryfall_prices.s(card_ids)
      ├── collect_cardtrader_prices.s(card_ids)
      ├── collect_tcgplayer_prices.s(card_ids)
      └── collect_manapool_prices.s()
  → Each task:
      1. Bulk fetch recent snapshots (one query)
      2. Check Redis cache for recently updated
      3. Collect prices from API
      4. Batch upsert snapshots (one statement per batch)
      5. Update Redis cache
```

## Key Components

### 1. SnapshotCache (Redis Cache-Aside)

```python
class SnapshotCache:
    """Cache-aside for recent snapshot timestamps."""

    PREFIX = "snapshot:last:"
    DEFAULT_TTL = 7200  # 2 hours (matches our update window)

    def __init__(self, redis: Redis):
        self.redis = redis

    async def get_recently_updated(
        self,
        card_ids: list[int],
        marketplace_id: int
    ) -> set[int]:
        """Returns card_ids that were updated within TTL window."""
        if not card_ids:
            return set()

        keys = [f"{self.PREFIX}{marketplace_id}:{cid}" for cid in card_ids]
        values = await self.redis.mget(keys)

        return {
            card_ids[i] for i, v in enumerate(values)
            if v is not None
        }

    async def mark_updated(
        self,
        card_ids: list[int],
        marketplace_id: int,
        ttl: int = DEFAULT_TTL
    ) -> None:
        """Mark cards as recently updated."""
        if not card_ids:
            return

        pipe = self.redis.pipeline()
        now = datetime.utcnow().isoformat()
        for cid in card_ids:
            key = f"{self.PREFIX}{marketplace_id}:{cid}"
            pipe.setex(key, ttl, now)
        await pipe.execute()
```

### 2. Bulk Fetch Recent Snapshots

```python
async def get_recent_snapshot_times(
    db: AsyncSession,
    card_ids: list[int],
    marketplace_id: int,
    since: datetime
) -> dict[int, datetime]:
    """Returns {card_id: last_snapshot_time} for cards updated since threshold."""
    result = await db.execute(
        select(
            PriceSnapshot.card_id,
            func.max(PriceSnapshot.time).label('last_time')
        )
        .where(
            PriceSnapshot.card_id.in_(card_ids),
            PriceSnapshot.marketplace_id == marketplace_id,
            PriceSnapshot.time >= since
        )
        .group_by(PriceSnapshot.card_id)
    )
    return {row.card_id: row.last_time for row in result}
```

### 3. Batch Upserts

```python
async def batch_upsert_snapshots(
    db: AsyncSession,
    snapshots: list[dict],
    batch_size: int = 500
) -> int:
    """Upsert snapshots in batches. Returns count inserted."""
    inserted = 0
    for i in range(0, len(snapshots), batch_size):
        batch = snapshots[i:i + batch_size]
        stmt = pg_insert(PriceSnapshot).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=['time', 'card_id', 'marketplace_id',
                          'condition', 'is_foil', 'language'],
            set_={
                'price': stmt.excluded.price,
                'price_low': stmt.excluded.price_low,
                'price_mid': stmt.excluded.price_mid,
                'price_high': stmt.excluded.price_high,
                'num_listings': stmt.excluded.num_listings,
            }
        )
        await db.execute(stmt)
        inserted += len(batch)
    await db.commit()
    return inserted
```

### 4. PostgreSQL COPY for Bulk Imports

```python
async def bulk_copy_snapshots(
    pool: asyncpg.Pool,
    records: list[tuple],
    columns: list[str]
) -> int:
    """Use PostgreSQL COPY for high-speed bulk inserts."""
    if not records:
        return 0

    async with pool.acquire() as conn:
        # Create temp table for staging
        await conn.execute("""
            CREATE TEMP TABLE snapshot_staging (LIKE price_snapshots INCLUDING DEFAULTS)
            ON COMMIT DROP
        """)

        # COPY into staging table
        await conn.copy_records_to_table(
            'snapshot_staging',
            records=records,
            columns=columns
        )

        # Upsert from staging to main table
        result = await conn.execute("""
            INSERT INTO price_snapshots (time, card_id, marketplace_id, condition,
                                         is_foil, language, price, currency, source)
            SELECT time, card_id, marketplace_id, condition,
                   is_foil, language, price, currency, source
            FROM snapshot_staging
            ON CONFLICT (time, card_id, marketplace_id, condition, is_foil, language)
            DO UPDATE SET price = EXCLUDED.price, source = EXCLUDED.source
        """)

        return int(result.split()[-1])
```

### 5. Parallel Task Structure

**Coordinator Task:**
```python
@celery_app.task(bind=True)
def dispatch_price_collection(self, batch_size: int = 500):
    """Coordinator: dispatch parallel adapter tasks."""

    card_ids = run_async(get_priority_card_ids(batch_size))

    job = group(
        collect_scryfall_prices.s(card_ids),
        collect_cardtrader_prices.s(card_ids),
        collect_tcgplayer_prices.s(card_ids),
        collect_manapool_prices.s(),
    )

    result = job.apply_async()

    return {
        "dispatched": len(card_ids),
        "tasks": ["scryfall", "cardtrader", "tcgplayer", "manapool"],
        "group_id": result.id,
    }
```

**Per-Adapter Task Pattern:**
```python
@celery_app.task(bind=True, max_retries=3)
def collect_scryfall_prices(self, card_ids: list[int]):
    return run_async(_collect_scryfall_async(card_ids))

async def _collect_scryfall_async(card_ids: list[int]) -> dict:
    async with async_session_maker() as db:
        cache = SnapshotCache(get_redis())
        marketplace_id = MARKETPLACE_IDS["scryfall"]

        # 1. Check Redis cache
        recently_updated = await cache.get_recently_updated(card_ids, marketplace_id)
        remaining_ids = [cid for cid in card_ids if cid not in recently_updated]

        # 2. Bulk fetch DB for any missed by cache
        threshold = datetime.utcnow() - timedelta(hours=2)
        db_recent = await get_recent_snapshot_times(db, remaining_ids, marketplace_id, threshold)
        cards_to_fetch = [cid for cid in remaining_ids if cid not in db_recent]

        # 3. Fetch from API
        adapter = ScryfallAdapter()
        snapshots = []
        for card_id in cards_to_fetch:
            price_data = await adapter.fetch_price(card_id)
            if price_data:
                snapshots.append(price_data.to_dict())

        # 4. Batch upsert
        inserted = await batch_upsert_snapshots(db, snapshots)

        # 5. Update cache
        await cache.mark_updated(cards_to_fetch, marketplace_id)

        return {"adapter": "scryfall", "fetched": len(cards_to_fetch), "inserted": inserted}
```

## Error Handling

Each adapter task handles failures independently:

```python
@celery_app.task(bind=True, max_retries=3, autoretry_for=(httpx.TimeoutException,))
def collect_tcgplayer_prices(self, card_ids: list[int]):
    try:
        return run_async(_collect_tcgplayer_async(card_ids))
    except AuthenticationError:
        logger.error("TCGPlayer auth failed - check credentials")
        return {"adapter": "tcgplayer", "error": "auth_failed", "fetched": 0}
    except RateLimitError as e:
        raise self.retry(countdown=e.retry_after or 60)
    except Exception as e:
        logger.exception(f"TCGPlayer collection failed: {e}")
        return {"adapter": "tcgplayer", "error": str(e), "fetched": 0}
```

## Migration Strategy

1. **Phase 1**: Add new utilities (`SnapshotCache`, `batch_upsert_snapshots`, `bulk_copy_snapshots`) - no behavior change
2. **Phase 2**: Add new parallel tasks alongside existing ones
3. **Phase 3**: Update Celery Beat to use new `dispatch_price_collection`
4. **Phase 4**: Monitor for 24-48 hours, then remove old tasks

## Testing Approach

- Unit tests for `SnapshotCache`, `batch_upsert_snapshots`
- Integration test: dispatch coordinator, verify all adapters called
- Load test: 5000 cards through new pipeline vs old, compare timing

## Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| DB queries per batch | O(n) | O(1) for reads, O(n/500) for writes |
| Adapter parallelism | Sequential | Fully parallel |
| Cache hit rate | 0% | ~80% for frequently updated cards |
| Bulk import speed | 1x | 10-50x with COPY |

## Files to Create/Modify

**New Files:**
- `backend/app/services/ingestion/cache.py` - SnapshotCache class
- `backend/app/services/ingestion/bulk_ops.py` - Batch upsert and COPY utilities
- `backend/app/tasks/ingestion_v2.py` - New parallel task structure

**Modified Files:**
- `backend/app/tasks/celery_app.py` - Register new tasks, update beat schedule
- `backend/app/services/pricing/bulk_import.py` - Integrate COPY for imports
- `backend/app/tasks/ingestion.py` - Deprecation markers on old tasks
