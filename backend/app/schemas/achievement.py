"""
Achievement-related Pydantic schemas for API request/response validation.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============ Achievement Definition Schemas ============


class AchievementDefinitionBase(BaseModel):
    """Base schema for achievement definitions."""
    key: str
    name: str
    description: Optional[str] = None
    category: str
    icon: Optional[str] = None
    threshold: Optional[dict[str, Any]] = None
    discovery_points: int = 0
    frame_tier_unlock: Optional[str] = None
    is_hidden: bool = False


class AchievementDefinitionResponse(AchievementDefinitionBase):
    """Response schema for achievement definitions."""
    id: int
    rarity_percent: Optional[float] = None
    is_seasonal: bool = False

    class Config:
        from_attributes = True


# ============ User Achievement Schemas ============


class UserAchievementResponse(BaseModel):
    """Response schema for a user's unlocked achievement."""
    id: int
    achievement_id: int
    unlocked_at: datetime
    progress: Optional[dict[str, Any]] = None
    achievement: AchievementDefinitionResponse

    class Config:
        from_attributes = True


class AchievementProgressResponse(BaseModel):
    """Achievement definition with user's progress toward unlocking."""
    achievement: AchievementDefinitionResponse
    unlocked: bool
    unlocked_at: Optional[datetime] = None
    progress: Optional[dict[str, Any]] = None  # {"current": 7, "target": 10}


class AchievementsListResponse(BaseModel):
    """Full list of achievements with user progress and stats."""
    achievements: list[AchievementProgressResponse]
    total_unlocked: int
    total_discovery_points: int


# ============ Frame Tier Schemas ============


class FrameTier(BaseModel):
    """Response schema for a profile frame tier."""
    tier: str  # bronze, silver, gold, platinum, legendary
    unlocked: bool
    unlocked_at: Optional[datetime] = None
    is_active: bool = False


class FramesResponse(BaseModel):
    """Response schema for user's available profile frames."""
    frames: list[FrameTier]
    active_frame: str


class SetActiveFrameRequest(BaseModel):
    """Request schema for setting active profile frame."""
    frame_tier: str = Field(
        ...,
        description="Frame tier to set as active: bronze, silver, gold, platinum, legendary"
    )
