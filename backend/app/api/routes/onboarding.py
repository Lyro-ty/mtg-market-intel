"""
Onboarding API routes.

Provides endpoints for tracking and managing new user onboarding progress.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.inventory import InventoryItem
from app.models.social import UserFormatSpecialty
from app.models.user import User
from app.schemas.onboarding import (
    OnboardingCompleteResponse,
    OnboardingStatusResponse,
    OnboardingStep,
)

router = APIRouter(prefix="/profile/me/onboarding", tags=["Onboarding"])

# Onboarding step definitions
ONBOARDING_STEPS = [
    {"id": "profile_basics", "name": "Set up profile basics", "required": False},
    {"id": "card_type", "name": "Choose your card type", "required": True},
    {"id": "location", "name": "Set your location", "required": False},
    {"id": "shipping", "name": "Set shipping preference", "required": True},
    {"id": "first_card", "name": "Add your first card", "required": True},
    {"id": "format_specialties", "name": "Select your formats", "required": False},
]


async def _check_step_completion(db: AsyncSession, user: User, step_id: str) -> bool:
    """Check if a specific onboarding step is complete."""
    if step_id == "profile_basics":
        return bool(user.display_name or user.bio)
    elif step_id == "card_type":
        return bool(user.card_type)
    elif step_id == "location":
        return bool(user.city and user.country)
    elif step_id == "shipping":
        return bool(user.shipping_preference)
    elif step_id == "first_card":
        count = await db.scalar(
            select(func.count()).select_from(InventoryItem)
            .where(InventoryItem.user_id == user.id)
        )
        return count is not None and count > 0
    elif step_id == "format_specialties":
        count = await db.scalar(
            select(func.count()).select_from(UserFormatSpecialty)
            .where(UserFormatSpecialty.user_id == user.id)
        )
        return count is not None and count > 0
    return False


@router.get("", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OnboardingStatusResponse:
    """Get the current user's onboarding status."""
    steps = []
    required_complete = 0
    required_total = 0

    for step_def in ONBOARDING_STEPS:
        completed = await _check_step_completion(db, current_user, step_def["id"])
        steps.append(OnboardingStep(
            id=step_def["id"],
            name=step_def["name"],
            completed=completed,
            required=step_def["required"],
        ))
        if step_def["required"]:
            required_total += 1
            if completed:
                required_complete += 1

    total_complete = sum(1 for s in steps if s.completed)
    progress_percent = int((total_complete / len(steps)) * 100)

    return OnboardingStatusResponse(
        completed=current_user.onboarding_completed_at is not None,
        completed_at=current_user.onboarding_completed_at,
        steps=steps,
        progress_percent=progress_percent,
        required_complete=required_complete,
        required_total=required_total,
    )


@router.post("/complete", response_model=OnboardingCompleteResponse)
async def complete_onboarding(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OnboardingCompleteResponse:
    """Mark onboarding as complete. Requires all required steps to be done."""
    # Check all required steps
    for step_def in ONBOARDING_STEPS:
        if step_def["required"]:
            completed = await _check_step_completion(db, current_user, step_def["id"])
            if not completed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Required step '{step_def['name']}' is not complete"
                )

    current_user.onboarding_completed_at = datetime.now(timezone.utc)
    await db.commit()

    return OnboardingCompleteResponse(
        success=True,
        completed_at=current_user.onboarding_completed_at,
        message="Onboarding completed successfully!"
    )


@router.post("/skip", response_model=OnboardingCompleteResponse)
async def skip_onboarding(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OnboardingCompleteResponse:
    """Skip onboarding. Profile may be incomplete."""
    current_user.onboarding_completed_at = datetime.now(timezone.utc)
    await db.commit()

    return OnboardingCompleteResponse(
        success=True,
        completed_at=current_user.onboarding_completed_at,
        message="Onboarding skipped. You can complete your profile later in settings."
    )
