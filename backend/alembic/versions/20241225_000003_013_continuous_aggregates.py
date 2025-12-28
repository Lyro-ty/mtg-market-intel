"""Create TimescaleDB continuous aggregates for market analytics

Revision ID: 013_continuous_aggregates
Revises: 012_price_snapshots_hypertable
Create Date: 2024-12-25

This migration creates continuous aggregates that pre-compute common
analytics queries for optimal dashboard performance:

1. market_index_30min - 30-minute buckets for 7-day charts
2. market_index_hourly - Hourly buckets for 30/90-day charts
3. market_index_daily - Daily buckets for 1-year charts
4. card_prices_hourly - Per-card hourly aggregates

Continuous aggregates are automatically refreshed by TimescaleDB
background workers, providing near-real-time analytics without
impacting query performance.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '013_continuous_aggregates'
down_revision: Union[str, None] = '012_price_snapshots_hypertable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create continuous aggregates for market analytics."""

    # ==========================================================================
    # 1. Market Index 30-minute aggregate (for 7-day charts)
    # ==========================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW market_index_30min
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('30 minutes', time) AS bucket,
            currency,
            condition,
            is_foil,
            language,
            AVG(price) AS avg_price,
            AVG(price_market) AS avg_market_price,
            MIN(price_low) AS min_price,
            MAX(price_high) AS max_price,
            COUNT(DISTINCT card_id) AS card_count,
            SUM(num_listings) AS total_listings,
            SUM(total_quantity) AS total_quantity,
            SUM(price * COALESCE(total_quantity, num_listings, 1)) AS volume
        FROM price_snapshots
        WHERE price > 0
        GROUP BY bucket, currency, condition, is_foil, language
        WITH NO DATA
    """)

    # Add refresh policy: refresh every 30 minutes,
    # looking back 2 hours to catch any late-arriving data
    op.execute("""
        SELECT add_continuous_aggregate_policy('market_index_30min',
            start_offset => INTERVAL '2 hours',
            end_offset => INTERVAL '30 minutes',
            schedule_interval => INTERVAL '30 minutes',
            if_not_exists => TRUE
        )
    """)

    # ==========================================================================
    # 2. Market Index Hourly aggregate (for 30/90-day charts)
    # ==========================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW market_index_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            currency,
            condition,
            is_foil,
            language,
            AVG(price) AS avg_price,
            AVG(price_market) AS avg_market_price,
            MIN(price_low) AS min_price,
            MAX(price_high) AS max_price,
            COUNT(DISTINCT card_id) AS card_count,
            SUM(num_listings) AS total_listings,
            SUM(total_quantity) AS total_quantity,
            SUM(price * COALESCE(total_quantity, num_listings, 1)) AS volume
        FROM price_snapshots
        WHERE price > 0
        GROUP BY bucket, currency, condition, is_foil, language
        WITH NO DATA
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('market_index_hourly',
            start_offset => INTERVAL '1 day',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE
        )
    """)

    # ==========================================================================
    # 3. Market Index Daily aggregate (for 1-year charts)
    # ==========================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW market_index_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', time) AS bucket,
            currency,
            condition,
            is_foil,
            language,
            AVG(price) AS avg_price,
            AVG(price_market) AS avg_market_price,
            MIN(price_low) AS min_price,
            MAX(price_high) AS max_price,
            COUNT(DISTINCT card_id) AS card_count,
            SUM(num_listings) AS total_listings,
            SUM(total_quantity) AS total_quantity,
            SUM(price * COALESCE(total_quantity, num_listings, 1)) AS volume
        FROM price_snapshots
        WHERE price > 0
        GROUP BY bucket, currency, condition, is_foil, language
        WITH NO DATA
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('market_index_daily',
            start_offset => INTERVAL '3 days',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
    """)

    # ==========================================================================
    # 4. Per-Card Hourly aggregate (for individual card charts)
    # ==========================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW card_prices_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            card_id,
            marketplace_id,
            condition,
            is_foil,
            language,
            currency,
            AVG(price) AS avg_price,
            AVG(price_market) AS avg_market_price,
            MIN(price_low) AS min_price,
            MAX(price_high) AS max_price,
            SUM(num_listings) AS total_listings,
            SUM(total_quantity) AS total_quantity
        FROM price_snapshots
        WHERE price > 0
        GROUP BY bucket, card_id, marketplace_id, condition, is_foil, language, currency
        WITH NO DATA
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('card_prices_hourly',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE
        )
    """)

    # ==========================================================================
    # Create indexes on continuous aggregates for faster queries
    # ==========================================================================

    # Market index indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_market_index_30min_currency_bucket
        ON market_index_30min (currency, bucket DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_market_index_hourly_currency_bucket
        ON market_index_hourly (currency, bucket DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_market_index_daily_currency_bucket
        ON market_index_daily (currency, bucket DESC)
    """)

    # Card prices indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_card_prices_hourly_card_bucket
        ON card_prices_hourly (card_id, bucket DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_card_prices_hourly_card_condition
        ON card_prices_hourly (card_id, condition, bucket DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_card_prices_hourly_card_currency
        ON card_prices_hourly (card_id, currency, bucket DESC)
    """)


def downgrade() -> None:
    """Remove continuous aggregates."""

    # Remove policies first (required before dropping views)
    op.execute("""
        SELECT remove_continuous_aggregate_policy('card_prices_hourly', if_exists => TRUE)
    """)
    op.execute("""
        SELECT remove_continuous_aggregate_policy('market_index_daily', if_exists => TRUE)
    """)
    op.execute("""
        SELECT remove_continuous_aggregate_policy('market_index_hourly', if_exists => TRUE)
    """)
    op.execute("""
        SELECT remove_continuous_aggregate_policy('market_index_30min', if_exists => TRUE)
    """)

    # Drop materialized views
    op.execute("DROP MATERIALIZED VIEW IF EXISTS card_prices_hourly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS market_index_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS market_index_hourly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS market_index_30min CASCADE")
