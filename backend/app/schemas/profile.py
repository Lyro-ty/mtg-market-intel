"""
Profile-related Pydantic schemas.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    """Schema for updating user profile."""
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)


class ProfileResponse(BaseModel):
    """Profile response schema."""
    id: int
    email: str
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    avatar_url: Optional[str] = None
    discord_id: Optional[str] = None
    created_at: datetime
    last_active_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PublicProfileResponse(BaseModel):
    """Public profile response - limited fields for other users."""
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    hashid: Optional[str] = None
    cards_for_trade: int = 0

    class Config:
        from_attributes = True
