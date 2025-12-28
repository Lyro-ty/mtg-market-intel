"""Merge migration heads

Revision ID: 20251228_merge
Revises: 013_continuous_aggregates, 20251227_003
Create Date: 2025-12-28
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20251228_merge'
down_revision: Union[str, tuple[str, ...], None] = ('013_continuous_aggregates', '20251227_003')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
