"""
Collection statistics and milestones API endpoints.

All collection endpoints require authentication and return data for the current user.
"""
from decimal import Decimal
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models import (
    Card,
    CollectionStats,
    InventoryItem,
    MTGSet,
    UserMilestone,
)
from app.schemas.collection import (
    CollectionStatsResponse,
    MilestoneList,
    MilestoneResponse,
    SetCompletion,
    SetCompletionList,
)

router = APIRouter()
logger = structlog.get_logger()


async def calculate_collection_stats(
    user_id: int,
    db: AsyncSession,
) -> CollectionStats:
    """
    Calculate and update collection statistics for a user.

    This is called on-demand when stats are stale or when a refresh is requested.
    """
    from datetime import datetime, timezone

    # Get total cards and unique cards
    totals_query = select(
        func.sum(InventoryItem.quantity).label("total_cards"),
        func.count(func.distinct(InventoryItem.card_id)).label("unique_cards"),
        func.sum(
            func.coalesce(InventoryItem.current_value, Decimal("0.00")) * InventoryItem.quantity
        ).label("total_value"),
    ).where(InventoryItem.user_id == user_id)

    totals_result = await db.execute(totals_query)
    totals = totals_result.one()

    total_cards = totals.total_cards or 0
    unique_cards = totals.unique_cards or 0
    total_value = totals.total_value or Decimal("0.00")

    # Get set completion data - count distinct sets user has cards from
    sets_query = select(
        func.count(func.distinct(Card.set_code)).label("sets_started")
    ).join(
        InventoryItem, InventoryItem.card_id == Card.id
    ).where(InventoryItem.user_id == user_id)

    sets_result = await db.execute(sets_query)
    sets_started = sets_result.scalar() or 0

    # Find sets that are 100% complete
    # For each set user has cards from, check if they own all cards in that set
    completed_sets_query = """
        WITH user_set_counts AS (
            SELECT c.set_code,
                   COUNT(DISTINCT c.id) as owned_count
            FROM inventory_items ii
            JOIN cards c ON ii.card_id = c.id
            WHERE ii.user_id = :user_id
            GROUP BY c.set_code
        ),
        set_totals AS (
            SELECT set_code, COUNT(*) as total_count
            FROM cards
            GROUP BY set_code
        )
        SELECT COUNT(*) as completed
        FROM user_set_counts usc
        JOIN set_totals st ON usc.set_code = st.set_code
        WHERE usc.owned_count >= st.total_count
    """
    from sqlalchemy import text
    completed_result = await db.execute(text(completed_sets_query), {"user_id": user_id})
    sets_completed = completed_result.scalar() or 0

    # Find top set by completion percentage
    top_set_query = """
        WITH user_set_counts AS (
            SELECT c.set_code,
                   COUNT(DISTINCT c.id) as owned_count
            FROM inventory_items ii
            JOIN cards c ON ii.card_id = c.id
            WHERE ii.user_id = :user_id
            GROUP BY c.set_code
        ),
        set_totals AS (
            SELECT set_code, COUNT(*) as total_count
            FROM cards
            GROUP BY set_code
        )
        SELECT usc.set_code,
               ROUND((usc.owned_count::numeric / NULLIF(st.total_count, 0) * 100), 2) as completion
        FROM user_set_counts usc
        JOIN set_totals st ON usc.set_code = st.set_code
        WHERE st.total_count > 0
        ORDER BY completion DESC, usc.set_code
        LIMIT 1
    """
    top_set_result = await db.execute(text(top_set_query), {"user_id": user_id})
    top_set_row = top_set_result.first()

    top_set_code = top_set_row.set_code if top_set_row else None
    top_set_completion = Decimal(str(top_set_row.completion)) if top_set_row else None

    # Get or create the CollectionStats record
    stats_query = select(CollectionStats).where(CollectionStats.user_id == user_id)
    stats_result = await db.execute(stats_query)
    stats = stats_result.scalar_one_or_none()

    if stats is None:
        stats = CollectionStats(user_id=user_id)
        db.add(stats)

    # Update the stats
    stats.total_cards = total_cards
    stats.total_value = total_value
    stats.unique_cards = unique_cards
    stats.sets_started = sets_started
    stats.sets_completed = sets_completed
    stats.top_set_code = top_set_code
    stats.top_set_completion = top_set_completion
    stats.is_stale = False
    stats.last_calculated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(stats)

    logger.info(
        "Collection stats calculated",
        user_id=user_id,
        total_cards=total_cards,
        unique_cards=unique_cards,
        total_value=float(total_value),
    )

    return stats


async def trigger_stats_recalculation(user_id: int, db: AsyncSession) -> None:
    """Background task to recalculate collection stats."""
    try:
        await calculate_collection_stats(user_id, db)
    except Exception as e:
        logger.error(
            "Failed to recalculate collection stats",
            user_id=user_id,
            error=str(e),
        )


@router.get("/stats", response_model=CollectionStatsResponse)
async def get_collection_stats(
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> CollectionStatsResponse:
    """
    Get collection statistics for the current user.

    Returns cached stats if available. If stats are stale (is_stale=True),
    a background recalculation is triggered and the stale data is returned
    immediately for responsiveness.
    """
    # Try to get existing stats
    stats_query = select(CollectionStats).where(
        CollectionStats.user_id == current_user.id
    )
    result = await db.execute(stats_query)
    stats = result.scalar_one_or_none()

    if stats is None:
        # No stats exist yet - calculate synchronously for first request
        stats = await calculate_collection_stats(current_user.id, db)
    elif stats.is_stale:
        # Stats exist but are stale - trigger background recalculation
        # Return stale data immediately for better UX
        background_tasks.add_task(
            trigger_stats_recalculation,
            current_user.id,
            db,
        )

    return CollectionStatsResponse.model_validate(stats)


@router.post("/stats/refresh")
async def refresh_collection_stats(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Force recalculation of collection statistics.

    This immediately recalculates all stats for the current user's collection.
    Use this after bulk imports or when you need the latest data.
    """
    # Mark stats as stale first
    stats_query = select(CollectionStats).where(
        CollectionStats.user_id == current_user.id
    )
    result = await db.execute(stats_query)
    stats = result.scalar_one_or_none()

    if stats:
        stats.is_stale = True
        await db.commit()

    # Recalculate synchronously
    await calculate_collection_stats(current_user.id, db)

    return {
        "status": "completed",
        "message": "Collection statistics have been recalculated.",
    }


@router.get("/sets", response_model=SetCompletionList)
async def get_set_completion(
    current_user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("completion", regex="^(completion|name)$"),
    db: AsyncSession = Depends(get_db),
) -> SetCompletionList:
    """
    Get set completion progress for the current user's collection.

    Returns a list of sets the user has cards from, with completion percentages.
    """
    from sqlalchemy import text

    # Build the query with dynamic ordering
    order_clause = "completion DESC, s.name" if sort_by == "completion" else "s.name"

    query = text(f"""
        WITH user_set_counts AS (
            SELECT c.set_code,
                   COUNT(DISTINCT c.id) as owned_count
            FROM inventory_items ii
            JOIN cards c ON ii.card_id = c.id
            WHERE ii.user_id = :user_id
            GROUP BY c.set_code
        ),
        set_totals AS (
            SELECT set_code, COUNT(*) as total_count
            FROM cards
            GROUP BY set_code
        )
        SELECT s.code as set_code,
               s.name as set_name,
               st.total_count as total_cards,
               usc.owned_count as owned_cards,
               ROUND((usc.owned_count::numeric / NULLIF(st.total_count, 0) * 100), 2) as completion,
               s.icon_svg_uri
        FROM user_set_counts usc
        JOIN set_totals st ON usc.set_code = st.set_code
        LEFT JOIN mtg_sets s ON UPPER(usc.set_code) = UPPER(s.code)
        WHERE st.total_count > 0
        ORDER BY {order_clause}
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(
        query,
        {"user_id": current_user.id, "limit": limit, "offset": offset}
    )
    rows = result.all()

    # Get total count
    count_query = text("""
        SELECT COUNT(DISTINCT c.set_code)
        FROM inventory_items ii
        JOIN cards c ON ii.card_id = c.id
        WHERE ii.user_id = :user_id
    """)
    count_result = await db.execute(count_query, {"user_id": current_user.id})
    total_sets = count_result.scalar() or 0

    items = [
        SetCompletion(
            set_code=row.set_code,
            set_name=row.set_name or row.set_code,  # Fallback to code if name not found
            total_cards=row.total_cards,
            owned_cards=row.owned_cards,
            completion_percentage=Decimal(str(row.completion)) if row.completion else Decimal("0.00"),
            icon_svg_uri=row.icon_svg_uri,
        )
        for row in rows
    ]

    return SetCompletionList(
        items=items,
        total_sets=total_sets,
    )


@router.get("/milestones", response_model=MilestoneList)
async def get_milestones(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> MilestoneList:
    """
    Get achieved milestones for the current user.

    Returns all milestones the user has earned, ordered by most recent first.
    """
    query = select(UserMilestone).where(
        UserMilestone.user_id == current_user.id
    ).order_by(desc(UserMilestone.achieved_at))

    result = await db.execute(query)
    milestones = result.scalars().all()

    items = [
        MilestoneResponse(
            id=m.id,
            type=m.type.value if hasattr(m.type, 'value') else m.type,
            name=m.name,
            description=m.description,
            threshold=m.threshold,
            achieved_at=m.achieved_at,
            metadata=m.metadata,
        )
        for m in milestones
    ]

    return MilestoneList(
        items=items,
        total=len(items),
    )
