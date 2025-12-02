"""
Card-related API endpoints.
"""
import json
from datetime import datetime, timedelta, time, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models import Card, PriceSnapshot, Marketplace, MetricsCardsDaily, Signal, Recommendation
from app.schemas.card import (
    CardResponse,
    CardSearchResponse,
    CardDetailResponse,
    CardPriceResponse,
    CardHistoryResponse,
    CardMetricsResponse,
    MarketplacePriceDetail,
    PricePoint,
    SignalSummary,
    RecommendationSummary,
)
from app.schemas.signal import SignalResponse, SignalListResponse
from app.tasks.analytics import compute_card_metrics
from app.tasks.recommendations import generate_card_recommendations
from app.services.ingestion import ScryfallAdapter
from app.services.agents.analytics import AnalyticsAgent
from app.services.agents.recommendation import RecommendationAgent
from app.services.vectorization.service import VectorizationService
from app.services.vectorization.ingestion import vectorize_card

router = APIRouter()
logger = structlog.get_logger(__name__)

REFRESH_THRESHOLD_HOURS = 24


@router.get("/search", response_model=CardSearchResponse)
async def search_cards(
    q: str = Query(..., min_length=1, description="Search query"),
    set_code: Optional[str] = Query(None, description="Filter by set code"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for cards by name.
    
    Supports partial matching and optional set filtering.
    """
    # Build query
    query = select(Card).where(Card.name.ilike(f"%{q}%"))
    
    if set_code:
        query = query.where(Card.set_code == set_code.upper())
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Apply pagination
    query = query.order_by(Card.name).offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    cards = result.scalars().all()
    
    return CardSearchResponse(
        cards=[CardResponse.model_validate(c) for c in cards],
        total=total or 0,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < (total or 0),
    )


@router.get("/{card_id}", response_model=CardDetailResponse)
async def get_card(
    card_id: int,
    refresh_if_stale: bool = Query(True, description="Automatically refresh data if stale"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed information about a card.
    
    Includes current prices, metrics, signals, and recommendations.
    """
    # Get card
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    # Get latest metrics
    metrics_query = select(MetricsCardsDaily).where(
        MetricsCardsDaily.card_id == card_id
    ).order_by(MetricsCardsDaily.date.desc()).limit(1)
    result = await db.execute(metrics_query)
    metrics = result.scalar_one_or_none()
    
    # Get current prices
    current_prices = await _get_current_prices(db, card_id)
    
    # Get recent signals
    signals_query = select(Signal).where(
        Signal.card_id == card_id
    ).order_by(Signal.date.desc()).limit(5)
    result = await db.execute(signals_query)
    signals = result.scalars().all()
    
    # Get active recommendations
    recs_query = select(Recommendation).where(
        Recommendation.card_id == card_id,
        Recommendation.is_active == True,
    ).order_by(Recommendation.created_at.desc()).limit(5)
    result = await db.execute(recs_query)
    recommendations = result.scalars().all()
    
    refresh_requested = False
    refresh_reason: Optional[str] = None
    if refresh_if_stale:
        refresh_requested, refresh_reason = await _maybe_trigger_refresh(db, card_id, metrics)
    
    return CardDetailResponse(
        card=CardResponse.model_validate(card),
        metrics=CardMetricsResponse(
            card_id=card_id,
            date=str(metrics.date) if metrics else None,
            avg_price=float(metrics.avg_price) if metrics and metrics.avg_price else None,
            min_price=float(metrics.min_price) if metrics and metrics.min_price else None,
            max_price=float(metrics.max_price) if metrics and metrics.max_price else None,
            spread_pct=float(metrics.spread_pct) if metrics and metrics.spread_pct else None,
            price_change_7d=float(metrics.price_change_pct_7d) if metrics and metrics.price_change_pct_7d else None,
            price_change_30d=float(metrics.price_change_pct_30d) if metrics and metrics.price_change_pct_30d else None,
            volatility_7d=float(metrics.volatility_7d) if metrics and metrics.volatility_7d else None,
            ma_7d=float(metrics.ma_7d) if metrics and metrics.ma_7d else None,
            ma_30d=float(metrics.ma_30d) if metrics and metrics.ma_30d else None,
            total_listings=metrics.total_listings if metrics else None,
        ) if metrics else None,
        current_prices=current_prices,
        recent_signals=[
            SignalSummary(
                signal_type=s.signal_type,
                value=float(s.value) if s.value else None,
                confidence=float(s.confidence) if s.confidence else None,
                date=str(s.date),
                llm_insight=s.llm_insight,
            )
            for s in signals
        ],
        active_recommendations=[
            RecommendationSummary(
                action=r.action,
                confidence=float(r.confidence),
                rationale=r.rationale,
                marketplace=None,
                potential_profit_pct=float(r.potential_profit_pct) if r.potential_profit_pct else None,
            )
            for r in recommendations
        ],
        refresh_requested=refresh_requested,
        refresh_reason=refresh_reason,
    )


@router.get("/{card_id}/prices", response_model=CardPriceResponse)
async def get_card_prices(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get current prices for a card across all marketplaces.
    """
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    prices = await _get_current_prices(db, card_id)
    
    lowest = min((p.price for p in prices), default=None)
    highest = max((p.price for p in prices), default=None)
    spread_pct = ((highest - lowest) / lowest * 100) if lowest and highest and lowest > 0 else None
    
    return CardPriceResponse(
        card_id=card_id,
        card_name=card.name,
        prices=prices,
        lowest_price=lowest,
        highest_price=highest,
        spread_pct=spread_pct,
        updated_at=datetime.now(timezone.utc),
    )


@router.get("/{card_id}/history", response_model=CardHistoryResponse)
async def get_card_history(
    card_id: int,
    days: int = Query(30, ge=1, le=365),
    marketplace_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get price history for a card.
    
    Returns daily price points for the specified time range.
    """
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    from_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Build query
    query = select(PriceSnapshot, Marketplace).join(
        Marketplace, PriceSnapshot.marketplace_id == Marketplace.id
    ).where(
        PriceSnapshot.card_id == card_id,
        PriceSnapshot.snapshot_time >= from_date,
    )
    
    if marketplace_id:
        query = query.where(PriceSnapshot.marketplace_id == marketplace_id)
    
    query = query.order_by(PriceSnapshot.snapshot_time)
    
    result = await db.execute(query)
    rows = result.all()
    
    now = datetime.now(timezone.utc)
    
    # Helper function to ensure timezone-aware datetime
    def ensure_timezone_aware(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    
    history = [
        PricePoint(
            date=snapshot.snapshot_time,
            price=float(snapshot.price),
            marketplace=marketplace.name,
            currency=snapshot.currency,
            min_price=float(snapshot.min_price) if snapshot.min_price else None,
            max_price=float(snapshot.max_price) if snapshot.max_price else None,
            num_listings=snapshot.num_listings,
            snapshot_time=snapshot.snapshot_time,
            data_age_minutes=int((now - ensure_timezone_aware(snapshot.snapshot_time)).total_seconds() / 60) if snapshot.snapshot_time else None,
        )
        for snapshot, marketplace in rows
    ]
    
    # Find latest snapshot time
    latest_snapshot = max((snapshot.snapshot_time for snapshot, _ in rows), default=None) if rows else None
    if latest_snapshot:
        latest_snapshot = ensure_timezone_aware(latest_snapshot)
    data_freshness = int((now - latest_snapshot).total_seconds() / 60) if latest_snapshot else None
    
    return CardHistoryResponse(
        card_id=card_id,
        card_name=card.name,
        history=history,
        from_date=from_date,
        to_date=now,
        data_points=len(history),
        latest_snapshot_time=latest_snapshot,
        data_freshness_minutes=data_freshness,
    )


@router.get("/{card_id}/signals", response_model=SignalListResponse)
async def get_card_signals(
    card_id: int,
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """
    Get analytics signals for a card.
    """
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    from_date = datetime.now(timezone.utc).date() - timedelta(days=days)
    
    query = select(Signal).where(
        Signal.card_id == card_id,
        Signal.date >= from_date,
    ).order_by(Signal.date.desc())
    
    result = await db.execute(query)
    signals = result.scalars().all()
    
    return SignalListResponse(
        card_id=card_id,
        signals=[
            SignalResponse(
                id=s.id,
                card_id=s.card_id,
                date=s.date,
                signal_type=s.signal_type,
                value=float(s.value) if s.value else None,
                confidence=float(s.confidence) if s.confidence else None,
                details=json.loads(s.details) if s.details else None,
                llm_insight=s.llm_insight,
                llm_provider=s.llm_provider,
                created_at=str(s.created_at) if s.created_at else None,
            )
            for s in signals
        ],
        total=len(signals),
    )


@router.post("/{card_id}/refresh")
async def refresh_card_data(
    card_id: int,
    payload: dict | None = None,
    sync: bool = Query(True, description="Run synchronously and return updated data immediately"),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger a refresh for a card's prices, metrics, and recommendations.
    
    If sync=True (default), fetches data immediately and returns updated card detail.
    If sync=False, dispatches background tasks and returns task IDs.
    """
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    if sync:
        # Synchronous refresh - fetch data immediately and return
        return await _sync_refresh_card(db, card)
    
    # Async refresh - dispatch background tasks
    # Note: Price collection is handled by scheduled tasks, so we only dispatch analytics/recommendations
    task_ids = _dispatch_refresh_tasks(card_id, [])
    return {
        "card_id": card_id,
        "tasks": task_ids,
        "note": "Price collection is handled by scheduled tasks (collect_price_data, collect_inventory_prices)",
    }


async def _get_current_prices(
    db: AsyncSession,
    card_id: int,
) -> list[MarketplacePriceDetail]:
    """Get latest price from each marketplace for a card."""
    # Subquery to get latest snapshot per marketplace
    subq = select(
        PriceSnapshot.marketplace_id,
        func.max(PriceSnapshot.snapshot_time).label("latest_time"),
    ).where(
        PriceSnapshot.card_id == card_id
    ).group_by(PriceSnapshot.marketplace_id).subquery()
    
    # Join to get full snapshot data
    query = select(PriceSnapshot, Marketplace).join(
        Marketplace, PriceSnapshot.marketplace_id == Marketplace.id
    ).join(
        subq,
        (PriceSnapshot.marketplace_id == subq.c.marketplace_id) &
        (PriceSnapshot.snapshot_time == subq.c.latest_time)
    ).where(
        PriceSnapshot.card_id == card_id
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    return [
        MarketplacePriceDetail(
            marketplace_id=marketplace.id,
            marketplace_name=marketplace.name,
            marketplace_slug=marketplace.slug,
            price=float(snapshot.price),
            currency=snapshot.currency,
            price_foil=float(snapshot.price_foil) if snapshot.price_foil else None,
            num_listings=snapshot.num_listings,
            last_updated=snapshot.snapshot_time,
        )
        for snapshot, marketplace in rows
    ]


async def _maybe_trigger_refresh(
    db: AsyncSession,
    card_id: int,
    metrics: MetricsCardsDaily | None,
) -> tuple[bool, Optional[str]]:
    """Trigger background refresh if data is stale."""
    threshold = datetime.now(timezone.utc) - timedelta(hours=REFRESH_THRESHOLD_HOURS)
    
    result = await db.execute(
        select(func.max(PriceSnapshot.snapshot_time)).where(PriceSnapshot.card_id == card_id)
    )
    latest_snapshot = result.scalar_one_or_none()
    
    metrics_stale = True
    if metrics and metrics.date:
        metrics_dt = datetime.combine(metrics.date, time.min, tzinfo=timezone.utc)
        metrics_stale = metrics_dt < threshold
    
    if latest_snapshot and latest_snapshot.tzinfo is None:
        latest_snapshot = latest_snapshot.replace(tzinfo=timezone.utc)
    
    prices_stale = latest_snapshot is None or latest_snapshot < threshold
    
    if not (metrics_stale or prices_stale):
        return False, None
    
    # Dispatch analytics and recommendation tasks
    # Note: Price collection is handled by scheduled tasks (collect_price_data, collect_inventory_prices)
    _dispatch_refresh_tasks(card_id, [])
    reason = "missing_data" if latest_snapshot is None else "stale_data"
    return True, reason


async def _get_enabled_marketplace_slugs(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(Marketplace.slug).where(Marketplace.is_enabled == True)
    )
    return [row[0] for row in result.all()]


def _dispatch_refresh_tasks(card_id: int, marketplace_slugs: list[str]) -> dict:
    """
    Enqueue analytics and recommendation tasks.
    
    Note: Price collection is now handled by scheduled tasks (collect_price_data, collect_inventory_prices).
    This function only dispatches analytics and recommendation tasks.
    """
    task_refs: dict[str, Optional[str]] = {}
    
    try:
        analytics_task = compute_card_metrics.delay(card_id)
        task_refs["analytics"] = getattr(analytics_task, "id", None)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to dispatch analytics task", card_id=card_id, error=str(exc))
        task_refs["analytics"] = None
    
    try:
        rec_task = generate_card_recommendations.delay(card_id)
        task_refs["recommendations"] = getattr(rec_task, "id", None)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to dispatch recommendation task", card_id=card_id, error=str(exc))
        task_refs["recommendations"] = None
    
    return task_refs


async def _sync_refresh_card(db: AsyncSession, card: Card) -> CardDetailResponse:
    """
    Synchronously refresh card data and return updated detail.
    
    1. Fetches latest price from Scryfall (aggregated prices from TCGPlayer, Cardmarket, etc.)
    2. Creates price snapshot
    3. Computes metrics
    4. Generates recommendations
    5. Returns complete card detail
    
    Note: We no longer scrape individual listings. Focus on aggregated price data from Scryfall.
    """
    logger.info("Sync refresh starting", card_id=card.id, card_name=card.name)
    
    # 1. Fetch price from Scryfall
    price_data = None  # Initialize to avoid UnboundLocalError
    scryfall = ScryfallAdapter()
    try:
        price_data = await scryfall.fetch_price(
            card_name=card.name,
            set_code=card.set_code,
            collector_number=card.collector_number,
            scryfall_id=card.scryfall_id,
        )
        
        if price_data and price_data.price > 0:
            # Get or create Scryfall marketplace entry
            scryfall_mp = await _get_or_create_scryfall_marketplace(db)
            
            # Create price snapshot
            snapshot = PriceSnapshot(
                card_id=card.id,
                marketplace_id=scryfall_mp.id,
                snapshot_time=datetime.now(timezone.utc),
                price=price_data.price,
                currency=price_data.currency,
                price_foil=price_data.price_foil,
            )
            db.add(snapshot)
            await db.flush()
            logger.info("Price snapshot created", card_id=card.id, price=price_data.price)
    except Exception as e:
        logger.warning("Failed to fetch Scryfall price", card_id=card.id, error=str(e))
    finally:
        await scryfall.close()
    
    # 2. Fetch and aggregate MTGJSON 30-day historical data
    mtgjson_snapshots_created = 0
    from app.services.ingestion import get_adapter
    mtgjson = get_adapter("mtgjson", cached=False)
    try:
        # Get or create MTGJSON marketplace
        mtgjson_query = select(Marketplace).where(Marketplace.slug == "mtgjson")
        result = await db.execute(mtgjson_query)
        mtgjson_marketplace = result.scalar_one_or_none()
        
        if not mtgjson_marketplace:
            mtgjson_marketplace = Marketplace(
                name="MTGJSON",
                slug="mtgjson",
                base_url="https://mtgjson.com",
                api_url="https://mtgjson.com/api/v5",
                is_enabled=True,
                supports_api=True,
                default_currency="USD",
                rate_limit_seconds=1.0,
            )
            db.add(mtgjson_marketplace)
            await db.flush()
        
        # Fetch 30-day historical prices from MTGJSON
        historical_prices = await mtgjson.fetch_price_history(
            card_name=card.name,
            set_code=card.set_code,
            collector_number=card.collector_number,
            scryfall_id=card.scryfall_id,
            days=30,  # 30-day historical data
        )
        
        if historical_prices:
            # Create price snapshots for historical data (only if they don't exist)
            for price_data in historical_prices:
                # Check if snapshot already exists for this timestamp
                existing_query = select(PriceSnapshot).where(
                    PriceSnapshot.card_id == card.id,
                    PriceSnapshot.marketplace_id == mtgjson_marketplace.id,
                    PriceSnapshot.snapshot_time == price_data.snapshot_time,
                )
                existing_result = await db.execute(existing_query)
                existing = existing_result.scalar_one_or_none()
                
                if not existing and price_data.price > 0:
                    snapshot = PriceSnapshot(
                        card_id=card.id,
                        marketplace_id=mtgjson_marketplace.id,
                        snapshot_time=price_data.snapshot_time,
                        price=price_data.price,
                        currency=price_data.currency,
                        price_foil=price_data.price_foil,
                    )
                    db.add(snapshot)
                    mtgjson_snapshots_created += 1
            
            logger.info(
                "MTGJSON historical data aggregated",
                card_id=card.id,
                historical_points=len(historical_prices),
                snapshots_created=mtgjson_snapshots_created,
            )
    except Exception as e:
        logger.warning(
            "Failed to fetch MTGJSON historical data",
            card_id=card.id,
            error=str(e),
        )
    finally:
        await mtgjson.close()
    
    # 3. Price data is already collected from Scryfall above
    # We no longer scrape individual listings - focus on aggregated price data
    scryfall_snapshots_created = 1 if price_data and price_data.price > 0 else 0
    total_snapshots_created = scryfall_snapshots_created + mtgjson_snapshots_created
    
    await db.flush()
    logger.info(
        "Price data refreshed",
        card_id=card.id,
        scryfall_snapshots=scryfall_snapshots_created,
        mtgjson_snapshots=mtgjson_snapshots_created,
        total_snapshots=total_snapshots_created,
    )
    
    # 2.5. Vectorize card for ML training
    from app.services.vectorization import get_vectorization_service
    vectorizer = get_vectorization_service()  # Use cached instance
    vectors_created = 0
    try:
        # Vectorize the card (used for training with price snapshots)
        card_vector_obj = await vectorize_card(db, card, vectorizer)
        if card_vector_obj:
            vectors_created += 1
            await db.flush()
            logger.info(
                "Card vectorization completed",
                card_id=card.id,
                vectors_created=vectors_created,
            )
    except Exception as e:
        logger.warning("Failed to vectorize card data", card_id=card.id, error=str(e))
    # Don't close the cached vectorizer - it's shared across requests
    
    # 3. Compute metrics
    try:
        analytics = AnalyticsAgent(db)
        metrics = await analytics.compute_daily_metrics(card.id)
        if metrics:
            await db.flush()
            logger.info("Metrics computed", card_id=card.id)
    except Exception as e:
        logger.warning("Failed to compute metrics", card_id=card.id, error=str(e))
        # Check if transaction needs rollback
        try:
            await db.rollback()
        except Exception:
            pass  # Already rolled back
        metrics = None
    
    # 4. Generate signals
    signals = []
    try:
        analytics = AnalyticsAgent(db)
        signals = await analytics.generate_signals(card.id)
        if signals:
            await db.flush()
            logger.info("Signals generated", card_id=card.id, count=len(signals))
    except Exception as e:
        logger.warning("Failed to generate signals", card_id=card.id, error=str(e))
        # Check if transaction needs rollback
        try:
            await db.rollback()
        except Exception:
            pass  # Already rolled back
    
    # 5. Generate recommendations
    recommendations = []
    try:
        rec_agent = RecommendationAgent(db)
        recommendations = await rec_agent.generate_recommendations(card.id)
        if recommendations:
            await db.flush()
            logger.info("Recommendations generated", card_id=card.id, count=len(recommendations))
    except Exception as e:
        logger.warning("Failed to generate recommendations", card_id=card.id, error=str(e))
        # Rollback the transaction if there was a database error
        try:
            await db.rollback()
        except Exception:
            pass  # Already rolled back
        # Don't re-raise - allow the refresh to complete even if recommendations fail
        # The other data (listings, snapshots, metrics) is still valuable
    
    try:
        await db.commit()
    except Exception as e:
        logger.error("Failed to commit transaction", card_id=card.id, error=str(e))
        try:
            await db.rollback()
        except Exception:
            pass
        raise
    
    # 6. Fetch and return updated card detail
    # Re-fetch metrics (might have been updated)
    metrics_query = select(MetricsCardsDaily).where(
        MetricsCardsDaily.card_id == card.id
    ).order_by(MetricsCardsDaily.date.desc()).limit(1)
    result = await db.execute(metrics_query)
    latest_metrics = result.scalar_one_or_none()
    
    # Get current prices
    current_prices = await _get_current_prices(db, card.id)
    
    # Get recent signals
    signals_query = select(Signal).where(
        Signal.card_id == card.id
    ).order_by(Signal.date.desc()).limit(5)
    result = await db.execute(signals_query)
    recent_signals = result.scalars().all()
    
    # Get active recommendations
    recs_query = select(Recommendation).where(
        Recommendation.card_id == card.id,
        Recommendation.is_active == True,
    ).order_by(Recommendation.created_at.desc()).limit(5)
    result = await db.execute(recs_query)
    active_recs = result.scalars().all()
    
    return CardDetailResponse(
        card=CardResponse.model_validate(card),
        metrics=CardMetricsResponse(
            card_id=card.id,
            date=str(latest_metrics.date) if latest_metrics else None,
            avg_price=float(latest_metrics.avg_price) if latest_metrics and latest_metrics.avg_price else None,
            min_price=float(latest_metrics.min_price) if latest_metrics and latest_metrics.min_price else None,
            max_price=float(latest_metrics.max_price) if latest_metrics and latest_metrics.max_price else None,
            spread_pct=float(latest_metrics.spread_pct) if latest_metrics and latest_metrics.spread_pct else None,
            price_change_7d=float(latest_metrics.price_change_pct_7d) if latest_metrics and latest_metrics.price_change_pct_7d else None,
            price_change_30d=float(latest_metrics.price_change_pct_30d) if latest_metrics and latest_metrics.price_change_pct_30d else None,
            volatility_7d=float(latest_metrics.volatility_7d) if latest_metrics and latest_metrics.volatility_7d else None,
            ma_7d=float(latest_metrics.ma_7d) if latest_metrics and latest_metrics.ma_7d else None,
            ma_30d=float(latest_metrics.ma_30d) if latest_metrics and latest_metrics.ma_30d else None,
            total_listings=latest_metrics.total_listings if latest_metrics else None,
        ) if latest_metrics else None,
        current_prices=current_prices,
        recent_signals=[
            SignalSummary(
                signal_type=s.signal_type,
                value=float(s.value) if s.value else None,
                confidence=float(s.confidence) if s.confidence else None,
                date=str(s.date),
                llm_insight=s.llm_insight,
            )
            for s in recent_signals
        ],
        active_recommendations=[
            RecommendationSummary(
                action=r.action,
                confidence=float(r.confidence),
                rationale=r.rationale,
                marketplace=None,
                potential_profit_pct=float(r.potential_profit_pct) if r.potential_profit_pct else None,
            )
            for r in active_recs
        ],
        refresh_requested=False,
        refresh_reason=None,
    )


async def _get_or_create_scryfall_marketplace(db: AsyncSession) -> Marketplace:
    """Get or create the Scryfall marketplace entry."""
    query = select(Marketplace).where(Marketplace.slug == "scryfall")
    result = await db.execute(query)
    marketplace = result.scalar_one_or_none()
    
    if not marketplace:
        marketplace = Marketplace(
            name="Scryfall (TCGPlayer)",
            slug="scryfall",
            base_url="https://scryfall.com",
            is_enabled=True,
            supports_api=True,
            default_currency="USD",
        )
        db.add(marketplace)
        await db.flush()
    
    return marketplace

