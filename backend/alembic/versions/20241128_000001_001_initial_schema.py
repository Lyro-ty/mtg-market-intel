"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-11-28 00:00:01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create cards table
    op.create_table(
        'cards',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('scryfall_id', sa.String(36), nullable=False),
        sa.Column('oracle_id', sa.String(36), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('set_code', sa.String(10), nullable=False),
        sa.Column('set_name', sa.String(255), nullable=True),
        sa.Column('collector_number', sa.String(20), nullable=False),
        sa.Column('rarity', sa.String(20), nullable=True),
        sa.Column('mana_cost', sa.String(100), nullable=True),
        sa.Column('cmc', sa.Float(), nullable=True),
        sa.Column('type_line', sa.String(255), nullable=True),
        sa.Column('oracle_text', sa.Text(), nullable=True),
        sa.Column('colors', sa.String(50), nullable=True),
        sa.Column('color_identity', sa.String(50), nullable=True),
        sa.Column('power', sa.String(10), nullable=True),
        sa.Column('toughness', sa.String(10), nullable=True),
        sa.Column('legalities', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('image_url_small', sa.String(500), nullable=True),
        sa.Column('image_url_large', sa.String(500), nullable=True),
        sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cards_scryfall_id', 'cards', ['scryfall_id'], unique=True)
    op.create_index('ix_cards_oracle_id', 'cards', ['oracle_id'], unique=False)
    op.create_index('ix_cards_name', 'cards', ['name'], unique=False)
    op.create_index('ix_cards_set_code', 'cards', ['set_code'], unique=False)
    op.create_index('ix_cards_name_set', 'cards', ['name', 'set_code'], unique=False)
    op.create_index('ix_cards_set_collector', 'cards', ['set_code', 'collector_number'], unique=False)

    # Create marketplaces table
    op.create_table(
        'marketplaces',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(50), nullable=False),
        sa.Column('base_url', sa.String(255), nullable=False),
        sa.Column('api_url', sa.String(255), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), default=True, nullable=False),
        sa.Column('supports_api', sa.Boolean(), default=False, nullable=False),
        sa.Column('default_currency', sa.String(3), default='USD', nullable=False),
        sa.Column('rate_limit_seconds', sa.Float(), default=1.0, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('ix_marketplaces_slug', 'marketplaces', ['slug'], unique=True)

    # Create listings table
    op.create_table(
        'listings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('marketplace_id', sa.Integer(), nullable=False),
        sa.Column('condition', sa.String(50), nullable=True),
        sa.Column('language', sa.String(50), default='English', nullable=False),
        sa.Column('is_foil', sa.Boolean(), default=False, nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), default='USD', nullable=False),
        sa.Column('quantity', sa.Integer(), default=1, nullable=False),
        sa.Column('seller_name', sa.String(255), nullable=True),
        sa.Column('seller_rating', sa.Float(), nullable=True),
        sa.Column('external_id', sa.String(100), nullable=True),
        sa.Column('listing_url', sa.String(500), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['marketplace_id'], ['marketplaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_listings_card_id', 'listings', ['card_id'], unique=False)
    op.create_index('ix_listings_marketplace_id', 'listings', ['marketplace_id'], unique=False)
    op.create_index('ix_listings_card_marketplace', 'listings', ['card_id', 'marketplace_id'], unique=False)
    op.create_index('ix_listings_price', 'listings', ['price'], unique=False)
    op.create_index('ix_listings_last_seen', 'listings', ['last_seen_at'], unique=False)

    # Create price_snapshots table
    op.create_table(
        'price_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('marketplace_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), default='USD', nullable=False),
        sa.Column('price_foil', sa.Numeric(10, 2), nullable=True),
        sa.Column('min_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('avg_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('median_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('num_listings', sa.Integer(), nullable=True),
        sa.Column('total_quantity', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['marketplace_id'], ['marketplaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_snapshots_card_id', 'price_snapshots', ['card_id'], unique=False)
    op.create_index('ix_snapshots_marketplace_id', 'price_snapshots', ['marketplace_id'], unique=False)
    op.create_index('ix_snapshots_snapshot_time', 'price_snapshots', ['snapshot_time'], unique=False)
    op.create_index('ix_snapshots_card_time', 'price_snapshots', ['card_id', 'snapshot_time'], unique=False)
    op.create_index('ix_snapshots_market_time', 'price_snapshots', ['marketplace_id', 'snapshot_time'], unique=False)
    op.create_index('ix_snapshots_card_market_time', 'price_snapshots', ['card_id', 'marketplace_id', 'snapshot_time'], unique=False)

    # Create metrics_cards_daily table
    op.create_table(
        'metrics_cards_daily',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('avg_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('min_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('median_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('spread', sa.Numeric(10, 2), nullable=True),
        sa.Column('spread_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('total_listings', sa.Integer(), nullable=True),
        sa.Column('total_quantity', sa.Integer(), nullable=True),
        sa.Column('num_marketplaces', sa.Integer(), nullable=True),
        sa.Column('price_change_1d', sa.Numeric(10, 2), nullable=True),
        sa.Column('price_change_7d', sa.Numeric(10, 2), nullable=True),
        sa.Column('price_change_30d', sa.Numeric(10, 2), nullable=True),
        sa.Column('price_change_pct_1d', sa.Numeric(5, 2), nullable=True),
        sa.Column('price_change_pct_7d', sa.Numeric(5, 2), nullable=True),
        sa.Column('price_change_pct_30d', sa.Numeric(5, 2), nullable=True),
        sa.Column('ma_7d', sa.Numeric(10, 2), nullable=True),
        sa.Column('ma_30d', sa.Numeric(10, 2), nullable=True),
        sa.Column('volatility_7d', sa.Numeric(10, 4), nullable=True),
        sa.Column('volatility_30d', sa.Numeric(10, 4), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_metrics_card_id', 'metrics_cards_daily', ['card_id'], unique=False)
    op.create_index('ix_metrics_date', 'metrics_cards_daily', ['date'], unique=False)
    op.create_index('ix_metrics_card_date', 'metrics_cards_daily', ['card_id', 'date'], unique=True)
    op.create_index('ix_metrics_spread', 'metrics_cards_daily', ['spread_pct'], unique=False)
    op.create_index('ix_metrics_change', 'metrics_cards_daily', ['price_change_pct_7d'], unique=False)

    # Create signals table
    op.create_table(
        'signals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('value', sa.Numeric(10, 4), nullable=True),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('llm_insight', sa.Text(), nullable=True),
        sa.Column('llm_provider', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_signals_card_id', 'signals', ['card_id'], unique=False)
    op.create_index('ix_signals_date', 'signals', ['date'], unique=False)
    op.create_index('ix_signals_signal_type', 'signals', ['signal_type'], unique=False)
    op.create_index('ix_signals_card_date', 'signals', ['card_id', 'date'], unique=False)
    op.create_index('ix_signals_type_date', 'signals', ['signal_type', 'date'], unique=False)
    op.create_index('ix_signals_card_type', 'signals', ['card_id', 'signal_type'], unique=False)

    # Create recommendations table
    op.create_table(
        'recommendations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('marketplace_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(10), nullable=False),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=False),
        sa.Column('horizon_days', sa.Integer(), default=7, nullable=False),
        sa.Column('target_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('current_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('potential_profit_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('source_signals', sa.Text(), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['marketplace_id'], ['marketplaces.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_recommendations_card_id', 'recommendations', ['card_id'], unique=False)
    op.create_index('ix_recommendations_marketplace_id', 'recommendations', ['marketplace_id'], unique=False)
    op.create_index('ix_recommendations_action', 'recommendations', ['action'], unique=False)
    op.create_index('ix_recommendations_card_action', 'recommendations', ['card_id', 'action'], unique=False)
    op.create_index('ix_recommendations_active', 'recommendations', ['is_active'], unique=False)
    op.create_index('ix_recommendations_confidence', 'recommendations', ['confidence'], unique=False)

    # Create app_settings table
    op.create_table(
        'app_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('value_type', sa.String(20), default='string', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    op.create_index('ix_app_settings_key', 'app_settings', ['key'], unique=True)


def downgrade() -> None:
    op.drop_table('app_settings')
    op.drop_table('recommendations')
    op.drop_table('signals')
    op.drop_table('metrics_cards_daily')
    op.drop_table('price_snapshots')
    op.drop_table('listings')
    op.drop_table('marketplaces')
    op.drop_table('cards')

