"""
EDHREC API endpoints.

Provides Commander format popularity data from EDHREC.
"""
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.edhrec import edhrec_client

router = APIRouter(prefix="/edhrec", tags=["edhrec"])
logger = structlog.get_logger(__name__)


class Commander(BaseModel):
    """Commander data from EDHREC."""
    name: str
    color_identity: list[str]
    num_decks: int
    rank: Optional[int] = None
    url: Optional[str] = None


class CommandersResponse(BaseModel):
    """Response for top commanders."""
    commanders: list[Commander]
    total: int


class CardUsage(BaseModel):
    """Card usage data from EDHREC."""
    name: str
    num_decks: int
    rank: Optional[int] = None
    potential_decks: int
    inclusion_rate: float
    synergies: list[dict]


class SynergyCard(BaseModel):
    """Card with synergy score."""
    name: str
    synergy: float = 0


class TopCard(BaseModel):
    """Card with inclusion rate."""
    name: str
    inclusion: float = 0


class CommanderRecommendations(BaseModel):
    """Recommended cards for a commander."""
    commander: str
    high_synergy: list[SynergyCard]
    top_cards: list[TopCard]
    new_cards: list[dict]


class StapleCard(BaseModel):
    """Commander staple card."""
    name: str
    num_decks: int = 0
    inclusion: float = 0


@router.get("/commanders/top", response_model=CommandersResponse)
async def get_top_commanders(
    limit: int = Query(default=50, le=100, ge=1),
):
    """
    Get the most popular commanders on EDHREC.

    Returns commanders sorted by deck count (most popular first).
    """
    commanders = await edhrec_client.get_top_commanders(limit)

    if not commanders:
        logger.warning("Failed to fetch top commanders from EDHREC")
        return CommandersResponse(commanders=[], total=0)

    return CommandersResponse(
        commanders=[Commander(**c) for c in commanders],
        total=len(commanders),
    )


@router.get("/cards/{card_name}", response_model=CardUsage)
async def get_card_edhrec_data(
    card_name: str,
):
    """
    Get EDHREC usage data for a specific card.

    Returns deck count, inclusion rate, and synergistic cards.
    """
    data = await edhrec_client.get_card_data(card_name)

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Card '{card_name}' not found on EDHREC"
        )

    return CardUsage(**data)


@router.get("/commanders/{commander_name}/recommendations", response_model=CommanderRecommendations)
async def get_commander_recommendations(
    commander_name: str,
):
    """
    Get recommended cards for a specific commander.

    Returns high synergy cards, most-played cards, and new additions.
    """
    data = await edhrec_client.get_commander_cards(commander_name)

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Commander '{commander_name}' not found on EDHREC"
        )

    return CommanderRecommendations(
        commander=data["commander"],
        high_synergy=[SynergyCard(**c) for c in data.get("high_synergy", [])],
        top_cards=[TopCard(**c) for c in data.get("top_cards", [])],
        new_cards=data.get("new_cards", []),
    )


@router.get("/staples", response_model=list[StapleCard])
async def get_commander_staples(
    colors: Optional[str] = Query(
        default=None,
        description="Color identity filter (e.g., 'WU' for Azorius, 'BRG' for Jund)"
    ),
    limit: int = Query(default=50, le=100, ge=1),
):
    """
    Get Commander staple cards.

    Optionally filter by color identity. Colors use single letters:
    W=White, U=Blue, B=Black, R=Red, G=Green
    """
    staples = await edhrec_client.get_staples(colors or "")

    if not staples:
        return []

    return [StapleCard(**s) for s in staples[:limit]]
