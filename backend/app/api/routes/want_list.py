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
    WantListIntelligence,
    WantListItemWithIntelligence,
    WantListIntelligenceResponse,
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

    Returns 404 if not found or not owned by current user.
    """
    # Filter by both id and user_id to prevent IDOR
    query = (
        select(WantListItem)
        .options(selectinload(WantListItem.card))
        .where(
            and_(
                WantListItem.id == item_id,
                WantListItem.user_id == current_user.id,
            )
        )
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        # Return 404 for both "not found" and "not owned" to prevent IDOR
        raise HTTPException(status_code=404, detail="Want list item not found")

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

    Returns 404 if not found or not owned by current user.
    """
    # Filter by both id and user_id to prevent IDOR
    query = (
        select(WantListItem)
        .options(selectinload(WantListItem.card))
        .where(
            and_(
                WantListItem.id == item_id,
                WantListItem.user_id == current_user.id,
            )
        )
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        # Return 404 for both "not found" and "not owned" to prevent IDOR
        raise HTTPException(status_code=404, detail="Want list item not found")

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

    Returns 404 if not found or not owned by current user.
    """
    # Filter by both id and user_id to prevent IDOR
    query = select(WantListItem).where(
        and_(
            WantListItem.id == item_id,
            WantListItem.user_id == current_user.id,
        )
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        # Return 404 for both "not found" and "not owned" to prevent IDOR
        raise HTTPException(status_code=404, detail="Want list item not found")

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


async def _get_price_7d_ago(db: AsyncSession, card_id: int) -> Optional[float]:
    """Get price from approximately 7 days ago."""
    from datetime import datetime, timedelta, timezone

    target_time = datetime.now(timezone.utc) - timedelta(days=7)
    price_query = (
        select(PriceSnapshot.price)
        .where(
            and_(
                PriceSnapshot.card_id == card_id,
                PriceSnapshot.currency == "USD",
                PriceSnapshot.time <= target_time,
            )
        )
        .order_by(PriceSnapshot.time.desc())
        .limit(1)
    )
    result = await db.execute(price_query)
    price = result.scalar_one_or_none()
    return float(price) if price else None


def _generate_recommendation(
    target_price: float,
    current_price: Optional[float],
    price_trend_7d: Optional[float],
    supply_status: str,
    reprint_risk: Optional[int],
) -> str:
    """Generate buy recommendation for a want list item."""
    if current_price is None:
        return "unknown"

    # Below target price? Buy now!
    if current_price <= target_price:
        return "buy_now"

    # Price dropping significantly? Wait
    if price_trend_7d is not None and price_trend_7d < -5:
        return "wait_dropping"

    # Low supply + rising? Might spike
    if supply_status in ("low", "very_low"):
        if price_trend_7d is not None and price_trend_7d > 5:
            return "buy_before_spike"

    # High reprint risk? Wait for reprint
    if reprint_risk is not None and reprint_risk > 70:
        return "wait_reprint_likely"

    # Price rising toward target
    if price_trend_7d is not None and price_trend_7d > 0:
        return "rising"

    return "hold"


def _get_supply_status(supply_count: Optional[int]) -> str:
    """Determine supply status based on listing count."""
    if supply_count is None:
        return "unknown"
    if supply_count < 5:
        return "very_low"
    if supply_count < 20:
        return "low"
    return "normal"


@router.get("/intelligence", response_model=WantListIntelligenceResponse)
async def get_want_list_with_intelligence(
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    priority: Optional[WantListPriority] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get want list items with market intelligence data.

    Returns each item with:
    - Current price and comparison to target
    - 7-day price trend
    - Meta share (if tournament data available)
    - Reprint risk score
    - Supply status
    - Buy recommendation
    """
    from decimal import Decimal as Dec
    from datetime import datetime, timezone

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

    # Build response items with intelligence
    response_items = []
    buy_now_count = 0
    price_alerts_count = 0

    for item in items:
        current_price = await _get_current_price(db, item.card_id)
        price_7d_ago = await _get_price_7d_ago(db, item.card_id)

        # Calculate price trend
        price_trend_7d = None
        if current_price and price_7d_ago and price_7d_ago > 0:
            price_trend_7d = round(((current_price - price_7d_ago) / price_7d_ago) * 100, 2)

        # Calculate price vs target
        price_vs_target = None
        if current_price:
            price_vs_target = round(
                ((current_price - float(item.target_price)) / float(item.target_price)) * 100, 2
            )

        # Get reprint risk from card model if available
        reprint_risk = None
        if hasattr(item.card, 'reprint_risk_score') and item.card.reprint_risk_score is not None:
            reprint_risk = int(item.card.reprint_risk_score)

        # Get meta share from card if available
        meta_share = None
        if hasattr(item.card, 'meta_score') and item.card.meta_score is not None:
            meta_share = item.card.meta_score

        # Determine supply status (placeholder - would need listing data)
        supply_status = "unknown"

        # Generate recommendation
        recommendation = _generate_recommendation(
            target_price=float(item.target_price),
            current_price=current_price,
            price_trend_7d=price_trend_7d,
            supply_status=supply_status,
            reprint_risk=reprint_risk,
        )

        # Count stats
        if recommendation == "buy_now":
            buy_now_count += 1
        if current_price and current_price <= float(item.target_price):
            price_alerts_count += 1

        # Build card summary
        card_summary = CardSummary(
            id=item.card.id,
            name=item.card.name,
            set_code=item.card.set_code,
            current_price=current_price,
        )

        # Build base response
        base_response = WantListItemResponse(
            id=item.id,
            user_id=item.user_id,
            card_id=item.card_id,
            target_price=item.target_price,
            priority=WantListPriority(item.priority),
            alert_enabled=item.alert_enabled,
            notes=item.notes,
            alert_on_spike=item.alert_on_spike,
            alert_threshold_pct=item.alert_threshold_pct,
            alert_on_supply_low=item.alert_on_supply_low,
            alert_on_price_drop=item.alert_on_price_drop,
            created_at=item.created_at,
            updated_at=item.updated_at,
            card=card_summary,
        )

        # Build intelligence
        intelligence = WantListIntelligence(
            current_price=Dec(str(current_price)) if current_price else None,
            price_vs_target=Dec(str(price_vs_target)) if price_vs_target else None,
            price_trend_7d=Dec(str(price_trend_7d)) if price_trend_7d else None,
            meta_share=meta_share,
            reprint_risk=reprint_risk,
            supply_status=supply_status,
            recommendation=recommendation,
        )

        response_items.append(WantListItemWithIntelligence(
            **base_response.model_dump(),
            intelligence=intelligence,
        ))

    logger.info(
        "Want list intelligence fetched",
        user_id=current_user.id,
        items_count=len(response_items),
        buy_now_count=buy_now_count,
    )

    return WantListIntelligenceResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
        buy_now_count=buy_now_count,
        price_alerts_count=price_alerts_count,
    )
