"""fix moderation table constraints

NOTE: This migration is REDUNDANT if 20260118_004 was already corrected before
being applied. The original 20260118_004 was fixed in-place to include:
- nullable=True on moderation_notes.moderator_id
- FK constraint on related_report_id
- timezone=True on all DateTime columns

If both migrations ran against a fresh database with the corrected 20260118_004,
this migration's operations are harmless no-ops (alter_column to same type is
idempotent, and create_foreign_key may create a duplicate named constraint).

Original fixes intended:
1. moderation_notes.moderator_id - must be nullable when using ondelete='SET NULL'
2. moderation_actions.related_report_id - add FK to user_reports table
3. All DateTime columns - convert to timestamptz for timezone consistency

Revision ID: 20260118_005
Revises: 20260118_004
Create Date: 2026-01-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260118_005'
down_revision: Union[str, None] = '20260118_004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix 1: Make moderation_notes.moderator_id nullable (required for ondelete='SET NULL')
    op.alter_column(
        'moderation_notes',
        'moderator_id',
        existing_type=sa.Integer(),
        nullable=True
    )

    # Fix 2: Add FK constraint for moderation_actions.related_report_id -> user_reports.id
    op.create_foreign_key(
        'fk_moderation_actions_related_report',
        'moderation_actions',
        'user_reports',
        ['related_report_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Fix 3: Convert DateTime columns to timestamptz for timezone support
    # moderation_actions table
    op.alter_column(
        'moderation_actions',
        'expires_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True
    )
    op.alter_column(
        'moderation_actions',
        'created_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        existing_server_default=sa.text('now()')
    )

    # moderation_notes table
    op.alter_column(
        'moderation_notes',
        'created_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        existing_server_default=sa.text('now()')
    )

    # appeals table
    op.alter_column(
        'appeals',
        'created_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        existing_server_default=sa.text('now()')
    )
    op.alter_column(
        'appeals',
        'resolved_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True
    )

    # trade_disputes table
    op.alter_column(
        'trade_disputes',
        'created_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        existing_server_default=sa.text('now()')
    )
    op.alter_column(
        'trade_disputes',
        'resolved_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True
    )


def downgrade() -> None:
    # Revert DateTime columns back to timestamp without timezone
    op.alter_column(
        'trade_disputes',
        'resolved_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True
    )
    op.alter_column(
        'trade_disputes',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
        existing_server_default=sa.text('now()')
    )
    op.alter_column(
        'appeals',
        'resolved_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True
    )
    op.alter_column(
        'appeals',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
        existing_server_default=sa.text('now()')
    )
    op.alter_column(
        'moderation_notes',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
        existing_server_default=sa.text('now()')
    )
    op.alter_column(
        'moderation_actions',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True,
        existing_server_default=sa.text('now()')
    )
    op.alter_column(
        'moderation_actions',
        'expires_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_nullable=True
    )

    # Remove FK constraint
    op.drop_constraint('fk_moderation_actions_related_report', 'moderation_actions', type_='foreignkey')

    # Revert moderator_id to not nullable (would fail if any NULL values exist)
    op.alter_column(
        'moderation_notes',
        'moderator_id',
        existing_type=sa.Integer(),
        nullable=False
    )
