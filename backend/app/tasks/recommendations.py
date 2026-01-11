"""
Recommendation tasks for generating trading recommendations and evaluating outcomes.
"""
from datetime import date, datetime, timezone
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import select, and_

from app.core.utils import parse_setting_value
from app.models import AppSettings, Recommendation
from app.models.price_snapshot import PriceSnapshot
from app.services.agents.recommendation import RecommendationAgent
from app.services.outcomes.evaluator import OutcomeEvaluator
from app.tasks.utils import create_task_session_maker, run_async

logger = structlog.get_logger()


async def _get_settings_value(db, user_id: int | None, key: str, default: Any) -> Any:
    """
    Get a setting value from the database for a specific user.

    If user_id is None, tries to get from system user, otherwise uses default.
    """
    from app.models.settings import DEFAULT_SETTINGS

    # Try to get from specified user
    if user_id:
        query = select(AppSettings).where(
            AppSettings.user_id == user_id,
            AppSettings.key == key
        )
        result = await db.execute(query)
        setting = result.scalar_one_or_none()

        if setting:
            return parse_setting_value(setting.value, setting.value_type)

    # Try system user as fallback
    from app.models.user import User
    system_user_query = select(User).where(User.username == "system")
    system_result = await db.execute(system_user_query)
    system_user = system_result.scalar_one_or_none()

    if system_user:
        query = select(AppSettings).where(
            AppSettings.user_id == system_user.id,
            AppSettings.key == key
        )
        result = await db.execute(query)
        setting = result.scalar_one_or_none()

        if setting:
            return parse_setting_value(setting.value, setting.value_type)

    # Use default from DEFAULT_SETTINGS if available
    if key in DEFAULT_SETTINGS:
        return parse_setting_value(
            DEFAULT_SETTINGS[key]["value"],
            DEFAULT_SETTINGS[key]["value_type"]
        )

    return default


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def generate_recommendations(
    self,
    card_ids: list[int] | None = None,
    target_date: str | None = None,
) -> dict[str, Any]:
    """
    Generate recommendations for cards.
    
    Args:
        card_ids: Optional list of card IDs. None = cards with signals.
        target_date: Date string (YYYY-MM-DD). None = today.
        
    Returns:
        Recommendation generation results.
    """
    parsed_date = date.fromisoformat(target_date) if target_date else None
    return run_async(_generate_recommendations_async(card_ids, parsed_date))


async def _generate_recommendations_async(
    card_ids: list[int] | None,
    target_date: date | None,
) -> dict[str, Any]:
    """Async implementation of recommendation generation."""
    logger.info("Starting recommendation generation", card_ids=card_ids, date=target_date)
    
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Get settings (use None for user_id to get system/default settings)
            min_roi = await _get_settings_value(db, None, "min_roi_threshold", 0.10)
            min_confidence = await _get_settings_value(db, None, "min_confidence_threshold", 0.60)
            horizon_days = await _get_settings_value(db, None, "recommendation_horizon_days", 7)
            
            agent = RecommendationAgent(
                db,
                min_roi=min_roi,
                min_confidence=min_confidence,
                horizon_days=horizon_days,
            )
            
            results = await agent.run_recommendations(
                card_ids=card_ids,
                target_date=target_date,
            )
            
            logger.info("Recommendation generation completed", results=results)
            return results
    finally:
        await engine.dispose()


@shared_task(bind=True)
def generate_card_recommendations(
    self,
    card_id: int,
    target_date: str | None = None,
) -> dict[str, Any]:
    """
    Generate recommendations for a single card.
    
    Args:
        card_id: Card ID to process.
        target_date: Date string (YYYY-MM-DD). None = today.
        
    Returns:
        Recommendations for the card.
    """
    parsed_date = date.fromisoformat(target_date) if target_date else None
    return run_async(_generate_card_recommendations_async(card_id, parsed_date))


async def _generate_card_recommendations_async(
    card_id: int,
    target_date: date | None,
) -> dict[str, Any]:
    """Async implementation of single card recommendation generation."""
    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            # Get settings (use None for user_id to get system/default settings)
            min_roi = await _get_settings_value(db, None, "min_roi_threshold", 0.10)
            min_confidence = await _get_settings_value(db, None, "min_confidence_threshold", 0.60)
            horizon_days = await _get_settings_value(db, None, "recommendation_horizon_days", 7)
            
            agent = RecommendationAgent(
                db,
                min_roi=min_roi,
                min_confidence=min_confidence,
                horizon_days=horizon_days,
            )
            
            recommendations = await agent.generate_recommendations(card_id, target_date)
            await db.commit()
            
            return {
                "card_id": card_id,
                "date": str(target_date or date.today()),
                "recommendations": [
                    {
                        "action": r.action,
                        "confidence": float(r.confidence),
                        "rationale": r.rationale,
                        "current_price": float(r.current_price) if r.current_price else None,
                        "target_price": float(r.target_price) if r.target_price else None,
                        "potential_profit_pct": float(r.potential_profit_pct) if r.potential_profit_pct else None,
                    }
                    for r in recommendations
                ],
            }
    finally:
        await engine.dispose()


@shared_task(bind=True)
def cleanup_old_recommendations(self, days: int = 30) -> dict[str, Any]:
    """
    Clean up old inactive recommendations.
    
    Args:
        days: Delete recommendations older than this many days.
        
    Returns:
        Cleanup results.
    """
    return run_async(_cleanup_old_recommendations_async(days))


async def _cleanup_old_recommendations_async(days: int) -> dict[str, Any]:
    """Async implementation of recommendation cleanup."""
    from datetime import datetime, timedelta, timezone
    from app.models import Recommendation
    from sqlalchemy import delete

    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            # Delete old inactive recommendations
            stmt = delete(Recommendation).where(
                Recommendation.is_active == False,
                Recommendation.created_at < cutoff,
            )
            result = await db.execute(stmt)
            deleted = result.rowcount

            await db.commit()

            logger.info("Cleaned up old recommendations", deleted=deleted, cutoff=str(cutoff))

            return {
                "deleted": deleted,
                "cutoff_date": str(cutoff),
            }
    finally:
        await engine.dispose()


# Batch size for outcome evaluation
OUTCOME_EVALUATION_BATCH_SIZE = 100


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def evaluate_outcomes(
    self,
    batch_size: int = OUTCOME_EVALUATION_BATCH_SIZE,
) -> dict[str, Any]:
    """
    Evaluate outcomes for expired recommendations.

    This task queries for unevaluated expired recommendations,
    fetches price snapshots for each recommendation's horizon period,
    and uses OutcomeEvaluator to compute accuracy metrics.

    Args:
        batch_size: Maximum number of recommendations to process per run.

    Returns:
        Evaluation results summary including processed, succeeded, skipped, and errors.
    """
    return run_async(_evaluate_outcomes_async(batch_size))


async def _evaluate_outcomes_async(batch_size: int) -> dict[str, Any]:
    """Async implementation of outcome evaluation."""
    logger.info("Starting recommendation outcome evaluation", batch_size=batch_size)

    session_maker, engine = create_task_session_maker()
    try:
        async with session_maker() as db:
            now = datetime.now(timezone.utc)

            # Query for unevaluated expired recommendations
            # Only evaluate after deactivation (is_active = false)
            query = (
                select(Recommendation)
                .where(
                    and_(
                        Recommendation.valid_until < now,
                        Recommendation.outcome_evaluated_at.is_(None),
                        Recommendation.is_active == False,
                    )
                )
                .order_by(Recommendation.valid_until.asc())
                .limit(batch_size)
            )

            result = await db.execute(query)
            recommendations = list(result.scalars().all())

            if not recommendations:
                logger.info("No unevaluated recommendations found")
                return {
                    "started_at": now.isoformat(),
                    "total_processed": 0,
                    "successful_evaluations": 0,
                    "skipped_no_data": 0,
                    "errors": 0,
                    "error_details": [],
                }

            logger.info(
                "Found recommendations to evaluate",
                count=len(recommendations),
            )

            evaluator = OutcomeEvaluator()

            results = {
                "started_at": now.isoformat(),
                "total_processed": 0,
                "successful_evaluations": 0,
                "skipped_no_data": 0,
                "errors": 0,
                "error_details": [],
            }

            for recommendation in recommendations:
                results["total_processed"] += 1

                try:
                    # Fetch price snapshots for the recommendation's horizon period
                    # From created_at to valid_until
                    snapshots_query = (
                        select(PriceSnapshot)
                        .where(
                            and_(
                                PriceSnapshot.card_id == recommendation.card_id,
                                PriceSnapshot.time >= recommendation.created_at,
                                PriceSnapshot.time <= recommendation.valid_until,
                            )
                        )
                        .order_by(PriceSnapshot.time.asc())
                    )

                    snapshots_result = await db.execute(snapshots_query)
                    snapshots = list(snapshots_result.scalars().all())

                    # Evaluate the recommendation
                    outcome = evaluator.evaluate_recommendation(recommendation, snapshots)

                    if outcome is None:
                        # No snapshots or insufficient data - skip but don't mark as evaluated
                        # This allows retry on next run when more data may be available
                        results["skipped_no_data"] += 1
                        logger.debug(
                            "Skipped recommendation - no price data",
                            recommendation_id=recommendation.id,
                            card_id=recommendation.card_id,
                            snapshots_count=len(snapshots),
                        )
                        continue

                    # Update the recommendation with outcome fields
                    recommendation.outcome_evaluated_at = now
                    recommendation.outcome_price_end = outcome.price_end
                    recommendation.outcome_price_peak = outcome.price_peak
                    recommendation.outcome_price_peak_at = outcome.price_peak_at
                    recommendation.accuracy_score_end = outcome.accuracy_end
                    recommendation.accuracy_score_peak = outcome.accuracy_peak
                    recommendation.actual_profit_pct_end = outcome.profit_pct_end
                    recommendation.actual_profit_pct_peak = outcome.profit_pct_peak

                    results["successful_evaluations"] += 1

                    logger.debug(
                        "Evaluated recommendation outcome",
                        recommendation_id=recommendation.id,
                        card_id=recommendation.card_id,
                        action=recommendation.action,
                        accuracy_end=outcome.accuracy_end,
                        accuracy_peak=outcome.accuracy_peak,
                        profit_pct_end=outcome.profit_pct_end,
                    )

                except Exception as e:
                    results["errors"] += 1
                    error_msg = f"Recommendation {recommendation.id}: {str(e)}"
                    results["error_details"].append(error_msg)
                    logger.warning(
                        "Failed to evaluate recommendation",
                        recommendation_id=recommendation.id,
                        card_id=recommendation.card_id,
                        error=str(e),
                    )
                    # Continue processing other recommendations
                    continue

            # Commit all updates
            await db.commit()

            results["completed_at"] = datetime.now(timezone.utc).isoformat()

            logger.info(
                "Recommendation outcome evaluation completed",
                total_processed=results["total_processed"],
                successful=results["successful_evaluations"],
                skipped=results["skipped_no_data"],
                errors=results["errors"],
            )

            return results
    finally:
        await engine.dispose()

