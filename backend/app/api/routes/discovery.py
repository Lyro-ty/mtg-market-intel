"""
User Discovery API endpoints.

Helps users find trading partners by matching wants and haves.
"""
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.services.matching import (
    find_users_with_my_wants,
    find_users_who_want_my_cards,
    find_mutual_matches,
    get_trade_details,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])
logger = structlog.get_logger(__name__)


class UserMatch(BaseModel):
    """A matched user for trading."""
    user_id: int
    username: str
    display_name: str | None = None
    location: str | None = None
    avatar_url: str | None = None
    matching_cards: int
    card_names: list[str]


class UserMatchWithMyWants(UserMatch):
    """A user who has cards I want."""
    total_quantity: int


class UserMatchWhoWantsMine(UserMatch):
    """A user who wants my cards."""
    total_target_value: float


class MutualMatch(BaseModel):
    """A mutual trading match."""
    user_id: int
    username: str
    display_name: str | None = None
    location: str | None = None
    avatar_url: str | None = None
    cards_they_have_i_want: int
    cards_i_have_they_want: int
    total_matching_cards: int


class DiscoveryResponse(BaseModel):
    """Response for discovery endpoints."""
    matches: list[dict]
    total: int


class TradeCard(BaseModel):
    """A card in a potential trade."""
    card_id: int
    name: str
    set_code: str
    image_url_small: str | None = None
    quantity: int
    condition: str
    is_foil: bool
    target_price: float | None = None


class TradeUser(BaseModel):
    """User info in trade details."""
    user_id: int
    username: str
    display_name: str | None = None
    location: str | None = None
    avatar_url: str | None = None


class TradeSummary(BaseModel):
    """Summary of a potential trade."""
    cards_i_can_get: int
    cards_i_can_give: int
    is_mutual: bool


class TradeDetailsResponse(BaseModel):
    """Detailed trade information between two users."""
    other_user: TradeUser
    cards_they_have_i_want: list[TradeCard]
    cards_i_have_they_want: list[TradeCard]
    trade_summary: TradeSummary


@router.get("/users-with-my-wants", response_model=DiscoveryResponse)
async def get_users_with_my_wants(
    current_user: CurrentUser,
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Find users who have cards I want.

    Matches your want list against other users' inventory items
    that are marked as available for trade.

    Returns users sorted by the number of matching cards (most matches first).
    """
    matches = await find_users_with_my_wants(db, current_user.id, limit)

    logger.info(
        "Discovery: users with my wants",
        user_id=current_user.id,
        matches_found=len(matches),
    )

    return DiscoveryResponse(
        matches=matches,
        total=len(matches),
    )


@router.get("/users-who-want-mine", response_model=DiscoveryResponse)
async def get_users_who_want_mine(
    current_user: CurrentUser,
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Find users who want my available-for-trade cards.

    Matches your tradeable inventory against other users' want lists.

    Returns users sorted by the number of matching cards (most matches first).
    """
    matches = await find_users_who_want_my_cards(db, current_user.id, limit)

    logger.info(
        "Discovery: users who want mine",
        user_id=current_user.id,
        matches_found=len(matches),
    )

    return DiscoveryResponse(
        matches=matches,
        total=len(matches),
    )


@router.get("/mutual-matches", response_model=DiscoveryResponse)
async def get_mutual_matches(
    current_user: CurrentUser,
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Find users where both parties have what the other wants.

    This is the best type of match - both users can benefit from a trade.
    These are sorted by total matching cards and balance of the trade.
    """
    matches = await find_mutual_matches(db, current_user.id, limit)

    logger.info(
        "Discovery: mutual matches",
        user_id=current_user.id,
        matches_found=len(matches),
    )

    return DiscoveryResponse(
        matches=matches,
        total=len(matches),
    )


@router.get("/trade-details/{user_id}", response_model=TradeDetailsResponse)
async def get_trade_details_with_user(
    user_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed trade information with a specific user.

    Shows exactly which cards can be traded between you and the other user:
    - Cards they have that you want
    - Cards you have that they want

    Useful for planning a trade proposal.
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot trade with yourself")

    details = await get_trade_details(db, current_user.id, user_id)

    if "error" in details:
        raise HTTPException(status_code=404, detail=details["error"])

    logger.info(
        "Discovery: trade details",
        current_user_id=current_user.id,
        other_user_id=user_id,
        cards_i_can_get=details["trade_summary"]["cards_i_can_get"],
        cards_i_can_give=details["trade_summary"]["cards_i_can_give"],
    )

    return TradeDetailsResponse(
        other_user=TradeUser(**details["other_user"]),
        cards_they_have_i_want=[TradeCard(**c) for c in details["cards_they_have_i_want"]],
        cards_i_have_they_want=[TradeCard(**c) for c in details["cards_i_have_they_want"]],
        trade_summary=TradeSummary(**details["trade_summary"]),
    )


@router.get("/my-tradeable-cards")
async def get_my_tradeable_cards(
    current_user: CurrentUser,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a list of your cards that are available for trade.

    Also shows how many users want each card, helping you prioritize
    which cards to offer in trades.
    """
    from sqlalchemy import text

    query = text("""
        SELECT
            c.id as card_id,
            c.name,
            c.set_code,
            c.image_url_small,
            ii.quantity,
            ii.condition,
            ii.is_foil,
            ii.current_value,
            COUNT(DISTINCT wli.user_id) as users_who_want_it
        FROM inventory_items ii
        JOIN cards c ON ii.card_id = c.id
        LEFT JOIN want_list_items wli ON ii.card_id = wli.card_id AND wli.user_id != :user_id
        WHERE ii.user_id = :user_id
          AND ii.available_for_trade = TRUE
        GROUP BY c.id, c.name, c.set_code, c.image_url_small,
                 ii.quantity, ii.condition, ii.is_foil, ii.current_value
        ORDER BY users_who_want_it DESC, c.name
        LIMIT :limit
    """)

    result = await db.execute(query, {"user_id": current_user.id, "limit": limit})
    cards = [dict(row._mapping) for row in result.all()]

    return {
        "cards": cards,
        "total": len(cards),
    }


@router.get("/summary")
async def get_discovery_summary(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a summary of your discovery potential.

    Returns counts of:
    - Your tradeable inventory cards
    - Your want list items
    - Potential trading partners
    - Mutual matches
    """
    from sqlalchemy import text

    # Count tradeable cards
    tradeable_query = text("""
        SELECT COUNT(*) FROM inventory_items
        WHERE user_id = :user_id AND available_for_trade = TRUE
    """)
    tradeable_count = await db.scalar(tradeable_query, {"user_id": current_user.id}) or 0

    # Count want list items
    wants_query = text("""
        SELECT COUNT(*) FROM want_list_items WHERE user_id = :user_id
    """)
    wants_count = await db.scalar(wants_query, {"user_id": current_user.id}) or 0

    # Count users with my wants (unique)
    users_with_wants_query = text("""
        SELECT COUNT(DISTINCT u.id)
        FROM users u
        JOIN inventory_items ii ON u.id = ii.user_id
        JOIN want_list_items wli ON ii.card_id = wli.card_id
        WHERE wli.user_id = :user_id
          AND ii.available_for_trade = TRUE
          AND u.id != :user_id
          AND u.is_active = TRUE
    """)
    users_with_wants = await db.scalar(users_with_wants_query, {"user_id": current_user.id}) or 0

    # Count mutual matches
    mutual_query = text("""
        WITH users_with_my_wants AS (
            SELECT DISTINCT u.id
            FROM users u
            JOIN inventory_items ii ON u.id = ii.user_id
            JOIN want_list_items wli ON ii.card_id = wli.card_id
            WHERE wli.user_id = :user_id
              AND ii.available_for_trade = TRUE
              AND u.id != :user_id
              AND u.is_active = TRUE
        ),
        users_who_want_mine AS (
            SELECT DISTINCT u.id
            FROM users u
            JOIN want_list_items wli ON u.id = wli.user_id
            JOIN inventory_items ii ON wli.card_id = ii.card_id
            WHERE ii.user_id = :user_id
              AND ii.available_for_trade = TRUE
              AND u.id != :user_id
              AND u.is_active = TRUE
        )
        SELECT COUNT(*) FROM (
            SELECT id FROM users_with_my_wants
            INTERSECT
            SELECT id FROM users_who_want_mine
        ) AS mutual
    """)
    mutual_count = await db.scalar(mutual_query, {"user_id": current_user.id}) or 0

    return {
        "tradeable_cards": tradeable_count,
        "want_list_items": wants_count,
        "users_with_my_wants": users_with_wants,
        "mutual_matches": mutual_count,
        "discovery_score": min(100, (tradeable_count + wants_count) * 5 + mutual_count * 20),
    }
