"""
Profile API endpoints.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User
from app.models.inventory import InventoryItem
from app.schemas.profile import ProfileResponse, ProfileUpdate, PublicProfileResponse
from app.core.hashids import encode_id, decode_id

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


@router.get("/me/share-link")
async def get_my_share_link(
    current_user: User = Depends(get_current_user),
):
    """
    Get the shareable link for the current user's public profile.

    Returns the hashid that can be used to share the profile publicly
    without exposing the username.
    """
    return {
        "hashid": encode_id(current_user.id),
        "url": f"/u/{encode_id(current_user.id)}",
    }


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


async def _get_trade_count(db: AsyncSession, user_id: int) -> int:
    """Count cards available for trade for a user."""
    result = await db.scalar(
        select(func.count())
        .select_from(InventoryItem)
        .where(InventoryItem.user_id == user_id)
        .where(InventoryItem.available_for_trade == True)
    )
    return result or 0


@router.get("/public/{hashid}", response_model=PublicProfileResponse)
async def get_public_profile(
    hashid: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a user's public profile by hashid.

    Hashids provide privacy - users share their hashid URL rather than username.
    Returns limited profile information visible to other users.
    """
    user_id = decode_id(hashid)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    trade_count = await _get_trade_count(db, user.id)

    return PublicProfileResponse(
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        location=user.location,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        hashid=hashid,
        cards_for_trade=trade_count,
    )


@router.get("/{username}", response_model=PublicProfileResponse)
async def get_user_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a user's public profile by username.

    Returns limited profile information visible to other users.
    """
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    trade_count = await _get_trade_count(db, user.id)

    return PublicProfileResponse(
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        location=user.location,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        hashid=encode_id(user.id),
        cards_for_trade=trade_count,
    )
