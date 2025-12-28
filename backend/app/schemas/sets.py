"""
MTG Set Pydantic schemas for API request/response validation.
"""
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MTGSetResponse(BaseModel):
    """Response schema for MTG set details."""
    id: int
    code: str
    name: str
    released_at: Optional[date] = None
    set_type: str
    card_count: int
    icon_svg_uri: Optional[str] = None
    scryfall_id: Optional[str] = None
    parent_set_code: Optional[str] = None
    is_digital: bool
    is_foil_only: bool

    model_config = ConfigDict(from_attributes=True)


class MTGSetList(BaseModel):
    """Paginated list of MTG sets."""
    items: list[MTGSetResponse]
    total: int


class SetSearchQuery(BaseModel):
    """Query parameters for searching sets."""
    search: Optional[str] = Field(None, description="Search by set name or code")
    set_type: Optional[str] = Field(None, description="Filter by set type")
    limit: int = Field(50, ge=1, le=200, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")
