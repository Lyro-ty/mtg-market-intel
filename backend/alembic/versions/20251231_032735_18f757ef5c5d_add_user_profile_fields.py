"""add user profile fields

Revision ID: 18f757ef5c5d
Revises: 20251229_001
Create Date: 2025-12-31 03:27:35.406079

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18f757ef5c5d'
down_revision: Union[str, None] = '20251229_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add profile fields to users table
    op.add_column('users', sa.Column('avatar_url', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('location', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('discord_id', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=True))

    # Create unique index on discord_id for lookups
    op.create_index('ix_users_discord_id', 'users', ['discord_id'], unique=True)


def downgrade() -> None:
    # Remove index first
    op.drop_index('ix_users_discord_id', table_name='users')

    # Remove columns
    op.drop_column('users', 'last_active_at')
    op.drop_column('users', 'discord_id')
    op.drop_column('users', 'location')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'avatar_url')
