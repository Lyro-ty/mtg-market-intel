# Decision: Keep Composite Primary Key on price_snapshots

**Date:** 2026-01-11
**Status:** Decided - Keep Current
**Context:** Architecture remediation Task 11 analysis

## Overview

The `price_snapshots` table uses a 6-column composite key as its UNIQUE constraint:
- `time` - Timestamp of the price observation (hypertable partition key)
- `card_id` - Foreign key to the card
- `marketplace_id` - Foreign key to the marketplace
- `condition` - Card condition (MINT, NEAR_MINT, LIGHTLY_PLAYED, etc.)
- `is_foil` - Whether this is a foil variant
- `language` - Card language (English, Japanese, German, etc.)

This natural key uniquely identifies a specific price observation for a card variant on a marketplace at a point in time.

## Analysis

### Why the Composite Key Works Well

1. **Natural Key Semantics**: The composite key represents the business reality - there can only be one price for a specific card variant (condition/foil/language) on a specific marketplace at a specific time.

2. **TimescaleDB Optimization**: As a hypertable with `time` as the partition key, TimescaleDB efficiently handles the composite key:
   - Chunk exclusion: Writes only touch relevant 7-day chunks
   - Compression: Uses `compress_segmentby = 'card_id, marketplace_id, condition, is_foil, language, currency'` for optimal compression ratios
   - Continuous aggregates: Pre-computed views handle analytical queries efficiently

3. **Upsert Efficiency**: The ON CONFLICT clause works directly with the natural key columns, enabling efficient upserts without separate lookup queries:
   ```sql
   ON CONFLICT (time, card_id, marketplace_id, condition, is_foil, language)
   DO UPDATE SET price = EXCLUDED.price, ...
   ```

4. **Data Integrity**: Duplicate price observations are impossible at the database level - no application logic required.

5. **No ORM Overhead**: No surrogate ID generation or management needed.

### Existing Infrastructure

The composite key is deeply integrated into the codebase:

- **`bulk_ops.py`**: Uses `SNAPSHOT_PK_COLUMNS` for batch upserts and PostgreSQL COPY operations
- **`price_repo.py`**: All insert methods use ON CONFLICT with the composite key
- **Migrations**: Hypertable created with UNIQUE constraint on these columns
- **Tests**: `test_composite_keys.py` validates composite key behavior extensively

### Risks of Changing to Surrogate Key

1. **Migration Complexity**: Would require:
   - Adding new `id` column to existing hypertable (TimescaleDB restrictions apply)
   - Updating all ON CONFLICT clauses across the codebase
   - Modifying continuous aggregate definitions
   - Re-indexing the table

2. **Increased Write Overhead**: Surrogate key would require:
   - ID generation for each insert
   - Separate unique constraint for deduplication
   - Additional index maintenance

3. **Breaking Changes**: Would break:
   - All existing upsert logic
   - Bulk import operations
   - Any external integrations

## Decision

**Keep the composite primary key** because:

1. **Natural key is semantically correct** for price time-series data
2. **TimescaleDB handles composite keys efficiently** with chunk exclusion and compression
3. **Change risk outweighs marginal benefit** - existing infrastructure works well
4. **No performance issues observed** in current usage patterns

## Monitoring Recommendations

If performance concerns arise in the future, monitor:

1. **Write latency**: Alert if average insert time exceeds 100ms
2. **Index bloat**: Review quarterly using `pgstattuple` extension
3. **Chunk size**: Verify 7-day chunks remain appropriately sized
4. **Compression ratio**: Monitor storage efficiency over time

## Alternatives Considered

### Option A: Add Surrogate ID as Additional Column
Add an auto-incrementing `id` column while keeping the composite unique constraint. This would provide an optional surrogate key for any future ORM requirements without breaking existing functionality.

**Rejected because**: No current need, adds complexity without benefit.

### Option B: Convert to Surrogate Primary Key
Replace composite key with single `id` column and move uniqueness to a separate constraint.

**Rejected because**: High migration risk, breaks existing code, no performance benefit for TimescaleDB hypertables.

## References

- TimescaleDB documentation on hypertable best practices
- Migration: `012_price_snapshots_hypertable.py`
- Integration tests: `test_composite_keys.py`
- Bulk operations: `bulk_ops.py`
