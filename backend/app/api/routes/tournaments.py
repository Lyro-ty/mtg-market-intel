"""
Tournament-related API endpoints.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models import Tournament, TournamentStanding, Decklist, DecklistCard, CardMetaStats, Card
from app.schemas.tournament import (
    TournamentListResponse,
    TournamentResponse,
    TournamentDetailResponse,
    StandingResponse,
    DecklistSummary,
    DecklistDetailResponse,
    DecklistCardResponse,
    DecklistSection,
    MetaCardsListResponse,
    CardMetaStatsResponse,
    CardMetaResponse,
    MetaPeriod,
)

router = APIRouter()
meta_router = APIRouter()
cards_meta_router = APIRouter()


@router.get("", response_model=TournamentListResponse)
async def get_tournaments(
    format: Optional[str] = None,
    days: Optional[int] = None,
    min_players: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get tournaments with optional filters.

    - **format**: Filter by format (e.g., Modern, Pioneer, Standard)
    - **days**: Filter to tournaments within last N days
    - **min_players**: Filter to tournaments with at least N players
    """
    # Build base query
    query = select(Tournament)

    # Apply filters
    if format:
        query = query.where(Tournament.format == format)

    if days is not None:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.where(Tournament.date >= cutoff_date)

    if min_players is not None:
        query = query.where(Tournament.player_count >= min_players)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination and ordering (most recent first)
    query = query.order_by(
        Tournament.date.desc()
    ).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    tournaments = result.scalars().all()

    return TournamentListResponse(
        tournaments=[
            TournamentResponse(
                id=t.id,
                topdeck_id=t.topdeck_id,
                name=t.name,
                format=t.format,
                date=t.date,
                player_count=t.player_count,
                swiss_rounds=t.swiss_rounds,
                top_cut_size=t.top_cut_size,
                city=t.city,
                venue=t.venue,
                topdeck_url=t.topdeck_url,
            )
            for t in tournaments
        ],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/{tournament_id}", response_model=TournamentDetailResponse)
async def get_tournament(
    tournament_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific tournament with standings.
    """
    # Load tournament with standings and decklists
    query = select(Tournament).where(Tournament.id == tournament_id).options(
        selectinload(Tournament.standings).selectinload(TournamentStanding.decklist)
    )

    result = await db.execute(query)
    tournament = result.scalar_one_or_none()

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    # Build standings with decklist summaries
    standings = []
    for standing in sorted(tournament.standings, key=lambda s: s.rank):
        decklist_summary = None
        if standing.decklist:
            # Count cards in decklist
            count_query = select(func.sum(DecklistCard.quantity)).where(
                DecklistCard.decklist_id == standing.decklist.id
            )
            card_count = await db.scalar(count_query) or 0

            decklist_summary = DecklistSummary(
                id=standing.decklist.id,
                archetype_name=standing.decklist.archetype_name,
                card_count=card_count,
            )

        standings.append(
            StandingResponse(
                id=standing.id,
                tournament_id=standing.tournament_id,
                player_name=standing.player_name,
                player_id=standing.player_id,
                rank=standing.rank,
                wins=standing.wins,
                losses=standing.losses,
                draws=standing.draws,
                win_rate=standing.win_rate,
                decklist=decklist_summary,
            )
        )

    return TournamentDetailResponse(
        id=tournament.id,
        topdeck_id=tournament.topdeck_id,
        name=tournament.name,
        format=tournament.format,
        date=tournament.date,
        player_count=tournament.player_count,
        swiss_rounds=tournament.swiss_rounds,
        top_cut_size=tournament.top_cut_size,
        city=tournament.city,
        venue=tournament.venue,
        topdeck_url=tournament.topdeck_url,
        standings=standings,
    )


@router.get("/{tournament_id}/decklists/{decklist_id}", response_model=DecklistDetailResponse)
async def get_decklist(
    tournament_id: int,
    decklist_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific decklist with all cards.
    """
    # Load decklist with relationships
    query = select(Decklist).where(Decklist.id == decklist_id).options(
        selectinload(Decklist.standing).selectinload(TournamentStanding.tournament),
        selectinload(Decklist.cards).selectinload(DecklistCard.card)
    )

    result = await db.execute(query)
    decklist = result.scalar_one_or_none()

    if not decklist:
        raise HTTPException(status_code=404, detail="Decklist not found")

    # Verify tournament_id matches
    if decklist.standing.tournament_id != tournament_id:
        raise HTTPException(status_code=404, detail="Decklist not found in this tournament")

    tournament = decklist.standing.tournament
    standing = decklist.standing

    # Build card list
    cards = []
    mainboard_count = 0
    sideboard_count = 0

    for dc in sorted(decklist.cards, key=lambda x: (x.section, x.card.name)):
        cards.append(
            DecklistCardResponse(
                card_id=dc.card_id,
                card_name=dc.card.name,
                quantity=dc.quantity,
                section=DecklistSection(dc.section),
                card_set=dc.card.set_code,
                card_image_url=dc.card.image_url_small,
            )
        )

        if dc.section == "mainboard":
            mainboard_count += dc.quantity
        elif dc.section == "sideboard":
            sideboard_count += dc.quantity

    return DecklistDetailResponse(
        id=decklist.id,
        archetype_name=decklist.archetype_name,
        tournament_id=tournament.id,
        tournament_name=tournament.name,
        tournament_format=tournament.format,
        player_name=standing.player_name,
        rank=standing.rank,
        wins=standing.wins,
        losses=standing.losses,
        draws=standing.draws,
        cards=cards,
        mainboard_count=mainboard_count,
        sideboard_count=sideboard_count,
    )


@meta_router.get("/cards", response_model=MetaCardsListResponse)
async def get_meta_cards(
    format: str = Query(..., description="Tournament format (e.g., Modern, Pioneer)"),
    period: MetaPeriod = Query(MetaPeriod.THIRTY_DAYS, description="Time period for statistics"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get card meta statistics for a format and period.

    Returns cards ranked by deck inclusion rate.
    """
    # Build query
    query = select(CardMetaStats, Card).join(
        Card, CardMetaStats.card_id == Card.id
    ).where(
        CardMetaStats.format == format,
        CardMetaStats.period == period.value,
    )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination and ordering (by deck inclusion rate)
    query = query.order_by(
        CardMetaStats.deck_inclusion_rate.desc()
    ).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    cards = [
        CardMetaStatsResponse(
            card_id=meta.card_id,
            card_name=card.name,
            card_set=card.set_code,
            card_image_url=card.image_url_small,
            format=meta.format,
            period=MetaPeriod(meta.period),
            deck_inclusion_rate=meta.deck_inclusion_rate,
            avg_copies=meta.avg_copies,
            top8_rate=meta.top8_rate,
            win_rate_delta=meta.win_rate_delta,
        )
        for meta, card in rows
    ]

    return MetaCardsListResponse(
        cards=cards,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@cards_meta_router.get("/{card_id}/meta", response_model=CardMetaResponse)
async def get_card_meta(
    card_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get meta statistics for a specific card across all formats and periods.
    """
    # Verify card exists
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Get all meta stats for this card
    query = select(CardMetaStats).where(CardMetaStats.card_id == card_id).order_by(
        CardMetaStats.format, CardMetaStats.period
    )

    result = await db.execute(query)
    meta_stats = result.scalars().all()

    stats = [
        CardMetaStatsResponse(
            card_id=meta.card_id,
            card_name=card.name,
            card_set=card.set_code,
            card_image_url=card.image_url_small,
            format=meta.format,
            period=MetaPeriod(meta.period),
            deck_inclusion_rate=meta.deck_inclusion_rate,
            avg_copies=meta.avg_copies,
            top8_rate=meta.top8_rate,
            win_rate_delta=meta.win_rate_delta,
        )
        for meta in meta_stats
    ]

    return CardMetaResponse(
        card_id=card.id,
        card_name=card.name,
        stats=stats,
    )
