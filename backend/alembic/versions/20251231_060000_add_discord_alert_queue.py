"""add discord alert queue table

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2025-12-31 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'discord_alert_queue',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notification_id', sa.Integer(), nullable=True),
        sa.Column('card_id', sa.Integer(), nullable=True),
        sa.Column('alert_type', sa.String(30), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('delivered', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivery_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='SET NULL'),
    )

    # Create indexes
    op.create_index('ix_discord_alert_queue_user_id', 'discord_alert_queue', ['user_id'])
    op.create_index('ix_discord_alert_queue_notification_id', 'discord_alert_queue', ['notification_id'])
    op.create_index('ix_discord_alert_queue_alert_type', 'discord_alert_queue', ['alert_type'])
    op.create_index('ix_discord_alert_queue_delivered', 'discord_alert_queue', ['delivered'])
    op.create_index('ix_discord_alert_queue_pending', 'discord_alert_queue', ['delivered', 'created_at'])
    op.create_index('ix_discord_alert_queue_user_pending', 'discord_alert_queue', ['user_id', 'delivered'])


def downgrade() -> None:
    op.drop_index('ix_discord_alert_queue_user_pending', 'discord_alert_queue')
    op.drop_index('ix_discord_alert_queue_pending', 'discord_alert_queue')
    op.drop_index('ix_discord_alert_queue_delivered', 'discord_alert_queue')
    op.drop_index('ix_discord_alert_queue_alert_type', 'discord_alert_queue')
    op.drop_index('ix_discord_alert_queue_notification_id', 'discord_alert_queue')
    op.drop_index('ix_discord_alert_queue_user_id', 'discord_alert_queue')
    op.drop_table('discord_alert_queue')
