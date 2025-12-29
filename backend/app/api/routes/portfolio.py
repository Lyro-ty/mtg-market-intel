"""API routes for portfolio history."""
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
