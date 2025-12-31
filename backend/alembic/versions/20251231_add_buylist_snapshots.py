"""Add buylist_snapshots table for tracking vendor buylist prices.

Revision ID: add_buylist_snapshots
Revises: 20251231_041900_add_news_tables
Create Date: 2025-12-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_buylist_snapshots'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'buylist_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('vendor', sa.String(length=50), nullable=False),
        sa.Column('condition', sa.String(length=20), nullable=False, server_default='NM'),
        sa.Column('is_foil', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('credit_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index('ix_buylist_snapshots_time', 'buylist_snapshots', ['time'], unique=False)
    op.create_index('ix_buylist_snapshots_card_id', 'buylist_snapshots', ['card_id'], unique=False)
    op.create_index('ix_buylist_snapshots_vendor', 'buylist_snapshots', ['vendor'], unique=False)

    # Composite index for finding latest buylist by card+vendor
    op.create_index(
        'ix_buylist_snapshots_card_vendor_time',
        'buylist_snapshots',
        ['card_id', 'vendor', 'time'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_buylist_snapshots_card_vendor_time', table_name='buylist_snapshots')
    op.drop_index('ix_buylist_snapshots_vendor', table_name='buylist_snapshots')
    op.drop_index('ix_buylist_snapshots_card_id', table_name='buylist_snapshots')
    op.drop_index('ix_buylist_snapshots_time', table_name='buylist_snapshots')
    op.drop_table('buylist_snapshots')
