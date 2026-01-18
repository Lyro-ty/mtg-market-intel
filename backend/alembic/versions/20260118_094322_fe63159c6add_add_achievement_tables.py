"""add achievement tables

Revision ID: fe63159c6add
Revises: 20260113_001
Create Date: 2026-01-18 09:43:22.719641

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'fe63159c6add'
down_revision: Union[str, None] = '20260113_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Achievement definitions
    op.create_table(
        'achievement_definitions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('icon', sa.String(100)),
        sa.Column('threshold', JSONB),
        sa.Column('discovery_points', sa.Integer(), default=0),
        sa.Column('frame_tier_unlock', sa.String(20)),
        sa.Column('rarity_percent', sa.Numeric(5, 2)),
        sa.Column('is_hidden', sa.Boolean(), default=False),
        sa.Column('is_seasonal', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # User achievements
    op.create_table(
        'user_achievements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('achievement_id', sa.Integer(), sa.ForeignKey('achievement_definitions.id'), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('progress', JSONB),
        sa.UniqueConstraint('user_id', 'achievement_id', name='uq_user_achievement'),
    )
    op.create_index('idx_user_achievements_user', 'user_achievements', ['user_id'])

    # User frames
    op.create_table(
        'user_frames',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('frame_tier', sa.String(20), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean(), default=False),
        sa.UniqueConstraint('user_id', 'frame_tier', name='uq_user_frame'),
    )


def downgrade() -> None:
    op.drop_table('user_frames')
    op.drop_index('idx_user_achievements_user')
    op.drop_table('user_achievements')
    op.drop_table('achievement_definitions')
