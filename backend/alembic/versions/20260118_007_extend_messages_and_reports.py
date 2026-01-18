"""extend messages and reports

Extends the messages table with trade thread linking, attachment tracking,
reactions, and moderation fields.

Extends the user_reports table with enhanced categorization, evidence
capture, and resolution tracking.

Revision ID: 20260118_007
Revises: 20260118_006
Create Date: 2026-01-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '20260118_007'
down_revision: Union[str, None] = '20260118_006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Messages table extensions ---

    # Trade thread linking - allows messages to be associated with trade negotiations
    op.add_column('messages', sa.Column('trade_thread_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_messages_trade_thread',
        'messages',
        'trade_threads',
        ['trade_thread_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Attachment and reaction tracking
    op.add_column('messages', sa.Column('has_attachments', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('messages', sa.Column('reactions', JSONB(), server_default='{}', nullable=False))

    # Soft delete and moderation tracking
    op.add_column('messages', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('messages', sa.Column('reported_at', sa.DateTime(timezone=True), nullable=True))

    # Index for finding messages in a trade thread
    op.create_index('ix_messages_trade_thread_id', 'messages', ['trade_thread_id'])

    # --- User reports table extensions ---

    # Report categorization
    op.add_column('user_reports', sa.Column('report_type', sa.String(50), nullable=True))

    # Evidence snapshot - captures relevant data at time of report
    op.add_column('user_reports', sa.Column('evidence_snapshot', JSONB(), nullable=True))

    # Resolution tracking
    op.add_column('user_reports', sa.Column('resolution', sa.String(50), nullable=True))
    op.add_column('user_reports', sa.Column('resolved_by', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_user_reports_resolved_by',
        'user_reports',
        'users',
        ['resolved_by'],
        ['id'],
        ondelete='SET NULL'
    )
    op.add_column('user_reports', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('user_reports', sa.Column('resolution_notes', sa.Text(), nullable=True))

    # Index for filtering reports by resolution status and age
    # Note: Using project convention 'ix_' prefix. There's already an ix_user_reports_status
    # index on status column, so we create a composite index for resolution queries
    op.create_index('ix_user_reports_resolution_created', 'user_reports', ['resolution', 'created_at'])


def downgrade() -> None:
    # --- User reports table - drop in reverse order ---
    op.drop_index('ix_user_reports_resolution_created', table_name='user_reports')
    op.drop_column('user_reports', 'resolution_notes')
    op.drop_column('user_reports', 'resolved_at')
    op.drop_constraint('fk_user_reports_resolved_by', 'user_reports', type_='foreignkey')
    op.drop_column('user_reports', 'resolved_by')
    op.drop_column('user_reports', 'resolution')
    op.drop_column('user_reports', 'evidence_snapshot')
    op.drop_column('user_reports', 'report_type')

    # --- Messages table - drop in reverse order ---
    op.drop_index('ix_messages_trade_thread_id', table_name='messages')
    op.drop_column('messages', 'reported_at')
    op.drop_column('messages', 'deleted_at')
    op.drop_column('messages', 'reactions')
    op.drop_column('messages', 'has_attachments')
    op.drop_constraint('fk_messages_trade_thread', 'messages', type_='foreignkey')
    op.drop_column('messages', 'trade_thread_id')
