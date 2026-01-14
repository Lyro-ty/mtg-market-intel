"""
Data integrity agent.

Monitors data quality and identifies issues.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

logger = get_logger()


class DataIntegrityAgent:
    """
    Agent for monitoring data quality and integrity.

    Checks:
    - Empty tables that should have data
    - Stale data (not updated recently)
    - Orphaned records
    - Data anomalies
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_empty_tables(self) -> dict[str, Any]:
        """
        Find tables that have zero rows but should have data.

        Returns:
            dict with empty tables and their expected population status
        """
        # Tables that should definitely have data
        expected_populated = [
            "cards",
            "mtg_sets",
            "users",
            "price_snapshots",
            "signals",
            "recommendations",
        ]

        # Tables that might be empty depending on usage
        optional_data = [
            "inventory_items",
            "want_list_items",
            "notifications",
            "tournaments",
            "news_articles",
        ]

        empty_tables = []
        warnings = []

        query = text("""
            SELECT
                relname as table_name,
                n_live_tup as row_count
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            ORDER BY relname
        """)

        result = await self.db.execute(query)
        rows = result.mappings().all()

        for row in rows:
            table_name = row["table_name"]
            row_count = row["row_count"]

            if row_count == 0:
                if table_name in expected_populated:
                    empty_tables.append({
                        "table": table_name,
                        "severity": "critical",
                        "message": f"Expected table '{table_name}' has no data",
                    })
                elif table_name in optional_data:
                    warnings.append({
                        "table": table_name,
                        "severity": "warning",
                        "message": f"Optional table '{table_name}' is empty",
                    })

        return {
            "critical_empty": [t for t in empty_tables if t["severity"] == "critical"],
            "warnings": warnings,
            "total_issues": len(empty_tables),
            "status": "critical" if len(empty_tables) > 0 else "ok",
        }

    async def check_stale_data(self) -> dict[str, Any]:
        """
        Find tables with data that hasn't been updated recently.

        Returns:
            dict with stale data indicators
        """
        stale_indicators = []
        now = datetime.now(timezone.utc)

        # Check price snapshots freshness
        query = text("""
            SELECT
                marketplace,
                MAX(snapshot_date) as last_update,
                COUNT(*) as record_count
            FROM price_snapshots
            GROUP BY marketplace
        """)

        try:
            result = await self.db.execute(query)
            rows = result.mappings().all()

            for row in rows:
                last_update = row["last_update"]
                if last_update:
                    # Convert to UTC if needed
                    if last_update.tzinfo is None:
                        last_update = last_update.replace(tzinfo=timezone.utc)
                    age = now - last_update
                    if age > timedelta(hours=2):
                        stale_indicators.append({
                            "table": "price_snapshots",
                            "category": row["marketplace"],
                            "last_update": str(last_update),
                            "age_hours": round(age.total_seconds() / 3600, 1),
                            "severity": "warning" if age < timedelta(hours=6) else "critical",
                        })
        except Exception as e:
            logger.error("stale_check_failed", table="price_snapshots", error=str(e))

        # Check signals freshness
        query = text("""
            SELECT MAX(created_at) as last_signal
            FROM signals
        """)

        try:
            result = await self.db.execute(query)
            row = result.mappings().first()
            if row and row["last_signal"]:
                last_signal = row["last_signal"]
                if last_signal.tzinfo is None:
                    last_signal = last_signal.replace(tzinfo=timezone.utc)
                age = now - last_signal
                if age > timedelta(hours=6):
                    stale_indicators.append({
                        "table": "signals",
                        "category": "all",
                        "last_update": str(last_signal),
                        "age_hours": round(age.total_seconds() / 3600, 1),
                        "severity": "warning" if age < timedelta(hours=12) else "critical",
                    })
        except Exception as e:
            logger.error("stale_check_failed", table="signals", error=str(e))

        # Check recommendations freshness
        query = text("""
            SELECT MAX(created_at) as last_rec
            FROM recommendations
        """)

        try:
            result = await self.db.execute(query)
            row = result.mappings().first()
            if row and row["last_rec"]:
                last_rec = row["last_rec"]
                if last_rec.tzinfo is None:
                    last_rec = last_rec.replace(tzinfo=timezone.utc)
                age = now - last_rec
                if age > timedelta(hours=12):
                    stale_indicators.append({
                        "table": "recommendations",
                        "category": "all",
                        "last_update": str(last_rec),
                        "age_hours": round(age.total_seconds() / 3600, 1),
                        "severity": "warning" if age < timedelta(hours=24) else "critical",
                    })
        except Exception as e:
            logger.error("stale_check_failed", table="recommendations", error=str(e))

        critical_count = len([s for s in stale_indicators if s["severity"] == "critical"])

        return {
            "stale_data": stale_indicators,
            "total_stale": len(stale_indicators),
            "critical_count": critical_count,
            "status": "critical" if critical_count > 0 else ("warning" if len(stale_indicators) > 0 else "ok"),
        }

    async def check_orphaned_records(self) -> dict[str, Any]:
        """
        Find records with broken foreign key relationships.

        Returns:
            dict with orphaned record counts
        """
        orphans = []

        # Check inventory items with non-existent cards
        query = text("""
            SELECT COUNT(*) as orphan_count
            FROM inventory_items i
            LEFT JOIN cards c ON i.card_id = c.id
            WHERE c.id IS NULL
        """)

        try:
            result = await self.db.execute(query)
            row = result.mappings().first()
            if row and row["orphan_count"] > 0:
                orphans.append({
                    "table": "inventory_items",
                    "foreign_key": "card_id",
                    "orphan_count": row["orphan_count"],
                })
        except Exception as e:
            logger.error("orphan_check_failed", table="inventory_items", error=str(e))

        # Check want list items with non-existent cards
        query = text("""
            SELECT COUNT(*) as orphan_count
            FROM want_list_items w
            LEFT JOIN cards c ON w.card_id = c.id
            WHERE c.id IS NULL
        """)

        try:
            result = await self.db.execute(query)
            row = result.mappings().first()
            if row and row["orphan_count"] > 0:
                orphans.append({
                    "table": "want_list_items",
                    "foreign_key": "card_id",
                    "orphan_count": row["orphan_count"],
                })
        except Exception as e:
            logger.error("orphan_check_failed", table="want_list_items", error=str(e))

        # Check signals with non-existent cards
        query = text("""
            SELECT COUNT(*) as orphan_count
            FROM signals s
            LEFT JOIN cards c ON s.card_id = c.id
            WHERE s.card_id IS NOT NULL AND c.id IS NULL
        """)

        try:
            result = await self.db.execute(query)
            row = result.mappings().first()
            if row and row["orphan_count"] > 0:
                orphans.append({
                    "table": "signals",
                    "foreign_key": "card_id",
                    "orphan_count": row["orphan_count"],
                })
        except Exception as e:
            logger.error("orphan_check_failed", table="signals", error=str(e))

        total_orphans = sum(o["orphan_count"] for o in orphans)

        return {
            "orphaned_records": orphans,
            "total_orphans": total_orphans,
            "status": "critical" if total_orphans > 100 else ("warning" if total_orphans > 0 else "ok"),
        }

    async def get_data_stats(self) -> dict[str, Any]:
        """
        Get quick statistics about key tables.

        Returns:
            dict with row counts and health indicators
        """
        stats = {}

        tables = [
            ("cards", "Core card catalog"),
            ("price_snapshots", "Price history"),
            ("signals", "Analytics signals"),
            ("recommendations", "Trading recommendations"),
            ("users", "User accounts"),
            ("inventory_items", "User inventories"),
            ("want_list_items", "User want lists"),
            ("tournaments", "Tournament data"),
            ("news_articles", "MTG news"),
        ]

        for table_name, description in tables:
            query = text(f"SELECT COUNT(*) as count FROM {table_name}")
            try:
                result = await self.db.execute(query)
                row = result.mappings().first()
                stats[table_name] = {
                    "description": description,
                    "count": row["count"] if row else 0,
                }
            except Exception as e:
                stats[table_name] = {
                    "description": description,
                    "count": -1,
                    "error": str(e),
                }

        return {"table_stats": stats}

    async def run_full_check(self) -> dict[str, Any]:
        """
        Run all data integrity checks.
        """
        logger.info("running_data_integrity_check")

        empty = await self.check_empty_tables()
        stale = await self.check_stale_data()
        orphans = await self.check_orphaned_records()
        stats = await self.get_data_stats()

        # Determine overall status
        if empty["status"] == "critical" or stale["status"] == "critical" or orphans["status"] == "critical":
            overall = "critical"
        elif empty["status"] == "warning" or stale["status"] == "warning" or orphans["status"] == "warning":
            overall = "warning"
        else:
            overall = "healthy"

        report = {
            "overall_status": overall,
            "empty_tables": empty,
            "stale_data": stale,
            "orphaned_records": orphans,
            "stats": stats,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("data_integrity_check_complete", status=overall)
        return report
