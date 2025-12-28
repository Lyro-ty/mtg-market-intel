"""Enable TimescaleDB extension and create condition/language enums

Revision ID: 011_enable_timescaledb
Revises: 010_tournament_news
Create Date: 2024-12-25

This migration enables the TimescaleDB extension and creates
PostgreSQL enums for card conditions and languages to ensure
data consistency across all price snapshots.

IMPORTANT: This migration requires the TimescaleDB extension to be
available in PostgreSQL. Make sure you're using the timescale/timescaledb
Docker image instead of postgres:16-alpine.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '011_enable_timescaledb'
down_revision: Union[str, None] = '010_tournament_news'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable TimescaleDB and create enums."""

    # Enable TimescaleDB extension
    # This is safe to run even if already enabled
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # Create card_condition enum
    # Using DO block for idempotent creation
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE card_condition AS ENUM (
                'MINT',
                'NEAR_MINT',
                'LIGHTLY_PLAYED',
                'MODERATELY_PLAYED',
                'HEAVILY_PLAYED',
                'DAMAGED'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Create card_language enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE card_language AS ENUM (
                'English',
                'Japanese',
                'German',
                'French',
                'Italian',
                'Spanish',
                'Portuguese',
                'Korean',
                'Chinese Simplified',
                'Chinese Traditional',
                'Russian',
                'Phyrexian'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)


def downgrade() -> None:
    """Remove enums and TimescaleDB extension."""

    # Note: We cannot drop the extension if there are hypertables
    # So we only drop the enums here

    # Drop enums if they exist and are not in use
    op.execute("""
        DO $$ BEGIN
            DROP TYPE IF EXISTS card_language;
        EXCEPTION
            WHEN dependent_objects_still_exist THEN NULL;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            DROP TYPE IF EXISTS card_condition;
        EXCEPTION
            WHEN dependent_objects_still_exist THEN NULL;
        END $$;
    """)

    # Note: Not dropping TimescaleDB extension as it may be used by other tables
    # op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE")
