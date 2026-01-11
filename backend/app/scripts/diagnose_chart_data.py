"""
Diagnostic script to check why market index charts show "No data available".

This script checks:
1. Total price snapshots in database
2. Snapshots by currency (USD, EUR)
3. Snapshots by marketplace
4. Recent snapshots (last 7 days)
5. Query conditions that might be filtering out data
"""
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, and_

from app.db.session import SessionLocal
from app.models import PriceSnapshot, Marketplace, Card


async def diagnose_chart_data():
    """Diagnose why market index charts show no data."""
    async with SessionLocal() as db:
        print("=" * 80)
        print("MARKET INDEX CHART DATA DIAGNOSTICS")
        print("=" * 80)
        print()
        
        # 1. Total snapshots
        total_snapshots = await db.scalar(
            select(func.count(PriceSnapshot.time))
        ) or 0
        print(f"1. Total price snapshots in database: {total_snapshots}")
        print()
        
        if total_snapshots == 0:
            print("❌ NO PRICE SNAPSHOTS FOUND IN DATABASE")
            print("   This is the problem! Price collection tasks may not be running.")
            print("   Check Celery workers and price collection tasks.")
            return
        
        # 2. Snapshots by currency
        print("2. Snapshots by currency:")
        for currency in ["USD", "EUR", "TIX"]:
            count = await db.scalar(
                select(func.count(PriceSnapshot.time)).where(
                    PriceSnapshot.currency == currency
                )
            ) or 0
            print(f"   {currency}: {count}")
        print()
        
        # 3. Snapshots by marketplace
        print("3. Snapshots by marketplace:")
        marketplace_query = select(
            Marketplace.slug,
            Marketplace.name,
            func.count(PriceSnapshot.time).label("count")
        ).join(
            PriceSnapshot, PriceSnapshot.marketplace_id == Marketplace.id
        ).group_by(Marketplace.slug, Marketplace.name)
        
        result = await db.execute(marketplace_query)
        for row in result.all():
            print(f"   {row.slug} ({row.name}): {row.count}")
        print()
        
        # 4. Recent snapshots (last 7 days)
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        
        recent_snapshots = await db.scalar(
            select(func.count(PriceSnapshot.time)).where(
                PriceSnapshot.time >= seven_days_ago
            )
        ) or 0
        print(f"4. Snapshots in last 7 days: {recent_snapshots}")
        print()
        
        # 5. USD snapshots in last 7 days (what the chart query needs)
        usd_recent = await db.scalar(
            select(func.count(PriceSnapshot.time)).where(
                and_(
                    PriceSnapshot.time >= seven_days_ago,
                    PriceSnapshot.currency == "USD",
                    PriceSnapshot.price.isnot(None),
                    PriceSnapshot.price > 0,
                )
            )
        ) or 0
        print(f"5. USD snapshots in last 7 days (with valid price): {usd_recent}")
        print()
        
        # 6. Check for snapshots with price > 0
        valid_price_snapshots = await db.scalar(
            select(func.count(PriceSnapshot.time)).where(
                and_(
                    PriceSnapshot.price.isnot(None),
                    PriceSnapshot.price > 0,
                )
            )
        ) or 0
        print(f"6. Snapshots with valid price (> 0): {valid_price_snapshots}")
        print()
        
        # 7. Sample of recent USD snapshots
        print("7. Sample of 5 most recent USD snapshots:")
        sample_query = select(
            PriceSnapshot.time,
            PriceSnapshot.price,
            PriceSnapshot.currency,
            Marketplace.slug.label("marketplace"),
            Card.name.label("card_name")
        ).join(
            Marketplace, PriceSnapshot.marketplace_id == Marketplace.id
        ).join(
            Card, PriceSnapshot.card_id == Card.id
        ).where(
            and_(
                PriceSnapshot.currency == "USD",
                PriceSnapshot.price > 0,
            )
        ).order_by(PriceSnapshot.time.desc()).limit(5)
        
        result = await db.execute(sample_query)
        samples = result.all()
        if samples:
            for sample in samples:
                print(f"   {sample.time} | ${sample.price} | {sample.marketplace} | {sample.card_name}")
        else:
            print("   ❌ No USD snapshots found!")
        print()
        
        # 8. Check time-bucketed query (what the chart actually uses)
        print("8. Testing time-bucketed query (7d range, 30min buckets):")
        bucket_seconds = 30 * 60  # 30 minutes
        bucket_expr = func.to_timestamp(
            func.floor(func.extract('epoch', PriceSnapshot.time) / bucket_seconds) * bucket_seconds
        )
        
        test_query = select(
            bucket_expr.label("bucket_time"),
            func.avg(PriceSnapshot.price).label("avg_price"),
            func.count(func.distinct(PriceSnapshot.card_id)).label("card_count"),
        ).where(
            and_(
                PriceSnapshot.time >= seven_days_ago,
                PriceSnapshot.currency == "USD",
                PriceSnapshot.price.isnot(None),
                PriceSnapshot.price > 0,
            )
        ).group_by(bucket_expr).order_by(bucket_expr)
        
        result = await db.execute(test_query)
        rows = result.all()
        print(f"   Buckets returned: {len(rows)}")
        if rows:
            print("   First 3 buckets:")
            for i, row in enumerate(rows[:3]):
                print(f"     {row.bucket_time}: avg=${row.avg_price:.2f}, cards={row.card_count}")
        else:
            print("   ❌ No buckets returned - this is why the chart shows 'No data available'")
        print()
        
        # 9. Recommendations
        print("=" * 80)
        print("RECOMMENDATIONS:")
        print("=" * 80)
        
        if total_snapshots == 0:
            print("1. ❌ No price snapshots exist. Run price collection tasks:")
            print("   - Check Celery workers are running")
            print("   - Check collect_price_data task is scheduled")
            print("   - Manually trigger: seed_comprehensive_price_data task")
        elif usd_recent == 0:
            print("1. ❌ No USD snapshots in last 7 days.")
            if recent_snapshots > 0:
                print("   - There are snapshots, but not USD currency")
                print("   - Check if snapshots are being created with correct currency")
                print("   - Verify marketplace structure (should be tcgplayer, cardmarket, mtgo)")
            else:
                print("   - No recent snapshots at all")
                print("   - Price collection tasks may not be running frequently enough")
        elif len(rows) == 0:
            print("1. ❌ Time-bucketed query returns no results")
            print("   - Data exists but query conditions are too restrictive")
            print("   - Check if snapshot_time is in correct timezone")
            print("   - Verify price values are > 0")
        else:
            print("1. ✅ Data exists and query should work")
            print("   - If chart still shows 'No data', check:")
            print("     * Frontend API call is correct")
            print("     * Network/authentication issues")
            print("     * Browser console for errors")
        
        print()


if __name__ == "__main__":
    asyncio.run(diagnose_chart_data())

