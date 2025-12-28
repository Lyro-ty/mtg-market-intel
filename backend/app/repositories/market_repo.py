"""
Market repository for aggregate market data queries.

This repository handles market-wide analytics using TimescaleDB
continuous aggregates, with special handling for the aggregate lag
to ensure real-time data is included in results.
"""
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CardCondition, CardLanguage, PERIOD_INTERVALS


class MarketRepository:
    """
    Repository for market-wide data operations.

    Uses continuous aggregates for historical data and supplements
    with real-time queries for the most recent data points.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_market_index(
        self,
        currency: str,
        period: str = "7d",
        *,
        condition: CardCondition | None = None,
        is_foil: bool | None = None,
        language: CardLanguage | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get market index data for charting.

        Combines continuous aggregate data with real-time data to handle
        the aggregate refresh lag transparently.

        Args:
            currency: Currency to filter by (USD, EUR)
            period: Time period (7d, 30d, 90d, 1y)
            condition: Optional condition filter
            is_foil: Optional foil filter
            language: Optional language filter

        Returns:
            List of time-series data points
        """
        # Determine which aggregate and bucket size to use
        if period == "7d":
            aggregate_table = "market_index_30min"
            bucket_interval = "30 minutes"
            lag_threshold = timedelta(minutes=30)
        elif period in ("30d", "90d"):
            aggregate_table = "market_index_hourly"
            bucket_interval = "1 hour"
            lag_threshold = timedelta(hours=1)
        else:  # 1y or longer
            aggregate_table = "market_index_daily"
            bucket_interval = "1 day"
            lag_threshold = timedelta(days=1)

        interval = PERIOD_INTERVALS.get(period, "7 days")
        now = datetime.utcnow()
        lag_cutoff = now - lag_threshold

        # Build filter conditions
        conditions = ["currency = :currency"]
        params: dict[str, Any] = {"currency": currency, "interval": interval}

        if condition:
            conditions.append("condition = :condition")
            params["condition"] = condition.value
        if is_foil is not None:
            conditions.append("is_foil = :is_foil")
            params["is_foil"] = is_foil
        if language:
            conditions.append("language = :language")
            params["language"] = language.value

        filter_clause = " AND ".join(conditions)

        # Query 1: Get historical data from aggregate (before lag cutoff)
        aggregate_query = text(f"""
            SELECT
                bucket as time,
                avg_price,
                avg_market_price,
                min_price,
                max_price,
                card_count,
                total_listings,
                volume
            FROM {aggregate_table}
            WHERE {filter_clause}
              AND bucket >= NOW() - :interval::interval
              AND bucket < :lag_cutoff
            ORDER BY bucket
        """)

        params["lag_cutoff"] = lag_cutoff
        aggregate_result = await self.db.execute(aggregate_query, params)
        historical_data = [dict(row._mapping) for row in aggregate_result]

        # Query 2: Get real-time data (after lag cutoff)
        realtime_query = text(f"""
            SELECT
                time_bucket('{bucket_interval}', time) AS time,
                AVG(price) AS avg_price,
                AVG(price_market) AS avg_market_price,
                MIN(price_low) AS min_price,
                MAX(price_high) AS max_price,
                COUNT(DISTINCT card_id) AS card_count,
                SUM(num_listings) AS total_listings,
                SUM(price * COALESCE(total_quantity, num_listings, 1)) AS volume
            FROM price_snapshots
            WHERE {filter_clause}
              AND time >= :lag_cutoff
              AND price > 0
            GROUP BY time_bucket('{bucket_interval}', time)
            ORDER BY time
        """)

        realtime_result = await self.db.execute(realtime_query, params)
        realtime_data = [dict(row._mapping) for row in realtime_result]

        # Combine and return
        return historical_data + realtime_data

    async def get_market_overview(self, currency: str = "USD") -> dict[str, Any]:
        """
        Get market overview statistics.

        Returns:
            Dictionary with total_cards, total_listings, avg_price, volume_24h
        """
        query = text("""
            SELECT
                COUNT(DISTINCT card_id) as total_cards,
                SUM(num_listings) as total_listings,
                AVG(price) as avg_price,
                SUM(price * COALESCE(total_quantity, num_listings, 1)) as volume_24h
            FROM price_snapshots
            WHERE currency = :currency
              AND time >= NOW() - INTERVAL '24 hours'
              AND price > 0
        """)

        result = await self.db.execute(query, {"currency": currency})
        row = result.first()

        if row:
            return {
                "total_cards": row.total_cards or 0,
                "total_listings": row.total_listings or 0,
                "avg_price": float(row.avg_price) if row.avg_price else 0,
                "volume_24h": float(row.volume_24h) if row.volume_24h else 0,
                "currency": currency,
            }
        return {
            "total_cards": 0,
            "total_listings": 0,
            "avg_price": 0,
            "volume_24h": 0,
            "currency": currency,
        }

    async def get_top_movers(
        self,
        currency: str,
        direction: str = "up",
        limit: int = 10,
        period: str = "24h",
    ) -> list[dict[str, Any]]:
        """
        Get cards with the biggest price movements.

        Args:
            currency: Currency to filter by
            direction: "up" for gainers, "down" for losers
            limit: Maximum number of results
            period: Time period to compare

        Returns:
            List of cards with price change data
        """
        interval = PERIOD_INTERVALS.get(period, "1 day")
        order = "DESC" if direction == "up" else "ASC"

        query = text(f"""
            WITH price_changes AS (
                SELECT
                    card_id,
                    FIRST(avg_price, bucket) as start_price,
                    LAST(avg_price, bucket) as end_price,
                    (LAST(avg_price, bucket) - FIRST(avg_price, bucket)) /
                        NULLIF(FIRST(avg_price, bucket), 0) as change_pct
                FROM card_prices_hourly
                WHERE currency = :currency
                  AND bucket >= NOW() - :interval::interval
                GROUP BY card_id
                HAVING FIRST(avg_price, bucket) > 0.5  -- Filter out very cheap cards
            )
            SELECT
                pc.card_id,
                c.name as card_name,
                c.set_code,
                pc.start_price,
                pc.end_price,
                pc.end_price - pc.start_price as change,
                pc.change_pct
            FROM price_changes pc
            JOIN cards c ON c.id = pc.card_id
            WHERE pc.change_pct IS NOT NULL
            ORDER BY pc.change_pct {order}
            LIMIT :limit
        """)

        result = await self.db.execute(query, {
            "currency": currency,
            "interval": interval,
            "limit": limit,
        })

        return [dict(row._mapping) for row in result]

    async def get_spread_opportunities(
        self,
        currency: str = "USD",
        min_spread_pct: float = 0.15,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Find arbitrage opportunities based on price spreads between marketplaces.

        Args:
            currency: Currency to filter by
            min_spread_pct: Minimum spread percentage (0.15 = 15%)
            limit: Maximum number of results

        Returns:
            List of arbitrage opportunities
        """
        query = text("""
            WITH recent_prices AS (
                SELECT DISTINCT ON (card_id, marketplace_id)
                    card_id,
                    marketplace_id,
                    price,
                    time
                FROM price_snapshots
                WHERE currency = :currency
                  AND time >= NOW() - INTERVAL '1 hour'
                  AND price > 0
                ORDER BY card_id, marketplace_id, time DESC
            ),
            spreads AS (
                SELECT
                    rp1.card_id,
                    rp1.marketplace_id as buy_marketplace_id,
                    rp2.marketplace_id as sell_marketplace_id,
                    rp1.price as buy_price,
                    rp2.price as sell_price,
                    rp2.price - rp1.price as spread,
                    (rp2.price - rp1.price) / rp1.price as spread_pct
                FROM recent_prices rp1
                JOIN recent_prices rp2 ON rp1.card_id = rp2.card_id
                    AND rp1.marketplace_id != rp2.marketplace_id
                    AND rp2.price > rp1.price
            )
            SELECT
                s.card_id,
                c.name as card_name,
                c.set_code,
                m1.name as buy_marketplace,
                m2.name as sell_marketplace,
                s.buy_price,
                s.sell_price,
                s.spread,
                s.spread_pct
            FROM spreads s
            JOIN cards c ON c.id = s.card_id
            JOIN marketplaces m1 ON m1.id = s.buy_marketplace_id
            JOIN marketplaces m2 ON m2.id = s.sell_marketplace_id
            WHERE s.spread_pct >= :min_spread_pct
            ORDER BY s.spread_pct DESC
            LIMIT :limit
        """)

        result = await self.db.execute(query, {
            "currency": currency,
            "min_spread_pct": min_spread_pct,
            "limit": limit,
        })

        return [dict(row._mapping) for row in result]

    async def get_volume_by_format(
        self,
        currency: str = "USD",
        period: str = "7d",
    ) -> list[dict[str, Any]]:
        """
        Get trading volume grouped by card format legality.

        Returns:
            List of format/volume pairs
        """
        interval = PERIOD_INTERVALS.get(period, "7 days")

        query = text("""
            SELECT
                c.legalities->>'standard' as format_legality,
                COUNT(DISTINCT ps.card_id) as card_count,
                SUM(ps.price * COALESCE(ps.total_quantity, ps.num_listings, 1)) as volume
            FROM price_snapshots ps
            JOIN cards c ON c.id = ps.card_id
            WHERE ps.currency = :currency
              AND ps.time >= NOW() - :interval::interval
              AND ps.price > 0
            GROUP BY c.legalities->>'standard'
            ORDER BY volume DESC
        """)

        result = await self.db.execute(query, {
            "currency": currency,
            "interval": interval,
        })

        return [dict(row._mapping) for row in result]
