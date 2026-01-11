"""API routes for portfolio history."""
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.portfolio import PortfolioService


router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class PortfolioSnapshotResponse(BaseModel):
    """Response schema for a portfolio snapshot."""
    id: int
    snapshot_date: str
    total_value: float
    total_cost: float
    total_cards: int
    unique_cards: int
    value_change_1d: Optional[float] = None
    value_change_7d: Optional[float] = None
    value_change_30d: Optional[float] = None
    value_change_pct_1d: Optional[float] = None
    value_change_pct_7d: Optional[float] = None
    value_change_pct_30d: Optional[float] = None
    breakdown: Optional[dict[str, Any]] = None
    top_gainers: Optional[list[dict[str, Any]]] = None
    top_losers: Optional[list[dict[str, Any]]] = None

    class Config:
        from_attributes = True


class PortfolioHistoryResponse(BaseModel):
    """Response for portfolio history."""
    snapshots: list[PortfolioSnapshotResponse]
    days: int


class PortfolioSummaryResponse(BaseModel):
    """Response for current portfolio summary."""
    total_value: float
    total_cost: float
    total_cards: int
    unique_cards: int
    profit_loss: float
    profit_loss_pct: float
    value_change_1d: Optional[float] = None
    value_change_7d: Optional[float] = None
    value_change_30d: Optional[float] = None
    value_change_pct_1d: Optional[float] = None
    value_change_pct_7d: Optional[float] = None
    value_change_pct_30d: Optional[float] = None
    top_gainers: Optional[list[dict[str, Any]]] = None
    top_losers: Optional[list[dict[str, Any]]] = None


def snapshot_to_response(snapshot) -> PortfolioSnapshotResponse:
    """Convert PortfolioSnapshot to response schema."""
    return PortfolioSnapshotResponse(
        id=snapshot.id,
        snapshot_date=snapshot.snapshot_date.isoformat(),
        total_value=snapshot.total_value,
        total_cost=snapshot.total_cost,
        total_cards=snapshot.total_cards,
        unique_cards=snapshot.unique_cards,
        value_change_1d=snapshot.value_change_1d,
        value_change_7d=snapshot.value_change_7d,
        value_change_30d=snapshot.value_change_30d,
        value_change_pct_1d=snapshot.value_change_pct_1d,
        value_change_pct_7d=snapshot.value_change_pct_7d,
        value_change_pct_30d=snapshot.value_change_pct_30d,
        breakdown=snapshot.breakdown,
        top_gainers=snapshot.top_gainers,
        top_losers=snapshot.top_losers,
    )


@router.get("/history", response_model=PortfolioHistoryResponse)
async def get_portfolio_history(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioHistoryResponse:
    """
    Get portfolio value history for the current user.

    Returns daily snapshots for the specified number of days.
    """
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Days must be between 1 and 365",
        )

    service = PortfolioService(db)
    snapshots = await service.get_history(current_user.id, days)

    return PortfolioHistoryResponse(
        snapshots=[snapshot_to_response(s) for s in snapshots],
        days=days,
    )


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioSummaryResponse:
    """
    Get current portfolio summary with value changes.
    """
    service = PortfolioService(db)

    # Get or create today's snapshot
    snapshot = await service.create_snapshot(current_user.id)

    profit_loss = snapshot.total_value - snapshot.total_cost
    profit_loss_pct = (
        (profit_loss / snapshot.total_cost * 100)
        if snapshot.total_cost > 0
        else 0.0
    )

    return PortfolioSummaryResponse(
        total_value=snapshot.total_value,
        total_cost=snapshot.total_cost,
        total_cards=snapshot.total_cards,
        unique_cards=snapshot.unique_cards,
        profit_loss=profit_loss,
        profit_loss_pct=profit_loss_pct,
        value_change_1d=snapshot.value_change_1d,
        value_change_7d=snapshot.value_change_7d,
        value_change_30d=snapshot.value_change_30d,
        value_change_pct_1d=snapshot.value_change_pct_1d,
        value_change_pct_7d=snapshot.value_change_pct_7d,
        value_change_pct_30d=snapshot.value_change_pct_30d,
        top_gainers=snapshot.top_gainers,
        top_losers=snapshot.top_losers,
    )


@router.post("/snapshot", response_model=PortfolioSnapshotResponse)
async def create_snapshot(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioSnapshotResponse:
    """
    Create or update today's portfolio snapshot.

    This is automatically called when getting the summary,
    but can be called manually to force a refresh.
    """
    service = PortfolioService(db)
    snapshot = await service.create_snapshot(current_user.id)
    return snapshot_to_response(snapshot)


@router.get("/chart-data")
async def get_chart_data(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Get simplified chart data for portfolio value over time.

    Returns arrays suitable for charting libraries.
    """
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Days must be between 1 and 365",
        )

    service = PortfolioService(db)
    snapshots = await service.get_history(current_user.id, days)

    return {
        "labels": [s.snapshot_date.strftime("%Y-%m-%d") for s in snapshots],
        "values": [s.total_value for s in snapshots],
        "costs": [s.total_cost for s in snapshots],
    }


class PortfolioIntelligence(BaseModel):
    """Portfolio intelligence insights."""
    # Health metrics
    health_score: int  # 0-100
    health_factors: list[dict[str, Any]]

    # Diversification
    diversification_score: int  # 0-100
    format_breakdown: dict[str, float]  # % by format
    color_breakdown: dict[str, float]  # % by color
    rarity_breakdown: dict[str, float]  # % by rarity

    # Risk assessment
    volatility_score: int  # 0-100
    concentration_risk: float  # % in top 5 cards
    reprint_risk_cards: list[dict[str, Any]]

    # Signals summary
    bullish_signals: int
    bearish_signals: int
    active_alerts: int

    # Suggestions
    suggestions: list[dict[str, Any]]


@router.get("/intelligence", response_model=PortfolioIntelligence)
async def get_portfolio_intelligence(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioIntelligence:
    """
    Get AI-powered portfolio intelligence insights.

    Analyzes portfolio composition, risk, and provides suggestions.
    """
    from sqlalchemy import text, select, func
    from app.models.inventory import InventoryItem
    from app.models.card import Card
    from app.models.signal import Signal
    from datetime import date, timedelta

    # Get inventory items with card details
    result = await db.execute(
        select(InventoryItem, Card)
        .join(Card, InventoryItem.card_id == Card.id)
        .where(InventoryItem.user_id == current_user.id)
    )
    items = result.all()

    if not items:
        return PortfolioIntelligence(
            health_score=0,
            health_factors=[{"factor": "empty_portfolio", "message": "Add cards to get insights"}],
            diversification_score=0,
            format_breakdown={},
            color_breakdown={},
            rarity_breakdown={},
            volatility_score=0,
            concentration_risk=0.0,
            reprint_risk_cards=[],
            bullish_signals=0,
            bearish_signals=0,
            active_alerts=0,
            suggestions=[{"type": "info", "message": "Add cards to your inventory to see insights"}],
        )

    # Calculate portfolio totals
    total_value = sum((item[0].current_value or 0) * item[0].quantity for item in items)
    total_cards = sum(item[0].quantity for item in items)
    unique_cards = len(items)

    # Format breakdown (from card legalities)
    format_values = {"commander": 0, "modern": 0, "standard": 0, "legacy": 0, "other": 0}
    for item, card in items:
        value = (item.current_value or 0) * item.quantity
        legalities = card.legalities if hasattr(card, 'legalities') and card.legalities else {}
        if isinstance(legalities, str):
            try:
                legalities = json.loads(legalities)
            except json.JSONDecodeError:
                legalities = {}

        if legalities.get("commander") == "legal":
            format_values["commander"] += value
        elif legalities.get("modern") == "legal":
            format_values["modern"] += value
        elif legalities.get("standard") == "legal":
            format_values["standard"] += value
        elif legalities.get("legacy") == "legal":
            format_values["legacy"] += value
        else:
            format_values["other"] += value

    format_breakdown = {
        k: round(v / total_value * 100, 1) if total_value > 0 else 0
        for k, v in format_values.items() if v > 0
    }

    # Color breakdown
    color_values = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0, "Multi": 0}
    for item, card in items:
        value = (item.current_value or 0) * item.quantity
        colors = card.colors if hasattr(card, 'colors') and card.colors else []
        if isinstance(colors, str):
            colors = list(colors)

        if len(colors) > 1:
            color_values["Multi"] += value
        elif len(colors) == 1:
            color_values[colors[0]] += value
        else:
            color_values["C"] += value

    color_breakdown = {
        k: round(v / total_value * 100, 1) if total_value > 0 else 0
        for k, v in color_values.items() if v > 0
    }

    # Rarity breakdown
    rarity_values = {"mythic": 0, "rare": 0, "uncommon": 0, "common": 0}
    for item, card in items:
        value = (item.current_value or 0) * item.quantity
        rarity = (card.rarity or "common").lower()
        if rarity in rarity_values:
            rarity_values[rarity] += value

    rarity_breakdown = {
        k: round(v / total_value * 100, 1) if total_value > 0 else 0
        for k, v in rarity_values.items() if v > 0
    }

    # Concentration risk (top 5 cards as % of portfolio)
    sorted_items = sorted(items, key=lambda x: (x[0].current_value or 0) * x[0].quantity, reverse=True)
    top_5_value = sum((item[0].current_value or 0) * item[0].quantity for item, _ in sorted_items[:5])
    concentration_risk = round(top_5_value / total_value * 100, 1) if total_value > 0 else 0

    # Diversification score (based on unique cards and spread)
    diversification_score = min(100, int(
        (unique_cards / 20) * 30 +  # More unique cards = better
        (100 - concentration_risk) * 0.4 +  # Lower concentration = better
        len(color_breakdown) * 5 +  # More colors = better
        len(format_breakdown) * 5  # More formats = better
    ))

    # Get signals for portfolio cards
    card_ids = [item[0].card_id for item in items]
    week_ago = date.today() - timedelta(days=7)

    signals_result = await db.execute(
        select(Signal)
        .where(Signal.card_id.in_(card_ids))
        .where(Signal.date >= week_ago)
    )
    signals = signals_result.scalars().all()

    bullish_types = ["momentum_bullish", "breakout", "trend_reversal_up", "accumulation"]
    bearish_types = ["momentum_bearish", "breakdown", "trend_reversal_down", "distribution"]

    bullish_signals = sum(1 for s in signals if s.signal_type in bullish_types)
    bearish_signals = sum(1 for s in signals if s.signal_type in bearish_types)

    # Volatility score (inverse of stability)
    volatility_score = min(100, int(
        (concentration_risk * 0.4) +  # Concentrated = volatile
        (bearish_signals * 5) +  # Bearish signals = volatile
        (100 - diversification_score) * 0.3  # Less diverse = volatile
    ))

    # Reprint risk (cards on reserved list are safe, others have risk)
    reprint_risk_cards = []
    for item, card in sorted_items[:20]:  # Check top 20 by value
        value = (item.current_value or 0) * item.quantity
        if value >= 20:  # Only care about valuable cards
            # Simple heuristic: mythics from recent sets have reprint risk
            is_reserved = getattr(card, 'reserved_list', False)
            if not is_reserved:
                reprint_risk_cards.append({
                    "card_id": card.id,
                    "name": card.name,
                    "value": round(value, 2),
                    "risk": "medium" if (card.rarity or "").lower() == "mythic" else "low",
                })
            if len(reprint_risk_cards) >= 5:
                break

    # Health factors
    health_factors = []

    if unique_cards < 5:
        health_factors.append({"factor": "low_diversity", "message": "Portfolio has few unique cards", "impact": -20})
    if concentration_risk > 50:
        health_factors.append({"factor": "high_concentration", "message": "Over 50% in top 5 cards", "impact": -15})
    if bullish_signals > bearish_signals:
        health_factors.append({"factor": "bullish_momentum", "message": "More bullish than bearish signals", "impact": +10})
    if bearish_signals > bullish_signals * 2:
        health_factors.append({"factor": "bearish_momentum", "message": "Many bearish signals detected", "impact": -10})
    if len(color_breakdown) >= 4:
        health_factors.append({"factor": "color_diversity", "message": "Good color diversification", "impact": +5})
    if len(format_breakdown) >= 3:
        health_factors.append({"factor": "format_diversity", "message": "Cards playable in multiple formats", "impact": +5})

    # Calculate health score
    base_health = 50
    health_score = base_health + sum(f.get("impact", 0) for f in health_factors)
    health_score = max(0, min(100, health_score))

    # Generate suggestions
    suggestions = []

    if concentration_risk > 50:
        suggestions.append({
            "type": "warning",
            "category": "diversification",
            "message": "Consider diversifying - over 50% of value is in your top 5 cards",
        })

    if unique_cards < 10:
        suggestions.append({
            "type": "info",
            "category": "growth",
            "message": "Building a larger collection helps reduce volatility",
        })

    if bearish_signals > bullish_signals:
        suggestions.append({
            "type": "warning",
            "category": "signals",
            "message": f"{bearish_signals} cards showing bearish signals - review positions",
        })

    if reprint_risk_cards:
        suggestions.append({
            "type": "info",
            "category": "risk",
            "message": f"{len(reprint_risk_cards)} high-value cards may have reprint risk",
        })

    if not suggestions:
        suggestions.append({
            "type": "success",
            "category": "health",
            "message": "Portfolio looks healthy! Keep monitoring for opportunities.",
        })

    # Get active alerts count from want list
    alerts_result = await db.execute(
        text("SELECT COUNT(*) FROM want_list_items WHERE user_id = :user_id AND alert_enabled = TRUE"),
        {"user_id": current_user.id}
    )
    active_alerts = alerts_result.scalar() or 0

    return PortfolioIntelligence(
        health_score=health_score,
        health_factors=health_factors,
        diversification_score=diversification_score,
        format_breakdown=format_breakdown,
        color_breakdown=color_breakdown,
        rarity_breakdown=rarity_breakdown,
        volatility_score=volatility_score,
        concentration_risk=concentration_risk,
        reprint_risk_cards=reprint_risk_cards,
        bullish_signals=bullish_signals,
        bearish_signals=bearish_signals,
        active_alerts=active_alerts,
        suggestions=suggestions,
    )
