"""add news tables

Revision ID: a1b2c3d4e5f6
Revises: 726e47e68fab
Create Date: 2025-12-31 04:19:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '5ad6dd9254e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create news_articles table
    op.create_table(
        'news_articles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('author', sa.String(100), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('categories', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url')
    )
    op.create_index('ix_news_articles_source', 'news_articles', ['source'])
    op.create_index('ix_news_articles_published_at', 'news_articles', ['published_at'])
    op.create_index('ix_news_articles_source_published', 'news_articles', ['source', 'published_at'])

    # Create card_news_mentions table
    op.create_table(
        'card_news_mentions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('mention_context', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['article_id'], ['news_articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('article_id', 'card_id', name='uq_card_news_mention')
    )
    op.create_index('ix_card_news_mentions_article_id', 'card_news_mentions', ['article_id'])
    op.create_index('ix_card_news_mentions_card_id', 'card_news_mentions', ['card_id'])
    op.create_index('ix_card_news_mentions_card_article', 'card_news_mentions', ['card_id', 'article_id'])


def downgrade() -> None:
    op.drop_table('card_news_mentions')
    op.drop_table('news_articles')
