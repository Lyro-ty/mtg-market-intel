"""Add portfolio_snapshots table for tracking collection value history.

Revision ID: 20251228_003
Revises: 20251228_002
Create Date: 2025-12-28 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20251228_003"
down_revision: Union[str, None] = "20251228_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create portfolio_snapshots table."""
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_cards", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_cards", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("value_change_1d", sa.Float(), nullable=True),
        sa.Column("value_change_7d", sa.Float(), nullable=True),
        sa.Column("value_change_30d", sa.Float(), nullable=True),
        sa.Column("value_change_pct_1d", sa.Float(), nullable=True),
        sa.Column("value_change_pct_7d", sa.Float(), nullable=True),
        sa.Column("value_change_pct_30d", sa.Float(), nullable=True),
        sa.Column("breakdown", sa.JSON(), nullable=True),
        sa.Column("top_gainers", sa.JSON(), nullable=True),
        sa.Column("top_losers", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_portfolio_snapshots_user_id", "portfolio_snapshots", ["user_id"])
    op.create_index("ix_portfolio_snapshots_snapshot_date", "portfolio_snapshots", ["snapshot_date"])
    op.create_index(
        "ix_portfolio_snapshots_user_date",
        "portfolio_snapshots",
        ["user_id", "snapshot_date"],
        unique=True,
    )


def downgrade() -> None:
    """Drop portfolio_snapshots table."""
    op.drop_index("ix_portfolio_snapshots_user_date", table_name="portfolio_snapshots")
    op.drop_index("ix_portfolio_snapshots_snapshot_date", table_name="portfolio_snapshots")
    op.drop_index("ix_portfolio_snapshots_user_id", table_name="portfolio_snapshots")
    op.drop_table("portfolio_snapshots")
