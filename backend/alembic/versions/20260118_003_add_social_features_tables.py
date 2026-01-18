"""add social features tables

Revision ID: 20260118_003
Revises: 20260118_002
Create Date: 2026-01-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '20260118_003'
down_revision: Union[str, None] = '20260118_002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # User favorites - bookmark other traders for quick access
    op.create_table(
        'user_favorites',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('favorited_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('notify_on_listings', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'favorited_user_id', name='uq_user_favorite'),
    )
    op.create_index('idx_user_favorites_user', 'user_favorites', ['user_id'])

    # User notes - private notes about other users (only visible to note creator)
    op.create_table(
        'user_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('user_id', 'target_user_id', name='uq_user_note'),
    )

    # User format specialties - Commander, Modern, Legacy, etc.
    op.create_table(
        'user_format_specialties',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('format', sa.String(50), nullable=False),
        sa.UniqueConstraint('user_id', 'format', name='uq_user_format'),
    )
    op.create_index('idx_user_format_specialties_user', 'user_format_specialties', ['user_id'])

    # Profile views - track who viewed which profile
    op.create_table(
        'profile_views',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('viewer_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('viewed_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_profile_views_viewed', 'profile_views', ['viewed_user_id', 'created_at'])

    # Notification preferences - granular control over alerts
    op.create_table(
        'notification_preferences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('preferences', JSONB, server_default='{}'),
        sa.Column('quiet_hours_enabled', sa.Boolean(), server_default='false'),
        sa.Column('quiet_hours_start', sa.Time()),
        sa.Column('quiet_hours_end', sa.Time()),
        sa.Column('timezone', sa.String(50), server_default='UTC'),
    )


def downgrade() -> None:
    op.drop_table('notification_preferences')
    op.drop_index('idx_profile_views_viewed', table_name='profile_views')
    op.drop_table('profile_views')
    op.drop_index('idx_user_format_specialties_user', table_name='user_format_specialties')
    op.drop_table('user_format_specialties')
    op.drop_table('user_notes')
    op.drop_index('idx_user_favorites_user', table_name='user_favorites')
    op.drop_table('user_favorites')
