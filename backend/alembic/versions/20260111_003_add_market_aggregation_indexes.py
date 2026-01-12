"""Add indexes for market aggregation queries

Optimizes the top movers and market overview queries by adding
targeted indexes that allow the database to efficiently find
the top N gainers/losers without scanning full tables.

Revision ID: add_market_aggregation_indexes
Revises: fix_trade_quote_schema_001
Create Date: 2026-01-11
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'add_market_aggregation_indexes'
down_revision: Union[str, None] = 'fix_trade_quote_schema_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add optimized indexes for market aggregation queries.

    These indexes target the specific query patterns used in:
    - /api/market/top-movers (gainers/losers by price change)
    - /api/market/overview (recent price snapshots)
    """
    # Index for top movers query - 1d price change with partial index
    # Covers: WHERE date = ? AND price_change_pct_1d IS NOT NULL
    #         ORDER BY price_change_pct_1d DESC
    # Using raw SQL for the expression index with ordering
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_metrics_date_change_1d_desc
        ON metrics_cards_daily (date, price_change_pct_1d DESC NULLS LAST)
        WHERE price_change_pct_1d IS NOT NULL
    """))

    # Index for top movers query - 7d price change with partial index
    # Covers: WHERE date = ? AND price_change_pct_7d IS NOT NULL
    #         ORDER BY price_change_pct_7d DESC
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_metrics_date_change_7d_desc
        ON metrics_cards_daily (date, price_change_pct_7d DESC NULLS LAST)
        WHERE price_change_pct_7d IS NOT NULL
    """))

    # Composite index for top movers filtering
    # Covers the common filtering pattern: date, avg_price > 0, total_listings >= 1
    # This helps with the WHERE clause filtering before ordering
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_metrics_top_movers_filter
        ON metrics_cards_daily (date, avg_price, total_listings)
        WHERE avg_price > 0 AND total_listings >= 1
    """))

    # Index for price_snapshots recent activity lookups
    # Used by market overview to count snapshots in last 24h
    # Also useful for finding cards with recent price data
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_price_snapshots_time_currency
        ON price_snapshots (time, currency)
    """))


def downgrade() -> None:
    """Remove the market aggregation indexes."""
    op.execute(text("DROP INDEX IF EXISTS ix_price_snapshots_time_currency"))
    op.execute(text("DROP INDEX IF EXISTS ix_metrics_top_movers_filter"))
    op.execute(text("DROP INDEX IF EXISTS ix_metrics_date_change_7d_desc"))
    op.execute(text("DROP INDEX IF EXISTS ix_metrics_date_change_1d_desc"))
