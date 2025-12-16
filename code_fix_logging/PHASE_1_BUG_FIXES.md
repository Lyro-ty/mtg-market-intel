# Phase 1: Critical Bug Fixes

## Issues Identified & Fixes

### 1. CardTrader Not Showing in Charts ✅ FIXED
**Problem**: 
- CardTrader marketplace created with inconsistent currency (USD in some places, EUR in others)
- Chart queries filter by currency, so mismatched currency = no data shown

**Fix**:
- Standardize CardTrader to use USD currency (matches adapter default)
- Ensure all CardTrader snapshots use USD currency
- Verify CardTrader adapter returns USD prices correctly

### 2. Synthetic Backfill Data ✅ TO REMOVE
**Problem**:
- `_backfill_historical_snapshots_for_charting` creates fake historical data
- Contaminates ML training data
- Should use real MTGJSON data instead

**Fix**:
- Remove synthetic backfill function
- Ensure MTGJSON 30-day history is properly imported
- Use interpolation in chart endpoints for gaps (already implemented)

### 3. Race Conditions in Price Collection ✅ TO FIX
**Problem**:
- Multiple tasks can run simultaneously (every 2min, 5min, 6hrs)
- Check-then-insert pattern allows duplicates
- No database-level constraints

**Fix**:
- Add unique constraint on (card_id, marketplace_id, snapshot_time)
- Use PostgreSQL upsert (ON CONFLICT) instead of check-then-insert
- Add proper transaction boundaries

### 4. Scryfall Bulk Data Memory Issue ✅ TO FIX
**Problem**:
- Loads entire JSON file into memory
- Can OOM on large files (100MB+)
- TODO comment mentions ijson but not implemented

**Fix**:
- Use ijson for streaming JSON parsing
- Process cards in batches without loading entire file
- Filter to physical cards only (exclude MTGO/digital)

### 5. Vectorization Bugs ✅ TO FIX
**Problems**:
- Marketplace ID uses modulo: `marketplace_id % marketplace_dim` (loses information)
- Color parsing inconsistent (JSON string vs list)
- Price normalization caps at $22k (loses info for expensive cards)

**Fixes**:
- Remove modulo, use proper marketplace mapping
- Fix color parsing to handle both formats
- Improve price normalization for high-value cards

### 6. Missing Transaction Boundaries ✅ TO FIX
**Problem**:
- Some operations flush but don't commit until end
- If process crashes, partial data lost

**Fix**:
- Add proper commit points in batch processing
- Use savepoints for error recovery

## Implementation Order

1. Fix CardTrader currency consistency (quick win)
2. Remove synthetic backfill
3. Fix race conditions with unique constraints
4. Fix Scryfall bulk streaming
5. Fix vectorization bugs
6. Add transaction boundaries

