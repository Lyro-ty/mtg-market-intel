"""Portfolio tracking service for collection value history."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.inventory import InventoryItem
from app.models.portfolio_snapshot import PortfolioSnapshot


class PortfolioService:
    """Service for tracking portfolio value over time."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_snapshot(self, user_id: int) -> PortfolioSnapshot:
        """Create a daily portfolio snapshot for a user."""
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Check if snapshot already exists for today
        existing = await self.db.execute(
            select(PortfolioSnapshot).where(
                PortfolioSnapshot.user_id == user_id,
                func.date(PortfolioSnapshot.snapshot_date) == today.date(),
            )
        )
        existing_snapshot = existing.scalar_one_or_none()

        # Calculate current portfolio metrics
        metrics = await self._calculate_portfolio_metrics(user_id)

        # Get historical values for change calculations
        value_1d = await self._get_historical_value(user_id, 1)
        value_7d = await self._get_historical_value(user_id, 7)
        value_30d = await self._get_historical_value(user_id, 30)

        current_value = metrics["total_value"]

        # Calculate changes
        change_1d = current_value - value_1d if value_1d is not None else None
        change_7d = current_value - value_7d if value_7d is not None else None
        change_30d = current_value - value_30d if value_30d is not None else None

        pct_1d = (change_1d / value_1d * 100) if value_1d and value_1d > 0 else None
        pct_7d = (change_7d / value_7d * 100) if value_7d and value_7d > 0 else None
        pct_30d = (change_30d / value_30d * 100) if value_30d and value_30d > 0 else None

        # Get top movers
        top_gainers, top_losers = await self._get_top_movers(user_id)

        # Get breakdown
        breakdown = await self._get_breakdown(user_id)

        if existing_snapshot:
            # Update existing snapshot
            existing_snapshot.total_value = metrics["total_value"]
            existing_snapshot.total_cost = metrics["total_cost"]
            existing_snapshot.total_cards = metrics["total_cards"]
            existing_snapshot.unique_cards = metrics["unique_cards"]
            existing_snapshot.value_change_1d = change_1d
            existing_snapshot.value_change_7d = change_7d
            existing_snapshot.value_change_30d = change_30d
            existing_snapshot.value_change_pct_1d = pct_1d
            existing_snapshot.value_change_pct_7d = pct_7d
            existing_snapshot.value_change_pct_30d = pct_30d
            existing_snapshot.breakdown = breakdown
            existing_snapshot.top_gainers = top_gainers
            existing_snapshot.top_losers = top_losers
            await self.db.commit()
            await self.db.refresh(existing_snapshot)
            return existing_snapshot
        else:
            # Create new snapshot
            snapshot = PortfolioSnapshot(
                user_id=user_id,
                snapshot_date=today,
                total_value=metrics["total_value"],
                total_cost=metrics["total_cost"],
                total_cards=metrics["total_cards"],
                unique_cards=metrics["unique_cards"],
                value_change_1d=change_1d,
                value_change_7d=change_7d,
                value_change_30d=change_30d,
                value_change_pct_1d=pct_1d,
                value_change_pct_7d=pct_7d,
                value_change_pct_30d=pct_30d,
                breakdown=breakdown,
                top_gainers=top_gainers,
                top_losers=top_losers,
            )
            self.db.add(snapshot)
            await self.db.commit()
            await self.db.refresh(snapshot)
            return snapshot

    async def get_history(
        self,
        user_id: int,
        days: int = 30,
    ) -> list[PortfolioSnapshot]:
        """Get portfolio history for a user."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.user_id == user_id,
                PortfolioSnapshot.snapshot_date >= cutoff,
            )
            .order_by(PortfolioSnapshot.snapshot_date.asc())
        )
        return list(result.scalars().all())

    async def get_latest_snapshot(self, user_id: int) -> Optional[PortfolioSnapshot]:
        """Get the most recent portfolio snapshot."""
        result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == user_id)
            .order_by(PortfolioSnapshot.snapshot_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _calculate_portfolio_metrics(self, user_id: int) -> dict:
        """Calculate current portfolio value and metrics."""
        # Get inventory with current values
        result = await self.db.execute(
            select(
                func.sum(InventoryItem.quantity).label("total_cards"),
                func.count(InventoryItem.id).label("unique_cards"),
                func.sum(InventoryItem.current_value * InventoryItem.quantity).label("total_value"),
                func.sum(
                    func.coalesce(InventoryItem.acquisition_price, 0) * InventoryItem.quantity
                ).label("total_cost"),
            ).where(InventoryItem.user_id == user_id)
        )
        row = result.one()

        return {
            "total_cards": row.total_cards or 0,
            "unique_cards": row.unique_cards or 0,
            "total_value": float(row.total_value or 0),
            "total_cost": float(row.total_cost or 0),
        }

    async def _get_historical_value(
        self, user_id: int, days_ago: int
    ) -> Optional[float]:
        """Get portfolio value from X days ago."""
        target_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
        result = await self.db.execute(
            select(PortfolioSnapshot.total_value)
            .where(
                PortfolioSnapshot.user_id == user_id,
                func.date(PortfolioSnapshot.snapshot_date) == target_date.date(),
            )
        )
        value = result.scalar_one_or_none()
        return float(value) if value is not None else None

    async def _get_top_movers(
        self, user_id: int, limit: int = 5
    ) -> tuple[list[dict], list[dict]]:
        """Get top gaining and losing cards in user's inventory."""
        # Get inventory items with value change
        result = await self.db.execute(
            select(
                InventoryItem.id,
                InventoryItem.card_id,
                Card.name.label("card_name"),
                Card.set_code,
                InventoryItem.current_value,
                InventoryItem.value_change_pct,
            )
            .join(Card, InventoryItem.card_id == Card.id)
            .where(
                InventoryItem.user_id == user_id,
                InventoryItem.value_change_pct.isnot(None),
            )
            .order_by(InventoryItem.value_change_pct.desc())
        )
        all_items = list(result.all())

        gainers = [
            {
                "card_id": item.card_id,
                "card_name": item.card_name,
                "set_code": item.set_code,
                "current_value": item.current_value,
                "change_pct": item.value_change_pct,
            }
            for item in all_items[:limit]
            if item.value_change_pct and item.value_change_pct > 0
        ]

        losers = [
            {
                "card_id": item.card_id,
                "card_name": item.card_name,
                "set_code": item.set_code,
                "current_value": item.current_value,
                "change_pct": item.value_change_pct,
            }
            for item in reversed(all_items[-limit:])
            if item.value_change_pct and item.value_change_pct < 0
        ]

        return gainers, losers

    async def _get_breakdown(self, user_id: int) -> dict:
        """Get portfolio value breakdown by category."""
        # By foil status
        foil_result = await self.db.execute(
            select(
                InventoryItem.is_foil,
                func.sum(InventoryItem.current_value * InventoryItem.quantity).label("value"),
            )
            .where(InventoryItem.user_id == user_id)
            .group_by(InventoryItem.is_foil)
        )
        foil_rows = list(foil_result.all())

        foil_value = 0.0
        non_foil_value = 0.0
        for row in foil_rows:
            if row.is_foil:
                foil_value = float(row.value or 0)
            else:
                non_foil_value = float(row.value or 0)

        # By set (top 10)
        set_result = await self.db.execute(
            select(
                Card.set_code,
                func.sum(InventoryItem.current_value * InventoryItem.quantity).label("value"),
            )
            .join(Card, InventoryItem.card_id == Card.id)
            .where(InventoryItem.user_id == user_id)
            .group_by(Card.set_code)
            .order_by(func.sum(InventoryItem.current_value * InventoryItem.quantity).desc())
            .limit(10)
        )
        set_rows = list(set_result.all())
        by_set = {row.set_code: float(row.value or 0) for row in set_rows}

        return {
            "foil": foil_value,
            "non_foil": non_foil_value,
            "by_set": by_set,
        }
