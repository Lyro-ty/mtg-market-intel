"""Convert price_snapshots to TimescaleDB hypertable with new schema

Revision ID: 012_price_snapshots_hypertable
Revises: 011_enable_timescaledb
Create Date: 2024-12-25

This migration transforms the price_snapshots table into a TimescaleDB
hypertable with support for:
- Card condition tracking (MINT, NEAR_MINT, etc.)
- Language tracking (English, Japanese, etc.)
- Foil status
- Multiple price tiers (price_low, price_mid, price_high, price_market)

The hypertable is partitioned by time with 7-day chunks for optimal
time-series query performance.

IMPORTANT: This migration will migrate existing data if present.
For a fresh install, it simply creates the new schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '012_price_snapshots_hypertable'
down_revision: Union[str, None] = '011_enable_timescaledb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Transform price_snapshots to hypertable with new schema."""

    # Check if old table exists and has data
    connection = op.get_bind()
    result = connection.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'price_snapshots'
        )
    """))
    old_table_exists = result.scalar()

    if old_table_exists:
        # Check if it's already a hypertable
        result = connection.execute(sa.text("""
            SELECT EXISTS (
                SELECT FROM timescaledb_information.hypertables
                WHERE hypertable_name = 'price_snapshots'
            )
        """))
        is_hypertable = result.scalar()

        if is_hypertable:
            # Already migrated, nothing to do
            return

        # Rename old table to preserve data
        op.rename_table('price_snapshots', 'price_snapshots_old')

    # Create new price_snapshots table with full schema
    # Note: We're using raw SQL because Alembic doesn't have native
    # support for PostgreSQL enums created in a previous migration
    op.execute("""
        CREATE TABLE price_snapshots (
            time TIMESTAMPTZ NOT NULL,
            card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
            marketplace_id INTEGER NOT NULL REFERENCES marketplaces(id) ON DELETE CASCADE,

            -- Card variant identifiers
            condition card_condition NOT NULL DEFAULT 'NEAR_MINT',
            is_foil BOOLEAN NOT NULL DEFAULT FALSE,
            language card_language NOT NULL DEFAULT 'English',

            -- Price tiers
            price NUMERIC(10,2) NOT NULL,
            price_low NUMERIC(10,2),
            price_mid NUMERIC(10,2),
            price_high NUMERIC(10,2),
            price_market NUMERIC(10,2),
            currency VARCHAR(3) NOT NULL DEFAULT 'USD',

            -- Volume indicators
            num_listings INTEGER,
            total_quantity INTEGER,

            -- Unique constraint for deduplication
            UNIQUE (time, card_id, marketplace_id, condition, is_foil, language)
        )
    """)

    # Convert to hypertable with 7-day chunks
    # Using 7 days provides good balance between query performance and chunk count
    op.execute("""
        SELECT create_hypertable(
            'price_snapshots',
            'time',
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        )
    """)

    # Create indexes for common query patterns
    # Index for card price history queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_snapshots_card_time
        ON price_snapshots (card_id, time DESC)
    """)

    # Index for condition-filtered queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_snapshots_card_condition
        ON price_snapshots (card_id, condition, time DESC)
    """)

    # Index for language-filtered queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_snapshots_card_language
        ON price_snapshots (card_id, language, time DESC)
    """)

    # Index for foil-filtered queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_snapshots_card_foil
        ON price_snapshots (card_id, is_foil, time DESC)
    """)

    # Index for currency-based market queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_snapshots_currency_time
        ON price_snapshots (currency, time DESC)
    """)

    # Index for marketplace-specific queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_snapshots_marketplace_time
        ON price_snapshots (marketplace_id, time DESC)
    """)

    # Migrate data from old table if it exists
    if old_table_exists:
        op.execute("""
            INSERT INTO price_snapshots (
                time,
                card_id,
                marketplace_id,
                condition,
                is_foil,
                language,
                price,
                price_low,
                price_mid,
                price_high,
                price_market,
                currency,
                num_listings,
                total_quantity
            )
            SELECT
                snapshot_time as time,
                card_id,
                marketplace_id,
                'NEAR_MINT'::card_condition as condition,
                FALSE as is_foil,
                'English'::card_language as language,
                price,
                min_price as price_low,
                avg_price as price_mid,
                max_price as price_high,
                median_price as price_market,
                currency,
                num_listings,
                total_quantity
            FROM price_snapshots_old
            ON CONFLICT (time, card_id, marketplace_id, condition, is_foil, language)
            DO NOTHING
        """)

        # Drop old table after successful migration
        op.drop_table('price_snapshots_old')

    # Enable compression for older data (after 7 days)
    op.execute("""
        ALTER TABLE price_snapshots SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'card_id, marketplace_id, condition, is_foil, language, currency'
        )
    """)

    op.execute("""
        SELECT add_compression_policy(
            'price_snapshots',
            INTERVAL '7 days',
            if_not_exists => TRUE
        )
    """)

    # Add retention policy to automatically drop data older than 2 years
    op.execute("""
        SELECT add_retention_policy(
            'price_snapshots',
            INTERVAL '2 years',
            if_not_exists => TRUE
        )
    """)


def downgrade() -> None:
    """Convert back to regular table (loses hypertable features)."""

    # Remove policies first
    op.execute("""
        SELECT remove_retention_policy('price_snapshots', if_exists => TRUE)
    """)
    op.execute("""
        SELECT remove_compression_policy('price_snapshots', if_exists => TRUE)
    """)

    # Create backup of data
    op.execute("""
        CREATE TABLE price_snapshots_backup AS
        SELECT * FROM price_snapshots
    """)

    # Drop the hypertable (this also drops all chunks)
    op.execute("DROP TABLE price_snapshots CASCADE")

    # Create old-style table
    op.create_table(
        'price_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('marketplace_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('price_foil', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('min_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('max_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('avg_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('median_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('num_listings', sa.Integer(), nullable=True),
        sa.Column('total_quantity', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['marketplace_id'], ['marketplaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Restore data
    op.execute("""
        INSERT INTO price_snapshots (
            card_id, marketplace_id, snapshot_time, price, currency,
            min_price, max_price, avg_price, median_price,
            num_listings, total_quantity
        )
        SELECT
            card_id, marketplace_id, time, price, currency,
            price_low, price_high, price_mid, price_market,
            num_listings, total_quantity
        FROM price_snapshots_backup
    """)

    # Drop backup
    op.execute("DROP TABLE price_snapshots_backup")

    # Recreate indexes
    op.create_index('ix_snapshots_card_time', 'price_snapshots', ['card_id', 'snapshot_time'])
    op.create_index('ix_snapshots_market_time', 'price_snapshots', ['marketplace_id', 'snapshot_time'])
    op.create_index('ix_snapshots_card_market_time', 'price_snapshots', ['card_id', 'marketplace_id', 'snapshot_time'])
