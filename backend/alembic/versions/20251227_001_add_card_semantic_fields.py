"""Add semantic search fields to cards table

Revision ID: 20251227_001
Revises: 010_tournament_news
Create Date: 2025-12-27

This migration adds fields to support semantic search and card matching:
- keywords: JSON array of card keywords (e.g., Flying, Trample)
- flavor_text: Card flavor text for display and matching
- edhrec_rank: EDHREC popularity ranking
- reserved_list: Whether the card is on the Reserved List
- meta_score: Calculated meta relevance score
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20251227_001'
down_revision: Union[str, None] = '010_tournament_news'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cards', sa.Column('keywords', sa.Text(), nullable=True))
    op.add_column('cards', sa.Column('flavor_text', sa.Text(), nullable=True))
    op.add_column('cards', sa.Column('edhrec_rank', sa.Integer(), nullable=True))
    op.add_column('cards', sa.Column('reserved_list', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('cards', sa.Column('meta_score', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('cards', 'meta_score')
    op.drop_column('cards', 'reserved_list')
    op.drop_column('cards', 'edhrec_rank')
    op.drop_column('cards', 'flavor_text')
    op.drop_column('cards', 'keywords')
