"""add reprint risk fields to cards

Revision ID: 5ad6dd9254e2
Revises: 726e47e68fab
Create Date: 2025-12-31 03:50:04.839962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ad6dd9254e2'
down_revision: Union[str, None] = '726e47e68fab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add reprint tracking fields
    op.add_column('cards', sa.Column('first_printed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('cards', sa.Column('reprint_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('cards', sa.Column('last_reprinted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('cards', sa.Column('reprint_risk_score', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('cards', 'reprint_risk_score')
    op.drop_column('cards', 'last_reprinted_at')
    op.drop_column('cards', 'reprint_count')
    op.drop_column('cards', 'first_printed_at')
