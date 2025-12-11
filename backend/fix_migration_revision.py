"""
Fix migration revision IDs in the database.

This script updates the alembic_version table to use the new shorter revision IDs.
"""
import asyncio
import sys
from sqlalchemy import create_engine, text
from app.core.config import settings

def fix_revision_ids():
    """Update revision IDs in the database to match the new shorter names."""
    # Use sync engine for this operation
    engine = create_engine(settings.sync_database_url)
    
    with engine.connect() as conn:
        # Check current revision
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        current_revision = result.scalar()
        
        print(f"Current revision in database: {current_revision}")
        
        # Map old revision IDs to new ones
        revision_map = {
            '008_add_price_snapshot_indexes': '008_price_snapshot_idx',
            '009_add_price_snapshot_unique_constraint': '009_price_snapshot_unique',
            '010_add_tournament_news_tables': '010_tournament_news',
        }
        
        # Update if needed
        if current_revision in revision_map:
            new_revision = revision_map[current_revision]
            print(f"Updating revision from '{current_revision}' to '{new_revision}'")
            conn.execute(
                text("UPDATE alembic_version SET version_num = :new WHERE version_num = :old"),
                {"new": new_revision, "old": current_revision}
            )
            conn.commit()
            print(f"✓ Updated revision to: {new_revision}")
        elif current_revision in revision_map.values():
            print(f"✓ Revision already correct: {current_revision}")
        else:
            print(f"⚠ Unknown revision: {current_revision}")
            print("Available revisions to update:")
            for old, new in revision_map.items():
                print(f"  {old} → {new}")

if __name__ == "__main__":
    try:
        fix_revision_ids()
        print("\n✓ Migration revision fix completed!")
        print("You can now run: docker-compose exec backend alembic upgrade head")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)

