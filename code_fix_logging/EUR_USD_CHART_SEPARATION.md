# EUR/USD Chart Separation Implementation Guide

## Overview

This guide shows how to implement separate charts for USD and EUR pricing data, addressing the currency mixing issue in current charts.

## Current Problem

The current implementation aggregates all currencies together:
- TCGPlayer prices (USD)
- Cardmarket prices (EUR) 
- CardTrader prices (EUR)

This creates inaccurate charts because:
1. USD and EUR prices are at different scales
2. Exchange rate fluctuations affect the index
3. Regional market differences are hidden

## Solution: Currency-Based Chart Separation

### Implementation Approach

**Recommended**: Add `currency` query parameter to existing endpoints, with option to return both currencies.

### Step 1: Update Market Index Endpoint

**File**: `backend/app/api/routes/market.py`

```python
@router.get("/index")
async def get_market_index(
    range: str = Query("7d", regex="^(7d|30d|90d|1y)$"),
    currency: str = Query(None, regex="^(USD|EUR)$"),  # NEW parameter
    separate_currencies: bool = Query(False),  # NEW: Return both currencies
    db: AsyncSession = Depends(get_db),
):
    """
    Get market index data for charting.
    
    Args:
        range: Time range (7d, 30d, 90d, 1y)
        currency: Filter by currency (USD or EUR). If None, aggregates all.
        separate_currencies: If True, returns separate indices for USD and EUR.
    """
    # Determine date range and bucket size (existing logic)
    now = datetime.utcnow()
    if range == "7d":
        start_date = now - timedelta(days=7)
        bucket_minutes = 30
    elif range == "30d":
        start_date = now - timedelta(days=30)
        bucket_minutes = 60
    elif range == "90d":
        start_date = now - timedelta(days=90)
        bucket_minutes = 240
    else:  # 1y
        start_date = now - timedelta(days=365)
        bucket_minutes = 1440
    
    bucket_seconds = bucket_minutes * 60
    bucket_expr = func.to_timestamp(
        func.floor(func.extract('epoch', PriceSnapshot.snapshot_time) / bucket_seconds) * bucket_seconds
    )
    
    # NEW: Handle separate currencies
    if separate_currencies:
        usd_points = await _get_currency_index("USD", start_date, bucket_expr, db)
        eur_points = await _get_currency_index("EUR", start_date, bucket_expr, db)
        
        return {
            "range": range,
            "separate_currencies": True,
            "currencies": {
                "USD": {
                    "currency": "USD",
                    "points": usd_points,
                    "isMockData": False,
                },
                "EUR": {
                    "currency": "EUR",
                    "points": eur_points,
                    "isMockData": False,
                }
            }
        }
    
    # Existing aggregated logic (or filtered by currency)
    query = select(
        bucket_expr.label("bucket_time"),
        func.avg(PriceSnapshot.price).label("avg_price"),
        func.count(func.distinct(PriceSnapshot.card_id)).label("card_count"),
    ).where(
        PriceSnapshot.snapshot_time >= start_date,
        PriceSnapshot.price.isnot(None),
        PriceSnapshot.price > 0,
    )
    
    # NEW: Filter by currency if specified
    if currency:
        query = query.where(PriceSnapshot.currency == currency)
    
    query = query.group_by(bucket_expr).order_by(bucket_expr)
    
    # ... rest of existing logic for normalization ...
    
    return {
        "range": range,
        "currency": currency or "ALL",
        "points": points,
        "isMockData": False,
    }


async def _get_currency_index(
    currency: str,
    start_date: datetime,
    bucket_expr,
    db: AsyncSession
) -> list[dict]:
    """
    Helper function to get index points for a specific currency.
    """
    query = select(
        bucket_expr.label("bucket_time"),
        func.avg(PriceSnapshot.price).label("avg_price"),
        func.count(func.distinct(PriceSnapshot.card_id)).label("card_count"),
    ).where(
        PriceSnapshot.snapshot_time >= start_date,
        PriceSnapshot.currency == currency,  # Filter by currency
        PriceSnapshot.price.isnot(None),
        PriceSnapshot.price > 0,
    ).group_by(bucket_expr).order_by(bucket_expr)
    
    try:
        result = await asyncio.wait_for(
            db.execute(query),
            timeout=QUERY_TIMEOUT
        )
        rows = result.all()
    except Exception as e:
        logger.error(f"Error fetching {currency} index", error=str(e))
        return []
    
    if not rows:
        return []
    
    # Normalize to base 100
    avg_prices = [float(row.avg_price) for row in rows if row.avg_price]
    if not avg_prices:
        return []
    
    # Use median of recent 25% as base
    recent_count = max(1, len(avg_prices) // 4)
    recent_prices = sorted(avg_prices[-recent_count:])
    base_value = recent_prices[len(recent_prices) // 2] if recent_prices else avg_prices[0]
    
    if not base_value or base_value <= 0:
        base_value = avg_prices[0]
    
    points = []
    for row in rows:
        if row.avg_price:
            index_value = (float(row.avg_price) / base_value) * 100.0
            
            bucket_dt = row.bucket_time
            if isinstance(bucket_dt, datetime):
                timestamp_str = bucket_dt.isoformat()
            else:
                timestamp_str = str(bucket_dt)
            
            points.append({
                "timestamp": timestamp_str,
                "indexValue": round(index_value, 2),
            })
    
    return points
```

### Step 2: Update Inventory Market Index Endpoint

**File**: `backend/app/api/routes/inventory.py`

```python
@router.get("/market-index")
async def get_inventory_market_index(
    current_user: CurrentUser,
    range: str = Query("7d", regex="^(7d|30d|90d|1y)$"),
    currency: str = Query(None, regex="^(USD|EUR)$"),  # NEW parameter
    separate_currencies: bool = Query(False),  # NEW
    db: AsyncSession = Depends(get_db),
):
    """
    Get market index data for user's inventory items.
    
    Args:
        range: Time range
        currency: Filter by currency (USD or EUR)
        separate_currencies: Return separate indices for USD and EUR
    """
    # ... existing date range logic ...
    
    # Get user's inventory items
    inventory_query = select(InventoryItem.card_id, InventoryItem.quantity).where(
        InventoryItem.user_id == current_user.id
    )
    inventory_result = await db.execute(inventory_query)
    inventory_items = inventory_result.all()
    
    if not inventory_items:
        return {
            "range": range,
            "points": [],
            "isMockData": False,
        }
    
    card_ids = [item.card_id for item in inventory_items]
    quantity_map = {item.card_id: item.quantity for item in inventory_items}
    
    # NEW: Handle separate currencies
    if separate_currencies:
        usd_points = await _get_inventory_currency_index(
            "USD", start_date, bucket_expr, card_ids, quantity_map, db
        )
        eur_points = await _get_inventory_currency_index(
            "EUR", start_date, bucket_expr, card_ids, quantity_map, db
        )
        
        return {
            "range": range,
            "separate_currencies": True,
            "currencies": {
                "USD": {"currency": "USD", "points": usd_points},
                "EUR": {"currency": "EUR", "points": eur_points},
            }
        }
    
    # Existing logic with currency filter
    query = select(
        bucket_expr.label("bucket_time"),
        PriceSnapshot.card_id,
        func.avg(PriceSnapshot.price).label("avg_price"),
    ).where(
        PriceSnapshot.snapshot_time >= start_date,
        PriceSnapshot.card_id.in_(card_ids),
        PriceSnapshot.price.isnot(None),
        PriceSnapshot.price > 0,
    )
    
    # NEW: Filter by currency
    if currency:
        query = query.where(PriceSnapshot.currency == currency)
    
    query = query.group_by(bucket_expr, PriceSnapshot.card_id).order_by(bucket_expr)
    
    # ... rest of existing weighted average logic ...
```

### Step 3: Update Frontend Types

**File**: `frontend/src/types/index.ts`

```typescript
export interface MarketIndex {
  range: '7d' | '30d' | '90d' | '1y';
  currency?: 'USD' | 'EUR' | 'ALL';  // NEW
  separate_currencies?: boolean;  // NEW
  points: Array<{
    timestamp: string;
    indexValue: number;
  }>;
  currencies?: {  // NEW: When separate_currencies=true
    USD: {
      currency: 'USD';
      points: Array<{
        timestamp: string;
        indexValue: number;
      }>;
    };
    EUR: {
      currency: 'EUR';
      points: Array<{
        timestamp: string;
        indexValue: number;
      }>;
    };
  };
  isMockData: boolean;
}
```

### Step 4: Update Frontend Chart Component

**File**: `frontend/src/components/charts/MarketIndexChart.tsx`

```typescript
export function MarketIndexChart({
  data,
  title = 'Global MTG Market Index',
  height = 350,
  onRangeChange,
}: MarketIndexChartProps) {
  const [selectedCurrency, setSelectedCurrency] = useState<'ALL' | 'USD' | 'EUR'>('ALL');
  const [showSeparate, setShowSeparate] = useState(false);

  // Handle separate currencies
  if (data?.separate_currencies && data.currencies) {
    const usdData = data.currencies.USD.points;
    const eurData = data.currencies.EUR.points;
    
    // Transform for multi-line chart
    const chartData = usdData.map((point, i) => ({
      date: format(new Date(point.timestamp), 'MMM d'),
      fullDate: point.timestamp,
      USD: point.indexValue,
      EUR: eurData[i]?.indexValue || null,
    }));

    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <div className="flex gap-2">
            <Button
              variant={showSeparate ? 'primary' : 'secondary'}
              onClick={() => setShowSeparate(!showSeparate)}
            >
              {showSeparate ? 'Show Combined' : 'Show Separate'}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={height}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="USD"
                stroke="#4a6cf7"
                name="USD Market"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="EUR"
                stroke="#10b981"
                name="EUR Market"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    );
  }

  // Existing single-currency or aggregated logic
  // ...
}
```

### Step 5: Update API Client

**File**: `frontend/src/lib/api.ts`

```typescript
export async function getMarketIndex(
  range: '7d' | '30d' | '90d' | '1y',
  currency?: 'USD' | 'EUR',
  separateCurrencies: boolean = false
): Promise<MarketIndex> {
  const params = new URLSearchParams({
    range,
  });
  
  if (currency) {
    params.append('currency', currency);
  }
  
  if (separateCurrencies) {
    params.append('separate_currencies', 'true');
  }
  
  const response = await fetch(`/api/market/index?${params}`);
  if (!response.ok) throw new Error('Failed to fetch market index');
  return response.json();
}
```

## Usage Examples

### Example 1: USD-Only Chart
```
GET /api/market/index?range=7d&currency=USD
```

### Example 2: EUR-Only Chart
```
GET /api/market/index?range=7d&currency=EUR
```

### Example 3: Both Currencies (Recommended)
```
GET /api/market/index?range=7d&separate_currencies=true
```

Returns:
```json
{
  "range": "7d",
  "separate_currencies": true,
  "currencies": {
    "USD": {
      "currency": "USD",
      "points": [...]
    },
    "EUR": {
      "currency": "EUR",
      "points": [...]
    }
  }
}
```

## Benefits

1. ✅ **No Currency Mixing**: USD and EUR charts are completely separate
2. ✅ **Regional Insights**: See US vs European market trends
3. ✅ **Accurate Comparisons**: Compare markets in native currencies
4. ✅ **Better Trading**: Identify arbitrage opportunities
5. ✅ **Backward Compatible**: Existing calls still work (aggregated)

## Testing

1. Test USD-only endpoint: `/api/market/index?range=7d&currency=USD`
2. Test EUR-only endpoint: `/api/market/index?range=7d&currency=EUR`
3. Test separate currencies: `/api/market/index?range=7d&separate_currencies=true`
4. Test default (aggregated): `/api/market/index?range=7d`
5. Verify frontend displays both lines correctly

## Migration Path

1. **Phase 1**: Add currency parameter (backward compatible)
2. **Phase 2**: Update frontend to use separate currencies by default
3. **Phase 3**: Deprecate aggregated endpoint (optional)

This approach maintains backward compatibility while adding the new functionality.



