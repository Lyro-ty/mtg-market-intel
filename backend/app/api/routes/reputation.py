"""
Reputation API routes for managing user trust and reviews.

Endpoints:
- GET /reputation/{user_id} - Get user reputation
- GET /reputation/{user_id}/reviews - Get reviews for user
- POST /reputation/reviews - Create a review
- GET /reputation/leaderboard - Get top users by reputation
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.services.reputation import ReputationService

router = APIRouter()


# Schemas
class ReputationResponse(BaseModel):
    """User reputation data."""
    user_id: int
    total_reviews: int
    average_rating: float
    tier: str
    five_star_count: int
    four_star_count: int
    three_star_count: int
    two_star_count: int
    one_star_count: int
    last_calculated_at: str

    class Config:
        from_attributes = True


class ReviewerInfo(BaseModel):
    """Basic info about a reviewer."""
    id: int
    username: str
    display_name: str | None = None


class ReviewResponse(BaseModel):
    """A reputation review."""
    id: int
    reviewer: ReviewerInfo
    rating: int
    comment: str | None = None
    trade_type: str | None = None
    created_at: str

    class Config:
        from_attributes = True


class ReviewListResponse(BaseModel):
    """List of reviews with pagination."""
    reviews: list[ReviewResponse]
    total: int


class CreateReviewRequest(BaseModel):
    """Request to create a review."""
    reviewee_id: int = Field(..., description="ID of user being reviewed")
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    comment: str | None = Field(None, max_length=1000)
    trade_id: int | None = Field(None, description="Optional trade proposal ID")
    trade_type: str | None = Field(None, description="Type: buy, sell, trade, meetup")


class LeaderboardEntry(BaseModel):
    """Entry in the reputation leaderboard."""
    user_id: int
    username: str
    display_name: str | None = None
    total_reviews: int
    average_rating: float
    tier: str


class LeaderboardResponse(BaseModel):
    """Reputation leaderboard."""
    entries: list[LeaderboardEntry]


# Routes - IMPORTANT: Static routes must come before parameterized routes
@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    limit: int = Query(20, ge=1, le=100),
    min_reviews: int = Query(5, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Get top users by reputation."""
    service = ReputationService(db)
    reputations = await service.get_leaderboard(limit, min_reviews)

    entries = []
    for rep in reputations:
        user = rep.user
        entries.append(LeaderboardEntry(
            user_id=rep.user_id,
            username=user.username if user else "Unknown",
            display_name=user.display_name if user else None,
            total_reviews=rep.total_reviews,
            average_rating=float(rep.average_rating),
            tier=rep.tier.value if hasattr(rep.tier, 'value') else str(rep.tier),
        ))

    return LeaderboardResponse(entries=entries)


@router.get("/me", response_model=ReputationResponse)
async def get_my_reputation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's reputation."""
    service = ReputationService(db)
    reputation = await service.get_or_create_reputation(current_user.id)

    return ReputationResponse(
        user_id=reputation.user_id,
        total_reviews=reputation.total_reviews,
        average_rating=float(reputation.average_rating),
        tier=reputation.tier.value if hasattr(reputation.tier, 'value') else str(reputation.tier),
        five_star_count=reputation.five_star_count,
        four_star_count=reputation.four_star_count,
        three_star_count=reputation.three_star_count,
        two_star_count=reputation.two_star_count,
        one_star_count=reputation.one_star_count,
        last_calculated_at=reputation.last_calculated_at.isoformat(),
    )


@router.get("/{user_id}", response_model=ReputationResponse)
async def get_user_reputation(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get reputation for a specific user."""
    service = ReputationService(db)
    reputation = await service.get_or_create_reputation(user_id)

    return ReputationResponse(
        user_id=reputation.user_id,
        total_reviews=reputation.total_reviews,
        average_rating=float(reputation.average_rating),
        tier=reputation.tier.value if hasattr(reputation.tier, 'value') else str(reputation.tier),
        five_star_count=reputation.five_star_count,
        four_star_count=reputation.four_star_count,
        three_star_count=reputation.three_star_count,
        two_star_count=reputation.two_star_count,
        one_star_count=reputation.one_star_count,
        last_calculated_at=reputation.last_calculated_at.isoformat(),
    )


@router.get("/{user_id}/reviews", response_model=ReviewListResponse)
async def get_user_reviews(
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get reviews received by a user."""
    service = ReputationService(db)
    reviews, total = await service.get_reviews_for_user(user_id, limit, offset)

    return ReviewListResponse(
        reviews=[
            ReviewResponse(
                id=r.id,
                reviewer=ReviewerInfo(
                    id=r.reviewer.id,
                    username=r.reviewer.username,
                    display_name=r.reviewer.display_name,
                ),
                rating=r.rating,
                comment=r.comment,
                trade_type=r.trade_type,
                created_at=r.created_at.isoformat(),
            )
            for r in reviews
        ],
        total=total,
    )


@router.post("/reviews", response_model=ReviewResponse)
async def create_review(
    request: CreateReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a review for another user."""
    if request.reviewee_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot review yourself")

    service = ReputationService(db)

    try:
        review = await service.create_review(
            reviewer_id=current_user.id,
            reviewee_id=request.reviewee_id,
            rating=request.rating,
            comment=request.comment,
            trade_id=request.trade_id,
            trade_type=request.trade_type,
        )
        await db.commit()

        return ReviewResponse(
            id=review.id,
            reviewer=ReviewerInfo(
                id=current_user.id,
                username=current_user.username,
                display_name=current_user.display_name,
            ),
            rating=review.rating,
            comment=review.comment,
            trade_type=review.trade_type,
            created_at=review.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
