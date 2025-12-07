# Potential Issues Preventing Charting from Working

## Summary

After fixing the marketplace structure inconsistency, here are additional potential issues that could prevent charts from working properly:

## 1. Currency Mixing Issue (CRITICAL)

### Problem
When `currency` parameter is not specified, the market index query aggregates **all currencies together** (USD and EUR). This creates inaccurate charts because:
- USD prices (TCGPlayer) are typically higher than EUR prices (Cardmarket)
- Exchange rate fluctuations affect the index
- Regional market differences are hidden
- The normalization base value becomes meaningless when mixing currencies

### Location
- `backend/app/api/routes/market.py:604-613` - Main query doesn't filter by currency when currency=None
- `backend/app/api/routes/inventory.py:969-979` - Same issue in inventory index

### Impact
- Charts show incorrect trends
- Index values are meaningless (mixing $10 USD and €8 EUR)
- Normalization base is calculated incorrectly

### Solution
**Option A (Recommended)**: Always require currency filter or default to USD
```python
# Default to USD if not specified
if not currency:
    currency = "USD"
    query_conditions.append(PriceSnapshot.currency == currency)
```

**Option B**: Use `separate_currencies=True` by default in frontend
- Frontend should always request separate currencies
- Backend already supports this via `separate_currencies` parameter

### Status
⚠️ **HIGH PRIORITY** - This is likely causing chart inaccuracies

---

## 2. Insufficient Data for Chart Ranges

### Problem
- **7d range**: Needs data points every 30 minutes (336 points)
- **30d range**: Needs data points every hour (720 points)
- **90d range**: Needs data points every 4 hours (540 points)
- **1y range**: Needs daily data points (365 points)

If price collection tasks aren't running frequently enough, charts will have gaps or show "No data available".

### Current Collection Frequency
- `collect_price_data`: Every 5 minutes (Celery schedule)
- `collect_inventory_prices`: Every 2 minutes (Celery schedule)
- `seed_comprehensive_price_data`: Every 6 hours (Celery schedule)

### Potential Issues
1. **Startup delay**: If tasks haven't run yet, no data exists
2. **Task failures**: If Celery tasks fail, no new data is collected
3. **Rate limiting**: Scryfall rate limits might prevent data collection
4. **Database issues**: Connection pool exhaustion might prevent writes

### Solution
- Ensure Celery workers are running
- Monitor task execution logs
- Add health checks for data freshness
- Consider running initial seeding on startup

### Status
⚠️ **MEDIUM PRIORITY** - Depends on infrastructure setup

---

## 3. Backfill Logic Creates Flat Lines

### Problem
The `_backfill_historical_snapshots_for_charting()` function creates placeholder snapshots using the **current price** for all historical dates. This means:
- Charts show flat lines going back in time
- No price variation until real historical data arrives
- Can be misleading to users

### Location
- `backend/app/tasks/ingestion.py:29-154`

### Current Behavior
- Creates 7 daily snapshots for 7d range
- Creates 15 snapshots (every 2 days) for 30d range  
- Creates 12 snapshots (every 5 days) for 90d range
- All use the same current price

### Impact
- Charts show artificial flat lines
- Users might think prices never changed
- Real historical data from MTGJSON will replace these, but there's a delay

### Solution
**Option A**: Disable backfill (already partially done in data_seeding.py)
- Rely on interpolation in chart endpoints instead
- Let charts show gaps until real data arrives

**Option B**: Improve backfill with better logic
- Use MTGJSON historical data if available
- Only backfill if no historical data exists
- Add a flag to indicate backfilled vs real data

### Status
⚠️ **LOW PRIORITY** - More of a UX issue than a functional bug

---

## 4. Base Value Calculation Edge Cases

### Problem
The normalization base value calculation might fail in edge cases:

1. **No data in first day**: Falls back to first point, which might be an outlier
2. **Sparse data**: If data is very sparse, base value might be calculated from a single point
3. **Currency mixing**: Base value is meaningless when currencies are mixed

### Location
- `backend/app/api/routes/market.py:772-801`
- `backend/app/api/routes/inventory.py:1032-1071`

### Current Logic
```python
base_date = start_date + timedelta(days=1)
base_query = select(func.avg(base_price_field)).where(
    and_(
        PriceSnapshot.snapshot_time >= start_date,
        PriceSnapshot.snapshot_time < base_date,
        # ... conditions
    )
)
base_value = await db.scalar(base_query)

# Fallback to first point if no base value
if not base_value or base_value <= 0:
    base_value = avg_prices[0]
```

### Potential Issues
- If first point is an outlier, normalization is skewed
- If no data in first day, uses first available point (could be days later)
- No validation that base value is reasonable

### Solution
- Use median of first 25% of points instead of average
- Validate base value is within reasonable range
- Add logging when fallback is used

### Status
⚠️ **LOW PRIORITY** - Edge case, but could cause chart inaccuracies

---

## 5. Interpolation Edge Cases

### Problem
The `interpolate_missing_points()` function might have issues:

1. **No data at all**: Returns empty array (correct, but frontend needs to handle)
2. **Very sparse data**: Interpolation might create artificial trends
3. **Time zone issues**: Timestamp parsing might fail with different formats

### Location
- `backend/app/api/routes/market.py:42-130`
- `backend/app/api/routes/inventory.py:43-131`

### Current Logic
- Forward-fills missing points
- Linear interpolation between known points
- Skips buckets with no data if no previous/next value exists

### Potential Issues
- If data is very sparse (e.g., only 2 points in 30 days), interpolation creates a straight line
- Time zone handling might be inconsistent
- No validation of interpolated values

### Solution
- Add minimum data point requirements before interpolation
- Validate interpolated values are reasonable
- Add logging for sparse data cases

### Status
⚠️ **LOW PRIORITY** - Generally works, but edge cases exist

---

## 6. Empty Data Handling

### Problem
When no data exists, endpoints return empty arrays. Frontend handles this, but:
- Empty arrays might cause chart libraries to error
- No indication of why data is missing
- Users see "No data available" but don't know why

### Current Behavior
- Backend returns `{"points": [], "isMockData": False}`
- Frontend shows "No data available" message
- No diagnostic information provided

### Solution
- Add diagnostic endpoint (already exists: `/api/market/diagnostics`)
- Return more context in empty responses (e.g., "No data in last 7 days")
- Frontend could show helpful messages based on diagnostic data

### Status
✅ **LOW PRIORITY** - Already handled, but could be improved

---

## 7. Marketplace Filtering (FIXED)

### Problem (NOW FIXED)
Previously, ingestion tasks created snapshots with wrong marketplace structure:
- `ingestion.py` used "scryfall" marketplace
- `data_seeding.py` used "tcgplayer"/"cardmarket"/"mtgo" marketplaces
- Charts query all marketplaces, but data was inconsistent

### Status
✅ **FIXED** - All ingestion tasks now use consistent marketplace structure

---

## 8. Data Freshness Issues

### Problem
If price collection tasks stop running:
- Charts show stale data
- No indication that data is outdated
- Users might make decisions based on old prices

### Current Behavior
- Tasks run every 2-5 minutes
- No freshness checks in chart endpoints
- Frontend refreshes every 2 minutes, but doesn't validate data age

### Solution
- Add `data_freshness_minutes` to chart responses
- Frontend could show warning if data is stale
- Add health checks for task execution

### Status
⚠️ **MEDIUM PRIORITY** - Important for data reliability

---

## 9. Foil Price Handling

### Problem
Foil price filtering might exclude valid data:
- If `is_foil=True` but card has no foil price, it's excluded
- If `is_foil=False`, cards with foil prices are excluded
- Default behavior uses regular prices, which might mix foil and non-foil

### Location
- `backend/app/api/routes/market.py:590-602`
- `backend/app/api/routes/inventory.py:955-967`

### Current Logic
- `is_foil=True`: Only uses `price_foil` field
- `is_foil=False`: Only uses `price` field where `price_foil IS NULL`
- `is_foil=None`: Uses `price` field (might include cards with foil prices)

### Potential Issues
- Mixing foil and non-foil prices in default mode
- Excluding valid data when filtering
- No way to show both foil and non-foil on same chart

### Solution
- Consider adding separate foil/non-foil toggle in frontend
- Document behavior clearly
- Consider separate endpoints for foil vs non-foil

### Status
✅ **LOW PRIORITY** - Current behavior is reasonable, but could be clearer

---

## 10. Query Performance Issues

### Problem
Chart queries might be slow with large datasets:
- Time-bucketing calculations are expensive
- No indexes on `snapshot_time` or `currency` (potentially)
- Aggregations across many cards can be slow

### Potential Impact
- Timeouts (currently 25-30 seconds)
- Database connection pool exhaustion
- Slow chart loading

### Solution
- Add database indexes on `snapshot_time`, `currency`, `card_id`
- Consider materialized views for common queries
- Add query result caching
- Optimize bucket calculation

### Status
⚠️ **MEDIUM PRIORITY** - Performance issue, not functional bug

---

## Recommended Fix Priority

1. **HIGH**: Fix currency mixing issue (#1)
2. **MEDIUM**: Ensure data collection is running (#2, #8)
3. **MEDIUM**: Add database indexes (#10)
4. **LOW**: Improve backfill logic (#3)
5. **LOW**: Improve base value calculation (#4)
6. **LOW**: Improve interpolation edge cases (#5)

---

## Testing Checklist

- [ ] Test with currency=None (should default to USD or show separate currencies)
- [ ] Test with no data (should show "No data available")
- [ ] Test with sparse data (should interpolate correctly)
- [ ] Test with only USD data (should work)
- [ ] Test with only EUR data (should work)
- [ ] Test with both USD and EUR data (should show separate lines)
- [ ] Test with foil prices (should filter correctly)
- [ ] Test with inventory that has no price data (should handle gracefully)
- [ ] Test chart refresh (should update every 2 minutes)
- [ ] Test with very old data (should still work)

