"""
Marketplace API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Marketplace
from app.schemas.marketplace import MarketplaceResponse, MarketplaceListResponse

router = APIRouter()


@router.get("", response_model=MarketplaceListResponse)
async def get_marketplaces(
    enabled_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all marketplaces.
    """
    query = select(Marketplace)
    
    if enabled_only:
        query = query.where(Marketplace.is_enabled == True)
    
    query = query.order_by(Marketplace.name)
    
    result = await db.execute(query)
    marketplaces = result.scalars().all()
    
    return MarketplaceListResponse(
        marketplaces=[MarketplaceResponse.model_validate(m) for m in marketplaces],
        total=len(marketplaces),
    )


@router.get("/{marketplace_id}", response_model=MarketplaceResponse)
async def get_marketplace(
    marketplace_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific marketplace by ID.
    """
    marketplace = await db.get(Marketplace, marketplace_id)
    
    if not marketplace:
        raise HTTPException(status_code=404, detail="Marketplace not found")
    
    return MarketplaceResponse.model_validate(marketplace)


@router.patch("/{marketplace_id}/toggle")
async def toggle_marketplace(
    marketplace_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Toggle a marketplace's enabled status.
    """
    marketplace = await db.get(Marketplace, marketplace_id)
    
    if not marketplace:
        raise HTTPException(status_code=404, detail="Marketplace not found")
    
    marketplace.is_enabled = not marketplace.is_enabled
    await db.commit()
    
    return {
        "marketplace_id": marketplace_id,
        "is_enabled": marketplace.is_enabled,
    }

