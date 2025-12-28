"""
Sets synchronization task for MTG set data from Scryfall.

Fetches and synchronizes MTG sets from Scryfall API to ensure
accurate set metadata for collection completion tracking.
"""
from datetime import datetime
from typing import Any

import httpx
import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.mtg_set import MTGSet
from app.tasks.utils import create_task_session_maker, run_async

logger = structlog.get_logger()

SCRYFALL_SETS_URL = "https://api.scryfall.com/sets"


@shared_task(name="sync_mtg_sets", bind=True, max_retries=3, default_retry_delay=300)
def sync_mtg_sets(self) -> dict[str, Any]:
    """
    Sync MTG sets from Scryfall API.

    Fetches https://api.scryfall.com/sets
    For each set:
    - Create or update MTGSet record
    - Update card_count from Scryfall data

    Runs daily via celery beat.

    Returns:
        Dictionary with sync statistics.
    """
    return run_async(_sync_mtg_sets_async())


async def _sync_mtg_sets_async() -> dict[str, Any]:
    """
    Async implementation of MTG sets sync.

    Fetches all sets from Scryfall and upserts them into the database.
    """
    logger.info("Starting MTG sets sync from Scryfall")

    results = {
        "sets_fetched": 0,
        "sets_created": 0,
        "sets_updated": 0,
        "errors": [],
    }

    session_maker, engine = create_task_session_maker()

    try:
        # Fetch sets from Scryfall API
        async with httpx.AsyncClient(timeout=60.0) as client:
            logger.info("Fetching sets from Scryfall API", url=SCRYFALL_SETS_URL)
            response = await client.get(SCRYFALL_SETS_URL)
            response.raise_for_status()
            data = response.json()

        sets_data = data.get("data", [])
        results["sets_fetched"] = len(sets_data)
        logger.info("Fetched sets from Scryfall", count=len(sets_data))

        async with session_maker() as db:
            # Get existing set codes for tracking creates vs updates
            existing_codes_result = await db.execute(
                select(MTGSet.code)
            )
            existing_codes = {row[0] for row in existing_codes_result.fetchall()}

            for set_data in sets_data:
                try:
                    set_code = set_data.get("code")
                    if not set_code:
                        logger.warning("Set missing code, skipping", set_data=set_data)
                        continue

                    # Parse released_at date if present
                    released_at = None
                    released_at_str = set_data.get("released_at")
                    if released_at_str:
                        try:
                            released_at = datetime.strptime(released_at_str, "%Y-%m-%d").date()
                        except ValueError:
                            logger.warning(
                                "Invalid released_at format",
                                set_code=set_code,
                                released_at=released_at_str
                            )

                    # Prepare values for upsert
                    values = {
                        "code": set_code,
                        "name": set_data.get("name", ""),
                        "set_type": set_data.get("set_type", "unknown"),
                        "released_at": released_at,
                        "card_count": set_data.get("card_count", 0),
                        "icon_svg_uri": set_data.get("icon_svg_uri"),
                        "scryfall_id": set_data.get("id"),
                        "parent_set_code": set_data.get("parent_set_code"),
                        "is_digital": set_data.get("digital", False),
                        "is_foil_only": set_data.get("foil_only", False),
                    }

                    # Upsert using PostgreSQL ON CONFLICT
                    stmt = pg_insert(MTGSet).values(**values)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["code"],
                        set_={
                            "name": stmt.excluded.name,
                            "set_type": stmt.excluded.set_type,
                            "released_at": stmt.excluded.released_at,
                            "card_count": stmt.excluded.card_count,
                            "icon_svg_uri": stmt.excluded.icon_svg_uri,
                            "scryfall_id": stmt.excluded.scryfall_id,
                            "parent_set_code": stmt.excluded.parent_set_code,
                            "is_digital": stmt.excluded.is_digital,
                            "is_foil_only": stmt.excluded.is_foil_only,
                        }
                    )

                    await db.execute(stmt)

                    # Track creates vs updates
                    if set_code in existing_codes:
                        results["sets_updated"] += 1
                    else:
                        results["sets_created"] += 1
                        existing_codes.add(set_code)

                except Exception as e:
                    error_msg = f"Error processing set {set_data.get('code', 'unknown')}: {str(e)}"
                    logger.error(error_msg, error=str(e))
                    results["errors"].append(error_msg)

            # Commit all changes
            await db.commit()

        logger.info(
            "MTG sets sync completed",
            sets_fetched=results["sets_fetched"],
            sets_created=results["sets_created"],
            sets_updated=results["sets_updated"],
            errors_count=len(results["errors"])
        )

    except httpx.HTTPError as e:
        error_msg = f"HTTP error fetching sets from Scryfall: {str(e)}"
        logger.error(error_msg, error=str(e))
        results["errors"].append(error_msg)
        raise

    except Exception as e:
        error_msg = f"Unexpected error during sets sync: {str(e)}"
        logger.error(error_msg, error=str(e))
        results["errors"].append(error_msg)
        raise

    finally:
        # Dispose engine to free resources
        await engine.dispose()

    return results
