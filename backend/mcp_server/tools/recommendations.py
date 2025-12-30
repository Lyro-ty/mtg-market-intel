"""
Recommendations and signals tools for MCP server.

Provides tools to query trading recommendations and analytics signals.
"""
from typing import Any
from mcp_server.utils import execute_query, api_client


async def get_recommendations(
    action: str | None = None,
    min_confidence: float | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Get trading recommendations.

    Args:
        action: Filter by action (BUY, SELL, HOLD)
        min_confidence: Minimum confidence score (0-1)
        limit: Maximum recommendations to return

    Returns:
        List of recommendations with rationale
    """
    try:
        params = {"limit": limit}
        if action:
            params["action"] = action.upper()
        if min_confidence:
            params["min_confidence"] = min_confidence

        return await api_client.get("/recommendations", params=params)
    except Exception:
        # Fall back to direct query
        conditions = ["r.is_active = true"]
        query_params: dict[str, Any] = {"limit": limit}

        if action:
            conditions.append("r.action = :action")
            query_params["action"] = action.upper()

        if min_confidence:
            conditions.append("r.confidence >= :min_confidence")
            query_params["min_confidence"] = min_confidence

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                r.id,
                r.card_id,
                c.name as card_name,
                c.set_code,
                r.action,
                r.confidence,
                r.target_price,
                r.current_price,
                r.potential_profit_pct,
                r.rationale,
                r.created_at
            FROM recommendations r
            JOIN cards c ON r.card_id = c.id
            WHERE {where_clause}
            ORDER BY r.confidence DESC, r.potential_profit_pct DESC
            LIMIT :limit
        """

        rows = await execute_query(query, query_params)
        return {"recommendations": rows}


async def get_signals(
    card_id: int | None = None,
    signal_type: str | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """
    Get analytics signals.

    Args:
        card_id: Filter by specific card
        signal_type: Filter by type (momentum_up, volatility_high, etc.)
        days: Number of days of signals to retrieve

    Returns:
        List of signals with confidence scores
    """
    conditions = ["s.date >= CURRENT_DATE - :days::interval"]
    params: dict[str, Any] = {"days": f"{days} days"}

    if card_id:
        conditions.append("s.card_id = :card_id")
        params["card_id"] = card_id

    if signal_type:
        conditions.append("s.signal_type = :signal_type")
        params["signal_type"] = signal_type

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            s.id,
            s.card_id,
            c.name as card_name,
            s.signal_type,
            s.value,
            s.confidence,
            s.llm_insight,
            s.date
        FROM signals s
        JOIN cards c ON s.card_id = c.id
        WHERE {where_clause}
        ORDER BY s.date DESC, s.confidence DESC
        LIMIT 50
    """

    rows = await execute_query(query, params)

    # Get signal type summary if no specific card
    if not card_id:
        summary_query = f"""
            SELECT
                signal_type,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence
            FROM signals s
            WHERE {where_clause}
            GROUP BY signal_type
            ORDER BY count DESC
        """
        summary = await execute_query(summary_query, params)
    else:
        summary = None

    return {
        "signals": rows,
        "summary": summary,
        "filters": {
            "card_id": card_id,
            "signal_type": signal_type,
            "days": days,
        }
    }
