"""Add tournament and news tables for RAG data sources

Revision ID: 010_add_tournament_news_tables
Revises: 009_add_price_snapshot_unique_constraint
Create Date: 2024-12-05

This migration adds tables for tournament results and news articles
to support RAG retrieval and popularity metrics.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '010_add_tournament_news_tables'
down_revision: Union[str, None] = '009_add_price_snapshot_unique_constraint'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tournaments table
    op.create_table(
        'tournaments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=True),
        sa.Column('format', sa.String(length=50), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('organizer', sa.String(length=255), nullable=True),
        sa.Column('external_id', sa.String(length=100), nullable=True),
        sa.Column('external_url', sa.String(length=500), nullable=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_players', sa.Integer(), nullable=True),
        sa.Column('total_decks', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('raw_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tournaments_start_date', 'tournaments', ['start_date'], unique=False)
    op.create_index('ix_tournaments_source', 'tournaments', ['source'], unique=False)
    op.create_index('ix_tournaments_external_id', 'tournaments', ['external_id'], unique=False)
    op.create_unique_constraint('ix_tournaments_external_id_source', 'tournaments', ['external_id', 'source'])
    
    # Create decklists table
    op.create_table(
        'decklists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('player_name', sa.String(length=255), nullable=True),
        sa.Column('deck_name', sa.String(length=255), nullable=True),
        sa.Column('archetype', sa.String(length=100), nullable=True),
        sa.Column('placement', sa.Integer(), nullable=True),
        sa.Column('record', sa.String(length=20), nullable=True),
        sa.Column('external_id', sa.String(length=100), nullable=True),
        sa.Column('external_url', sa.String(length=500), nullable=True),
        sa.Column('mainboard', sa.Text(), nullable=True),
        sa.Column('sideboard', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decklists_tournament_id', 'decklists', ['tournament_id'], unique=False)
    op.create_index('ix_decklists_placement', 'decklists', ['placement'], unique=False)
    op.create_index('ix_decklists_tournament_placement', 'decklists', ['tournament_id', 'placement'], unique=False)
    
    # Create card_tournament_usage table
    op.create_table(
        'card_tournament_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('decklist_id', sa.Integer(), nullable=False),
        sa.Column('quantity_mainboard', sa.Integer(), nullable=False),
        sa.Column('quantity_sideboard', sa.Integer(), nullable=False),
        sa.Column('is_commander', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['decklist_id'], ['decklists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_card_tournament_usage_card_id', 'card_tournament_usage', ['card_id'], unique=False)
    op.create_index('ix_card_tournament_usage_decklist_id', 'card_tournament_usage', ['decklist_id'], unique=False)
    op.create_unique_constraint('ix_card_tournament_usage_card_decklist', 'card_tournament_usage', ['card_id', 'decklist_id'])
    
    # Create news_articles table
    op.create_table(
        'news_articles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('external_id', sa.String(length=200), nullable=True),
        sa.Column('external_url', sa.String(length=500), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('tags', sa.String(length=500), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('upvotes', sa.Integer(), nullable=True),
        sa.Column('comments_count', sa.Integer(), nullable=True),
        sa.Column('views', sa.Integer(), nullable=True),
        sa.Column('raw_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_news_articles_published_at', 'news_articles', ['published_at'], unique=False)
    op.create_index('ix_news_articles_source', 'news_articles', ['source'], unique=False)
    op.create_index('ix_news_articles_external_id', 'news_articles', ['external_id'], unique=False)
    op.create_index('ix_news_articles_category', 'news_articles', ['category'], unique=False)
    op.create_unique_constraint('ix_news_articles_source_external_id', 'news_articles', ['source', 'external_id'])
    
    # Create card_news_mentions table
    op.create_table(
        'card_news_mentions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('mention_count', sa.Integer(), nullable=False),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('sentiment', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['article_id'], ['news_articles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_card_news_mentions_card_id', 'card_news_mentions', ['card_id'], unique=False)
    op.create_index('ix_card_news_mentions_article_id', 'card_news_mentions', ['article_id'], unique=False)
    op.create_unique_constraint('ix_card_news_mentions_card_article', 'card_news_mentions', ['card_id', 'article_id'])


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('card_news_mentions')
    op.drop_table('news_articles')
    op.drop_table('card_tournament_usage')
    op.drop_table('decklists')
    op.drop_table('tournaments')

