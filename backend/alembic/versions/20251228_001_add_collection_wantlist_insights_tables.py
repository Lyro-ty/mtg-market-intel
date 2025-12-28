"""Add collection, want list, and insights tables

Revision ID: 20251228_001
Revises: 20251227_005
Create Date: 2025-12-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20251228_001'
down_revision: Union[str, None] = '20251227_005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create mtg_sets table
    op.create_table(
        'mtg_sets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(10), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('released_at', sa.Date(), nullable=True),
        sa.Column('set_type', sa.String(50), nullable=False),
        sa.Column('card_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('icon_svg_uri', sa.String(500), nullable=True),
        sa.Column('scryfall_id', sa.String(50), nullable=True),
        sa.Column('parent_set_code', sa.String(10), nullable=True),
        sa.Column('is_digital', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_foil_only', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.UniqueConstraint('scryfall_id')
    )
    op.create_index('ix_mtg_sets_code', 'mtg_sets', ['code'])
    op.create_index('ix_mtg_sets_set_type', 'mtg_sets', ['set_type'])

    # Create want_list_items table
    op.create_table(
        'want_list_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('target_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('priority', sa.String(10), nullable=False, server_default='medium'),
        sa.Column('alert_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_want_list_items_user_id', 'want_list_items', ['user_id'])
    op.create_index('ix_want_list_items_card_id', 'want_list_items', ['card_id'])
    op.create_index('ix_want_list_user_card', 'want_list_items', ['user_id', 'card_id'], unique=True)
    op.create_index('ix_want_list_alert_enabled', 'want_list_items', ['alert_enabled'])

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('priority', sa.String(10), nullable=False, server_default='medium'),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dedup_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dedup_hash')
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_type', 'notifications', ['type'])
    op.create_index('ix_notifications_card_id', 'notifications', ['card_id'])
    op.create_index('ix_notifications_user_read', 'notifications', ['user_id', 'read'])
    op.create_index('ix_notifications_user_type', 'notifications', ['user_id', 'type'])
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])

    # Create collection_stats table
    op.create_table(
        'collection_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('total_cards', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_value', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('unique_cards', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sets_started', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sets_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('top_set_code', sa.String(10), nullable=True),
        sa.Column('top_set_completion', sa.Numeric(5, 2), nullable=True),
        sa.Column('is_stale', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_calculated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_collection_stats_user_id', 'collection_stats', ['user_id'])

    # Create user_milestones table
    op.create_table(
        'user_milestones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(30), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('threshold', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('achieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'type', 'threshold', name='uq_user_milestones_user_type_threshold')
    )
    op.create_index('ix_user_milestones_user_id', 'user_milestones', ['user_id'])
    op.create_index('ix_user_milestones_type', 'user_milestones', ['type'])
    op.create_index('ix_user_milestones_achieved_at', 'user_milestones', ['achieved_at'])
    op.create_index('ix_user_milestones_user_type', 'user_milestones', ['user_id', 'type'])

    # Add notification preference columns to users table
    op.add_column('users', sa.Column('email_alerts', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column('price_drop_threshold', sa.Integer(), nullable=False, server_default='10'))
    op.add_column('users', sa.Column('digest_frequency', sa.String(10), nullable=False, server_default='instant'))


def downgrade() -> None:
    # Remove user notification preference columns
    op.drop_column('users', 'digest_frequency')
    op.drop_column('users', 'price_drop_threshold')
    op.drop_column('users', 'email_alerts')

    # Drop user_milestones table
    op.drop_index('ix_user_milestones_user_type', table_name='user_milestones')
    op.drop_index('ix_user_milestones_achieved_at', table_name='user_milestones')
    op.drop_index('ix_user_milestones_type', table_name='user_milestones')
    op.drop_index('ix_user_milestones_user_id', table_name='user_milestones')
    op.drop_table('user_milestones')

    # Drop collection_stats table
    op.drop_index('ix_collection_stats_user_id', table_name='collection_stats')
    op.drop_table('collection_stats')

    # Drop notifications table
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_index('ix_notifications_user_type', table_name='notifications')
    op.drop_index('ix_notifications_user_read', table_name='notifications')
    op.drop_index('ix_notifications_card_id', table_name='notifications')
    op.drop_index('ix_notifications_type', table_name='notifications')
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_table('notifications')

    # Drop want_list_items table
    op.drop_index('ix_want_list_alert_enabled', table_name='want_list_items')
    op.drop_index('ix_want_list_user_card', table_name='want_list_items')
    op.drop_index('ix_want_list_items_card_id', table_name='want_list_items')
    op.drop_index('ix_want_list_items_user_id', table_name='want_list_items')
    op.drop_table('want_list_items')

    # Drop mtg_sets table
    op.drop_index('ix_mtg_sets_set_type', table_name='mtg_sets')
    op.drop_index('ix_mtg_sets_code', table_name='mtg_sets')
    op.drop_table('mtg_sets')
