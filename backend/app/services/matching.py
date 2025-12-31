"""
User discovery and matching service.

Helps users find trading partners by matching:
- Users who have cards I want
- Users who want cards I have available for trade
"""
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def find_users_with_my_wants(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> list[dict]:
    """
    Find users who have cards I want (that are available for trade).

    Matches the current user's want list against other users' inventory
    items that are marked as available for trade.

    Args:
        db: Database session
        user_id: Current user's ID
        limit: Maximum number of users to return

    Returns:
        List of matching users with their matching card counts and names
    """
    query = text("""
        SELECT
            u.id as user_id,
            u.username,
            u.display_name,
            u.location,
            u.avatar_url,
            COUNT(DISTINCT ii.card_id) as matching_cards,
            ARRAY_AGG(DISTINCT c.name ORDER BY c.name) as card_names,
            SUM(ii.quantity) as total_quantity
        FROM users u
        JOIN inventory_items ii ON u.id = ii.user_id
        JOIN want_list_items wli ON ii.card_id = wli.card_id
        JOIN cards c ON ii.card_id = c.id
        WHERE wli.user_id = :user_id
          AND ii.available_for_trade = TRUE
          AND u.id != :user_id
          AND u.is_active = TRUE
        GROUP BY u.id, u.username, u.display_name, u.location, u.avatar_url
        ORDER BY matching_cards DESC
        LIMIT :limit
    """)

    result = await db.execute(query, {"user_id": user_id, "limit": limit})
    rows = result.all()

    matches = []
    for row in rows:
        matches.append({
            "user_id": row.user_id,
            "username": row.username,
            "display_name": row.display_name,
            "location": row.location,
            "avatar_url": row.avatar_url,
            "matching_cards": row.matching_cards,
            "card_names": list(row.card_names) if row.card_names else [],
            "total_quantity": row.total_quantity,
        })

    logger.debug(
        "Found users with wanted cards",
        user_id=user_id,
        matches_found=len(matches),
    )

    return matches


async def find_users_who_want_my_cards(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> list[dict]:
    """
    Find users who want cards I have available for trade.

    Matches the current user's tradeable inventory against other users'
    want lists.

    Args:
        db: Database session
        user_id: Current user's ID
        limit: Maximum number of users to return

    Returns:
        List of matching users with their matching card counts and names
    """
    query = text("""
        SELECT
            u.id as user_id,
            u.username,
            u.display_name,
            u.location,
            u.avatar_url,
            COUNT(DISTINCT wli.card_id) as matching_cards,
            ARRAY_AGG(DISTINCT c.name ORDER BY c.name) as card_names,
            SUM(
                CASE WHEN wli.target_price IS NOT NULL THEN wli.target_price ELSE 0 END
            ) as total_target_value
        FROM users u
        JOIN want_list_items wli ON u.id = wli.user_id
        JOIN inventory_items ii ON wli.card_id = ii.card_id
        JOIN cards c ON wli.card_id = c.id
        WHERE ii.user_id = :user_id
          AND ii.available_for_trade = TRUE
          AND u.id != :user_id
          AND u.is_active = TRUE
        GROUP BY u.id, u.username, u.display_name, u.location, u.avatar_url
        ORDER BY matching_cards DESC
        LIMIT :limit
    """)

    result = await db.execute(query, {"user_id": user_id, "limit": limit})
    rows = result.all()

    matches = []
    for row in rows:
        matches.append({
            "user_id": row.user_id,
            "username": row.username,
            "display_name": row.display_name,
            "location": row.location,
            "avatar_url": row.avatar_url,
            "matching_cards": row.matching_cards,
            "card_names": list(row.card_names) if row.card_names else [],
            "total_target_value": float(row.total_target_value) if row.total_target_value else 0,
        })

    logger.debug(
        "Found users who want my cards",
        user_id=user_id,
        matches_found=len(matches),
    )

    return matches


async def find_mutual_matches(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> list[dict]:
    """
    Find users where both parties have what the other wants.

    This is the holy grail of trading - mutual matches where both
    users can benefit from a trade.

    Args:
        db: Database session
        user_id: Current user's ID
        limit: Maximum number of users to return

    Returns:
        List of users with mutual trading opportunities
    """
    query = text("""
        WITH users_with_my_wants AS (
            -- Users who have cards I want
            SELECT DISTINCT u.id as user_id
            FROM users u
            JOIN inventory_items ii ON u.id = ii.user_id
            JOIN want_list_items wli ON ii.card_id = wli.card_id
            WHERE wli.user_id = :user_id
              AND ii.available_for_trade = TRUE
              AND u.id != :user_id
              AND u.is_active = TRUE
        ),
        users_who_want_mine AS (
            -- Users who want cards I have
            SELECT DISTINCT u.id as user_id
            FROM users u
            JOIN want_list_items wli ON u.id = wli.user_id
            JOIN inventory_items ii ON wli.card_id = ii.card_id
            WHERE ii.user_id = :user_id
              AND ii.available_for_trade = TRUE
              AND u.id != :user_id
              AND u.is_active = TRUE
        ),
        mutual_users AS (
            SELECT user_id FROM users_with_my_wants
            INTERSECT
            SELECT user_id FROM users_who_want_mine
        )
        SELECT
            u.id as user_id,
            u.username,
            u.display_name,
            u.location,
            u.avatar_url,
            -- Cards they have that I want
            (
                SELECT COUNT(DISTINCT ii2.card_id)
                FROM inventory_items ii2
                JOIN want_list_items wli2 ON ii2.card_id = wli2.card_id
                WHERE ii2.user_id = u.id
                  AND ii2.available_for_trade = TRUE
                  AND wli2.user_id = :user_id
            ) as cards_they_have_i_want,
            -- Cards I have that they want
            (
                SELECT COUNT(DISTINCT ii2.card_id)
                FROM inventory_items ii2
                JOIN want_list_items wli2 ON ii2.card_id = wli2.card_id
                WHERE ii2.user_id = :user_id
                  AND ii2.available_for_trade = TRUE
                  AND wli2.user_id = u.id
            ) as cards_i_have_they_want
        FROM users u
        JOIN mutual_users mu ON u.id = mu.user_id
        ORDER BY
            (cards_they_have_i_want + cards_i_have_they_want) DESC,
            LEAST(cards_they_have_i_want, cards_i_have_they_want) DESC
        LIMIT :limit
    """)

    result = await db.execute(query, {"user_id": user_id, "limit": limit})
    rows = result.all()

    matches = []
    for row in rows:
        matches.append({
            "user_id": row.user_id,
            "username": row.username,
            "display_name": row.display_name,
            "location": row.location,
            "avatar_url": row.avatar_url,
            "cards_they_have_i_want": row.cards_they_have_i_want,
            "cards_i_have_they_want": row.cards_i_have_they_want,
            "total_matching_cards": row.cards_they_have_i_want + row.cards_i_have_they_want,
        })

    logger.info(
        "Found mutual trading matches",
        user_id=user_id,
        matches_found=len(matches),
    )

    return matches


async def get_trade_details(
    db: AsyncSession,
    current_user_id: int,
    other_user_id: int,
) -> dict:
    """
    Get detailed trade information between two users.

    Shows exactly which cards can be traded between the users.

    Args:
        db: Database session
        current_user_id: Current user's ID
        other_user_id: Other user's ID

    Returns:
        Detailed trade information with card lists
    """
    # Cards they have that I want
    cards_they_have_query = text("""
        SELECT
            c.id as card_id,
            c.name,
            c.set_code,
            c.image_url_small,
            ii.quantity,
            ii.condition,
            ii.is_foil,
            wli.target_price
        FROM inventory_items ii
        JOIN want_list_items wli ON ii.card_id = wli.card_id
        JOIN cards c ON ii.card_id = c.id
        WHERE ii.user_id = :other_user_id
          AND ii.available_for_trade = TRUE
          AND wli.user_id = :current_user_id
        ORDER BY wli.priority DESC, c.name
    """)

    result1 = await db.execute(cards_they_have_query, {
        "current_user_id": current_user_id,
        "other_user_id": other_user_id,
    })
    cards_they_have = [dict(row._mapping) for row in result1.all()]

    # Cards I have that they want
    cards_i_have_query = text("""
        SELECT
            c.id as card_id,
            c.name,
            c.set_code,
            c.image_url_small,
            ii.quantity,
            ii.condition,
            ii.is_foil,
            wli.target_price
        FROM inventory_items ii
        JOIN want_list_items wli ON ii.card_id = wli.card_id
        JOIN cards c ON ii.card_id = c.id
        WHERE ii.user_id = :current_user_id
          AND ii.available_for_trade = TRUE
          AND wli.user_id = :other_user_id
        ORDER BY wli.priority DESC, c.name
    """)

    result2 = await db.execute(cards_i_have_query, {
        "current_user_id": current_user_id,
        "other_user_id": other_user_id,
    })
    cards_i_have = [dict(row._mapping) for row in result2.all()]

    # Get other user's info
    user_query = text("""
        SELECT id, username, display_name, location, avatar_url
        FROM users
        WHERE id = :user_id AND is_active = TRUE
    """)
    result3 = await db.execute(user_query, {"user_id": other_user_id})
    other_user = result3.first()

    if not other_user:
        return {"error": "User not found"}

    return {
        "other_user": {
            "user_id": other_user.id,
            "username": other_user.username,
            "display_name": other_user.display_name,
            "location": other_user.location,
            "avatar_url": other_user.avatar_url,
        },
        "cards_they_have_i_want": cards_they_have,
        "cards_i_have_they_want": cards_i_have,
        "trade_summary": {
            "cards_i_can_get": len(cards_they_have),
            "cards_i_can_give": len(cards_i_have),
            "is_mutual": len(cards_they_have) > 0 and len(cards_i_have) > 0,
        },
    }
