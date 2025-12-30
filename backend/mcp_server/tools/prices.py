"""
Price data tools for MCP server.

Provides tools to query price data and market analytics.
"""
from typing import Any
from datetime import datetime, timedelta, timezone
from mcp_server.utils import execute_query, api_client


async def get_current_price(card_id: int) -> dict[str, Any]:
    """
    Get current price for a card across all marketplaces.

    Args:
        card_id: The database ID of the card

    Returns:
        Price breakdown by marketplace and condition
    """
    # Get card info first
    card_query = """
        SELECT name, set_code, scryfall_price_usd, scryfall_price_usd_foil
        FROM cards WHERE id = :card_id
    """
    card_rows = await execute_query(card_query, {"card_id": card_id})
    if not card_rows:
        return {"error": f"Card with ID {card_id} not found"}

    card = card_rows[0]

    # Get latest price snapshots
    price_query = """
        SELECT
            m.name as marketplace,
            ps.price,
            ps.currency,
            ps.condition,
            ps.is_foil,
            ps.time
        FROM price_snapshots ps
        JOIN marketplaces m ON ps.marketplace_id = m.id
        WHERE ps.card_id = :card_id
        AND ps.time >= NOW() - INTERVAL '24 hours'
        ORDER BY ps.time DESC
        LIMIT 20
    """
    prices = await execute_query(price_query, {"card_id": card_id})

    return {
        "card_id": card_id,
        "name": card["name"],
        "set_code": card["set_code"],
        "scryfall_price_usd": card["scryfall_price_usd"],
        "scryfall_price_usd_foil": card["scryfall_price_usd_foil"],
        "recent_prices": prices,
    }


async def get_price_history(
    card_id: int,
    days: int = 30,
    condition: str | None = None,
    is_foil: bool | None = None,
) -> dict[str, Any]:
    """
    Get historical prices for a card.

    Args:
        card_id: The database ID of the card
        days: Number of days of history (default 30)
        condition: Filter by condition (NEAR_MINT, LIGHTLY_PLAYED, etc.)
        is_foil: Filter by foil status

    Returns:
        Time-series price data
    """
    conditions = ["ps.card_id = :card_id", "ps.time >= NOW() - :interval::interval"]
    params: dict[str, Any] = {"card_id": card_id, "interval": f"{days} days"}

    if condition:
        conditions.append("ps.condition = :condition")
        params["condition"] = condition

    if is_foil is not None:
        conditions.append("ps.is_foil = :is_foil")
        params["is_foil"] = is_foil

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            DATE_TRUNC('day', ps.time) as date,
            m.name as marketplace,
            AVG(ps.price) as avg_price,
            MIN(ps.price) as min_price,
            MAX(ps.price) as max_price,
            COUNT(*) as samples
        FROM price_snapshots ps
        JOIN marketplaces m ON ps.marketplace_id = m.id
        WHERE {where_clause}
        GROUP BY DATE_TRUNC('day', ps.time), m.name
        ORDER BY date DESC, marketplace
    """
    rows = await execute_query(query, params)

    return {
        "card_id": card_id,
        "days": days,
        "condition": condition,
        "is_foil": is_foil,
        "history": rows,
    }


async def get_top_movers(window: str = "24h", limit: int = 10) -> dict[str, Any]:
    """
    Get top gaining and losing cards.

    Args:
        window: Time window ("24h" or "7d")
        limit: Number of cards per category (default 10)

    Returns:
        Top gainers and losers with percentage changes
    """
    try:
        # Use the API endpoint for this
        result = await api_client.get("/market/top-movers", params={"window": window, "limit": limit})
        return result
    except Exception as e:
        # Fall back to direct query
        interval = "1 day" if window == "24h" else "7 days"

        query = """
            WITH price_changes AS (
                SELECT
                    c.id,
                    c.name,
                    c.set_code,
                    c.scryfall_price_usd as current_price,
                    LAG(c.scryfall_price_usd) OVER (PARTITION BY c.id ORDER BY c.updated_at) as prev_price
                FROM cards c
                WHERE c.scryfall_price_usd IS NOT NULL
                AND c.scryfall_price_usd > 0.5
            )
            SELECT
                id, name, set_code, current_price,
                (current_price - prev_price) / NULLIF(prev_price, 0) * 100 as pct_change
            FROM price_changes
            WHERE prev_price IS NOT NULL
            ORDER BY pct_change DESC
            LIMIT :limit
        """
        gainers = await execute_query(query, {"limit": limit})

        query_losers = query.replace("ORDER BY pct_change DESC", "ORDER BY pct_change ASC")
        losers = await execute_query(query_losers, {"limit": limit})

        return {
            "window": window,
            "gainers": gainers,
            "losers": losers,
        }


async def get_market_overview() -> dict[str, Any]:
    """
    Get market-wide statistics.

    Returns:
        Total cards, price snapshots, average prices, etc.
    """
    try:
        return await api_client.get("/market/overview")
    except Exception:
        # Fall back to direct queries
        stats_query = """
            SELECT
                (SELECT COUNT(*) FROM cards) as total_cards,
                (SELECT COUNT(*) FROM cards WHERE scryfall_price_usd IS NOT NULL) as priced_cards,
                (SELECT COUNT(*) FROM price_snapshots WHERE time >= NOW() - INTERVAL '24 hours') as snapshots_24h,
                (SELECT AVG(scryfall_price_usd) FROM cards WHERE scryfall_price_usd IS NOT NULL) as avg_price,
                (SELECT COUNT(*) FROM marketplaces WHERE is_enabled = true) as active_marketplaces
        """
        rows = await execute_query(stats_query)
        return rows[0] if rows else {}


async def get_market_index(range: str = "30d") -> dict[str, Any]:
    """
    Get market index trend.

    Args:
        range: Time range ("7d", "30d", "90d", "1y")

    Returns:
        Normalized market index values over time
    """
    try:
        return await api_client.get("/market/index", params={"range": range})
    except Exception as e:
        return {"error": str(e), "range": range}
