"""
Profile API endpoints.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User
from app.models.card import Card
from app.models.inventory import InventoryItem
from app.schemas.profile import (
    ProfileResponse,
    ProfileUpdate,
    PublicProfileResponse,
    SignatureCardResponse,
)
from app.core.hashids import encode_id, decode_id
from app.services.profile_card_generator import ProfileCardGenerator

router = APIRouter(prefix="/profile", tags=["profile"])

# Cooldown period for card_type changes (30 days)
CARD_TYPE_CHANGE_COOLDOWN_DAYS = 30


def _build_signature_card_response(card: Card | None) -> SignatureCardResponse | None:
    """Build SignatureCardResponse from Card model."""
    if card is None:
        return None
    return SignatureCardResponse(
        id=card.id,
        name=card.name,
        image_url=card.image_url,
    )


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's profile.

    Returns all profile fields for the authenticated user, including
    social trading fields and privacy settings.
    """
    # Build signature card response if set
    signature_card = _build_signature_card_response(current_user.signature_card)

    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        display_name=current_user.display_name,
        bio=current_user.bio,
        location=current_user.location,
        avatar_url=current_user.avatar_url,
        discord_id=current_user.discord_id,
        created_at=current_user.created_at,
        last_active_at=current_user.last_active_at,
        tagline=current_user.tagline,
        card_type=current_user.card_type,
        signature_card_id=current_user.signature_card_id,
        signature_card=signature_card,
        city=current_user.city,
        country=current_user.country,
        shipping_preference=current_user.shipping_preference,
        active_frame_tier=current_user.active_frame_tier,
        discovery_score=current_user.discovery_score,
        show_in_directory=current_user.show_in_directory,
        show_in_search=current_user.show_in_search,
        show_online_status=current_user.show_online_status,
        show_portfolio_tier=current_user.show_portfolio_tier,
        onboarding_completed_at=current_user.onboarding_completed_at,
    )


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

    Validation rules:
    - card_type can only be changed once every 30 days
    - signature_card_id must reference a valid card
    """
    update_data = profile_update.model_dump(exclude_unset=True)

    # Validate card_type change cooldown
    if "card_type" in update_data and update_data["card_type"] is not None:
        new_card_type = update_data["card_type"]
        # Only enforce cooldown if changing to a different type
        if current_user.card_type != new_card_type:
            if current_user.card_type_changed_at is not None:
                cooldown_end = current_user.card_type_changed_at + timedelta(
                    days=CARD_TYPE_CHANGE_COOLDOWN_DAYS
                )
                if datetime.now(timezone.utc) < cooldown_end:
                    days_remaining = (cooldown_end - datetime.now(timezone.utc)).days
                    raise HTTPException(
                        status_code=400,
                        detail=f"Card type can only be changed every {CARD_TYPE_CHANGE_COOLDOWN_DAYS} days. "
                        f"You can change it again in {days_remaining} days.",
                    )
            # Update the timestamp when card_type changes
            update_data["card_type_changed_at"] = datetime.now(timezone.utc)

    # Validate signature_card_id references a valid card
    if "signature_card_id" in update_data and update_data["signature_card_id"] is not None:
        card_id = update_data["signature_card_id"]
        result = await db.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one_or_none()
        if not card:
            raise HTTPException(
                status_code=400,
                detail=f"Card with id {card_id} not found",
            )

    # Update the fields
    for field, value in update_data.items():
        setattr(current_user, field, value)

    # Update last_active_at
    current_user.last_active_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(current_user)

    # Build signature card response
    signature_card = _build_signature_card_response(current_user.signature_card)

    return ProfileResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        display_name=current_user.display_name,
        bio=current_user.bio,
        location=current_user.location,
        avatar_url=current_user.avatar_url,
        discord_id=current_user.discord_id,
        created_at=current_user.created_at,
        last_active_at=current_user.last_active_at,
        tagline=current_user.tagline,
        card_type=current_user.card_type,
        signature_card_id=current_user.signature_card_id,
        signature_card=signature_card,
        city=current_user.city,
        country=current_user.country,
        shipping_preference=current_user.shipping_preference,
        active_frame_tier=current_user.active_frame_tier,
        discovery_score=current_user.discovery_score,
        show_in_directory=current_user.show_in_directory,
        show_in_search=current_user.show_in_search,
        show_online_status=current_user.show_online_status,
        show_portfolio_tier=current_user.show_portfolio_tier,
        onboarding_completed_at=current_user.onboarding_completed_at,
    )


@router.get("/me/card.png")
async def get_my_profile_card(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a PNG image of the user's profile card for sharing.

    Returns the image directly with Content-Type: image/png.
    The card displays user information in a trading card format.
    """
    # Get cards for trade count
    trade_count = await _get_trade_count(db, current_user.id)

    # Get signature card name if set
    signature_card_name = None
    if current_user.signature_card:
        signature_card_name = current_user.signature_card.name

    # Format member since date
    member_since = current_user.created_at.strftime("%b %Y") if current_user.created_at else None

    generator = ProfileCardGenerator()
    png_bytes = await generator.generate(
        display_name=current_user.display_name,
        username=current_user.username,
        frame_tier=current_user.active_frame_tier or "bronze",
        tagline=current_user.tagline,
        card_type=current_user.card_type,
        cards_for_trade=trade_count,
        signature_card_name=signature_card_name,
        member_since=member_since,
    )

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="{current_user.username}-card.png"'
        },
    )


async def _get_trade_count(db: AsyncSession, user_id: int) -> int:
    """Count cards available for trade for a user."""
    result = await db.scalar(
        select(func.count())
        .select_from(InventoryItem)
        .where(InventoryItem.user_id == user_id)
        .where(InventoryItem.available_for_trade == True)
    )
    return result or 0


def _build_public_profile_response(
    user: User,
    hashid: str,
    trade_count: int,
) -> PublicProfileResponse:
    """Build PublicProfileResponse respecting privacy settings."""
    # Build signature card response if set
    signature_card = _build_signature_card_response(user.signature_card)

    # Only include city/country if user allows showing in directory
    city = user.city if user.show_in_directory else None
    country = user.country if user.show_in_directory else None

    return PublicProfileResponse(
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        location=user.location,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        hashid=hashid,
        cards_for_trade=trade_count,
        tagline=user.tagline,
        card_type=user.card_type,
        signature_card=signature_card,
        active_frame_tier=user.active_frame_tier,
        shipping_preference=user.shipping_preference,
        city=city,
        country=country,
    )


@router.get("/public/{hashid}/card.png")
async def get_public_profile_card(
    hashid: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a PNG image of a user's public profile card.

    Returns the image directly with Content-Type: image/png.
    Anyone can access this endpoint with a valid hashid.
    """
    user_id = decode_id(hashid)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    # Get cards for trade count
    trade_count = await _get_trade_count(db, user.id)

    # Get signature card name if set
    signature_card_name = None
    if user.signature_card:
        signature_card_name = user.signature_card.name

    # Format member since date
    member_since = user.created_at.strftime("%b %Y") if user.created_at else None

    generator = ProfileCardGenerator()
    png_bytes = await generator.generate(
        display_name=user.display_name,
        username=user.username,
        frame_tier=user.active_frame_tier or "bronze",
        tagline=user.tagline,
        card_type=user.card_type,
        cards_for_trade=trade_count,
        signature_card_name=signature_card_name,
        member_since=member_since,
    )

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="{user.username}-card.png"'
        },
    )


@router.get("/public/{hashid}", response_model=PublicProfileResponse)
async def get_public_profile(
    hashid: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a user's public profile by hashid.

    Hashids provide privacy - users share their hashid URL rather than username.
    Returns limited profile information visible to other users.
    Privacy settings are respected for location fields.
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

    return _build_public_profile_response(user, hashid, trade_count)


@router.get("/{username}", response_model=PublicProfileResponse)
async def get_user_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a user's public profile by username.

    Returns limited profile information visible to other users.
    Privacy settings are respected for location fields.
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
    hashid = encode_id(user.id)

    return _build_public_profile_response(user, hashid, trade_count)
