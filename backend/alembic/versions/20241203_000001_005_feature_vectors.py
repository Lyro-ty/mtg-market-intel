"""Add feature vector tables for ML training

Revision ID: 005_feature_vectors
Revises: 004_user_settings
Create Date: 2024-12-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_feature_vectors'
down_revision: Union[str, None] = '004_user_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create card_feature_vectors table
    op.create_table(
        'card_feature_vectors',
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('feature_vector', sa.LargeBinary(), nullable=False),
        sa.Column('feature_dim', sa.Integer(), nullable=False),
        sa.Column('model_version', sa.String(), nullable=False, server_default='all-MiniLM-L6-v2'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('card_id')
    )
    op.create_index('ix_card_feature_vectors_card_id', 'card_feature_vectors', ['card_id'])
    
    # Create listing_feature_vectors table
    op.create_table(
        'listing_feature_vectors',
        sa.Column('listing_id', sa.Integer(), nullable=False),
        sa.Column('feature_vector', sa.LargeBinary(), nullable=False),
        sa.Column('feature_dim', sa.Integer(), nullable=False),
        sa.Column('model_version', sa.String(), nullable=False, server_default='all-MiniLM-L6-v2'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('listing_id')
    )
    op.create_index('ix_listing_feature_vectors_listing_id', 'listing_feature_vectors', ['listing_id'])


def downgrade() -> None:
    op.drop_index('ix_listing_feature_vectors_listing_id', table_name='listing_feature_vectors')
    op.drop_table('listing_feature_vectors')
    op.drop_index('ix_card_feature_vectors_card_id', table_name='card_feature_vectors')
    op.drop_table('card_feature_vectors')

