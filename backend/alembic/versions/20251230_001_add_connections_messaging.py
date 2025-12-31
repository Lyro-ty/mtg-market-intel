"""Add connections, messaging, endorsements, and moderation tables.

Revision ID: 20251230_001
Revises:
Create Date: 2025-12-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251230_001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Connection requests table
    op.create_table(
        'connection_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('requester_id', sa.Integer(), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('card_ids', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['requester_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_connection_requests_requester_id', 'connection_requests', ['requester_id'])
    op.create_index('ix_connection_requests_recipient_id', 'connection_requests', ['recipient_id'])
    op.create_index('ix_connection_requests_status', 'connection_requests', ['status'])
    op.create_index('ix_connection_requests_recipient_status', 'connection_requests', ['recipient_id', 'status'])

    # Messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messages_sender_id', 'messages', ['sender_id'])
    op.create_index('ix_messages_recipient_id', 'messages', ['recipient_id'])
    op.create_index('ix_messages_recipient_read', 'messages', ['recipient_id', 'read_at'])

    # User endorsements table
    op.create_table(
        'user_endorsements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('endorser_id', sa.Integer(), nullable=False),
        sa.Column('endorsed_id', sa.Integer(), nullable=False),
        sa.Column('endorsement_type', sa.String(30), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['endorser_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['endorsed_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_endorsements_endorser_id', 'user_endorsements', ['endorser_id'])
    op.create_index('ix_endorsements_endorsed_id', 'user_endorsements', ['endorsed_id'])
    op.create_unique_constraint(
        'uq_endorsement_type',
        'user_endorsements',
        ['endorser_id', 'endorsed_id', 'endorsement_type']
    )

    # Blocked users table
    op.create_table(
        'blocked_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('blocker_id', sa.Integer(), nullable=False),
        sa.Column('blocked_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['blocker_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['blocked_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_blocked_users_blocker_id', 'blocked_users', ['blocker_id'])
    op.create_unique_constraint('uq_blocked_pair', 'blocked_users', ['blocker_id', 'blocked_id'])

    # User reports table
    op.create_table(
        'user_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reporter_id', sa.Integer(), nullable=False),
        sa.Column('reported_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(100), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reported_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_reports_reporter_id', 'user_reports', ['reporter_id'])
    op.create_index('ix_user_reports_reported_id', 'user_reports', ['reported_id'])
    op.create_index('ix_user_reports_status', 'user_reports', ['status'])


def downgrade() -> None:
    op.drop_table('user_reports')
    op.drop_table('blocked_users')
    op.drop_table('user_endorsements')
    op.drop_table('messages')
    op.drop_table('connection_requests')
