# Phase 1: Critical Bug Fixes - COMPLETE ✅

## Summary
All critical bugs in the ingestion/RAG pipeline have been fixed. The system is now more robust, memory-efficient, and data-integrity focused.

## Fixes Implemented

### 1. ✅ CardTrader Currency Consistency
**Problem**: CardTrader marketplace was created with EUR in some places, USD in others, causing data to not appear in charts.

**Fix**: 
- Standardized CardTrader marketplace creation to use USD currency
- Updated `data_seeding.py` to use USD instead of EUR

**Files Changed**:
- `backend/app/tasks/data_seeding.py`

### 2. ✅ Removed Synthetic Backfill Data
**Problem**: `_backfill_historical_snapshots_for_charting` created fake historical data using current prices, contaminating ML training data.

**Fix**:
- Removed all 4 calls to synthetic backfill function
- Added comments noting that historical data should come from MTGJSON
- Chart endpoints already have interpolation for gaps, so charts still work

**Files Changed**:
- `backend/app/tasks/ingestion.py`

### 3. ✅ Fixed Race Conditions
**Problem**: Multiple tasks (every 2min, 5min, 6hrs) could create duplicate snapshots due to check-then-insert pattern.

**Fix**:
- Created migration `009_add_price_snapshot_unique_constraint.py` with unique constraint on (card_id, marketplace_id, snapshot_time)
- Created `_upsert_price_snapshot()` helper function using PostgreSQL `ON CONFLICT DO UPDATE`
- Updated all snapshot creation code to use upsert instead of check-then-insert
- Migration automatically removes existing duplicates before adding constraint

**Files Changed**:
- `backend/alembic/versions/20241205_000001_009_add_price_snapshot_unique_constraint.py` (new)
- `backend/app/tasks/ingestion.py`

### 4. ✅ Fixed Scryfall Bulk Data Memory Issues
**Problem**: Entire JSON file (100MB+) loaded into memory, causing OOM errors.

**Fix**:
- Replaced memory-intensive JSON parsing with ijson streaming parser
- Downloads to temp file, then streams parse using `ijson.items()`
- Processes cards in batches of 1000 without loading entire file
- Filters to physical cards only (excludes MTGO/digital cards)
- Removes temp file after processing

**Files Changed**:
- `backend/app/tasks/data_seeding.py`

### 5. ✅ Fixed Vectorization Bugs
**Problem**: 
- Marketplace ID used modulo, causing collisions and information loss
- Price normalization capped at $22k, losing information for expensive cards

**Fix**:
- Increased `marketplace_dim` from 5 to 20 to reduce collisions
- Changed marketplace mapping from simple modulo to hash-based approach
- Improved price normalization: `log(1+price) / log(1+100000)` to handle cards up to $100k
- Color parsing already handled both JSON string and list formats correctly

**Files Changed**:
- `backend/app/services/vectorization/service.py`

## Migration Required

**Important**: Run the new migration to add the unique constraint:
```bash
alembic upgrade head
```

This will:
1. Remove any existing duplicate snapshots
2. Add unique constraint on (card_id, marketplace_id, snapshot_time)

## Testing Recommendations

1. **CardTrader Charts**: Verify CardTrader data appears in market index charts
2. **No Synthetic Data**: Check that price snapshots have real timestamps (not backfilled)
3. **No Duplicates**: Verify no duplicate snapshots exist after migration
4. **Memory Usage**: Monitor bulk data processing - should use less memory
5. **Vectorization**: Test with expensive cards (>$22k) - should normalize correctly

## Next Steps

Phase 1 is complete! Ready to proceed with:
- **Phase 2**: Add Manapool API, TCGPlayer listings, tournament/news sources
- **Phase 3**: Expand vectorization (price history, signals, popularity)
- **Phase 4**: Implement RAG retrieval with pgvector
- **Phase 5**: Add semantic search endpoints

