"""Add user_id to app_settings for per-user settings

Revision ID: 004_user_settings
Revises: 003_add_user_auth
Create Date: 2024-12-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_user_settings'
down_revision: Union[str, None] = '003_add_user_auth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the unique index on key first (since we'll have user_id + key as unique)
    # This will also remove the unique constraint since it's enforced by the index
    op.drop_index('ix_app_settings_key', 'app_settings')
    
    # Add user_id column, nullable first
    op.add_column('app_settings', sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Get system user ID and assign existing settings to it
    # If no system user exists, create one
    op.execute("""
        INSERT INTO users (email, username, hashed_password, display_name, is_active, is_verified, is_admin)
        VALUES ('system@dualcasterdeals.com', 'system', '$2b$12$placeholder.hash.for.migration.only', 'System User', true, true, true)
        ON CONFLICT (username) DO NOTHING
    """)
    
    # Update existing settings to belong to system user
    op.execute("""
        UPDATE app_settings 
        SET user_id = (SELECT id FROM users WHERE username = 'system' LIMIT 1)
        WHERE user_id IS NULL
    """)
    
    # Make user_id not nullable
    op.alter_column('app_settings', 'user_id', nullable=False)
    
    # Create foreign key
    op.create_foreign_key(
        'fk_app_settings_user_id',
        'app_settings',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Create composite unique index on (user_id, key)
    op.create_index('ix_app_settings_user_key', 'app_settings', ['user_id', 'key'], unique=True)
    op.create_index('ix_app_settings_user', 'app_settings', ['user_id'])


def downgrade() -> None:
    # Remove indexes
    op.drop_index('ix_app_settings_user', 'app_settings')
    op.drop_index('ix_app_settings_user_key', 'app_settings')
    
    # Remove foreign key
    op.drop_constraint('fk_app_settings_user_id', 'app_settings', type_='foreignkey')
    
    # Remove user_id column
    op.drop_column('app_settings', 'user_id')
    
    # Restore original unique index on key
    op.create_index('ix_app_settings_key', 'app_settings', ['key'], unique=True)

