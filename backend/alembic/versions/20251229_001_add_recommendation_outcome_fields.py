"""Add recommendation outcome tracking fields.

Revision ID: 20251229_001
Revises: 20251228_004_add_saved_searches_table
Create Date: 2025-12-29

Adds fields to track recommendation outcomes for accuracy measurement:
- outcome_evaluated_at: When the outcome was evaluated
- outcome_price_end: Price at horizon expiry
- outcome_price_peak: Best price during horizon
- outcome_price_peak_at: When peak was reached
- accuracy_score_end: Accuracy based on end price
- accuracy_score_peak: Accuracy based on peak price
- actual_profit_pct_end: Actual profit if held to end
- actual_profit_pct_peak: Actual profit at optimal exit
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251229_001"
down_revision = "20251228_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add outcome tracking fields
    op.add_column(
        "recommendations",
        sa.Column("outcome_evaluated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "recommendations",
        sa.Column("outcome_price_end", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "recommendations",
        sa.Column("outcome_price_peak", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "recommendations",
        sa.Column("outcome_price_peak_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add accuracy scores (0.0 to 1.0)
    op.add_column(
        "recommendations",
        sa.Column("accuracy_score_end", sa.Numeric(3, 2), nullable=True),
    )
    op.add_column(
        "recommendations",
        sa.Column("accuracy_score_peak", sa.Numeric(3, 2), nullable=True),
    )

    # Add actual results for analysis
    op.add_column(
        "recommendations",
        sa.Column("actual_profit_pct_end", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "recommendations",
        sa.Column("actual_profit_pct_peak", sa.Numeric(10, 2), nullable=True),
    )

    # Add indexes for querying outcomes
    op.create_index(
        "ix_recommendations_outcome_evaluated",
        "recommendations",
        ["outcome_evaluated_at"],
    )
    op.create_index(
        "ix_recommendations_accuracy",
        "recommendations",
        ["accuracy_score_end"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_recommendations_accuracy", table_name="recommendations")
    op.drop_index("ix_recommendations_outcome_evaluated", table_name="recommendations")

    # Drop columns
    op.drop_column("recommendations", "actual_profit_pct_peak")
    op.drop_column("recommendations", "actual_profit_pct_end")
    op.drop_column("recommendations", "accuracy_score_peak")
    op.drop_column("recommendations", "accuracy_score_end")
    op.drop_column("recommendations", "outcome_price_peak_at")
    op.drop_column("recommendations", "outcome_price_peak")
    op.drop_column("recommendations", "outcome_price_end")
    op.drop_column("recommendations", "outcome_evaluated_at")
