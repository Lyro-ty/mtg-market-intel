"""Add legality_changes table for tracking format bans/unbans.

Revision ID: add_legality_changes
Revises: add_buylist_snapshots
Create Date: 2025-12-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_legality_changes'
down_revision: Union[str, None] = 'add_buylist_snapshots'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'legality_changes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('format', sa.String(length=50), nullable=False),
        sa.Column('old_status', sa.String(length=20), nullable=True),
        sa.Column('new_status', sa.String(length=20), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.Column('announcement_url', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index('ix_legality_changes_card_id', 'legality_changes', ['card_id'], unique=False)
    op.create_index('ix_legality_changes_format', 'legality_changes', ['format'], unique=False)
    op.create_index('ix_legality_changes_changed_at', 'legality_changes', ['changed_at'], unique=False)

    # Composite index for finding changes by format+status
    op.create_index(
        'ix_legality_changes_format_status',
        'legality_changes',
        ['format', 'new_status'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_legality_changes_format_status', table_name='legality_changes')
    op.drop_index('ix_legality_changes_changed_at', table_name='legality_changes')
    op.drop_index('ix_legality_changes_format', table_name='legality_changes')
    op.drop_index('ix_legality_changes_card_id', table_name='legality_changes')
    op.drop_table('legality_changes')
