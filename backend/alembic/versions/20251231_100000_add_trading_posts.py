"""add trading posts tables

Revision ID: add_trading_posts_001
Revises: c3d4e5f6g7h8
Create Date: 2025-12-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'add_trading_posts_001'
down_revision: Union[str, None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create trading_posts table
    op.create_table(
        'trading_posts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('store_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(50), nullable=True),
        sa.Column('country', sa.String(50), server_default='US', nullable=False),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('website', sa.String(500), nullable=True),
        sa.Column('hours', JSONB(), nullable=True),
        sa.Column('services', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('buylist_margin', sa.Numeric(3, 2), server_default='0.50', nullable=False),
        sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verification_method', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', name='uq_trading_posts_user')
    )
    op.create_index('ix_trading_posts_city', 'trading_posts', ['city'])
    op.create_index('ix_trading_posts_state', 'trading_posts', ['state'])
    op.create_index('ix_trading_posts_verified', 'trading_posts', ['email_verified_at'],
                    postgresql_where=sa.text('email_verified_at IS NOT NULL'))

    # Create trade_quotes table
    op.create_table(
        'trade_quotes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), server_default='draft', nullable=False),
        sa.Column('total_market_value', sa.Numeric(10, 2), nullable=True),
        sa.Column('item_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    op.create_index('ix_trade_quotes_user', 'trade_quotes', ['user_id'])
    op.create_index('ix_trade_quotes_status', 'trade_quotes', ['status'])

    # Create trade_quote_items table
    op.create_table(
        'trade_quote_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
        sa.Column('condition', sa.String(20), server_default='NM', nullable=False),
        sa.Column('market_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['quote_id'], ['trade_quotes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('quote_id', 'card_id', 'condition', name='uq_trade_quote_items')
    )
    op.create_index('ix_trade_quote_items_quote', 'trade_quote_items', ['quote_id'])

    # Create trade_quote_submissions table
    op.create_table(
        'trade_quote_submissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('trading_post_id', sa.Integer(), nullable=False),
        sa.Column('offer_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('counter_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('counter_note', sa.Text(), nullable=True),
        sa.Column('store_responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['quote_id'], ['trade_quotes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trading_post_id'], ['trading_posts.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('quote_id', 'trading_post_id', name='uq_trade_quote_submissions')
    )
    op.create_index('ix_trade_quote_submissions_quote', 'trade_quote_submissions', ['quote_id'])
    op.create_index('ix_trade_quote_submissions_store', 'trade_quote_submissions', ['trading_post_id'])
    op.create_index('ix_trade_quote_submissions_status', 'trade_quote_submissions', ['status'])

    # Create trading_post_events table
    op.create_table(
        'trading_post_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('trading_post_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('format', sa.String(50), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('entry_fee', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_players', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['trading_post_id'], ['trading_posts.id'], ondelete='CASCADE')
    )
    op.create_index('ix_trading_post_events_store', 'trading_post_events', ['trading_post_id'])
    op.create_index('ix_trading_post_events_start', 'trading_post_events', ['start_time'])
    op.create_index('ix_trading_post_events_type', 'trading_post_events', ['event_type'])


def downgrade() -> None:
    op.drop_table('trading_post_events')
    op.drop_table('trade_quote_submissions')
    op.drop_table('trade_quote_items')
    op.drop_table('trade_quotes')
    op.drop_table('trading_posts')
