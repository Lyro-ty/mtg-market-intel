"""add moderation tables

Revision ID: 20260118_004
Revises: 20260118_003
Create Date: 2026-01-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY


# revision identifiers, used by Alembic.
revision: str = '20260118_004'
down_revision: Union[str, None] = '20260118_003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Moderation actions - track warn, restrict, suspend, ban actions
    op.create_table(
        'moderation_actions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('moderator_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('target_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('duration_days', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        # related_report_id references user_reports table (created in 20251230_001)
        sa.Column('related_report_id', sa.Integer(), sa.ForeignKey('user_reports.id', ondelete='SET NULL'), nullable=True),
        # related_dispute_id references trade_disputes (created in this migration, so no FK here to avoid circular reference)
        sa.Column('related_dispute_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_moderation_actions_target', 'moderation_actions', ['target_user_id', 'created_at'])

    # Moderation notes - internal admin notes on users
    op.create_table(
        'moderation_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        # moderator_id must be nullable if ondelete='SET NULL'
        sa.Column('moderator_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('target_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_moderation_notes_target', 'moderation_notes', ['target_user_id'])

    # Appeals - users appealing moderation actions
    op.create_table(
        'appeals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('moderation_action_id', sa.Integer(), sa.ForeignKey('moderation_actions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('appeal_text', sa.Text(), nullable=False),
        sa.Column('evidence_urls', ARRAY(sa.Text()), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_appeals_user', 'appeals', ['user_id'])
    op.create_index('ix_appeals_status', 'appeals', ['status', 'created_at'])

    # Trade disputes - trade-specific issues between users
    op.create_table(
        'trade_disputes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trade_proposal_id', sa.Integer(), sa.ForeignKey('trade_proposals.id', ondelete='SET NULL'), nullable=True),
        sa.Column('filed_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('dispute_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), server_default='open', nullable=False),
        sa.Column('assigned_moderator_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resolution', sa.String(50), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('evidence_snapshot', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_trade_disputes_status', 'trade_disputes', ['status', 'created_at'])
    op.create_index('ix_trade_disputes_filed_by', 'trade_disputes', ['filed_by'])


def downgrade() -> None:
    op.drop_index('ix_trade_disputes_filed_by', table_name='trade_disputes')
    op.drop_index('ix_trade_disputes_status', table_name='trade_disputes')
    op.drop_table('trade_disputes')
    op.drop_index('ix_appeals_status', table_name='appeals')
    op.drop_index('ix_appeals_user', table_name='appeals')
    op.drop_table('appeals')
    op.drop_index('ix_moderation_notes_target', table_name='moderation_notes')
    op.drop_table('moderation_notes')
    op.drop_index('ix_moderation_actions_target', table_name='moderation_actions')
    op.drop_table('moderation_actions')
