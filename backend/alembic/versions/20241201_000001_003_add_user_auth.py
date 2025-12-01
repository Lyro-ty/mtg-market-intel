"""Add user authentication tables and link inventory to users

Revision ID: 003_add_user_auth
Revises: 002
Create Date: 2024-12-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_user_auth'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes on users table
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    
    # Add user_id column to inventory_items table
    # First, create a default user for existing data
    op.execute("""
        INSERT INTO users (email, username, hashed_password, display_name, is_active, is_verified, is_admin)
        VALUES ('system@dualcasterdeals.com', 'system', '$2b$12$placeholder.hash.for.migration.only', 'System User', true, true, true)
        ON CONFLICT DO NOTHING
    """)
    
    # Add user_id column with nullable first
    op.add_column('inventory_items', sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Update existing items to belong to system user
    op.execute("""
        UPDATE inventory_items 
        SET user_id = (SELECT id FROM users WHERE username = 'system' LIMIT 1)
        WHERE user_id IS NULL
    """)
    
    # Make user_id not nullable
    op.alter_column('inventory_items', 'user_id', nullable=False)
    
    # Create foreign key and indexes
    op.create_foreign_key(
        'fk_inventory_items_user_id',
        'inventory_items',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )
    op.create_index('ix_inventory_user', 'inventory_items', ['user_id'])
    op.create_index('ix_inventory_user_card', 'inventory_items', ['user_id', 'card_id'])


def downgrade() -> None:
    # Remove indexes
    op.drop_index('ix_inventory_user_card', 'inventory_items')
    op.drop_index('ix_inventory_user', 'inventory_items')
    
    # Remove foreign key
    op.drop_constraint('fk_inventory_items_user_id', 'inventory_items', type_='foreignkey')
    
    # Remove user_id column
    op.drop_column('inventory_items', 'user_id')
    
    # Drop users table indexes
    op.drop_index('ix_users_username', 'users')
    op.drop_index('ix_users_email', 'users')
    
    # Drop users table
    op.drop_table('users')

