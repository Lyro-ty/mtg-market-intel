"""
Fast autocomplete service for card names.

Uses prefix matching on card names for instant suggestions.
"""
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card

logger = structlog.get_logger()


class AutocompleteService:
    """
    Service for fast card name autocomplete.

    Uses database prefix matching for instant suggestions.
    """

    async def get_suggestions(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        """
        Get autocomplete suggestions for a search query.

        Args:
            db: Database session
            query: Partial card name to search for
            limit: Maximum suggestions to return (default 5)

        Returns:
            List of suggestion dicts with id, name, set_code, image_url
        """
        if not query or len(query) < 1:
            return []

        # Use ILIKE for case-insensitive prefix matching
        search_query = select(Card).where(
            Card.name.ilike(f"{query}%")
        ).order_by(Card.name).limit(limit)

        result = await db.execute(search_query)
        cards = result.scalars().all()

        return [
            {
                "id": card.id,
                "name": card.name,
                "set_code": card.set_code,
                "image_url": card.image_url_small or card.image_url,
            }
            for card in cards
        ]
