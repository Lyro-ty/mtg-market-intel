"""
Price repository for TimescaleDB price snapshot operations.

This repository handles all price-related database operations,
including inserting new snapshots and querying historical data
from both the hypertable and continuous aggregates.
"""
from datetime import datetime, timedelta
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    CardCondition,
    CardLanguage,
    PERIOD_INTERVALS,
)


class PriceRepository:
    """
    Repository for price snapshot operations.

    Handles:
    - Inserting individual and batch price snapshots
    - Querying price history for cards
    - Getting latest prices with optional filters
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def insert_snapshot(
        self,
        card_id: int,
        marketplace_id: int,
        price: float,
        currency: str,
        *,
        time: datetime | None = None,
        condition: CardCondition = CardCondition.NEAR_MINT,
        is_foil: bool = False,
        language: CardLanguage = CardLanguage.ENGLISH,
        price_low: float | None = None,
        price_mid: float | None = None,
        price_high: float | None = None,
        price_market: float | None = None,
        num_listings: int | None = None,
        total_quantity: int | None = None,
    ) -> None:
        """
        Insert a single price snapshot.

        Uses ON CONFLICT DO UPDATE to handle duplicates gracefully.
        """
        query = text("""
            INSERT INTO price_snapshots (
                time, card_id, marketplace_id, condition, is_foil, language,
                price, price_low, price_mid, price_high, price_market,
                currency, num_listings, total_quantity
            ) VALUES (
                :time, :card_id, :marketplace_id, :condition, :is_foil, :language,
                :price, :price_low, :price_mid, :price_high, :price_market,
                :currency, :num_listings, :total_quantity
            )
            ON CONFLICT (time, card_id, marketplace_id, condition, is_foil, language)
            DO UPDATE SET
                price = EXCLUDED.price,
                price_low = EXCLUDED.price_low,
                price_mid = EXCLUDED.price_mid,
                price_high = EXCLUDED.price_high,
                price_market = EXCLUDED.price_market,
                num_listings = EXCLUDED.num_listings,
                total_quantity = EXCLUDED.total_quantity
        """)

        await self.db.execute(query, {
            "time": time or datetime.utcnow(),
            "card_id": card_id,
            "marketplace_id": marketplace_id,
            "condition": condition.value,
            "is_foil": is_foil,
            "language": language.value,
            "price": price,
            "price_low": price_low,
            "price_mid": price_mid,
            "price_high": price_high,
            "price_market": price_market,
            "currency": currency,
            "num_listings": num_listings,
            "total_quantity": total_quantity,
        })

    async def insert_batch(self, snapshots: list[dict[str, Any]]) -> int:
        """
        Insert multiple price snapshots efficiently.

        Args:
            snapshots: List of snapshot dictionaries with keys matching
                       the insert_snapshot parameters

        Returns:
            Number of rows inserted/updated
        """
        if not snapshots:
            return 0

        # Build batch insert with ON CONFLICT
        query = text("""
            INSERT INTO price_snapshots (
                time, card_id, marketplace_id, condition, is_foil, language,
                price, price_low, price_mid, price_high, price_market,
                currency, num_listings, total_quantity
            )
            SELECT
                (data->>'time')::timestamptz,
                (data->>'card_id')::int,
                (data->>'marketplace_id')::int,
                (data->>'condition')::card_condition,
                (data->>'is_foil')::boolean,
                (data->>'language')::card_language,
                (data->>'price')::numeric,
                (data->>'price_low')::numeric,
                (data->>'price_mid')::numeric,
                (data->>'price_high')::numeric,
                (data->>'price_market')::numeric,
                data->>'currency',
                (data->>'num_listings')::int,
                (data->>'total_quantity')::int
            FROM jsonb_array_elements(:data) AS data
            ON CONFLICT (time, card_id, marketplace_id, condition, is_foil, language)
            DO UPDATE SET
                price = EXCLUDED.price,
                price_low = EXCLUDED.price_low,
                price_mid = EXCLUDED.price_mid,
                price_high = EXCLUDED.price_high,
                price_market = EXCLUDED.price_market,
                num_listings = EXCLUDED.num_listings,
                total_quantity = EXCLUDED.total_quantity
        """)

        import json
        # Prepare data with defaults
        now = datetime.utcnow().isoformat()
        prepared = []
        for s in snapshots:
            prepared.append({
                "time": s.get("time", now) if isinstance(s.get("time"), str) else (s.get("time") or datetime.utcnow()).isoformat(),
                "card_id": s["card_id"],
                "marketplace_id": s["marketplace_id"],
                "condition": s.get("condition", CardCondition.NEAR_MINT.value),
                "is_foil": s.get("is_foil", False),
                "language": s.get("language", CardLanguage.ENGLISH.value),
                "price": s["price"],
                "price_low": s.get("price_low"),
                "price_mid": s.get("price_mid"),
                "price_high": s.get("price_high"),
                "price_market": s.get("price_market"),
                "currency": s.get("currency", "USD"),
                "num_listings": s.get("num_listings"),
                "total_quantity": s.get("total_quantity"),
            })

        result = await self.db.execute(query, {"data": json.dumps(prepared)})
        return result.rowcount

    async def get_card_history(
        self,
        card_id: int,
        period: str = "30d",
        *,
        condition: CardCondition | None = None,
        is_foil: bool | None = None,
        language: CardLanguage | None = None,
        currency: str | None = None,
        marketplace_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get price history for a card.

        Uses the card_prices_hourly continuous aggregate for efficient
        retrieval, supplemented with real-time data for the most recent hour.

        Args:
            card_id: Card to get history for
            period: Time period (1d, 7d, 30d, 90d, 1y)
            condition: Filter by condition
            is_foil: Filter by foil status
            language: Filter by language
            currency: Filter by currency
            marketplace_id: Filter by marketplace

        Returns:
            List of price data points
        """
        interval = PERIOD_INTERVALS.get(period, "30 days")

        # Build WHERE clauses
        conditions = ["card_id = :card_id", "bucket >= NOW() - :interval::interval"]
        params: dict[str, Any] = {"card_id": card_id, "interval": interval}

        if condition:
            conditions.append("condition = :condition")
            params["condition"] = condition.value
        if is_foil is not None:
            conditions.append("is_foil = :is_foil")
            params["is_foil"] = is_foil
        if language:
            conditions.append("language = :language")
            params["language"] = language.value
        if currency:
            conditions.append("currency = :currency")
            params["currency"] = currency
        if marketplace_id:
            conditions.append("marketplace_id = :marketplace_id")
            params["marketplace_id"] = marketplace_id

        where_clause = " AND ".join(conditions)

        query = text(f"""
            SELECT
                bucket as time,
                marketplace_id,
                condition,
                is_foil,
                language,
                currency,
                avg_price,
                avg_market_price,
                min_price,
                max_price,
                total_listings,
                total_quantity
            FROM card_prices_hourly
            WHERE {where_clause}
            ORDER BY bucket DESC
        """)

        result = await self.db.execute(query, params)
        return [dict(row._mapping) for row in result]

    async def get_latest_price(
        self,
        card_id: int,
        *,
        condition: CardCondition = CardCondition.NEAR_MINT,
        is_foil: bool = False,
        language: CardLanguage = CardLanguage.ENGLISH,
        currency: str = "USD",
        marketplace_id: int | None = None,
    ) -> float | None:
        """
        Get the most recent price for a card variant.

        Returns:
            Latest price or None if no price data exists
        """
        conditions = [
            "card_id = :card_id",
            "condition = :condition",
            "is_foil = :is_foil",
            "language = :language",
            "currency = :currency",
        ]
        params: dict[str, Any] = {
            "card_id": card_id,
            "condition": condition.value,
            "is_foil": is_foil,
            "language": language.value,
            "currency": currency,
        }

        if marketplace_id:
            conditions.append("marketplace_id = :marketplace_id")
            params["marketplace_id"] = marketplace_id

        where_clause = " AND ".join(conditions)

        query = text(f"""
            SELECT price
            FROM price_snapshots
            WHERE {where_clause}
            ORDER BY time DESC
            LIMIT 1
        """)

        result = await self.db.execute(query, params)
        row = result.first()
        return float(row.price) if row else None

    async def get_latest_prices_for_cards(
        self,
        card_ids: list[int],
        *,
        condition: CardCondition = CardCondition.NEAR_MINT,
        currency: str = "USD",
    ) -> dict[int, float]:
        """
        Get latest prices for multiple cards efficiently.

        Returns:
            Dictionary mapping card_id to price
        """
        if not card_ids:
            return {}

        query = text("""
            SELECT DISTINCT ON (card_id)
                card_id,
                price
            FROM price_snapshots
            WHERE card_id = ANY(:card_ids)
              AND condition = :condition
              AND currency = :currency
            ORDER BY card_id, time DESC
        """)

        result = await self.db.execute(query, {
            "card_ids": card_ids,
            "condition": condition.value,
            "currency": currency,
        })

        return {row.card_id: float(row.price) for row in result}

    async def get_price_change(
        self,
        card_id: int,
        period: str = "24h",
        *,
        condition: CardCondition = CardCondition.NEAR_MINT,
        currency: str = "USD",
    ) -> dict[str, Any] | None:
        """
        Calculate price change over a period.

        Returns:
            Dictionary with start_price, end_price, change, change_pct
        """
        interval = PERIOD_INTERVALS.get(period, "1 day")

        query = text("""
            WITH prices AS (
                SELECT
                    FIRST(price, time) as start_price,
                    LAST(price, time) as end_price
                FROM price_snapshots
                WHERE card_id = :card_id
                  AND condition = :condition
                  AND currency = :currency
                  AND time >= NOW() - :interval::interval
            )
            SELECT
                start_price,
                end_price,
                end_price - start_price as change,
                CASE WHEN start_price > 0
                    THEN (end_price - start_price) / start_price
                    ELSE 0
                END as change_pct
            FROM prices
            WHERE start_price IS NOT NULL
        """)

        result = await self.db.execute(query, {
            "card_id": card_id,
            "condition": condition.value,
            "currency": currency,
            "interval": interval,
        })

        row = result.first()
        if row:
            return {
                "start_price": float(row.start_price),
                "end_price": float(row.end_price),
                "change": float(row.change),
                "change_pct": float(row.change_pct),
            }
        return None
