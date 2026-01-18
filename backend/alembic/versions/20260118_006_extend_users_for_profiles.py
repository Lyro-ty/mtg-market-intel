"""extend users for profiles

Adds profile card fields, location fields, frame/discovery settings,
privacy settings, and activity tracking to the users table.

Enables pg_trgm extension for fuzzy search capabilities.

Revision ID: 20260118_006
Revises: 20260118_005
Create Date: 2026-01-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260118_006'
down_revision: Union[str, None] = '20260118_005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pg_trgm extension for trigram search
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    # Profile card fields
    op.add_column('users', sa.Column('tagline', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('signature_card_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('card_type', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('card_type_changed_at', sa.DateTime(timezone=True), nullable=True))

    # Location fields (city and country are new; location already exists)
    op.add_column('users', sa.Column('city', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('country', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('shipping_preference', sa.String(20), nullable=True))

    # Frame and discovery
    op.add_column('users', sa.Column('active_frame_tier', sa.String(20), server_default='bronze', nullable=False))
    op.add_column('users', sa.Column('discovery_score', sa.Integer(), server_default='100', nullable=False))

    # Privacy settings
    op.add_column('users', sa.Column('show_in_directory', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('users', sa.Column('show_in_search', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('users', sa.Column('show_online_status', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('users', sa.Column('show_portfolio_tier', sa.Boolean(), server_default='true', nullable=False))

    # Onboarding tracking (last_active_at already exists)
    op.add_column('users', sa.Column('onboarding_completed_at', sa.DateTime(timezone=True), nullable=True))

    # Add foreign key constraint for signature_card_id
    op.create_foreign_key(
        'fk_users_signature_card',
        'users',
        'cards',
        ['signature_card_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Index for discovery directory (partial index for active users)
    op.execute('''
        CREATE INDEX ix_users_discovery_directory
        ON users (discovery_score DESC)
        WHERE show_in_directory = true
    ''')

    # Index for location-based search
    op.create_index('ix_users_location', 'users', ['country', 'city'])

    # GIN trigram index for fuzzy search on username and display_name
    op.execute('''
        CREATE INDEX ix_users_search_trgm
        ON users USING gin ((username || ' ' || COALESCE(display_name, '')) gin_trgm_ops)
    ''')


def downgrade() -> None:
    # Drop indexes
    op.execute('DROP INDEX IF EXISTS ix_users_search_trgm')
    op.drop_index('ix_users_location', table_name='users')
    op.execute('DROP INDEX IF EXISTS ix_users_discovery_directory')

    # Drop foreign key
    op.drop_constraint('fk_users_signature_card', 'users', type_='foreignkey')

    # Drop columns (reverse order of addition)
    op.drop_column('users', 'onboarding_completed_at')
    op.drop_column('users', 'show_portfolio_tier')
    op.drop_column('users', 'show_online_status')
    op.drop_column('users', 'show_in_search')
    op.drop_column('users', 'show_in_directory')
    op.drop_column('users', 'discovery_score')
    op.drop_column('users', 'active_frame_tier')
    op.drop_column('users', 'shipping_preference')
    op.drop_column('users', 'country')
    op.drop_column('users', 'city')
    op.drop_column('users', 'card_type_changed_at')
    op.drop_column('users', 'card_type')
    op.drop_column('users', 'signature_card_id')
    op.drop_column('users', 'tagline')

    # Note: We don't drop pg_trgm extension as it may be used elsewhere
