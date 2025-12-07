"""Add indexes for price snapshot chart queries

Revision ID: 008_add_price_snapshot_indexes
Revises: 007_fix_profit_pct
Create Date: 2024-12-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_add_price_snapshot_indexes'
down_revision: Union[str, None] = '007_fix_profit_pct'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add index on currency for filtering by currency in chart queries
    # This is critical for preventing currency mixing issues
    op.create_index(
        'ix_price_snapshots_currency',
        'price_snapshots',
        ['currency'],
        unique=False
    )
    
    # Add composite index on (snapshot_time, currency) for efficient time-range queries with currency filtering
    # This is the most common query pattern for chart endpoints
    op.create_index(
        'ix_price_snapshots_time_currency',
        'price_snapshots',
        ['snapshot_time', 'currency'],
        unique=False
    )
    
    # Add composite index on (card_id, snapshot_time, currency) for inventory chart queries
    # This optimizes queries that filter by specific cards, time range, and currency
    op.create_index(
        'ix_price_snapshots_card_time_currency',
        'price_snapshots',
        ['card_id', 'snapshot_time', 'currency'],
        unique=False
    )


def downgrade() -> None:
    # Remove indexes in reverse order
    op.drop_index('ix_price_snapshots_card_time_currency', table_name='price_snapshots')
    op.drop_index('ix_price_snapshots_time_currency', table_name='price_snapshots')
    op.drop_index('ix_price_snapshots_currency', table_name='price_snapshots')

