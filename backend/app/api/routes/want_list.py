"""
Want List API endpoints for managing cards users want to acquire.

All want list endpoints require authentication and filter data by the current user.
"""
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models import Card, WantListItem, PriceSnapshot
from app.schemas.want_list import (
    WantListItemCreate,
    WantListItemUpdate,
    WantListItemResponse,
    WantListListResponse,
    WantListPriority,
    CardSummary,
)

router = APIRouter()
logger = structlog.get_logger()


def _build_item_response(item: WantListItem, current_price: Optional[float] = None) -> WantListItemResponse:
    """Build a WantListItemResponse from a WantListItem model."""
    card_summary = CardSummary(
        id=item.card.id,
        name=item.card.name,
        set_code=item.card.set_code,
        current_price=current_price,
    )

    return WantListItemResponse(
        id=item.id,
        user_id=item.user_id,
        card_id=item.card_id,
        target_price=item.target_price,
        priority=WantListPriority(item.priority),
        alert_enabled=item.alert_enabled,
        notes=item.notes,
        created_at=item.created_at,
        updated_at=item.updated_at,
        card=card_summary,
    )


async def _get_current_price(db: AsyncSession, card_id: int) -> Optional[float]:
    """Get the most recent price for a card."""
    price_query = (
        select(PriceSnapshot.price)
        .where(
            and_(
                PriceSnapshot.card_id == card_id,
                PriceSnapshot.currency == "USD",
                PriceSnapshot.price.isnot(None),
            )
        )
        .order_by(PriceSnapshot.time.desc())
        .limit(1)
    )
    result = await db.execute(price_query)
    price = result.scalar_one_or_none()
    return float(price) if price else None


@router.get("", response_model=WantListListResponse)
async def list_want_list_items(
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    priority: Optional[WantListPriority] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current user's want list items with pagination.

    Optionally filter by priority level.
    """
    # Build base query filtered by current user
    query = (
        select(WantListItem)
        .options(selectinload(WantListItem.card))
        .where(WantListItem.user_id == current_user.id)
    )

    # Apply priority filter if specified
    if priority:
        query = query.where(WantListItem.priority == priority.value)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply ordering and pagination
    # Use CASE expression for priority ordering (PostgreSQL compatible)
    priority_order = case(
        (WantListItem.priority == "high", 1),
        (WantListItem.priority == "medium", 2),
        (WantListItem.priority == "low", 3),
        else_=4,
    )
    query = (
        query.order_by(
            priority_order,
            WantListItem.created_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    items = result.scalars().all()

    # Build response items with current prices
    response_items = []
    for item in items:
        current_price = await _get_current_price(db, item.card_id)
        response_items.append(_build_item_response(item, current_price))

    return WantListListResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.post("", response_model=WantListItemResponse, status_code=status.HTTP_201_CREATED)
async def create_want_list_item(
    item: WantListItemCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a card to the current user's want list.
    """
    # Verify card exists
    card = await db.get(Card, item.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check if item already exists for this user/card combination
    existing_query = select(WantListItem).where(
        and_(
            WantListItem.user_id == current_user.id,
            WantListItem.card_id == item.card_id,
        )
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Card is already on your want list"
        )

    # Create the want list item
    want_item = WantListItem(
        user_id=current_user.id,
        card_id=item.card_id,
        target_price=item.target_price,
        priority=item.priority.value,
        alert_enabled=item.alert_enabled,
        notes=item.notes,
    )
    db.add(want_item)
    await db.commit()
    await db.refresh(want_item)

    # Load the card relationship for response
    await db.refresh(want_item, ["card"])

    current_price = await _get_current_price(db, want_item.card_id)

    logger.info(
        "Want list item created",
        user_id=current_user.id,
        card_id=item.card_id,
        target_price=float(item.target_price),
    )

    return _build_item_response(want_item, current_price)


@router.get("/{item_id}", response_model=WantListItemResponse)
async def get_want_list_item(
    item_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific want list item by ID.

    Returns 404 if not found, 403 if not owned by current user.
    """
    query = (
        select(WantListItem)
        .options(selectinload(WantListItem.card))
        .where(WantListItem.id == item_id)
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Want list item not found")

    if item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this item")

    current_price = await _get_current_price(db, item.card_id)

    return _build_item_response(item, current_price)


@router.patch("/{item_id}", response_model=WantListItemResponse)
async def update_want_list_item(
    item_id: int,
    updates: WantListItemUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a want list item.

    Returns 404 if not found, 403 if not owned by current user.
    """
    query = (
        select(WantListItem)
        .options(selectinload(WantListItem.card))
        .where(WantListItem.id == item_id)
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Want list item not found")

    if item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this item")

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "priority" and value is not None:
            setattr(item, field, value.value)
        else:
            setattr(item, field, value)

    await db.commit()
    await db.refresh(item)

    current_price = await _get_current_price(db, item.card_id)

    logger.info(
        "Want list item updated",
        user_id=current_user.id,
        item_id=item_id,
        updates=list(update_data.keys()),
    )

    return _build_item_response(item, current_price)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_want_list_item(
    item_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Remove an item from the want list.

    Returns 404 if not found, 403 if not owned by current user.
    """
    query = select(WantListItem).where(WantListItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Want list item not found")

    if item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this item")

    await db.delete(item)
    await db.commit()

    logger.info(
        "Want list item deleted",
        user_id=current_user.id,
        item_id=item_id,
    )

    return None


@router.post("/check-prices")
async def check_want_list_prices(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Check current prices for all want list items and return items
    where the current price is at or below the target price.

    This is an on-demand price check for identifying buying opportunities.
    """
    # Get all user's want list items with alert enabled
    query = (
        select(WantListItem)
        .options(selectinload(WantListItem.card))
        .where(
            and_(
                WantListItem.user_id == current_user.id,
                WantListItem.alert_enabled == True,
            )
        )
    )
    result = await db.execute(query)
    items = result.scalars().all()

    if not items:
        return {
            "message": "No want list items with alerts enabled",
            "deals": [],
            "checked_count": 0,
        }

    deals = []

    for item in items:
        current_price = await _get_current_price(db, item.card_id)

        if current_price is not None and current_price <= float(item.target_price):
            deals.append({
                "id": item.id,
                "card_id": item.card_id,
                "card_name": item.card.name,
                "set_code": item.card.set_code,
                "target_price": float(item.target_price),
                "current_price": current_price,
                "savings": float(item.target_price) - current_price,
                "savings_pct": round(
                    ((float(item.target_price) - current_price) / float(item.target_price)) * 100, 1
                ),
                "priority": item.priority,
            })

    # Sort by savings percentage (best deals first)
    deals.sort(key=lambda x: x["savings_pct"], reverse=True)

    logger.info(
        "Want list price check completed",
        user_id=current_user.id,
        checked_count=len(items),
        deals_found=len(deals),
    )

    return {
        "message": f"Found {len(deals)} items at or below target price",
        "deals": deals,
        "checked_count": len(items),
    }
