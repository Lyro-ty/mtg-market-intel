"""
User Directory API endpoints.

Provides endpoints for browsing, searching, and discovering traders
in the social trading platform.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, OptionalUser
from app.db.session import get_db
from app.models.reputation import UserReputation
from app.models.social import UserFormatSpecialty
from app.models.user import User
from app.schemas.directory import (
    DirectoryResponse,
    ProfileCardResponse,
    QuickTradePreviewResponse,
    SuggestedUserResponse,
)

router = APIRouter(prefix="/directory", tags=["Directory"])
logger = structlog.get_logger(__name__)


def build_profile_card(
    user: User,
    reputation: Optional[UserReputation] = None,
) -> ProfileCardResponse:
    """
    Convert a User model to ProfileCardResponse.

    Handles null safety for optional fields and extracts format specialties.

    Args:
        user: The User model to convert
        reputation: Optional UserReputation for the user

    Returns:
        ProfileCardResponse with trading card-style profile data
    """
    # Get formats from format_specialties relationship if loaded
    formats = []
    if hasattr(user, "format_specialties") and user.format_specialties:
        formats = [fs.format for fs in user.format_specialties]

    # Determine if user is "online" (active within last 15 minutes)
    is_online = False
    if user.last_active_at:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        # Handle both timezone-aware and naive datetimes
        last_active = user.last_active_at
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
        is_online = last_active > cutoff

    # Build signature card dict if available
    signature_card = None
    if hasattr(user, "signature_card") and user.signature_card:
        card = user.signature_card
        signature_card = {
            "id": card.id,
            "name": card.name,
            "image_url": getattr(card, "image_url_small", None) or getattr(card, "image_url", None),
        }

    # Handle location visibility
    city = user.city if user.show_in_directory else None
    country = user.country if user.show_in_directory else None

    # Extract reputation data
    rep_score = None
    rep_count = 0
    if reputation:
        rep_score = float(reputation.average_rating) if reputation.average_rating else None
        rep_count = reputation.total_reviews or 0
    elif hasattr(user, "reputation") and user.reputation:
        rep_score = float(user.reputation.average_rating) if user.reputation.average_rating else None
        rep_count = user.reputation.total_reviews or 0

    return ProfileCardResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        tagline=user.tagline,
        card_type=user.card_type,
        trade_count=0,  # TODO: Calculate from completed trades
        reputation_score=rep_score,
        reputation_count=rep_count,
        success_rate=None,  # TODO: Calculate from trade history
        response_time_hours=None,  # TODO: Calculate from message history
        frame_tier=user.active_frame_tier or "bronze",
        city=city,
        country=country,
        shipping_preference=user.shipping_preference,
        is_online=is_online,
        last_active_at=user.last_active_at,
        open_to_trades=True,  # TODO: Add user preference field
        email_verified=user.is_verified,
        discord_linked=user.discord_id is not None,
        id_verified=False,  # TODO: Add ID verification system
        badges=[],  # TODO: Load from achievements
        formats=formats,
        signature_card=signature_card,
        member_since=user.created_at,
    )


@router.get("", response_model=DirectoryResponse)
async def get_directory(
    db: AsyncSession = Depends(get_db),
    current_user: OptionalUser = None,
    q: Optional[str] = Query(None, description="Search query for username/display name"),
    sort: str = Query("discovery_score", description="Sort field"),
    reputation_tier: Optional[list[str]] = Query(None, description="Filter by reputation tier"),
    frame_tier: Optional[list[str]] = Query(None, description="Filter by frame tier"),
    card_type: Optional[list[str]] = Query(None, description="Filter by card type"),
    format: Optional[list[str]] = Query(None, description="Filter by MTG formats"),
    shipping: Optional[list[str]] = Query(None, description="Filter by shipping preference"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    online_only: bool = Query(False, description="Only show online users"),
    verified_only: bool = Query(False, description="Only show verified users"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Get paginated user directory with filters.

    Returns a list of users who have opted into the directory,
    sorted and filtered according to the query parameters.
    """
    offset = (page - 1) * limit

    # Base query - only show active users who opted into directory
    base_conditions = [
        User.show_in_directory == True,
        User.is_active == True,
    ]

    # Exclude current user from results
    if current_user:
        base_conditions.append(User.id != current_user.id)

    # Search filter
    if q:
        search_pattern = f"%{q}%"
        base_conditions.append(
            or_(
                User.username.ilike(search_pattern),
                User.display_name.ilike(search_pattern),
            )
        )

    # Frame tier filter
    if frame_tier:
        base_conditions.append(User.active_frame_tier.in_(frame_tier))

    # Card type filter
    if card_type:
        base_conditions.append(User.card_type.in_(card_type))

    # Shipping preference filter
    if shipping:
        base_conditions.append(User.shipping_preference.in_(shipping))

    # Country filter
    if country:
        base_conditions.append(User.country == country)

    # Online only filter
    if online_only:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        base_conditions.append(User.last_active_at > cutoff)

    # Verified only filter
    if verified_only:
        base_conditions.append(User.is_verified == True)

    # Build query with eager loading
    query = (
        select(User)
        .options(
            selectinload(User.format_specialties),
            selectinload(User.reputation),
            selectinload(User.signature_card),
        )
        .where(and_(*base_conditions))
    )

    # Format filter (requires join)
    if format:
        format_subquery = (
            select(UserFormatSpecialty.user_id)
            .where(UserFormatSpecialty.format.in_(format))
            .distinct()
        )
        query = query.where(User.id.in_(format_subquery))

    # Reputation tier filter (requires join with UserReputation)
    if reputation_tier:
        rep_subquery = (
            select(UserReputation.user_id)
            .where(UserReputation.tier.in_(reputation_tier))
        )
        query = query.where(User.id.in_(rep_subquery))

    # Sorting
    if sort == "discovery_score":
        query = query.order_by(desc(User.discovery_score))
    elif sort == "reputation":
        # Join with reputation and sort by average rating
        query = query.outerjoin(UserReputation).order_by(
            desc(UserReputation.average_rating).nulls_last()
        )
    elif sort == "trades":
        # TODO: Sort by trade count when trade tracking is implemented
        query = query.order_by(desc(User.discovery_score))
    elif sort == "newest":
        query = query.order_by(desc(User.created_at))
    elif sort == "best_match":
        # TODO: Implement matching algorithm
        query = query.order_by(desc(User.discovery_score))
    else:
        # Default to discovery_score
        query = query.order_by(desc(User.discovery_score))

    # Get total count
    count_query = select(func.count()).select_from(
        select(User.id).where(and_(*base_conditions)).subquery()
    )

    # Apply format filter to count if needed
    if format:
        count_query = select(func.count()).select_from(
            select(User.id)
            .where(and_(*base_conditions))
            .where(User.id.in_(format_subquery))
            .subquery()
        )

    # Apply reputation tier filter to count if needed
    if reputation_tier:
        count_conditions = base_conditions.copy()
        count_query = select(func.count()).select_from(
            select(User.id)
            .where(and_(*count_conditions))
            .where(User.id.in_(rep_subquery))
            .subquery()
        )

    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    users = result.scalars().unique().all()

    # Build response
    profile_cards = [build_profile_card(user) for user in users]

    logger.info(
        "Directory listing",
        page=page,
        limit=limit,
        total=total,
        results=len(profile_cards),
        filters={
            "q": q,
            "sort": sort,
            "frame_tier": frame_tier,
            "card_type": card_type,
            "format": format,
            "shipping": shipping,
            "country": country,
            "online_only": online_only,
            "verified_only": verified_only,
        },
    )

    return DirectoryResponse(
        users=profile_cards,
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(profile_cards)) < total,
    )


@router.get("/search")
async def search_users(
    db: AsyncSession = Depends(get_db),
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
):
    """
    Quick search for users by name.

    Returns a simplified list of matching users for autocomplete/quick search.
    Only searches users who have opted into search visibility.
    """
    search_pattern = f"%{q}%"

    query = (
        select(User)
        .where(
            and_(
                User.show_in_search == True,
                User.is_active == True,
                or_(
                    User.username.ilike(search_pattern),
                    User.display_name.ilike(search_pattern),
                ),
            )
        )
        .order_by(
            # Prioritize exact matches
            func.length(User.username).asc(),
        )
        .limit(limit)
    )

    result = await db.execute(query)
    users = result.scalars().all()

    logger.debug(
        "User search",
        query=q,
        results=len(users),
    )

    return [
        {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "frame_tier": user.active_frame_tier or "bronze",
        }
        for user in users
    ]


@router.get("/suggested", response_model=list[SuggestedUserResponse])
async def get_suggested_users(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
):
    """
    Get suggested connections for the current user.

    Suggests users based on:
    - Matching MTG formats
    - High discovery scores
    - Active traders
    """
    # Get current user's formats
    user_formats_query = (
        select(UserFormatSpecialty.format)
        .where(UserFormatSpecialty.user_id == current_user.id)
    )
    result = await db.execute(user_formats_query)
    user_formats = [row[0] for row in result.all()]

    suggestions = []

    # Find users with matching formats
    if user_formats:
        matching_users_query = (
            select(User)
            .options(
                selectinload(User.format_specialties),
                selectinload(User.reputation),
                selectinload(User.signature_card),
            )
            .join(UserFormatSpecialty)
            .where(
                and_(
                    User.show_in_directory == True,
                    User.is_active == True,
                    User.id != current_user.id,
                    UserFormatSpecialty.format.in_(user_formats),
                )
            )
            .group_by(User.id)
            .order_by(desc(User.discovery_score))
            .limit(limit)
        )

        result = await db.execute(matching_users_query)
        matching_users = result.scalars().unique().all()

        for user in matching_users:
            user_format_list = [fs.format for fs in user.format_specialties]
            matching = list(set(user_formats) & set(user_format_list))

            suggestions.append(
                SuggestedUserResponse(
                    user=build_profile_card(user),
                    reason=f"Also plays {', '.join(matching[:3])}",
                    mutual_connection_count=0,  # TODO: Calculate mutual connections
                    matching_formats=matching,
                    matching_cards=0,  # TODO: Calculate from want list/inventory overlap
                )
            )

    # Fill remaining slots with top users by discovery score
    if len(suggestions) < limit:
        excluded_ids = [s.user.id for s in suggestions] + [current_user.id]
        remaining = limit - len(suggestions)

        top_users_query = (
            select(User)
            .options(
                selectinload(User.format_specialties),
                selectinload(User.reputation),
                selectinload(User.signature_card),
            )
            .where(
                and_(
                    User.show_in_directory == True,
                    User.is_active == True,
                    ~User.id.in_(excluded_ids),
                )
            )
            .order_by(desc(User.discovery_score))
            .limit(remaining)
        )

        result = await db.execute(top_users_query)
        top_users = result.scalars().unique().all()

        for user in top_users:
            suggestions.append(
                SuggestedUserResponse(
                    user=build_profile_card(user),
                    reason="Active trader in the community",
                    mutual_connection_count=0,
                    matching_formats=[],
                    matching_cards=0,
                )
            )

    logger.info(
        "Suggested users",
        user_id=current_user.id,
        suggestions=len(suggestions),
        user_formats=user_formats,
    )

    return suggestions


@router.get("/recent")
async def get_recent_users(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
):
    """
    Get recently interacted users for the current user.

    Returns users the current user has recently:
    - Messaged
    - Traded with
    - Viewed profiles of

    TODO: Implement after adding interaction tracking.
    """
    logger.debug(
        "Recent users requested",
        user_id=current_user.id,
    )

    # TODO: Query ProfileView, Message, TradeProposal tables
    # to find recently interacted users
    return []


@router.get("/{user_id}/preview", response_model=QuickTradePreviewResponse)
async def get_trade_preview(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
):
    """
    Get quick trade preview between current user and target user.

    Shows potential trade matches:
    - Cards they have that you want
    - Cards you have that they want

    TODO: Implement actual want list/inventory matching.
    """
    logger.debug(
        "Trade preview requested",
        current_user_id=current_user.id,
        target_user_id=user_id,
    )

    # TODO: Implement actual want list/inventory matching
    # For now, return placeholder values
    return QuickTradePreviewResponse(
        user_id=user_id,
        cards_they_have_you_want=0,
        cards_they_have_you_want_value=0.0,
        cards_you_have_they_want=0,
        cards_you_have_they_want_value=0.0,
        is_mutual_match=False,
    )
