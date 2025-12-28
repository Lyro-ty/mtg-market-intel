"""
Signal repository for market signals and analytics.

This repository handles signal detection using TimescaleDB's
time-series capabilities, replacing Python-based metric computation
with efficient SQL queries on continuous aggregates.
"""
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import PERIOD_INTERVALS


class SignalRepository:
    """
    Repository for market signal detection.

    Uses TimescaleDB aggregate functions (FIRST, LAST, STDDEV) for
    efficient momentum and volatility calculations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_momentum_signals(
        self,
        currency: str = "USD",
        period: str = "7d",
        threshold: float = 0.1,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get cards with significant price momentum.

        Momentum is calculated as (end_price - start_price) / start_price
        over the specified period.

        Args:
            currency: Currency to filter by
            period: Time period for momentum calculation
            threshold: Minimum absolute momentum (0.1 = 10%)
            limit: Maximum number of results

        Returns:
            List of cards with momentum data
        """
        interval = PERIOD_INTERVALS.get(period, "7 days")

        query = text("""
            WITH momentum_calc AS (
                SELECT
                    card_id,
                    currency,
                    FIRST(avg_price, bucket) as price_start,
                    LAST(avg_price, bucket) as price_end,
                    (LAST(avg_price, bucket) - FIRST(avg_price, bucket)) /
                        NULLIF(FIRST(avg_price, bucket), 0) as momentum
                FROM card_prices_hourly
                WHERE currency = :currency
                  AND bucket >= NOW() - :interval::interval
                GROUP BY card_id, currency
                HAVING FIRST(avg_price, bucket) > 0
            )
            SELECT
                mc.card_id,
                c.name as card_name,
                c.set_code,
                mc.currency,
                mc.price_start,
                mc.price_end,
                mc.momentum,
                CASE
                    WHEN mc.momentum > 0 THEN 'up'
                    WHEN mc.momentum < 0 THEN 'down'
                    ELSE 'neutral'
                END as direction
            FROM momentum_calc mc
            JOIN cards c ON c.id = mc.card_id
            WHERE ABS(mc.momentum) >= :threshold
            ORDER BY ABS(mc.momentum) DESC
            LIMIT :limit
        """)

        result = await self.db.execute(query, {
            "currency": currency,
            "interval": interval,
            "threshold": threshold,
            "limit": limit,
        })

        return [dict(row._mapping) for row in result]

    async def get_volatility_signals(
        self,
        currency: str = "USD",
        period: str = "7d",
        min_volatility: float = 0.2,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get cards with high price volatility.

        Volatility is calculated as the coefficient of variation
        (STDDEV / AVG) of prices over the period.

        Args:
            currency: Currency to filter by
            period: Time period for volatility calculation
            min_volatility: Minimum volatility coefficient (0.2 = 20%)
            limit: Maximum number of results

        Returns:
            List of cards with volatility data
        """
        interval = PERIOD_INTERVALS.get(period, "7 days")

        query = text("""
            WITH volatility_calc AS (
                SELECT
                    card_id,
                    currency,
                    AVG(avg_price) as avg_price,
                    STDDEV(avg_price) as price_stddev,
                    STDDEV(avg_price) / NULLIF(AVG(avg_price), 0) as volatility
                FROM card_prices_hourly
                WHERE currency = :currency
                  AND bucket >= NOW() - :interval::interval
                GROUP BY card_id, currency
                HAVING AVG(avg_price) > 0
            )
            SELECT
                vc.card_id,
                c.name as card_name,
                c.set_code,
                vc.currency,
                vc.avg_price,
                vc.price_stddev,
                vc.volatility
            FROM volatility_calc vc
            JOIN cards c ON c.id = vc.card_id
            WHERE vc.volatility >= :min_volatility
            ORDER BY vc.volatility DESC
            LIMIT :limit
        """)

        result = await self.db.execute(query, {
            "currency": currency,
            "interval": interval,
            "min_volatility": min_volatility,
            "limit": limit,
        })

        return [dict(row._mapping) for row in result]

    async def get_trend_signals(
        self,
        currency: str = "USD",
        period: str = "30d",
        min_correlation: float = 0.7,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get cards with consistent price trends.

        Uses linear regression to identify cards with strong
        upward or downward trends.

        Args:
            currency: Currency to filter by
            period: Time period for trend analysis
            min_correlation: Minimum R-squared value (0.7 = 70%)
            limit: Maximum number of results

        Returns:
            List of cards with trend data
        """
        interval = PERIOD_INTERVALS.get(period, "30 days")

        query = text("""
            WITH numbered_prices AS (
                SELECT
                    card_id,
                    bucket,
                    avg_price,
                    ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY bucket) as row_num
                FROM card_prices_hourly
                WHERE currency = :currency
                  AND bucket >= NOW() - :interval::interval
            ),
            trend_calc AS (
                SELECT
                    card_id,
                    REGR_SLOPE(avg_price, row_num) as slope,
                    REGR_R2(avg_price, row_num) as r_squared,
                    AVG(avg_price) as avg_price,
                    COUNT(*) as data_points
                FROM numbered_prices
                GROUP BY card_id
                HAVING COUNT(*) >= 10  -- Need minimum data points
            )
            SELECT
                tc.card_id,
                c.name as card_name,
                c.set_code,
                tc.slope,
                tc.r_squared,
                tc.avg_price,
                tc.data_points,
                CASE
                    WHEN tc.slope > 0 THEN 'uptrend'
                    WHEN tc.slope < 0 THEN 'downtrend'
                    ELSE 'sideways'
                END as trend_direction
            FROM trend_calc tc
            JOIN cards c ON c.id = tc.card_id
            WHERE tc.r_squared >= :min_correlation
            ORDER BY tc.r_squared DESC, ABS(tc.slope) DESC
            LIMIT :limit
        """)

        result = await self.db.execute(query, {
            "currency": currency,
            "interval": interval,
            "min_correlation": min_correlation,
            "limit": limit,
        })

        return [dict(row._mapping) for row in result]

    async def get_all_signals(
        self,
        card_id: int,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """
        Get all signal types for a specific card.

        Returns:
            Dictionary with momentum, volatility, and trend data
        """
        query = text("""
            WITH price_data AS (
                SELECT
                    bucket,
                    avg_price,
                    ROW_NUMBER() OVER (ORDER BY bucket) as row_num
                FROM card_prices_hourly
                WHERE card_id = :card_id
                  AND currency = :currency
                  AND bucket >= NOW() - INTERVAL '30 days'
            ),
            stats AS (
                SELECT
                    FIRST(avg_price, bucket) as price_7d_start,
                    LAST(avg_price, bucket) as price_current,
                    AVG(avg_price) as avg_price,
                    STDDEV(avg_price) as price_stddev,
                    REGR_SLOPE(avg_price, row_num) as trend_slope,
                    REGR_R2(avg_price, row_num) as trend_r2
                FROM price_data
            )
            SELECT
                price_7d_start,
                price_current,
                (price_current - price_7d_start) / NULLIF(price_7d_start, 0) as momentum_7d,
                avg_price,
                price_stddev,
                price_stddev / NULLIF(avg_price, 0) as volatility,
                trend_slope,
                trend_r2
            FROM stats
        """)

        result = await self.db.execute(query, {
            "card_id": card_id,
            "currency": currency,
        })

        row = result.first()
        if row:
            return {
                "card_id": card_id,
                "currency": currency,
                "momentum": {
                    "value": float(row.momentum_7d) if row.momentum_7d else 0,
                    "period": "7d",
                },
                "volatility": {
                    "value": float(row.volatility) if row.volatility else 0,
                    "stddev": float(row.price_stddev) if row.price_stddev else 0,
                },
                "trend": {
                    "slope": float(row.trend_slope) if row.trend_slope else 0,
                    "r_squared": float(row.trend_r2) if row.trend_r2 else 0,
                    "direction": (
                        "uptrend" if (row.trend_slope or 0) > 0
                        else "downtrend" if (row.trend_slope or 0) < 0
                        else "sideways"
                    ),
                },
                "current_price": float(row.price_current) if row.price_current else 0,
                "avg_price": float(row.avg_price) if row.avg_price else 0,
            }
        return {"card_id": card_id, "currency": currency}
