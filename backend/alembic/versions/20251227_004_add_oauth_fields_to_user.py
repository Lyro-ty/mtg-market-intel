"""Add OAuth fields to user table

Revision ID: 20251227_004
Revises: 20251228_merge
Create Date: 2025-12-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251227_004'
down_revision: Union[str, None] = '20251228_merge'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add OAuth provider field - stores "google", "github", etc.
    op.add_column('users', sa.Column('oauth_provider', sa.String(length=50), nullable=True))

    # Add OAuth ID field - stores the user's ID from the OAuth provider
    op.add_column('users', sa.Column('oauth_id', sa.String(length=255), nullable=True))

    # Create index for efficient OAuth lookups
    op.create_index('ix_users_oauth', 'users', ['oauth_provider', 'oauth_id'], unique=True)


def downgrade() -> None:
    # Drop index first
    op.drop_index('ix_users_oauth', 'users')

    # Remove OAuth columns
    op.drop_column('users', 'oauth_id')
    op.drop_column('users', 'oauth_provider')
