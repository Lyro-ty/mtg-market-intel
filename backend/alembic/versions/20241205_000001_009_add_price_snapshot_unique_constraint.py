"""Add unique constraint to prevent duplicate price snapshots

Revision ID: 009_add_price_snapshot_unique_constraint
Revises: 008_add_price_snapshot_indexes
Create Date: 2024-12-05

This migration adds a unique constraint on (card_id, marketplace_id, snapshot_time)
to prevent race conditions where multiple tasks create duplicate snapshots.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_add_price_snapshot_unique_constraint'
down_revision: Union[str, None] = '008_add_price_snapshot_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, remove any existing duplicates (keep the most recent one)
    # This is safe to run even if no duplicates exist
    op.execute("""
        DELETE FROM price_snapshots ps1
        USING price_snapshots ps2
        WHERE ps1.id < ps2.id
          AND ps1.card_id = ps2.card_id
          AND ps1.marketplace_id = ps2.marketplace_id
          AND ps1.snapshot_time = ps2.snapshot_time;
    """)
    
    # Add unique constraint to prevent future duplicates
    # This prevents race conditions where multiple tasks try to create the same snapshot
    op.create_unique_constraint(
        'uq_price_snapshots_card_marketplace_time',
        'price_snapshots',
        ['card_id', 'marketplace_id', 'snapshot_time']
    )


def downgrade() -> None:
    # Remove unique constraint
    op.drop_constraint(
        'uq_price_snapshots_card_marketplace_time',
        'price_snapshots',
        type_='unique'
    )

