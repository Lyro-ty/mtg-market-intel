# Troubleshooting: "No data available" in Market Index Chart

## Issue
The Global MTG Market Index chart shows "No data available" even after all fixes have been applied.

## Root Causes

The chart defaults to USD currency (to prevent currency mixing). The most common reasons for "No data available" are:

### 1. **No Price Snapshot Data Exists** (Most Common)
- Price collection tasks haven't run yet
- Celery workers aren't running
- Tasks are failing silently

### 2. **No USD Currency Data**
- Data exists but with wrong currency (EUR, TIX, or NULL)
- Old data collected before currency fix
- Marketplace structure mismatch (old "scryfall" marketplace)

### 3. **Data Outside Time Range**
- Data exists but is older than 7 days
- Price collection tasks not running frequently enough

### 4. **Data with Wrong Marketplace Structure**
- Old snapshots created with "scryfall" marketplace instead of "tcgplayer"/"cardmarket"
- This was fixed in ingestion tasks, but old data may still exist

## Diagnostic Steps

### Step 1: Check Diagnostics Endpoint

Call the diagnostics endpoint to see what data exists:

```bash
curl http://localhost:8000/api/market/diagnostics
```

Or visit in browser: `http://localhost:8000/api/market/diagnostics`

**Look for:**
- `total_snapshots`: Should be > 0
- `usd_recent_7d`: Should be > 0 for 7d chart
- `available_currencies`: Shows what currencies have data
- `chart_issue`: Explains the problem

### Step 2: Check Backend Logs

Look for these log messages:

```
"Currency not specified, defaulting to USD (data available)"
"No market index data found"
```

The logs will show:
- Total snapshots in database
- USD snapshots in range
- Available currencies
- Diagnostic message

### Step 3: Run Diagnostic Script

```bash
cd backend
python -m app.scripts.diagnose_chart_data
```

This will show:
- Total snapshots by currency
- Snapshots by marketplace
- Recent snapshots (last 7 days)
- Sample snapshots
- Test query results

## Solutions

### Solution 1: Run Price Collection Tasks

If no data exists, trigger price collection:

**Option A: Via Celery (if workers running)**
```python
from app.tasks.data_seeding import seed_comprehensive_price_data
from app.tasks.ingestion import collect_price_data

# Comprehensive seeding (current + historical)
seed_comprehensive_price_data.delay()

# Regular price collection
collect_price_data.delay()
```

**Option B: Direct Python Script**
```bash
cd backend
python -c "
import asyncio
from app.tasks.data_seeding import _seed_comprehensive_price_data_async
asyncio.run(_seed_comprehensive_price_data_async())
"
```

**Option C: Check Celery Schedule**
- Ensure `collect_price_data` runs every 5 minutes
- Ensure `seed_comprehensive_price_data` runs every 6 hours
- Check Celery workers are running: `docker logs mtg-market-intel-celery-worker`

### Solution 2: Fix Currency Mismatch

If data exists but wrong currency:

**Check what currencies exist:**
```sql
SELECT currency, COUNT(*) 
FROM price_snapshots 
WHERE snapshot_time >= NOW() - INTERVAL '7 days'
GROUP BY currency;
```

**If only EUR exists:**
- Frontend should request EUR explicitly, OR
- Backend will now try EUR if USD not available (fallback added)

**If currency is NULL or wrong:**
- Old data from before currency fix
- Need to re-collect data with fixed ingestion tasks
- Or update existing data:
```sql
UPDATE price_snapshots 
SET currency = 'USD' 
WHERE currency IS NULL 
AND marketplace_id IN (SELECT id FROM marketplaces WHERE slug = 'tcgplayer');
```

### Solution 3: Fix Marketplace Structure

If data exists with old "scryfall" marketplace:

**Check marketplace structure:**
```sql
SELECT m.slug, m.name, COUNT(ps.id) as snapshot_count
FROM marketplaces m
LEFT JOIN price_snapshots ps ON ps.marketplace_id = m.id
GROUP BY m.slug, m.name;
```

**If "scryfall" marketplace has snapshots:**
- These need to be migrated to tcgplayer/cardmarket/mtgo
- Or re-collect data with fixed ingestion tasks

### Solution 4: Check Time Range

If data exists but outside range:

**Check oldest snapshot:**
```sql
SELECT MIN(snapshot_time) as oldest, MAX(snapshot_time) as newest
FROM price_snapshots;
```

**If data is too old:**
- Run `collect_price_data` task to get recent data
- Or try a longer range (30d, 90d) in the chart

## Quick Fixes

### Fix 1: Force Data Collection

```bash
# In Docker container or local environment
docker exec -it mtg-market-intel-backend python -c "
import asyncio
from app.tasks.data_seeding import _seed_comprehensive_price_data_async
asyncio.run(_seed_comprehensive_price_data_async())
"
```

### Fix 2: Check Celery Tasks

```bash
# Check if Celery workers are running
docker ps | grep celery

# Check Celery logs
docker logs mtg-market-intel-celery-worker

# Check Celery beat (scheduler)
docker logs mtg-market-intel-celery-beat
```

### Fix 3: Manual Data Check

```bash
# Connect to database
docker exec -it mtg-market-intel-db psql -U postgres -d mtg_market_intel

# Check snapshots
SELECT COUNT(*) FROM price_snapshots;
SELECT currency, COUNT(*) FROM price_snapshots GROUP BY currency;
SELECT MIN(snapshot_time), MAX(snapshot_time) FROM price_snapshots;
```

## Expected Behavior After Fixes

1. **Data Collection Running**: 
   - `collect_price_data` runs every 5 minutes
   - Creates snapshots with USD/EUR currency
   - Uses tcgplayer/cardmarket/mtgo marketplaces

2. **Chart Query**:
   - Defaults to USD if currency not specified
   - Falls back to EUR if USD not available
   - Returns diagnostic info if no data

3. **Chart Display**:
   - Shows data if available
   - Shows "No data available" with diagnostic info if empty
   - Frontend can display diagnostic message to user

## Verification

After applying fixes, verify:

1. **Check diagnostics endpoint**: Should show `usd_recent_7d > 0`
2. **Check chart API**: `/api/market/index?range=7d` should return points
3. **Check frontend**: Chart should display data
4. **Check logs**: No "No market index data found" warnings

## Next Steps

1. Run diagnostic script to identify the exact issue
2. Check Celery workers are running
3. Trigger price collection tasks
4. Verify data exists with correct currency
5. Check chart displays correctly

