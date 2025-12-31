"""Add enhanced alert columns to want_list_items.

Revision ID: add_want_list_enhanced_alerts
Revises: add_legality_changes
Create Date: 2025-12-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_want_list_enhanced_alerts'
down_revision: Union[str, None] = 'add_legality_changes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add enhanced alert columns
    op.add_column(
        'want_list_items',
        sa.Column('alert_on_spike', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column(
        'want_list_items',
        sa.Column(
            'alert_threshold_pct',
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment='Price change threshold % to trigger spike alert (e.g., 15.00 = 15%)'
        )
    )
    op.add_column(
        'want_list_items',
        sa.Column('alert_on_supply_low', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column(
        'want_list_items',
        sa.Column(
            'alert_on_price_drop',
            sa.Boolean(),
            nullable=False,
            server_default='true',
            comment='Alert when price drops below target'
        )
    )


def downgrade() -> None:
    op.drop_column('want_list_items', 'alert_on_price_drop')
    op.drop_column('want_list_items', 'alert_on_supply_low')
    op.drop_column('want_list_items', 'alert_threshold_pct')
    op.drop_column('want_list_items', 'alert_on_spike')
