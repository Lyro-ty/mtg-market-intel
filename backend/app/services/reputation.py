"""
Reputation service for managing user trust scores and reviews.

Handles:
- Creating and updating reputation records
- Calculating reputation tiers
- Managing reviews
"""
from datetime import datetime
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.models.reputation import (
    UserReputation,
    ReputationReview,
    ReputationTier,
)

logger = get_logger()


class ReputationService:
    """Service for managing user reputation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_reputation(self, user_id: int) -> UserReputation:
        """Get or create a reputation record for a user."""
        query = select(UserReputation).where(UserReputation.user_id == user_id)
        result = await self.db.execute(query)
        reputation = result.scalar_one_or_none()

        if not reputation:
            reputation = UserReputation(
                user_id=user_id,
                total_reviews=0,
                average_rating=0.0,
                tier=ReputationTier.NEW,
                last_calculated_at=datetime.utcnow(),
            )
            self.db.add(reputation)
            await self.db.flush()

        return reputation

    async def get_reputation(self, user_id: int) -> UserReputation | None:
        """Get a user's reputation record."""
        query = select(UserReputation).where(UserReputation.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_review(
        self,
        reviewer_id: int,
        reviewee_id: int,
        rating: int,
        comment: str | None = None,
        trade_id: int | None = None,
        trade_type: str | None = None,
    ) -> ReputationReview:
        """
        Create a new review for a user.

        Args:
            reviewer_id: ID of the user leaving the review
            reviewee_id: ID of the user being reviewed
            rating: Rating 1-5
            comment: Optional comment
            trade_id: Optional trade proposal ID
            trade_type: Type of trade (buy, sell, trade, meetup)

        Returns:
            The created review

        Raises:
            ValueError: If rating is invalid or user is reviewing themselves
        """
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        if reviewer_id == reviewee_id:
            raise ValueError("Cannot review yourself")

        review = ReputationReview(
            reviewer_id=reviewer_id,
            reviewee_id=reviewee_id,
            rating=rating,
            comment=comment,
            trade_id=trade_id,
            trade_type=trade_type,
            created_at=datetime.utcnow(),
        )
        self.db.add(review)
        await self.db.flush()

        # Recalculate reputation
        await self.recalculate_reputation(reviewee_id)

        return review

    async def get_reviews_for_user(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ReputationReview], int]:
        """
        Get reviews received by a user.

        Returns:
            Tuple of (reviews, total_count)
        """
        # Get total count
        count_query = select(func.count()).where(
            ReputationReview.reviewee_id == user_id
        )
        result = await self.db.execute(count_query)
        total = result.scalar() or 0

        # Get reviews
        query = (
            select(ReputationReview)
            .where(ReputationReview.reviewee_id == user_id)
            .order_by(ReputationReview.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        reviews = list(result.scalars().all())

        return reviews, total

    async def get_reviews_by_user(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ReputationReview], int]:
        """
        Get reviews given by a user.

        Returns:
            Tuple of (reviews, total_count)
        """
        count_query = select(func.count()).where(
            ReputationReview.reviewer_id == user_id
        )
        result = await self.db.execute(count_query)
        total = result.scalar() or 0

        query = (
            select(ReputationReview)
            .where(ReputationReview.reviewer_id == user_id)
            .order_by(ReputationReview.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        reviews = list(result.scalars().all())

        return reviews, total

    async def recalculate_reputation(self, user_id: int) -> UserReputation:
        """
        Recalculate a user's reputation based on all their reviews.

        This aggregates all reviews and updates:
        - Total review count
        - Average rating
        - Rating breakdown
        - Tier

        Returns:
            Updated reputation record
        """
        reputation = await self.get_or_create_reputation(user_id)

        # Get all reviews for this user
        query = select(ReputationReview).where(
            ReputationReview.reviewee_id == user_id
        )
        result = await self.db.execute(query)
        reviews = list(result.scalars().all())

        if not reviews:
            reputation.total_reviews = 0
            reputation.average_rating = 0.0
            reputation.five_star_count = 0
            reputation.four_star_count = 0
            reputation.three_star_count = 0
            reputation.two_star_count = 0
            reputation.one_star_count = 0
            reputation.tier = ReputationTier.NEW
        else:
            # Count by rating
            counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for review in reviews:
                counts[review.rating] = counts.get(review.rating, 0) + 1

            reputation.total_reviews = len(reviews)
            reputation.average_rating = sum(r.rating for r in reviews) / len(reviews)
            reputation.five_star_count = counts[5]
            reputation.four_star_count = counts[4]
            reputation.three_star_count = counts[3]
            reputation.two_star_count = counts[2]
            reputation.one_star_count = counts[1]
            reputation.tier = reputation.calculate_tier()

        reputation.last_calculated_at = datetime.utcnow()
        await self.db.flush()

        logger.info(
            "reputation_recalculated",
            user_id=user_id,
            total_reviews=reputation.total_reviews,
            average_rating=float(reputation.average_rating),
            tier=reputation.tier.value,
        )

        return reputation

    async def get_leaderboard(
        self,
        limit: int = 20,
        min_reviews: int = 5,
    ) -> list[UserReputation]:
        """
        Get top users by reputation.

        Args:
            limit: Number of users to return
            min_reviews: Minimum reviews required to be included

        Returns:
            List of top reputation records
        """
        query = (
            select(UserReputation)
            .where(UserReputation.total_reviews >= min_reviews)
            .order_by(UserReputation.average_rating.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_statistics(self) -> dict[str, Any]:
        """Get overall reputation statistics."""
        # Count by tier
        tier_query = select(
            UserReputation.tier,
            func.count().label("count")
        ).group_by(UserReputation.tier)
        result = await self.db.execute(tier_query)
        tier_counts = {row.tier: row.count for row in result.all()}

        # Total reviews
        review_count_query = select(func.count()).select_from(ReputationReview)
        result = await self.db.execute(review_count_query)
        total_reviews = result.scalar() or 0

        # Average rating across all reviews
        avg_query = select(func.avg(ReputationReview.rating))
        result = await self.db.execute(avg_query)
        avg_rating = result.scalar() or 0.0

        return {
            "tier_distribution": tier_counts,
            "total_reviews": total_reviews,
            "average_rating": float(avg_rating),
        }
