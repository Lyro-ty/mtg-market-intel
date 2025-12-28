"""Refactor tournament tables for TopDeck.gg integration

Revision ID: 20251227_003
Revises: 20251227_002
Create Date: 2025-12-27

This migration refactors the tournament schema to align with TopDeck.gg data model:
- Restructures tournaments table for TopDeck.gg specific fields
- Adds tournament_standings table for player performance
- Refactors decklists to link to standings (not tournaments)
- Replaces card_tournament_usage with decklist_cards
- Adds card_meta_stats for aggregated tournament metrics
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251227_003'
down_revision: Union[str, None] = '20251227_002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing tables to recreate with new schema
    # Note: This is a destructive migration - any existing tournament data will be lost
    # Use op.execute for raw SQL - do NOT call conn.commit() as Alembic manages the transaction
    op.execute("DROP TABLE IF EXISTS card_tournament_usage CASCADE")
    op.execute("DROP TABLE IF EXISTS decklists CASCADE")
    op.execute("DROP TABLE IF EXISTS tournaments CASCADE")

    # Create tournaments table with TopDeck.gg schema
    op.create_table(
        'tournaments',
        sa.Column('id', sa.Integer(), nullable=False),
        # topdeck_id: String(100) allows alphanumeric IDs + room for future formats
        sa.Column('topdeck_id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('format', sa.String(length=50), nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('player_count', sa.Integer(), nullable=False),
        sa.Column('swiss_rounds', sa.Integer(), nullable=True),
        sa.Column('top_cut_size', sa.Integer(), nullable=True),
        sa.Column('city', sa.String(length=255), nullable=True),
        sa.Column('venue', sa.String(length=255), nullable=True),
        sa.Column('topdeck_url', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tournaments_topdeck_id', 'tournaments', ['topdeck_id'], unique=True)
    op.create_index('ix_tournaments_format', 'tournaments', ['format'], unique=False)
    op.create_index('ix_tournaments_date', 'tournaments', ['date'], unique=False)
    op.create_index('ix_tournaments_format_date', 'tournaments', ['format', 'date'], unique=False)
    op.create_index('ix_tournaments_date_desc', 'tournaments', ['date'], unique=False, postgresql_ops={'date': 'DESC'})

    # Create tournament_standings table
    op.create_table(
        'tournament_standings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('player_name', sa.String(length=255), nullable=False),
        sa.Column('player_id', sa.String(length=100), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('wins', sa.Integer(), nullable=False),
        sa.Column('losses', sa.Integer(), nullable=False),
        sa.Column('draws', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('win_rate', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('wins >= 0', name='check_wins_non_negative'),
        sa.CheckConstraint('losses >= 0', name='check_losses_non_negative'),
        sa.CheckConstraint('draws >= 0', name='check_draws_non_negative'),
        sa.CheckConstraint('win_rate >= 0 AND win_rate <= 1', name='check_win_rate_range'),
    )
    op.create_index('ix_tournament_standings_tournament_id', 'tournament_standings', ['tournament_id'], unique=False)
    op.create_index('ix_tournament_standings_tournament_rank', 'tournament_standings', ['tournament_id', 'rank'], unique=False)

    # Create decklists table (linked to standings)
    op.create_table(
        'decklists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('standing_id', sa.Integer(), nullable=False),
        sa.Column('archetype_name', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['standing_id'], ['tournament_standings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decklists_standing_id', 'decklists', ['standing_id'], unique=True)
    op.create_index('ix_decklists_archetype_name', 'decklists', ['archetype_name'], unique=False)

    # Create decklist_cards table
    op.create_table(
        'decklist_cards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('decklist_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('section', sa.Enum('mainboard', 'sideboard', 'commander', name='decklist_section'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['decklist_id'], ['decklists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('quantity > 0', name='check_quantity_positive'),
    )
    op.create_index('ix_decklist_cards_decklist_id', 'decklist_cards', ['decklist_id'], unique=False)
    op.create_index('ix_decklist_cards_card_id', 'decklist_cards', ['card_id'], unique=False)
    op.create_index('ix_decklist_cards_section', 'decklist_cards', ['section'], unique=False)
    op.create_index('ix_decklist_cards_decklist_section', 'decklist_cards', ['decklist_id', 'section'], unique=False)
    op.create_index('ix_decklist_cards_card_section', 'decklist_cards', ['card_id', 'section'], unique=False)

    # Create card_meta_stats table
    op.create_table(
        'card_meta_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('format', sa.String(length=50), nullable=False),
        sa.Column('period', sa.Enum('7d', '30d', '90d', name='meta_period'), nullable=False),
        sa.Column('deck_inclusion_rate', sa.Float(), nullable=False),
        sa.Column('avg_copies', sa.Float(), nullable=False),
        sa.Column('top8_rate', sa.Float(), nullable=False),
        sa.Column('win_rate_delta', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('deck_inclusion_rate >= 0 AND deck_inclusion_rate <= 1', name='check_inclusion_rate_range'),
        sa.CheckConstraint('avg_copies >= 0', name='check_avg_copies_non_negative'),
        sa.CheckConstraint('top8_rate >= 0 AND top8_rate <= 1', name='check_top8_rate_range'),
        sa.CheckConstraint('win_rate_delta >= -1 AND win_rate_delta <= 1', name='check_win_rate_delta_range'),
    )
    op.create_index('ix_card_meta_stats_card_id', 'card_meta_stats', ['card_id'], unique=False)
    op.create_index('ix_card_meta_stats_format', 'card_meta_stats', ['format'], unique=False)
    op.create_index('ix_card_meta_stats_card_format_period', 'card_meta_stats', ['card_id', 'format', 'period'], unique=True)
    op.create_index('ix_card_meta_stats_format_period', 'card_meta_stats', ['format', 'period'], unique=False)


def downgrade() -> None:
    # Drop new tables
    op.drop_table('card_meta_stats')
    op.drop_table('decklist_cards')
    op.drop_table('decklists')
    op.drop_table('tournament_standings')
    op.drop_table('tournaments')

    # Recreate old schema
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
