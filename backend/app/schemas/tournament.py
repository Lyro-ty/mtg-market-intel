"""
Tournament-related Pydantic schemas.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DecklistSection(str, Enum):
    """Decklist section types."""
    MAINBOARD = "mainboard"
    SIDEBOARD = "sideboard"
    COMMANDER = "commander"


class MetaPeriod(str, Enum):
    """Meta statistics period types."""
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"
    NINETY_DAYS = "90d"


class TournamentBase(BaseModel):
    """Base tournament schema."""
    topdeck_id: str
    name: str
    format: str
    date: datetime
    player_count: int
    swiss_rounds: Optional[int] = None
    top_cut_size: Optional[int] = None
    city: Optional[str] = None
    venue: Optional[str] = None
    topdeck_url: str

    class Config:
        from_attributes = True


class TournamentResponse(TournamentBase):
    """Tournament response without standings."""
    id: int

    class Config:
        from_attributes = True


class StandingBase(BaseModel):
    """Base standing schema."""
    player_name: str
    player_id: Optional[str] = None
    rank: int
    wins: int
    losses: int
    draws: int
    win_rate: float

    class Config:
        from_attributes = True


class DecklistCardResponse(BaseModel):
    """Card in a decklist."""
    card_id: int
    card_name: str
    quantity: int
    section: DecklistSection
    card_set: Optional[str] = None
    card_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class DecklistSummary(BaseModel):
    """Brief decklist info for standings."""
    id: int
    archetype_name: Optional[str] = None
    card_count: Optional[int] = None

    class Config:
        from_attributes = True


class StandingResponse(StandingBase):
    """Standing with optional decklist summary."""
    id: int
    tournament_id: int
    decklist: Optional[DecklistSummary] = None

    class Config:
        from_attributes = True


class TournamentDetailResponse(TournamentBase):
    """Detailed tournament with standings."""
    id: int
    standings: list[StandingResponse] = []
    attribution: str = "Data provided by TopDeck.gg"

    class Config:
        from_attributes = True


class TournamentListResponse(BaseModel):
    """Paginated tournament list."""
    tournaments: list[TournamentResponse]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False
    attribution: str = "Data provided by TopDeck.gg"


class DecklistDetailResponse(BaseModel):
    """Detailed decklist with all cards."""
    id: int
    archetype_name: Optional[str] = None
    tournament_id: int
    tournament_name: str
    tournament_format: str
    player_name: str
    rank: int
    wins: int
    losses: int
    draws: int
    cards: list[DecklistCardResponse] = []
    mainboard_count: int = 0
    sideboard_count: int = 0
    attribution: str = "Data provided by TopDeck.gg"

    class Config:
        from_attributes = True


class CardMetaStatsResponse(BaseModel):
    """Card meta statistics response."""
    card_id: int
    card_name: str
    card_set: Optional[str] = None
    card_image_url: Optional[str] = None
    format: str
    period: MetaPeriod
    deck_inclusion_rate: float = Field(..., ge=0, le=1)
    avg_copies: float = Field(..., ge=0)
    top8_rate: float = Field(..., ge=0, le=1)
    win_rate_delta: float = Field(..., ge=-1, le=1)

    class Config:
        from_attributes = True


class MetaCardsListResponse(BaseModel):
    """Paginated meta cards list."""
    cards: list[CardMetaStatsResponse]
    total: int
    page: int = 1
    page_size: int = 50
    has_more: bool = False
    attribution: str = "Data provided by TopDeck.gg"


class CardMetaResponse(BaseModel):
    """Meta statistics for a specific card."""
    card_id: int
    card_name: str
    stats: list[CardMetaStatsResponse] = []
    attribution: str = "Data provided by TopDeck.gg"

    class Config:
        from_attributes = True
