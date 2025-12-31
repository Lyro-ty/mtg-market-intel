"""
Profile API endpoints.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User
from app.schemas.profile import ProfileResponse, ProfileUpdate, PublicProfileResponse

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's profile.

    Returns all profile fields for the authenticated user.
    """
    return current_user


@router.patch("/me", response_model=ProfileResponse)
async def update_my_profile(
    profile_update: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update current user's profile.

    Only provided fields will be updated.
    """
    # Update only the fields that were provided
    update_data = profile_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    # Update last_active_at
    current_user.last_active_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.get("/{username}", response_model=PublicProfileResponse)
async def get_user_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a user's public profile by username.

    Returns limited profile information visible to other users.
    """
    from sqlalchemy import select

    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    return user
