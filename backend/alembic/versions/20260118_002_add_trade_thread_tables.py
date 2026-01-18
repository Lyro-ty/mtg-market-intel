"""add trade thread tables

Revision ID: 20260118_002
Revises: fe63159c6add
Create Date: 2026-01-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '20260118_002'
down_revision: Union[str, None] = 'fe63159c6add'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Trade threads - one thread per trade proposal for negotiation
    op.create_table(
        'trade_threads',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trade_proposal_id', sa.Integer(), sa.ForeignKey('trade_proposals.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('archived_at', sa.DateTime()),
        sa.Column('last_message_at', sa.DateTime()),
        sa.Column('message_count', sa.Integer(), server_default='0'),
    )
    op.create_index('idx_trade_threads_proposal', 'trade_threads', ['trade_proposal_id'])

    # Trade thread messages - messages within a thread, can include card references
    op.create_table(
        'trade_thread_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('thread_id', sa.Integer(), sa.ForeignKey('trade_threads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text()),
        sa.Column('card_id', sa.Integer(), sa.ForeignKey('cards.id')),
        sa.Column('has_attachments', sa.Boolean(), server_default='false'),
        sa.Column('reactions', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime()),
        sa.Column('reported_at', sa.DateTime()),
    )
    op.create_index('idx_trade_thread_messages_thread', 'trade_thread_messages', ['thread_id', 'created_at'])

    # Trade thread attachments - photos for condition verification
    op.create_table(
        'trade_thread_attachments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('message_id', sa.Integer(), sa.ForeignKey('trade_thread_messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_url', sa.String(500), nullable=False),
        sa.Column('file_type', sa.String(50)),
        sa.Column('file_size', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('purge_after', sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table('trade_thread_attachments')
    op.drop_index('idx_trade_thread_messages_thread', table_name='trade_thread_messages')
    op.drop_table('trade_thread_messages')
    op.drop_index('idx_trade_threads_proposal', table_name='trade_threads')
    op.drop_table('trade_threads')
