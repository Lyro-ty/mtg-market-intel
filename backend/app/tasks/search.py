"""
Search-related Celery tasks.

Handles embedding refresh and search index maintenance.
"""
from datetime import datetime, timezone
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select

from app.models import Card, CardFeatureVector
from app.services.vectorization.service import VectorizationService
from app.services.vectorization.ingestion import vectorize_card_by_attrs
from app.tasks.utils import create_task_session_maker, run_async

logger = structlog.get_logger()


@shared_task(
    bind=True,
    name="app.tasks.search.refresh_embeddings",
    max_retries=2,
    default_retry_delay=600,
    autoretry_for=(Exception,),
)
def refresh_embeddings(self, batch_size: int = 100, force: bool = False) -> dict[str, Any]:
    """
    Refresh card embeddings for semantic search.

    Processes cards that:
    - Have no embedding yet, or
    - Were updated since last embedding (if force=False)

    Args:
        batch_size: Number of cards to process per batch
        force: If True, re-embed all cards regardless of status

    Returns:
        Dict with processing statistics
    """
    return run_async(_refresh_embeddings_async(batch_size, force))


async def _refresh_embeddings_async(batch_size: int, force: bool) -> dict[str, Any]:
    """Async implementation of embedding refresh."""
    session_maker, engine = create_task_session_maker()
    vectorizer = VectorizationService()

    stats: dict[str, Any] = {
        "cards_processed": 0,
        "embeddings_created": 0,
        "embeddings_updated": 0,
        "errors": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with session_maker() as db:
            if force:
                # Get all cards
                query = select(Card)
            else:
                # Get cards without embeddings
                subquery = select(CardFeatureVector.card_id)
                query = select(Card).where(Card.id.notin_(subquery))

            result = await db.execute(query)
            cards = result.scalars().all()

            logger.info(
                "Starting embedding refresh",
                total_cards=len(cards),
                force=force,
            )

            for card in cards:
                try:
                    # Prepare card attributes
                    card_attrs = {
                        "name": card.name,
                        "type_line": card.type_line,
                        "oracle_text": card.oracle_text,
                        "rarity": card.rarity,
                        "cmc": card.cmc,
                        "colors": card.colors,
                        "mana_cost": card.mana_cost,
                    }

                    # Check if embedding exists
                    existing_query = select(CardFeatureVector).where(
                        CardFeatureVector.card_id == card.id
                    )
                    existing_result = await db.execute(existing_query)
                    existing = existing_result.scalar_one_or_none()

                    # Create or update embedding
                    vector_obj = await vectorize_card_by_attrs(
                        db, card.id, card_attrs, vectorizer
                    )

                    if vector_obj:
                        if existing:
                            stats["embeddings_updated"] += 1
                        else:
                            stats["embeddings_created"] += 1

                    stats["cards_processed"] += 1

                    # Commit in batches
                    if stats["cards_processed"] % batch_size == 0:
                        await db.commit()
                        logger.info(
                            "Embedding batch committed",
                            processed=stats["cards_processed"],
                        )

                except Exception as e:
                    stats["errors"] += 1
                    logger.warning(
                        "Failed to embed card",
                        card_id=card.id,
                        error=str(e),
                    )

            # Final commit
            await db.commit()

    except Exception as e:
        logger.error("Embedding refresh failed", error=str(e))
        stats["error_message"] = str(e)

    finally:
        await engine.dispose()
        vectorizer.close()

    stats["completed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Embedding refresh completed",
        **stats,
    )

    return stats
