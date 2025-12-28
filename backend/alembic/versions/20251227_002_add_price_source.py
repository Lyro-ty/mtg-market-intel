"""Add source column to price_snapshots

Revision ID: 20251227_002
Revises: 20251227_001
Create Date: 2025-12-27

This migration adds a 'source' column to track where each price came from:
- bulk: Prices from bulk data imports (MTGJSON, Scryfall)
- api: Prices from marketplace API calls
- tcgplayer: Prices from TCGPlayer specifically
- calculated: Prices computed from other data
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20251227_002'
down_revision: Union[str, None] = '20251227_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('price_snapshots', sa.Column(
        'source',
        sa.String(20),
        server_default='bulk',
        nullable=False
    ))
    op.create_index('ix_price_snapshots_source', 'price_snapshots', ['source'])


def downgrade() -> None:
    op.drop_index('ix_price_snapshots_source', table_name='price_snapshots')
    op.drop_column('price_snapshots', 'source')
