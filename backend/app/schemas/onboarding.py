"""
Onboarding-related Pydantic schemas.

Provides schemas for tracking new user onboarding progress.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OnboardingStep(BaseModel):
    """Represents a single onboarding step and its completion status."""
    id: str
    name: str
    completed: bool
    required: bool


class OnboardingStatusResponse(BaseModel):
    """Response schema for onboarding status endpoint."""
    completed: bool
    completed_at: Optional[datetime] = None
    steps: list[OnboardingStep]
    progress_percent: int  # 0-100
    required_complete: int  # count of required steps completed
    required_total: int  # total required steps


class OnboardingCompleteResponse(BaseModel):
    """Response schema for onboarding completion endpoint."""
    success: bool
    completed_at: datetime
    message: str
