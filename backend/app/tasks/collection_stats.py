"""
Collection stats tasks for updating user collection metrics.

Includes:
- Batch updates for stale collection stats
- Single user updates for background refresh
- Milestone detection and notification creation
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.models import (
    Card,
    CollectionStats,
    InventoryItem,
    MilestoneType,
    MTGSet,
    Notification,
    NotificationPriority,
    NotificationType,
    UserMilestone,
)
from app.tasks.utils import create_task_session_maker, run_async

logger = structlog.get_logger()

# Milestone thresholds
CARDS_OWNED_THRESHOLDS = [10, 50, 100, 250, 500, 1000, 2500, 5000]
COLLECTION_VALUE_THRESHOLDS = [100, 500, 1000, 2500, 5000, 10000]
SETS_STARTED_THRESHOLDS = [5, 10, 25, 50]


@shared_task(name="update_collection_stats")
def update_collection_stats() -> dict[str, Any]:
    """
    Update collection stats for all users with stale stats.

    For each user where CollectionStats.is_stale=True:
    - Recalculate total_cards, unique_cards, total_value
    - Recalculate sets_started, sets_completed
    - Find top_set_code and top_set_completion
    - Set is_stale=False and update last_calculated_at
    - Check for new milestones and create notifications

    Runs every hour via celery beat.
    """
    return run_async(_update_collection_stats_async())


async def _update_collection_stats_async() -> dict[str, Any]:
    """Async implementation of collection stats update."""
    logger.info("Starting collection stats update for stale users")

    session_maker, engine = create_task_session_maker()
    results = {
        "users_processed": 0,
        "milestones_created": 0,
        "errors": [],
    }

    try:
        async with session_maker() as db:
            # Find all stale collection stats
            stale_stats_query = select(CollectionStats).where(
                CollectionStats.is_stale == True  # noqa: E712
            ).options(joinedload(CollectionStats.user))

            stale_stats_result = await db.execute(stale_stats_query)
            stale_stats = stale_stats_result.scalars().all()

            logger.info(f"Found {len(stale_stats)} users with stale stats")

            for stats in stale_stats:
                try:
                    milestones = await _calculate_user_stats(db, stats)
                    results["users_processed"] += 1
                    results["milestones_created"] += milestones
                except Exception as e:
                    logger.error(
                        "Error updating stats for user",
                        user_id=stats.user_id,
                        error=str(e)
                    )
                    results["errors"].append(f"user {stats.user_id}: {str(e)}")

            await db.commit()

    finally:
        await engine.dispose()

    logger.info("Collection stats update completed", results=results)
    return results


@shared_task(name="update_user_collection_stats")
def update_user_collection_stats(user_id: int) -> dict[str, Any]:
    """Update stats for a specific user (for background refresh)."""
    return run_async(_update_user_collection_stats_async(user_id))


async def _update_user_collection_stats_async(user_id: int) -> dict[str, Any]:
    """Async implementation of single user stats update."""
    logger.info("Updating collection stats for user", user_id=user_id)

    session_maker, engine = create_task_session_maker()

    try:
        async with session_maker() as db:
            # Get or create collection stats for user
            stats_query = select(CollectionStats).where(
                CollectionStats.user_id == user_id
            )
            stats_result = await db.execute(stats_query)
            stats = stats_result.scalar_one_or_none()

            if not stats:
                # Create new stats record
                stats = CollectionStats(user_id=user_id, is_stale=True)
                db.add(stats)
                await db.flush()

            milestones_created = await _calculate_user_stats(db, stats)
            await db.commit()

            return {
                "user_id": user_id,
                "total_cards": stats.total_cards,
                "unique_cards": stats.unique_cards,
                "total_value": float(stats.total_value),
                "sets_started": stats.sets_started,
                "sets_completed": stats.sets_completed,
                "top_set_code": stats.top_set_code,
                "top_set_completion": float(stats.top_set_completion) if stats.top_set_completion else None,
                "milestones_created": milestones_created,
            }
    finally:
        await engine.dispose()


async def _calculate_user_stats(db, stats: CollectionStats) -> int:
    """
    Calculate and update stats for a user.

    Returns the number of new milestones created.
    """
    user_id = stats.user_id

    # Calculate total_cards and total_value
    totals_query = select(
        func.sum(InventoryItem.quantity).label("total_cards"),
        func.sum(
            InventoryItem.quantity * func.coalesce(InventoryItem.current_value, 0)
        ).label("total_value"),
        func.count(func.distinct(InventoryItem.card_id)).label("unique_cards")
    ).where(InventoryItem.user_id == user_id)

    totals_result = await db.execute(totals_query)
    totals = totals_result.one()

    old_total_cards = stats.total_cards
    old_total_value = stats.total_value
    old_sets_started = stats.sets_started

    stats.total_cards = totals.total_cards or 0
    stats.total_value = Decimal(str(totals.total_value or 0))
    stats.unique_cards = totals.unique_cards or 0

    # Calculate set completion stats
    # Get all set codes with cards in user's inventory
    set_counts_query = (
        select(
            Card.set_code,
            func.count(func.distinct(InventoryItem.card_id)).label("owned_count")
        )
        .join(InventoryItem, InventoryItem.card_id == Card.id)
        .where(InventoryItem.user_id == user_id)
        .group_by(Card.set_code)
    )

    set_counts_result = await db.execute(set_counts_query)
    set_counts = set_counts_result.all()

    # Get total cards per set from MTGSet table
    set_codes = [sc.set_code for sc in set_counts]
    if set_codes:
        set_totals_query = select(MTGSet.code, MTGSet.card_count).where(
            MTGSet.code.in_(set_codes)
        )
        set_totals_result = await db.execute(set_totals_query)
        set_totals = {row.code: row.card_count for row in set_totals_result.all()}
    else:
        set_totals = {}

    # Calculate completion percentages
    set_completions = []
    completed_sets = 0

    for sc in set_counts:
        total_in_set = set_totals.get(sc.set_code, 0)
        if total_in_set > 0:
            completion_pct = (sc.owned_count / total_in_set) * 100
            set_completions.append((sc.set_code, completion_pct))
            if completion_pct >= 100:
                completed_sets += 1

    stats.sets_started = len(set_counts)
    stats.sets_completed = completed_sets

    # Find top set
    if set_completions:
        top_set = max(set_completions, key=lambda x: x[1])
        stats.top_set_code = top_set[0]
        stats.top_set_completion = Decimal(str(round(top_set[1], 2)))
    else:
        stats.top_set_code = None
        stats.top_set_completion = None

    # Update cache metadata
    stats.is_stale = False
    stats.last_calculated_at = datetime.now(timezone.utc)

    # Check for milestones
    milestones_created = await _check_milestones(
        db,
        user_id,
        old_total_cards=old_total_cards,
        new_total_cards=stats.total_cards,
        old_total_value=old_total_value,
        new_total_value=stats.total_value,
        old_sets_started=old_sets_started,
        new_sets_started=stats.sets_started,
    )

    return milestones_created


async def _check_milestones(
    db,
    user_id: int,
    old_total_cards: int,
    new_total_cards: int,
    old_total_value: Decimal,
    new_total_value: Decimal,
    old_sets_started: int,
    new_sets_started: int,
) -> int:
    """Check for and create new milestones. Returns count of new milestones."""
    milestones_created = 0

    # Get existing milestones for user
    existing_query = select(UserMilestone).where(UserMilestone.user_id == user_id)
    existing_result = await db.execute(existing_query)
    existing_milestones = existing_result.scalars().all()

    # Build set of (type, threshold) for existing milestones
    existing_set = {
        (m.type, m.threshold) for m in existing_milestones
    }

    now = datetime.now(timezone.utc)

    # Check cards owned milestones
    for threshold in CARDS_OWNED_THRESHOLDS:
        if (MilestoneType.CARDS_OWNED.value, threshold) not in existing_set:
            if old_total_cards < threshold <= new_total_cards:
                milestone = UserMilestone(
                    user_id=user_id,
                    type=MilestoneType.CARDS_OWNED,
                    name=f"Collector: {threshold} Cards",
                    description=f"Your collection has grown to {threshold} cards!",
                    threshold=threshold,
                    achieved_at=now,
                )
                db.add(milestone)

                # Create notification
                notification = Notification(
                    user_id=user_id,
                    type=NotificationType.MILESTONE,
                    priority=NotificationPriority.MEDIUM,
                    title=f"Milestone Achieved: {threshold} Cards!",
                    message=f"Congratulations! Your collection has grown to {threshold} cards.",
                    extra_data={"milestone_type": "cards_owned", "threshold": threshold},
                )
                db.add(notification)
                milestones_created += 1

    # Check collection value milestones
    old_value = float(old_total_value)
    new_value = float(new_total_value)

    for threshold in COLLECTION_VALUE_THRESHOLDS:
        if (MilestoneType.COLLECTION_VALUE.value, threshold) not in existing_set:
            if old_value < threshold <= new_value:
                milestone = UserMilestone(
                    user_id=user_id,
                    type=MilestoneType.COLLECTION_VALUE,
                    name=f"Value: ${threshold}",
                    description=f"Your collection value has reached ${threshold}!",
                    threshold=threshold,
                    achieved_at=now,
                )
                db.add(milestone)

                notification = Notification(
                    user_id=user_id,
                    type=NotificationType.MILESTONE,
                    priority=NotificationPriority.MEDIUM,
                    title=f"Milestone Achieved: ${threshold} Collection Value!",
                    message=f"Congratulations! Your collection is now worth ${threshold}.",
                    extra_data={"milestone_type": "collection_value", "threshold": threshold},
                )
                db.add(notification)
                milestones_created += 1

    # Check sets started milestones
    for threshold in SETS_STARTED_THRESHOLDS:
        if (MilestoneType.SETS_STARTED.value, threshold) not in existing_set:
            if old_sets_started < threshold <= new_sets_started:
                milestone = UserMilestone(
                    user_id=user_id,
                    type=MilestoneType.SETS_STARTED,
                    name=f"Explorer: {threshold} Sets",
                    description=f"You've started collecting cards from {threshold} different sets!",
                    threshold=threshold,
                    achieved_at=now,
                )
                db.add(milestone)

                notification = Notification(
                    user_id=user_id,
                    type=NotificationType.MILESTONE,
                    priority=NotificationPriority.MEDIUM,
                    title=f"Milestone Achieved: {threshold} Sets Started!",
                    message=f"Congratulations! You've started collecting from {threshold} different sets.",
                    extra_data={"milestone_type": "sets_started", "threshold": threshold},
                )
                db.add(notification)
                milestones_created += 1

    return milestones_created
