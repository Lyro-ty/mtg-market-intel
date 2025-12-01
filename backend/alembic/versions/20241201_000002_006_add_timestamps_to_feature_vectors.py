"""Add timestamps to feature vector tables

Revision ID: 006_add_timestamps_to_feature_vectors
Revises: 005_feature_vectors
Create Date: 2024-12-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_timestamps_to_feature_vectors'
down_revision: Union[str, None] = '005_feature_vectors'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add created_at and updated_at to card_feature_vectors
    op.add_column('card_feature_vectors', 
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column('card_feature_vectors', 
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    
    # Add created_at and updated_at to listing_feature_vectors
    op.add_column('listing_feature_vectors', 
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column('listing_feature_vectors', 
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    op.drop_column('listing_feature_vectors', 'updated_at')
    op.drop_column('listing_feature_vectors', 'created_at')
    op.drop_column('card_feature_vectors', 'updated_at')
    op.drop_column('card_feature_vectors', 'created_at')

