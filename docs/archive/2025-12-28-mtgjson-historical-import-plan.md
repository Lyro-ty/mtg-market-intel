# MTGJSON Historical Price Import Fix

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the MTGJSON historical import script to match current PriceSnapshot model and enable automatic execution on startup.

**Architecture:** Update `seed_mtgjson_historical.py` to use correct field names (`time` not `snapshot_time`, separate foil snapshots with `is_foil=True`), add UUID→Scryfall→CardID mapping, and configure docker-compose to run the startup script.

**Tech Stack:** Python, SQLAlchemy, PostgreSQL, Docker Compose

---

## Task 1: Fix PriceSnapshot Field Names in Seed Script

**Files:**
- Modify: `backend/app/scripts/seed_mtgjson_historical.py:190-213`

**Step 1: Update the snapshot creation code**

Find lines 190-213 where `PriceSnapshot` is created and fix field names:

```python
# OLD (wrong fields):
snapshot = PriceSnapshot(
    card_id=card.id,
    marketplace_id=marketplace.id,
    snapshot_time=price_data.snapshot_time,  # WRONG
    price=price_data.price,
    currency=price_data.currency,
    price_foil=price_data.price_foil,  # WRONG
)

# NEW (correct fields):
snapshot = PriceSnapshot(
    time=price_data.snapshot_time,  # Correct field name
    card_id=card.id,
    marketplace_id=marketplace.id,
    condition="NEAR_MINT",  # Required field
    is_foil=False,  # Separate foil/non-foil
    language="English",  # Required field
    price=price_data.price,
    currency=price_data.currency,
    source="mtgjson",  # Track data source
)
```

**Step 2: Handle foil prices as separate snapshots**

After creating the normal snapshot, add foil if available:

```python
# If foil price exists, create separate foil snapshot
if price_data.price_foil and price_data.price_foil > 0:
    foil_snapshot = PriceSnapshot(
        time=price_data.snapshot_time,
        card_id=card.id,
        marketplace_id=marketplace.id,
        condition="NEAR_MINT",
        is_foil=True,
        language="English",
        price=price_data.price_foil,
        currency=price_data.currency,
        source="mtgjson",
    )
    db.add(foil_snapshot)
    stats["snapshots_created"] += 1
```

**Step 3: Update the existing check query**

Fix the duplicate check to include all composite key fields:

```python
# Check if snapshot already exists (full composite key)
existing_query = select(PriceSnapshot).where(
    and_(
        PriceSnapshot.card_id == card.id,
        PriceSnapshot.marketplace_id == marketplace.id,
        PriceSnapshot.time == price_data.snapshot_time,
        PriceSnapshot.condition == "NEAR_MINT",
        PriceSnapshot.is_foil == False,
        PriceSnapshot.language == "English",
    )
)
```

**Step 4: Verify syntax**

Run: `python3 -m py_compile backend/app/scripts/seed_mtgjson_historical.py`
Expected: No output (success)

**Step 5: Commit**

```bash
git add backend/app/scripts/seed_mtgjson_historical.py
git commit -m "fix: update seed_mtgjson_historical to match current PriceSnapshot model"
```

---

## Task 2: Use Bulk Insert with ON CONFLICT for Performance

**Files:**
- Modify: `backend/app/scripts/seed_mtgjson_historical.py`

**Step 1: Replace individual inserts with batch upsert**

Add import at top:
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert
```

**Step 2: Collect snapshots in batch and insert at once**

Replace the card-by-card insert with batch collection:

```python
# Collect all snapshots for batch insert
snapshot_records = []

for price_data in historical_prices:
    if not price_data or price_data.price <= 0:
        continue

    # ... marketplace lookup code ...

    # Add normal price record
    snapshot_records.append({
        "time": price_data.snapshot_time,
        "card_id": card.id,
        "marketplace_id": marketplace.id,
        "condition": "NEAR_MINT",
        "is_foil": False,
        "language": "English",
        "price": float(price_data.price),
        "currency": price_data.currency,
        "source": "mtgjson",
    })

    # Add foil price record if available
    if price_data.price_foil and price_data.price_foil > 0:
        snapshot_records.append({
            "time": price_data.snapshot_time,
            "card_id": card.id,
            "marketplace_id": marketplace.id,
            "condition": "NEAR_MINT",
            "is_foil": True,
            "language": "English",
            "price": float(price_data.price_foil),
            "currency": price_data.currency,
            "source": "mtgjson",
        })

# Batch insert with ON CONFLICT DO NOTHING
if snapshot_records:
    stmt = pg_insert(PriceSnapshot).values(snapshot_records)
    stmt = stmt.on_conflict_do_nothing()
    await db.execute(stmt)
    stats["snapshots_created"] += len(snapshot_records)
```

**Step 3: Verify syntax**

Run: `python3 -m py_compile backend/app/scripts/seed_mtgjson_historical.py`
Expected: No output (success)

**Step 4: Commit**

```bash
git add backend/app/scripts/seed_mtgjson_historical.py
git commit -m "perf: use bulk insert for MTGJSON historical data"
```

---

## Task 3: Update Docker Compose to Use Startup Script

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Add command override for backend service**

Find the backend service section and add command:

```yaml
backend:
  build:
    context: ./backend
    dockerfile: Dockerfile
  container_name: ${COMPOSE_PROJECT_NAME:-dualcaster}-backend
  command: ["python", "-m", "app.scripts.startup_with_backfill"]  # ADD THIS LINE
  restart: ${RESTART_POLICY:-always}
```

**Step 2: Verify docker-compose syntax**

Run: `docker compose config --quiet`
Expected: No output (valid config)

**Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: use startup script with MTGJSON backfill on container start"
```

---

## Task 4: Increase Historical Days from 30 to 90

**Files:**
- Modify: `backend/app/scripts/seed_mtgjson_historical.py`
- Modify: `backend/app/scripts/startup_with_backfill.py`

**Step 1: Update default days in seed script**

Change the default from 30 to 90:
```python
async def seed_mtgjson_historical(
    card_limit: int | None = None,
    skip_existing: bool = False,
    days: int = 90,  # Changed from 30 to 90
    batch_size: int = 50,
) -> dict:
```

**Step 2: Update startup script call**

In `startup_with_backfill.py`, update the backfill call:
```python
stats = await asyncio.wait_for(
    seed_mtgjson_historical(
        card_limit=card_limit,
        skip_existing=True,
        days=90,  # Changed from 30 to 90
        batch_size=50,
    ),
    timeout=timeout_minutes * 60
)
```

**Step 3: Update docstrings**

Update docstrings to reflect 90-day default.

**Step 4: Verify syntax**

Run: `python3 -m py_compile backend/app/scripts/seed_mtgjson_historical.py backend/app/scripts/startup_with_backfill.py`
Expected: No output

**Step 5: Commit**

```bash
git add backend/app/scripts/seed_mtgjson_historical.py backend/app/scripts/startup_with_backfill.py
git commit -m "feat: increase MTGJSON historical data from 30 to 90 days"
```

---

## Task 5: Test the Import Locally

**Step 1: Rebuild backend container**

```bash
docker compose up -d --build backend
```

**Step 2: Check logs for startup script execution**

```bash
docker compose logs -f backend | head -100
```

Expected: Should see "Starting MTGJSON historical data backfill" and progress logs.

**Step 3: Verify snapshots were created**

```bash
docker compose exec db psql -U dualcaster_user -d dualcaster_deals -c "
SELECT source, COUNT(*) as count, MIN(time) as oldest, MAX(time) as newest
FROM price_snapshots
GROUP BY source
ORDER BY count DESC;
"
```

Expected: Shows `mtgjson` source with historical data spanning ~90 days.

**Step 4: Push changes**

```bash
git push origin main
```

---

## Summary

After completing all tasks:

1. **Fixed field names** - Uses `time`, `is_foil`, `condition`, `language`, `source`
2. **Separate foil snapshots** - Foil prices stored as `is_foil=True` records
3. **Bulk inserts** - Uses `ON CONFLICT DO NOTHING` for performance
4. **90 days of history** - MTGJSON provides full 90-day window
5. **Automatic on startup** - Runs via `startup_with_backfill.py` on container start

When deployed to prod, the container will:
1. Run migrations
2. Seed basic data
3. Sync MTG sets
4. **Backfill 90 days of MTGJSON historical prices** (5-minute timeout on startup, background task continues)
5. Start the API server
