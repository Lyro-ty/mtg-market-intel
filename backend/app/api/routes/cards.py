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
from app.models import Card, PriceSnapshot, Marketplace, MetricsCardsDaily, Signal, Recommendation, Listing
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
from app.tasks.ingestion import scrape_marketplace
from app.tasks.analytics import compute_card_metrics
from app.tasks.recommendations import generate_card_recommendations
from app.services.ingestion import ScryfallAdapter
from app.services.agents.analytics import AnalyticsAgent
from app.services.agents.recommendation import RecommendationAgent
from app.services.vectorization.service import VectorizationService
from app.services.vectorization.ingestion import vectorize_card, vectorize_listing

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
        updated_at=datetime.utcnow(),
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
    
    from_date = datetime.utcnow() - timedelta(days=days)
    
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
    
    history = [
        PricePoint(
            date=snapshot.snapshot_time,
            price=float(snapshot.price),
            marketplace=marketplace.name,
            currency=snapshot.currency,
            min_price=float(snapshot.min_price) if snapshot.min_price else None,
            max_price=float(snapshot.max_price) if snapshot.max_price else None,
            num_listings=snapshot.num_listings,
        )
        for snapshot, marketplace in rows
    ]
    
    return CardHistoryResponse(
        card_id=card_id,
        card_name=card.name,
        history=history,
        from_date=from_date,
        to_date=datetime.utcnow(),
        data_points=len(history),
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
    
    from_date = datetime.utcnow().date() - timedelta(days=days)
    
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
    marketplaces = payload.get("marketplaces") if payload else None
    slugs = marketplaces or await _get_enabled_marketplace_slugs(db)
    if not slugs:
        raise HTTPException(status_code=400, detail="No enabled marketplaces to refresh")
    
    task_ids = _dispatch_refresh_tasks(card_id, slugs)
    return {
        "card_id": card_id,
        "marketplaces": slugs,
        "tasks": task_ids,
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
    
    slugs = await _get_enabled_marketplace_slugs(db)
    if not slugs:
        logger.info("Skipping refresh, no marketplaces enabled", card_id=card_id)
        return False, None
    
    _dispatch_refresh_tasks(card_id, slugs)
    reason = "missing_data" if latest_snapshot is None else "stale_data"
    return True, reason


async def _get_enabled_marketplace_slugs(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(Marketplace.slug).where(Marketplace.is_enabled == True)
    )
    return [row[0] for row in result.all()]


def _dispatch_refresh_tasks(card_id: int, marketplace_slugs: list[str]) -> dict:
    """Enqueue ingestion, analytics, and recommendation tasks."""
    task_refs: dict[str, list[dict[str, Optional[str]]]] = {"marketplaces": []}
    
    for slug in marketplace_slugs:
        try:
            result = scrape_marketplace.delay(slug, [card_id])
            task_refs["marketplaces"].append(
                {"slug": slug, "task_id": getattr(result, "id", None)}
            )
        except Exception as exc:  # pragma: no cover - celery misconfig
            logger.warning("Failed to dispatch marketplace scrape", slug=slug, card_id=card_id, error=str(exc))
    
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
    
    1. Fetches latest price from Scryfall (includes TCGPlayer prices)
    2. Fetches real listings from enabled marketplaces (TCGPlayer, Card Kingdom, Cardmarket)
    3. Creates price snapshots and listings
    4. Computes metrics
    5. Generates recommendations
    6. Returns complete card detail
    """
    logger.info("Sync refresh starting", card_id=card.id, card_name=card.name)
    
    # 1. Fetch price from Scryfall
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
                snapshot_time=datetime.utcnow(),
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
    
    # 2. Fetch real listings from enabled marketplaces
    enabled_marketplaces = await _get_enabled_marketplace_slugs(db)
    # Filter out 'scryfall' and 'mock' - we want real marketplaces only
    real_marketplaces = [slug for slug in enabled_marketplaces if slug not in ['scryfall', 'mock']]
    
    listings_created = 0
    snapshots_created = 0
    
    for marketplace_slug in real_marketplaces:
        try:
            # Get marketplace record
            mp_query = select(Marketplace).where(Marketplace.slug == marketplace_slug)
            mp_result = await db.execute(mp_query)
            marketplace = mp_result.scalar_one_or_none()
            
            if not marketplace:
                continue
            
            # Get adapter for this marketplace
            from app.services.ingestion import get_adapter
            adapter = get_adapter(marketplace_slug, cached=False)
            
            try:
                # Fetch price data from marketplace
                price_data = await adapter.fetch_price(
                    card_name=card.name,
                    set_code=card.set_code,
                    collector_number=card.collector_number,
                    scryfall_id=card.scryfall_id,
                )
                
                if price_data and price_data.price > 0:
                    # Create price snapshot
                    snapshot = PriceSnapshot(
                        card_id=card.id,
                        marketplace_id=marketplace.id,
                        snapshot_time=datetime.utcnow(),
                        price=price_data.price,
                        currency=price_data.currency,
                        price_foil=price_data.price_foil,
                        min_price=price_data.price_low,
                        max_price=price_data.price_high,
                        avg_price=price_data.price_mid,
                        median_price=price_data.price_market,
                        num_listings=price_data.num_listings,
                        total_quantity=price_data.total_quantity,
                    )
                    db.add(snapshot)
                    snapshots_created += 1
                
                # Fetch individual listings (this is the key part - real scraping!)
                listings = await adapter.fetch_listings(
                    card_name=card.name,
                    set_code=card.set_code,
                    scryfall_id=card.scryfall_id,
                    limit=100,  # Get as many listings as possible
                )
                
                # Store listings in database
                for listing_data in listings:
                    # Check if listing already exists by external_id
                    existing_query = select(Listing).where(
                        Listing.external_id == listing_data.external_id,
                        Listing.marketplace_id == marketplace.id,
                    )
                    existing_result = await db.execute(existing_query)
                    existing = existing_result.scalar_one_or_none()
                    
                    if existing:
                        # Update existing listing
                        existing.condition = listing_data.condition
                        existing.language = listing_data.language
                        existing.is_foil = listing_data.is_foil
                        existing.price = listing_data.price
                        existing.currency = listing_data.currency
                        existing.quantity = listing_data.quantity
                        existing.seller_name = listing_data.seller_name
                        existing.seller_rating = listing_data.seller_rating
                        existing.listing_url = listing_data.listing_url
                        existing.last_seen_at = datetime.utcnow()
                    else:
                        # Create new listing
                        listing = Listing(
                            card_id=card.id,
                            marketplace_id=marketplace.id,
                            condition=listing_data.condition,
                            language=listing_data.language,
                            is_foil=listing_data.is_foil,
                            price=listing_data.price,
                            currency=listing_data.currency,
                            quantity=listing_data.quantity,
                            seller_name=listing_data.seller_name,
                            seller_rating=listing_data.seller_rating,
                            external_id=listing_data.external_id,
                            listing_url=listing_data.listing_url,
                            last_seen_at=datetime.utcnow(),
                        )
                        db.add(listing)
                        listings_created += 1
                
                logger.info(
                    "Fetched listings from marketplace",
                    marketplace=marketplace_slug,
                    card_id=card.id,
                    listings_count=len(listings),
                )
                
            except Exception as e:
                logger.warning(
                    "Failed to fetch from marketplace",
                    marketplace=marketplace_slug,
                    card_id=card.id,
                    error=str(e),
                )
            finally:
                # Close adapter to release resources
                if hasattr(adapter, 'close'):
                    await adapter.close()
                    
        except Exception as e:
            logger.warning(
                "Error processing marketplace",
                marketplace=marketplace_slug,
                card_id=card.id,
                error=str(e),
            )
    
    await db.flush()
    logger.info(
        "Marketplace listings fetched",
        card_id=card.id,
        listings_created=listings_created,
        snapshots_created=snapshots_created,
    )
    
    # 2.5. Vectorize card and listings for ML training
    vectorizer = VectorizationService()
    vectors_created = 0
    try:
        # Vectorize the card
        card_vector_obj = await vectorize_card(db, card, vectorizer)
        if card_vector_obj:
            vectors_created += 1
            await db.flush()
        
        # Vectorize all listings for this card
        listings_query = select(Listing).where(Listing.card_id == card.id)
        listings_result = await db.execute(listings_query)
        all_listings = listings_result.scalars().all()
        
        for listing in all_listings:
            listing_vector = await vectorize_listing(db, listing, card_vector_obj, vectorizer)
            if listing_vector:
                vectors_created += 1
        
        await db.flush()
        logger.info(
            "Vectorization completed",
            card_id=card.id,
            vectors_created=vectors_created,
        )
    except Exception as e:
        logger.warning("Failed to vectorize card data", card_id=card.id, error=str(e))
    finally:
        vectorizer.close()
    
    # 3. Compute metrics
    try:
        analytics = AnalyticsAgent(db)
        metrics = await analytics.compute_daily_metrics(card.id)
        if metrics:
            await db.flush()
            logger.info("Metrics computed", card_id=card.id)
    except Exception as e:
        logger.warning("Failed to compute metrics", card_id=card.id, error=str(e))
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
    
    await db.commit()
    
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

