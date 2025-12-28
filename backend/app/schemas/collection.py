"""
Collection-related Pydantic schemas.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CollectionStatsResponse(BaseModel):
    """Cached collection statistics response."""
    total_cards: int
    total_value: Decimal
    unique_cards: int
    sets_started: int
    sets_completed: int
    top_set_code: Optional[str] = None
    top_set_completion: Optional[Decimal] = None
    is_stale: bool
    last_calculated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SetCompletion(BaseModel):
    """Per-set completion data."""
    set_code: str
    set_name: str
    total_cards: int
    owned_cards: int
    completion_percentage: Decimal
    icon_svg_uri: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SetCompletionList(BaseModel):
    """List of set completions."""
    items: list[SetCompletion]
    total_sets: int


class MilestoneResponse(BaseModel):
    """Achieved milestone response."""
    id: int
    type: str
    name: str
    description: Optional[str] = None
    threshold: int
    achieved_at: datetime
    metadata: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class MilestoneList(BaseModel):
    """List of milestones."""
    items: list[MilestoneResponse]
    total: int
