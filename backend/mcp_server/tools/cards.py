"""
Card lookup tools for MCP server.

Provides tools to search and retrieve card information.
"""
from typing import Any
from mcp_server.utils import execute_query, api_client


async def get_card_by_id(card_id: int) -> dict[str, Any]:
    """
    Fetch a card by its database ID.

    Args:
        card_id: The database ID of the card

    Returns:
        Card object with name, set, etc.
    """
    query = """
        SELECT
            c.id, c.name, c.set_code, c.set_name, c.collector_number,
            c.scryfall_id, c.oracle_id, c.rarity, c.mana_cost, c.cmc,
            c.type_line, c.oracle_text, c.colors, c.color_identity,
            c.power, c.toughness, c.image_url_small, c.image_url,
            c.legalities, c.edhrec_rank, c.reserved_list
        FROM cards c
        WHERE c.id = :card_id
    """
    rows = await execute_query(query, {"card_id": card_id})
    if not rows:
        return {"error": f"Card with ID {card_id} not found"}
    return rows[0]


async def get_card_by_name(name: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Search for cards by name (fuzzy match).

    Args:
        name: Card name to search for
        limit: Maximum number of results (default 10)

    Returns:
        List of matching cards
    """
    query = """
        SELECT
            id, name, set_code, set_name, rarity, mana_cost, type_line,
            image_url_small
        FROM cards
        WHERE name ILIKE :pattern
        ORDER BY
            CASE WHEN name ILIKE :exact THEN 0 ELSE 1 END,
            name
        LIMIT :limit
    """
    pattern = f"%{name}%"
    exact = name
    rows = await execute_query(query, {"pattern": pattern, "exact": exact, "limit": limit})
    return rows


async def get_card_by_scryfall_id(scryfall_id: str) -> dict[str, Any]:
    """
    Fetch a card by its Scryfall UUID.

    Args:
        scryfall_id: The Scryfall UUID of the card

    Returns:
        Card object
    """
    query = """
        SELECT
            id, name, set_code, set_name, collector_number,
            scryfall_id, oracle_id, rarity, mana_cost, cmc,
            type_line, oracle_text, colors, color_identity, legalities
        FROM cards
        WHERE scryfall_id = :scryfall_id
    """
    rows = await execute_query(query, {"scryfall_id": scryfall_id})
    if not rows:
        return {"error": f"Card with Scryfall ID {scryfall_id} not found"}
    return rows[0]


async def search_cards(
    colors: str | None = None,
    card_type: str | None = None,
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    rarity: str | None = None,
    set_code: str | None = None,
    format_legal: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Search cards with filters.

    Args:
        colors: Color filter (e.g., "W", "UB", "WUBRG")
        card_type: Type filter (e.g., "Creature", "Instant")
        cmc_min: Minimum converted mana cost
        cmc_max: Maximum converted mana cost
        rarity: Rarity filter (common, uncommon, rare, mythic)
        set_code: Set code filter (e.g., "MKM", "ONE")
        format_legal: Format legality filter (e.g., "modern", "commander")
        limit: Maximum results (default 20)
        offset: Pagination offset

    Returns:
        Paginated list of matching cards with total count
    """
    conditions = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if colors:
        # Match cards containing these colors
        for i, color in enumerate(colors.upper()):
            if color in "WUBRG":
                conditions.append(f"colors::text ILIKE :color{i}")
                params[f"color{i}"] = f"%{color}%"

    if card_type:
        conditions.append("type_line ILIKE :card_type")
        params["card_type"] = f"%{card_type}%"

    if cmc_min is not None:
        conditions.append("cmc >= :cmc_min")
        params["cmc_min"] = cmc_min

    if cmc_max is not None:
        conditions.append("cmc <= :cmc_max")
        params["cmc_max"] = cmc_max

    if rarity:
        conditions.append("rarity = :rarity")
        params["rarity"] = rarity.lower()

    if set_code:
        conditions.append("set_code = :set_code")
        params["set_code"] = set_code.lower()

    if format_legal:
        conditions.append(f"legalities ILIKE :format_pattern")
        params["format_pattern"] = f'%"{format_legal.lower()}": "legal"%'

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Get total count
    count_query = f"SELECT COUNT(*) as count FROM cards WHERE {where_clause}"
    count_result = await execute_query(count_query, params)
    total = count_result[0]["count"] if count_result else 0

    # Get results
    query = f"""
        SELECT
            id, name, set_code, set_name, rarity, mana_cost, cmc,
            type_line, colors, image_url_small
        FROM cards
        WHERE {where_clause}
        ORDER BY name
        LIMIT :limit OFFSET :offset
    """
    rows = await execute_query(query, params)

    return {
        "cards": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_random_cards(count: int = 5) -> list[dict[str, Any]]:
    """
    Get random cards (useful for testing).

    Args:
        count: Number of random cards to return (default 5, max 20)

    Returns:
        List of random cards
    """
    count = min(count, 20)  # Cap at 20
    query = """
        SELECT
            id, name, set_code, set_name, rarity, mana_cost, type_line,
            image_url_small
        FROM cards
        ORDER BY RANDOM()
        LIMIT :count
    """
    return await execute_query(query, {"count": count})
