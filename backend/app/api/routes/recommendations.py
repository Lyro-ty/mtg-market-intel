"""
Recommendation-related API endpoints.
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Recommendation, Card, Marketplace
from app.schemas.recommendation import (
    RecommendationResponse,
    RecommendationListResponse,
    ActionType,
)

router = APIRouter()


@router.get("", response_model=RecommendationListResponse)
async def get_recommendations(
    action: Optional[ActionType] = None,
    min_confidence: Optional[float] = Query(None, ge=0, le=1),
    marketplace_id: Optional[int] = None,
    set_code: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    is_active: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get trading recommendations with optional filters.
    """
    # Build base query
    query = select(Recommendation, Card, Marketplace).join(
        Card, Recommendation.card_id == Card.id
    ).outerjoin(
        Marketplace, Recommendation.marketplace_id == Marketplace.id
    )
    
    # Apply filters
    if is_active:
        query = query.where(Recommendation.is_active == True)
    
    if action:
        query = query.where(Recommendation.action == action.value)
    
    if min_confidence is not None:
        query = query.where(Recommendation.confidence >= min_confidence)
    
    if marketplace_id:
        query = query.where(Recommendation.marketplace_id == marketplace_id)
    
    if set_code:
        query = query.where(Card.set_code == set_code.upper())
    
    if min_price is not None:
        query = query.where(Recommendation.current_price >= min_price)
    
    if max_price is not None:
        query = query.where(Recommendation.current_price <= max_price)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # Get counts by action
    buy_count_q = select(func.count()).where(
        Recommendation.is_active == True,
        Recommendation.action == ActionType.BUY.value,
    )
    sell_count_q = select(func.count()).where(
        Recommendation.is_active == True,
        Recommendation.action == ActionType.SELL.value,
    )
    hold_count_q = select(func.count()).where(
        Recommendation.is_active == True,
        Recommendation.action == ActionType.HOLD.value,
    )
    
    buy_count = await db.scalar(buy_count_q) or 0
    sell_count = await db.scalar(sell_count_q) or 0
    hold_count = await db.scalar(hold_count_q) or 0
    
    # Apply pagination and ordering
    query = query.order_by(
        Recommendation.confidence.desc(),
        Recommendation.created_at.desc(),
    ).offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    rows = result.all()
    
    recommendations = [
        RecommendationResponse(
            id=rec.id,
            card_id=rec.card_id,
            card_name=card.name,
            card_set=card.set_code,
            card_image_url=card.image_url_small,
            marketplace_id=rec.marketplace_id,
            marketplace_name=marketplace.name if marketplace else None,
            action=ActionType(rec.action),
            confidence=float(rec.confidence),
            horizon_days=rec.horizon_days,
            target_price=float(rec.target_price) if rec.target_price else None,
            current_price=float(rec.current_price) if rec.current_price else None,
            potential_profit_pct=float(rec.potential_profit_pct) if rec.potential_profit_pct else None,
            rationale=rec.rationale,
            source_signals=json.loads(rec.source_signals) if rec.source_signals else None,
            valid_until=rec.valid_until,
            is_active=rec.is_active,
            created_at=rec.created_at,
        )
        for rec, card, marketplace in rows
    ]
    
    return RecommendationListResponse(
        recommendations=recommendations,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
        buy_count=buy_count,
        sell_count=sell_count,
        hold_count=hold_count,
    )


@router.get("/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific recommendation by ID.
    """
    query = select(Recommendation, Card, Marketplace).join(
        Card, Recommendation.card_id == Card.id
    ).outerjoin(
        Marketplace, Recommendation.marketplace_id == Marketplace.id
    ).where(Recommendation.id == recommendation_id)
    
    result = await db.execute(query)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    
    rec, card, marketplace = row
    
    return RecommendationResponse(
        id=rec.id,
        card_id=rec.card_id,
        card_name=card.name,
        card_set=card.set_code,
        card_image_url=card.image_url_small,
        marketplace_id=rec.marketplace_id,
        marketplace_name=marketplace.name if marketplace else None,
        action=ActionType(rec.action),
        confidence=float(rec.confidence),
        horizon_days=rec.horizon_days,
        target_price=float(rec.target_price) if rec.target_price else None,
        current_price=float(rec.current_price) if rec.current_price else None,
        potential_profit_pct=float(rec.potential_profit_pct) if rec.potential_profit_pct else None,
        rationale=rec.rationale,
        source_signals=json.loads(rec.source_signals) if rec.source_signals else None,
        valid_until=rec.valid_until,
        is_active=rec.is_active,
        created_at=rec.created_at,
    )


@router.get("/card/{card_id}", response_model=RecommendationListResponse)
async def get_card_recommendations(
    card_id: int,
    is_active: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all recommendations for a specific card.
    """
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    query = select(Recommendation, Card, Marketplace).join(
        Card, Recommendation.card_id == Card.id
    ).outerjoin(
        Marketplace, Recommendation.marketplace_id == Marketplace.id
    ).where(Recommendation.card_id == card_id)
    
    if is_active:
        query = query.where(Recommendation.is_active == True)
    
    query = query.order_by(Recommendation.created_at.desc())
    
    result = await db.execute(query)
    rows = result.all()
    
    recommendations = [
        RecommendationResponse(
            id=rec.id,
            card_id=rec.card_id,
            card_name=card.name,
            card_set=card.set_code,
            card_image_url=card.image_url_small,
            marketplace_id=rec.marketplace_id,
            marketplace_name=marketplace.name if marketplace else None,
            action=ActionType(rec.action),
            confidence=float(rec.confidence),
            horizon_days=rec.horizon_days,
            target_price=float(rec.target_price) if rec.target_price else None,
            current_price=float(rec.current_price) if rec.current_price else None,
            potential_profit_pct=float(rec.potential_profit_pct) if rec.potential_profit_pct else None,
            rationale=rec.rationale,
            source_signals=json.loads(rec.source_signals) if rec.source_signals else None,
            valid_until=rec.valid_until,
            is_active=rec.is_active,
            created_at=rec.created_at,
        )
        for rec, card, marketplace in rows
    ]
    
    return RecommendationListResponse(
        recommendations=recommendations,
        total=len(recommendations),
        page=1,
        page_size=len(recommendations),
        has_more=False,
    )

