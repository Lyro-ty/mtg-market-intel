"""
Trading Post (LGS) API routes.

Enables local game stores to:
- Register and manage their store profile
- Set buylist margins for trade-in quotes
- Create and manage events
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.trading_post import (
    TradingPost,
    TradingPostEvent,
)
from app.models.user import User
from app.schemas.trading_post import (
    TradingPostCreate,
    TradingPostUpdate,
    TradingPostResponse,
    TradingPostPublic,
    TradingPostListResponse,
    EventCreate,
    EventUpdate,
    EventResponse,
    EventListResponse,
)

router = APIRouter(prefix="/trading-posts", tags=["Trading Posts"])


# ============ Trading Post CRUD ============

@router.post("/register", response_model=TradingPostResponse, status_code=201)
async def register_trading_post(
    data: TradingPostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register a new Trading Post (LGS).

    Each user can only have one Trading Post profile.
    Email verification is required before the store goes live.
    """
    # Check if user already has a trading post
    existing = await db.execute(
        select(TradingPost).where(TradingPost.user_id == current_user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="You already have a Trading Post registered"
        )

    # Create the trading post
    trading_post = TradingPost(
        user_id=current_user.id,
        store_name=data.store_name,
        description=data.description,
        address=data.address,
        city=data.city,
        state=data.state,
        country=data.country,
        postal_code=data.postal_code,
        phone=data.phone,
        website=data.website,
        hours=data.hours,
        services=data.services,
        buylist_margin=data.buylist_margin,
        # Auto-verify email for now (TODO: implement email verification)
        email_verified_at=datetime.now(timezone.utc),
    )

    db.add(trading_post)
    await db.commit()
    await db.refresh(trading_post)

    return _to_response(trading_post)


@router.get("/me", response_model=TradingPostResponse)
async def get_my_trading_post(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's Trading Post profile."""
    result = await db.execute(
        select(TradingPost).where(TradingPost.user_id == current_user.id)
    )
    trading_post = result.scalar_one_or_none()

    if not trading_post:
        raise HTTPException(
            status_code=404,
            detail="You don't have a Trading Post registered"
        )

    return _to_response(trading_post)


@router.put("/me", response_model=TradingPostResponse)
async def update_my_trading_post(
    data: TradingPostUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the current user's Trading Post profile."""
    result = await db.execute(
        select(TradingPost).where(TradingPost.user_id == current_user.id)
    )
    trading_post = result.scalar_one_or_none()

    if not trading_post:
        raise HTTPException(
            status_code=404,
            detail="You don't have a Trading Post registered"
        )

    # Update fields that were provided
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(trading_post, field, value)

    trading_post.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(trading_post)

    return _to_response(trading_post)


@router.get("/nearby", response_model=TradingPostListResponse)
async def get_nearby_trading_posts(
    city: Optional[str] = Query(None, description="Filter by city"),
    state: Optional[str] = Query(None, description="Filter by state"),
    verified_only: bool = Query(True, description="Only show email-verified stores"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Find Trading Posts by location.

    Returns paginated list of stores matching the location criteria.
    By default, only shows email-verified stores.
    """
    query = select(TradingPost)
    count_query = select(func.count(TradingPost.id))

    # Apply filters
    if verified_only:
        query = query.where(TradingPost.email_verified_at.isnot(None))
        count_query = count_query.where(TradingPost.email_verified_at.isnot(None))

    if city:
        query = query.where(TradingPost.city.ilike(f"%{city}%"))
        count_query = count_query.where(TradingPost.city.ilike(f"%{city}%"))

    if state:
        query = query.where(TradingPost.state == state)
        count_query = count_query.where(TradingPost.state == state)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(TradingPost.store_name).offset(offset).limit(page_size)

    result = await db.execute(query)
    trading_posts = result.scalars().all()

    return TradingPostListResponse(
        items=[_to_public(tp) for tp in trading_posts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{trading_post_id}", response_model=TradingPostPublic)
async def get_trading_post(
    trading_post_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a Trading Post's public profile."""
    result = await db.execute(
        select(TradingPost).where(TradingPost.id == trading_post_id)
    )
    trading_post = result.scalar_one_or_none()

    if not trading_post:
        raise HTTPException(status_code=404, detail="Trading Post not found")

    # Only show if email verified
    if not trading_post.email_verified_at:
        raise HTTPException(status_code=404, detail="Trading Post not found")

    return _to_public(trading_post)


# ============ Events ============

@router.post("/me/events", response_model=EventResponse, status_code=201)
async def create_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new event for your Trading Post."""
    # Get user's trading post
    result = await db.execute(
        select(TradingPost).where(TradingPost.user_id == current_user.id)
    )
    trading_post = result.scalar_one_or_none()

    if not trading_post:
        raise HTTPException(
            status_code=403,
            detail="You must register a Trading Post first"
        )

    event = TradingPostEvent(
        trading_post_id=trading_post.id,
        title=data.title,
        description=data.description,
        event_type=data.event_type.value,
        format=data.format,
        start_time=data.start_time,
        end_time=data.end_time,
        entry_fee=data.entry_fee,
        max_players=data.max_players,
    )

    db.add(event)
    await db.commit()
    await db.refresh(event)

    return _event_to_response(event, trading_post)


@router.get("/me/events", response_model=EventListResponse)
async def get_my_events(
    include_past: bool = Query(False, description="Include past events"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get events for your Trading Post."""
    result = await db.execute(
        select(TradingPost).where(TradingPost.user_id == current_user.id)
    )
    trading_post = result.scalar_one_or_none()

    if not trading_post:
        raise HTTPException(
            status_code=403,
            detail="You must register a Trading Post first"
        )

    query = select(TradingPostEvent).where(
        TradingPostEvent.trading_post_id == trading_post.id
    )

    if not include_past:
        query = query.where(
            TradingPostEvent.start_time >= datetime.now(timezone.utc)
        )

    query = query.order_by(TradingPostEvent.start_time)

    result = await db.execute(query)
    events = result.scalars().all()

    return EventListResponse(
        items=[_event_to_response(e, trading_post) for e in events],
        total=len(events),
    )


@router.put("/me/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an event."""
    # Get user's trading post
    result = await db.execute(
        select(TradingPost).where(TradingPost.user_id == current_user.id)
    )
    trading_post = result.scalar_one_or_none()

    if not trading_post:
        raise HTTPException(status_code=403, detail="Trading Post required")

    # Get event
    result = await db.execute(
        select(TradingPostEvent).where(
            TradingPostEvent.id == event_id,
            TradingPostEvent.trading_post_id == trading_post.id,
        )
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "event_type" and value:
            value = value.value
        setattr(event, field, value)

    event.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(event)

    return _event_to_response(event, trading_post)


@router.delete("/me/events/{event_id}", status_code=204)
async def delete_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an event."""
    # Get user's trading post
    result = await db.execute(
        select(TradingPost).where(TradingPost.user_id == current_user.id)
    )
    trading_post = result.scalar_one_or_none()

    if not trading_post:
        raise HTTPException(status_code=403, detail="Trading Post required")

    # Get event
    result = await db.execute(
        select(TradingPostEvent).where(
            TradingPostEvent.id == event_id,
            TradingPostEvent.trading_post_id == trading_post.id,
        )
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    await db.delete(event)
    await db.commit()


# ============ Public Event Discovery ============

@router.get("/{trading_post_id}/events", response_model=EventListResponse)
async def get_trading_post_events(
    trading_post_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get upcoming events for a specific Trading Post."""
    # Get trading post
    result = await db.execute(
        select(TradingPost).where(TradingPost.id == trading_post_id)
    )
    trading_post = result.scalar_one_or_none()

    if not trading_post or not trading_post.email_verified_at:
        raise HTTPException(status_code=404, detail="Trading Post not found")

    # Get upcoming events
    result = await db.execute(
        select(TradingPostEvent)
        .where(TradingPostEvent.trading_post_id == trading_post_id)
        .where(TradingPostEvent.start_time >= datetime.now(timezone.utc))
        .order_by(TradingPostEvent.start_time)
    )
    events = result.scalars().all()

    return EventListResponse(
        items=[_event_to_response(e, trading_post) for e in events],
        total=len(events),
    )


# Separate router for events discovery (mounted at /events)
events_router = APIRouter(prefix="/events", tags=["Events"])


@events_router.get("/nearby", response_model=EventListResponse)
async def get_nearby_events(
    city: Optional[str] = Query(None, description="Filter by city"),
    state: Optional[str] = Query(None, description="Filter by state"),
    format: Optional[str] = Query(None, description="Filter by format (modern, standard, commander)"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    days: int = Query(14, ge=1, le=60, description="Days ahead to search"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Find upcoming events near a location.

    Returns events from verified Trading Posts within the specified timeframe.
    """
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=days)

    query = (
        select(TradingPostEvent)
        .join(TradingPost)
        .where(TradingPost.email_verified_at.isnot(None))
        .where(TradingPostEvent.start_time >= now)
        .where(TradingPostEvent.start_time <= end_date)
    )

    if city:
        query = query.where(TradingPost.city.ilike(f"%{city}%"))

    if state:
        query = query.where(TradingPost.state == state)

    if format:
        query = query.where(TradingPostEvent.format == format)

    if event_type:
        query = query.where(TradingPostEvent.event_type == event_type)

    query = query.order_by(TradingPostEvent.start_time).limit(limit)

    # Need to load trading post for each event
    query = query.options(selectinload(TradingPostEvent.trading_post))

    result = await db.execute(query)
    events = result.scalars().all()

    return EventListResponse(
        items=[_event_to_response(e, e.trading_post) for e in events],
        total=len(events),
    )


# ============ Helper Functions ============

def _to_response(tp: TradingPost) -> TradingPostResponse:
    """Convert TradingPost model to response schema."""
    return TradingPostResponse(
        id=tp.id,
        user_id=tp.user_id,
        store_name=tp.store_name,
        description=tp.description,
        address=tp.address,
        city=tp.city,
        state=tp.state,
        country=tp.country,
        postal_code=tp.postal_code,
        phone=tp.phone,
        website=tp.website,
        hours=tp.hours,
        services=tp.services,
        logo_url=tp.logo_url,
        buylist_margin=tp.buylist_margin,
        email_verified_at=tp.email_verified_at,
        verified_at=tp.verified_at,
        created_at=tp.created_at,
        updated_at=tp.updated_at,
        is_verified=tp.verified_at is not None,
        is_email_verified=tp.email_verified_at is not None,
    )


def _to_public(tp: TradingPost) -> TradingPostPublic:
    """Convert TradingPost model to public schema."""
    return TradingPostPublic(
        id=tp.id,
        store_name=tp.store_name,
        description=tp.description,
        city=tp.city,
        state=tp.state,
        country=tp.country,
        website=tp.website,
        hours=tp.hours,
        services=tp.services,
        logo_url=tp.logo_url,
        is_verified=tp.verified_at is not None,
    )


def _event_to_response(
    event: TradingPostEvent,
    trading_post: Optional[TradingPost] = None,
) -> EventResponse:
    """Convert TradingPostEvent model to response schema."""
    return EventResponse(
        id=event.id,
        trading_post_id=event.trading_post_id,
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        format=event.format,
        start_time=event.start_time,
        end_time=event.end_time,
        entry_fee=event.entry_fee,
        max_players=event.max_players,
        created_at=event.created_at,
        updated_at=event.updated_at,
        trading_post=_to_public(trading_post) if trading_post else None,
    )
