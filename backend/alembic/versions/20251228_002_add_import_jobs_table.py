"""Add import_jobs table for platform imports.

Revision ID: 20251228_002
Revises: 20251228_001_add_collection_wantlist_insights_tables
Create Date: 2025-12-28 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20251228_002"
down_revision: Union[str, None] = "20251228_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create import_jobs table."""
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("preview_data", sa.JSON(), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_cards", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unmatched_cards", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("errors_detail", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_import_jobs_user_id", "import_jobs", ["user_id"])
    op.create_index("ix_import_jobs_platform", "import_jobs", ["platform"])
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])
    op.create_index("ix_import_jobs_user_status", "import_jobs", ["user_id", "status"])
    op.create_index("ix_import_jobs_created", "import_jobs", ["created_at"])


def downgrade() -> None:
    """Drop import_jobs table."""
    op.drop_index("ix_import_jobs_created", table_name="import_jobs")
    op.drop_index("ix_import_jobs_user_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_platform", table_name="import_jobs")
    op.drop_index("ix_import_jobs_user_id", table_name="import_jobs")
    op.drop_table("import_jobs")
