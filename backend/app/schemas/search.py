"""Search API schemas."""
from typing import Optional
from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    """Filters for search queries."""
    colors: Optional[list[str]] = Field(None, description="Filter by colors (W, U, B, R, G)")
    card_type: Optional[str] = Field(None, description="Filter by card type")
    cmc_min: Optional[float] = Field(None, description="Minimum CMC")
    cmc_max: Optional[float] = Field(None, description="Maximum CMC")
    format_legal: Optional[str] = Field(None, description="Format legality (modern, standard, etc.)")
    rarity: Optional[str] = Field(None, description="Card rarity")
    keywords: Optional[list[str]] = Field(None, description="Card keywords (Flying, Haste, etc.)")


class SearchResult(BaseModel):
    """Single search result."""
    id: int
    name: str
    set_code: str
    oracle_text: Optional[str] = None
    type_line: Optional[str] = None
    image_url: Optional[str] = None
    similarity_score: Optional[float] = None


class SearchResponse(BaseModel):
    """Search response with results and metadata."""
    results: list[SearchResult]
    total: int
    page: int
    page_size: int
    has_more: bool
    query: str
    search_type: str = "semantic"  # "semantic" or "text"


class AutocompleteSuggestion(BaseModel):
    """Single autocomplete suggestion."""
    id: int
    name: str
    set_code: str
    image_url: Optional[str] = None


class AutocompleteResponse(BaseModel):
    """Autocomplete response."""
    suggestions: list[AutocompleteSuggestion]
    query: str


class SimilarCardsResponse(BaseModel):
    """Similar cards response."""
    card_id: int
    card_name: str
    similar_cards: list[SearchResult]
