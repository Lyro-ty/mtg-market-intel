"""add available_for_trade to inventory

Revision ID: 726e47e68fab
Revises: 18f757ef5c5d
Create Date: 2025-12-31 03:36:08.801736

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '726e47e68fab'
down_revision: Union[str, None] = '18f757ef5c5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add available_for_trade column with default False
    op.add_column(
        'inventory_items',
        sa.Column('available_for_trade', sa.Boolean(), server_default='false', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('inventory_items', 'available_for_trade')
