"""
Inventory repository for user collection management.

This repository handles all inventory-related database operations
including CRUD, valuation, and portfolio analysis.
"""
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryItem, InventoryCondition
from app.repositories.base import BaseRepository


class InventoryRepository(BaseRepository[InventoryItem]):
    """
    Repository for user inventory operations.

    Extends BaseRepository with inventory-specific functionality
    like portfolio analysis and condition-based filtering.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(InventoryItem, db)

    async def get_user_inventory(
        self,
        user_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        condition: InventoryCondition | None = None,
        is_foil: bool | None = None,
        sort_by: str = "created_at",
        sort_desc: bool = True,
    ) -> Sequence[InventoryItem]:
        """
        Get all inventory items for a user.

        Args:
            user_id: User ID
            skip: Number of items to skip
            limit: Maximum items to return
            condition: Filter by condition
            is_foil: Filter by foil status
            sort_by: Column to sort by
            sort_desc: Sort descending if True

        Returns:
            Sequence of inventory items
        """
        stmt = select(InventoryItem).where(InventoryItem.user_id == user_id)

        if condition:
            stmt = stmt.where(InventoryItem.condition == condition)
        if is_foil is not None:
            stmt = stmt.where(InventoryItem.is_foil == is_foil)

        if hasattr(InventoryItem, sort_by):
            column = getattr(InventoryItem, sort_by)
            stmt = stmt.order_by(column.desc() if sort_desc else column)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_user_item(
        self,
        user_id: int,
        card_id: int,
        condition: InventoryCondition = InventoryCondition.NEAR_MINT,
        is_foil: bool = False,
    ) -> InventoryItem | None:
        """
        Get a specific inventory item by card and variant.

        Args:
            user_id: User ID
            card_id: Card ID
            condition: Card condition
            is_foil: Foil status

        Returns:
            InventoryItem or None
        """
        stmt = select(InventoryItem).where(
            and_(
                InventoryItem.user_id == user_id,
                InventoryItem.card_id == card_id,
                InventoryItem.condition == condition,
                InventoryItem.is_foil == is_foil,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_item(
        self,
        user_id: int,
        card_id: int,
        quantity: int = 1,
        *,
        condition: InventoryCondition = InventoryCondition.NEAR_MINT,
        is_foil: bool = False,
        acquisition_price: float | None = None,
        acquisition_date: datetime | None = None,
        notes: str | None = None,
    ) -> InventoryItem:
        """
        Add or update an inventory item.

        If an item with the same card/condition/foil exists, updates quantity.
        Otherwise creates a new item.

        Args:
            user_id: User ID
            card_id: Card ID
            quantity: Number to add
            condition: Card condition
            is_foil: Foil status
            acquisition_price: Price paid per card
            acquisition_date: When acquired
            notes: Optional notes

        Returns:
            Created or updated InventoryItem
        """
        existing = await self.get_user_item(user_id, card_id, condition, is_foil)

        if existing:
            existing.quantity += quantity
            if acquisition_price is not None:
                # Average the acquisition prices
                total_value = (existing.acquisition_price or 0) * (existing.quantity - quantity)
                total_value += acquisition_price * quantity
                existing.acquisition_price = total_value / existing.quantity
            await self.db.flush()
            return existing

        return await self.create(
            user_id=user_id,
            card_id=card_id,
            quantity=quantity,
            condition=condition,
            is_foil=is_foil,
            acquisition_price=acquisition_price,
            acquisition_date=acquisition_date or datetime.utcnow(),
            notes=notes,
        )

    async def remove_item(
        self,
        user_id: int,
        card_id: int,
        quantity: int = 1,
        *,
        condition: InventoryCondition = InventoryCondition.NEAR_MINT,
        is_foil: bool = False,
    ) -> InventoryItem | None:
        """
        Remove quantity from an inventory item.

        If quantity reaches zero, deletes the item.

        Args:
            user_id: User ID
            card_id: Card ID
            quantity: Number to remove
            condition: Card condition
            is_foil: Foil status

        Returns:
            Updated InventoryItem or None if deleted/not found
        """
        existing = await self.get_user_item(user_id, card_id, condition, is_foil)

        if not existing:
            return None

        if existing.quantity <= quantity:
            await self.db.delete(existing)
            await self.db.flush()
            return None

        existing.quantity -= quantity
        await self.db.flush()
        return existing

    async def count_user_items(self, user_id: int) -> int:
        """
        Count total inventory items for a user.

        Args:
            user_id: User ID

        Returns:
            Number of distinct items (not total quantity)
        """
        return await self.count(user_id=user_id)

    async def sum_user_quantity(self, user_id: int) -> int:
        """
        Sum total card quantity across all inventory items.

        Args:
            user_id: User ID

        Returns:
            Total quantity of cards
        """
        stmt = select(func.sum(InventoryItem.quantity)).where(
            InventoryItem.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_card_ids(self, user_id: int) -> list[int]:
        """
        Get all unique card IDs in user's inventory.

        Args:
            user_id: User ID

        Returns:
            List of card IDs
        """
        stmt = (
            select(InventoryItem.card_id)
            .where(InventoryItem.user_id == user_id)
            .distinct()
        )
        result = await self.db.execute(stmt)
        return [row.card_id for row in result]

    async def get_by_condition(
        self,
        user_id: int,
        condition: InventoryCondition,
    ) -> Sequence[InventoryItem]:
        """
        Get all items with a specific condition.

        Args:
            user_id: User ID
            condition: Card condition

        Returns:
            Sequence of matching items
        """
        return await self.find_by(user_id=user_id, condition=condition)

    async def get_acquisition_stats(self, user_id: int) -> dict[str, Any]:
        """
        Get acquisition statistics for user's inventory.

        Returns:
            Dictionary with total_invested, avg_acquisition_price, item_count
        """
        stmt = select(
            func.sum(InventoryItem.acquisition_price * InventoryItem.quantity).label("total_invested"),
            func.avg(InventoryItem.acquisition_price).label("avg_acquisition_price"),
            func.count(InventoryItem.id).label("item_count"),
            func.sum(InventoryItem.quantity).label("total_quantity"),
        ).where(
            and_(
                InventoryItem.user_id == user_id,
                InventoryItem.acquisition_price.isnot(None),
            )
        )
        result = await self.db.execute(stmt)
        row = result.first()

        return {
            "total_invested": float(row.total_invested) if row.total_invested else 0,
            "avg_acquisition_price": float(row.avg_acquisition_price) if row.avg_acquisition_price else 0,
            "item_count": row.item_count or 0,
            "total_quantity": row.total_quantity or 0,
        }

    async def bulk_add(
        self,
        user_id: int,
        items: list[dict[str, Any]],
    ) -> list[InventoryItem]:
        """
        Add multiple items to inventory.

        Args:
            user_id: User ID
            items: List of item dictionaries with card_id, quantity, etc.

        Returns:
            List of created/updated items
        """
        results = []
        for item in items:
            result = await self.add_item(
                user_id=user_id,
                card_id=item["card_id"],
                quantity=item.get("quantity", 1),
                condition=item.get("condition", InventoryCondition.NEAR_MINT),
                is_foil=item.get("is_foil", False),
                acquisition_price=item.get("acquisition_price"),
                acquisition_date=item.get("acquisition_date"),
                notes=item.get("notes"),
            )
            results.append(result)
        return results
