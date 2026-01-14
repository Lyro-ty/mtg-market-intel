"""Add reputation and trade proposal tables.

Revision ID: 20260113_001
Revises: 20260111_003_add_market_aggregation_indexes
Create Date: 2026-01-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260113_001'
down_revision: Union[str, None] = 'add_market_aggregation_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create trade_proposals table first (reputation_reviews references it)
    op.create_table(
        'trade_proposals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proposer_id', sa.Integer(), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('parent_proposal_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('proposer_confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('recipient_confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['proposer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_proposal_id'], ['trade_proposals.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_trade_proposals_proposer_id', 'trade_proposals', ['proposer_id'])
    op.create_index('ix_trade_proposals_recipient_id', 'trade_proposals', ['recipient_id'])
    op.create_index('ix_trade_proposals_status', 'trade_proposals', ['status'])

    # Create trade_proposal_items table
    op.create_table(
        'trade_proposal_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proposal_id', sa.Integer(), nullable=False),
        sa.Column('side', sa.String(20), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, default=1),
        sa.Column('condition', sa.String(20), nullable=True),
        sa.Column('price_at_proposal', sa.Numeric(10, 2), nullable=True),
        sa.ForeignKeyConstraint(['proposal_id'], ['trade_proposals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_trade_proposal_items_proposal_id', 'trade_proposal_items', ['proposal_id'])

    # Create user_reputation table
    op.create_table(
        'user_reputation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('total_reviews', sa.Integer(), nullable=False, default=0),
        sa.Column('average_rating', sa.Numeric(3, 2), nullable=False, default=0.0),
        sa.Column('five_star_count', sa.Integer(), default=0),
        sa.Column('four_star_count', sa.Integer(), default=0),
        sa.Column('three_star_count', sa.Integer(), default=0),
        sa.Column('two_star_count', sa.Integer(), default=0),
        sa.Column('one_star_count', sa.Integer(), default=0),
        sa.Column('tier', sa.String(20), nullable=False, default='new'),
        sa.Column('last_calculated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_user_reputation_user_id', 'user_reputation', ['user_id'])

    # Create reputation_reviews table
    op.create_table(
        'reputation_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), nullable=False),
        sa.Column('reviewee_id', sa.Integer(), nullable=False),
        sa.Column('trade_id', sa.Integer(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('trade_type', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewee_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trade_id'], ['trade_proposals.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reviewer_id', 'reviewee_id', 'trade_id', name='uq_review_per_trade')
    )
    op.create_index('ix_reputation_reviews_reviewer_id', 'reputation_reviews', ['reviewer_id'])
    op.create_index('ix_reputation_reviews_reviewee_id', 'reputation_reviews', ['reviewee_id'])


def downgrade() -> None:
    op.drop_table('reputation_reviews')
    op.drop_table('user_reputation')
    op.drop_table('trade_proposal_items')
    op.drop_table('trade_proposals')
