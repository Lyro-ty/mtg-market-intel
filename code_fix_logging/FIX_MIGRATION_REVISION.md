# Fix Migration Revision ID Mismatch

## Problem
The database has the old revision ID `008_add_price_snapshot_indexes` recorded, but the migration file now uses `008_price_snapshot_idx`. Alembic can't find the old revision ID.

## Solution

### Option 1: Update Database Directly (Quickest)

Connect to the database and update the revision ID:

```bash
# Connect to database
docker-compose exec db psql -U postgres -d mtg_market_intel

# Update the revision ID
UPDATE alembic_version 
SET version_num = '008_price_snapshot_idx' 
WHERE version_num = '008_add_price_snapshot_indexes';

# Verify
SELECT version_num FROM alembic_version;

# Exit
\q
```

Then run migrations:
```bash
docker-compose exec backend alembic upgrade head
```

### Option 2: Use Python Script

Run the fix script inside the backend container:

```bash
docker-compose exec backend python fix_migration_revision.py
```

Then run migrations:
```bash
docker-compose exec backend alembic upgrade head
```

### Option 3: Manual SQL Update

If you need to update multiple revisions:

```sql
-- Update revision 008
UPDATE alembic_version 
SET version_num = '008_price_snapshot_idx' 
WHERE version_num = '008_add_price_snapshot_indexes';

-- Update revision 009 (if it exists)
UPDATE alembic_version 
SET version_num = '009_price_snapshot_unique' 
WHERE version_num = '009_add_price_snapshot_unique_constraint';

-- Update revision 010 (if it exists)
UPDATE alembic_version 
SET version_num = '010_tournament_news' 
WHERE version_num = '010_add_tournament_news_tables';
```

## Verification

After updating, verify the migration chain:

```bash
# Check current revision
docker-compose exec backend alembic current

# Check migration history
docker-compose exec backend alembic history

# Run migrations
docker-compose exec backend alembic upgrade head
```

## Expected Result

After fixing, you should see:
- Current revision: `008_price_snapshot_idx` (or later)
- Migrations run successfully
- Container starts without errors

## Why This Happened

We shortened the revision IDs to fit within PostgreSQL's 32-character limit for the `version_num` column. The database still had the old longer revision ID recorded, causing a mismatch.

