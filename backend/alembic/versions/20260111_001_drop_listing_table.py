"""drop listing and listing_feature_vectors tables

This migration completes the Listing to PriceSnapshot migration by removing
the deprecated listings table and its associated listing_feature_vectors table.

All price data should now be stored in PriceSnapshot, which provides:
- Better variant tracking (condition, language, foil status)
- TimescaleDB hypertable support for time-series queries
- Improved indexing for marketplace and card queries

Revision ID: drop_listing_001
Revises: add_trading_posts_001
Create Date: 2026-01-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'drop_listing_001'
down_revision: Union[str, None] = 'add_trading_posts_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop listings and listing_feature_vectors tables.

    Both tables are empty and the Listing model has been removed.
    All price data is now stored in PriceSnapshot.
    """
    # Drop listing_feature_vectors first (depends on listings)
    op.drop_index('ix_listing_feature_vectors_listing_id', table_name='listing_feature_vectors')
    op.drop_table('listing_feature_vectors')

    # Drop indexes on listings table
    op.drop_index('ix_listings_card_marketplace', table_name='listings')
    op.drop_index('ix_listings_price', table_name='listings')
    op.drop_index('ix_listings_last_seen', table_name='listings')
    op.drop_index('ix_listings_card_id', table_name='listings')
    op.drop_index('ix_listings_marketplace_id', table_name='listings')

    # Drop the listings table
    op.drop_table('listings')


def downgrade() -> None:
    """Recreate listings and listing_feature_vectors tables.

    This is provided for completeness but should not be used in production.
    The Listing model has been removed from the codebase.
    """
    # Recreate listings table
    op.create_table(
        'listings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('marketplace_id', sa.Integer(), nullable=False),
        sa.Column('condition', sa.String(50), nullable=True),
        sa.Column('language', sa.String(50), nullable=False, server_default='English'),
        sa.Column('is_foil', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('seller_name', sa.String(255), nullable=True),
        sa.Column('seller_rating', sa.Float(), nullable=True),
        sa.Column('external_id', sa.String(100), nullable=True),
        sa.Column('listing_url', sa.String(500), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['marketplace_id'], ['marketplaces.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_listings_card_id', 'listings', ['card_id'])
    op.create_index('ix_listings_marketplace_id', 'listings', ['marketplace_id'])
    op.create_index('ix_listings_card_marketplace', 'listings', ['card_id', 'marketplace_id'])
    op.create_index('ix_listings_price', 'listings', ['price'])
    op.create_index('ix_listings_last_seen', 'listings', ['last_seen_at'])

    # Recreate listing_feature_vectors table
    op.create_table(
        'listing_feature_vectors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('listing_id', sa.Integer(), nullable=False),
        sa.Column('embedding', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_listing_feature_vectors_listing_id', 'listing_feature_vectors', ['listing_id'])
