"""
MTG Sets API endpoints for browsing Magic: The Gathering sets.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import MTGSet
from app.schemas.sets import MTGSetList, MTGSetResponse

router = APIRouter(prefix="/sets", tags=["Sets"])


@router.get("", response_model=MTGSetList)
async def list_sets(
    search: str | None = Query(None, description="Search by set name or code"),
    set_type: str | None = Query(None, description="Filter by set type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all MTG sets with optional filtering.

    This is a public endpoint - no authentication required.

    - **search**: Filter sets by name or code (case-insensitive)
    - **set_type**: Filter by set type (e.g., 'expansion', 'core', 'masters')
    - **limit**: Maximum number of sets to return (1-200, default 50)
    - **offset**: Number of sets to skip for pagination
    """
    query = select(MTGSet)
    count_query = select(func.count(MTGSet.id))

    # Apply search filter if provided
    if search:
        search_pattern = f"%{search}%"
        search_filter = or_(
            MTGSet.name.ilike(search_pattern),
            MTGSet.code.ilike(search_pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Apply set type filter if provided
    if set_type:
        query = query.where(MTGSet.set_type == set_type)
        count_query = count_query.where(MTGSet.set_type == set_type)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply ordering (most recent first), then pagination
    query = query.order_by(MTGSet.released_at.desc().nullslast(), MTGSet.name)
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    sets = result.scalars().all()

    return MTGSetList(
        items=[MTGSetResponse.model_validate(s) for s in sets],
        total=total,
    )


@router.get("/{set_code}", response_model=MTGSetResponse)
async def get_set(
    set_code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific MTG set by its code.

    This is a public endpoint - no authentication required.

    - **set_code**: The unique set code (e.g., 'NEO', 'MKM', 'OTJ')
    """
    # Query by code (case-insensitive)
    query = select(MTGSet).where(func.lower(MTGSet.code) == set_code.lower())
    result = await db.execute(query)
    mtg_set = result.scalar_one_or_none()

    if not mtg_set:
        raise HTTPException(
            status_code=404,
            detail=f"Set with code '{set_code}' not found",
        )

    return MTGSetResponse.model_validate(mtg_set)
