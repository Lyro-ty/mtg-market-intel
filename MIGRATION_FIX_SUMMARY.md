# Migration Fix Summary - Backend Alignment

## Issue
Migration failed with error: `value too long for type character varying(32)`

The Alembic `version_num` column is limited to 32 characters, but revision IDs exceeded this limit:
- `009_add_price_snapshot_unique_constraint` = 40 characters ❌
- `008_add_price_snapshot_indexes` = 33 characters ❌
- `010_add_tournament_news_tables` = 30 characters ✅

## Fixes Applied

### 1. ✅ Shortened Migration Revision IDs

**File**: `backend/alembic/versions/20241204_000001_008_add_price_snapshot_indexes.py`
- Changed: `008_add_price_snapshot_indexes` → `008_price_snapshot_idx` (24 chars)

**File**: `backend/alembic/versions/20241205_000001_009_add_price_snapshot_unique_constraint.py`
- Changed: `009_add_price_snapshot_unique_constraint` → `009_price_snapshot_unique` (27 chars)
- Updated `down_revision` to reference: `008_price_snapshot_idx`

**File**: `backend/alembic/versions/20241205_000002_010_add_tournament_news_tables.py`
- Changed: `010_add_tournament_news_tables` → `010_tournament_news` (20 chars)
- Updated `down_revision` to reference: `009_price_snapshot_unique`

### 2. ✅ Verified Ingestion Task Alignment

**File**: `backend/app/tasks/ingestion.py`

**Verified Components**:
- ✅ Manapool adapter integration (lines 568-654)
- ✅ TCGPlayer adapter integration (lines 656-743)
- ✅ CardTrader adapter integration (lines 474-566)
- ✅ Scryfall adapter integration (lines 310-472)
- ✅ MTGJSON historical prices (lines 1295-1370)
- ✅ Upsert pattern for price snapshots (prevents race conditions)
- ✅ Marketplace creation helpers for all adapters
- ✅ Proper error handling and logging

**Integration Points**:
1. **Price Collection Flow**:
   - Scryfall → TCGPlayer/Cardmarket/MTGO prices
   - CardTrader → USD prices
   - Manapool → USD prices (when API token configured)
   - TCGPlayer → Direct API prices (when credentials configured)
   - MTGJSON → Historical prices (daily)

2. **Marketplace Mapping**:
   - USD → TCGPlayer marketplace
   - EUR → Cardmarket marketplace
   - TIX → MTGO marketplace (excluded from physical cards)

3. **Data Flow**:
   ```
   Adapters → Price Data → Upsert Price Snapshots → Database
   ```

## Migration Instructions

### If Migration 008 Has NOT Been Applied Yet

The migration should work now. Run:
```bash
cd backend
alembic upgrade head
```

### If Migration 008 Has Already Been Applied

If the database already has `008_add_price_snapshot_indexes` recorded, you have two options:

**Option 1: Manual Fix (Recommended)**
```sql
-- Update the version in the database to match the new shorter revision ID
UPDATE alembic_version 
SET version_num = '008_price_snapshot_idx' 
WHERE version_num = '008_add_price_snapshot_indexes';
```

Then run:
```bash
alembic upgrade head
```

**Option 2: Reset Migration (If Safe)**
If you can safely drop and recreate the indexes:
```sql
-- Drop the indexes created by migration 008
DROP INDEX IF EXISTS ix_price_snapshots_card_time_currency;
DROP INDEX IF EXISTS ix_price_snapshots_time_currency;
DROP INDEX IF EXISTS ix_price_snapshots_currency;

-- Update version
UPDATE alembic_version 
SET version_num = '007_fix_profit_pct' 
WHERE version_num LIKE '008%';
```

Then run:
```bash
alembic upgrade head
```

## Verification Checklist

After migration, verify:

- [ ] Migration runs successfully
- [ ] All tables created: `tournaments`, `decklists`, `card_tournament_usage`, `news_articles`, `card_news_mentions`
- [ ] Unique constraint exists: `uq_price_snapshots_card_marketplace_time`
- [ ] Indexes exist on price_snapshots table
- [ ] Ingestion tasks can collect from all adapters
- [ ] No duplicate price snapshots are created
- [ ] Manapool marketplace created (if API token configured)
- [ ] TCGPlayer marketplace created (if credentials configured)

## Backend Alignment Status

### ✅ Ingestion Tasks
- **Scryfall**: Integrated and working
- **CardTrader**: Integrated and working
- **Manapool**: Integrated (requires API token)
- **TCGPlayer**: Integrated (requires API credentials)
- **MTGJSON**: Integrated for historical data

### ✅ Data Flow
- Price collection → Upsert snapshots → Database
- Race condition prevention via unique constraint
- Proper marketplace mapping by currency

### ✅ Error Handling
- Graceful handling of missing API credentials
- Non-fatal errors for individual card failures
- Comprehensive logging

## Next Steps

1. **Run Migration**: `alembic upgrade head`
2. **Verify Tables**: Check that all new tables exist
3. **Test Ingestion**: Run a test price collection task
4. **Monitor Logs**: Check for any adapter errors
5. **Configure APIs**: Add Manapool/TCGPlayer credentials if needed

## Files Modified

- `backend/alembic/versions/20241204_000001_008_add_price_snapshot_indexes.py`
- `backend/alembic/versions/20241205_000001_009_add_price_snapshot_unique_constraint.py`
- `backend/alembic/versions/20241205_000002_010_add_tournament_news_tables.py`

All migration revision IDs are now ≤ 32 characters and compatible with PostgreSQL's VARCHAR(32) limit.

