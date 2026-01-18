"""
Achievements API routes for managing user achievements and profile frames.

Endpoints:
- GET /achievements - Get all achievement definitions with current user's progress
- GET /achievements/users/{user_id} - Get achievements for a specific user (public unlocked only)
- GET /achievements/frames - Get available frames for current user
- POST /achievements/frames/active - Set active frame tier
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_user_optional, get_db
from app.models import User
from app.models.achievement import AchievementDefinition, UserAchievement, UserFrame
from app.schemas.achievement import (
    AchievementDefinitionResponse,
    AchievementProgressResponse,
    AchievementsListResponse,
    FramesResponse,
    FrameTier,
    SetActiveFrameRequest,
)

router = APIRouter(prefix="/achievements", tags=["Achievements"])

# Define all available frame tiers in order
FRAME_TIERS = ["bronze", "silver", "gold", "platinum", "legendary"]


@router.get("", response_model=AchievementsListResponse)
async def get_achievements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all achievement definitions with current user's progress.

    Returns all achievements (excluding hidden ones unless unlocked) with
    the user's progress toward each one.
    """
    # Get all achievement definitions
    definitions_result = await db.execute(
        select(AchievementDefinition).order_by(
            AchievementDefinition.category,
            AchievementDefinition.discovery_points.desc(),
        )
    )
    all_definitions = definitions_result.scalars().all()

    # Get user's achievements (progress and unlocks)
    user_achievements_result = await db.execute(
        select(UserAchievement)
        .where(UserAchievement.user_id == current_user.id)
        .options(selectinload(UserAchievement.achievement))
    )
    user_achievements = {
        ua.achievement_id: ua for ua in user_achievements_result.scalars().all()
    }

    # Build response
    achievements = []
    total_unlocked = 0
    total_discovery_points = 0

    for definition in all_definitions:
        user_achievement = user_achievements.get(definition.id)
        is_unlocked = user_achievement is not None and user_achievement.unlocked_at is not None

        # Skip hidden achievements that are not unlocked
        if definition.is_hidden and not is_unlocked:
            continue

        # Count unlocked achievements
        if is_unlocked:
            total_unlocked += 1
            total_discovery_points += definition.discovery_points

        achievements.append(
            AchievementProgressResponse(
                achievement=AchievementDefinitionResponse(
                    id=definition.id,
                    key=definition.key,
                    name=definition.name,
                    description=definition.description,
                    category=definition.category,
                    icon=definition.icon,
                    threshold=definition.threshold,
                    discovery_points=definition.discovery_points,
                    frame_tier_unlock=definition.frame_tier_unlock,
                    is_hidden=definition.is_hidden,
                    rarity_percent=float(definition.rarity_percent) if definition.rarity_percent else None,
                    is_seasonal=definition.is_seasonal,
                ),
                unlocked=is_unlocked,
                unlocked_at=user_achievement.unlocked_at if user_achievement else None,
                progress=user_achievement.progress if user_achievement else None,
            )
        )

    return AchievementsListResponse(
        achievements=achievements,
        total_unlocked=total_unlocked,
        total_discovery_points=total_discovery_points,
    )


@router.get("/users/{user_id}", response_model=AchievementsListResponse)
async def get_user_achievements(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    Get achievements for a specific user.

    For public viewing, only shows unlocked achievements.
    Hidden achievements are only shown if the viewer is the user themselves.
    """
    # Verify user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if viewing own profile
    is_own_profile = current_user is not None and current_user.id == user_id

    # Get user's unlocked achievements
    user_achievements_result = await db.execute(
        select(UserAchievement)
        .where(UserAchievement.user_id == user_id)
        .where(UserAchievement.unlocked_at.isnot(None))
        .options(selectinload(UserAchievement.achievement))
    )
    user_achievements = list(user_achievements_result.scalars().all())

    # Build response
    achievements = []
    total_unlocked = 0
    total_discovery_points = 0

    for user_achievement in user_achievements:
        definition = user_achievement.achievement

        # Skip hidden achievements unless viewing own profile
        if definition.is_hidden and not is_own_profile:
            continue

        total_unlocked += 1
        total_discovery_points += definition.discovery_points

        achievements.append(
            AchievementProgressResponse(
                achievement=AchievementDefinitionResponse(
                    id=definition.id,
                    key=definition.key,
                    name=definition.name,
                    description=definition.description,
                    category=definition.category,
                    icon=definition.icon,
                    threshold=definition.threshold,
                    discovery_points=definition.discovery_points,
                    frame_tier_unlock=definition.frame_tier_unlock,
                    is_hidden=definition.is_hidden,
                    rarity_percent=float(definition.rarity_percent) if definition.rarity_percent else None,
                    is_seasonal=definition.is_seasonal,
                ),
                unlocked=True,
                unlocked_at=user_achievement.unlocked_at,
                progress=user_achievement.progress,
            )
        )

    return AchievementsListResponse(
        achievements=achievements,
        total_unlocked=total_unlocked,
        total_discovery_points=total_discovery_points,
    )


@router.get("/frames", response_model=FramesResponse)
async def get_frames(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get available profile frames for the current user.

    Returns all frame tiers with their unlock status.
    """
    # Get user's unlocked frames
    frames_result = await db.execute(
        select(UserFrame).where(UserFrame.user_id == current_user.id)
    )
    user_frames = {uf.frame_tier: uf for uf in frames_result.scalars().all()}

    # Build response with all frame tiers
    frames = []
    for tier in FRAME_TIERS:
        user_frame = user_frames.get(tier)
        is_unlocked = user_frame is not None
        is_active = current_user.active_frame_tier == tier

        frames.append(
            FrameTier(
                tier=tier,
                unlocked=is_unlocked,
                unlocked_at=user_frame.unlocked_at if user_frame else None,
                is_active=is_active,
            )
        )

    return FramesResponse(
        frames=frames,
        active_frame=current_user.active_frame_tier,
    )


@router.post("/frames/active", response_model=FramesResponse)
async def set_active_frame(
    request: SetActiveFrameRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Set the active profile frame tier.

    The frame must be unlocked to be set as active.
    """
    frame_tier = request.frame_tier.lower()

    # Validate frame tier exists
    if frame_tier not in FRAME_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid frame tier. Must be one of: {', '.join(FRAME_TIERS)}",
        )

    # Check if the user has unlocked this frame
    frame_result = await db.execute(
        select(UserFrame).where(
            UserFrame.user_id == current_user.id,
            UserFrame.frame_tier == frame_tier,
        )
    )
    user_frame = frame_result.scalar_one_or_none()

    if not user_frame:
        raise HTTPException(
            status_code=403,
            detail=f"Frame tier '{frame_tier}' has not been unlocked",
        )

    # Update the active frame tier on the user
    current_user.active_frame_tier = frame_tier
    await db.commit()
    await db.refresh(current_user)

    # Return updated frames list
    return await get_frames(current_user=current_user, db=db)
