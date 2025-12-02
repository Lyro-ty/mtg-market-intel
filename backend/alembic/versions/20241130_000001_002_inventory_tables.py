"""Add inventory tables

Revision ID: 002
Revises: 001
Create Date: 2024-11-30 00:00:01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create inventory_items table
    op.create_table(
        'inventory_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), default=1, nullable=False),
        sa.Column('condition', sa.String(30), default='NEAR_MINT', nullable=False),
        sa.Column('is_foil', sa.Boolean(), default=False, nullable=False),
        sa.Column('language', sa.String(50), default='English', nullable=False),
        sa.Column('acquisition_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('acquisition_currency', sa.String(3), default='USD', nullable=False),
        sa.Column('acquisition_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acquisition_source', sa.String(255), nullable=True),
        sa.Column('current_value', sa.Numeric(10, 2), nullable=True),
        sa.Column('value_change_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('last_valued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('import_batch_id', sa.String(36), nullable=True),
        sa.Column('import_raw_line', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_inventory_items_card_id', 'inventory_items', ['card_id'], unique=False)
    op.create_index('ix_inventory_items_import_batch', 'inventory_items', ['import_batch_id'], unique=False)
    op.create_index('ix_inventory_card_condition', 'inventory_items', ['card_id', 'condition'], unique=False)
    op.create_index('ix_inventory_acquisition_date', 'inventory_items', ['acquisition_date'], unique=False)
    op.create_index('ix_inventory_value', 'inventory_items', ['current_value'], unique=False)
    op.create_index('ix_inventory_value_change', 'inventory_items', ['value_change_pct'], unique=False)

    # Create inventory_recommendations table
    op.create_table(
        'inventory_recommendations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(10), nullable=False),
        sa.Column('urgency', sa.String(20), default='NORMAL', nullable=False),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=False),
        sa.Column('horizon_days', sa.Integer(), default=3, nullable=False),
        sa.Column('target_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('current_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('potential_profit_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('roi_from_acquisition', sa.Numeric(6, 2), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('suggested_marketplace', sa.String(100), nullable=True),
        sa.Column('suggested_listing_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_inv_rec_item_id', 'inventory_recommendations', ['inventory_item_id'], unique=False)
    op.create_index('ix_inv_rec_card_id', 'inventory_recommendations', ['card_id'], unique=False)
    op.create_index('ix_inv_rec_action', 'inventory_recommendations', ['action'], unique=False)
    op.create_index('ix_inv_rec_item_action', 'inventory_recommendations', ['inventory_item_id', 'action'], unique=False)
    op.create_index('ix_inv_rec_urgency', 'inventory_recommendations', ['urgency'], unique=False)
    op.create_index('ix_inv_rec_active', 'inventory_recommendations', ['is_active'], unique=False)
    op.create_index('ix_inv_rec_confidence', 'inventory_recommendations', ['confidence'], unique=False)


def downgrade() -> None:
    op.drop_table('inventory_recommendations')
    op.drop_table('inventory_items')




