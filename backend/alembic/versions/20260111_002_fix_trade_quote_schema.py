"""fix trade quote schema - add missing columns

Revision ID: fix_trade_quote_schema_001
Revises: drop_listing_001
Create Date: 2026-01-11 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fix_trade_quote_schema_001'
down_revision: Union[str, None] = 'drop_listing_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add name column to trade_quotes
    op.add_column('trade_quotes', sa.Column('name', sa.String(100), nullable=True))

    # Add updated_at to trade_quote_items (missing from original migration)
    op.add_column('trade_quote_items', sa.Column(
        'updated_at',
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False
    ))

    # Add new columns to trade_quote_submissions
    op.add_column('trade_quote_submissions', sa.Column('user_message', sa.Text(), nullable=True))
    op.add_column('trade_quote_submissions', sa.Column('store_message', sa.Text(), nullable=True))
    op.add_column('trade_quote_submissions', sa.Column(
        'submitted_at',
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False
    ))
    op.add_column('trade_quote_submissions', sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True))

    # Drop old columns from trade_quote_submissions
    op.drop_column('trade_quote_submissions', 'counter_note')
    op.drop_column('trade_quote_submissions', 'store_responded_at')
    op.drop_column('trade_quote_submissions', 'user_responded_at')


def downgrade() -> None:
    # Restore old columns
    op.add_column('trade_quote_submissions', sa.Column('counter_note', sa.Text(), nullable=True))
    op.add_column('trade_quote_submissions', sa.Column('store_responded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('trade_quote_submissions', sa.Column('user_responded_at', sa.DateTime(timezone=True), nullable=True))

    # Drop new columns
    op.drop_column('trade_quote_submissions', 'responded_at')
    op.drop_column('trade_quote_submissions', 'submitted_at')
    op.drop_column('trade_quote_submissions', 'store_message')
    op.drop_column('trade_quote_submissions', 'user_message')

    # Drop updated_at from trade_quote_items
    op.drop_column('trade_quote_items', 'updated_at')

    # Drop name column
    op.drop_column('trade_quotes', 'name')
