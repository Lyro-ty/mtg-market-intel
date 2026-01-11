"""
Search API endpoints.

Provides semantic search, autocomplete, and similar cards functionality.
"""
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MAX_SEARCH_LENGTH
from app.db.session import get_db
from app.models import Card
from app.schemas.search import (
    SearchResponse,
    SearchResult,
    AutocompleteResponse,
    AutocompleteSuggestion,
    SimilarCardsResponse,
)
from app.services.search import (
    SemanticSearchService,
    AutocompleteService,
    apply_card_filters,
)

router = APIRouter()
logger = structlog.get_logger(__name__)

# Service instances (lazy initialization)
_semantic_service: Optional[SemanticSearchService] = None
_autocomplete_service: Optional[AutocompleteService] = None


def get_semantic_service() -> SemanticSearchService:
    """Get or create semantic search service."""
    global _semantic_service
    if _semantic_service is None:
        _semantic_service = SemanticSearchService()
    return _semantic_service


def get_autocomplete_service() -> AutocompleteService:
    """Get or create autocomplete service."""
    global _autocomplete_service
    if _autocomplete_service is None:
        _autocomplete_service = AutocompleteService()
    return _autocomplete_service


@router.get("", response_model=SearchResponse)
async def search_cards(
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    colors: Optional[str] = Query(None, description="Comma-separated colors (W,U,B,R,G)"),
    card_type: Optional[str] = Query(None, description="Card type filter"),
    cmc_min: Optional[float] = Query(None, description="Minimum CMC"),
    cmc_max: Optional[float] = Query(None, description="Maximum CMC"),
    format_legal: Optional[str] = Query(None, description="Format legality"),
    rarity: Optional[str] = Query(None, description="Rarity filter"),
    mode: str = Query("semantic", description="Search mode: 'semantic' or 'text'"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for cards using semantic similarity or text matching.

    Semantic mode uses AI embeddings to find cards by meaning.
    Text mode uses traditional ILIKE matching on card name.
    """
    offset = (page - 1) * page_size

    # Parse color filter
    color_list = colors.split(",") if colors else None

    filters = {
        "colors": color_list,
        "card_type": card_type,
        "cmc_min": cmc_min,
        "cmc_max": cmc_max,
        "format_legal": format_legal,
        "rarity": rarity,
    }

    # Wildcard '*' means "browse all" - always use text mode for proper pagination
    if q == "*":
        mode = "text"
        q = ""  # Empty string for ILIKE will match all

    if mode == "semantic":
        service = get_semantic_service()
        # Get more results than needed for filtering
        raw_results = await service.search(
            db=db,
            query=q,
            limit=page_size * 3,  # Get extra for filtering
            offset=0,
        )

        # Apply filters
        filtered = apply_card_filters(raw_results, **{k: v for k, v in filters.items() if v})

        # Apply pagination to filtered results
        paginated = filtered[offset:offset + page_size]
        total = len(filtered)

        results = [
            SearchResult(
                id=r["card_id"],
                name=r["name"],
                set_code=r["set_code"],
                oracle_text=r.get("oracle_text"),
                type_line=r.get("type_line"),
                image_url=r.get("image_url"),
                similarity_score=r.get("similarity_score"),
            )
            for r in paginated
        ]
    else:
        # Text search fallback
        from sqlalchemy import select, func
        from app.services.search.filters import build_filter_query

        # Validate search length
        if len(q) > MAX_SEARCH_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Search query too long. Maximum {MAX_SEARCH_LENGTH} characters.",
            )

        # Escape SQL wildcard characters in user input to prevent wildcard abuse
        q_escaped = q.replace("%", r"\%").replace("_", r"\_")

        query = select(Card).where(Card.name.ilike(f"%{q_escaped}%", escape="\\"))
        query = build_filter_query(query, filters)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query) or 0

        # Apply pagination
        query = query.order_by(Card.name).offset(offset).limit(page_size)
        result = await db.execute(query)
        cards = result.scalars().all()

        results = [
            SearchResult(
                id=c.id,
                name=c.name,
                set_code=c.set_code,
                oracle_text=c.oracle_text,
                type_line=c.type_line,
                image_url=c.image_url,
            )
            for c in cards
        ]

    return SearchResponse(
        results=results,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
        query=q,
        search_type=mode,
    )


@router.get("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(
    q: str = Query(..., min_length=1, description="Partial card name"),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """
    Get autocomplete suggestions for card names.

    Returns up to `limit` cards whose names start with the query.
    """
    service = get_autocomplete_service()
    suggestions = await service.get_suggestions(db, q, limit)

    return AutocompleteResponse(
        suggestions=[
            AutocompleteSuggestion(
                id=s["id"],
                name=s["name"],
                set_code=s["set_code"],
                image_url=s.get("image_url"),
            )
            for s in suggestions
        ],
        query=q,
    )


@router.get("/similar/{card_id}", response_model=SimilarCardsResponse)
async def get_similar_cards(
    card_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Get cards similar to a specific card.

    Uses semantic similarity based on card text and attributes.
    """
    # Get the target card
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Search using the card's text as query
    search_text = f"{card.name} {card.type_line or ''} {card.oracle_text or ''}"

    service = get_semantic_service()
    results = await service.search(
        db=db,
        query=search_text,
        limit=limit + 1,  # Get one extra to filter out the source card
    )

    # Filter out the source card
    similar = [r for r in results if r["card_id"] != card_id][:limit]

    return SimilarCardsResponse(
        card_id=card_id,
        card_name=card.name,
        similar_cards=[
            SearchResult(
                id=r["card_id"],
                name=r["name"],
                set_code=r["set_code"],
                oracle_text=r.get("oracle_text"),
                type_line=r.get("type_line"),
                image_url=r.get("image_url"),
                similarity_score=r.get("similarity_score"),
            )
            for r in similar
        ],
    )
