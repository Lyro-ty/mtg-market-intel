# Running Migrations - Instructions

## Issue
When running `alembic upgrade head` from the host system, it uses the system Python which may have an older SQLAlchemy version that doesn't include `async_sessionmaker`.

## Solutions

### Option 1: Run Migrations Inside Docker (Recommended)

Run migrations inside the Docker container where the correct dependencies are installed:

```bash
docker-compose exec backend alembic upgrade head
```

Or if the container isn't running:

```bash
docker-compose run --rm backend alembic upgrade head
```

### Option 2: Use Docker Container Shell

Get a shell in the backend container and run migrations:

```bash
docker-compose exec backend bash
# Inside container:
alembic upgrade head
```

### Option 3: Fix Host System Python (If Needed)

If you need to run migrations from the host, ensure you're using the correct Python environment:

```bash
# Activate virtual environment
source venv/bin/activate  # or your venv path

# Install correct SQLAlchemy version
pip install 'sqlalchemy[asyncio]>=2.0.0'

# Run migrations
alembic upgrade head
```

### Option 4: Rebuild Docker Containers

If the Docker container itself has the wrong SQLAlchemy version, rebuild:

```bash
docker-compose build --no-cache backend
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

## Verification

After running migrations, verify they succeeded:

```bash
# Check migration status
docker-compose exec backend alembic current

# Check database tables
docker-compose exec db psql -U postgres -d mtg_market_intel -c "\dt"
```

## Expected Migration Chain

The migrations should run in this order:
1. `001` - Initial schema
2. `002` - Inventory tables
3. `003_add_user_auth` - User authentication
4. `004_user_settings` - User settings
5. `005_feature_vectors` - Feature vectors
6. `006_feature_vectors_ts` - Feature vector timestamps
7. `007_fix_profit_pct` - Profit percentage fix
8. `008_price_snapshot_idx` - Price snapshot indexes
9. `009_price_snapshot_unique` - Price snapshot unique constraint
10. `010_tournament_news` - Tournament and news tables

## Troubleshooting

### Error: "cannot import name 'async_sessionmaker'"

**Cause**: System Python has old SQLAlchemy version

**Fix**: Run migrations inside Docker container (Option 1)

### Error: "value too long for type character varying(32)"

**Cause**: Migration revision ID too long (already fixed)

**Fix**: The revision IDs have been shortened. If you still see this error, you may need to manually update the database:

```sql
-- If migration 008 was already applied with old ID
UPDATE alembic_version 
SET version_num = '008_price_snapshot_idx' 
WHERE version_num = '008_add_price_snapshot_indexes';
```

### Error: Container won't start

**Cause**: Import error during container startup

**Fix**: 
1. Rebuild container: `docker-compose build --no-cache backend`
2. Check requirements.txt has correct SQLAlchemy version
3. Check Docker logs: `docker-compose logs backend`

## Quick Start

For the fastest resolution, use:

```bash
# Rebuild and start containers
docker-compose up -d --build

# Run migrations inside container
docker-compose exec backend alembic upgrade head

# Verify
docker-compose exec backend alembic current
```

