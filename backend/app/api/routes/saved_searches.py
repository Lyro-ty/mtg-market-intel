"""API routes for saved searches."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.saved_search import SavedSearch, SearchAlertFrequency
from app.models.user import User


router = APIRouter(prefix="/saved-searches", tags=["saved-searches"])


class SavedSearchCreate(BaseModel):
    """Schema for creating a saved search."""
    name: str = Field(..., min_length=1, max_length=100)
    query: Optional[str] = Field(None, max_length=255)
    filters: Optional[dict[str, Any]] = None
    alert_enabled: bool = False
    alert_frequency: SearchAlertFrequency = SearchAlertFrequency.NEVER
    price_alert_threshold: Optional[float] = None


class SavedSearchUpdate(BaseModel):
    """Schema for updating a saved search."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    query: Optional[str] = Field(None, max_length=255)
    filters: Optional[dict[str, Any]] = None
    alert_enabled: Optional[bool] = None
    alert_frequency: Optional[SearchAlertFrequency] = None
    price_alert_threshold: Optional[float] = None


class SavedSearchResponse(BaseModel):
    """Response schema for a saved search."""
    id: int
    name: str
    query: Optional[str] = None
    filters: Optional[dict[str, Any]] = None
    alert_enabled: bool
    alert_frequency: str
    price_alert_threshold: Optional[float] = None
    last_run_at: Optional[str] = None
    last_result_count: int
    created_at: str

    class Config:
        from_attributes = True


class SavedSearchListResponse(BaseModel):
    """Response for listing saved searches."""
    items: list[SavedSearchResponse]
    total: int


def search_to_response(search: SavedSearch) -> SavedSearchResponse:
    """Convert SavedSearch to response schema."""
    return SavedSearchResponse(
        id=search.id,
        name=search.name,
        query=search.query,
        filters=search.filters,
        alert_enabled=search.alert_enabled,
        alert_frequency=search.alert_frequency.value if isinstance(search.alert_frequency, SearchAlertFrequency) else search.alert_frequency,
        price_alert_threshold=search.price_alert_threshold,
        last_run_at=search.last_run_at.isoformat() if search.last_run_at else None,
        last_result_count=search.last_result_count,
        created_at=search.created_at.isoformat(),
    )


@router.get("", response_model=SavedSearchListResponse)
async def list_saved_searches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchListResponse:
    """List all saved searches for the current user."""
    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(SavedSearch).where(
            SavedSearch.user_id == current_user.id
        )
    )
    total = count_result.scalar_one()

    # Get items
    result = await db.execute(
        select(SavedSearch)
        .where(SavedSearch.user_id == current_user.id)
        .order_by(SavedSearch.created_at.desc())
    )
    searches = list(result.scalars().all())

    return SavedSearchListResponse(
        items=[search_to_response(s) for s in searches],
        total=total,
    )


@router.post("", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    data: SavedSearchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchResponse:
    """Create a new saved search."""
    # Check if name already exists for this user
    existing = await db.execute(
        select(SavedSearch).where(
            SavedSearch.user_id == current_user.id,
            SavedSearch.name == data.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A saved search with this name already exists",
        )

    # Limit to 50 saved searches per user
    count_result = await db.execute(
        select(func.count()).select_from(SavedSearch).where(
            SavedSearch.user_id == current_user.id
        )
    )
    count = count_result.scalar_one()
    if count >= 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum of 50 saved searches reached",
        )

    search = SavedSearch(
        user_id=current_user.id,
        name=data.name,
        query=data.query,
        filters=data.filters,
        alert_enabled=data.alert_enabled,
        alert_frequency=data.alert_frequency,
        price_alert_threshold=data.price_alert_threshold,
    )
    db.add(search)
    await db.commit()
    await db.refresh(search)

    return search_to_response(search)


@router.get("/{search_id}", response_model=SavedSearchResponse)
async def get_saved_search(
    search_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchResponse:
    """Get a saved search by ID."""
    result = await db.execute(
        select(SavedSearch).where(
            SavedSearch.id == search_id,
            SavedSearch.user_id == current_user.id,
        )
    )
    search = result.scalar_one_or_none()
    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )

    return search_to_response(search)


@router.patch("/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: int,
    data: SavedSearchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedSearchResponse:
    """Update a saved search."""
    result = await db.execute(
        select(SavedSearch).where(
            SavedSearch.id == search_id,
            SavedSearch.user_id == current_user.id,
        )
    )
    search = result.scalar_one_or_none()
    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )

    # Check if new name conflicts with existing
    if data.name and data.name != search.name:
        existing = await db.execute(
            select(SavedSearch).where(
                SavedSearch.user_id == current_user.id,
                SavedSearch.name == data.name,
                SavedSearch.id != search_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A saved search with this name already exists",
            )

    # Update fields
    if data.name is not None:
        search.name = data.name
    if data.query is not None:
        search.query = data.query
    if data.filters is not None:
        search.filters = data.filters
    if data.alert_enabled is not None:
        search.alert_enabled = data.alert_enabled
    if data.alert_frequency is not None:
        search.alert_frequency = data.alert_frequency
    if data.price_alert_threshold is not None:
        search.price_alert_threshold = data.price_alert_threshold

    await db.commit()
    await db.refresh(search)

    return search_to_response(search)


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    search_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a saved search."""
    result = await db.execute(
        select(SavedSearch).where(
            SavedSearch.id == search_id,
            SavedSearch.user_id == current_user.id,
        )
    )
    search = result.scalar_one_or_none()
    if not search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )

    await db.delete(search)
    await db.commit()
