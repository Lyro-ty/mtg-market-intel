"""
Favorites and notes schemas for API request/response validation.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============ Favorite User Schemas ============

class FavoriteUserResponse(BaseModel):
    """Response schema for a favorited user."""
    id: int
    favorited_user_id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    frame_tier: str = "bronze"
    notify_on_listings: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class FavoritesListResponse(BaseModel):
    """List of favorited users."""
    favorites: list[FavoriteUserResponse]
    total: int


class AddFavoriteRequest(BaseModel):
    """Schema for adding a user to favorites."""
    notify_on_listings: bool = Field(
        default=False,
        description="Whether to receive notifications when this user posts new listings"
    )


# ============ User Note Schemas ============

class UserNoteResponse(BaseModel):
    """Response schema for a user note."""
    id: int
    target_user_id: int
    username: str
    display_name: Optional[str] = None
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotesListResponse(BaseModel):
    """List of user notes."""
    notes: list[UserNoteResponse]
    total: int


class CreateNoteRequest(BaseModel):
    """Schema for creating a note on a user."""
    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Note content"
    )


class UpdateNoteRequest(BaseModel):
    """Schema for updating a note on a user."""
    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Updated note content"
    )
