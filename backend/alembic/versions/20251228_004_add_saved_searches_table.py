"""Add saved_searches table for user search queries.

Revision ID: 20251228_004
Revises: 20251228_003
Create Date: 2025-12-28 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20251228_004"
down_revision: Union[str, None] = "20251228_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create saved_searches table."""
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("query", sa.String(255), nullable=True),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("alert_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("alert_frequency", sa.String(20), nullable=False, server_default="never"),
        sa.Column("price_alert_threshold", sa.Float(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result_count", sa.Integer(), nullable=False, server_default="0"),
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
    op.create_index("ix_saved_searches_user_id", "saved_searches", ["user_id"])
    op.create_index(
        "ix_saved_searches_user_name",
        "saved_searches",
        ["user_id", "name"],
        unique=True,
    )


def downgrade() -> None:
    """Drop saved_searches table."""
    op.drop_index("ix_saved_searches_user_name", table_name="saved_searches")
    op.drop_index("ix_saved_searches_user_id", table_name="saved_searches")
    op.drop_table("saved_searches")
