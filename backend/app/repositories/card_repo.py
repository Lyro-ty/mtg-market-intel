"""
Card repository for card catalog operations.

This repository handles card-related database operations including
search, filtering, and retrieval of card metadata.
"""
from typing import Any, Sequence

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.repositories.base import BaseRepository


class CardRepository(BaseRepository[Card]):
    """
    Repository for card operations.

    Extends BaseRepository with card-specific functionality
    like full-text search and format filtering.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(Card, db)

    async def search(
        self,
        query: str,
        *,
        set_code: str | None = None,
        colors: list[str] | None = None,
        rarity: str | None = None,
        type_line: str | None = None,
        format_legal: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[Card]:
        """
        Search cards with various filters.

        Args:
            query: Search term (matches name, type_line, oracle_text)
            set_code: Filter by set code
            colors: Filter by colors (e.g., ["W", "U"])
            rarity: Filter by rarity
            type_line: Filter by type (partial match)
            format_legal: Filter by format legality (e.g., "standard")
            min_price: Minimum price filter
            max_price: Maximum price filter
            skip: Number of results to skip
            limit: Maximum results to return

        Returns:
            Sequence of matching cards
        """
        stmt = select(Card)

        # Text search on name, type_line, oracle_text
        if query:
            search_term = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Card.name).like(search_term),
                    func.lower(Card.type_line).like(search_term),
                    func.lower(Card.oracle_text).like(search_term),
                )
            )

        # Set filter
        if set_code:
            stmt = stmt.where(Card.set_code == set_code.lower())

        # Rarity filter
        if rarity:
            stmt = stmt.where(Card.rarity == rarity.lower())

        # Type filter
        if type_line:
            stmt = stmt.where(func.lower(Card.type_line).like(f"%{type_line.lower()}%"))

        # Color filter (cards that contain ALL specified colors)
        if colors:
            for color in colors:
                stmt = stmt.where(Card.colors.contains([color]))

        # Format legality filter
        if format_legal:
            stmt = stmt.where(
                Card.legalities[format_legal].astext == "legal"
            )

        # Order by name and apply pagination
        stmt = stmt.order_by(Card.name).offset(skip).limit(limit)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_by_scryfall_id(self, scryfall_id: str) -> Card | None:
        """
        Get a card by its Scryfall UUID.

        Args:
            scryfall_id: Scryfall UUID

        Returns:
            Card or None if not found
        """
        return await self.find_one_by(scryfall_id=scryfall_id)

    async def get_by_name(self, name: str, set_code: str | None = None) -> Card | None:
        """
        Get a card by exact name, optionally filtered by set.

        Args:
            name: Exact card name
            set_code: Optional set code

        Returns:
            Card or None if not found
        """
        stmt = select(Card).where(func.lower(Card.name) == name.lower())
        if set_code:
            stmt = stmt.where(Card.set_code == set_code.lower())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ids(self, card_ids: list[int]) -> Sequence[Card]:
        """
        Get multiple cards by their IDs.

        Args:
            card_ids: List of card IDs

        Returns:
            Sequence of cards (may be fewer than requested if some don't exist)
        """
        if not card_ids:
            return []
        stmt = select(Card).where(Card.id.in_(card_ids))
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_sets(self) -> list[dict[str, Any]]:
        """
        Get all unique sets with card counts.

        Returns:
            List of sets with code, name, and card count
        """
        stmt = (
            select(
                Card.set_code,
                Card.set_name,
                func.count(Card.id).label("card_count"),
            )
            .group_by(Card.set_code, Card.set_name)
            .order_by(Card.set_name)
        )
        result = await self.db.execute(stmt)
        return [
            {"code": row.set_code, "name": row.set_name, "card_count": row.card_count}
            for row in result
        ]

    async def count_by_format(self, format_name: str) -> int:
        """
        Count cards legal in a specific format.

        Args:
            format_name: Format name (e.g., "standard", "modern")

        Returns:
            Number of legal cards
        """
        stmt = select(func.count(Card.id)).where(
            Card.legalities[format_name].astext == "legal"
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_random(self, limit: int = 10) -> Sequence[Card]:
        """
        Get random cards.

        Args:
            limit: Number of random cards to return

        Returns:
            Sequence of random cards
        """
        stmt = select(Card).order_by(func.random()).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def upsert(
        self,
        scryfall_id: str,
        **data: Any,
    ) -> Card:
        """
        Insert or update a card by Scryfall ID.

        Args:
            scryfall_id: Scryfall UUID
            **data: Card data fields

        Returns:
            Created or updated card
        """
        existing = await self.get_by_scryfall_id(scryfall_id)
        if existing:
            for key, value in data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await self.db.flush()
            return existing
        else:
            return await self.create(scryfall_id=scryfall_id, **data)
