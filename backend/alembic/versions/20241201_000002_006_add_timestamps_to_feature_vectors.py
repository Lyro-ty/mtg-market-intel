"""Add timestamps to feature vector tables

Revision ID: 006_feature_vectors_ts
Revises: 005_feature_vectors
Create Date: 2024-12-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_feature_vectors_ts'
down_revision: Union[str, None] = '005_feature_vectors'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: Migration 005 already creates these tables with created_at and updated_at columns.
    # This migration is now a no-op to avoid "column already exists" errors.
    # The columns were originally added in migration 005.
    pass


def downgrade() -> None:
    # No-op since columns are created in migration 005
    pass

