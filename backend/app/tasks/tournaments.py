"""
Tournament data ingestion tasks.

Fetches tournament results from TopDeck.gg and updates card meta statistics.
"""
import asyncio
from typing import Any

import structlog
from celery import shared_task

from app.services.tournaments import TopDeckClient
from app.services.tournaments.ingestion import TournamentIngestionService
from app.tasks.utils import create_task_session_maker, run_async

logger = structlog.get_logger()


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="app.tasks.tournaments.ingest_recent")
def ingest_recent_tournaments(self) -> dict[str, Any]:
    """
    Ingest recent tournaments for all major formats.

    Fetches tournament data from TopDeck.gg for the past 30 days across
    major competitive formats. Updates tournament records, standings,
    decklists, and card meta statistics.

    Returns:
        Dictionary with ingestion results for each format
    """
    return run_async(_ingest_recent_tournaments_async())


async def _ingest_recent_tournaments_async() -> dict[str, Any]:
    """
    Async implementation of recent tournament ingestion.

    Processes tournaments for all major formats and updates meta statistics.
    """
    # Create session maker and engine
    session_maker, engine = create_task_session_maker()

    # Major competitive formats (case-sensitive for TopDeck.gg API)
    formats = ["Modern", "Pioneer", "Standard", "Legacy", "Vintage", "Pauper"]

    results = {
        "formats": {},
        "total_tournaments": 0,
        "total_errors": 0,
    }

    try:
        # Create TopDeck client
        async with TopDeckClient() as client:
            # Process each format
            for format in formats:
                logger.info("Processing format", format=format)

                format_result = {
                    "tournaments_fetched": 0,
                    "tournaments_created": 0,
                    "tournaments_updated": 0,
                    "meta_stats_updated": 0,
                    "errors": [],
                }

                try:
                    # Ingest recent tournaments
                    async with session_maker() as db:
                        service = TournamentIngestionService(db, client)

                        # Fetch and store tournaments (30 days)
                        ingestion_stats = await service.ingest_recent_tournaments(
                            format=format,
                            days=30
                        )

                        format_result.update(ingestion_stats)
                        results["total_tournaments"] += ingestion_stats.get("tournaments_fetched", 0)

                    # Update meta statistics for different periods
                    for period in ["7d", "30d", "90d"]:
                        try:
                            async with session_maker() as db:
                                service = TournamentIngestionService(db, client)
                                stats_updated = await service.update_card_meta_stats(
                                    format=format,
                                    period=period
                                )

                                if period == "30d":
                                    format_result["meta_stats_updated"] = stats_updated

                                logger.info(
                                    "Meta stats updated",
                                    format=format,
                                    period=period,
                                    count=stats_updated
                                )

                        except Exception as e:
                            error_msg = f"Failed to update meta stats for {format} ({period}): {str(e)}"
                            logger.error(error_msg, error=str(e))
                            format_result["errors"].append(error_msg)

                except Exception as e:
                    error_msg = f"Failed to process format {format}: {str(e)}"
                    logger.error(error_msg, error=str(e))
                    format_result["errors"].append(error_msg)

                results["formats"][format] = format_result
                results["total_errors"] += len(format_result["errors"])

        logger.info("Tournament ingestion completed", **results)

    except Exception as e:
        logger.error("Tournament ingestion task failed", error=str(e))
        results["fatal_error"] = str(e)
        raise

    finally:
        # Dispose engine to free resources
        await engine.dispose()

    return results


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="app.tasks.tournaments.ingest_format")
def ingest_format_tournaments(self, format: str, days: int = 30) -> dict[str, Any]:
    """
    Ingest recent tournaments for a specific format.

    Args:
        format: MTG format (modern, pioneer, standard, etc.)
        days: Number of days to look back (default: 30)

    Returns:
        Dictionary with ingestion statistics
    """
    return run_async(_ingest_format_tournaments_async(format, days))


async def _ingest_format_tournaments_async(format: str, days: int) -> dict[str, Any]:
    """
    Async implementation of format-specific tournament ingestion.

    Args:
        format: MTG format to ingest
        days: Number of days to look back
    """
    session_maker, engine = create_task_session_maker()

    results = {
        "format": format,
        "days": days,
        "tournaments_fetched": 0,
        "tournaments_created": 0,
        "errors": [],
    }

    try:
        async with TopDeckClient() as client:
            async with session_maker() as db:
                service = TournamentIngestionService(db, client)

                # Fetch and store tournaments
                stats = await service.ingest_recent_tournaments(
                    format=format,
                    days=days
                )

                results.update(stats)

        logger.info("Format tournament ingestion completed", **results)

    except Exception as e:
        error_msg = f"Failed to ingest {format} tournaments: {str(e)}"
        logger.error(error_msg, error=str(e))
        results["errors"].append(error_msg)
        raise

    finally:
        await engine.dispose()

    return results


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="app.tasks.tournaments.update_meta_stats")
def update_meta_stats(self, format: str, period: str = "30d") -> dict[str, Any]:
    """
    Update card meta statistics for a specific format and period.

    Args:
        format: MTG format (modern, pioneer, standard, etc.)
        period: Time period (7d, 30d, 90d)

    Returns:
        Dictionary with update statistics
    """
    return run_async(_update_meta_stats_async(format, period))


async def _update_meta_stats_async(format: str, period: str) -> dict[str, Any]:
    """
    Async implementation of meta stats update.

    Args:
        format: MTG format to update
        period: Time period for aggregation
    """
    session_maker, engine = create_task_session_maker()

    results = {
        "format": format,
        "period": period,
        "stats_updated": 0,
        "errors": [],
    }

    try:
        async with TopDeckClient() as client:
            async with session_maker() as db:
                service = TournamentIngestionService(db, client)

                # Update meta statistics
                count = await service.update_card_meta_stats(
                    format=format,
                    period=period
                )

                results["stats_updated"] = count

        logger.info("Meta stats update completed", **results)

    except Exception as e:
        error_msg = f"Failed to update meta stats for {format} ({period}): {str(e)}"
        logger.error(error_msg, error=str(e))
        results["errors"].append(error_msg)
        raise

    finally:
        await engine.dispose()

    return results
