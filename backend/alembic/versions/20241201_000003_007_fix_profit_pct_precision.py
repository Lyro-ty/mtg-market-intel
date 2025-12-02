"""Fix potential_profit_pct precision to handle large percentages

Revision ID: 007_fix_profit_pct
Revises: 006_feature_vectors_ts
Create Date: 2024-12-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_fix_profit_pct'
down_revision: Union[str, None] = '006_feature_vectors_ts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Increase precision of potential_profit_pct from NUMERIC(5,2) to NUMERIC(10,2)
    # This allows values up to 99,999,999.99 (though we cap at 9999.99 in code)
    op.alter_column(
        'recommendations',
        'potential_profit_pct',
        existing_type=sa.Numeric(5, 2),
        type_=sa.Numeric(10, 2),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Revert to original precision (may fail if data exceeds limit)
    op.alter_column(
        'recommendations',
        'potential_profit_pct',
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(5, 2),
        existing_nullable=True,
    )


