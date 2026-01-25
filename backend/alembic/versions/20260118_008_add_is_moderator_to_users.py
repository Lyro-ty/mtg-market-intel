"""Add is_moderator field to users table.

Revision ID: 20260118_008
Revises: 20260118_007_extend_messages_and_reports
Create Date: 2026-01-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260118_008'
down_revision = '20260118_007'
branch_labels = None
depends_on = None


def upgrade():
    """Add is_moderator column to users table."""
    op.add_column(
        'users',
        sa.Column('is_moderator', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )


def downgrade():
    """Remove is_moderator column from users table."""
    op.drop_column('users', 'is_moderator')
