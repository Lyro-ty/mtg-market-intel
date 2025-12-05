# Charting Analysis & Improvement Recommendations

## Executive Summary

This document analyzes the current charting implementation for inventory and dashboard, identifies issues causing inaccurate or choppy charts, and provides recommendations for data ingestion to improve chart reliability.

**⚠️ Constraint**: Recommendations are limited to **MTGJSON, Scryfall, and CardTrader** - no access to other marketplace APIs (TCGPlayer Direct API, Cardmarket API, etc.) at this time.

**✅ New Addition**: CardTrader API is now available as an additional data source.

### Key Recommendations

1. **⭐ NEW: CardTrader API Integration** (High Priority)
   - Integrate CardTrader marketplace API for European market data
   - Provides market depth (multiple listings per card)
   - Potential transaction history from orders
   - Excellent rate limits (200 req/10s)
   - **Impact**: Adds EUR market coverage and market depth data

2. **⭐ Highest Priority: Scryfall Bulk Data Integration**
   - Download Scryfall bulk data files daily (free, no API key)
   - Extract historical prices from bulk files
   - Significantly improves historical data coverage
   - **Impact**: Dramatically better charts with minimal implementation

3. **Immediate Fixes (No New Data Sources)**
   - Implement interpolation to fill data gaps
   - Improve normalization strategy
   - Separate marketplace data aggregation
   - Remove synthetic backfilling
   - **Impact**: Immediate improvement to chart smoothness

4. **Enhanced MTGJSON Usage**
   - Better parsing of historical data
   - Extract all available historical points
   - Process archived versions for longer history
   - **Impact**: Better utilization of existing data source

## Application Overview

The MTG Market Intelligence application is designed to:
- Track Magic: The Gathering card prices across multiple marketplaces (TCGPlayer, Cardmarket, MTGO)
- Provide inventory management with real-time valuations
- Generate buy/hold/sell recommendations based on pricing trends
- Display market-wide analytics and inventory-specific charts

**Data Sources:**
- **Scryfall API**: Current prices (updated daily, collected every 5 minutes)
- **MTGJSON**: Historical prices (weekly intervals, ~90 days back)
- **CardTrader API**: Marketplace prices and transaction data (new addition)
- **Price Snapshots**: Stored in `price_snapshots` table with timestamps

## Current Charting Architecture

### 1. Market Index Chart (`/api/market/index`)
- **Purpose**: Shows normalized aggregate of all card prices over time
- **Data Aggregation**: 
  - Time-bucketed averages from `price_snapshots`
  - Bucket sizes: 30min (7d), 1hr (30d), 4hr (90d), daily (1y)
  - Normalization: Uses median of recent 25% of points as base (100)
- **Location**: `backend/app/api/routes/market.py:237-423`

### 2. Inventory Market Index Chart (`/api/inventory/market-index`)
- **Purpose**: Shows weighted index based on user's inventory items
- **Data Aggregation**:
  - Time-bucketed prices for inventory cards only
  - Weighted by quantity owned
  - Same bucket sizes as market index
  - Normalization: Uses first point as base (100)
- **Location**: `backend/app/api/routes/inventory.py:700-866`

### 3. Frontend Chart Component
- **Library**: Recharts
- **Component**: `MarketIndexChart.tsx`
- **Features**: Range selection (7d/30d/90d/1y), auto-refresh every 2 minutes
- **Location**: `frontend/src/components/charts/MarketIndexChart.tsx`

## Identified Issues Causing Choppy/Inaccurate Charts

### Issue 1: **Sparse Historical Data**
**Problem:**
- MTGJSON only provides weekly price data (~90 days back)
- Scryfall provides daily updates but no historical data
- This creates large gaps in time-series data, especially for longer ranges (90d, 1y)

**Evidence:**
- `backend/app/tasks/data_seeding.py:260-267` - MTGJSON fetches weekly intervals
- `backend/app/services/ingestion/adapters/mtgjson.py:151-251` - Historical data is weekly

**Impact:**
- Charts show gaps where no data exists
- Line charts appear choppy with missing segments
- Normalization can be skewed by sparse data points

### Issue 2: **Synthetic Backfilled Data**
**Problem:**
- System generates deterministic synthetic prices when historical data is missing
- Uses MD5 hash-based variation (±3%) which creates artificial patterns
- Backfilled data doesn't reflect actual market movements

**Evidence:**
- `backend/app/tasks/data_seeding.py:340-395` - Backfilling logic with hash-based variation
- `backend/app/api/routes/cards.py:817-848` - Similar backfilling in card refresh

**Impact:**
- Charts show artificial price movements that don't represent real market data
- Users can't distinguish between real and synthetic data
- ML training data becomes contaminated with fake patterns

### Issue 3: **Inconsistent Data Collection Intervals**
**Problem:**
- Mixing daily (Scryfall) and weekly (MTGJSON) data sources
- Different marketplaces may have different update frequencies
- No interpolation between data points

**Evidence:**
- Scryfall: Daily updates (collected every 5 minutes)
- MTGJSON: Weekly intervals
- No interpolation logic found in aggregation queries

**Impact:**
- Uneven data density across time ranges
- Charts appear choppy when switching between data sources
- Normalization base can shift when data sources change

### Issue 4: **Normalization Base Selection Issues**
**Problem:**
- Market index uses median of recent 25% of points as base
- Inventory index uses first point as base
- Both approaches can cause jumps when new data arrives or data quality changes

**Evidence:**
- `backend/app/api/routes/market.py:391-399` - Median of recent 25%
- `backend/app/api/routes/inventory.py:800-804` - First point as base

**Impact:**
- Index values can jump when normalization base changes
- Charts show sudden shifts that don't reflect actual price movements
- Inconsistent behavior between market and inventory charts

### Issue 5: **No Interpolation for Missing Data**
**Problem:**
- When a time bucket has no data, it's simply omitted
- No forward-fill or interpolation between known points
- Creates gaps in chart lines

**Evidence:**
- `backend/app/api/routes/market.py:401-417` - Only processes rows with data
- `backend/app/api/routes/inventory.py:795-809` - Only adds points when data exists

**Impact:**
- Charts have visible gaps
- Line charts appear broken or disconnected
- Users can't see smooth trends

### Issue 6: **Marketplace Mixing Without Normalization**
**Problem:**
- Different marketplaces (TCGPlayer USD, Cardmarket EUR) have different price levels
- Aggregating across marketplaces without currency conversion or normalization
- Can skew averages when marketplace mix changes over time

**Evidence:**
- `backend/app/api/routes/market.py:273-285` - Aggregates all marketplaces together
- No currency conversion or marketplace weighting

**Impact:**
- Index values can shift when marketplace data availability changes
- Charts don't accurately represent market movements
- Currency differences create noise

**CardTrader Impact**: 
- ✅ Adds EUR market data (complements existing USD data)
- ✅ Provides market depth (multiple listings) for better price reliability
- ✅ Can help separate marketplace data more effectively
- ⚠️ Still requires proper currency conversion and marketplace weighting

### Issue 7: **Bucket Size Mismatches**
**Problem:**
- Bucket sizes don't align with actual data collection frequency
- 30-minute buckets for 7d range, but data may only be available daily or weekly
- Creates empty buckets that are skipped

**Evidence:**
- `backend/app/api/routes/market.py:251-262` - Bucket sizes defined
- `backend/app/api/routes/market.py:273-285` - Query groups by bucket but may have no data

**Impact:**
- Many empty buckets for longer ranges
- Charts appear sparse even with data
- Wasted computation on empty aggregations

## Recommended Data Sources for Better Charting (MTGJSON, Scryfall & CardTrader)

### 1. **Scryfall Bulk Data Files** ⭐ **HIGHEST PRIORITY**

#### What It Is
- Scryfall provides bulk data downloads (free, no API key required)
- Updated daily with complete card database including price history
- Available at: `https://scryfall.com/docs/api/bulk-data`

#### Benefits
- **Historical Price Data**: Bulk files contain price history going back further than API
- **Daily Updates**: More frequent than MTGJSON's weekly intervals
- **Complete Coverage**: All cards in one download
- **Free**: No API key or rate limits for bulk downloads
- **Structured Format**: JSON files ready for parsing

#### Implementation Strategy
1. **Download Bulk Files Daily**: 
   - `default_cards.json` - Current card data with prices
   - `all_cards.json` - Complete card database
   - Check `bulk-data.json` endpoint for available files

2. **Extract Historical Prices**:
   - Scryfall bulk data includes `prices` object with historical data
   - Can extract daily/weekly price points from bulk files
   - Store as price snapshots with proper timestamps

3. **Combine with Current API Data**:
   - Use bulk data for historical backfill
   - Use API for real-time updates (current collection)
   - Merge seamlessly in database

#### Data Quality: ⭐⭐⭐⭐ (Very Good - Best option with current constraints)

### 2. **Enhanced MTGJSON Usage**

#### Current Usage
- Currently using `AllPrintings.json` for weekly historical data
- Limited to ~90 days of history

#### Improvements Available

##### Option A: MTGJSON AllPrices.json (If Available)
- **What**: Separate price-only file from MTGJSON
- **Benefits**: 
  - May have more frequent updates
  - Smaller file size (price data only)
  - Easier to parse
- **Limitation**: Still likely weekly intervals
- **Check**: Verify if this file exists in MTGJSON releases

##### Option B: Enhanced AllPrintings Parsing
- **What**: Better extraction of historical price data
- **Benefits**:
  - Extract all available historical points (not just last 90 days)
  - Parse multiple marketplace prices (TCGPlayer, Cardmarket)
  - Store with proper timestamps
- **Implementation**: Enhanced parsing in `MTGJSONAdapter`

##### Option C: MTGJSON Version History
- **What**: Download older versions of AllPrintings.json
- **Benefits**:
  - Can reconstruct longer price history
  - Build historical database from archived versions
  - Extend beyond 90-day limit
- **Limitation**: Requires storing/processing multiple file versions

#### Data Quality: ⭐⭐⭐ (Good - Works with what we have)

### 3. **CardTrader API Integration** ⭐ **NEW DATA SOURCE**

#### Overview
- **What**: CardTrader marketplace API for current prices and transaction data
- **API Base**: `https://api.cardtrader.com/api/v2`
- **Authentication**: Bearer token (API key required)
- **Rate Limit**: 200 requests per 10 seconds (excellent rate limit)
- **Documentation**: [CardTrader API Reference](https://www.cardtrader.com/docs/api/full/reference)

#### Available Endpoints for Price Data

##### Marketplace Products (`GET /marketplace/products`)
- **What**: Lists products available on CardTrader marketplace
- **Benefits**:
  - Current marketplace prices
  - Product listings with quantities
  - Multiple sellers (market depth)
- **Data Available**:
  - Product prices (seller_price with cents and currency)
  - Product quantities
  - Blueprint IDs (links to cards)
  - Expansion information
- **Use Case**: Current market prices, market depth analysis

##### Blueprints (`GET /blueprints/export`)
- **What**: Card/item definitions that can be sold
- **Benefits**:
  - Links products to specific card printings
  - Expansion information
  - Properties (condition, language, foil, etc.)
- **Use Case**: Card identification and matching

##### Orders (`GET /orders`)
- **What**: Transaction history (if accessible)
- **Benefits**:
  - Historical transaction prices
  - Actual sale prices (not just listings)
  - Transaction timestamps
- **Limitation**: May only show your own orders (not all marketplace transactions)
- **Use Case**: Historical price data from actual sales

#### Implementation Strategy

**Step 1: Marketplace Price Collection**
```python
async def collect_cardtrader_prices(card_id: int, db: AsyncSession):
    """
    Collect current marketplace prices from CardTrader.
    
    Strategy:
    1. Get blueprint ID for card (via expansion + card name)
    2. Query marketplace products for that blueprint
    3. Extract prices from product listings
    4. Store as price snapshots
    """
    # Get card info
    card = await db.get(Card, card_id)
    
    # Find blueprint ID (may need expansion mapping)
    blueprint_id = await find_cardtrader_blueprint(
        card.name, card.set_code, db
    )
    
    # Query marketplace products
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.cardtrader.com/api/v2/marketplace/products",
            headers={"Authorization": f"Bearer {CARDTRADER_TOKEN}"},
            params={"blueprint_id": blueprint_id}
        )
        products = response.json()
    
    # Extract prices
    prices = []
    for product in products:
        if product.get('seller_price'):
            price_cents = product['seller_price']['cents']
            currency = product['seller_price']['currency']
            price = price_cents / 100.0
            
            prices.append({
                'price': price,
                'currency': currency,
                'quantity': product.get('quantity', 1),
                'timestamp': datetime.utcnow()
            })
    
    # Store as price snapshots
    # Calculate average, min, max from listings
    if prices:
        avg_price = sum(p['price'] for p in prices) / len(prices)
        min_price = min(p['price'] for p in prices)
        max_price = max(p['price'] for p in prices)
        
        # Create snapshot
        snapshot = PriceSnapshot(
            card_id=card_id,
            marketplace_id=cardtrader_marketplace.id,
            snapshot_time=datetime.utcnow(),
            price=avg_price,
            currency=currency,
            min_price=min_price,
            max_price=max_price,
            num_listings=len(prices),
            total_quantity=sum(p['quantity'] for p in prices)
        )
        db.add(snapshot)
```

**Step 2: Historical Data from Orders** (If Available)
```python
async def collect_cardtrader_order_prices(db: AsyncSession):
    """
    Collect historical prices from CardTrader orders.
    
    Note: This may only show your own orders or orders you have access to.
    Still valuable for building price history over time.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.cardtrader.com/api/v2/orders",
            headers={"Authorization": f"Bearer {CARDTRADER_TOKEN}"},
            params={"limit": 100}  # Get recent orders
        )
        orders = response.json()
    
    # Extract transaction prices from order items
    for order in orders:
        if order.get('order_items'):
            for item in order['order_items']:
                blueprint_id = item.get('blueprint_id')
                transaction_price = item.get('seller_price', {}).get('cents', 0) / 100.0
                transaction_date = parse_datetime(order.get('paid_at'))
                
                # Find card by blueprint
                card = await find_card_by_blueprint(blueprint_id, db)
                if card:
                    # Store as historical price snapshot
                    snapshot = PriceSnapshot(
                        card_id=card.id,
                        marketplace_id=cardtrader_marketplace.id,
                        snapshot_time=transaction_date,
                        price=transaction_price,
                        currency=item.get('seller_price', {}).get('currency', 'EUR'),
                        # Mark as transaction data (not listing)
                    )
                    db.add(snapshot)
```

**Step 3: Blueprint Mapping**
```python
async def build_blueprint_mapping(db: AsyncSession):
    """
    Build mapping between cards and CardTrader blueprints.
    
    Strategy:
    1. Get all expansions from CardTrader
    2. Match to our set codes
    3. Get blueprints for each expansion
    4. Match blueprints to cards by name + set
    """
    # Get CardTrader expansions
    expansions = await get_cardtrader_expansions()
    
    # Match to our sets
    for ct_expansion in expansions:
        our_set = await find_set_by_code(ct_expansion['code'], db)
        if our_set:
            # Get blueprints for this expansion
            blueprints = await get_blueprints_for_expansion(ct_expansion['id'])
            
            # Match blueprints to cards
            for blueprint in blueprints:
                card = await find_card_by_name_and_set(
                    blueprint['name'], our_set.code, db
                )
                if card:
                    # Store mapping
                    store_blueprint_mapping(card.id, blueprint['id'], db)
```

#### Benefits of CardTrader Integration

1. **✅ Additional Marketplace Data**
   - European market focus (EUR prices)
   - Complements Scryfall's TCGPlayer (USD) data
   - More marketplace coverage = better price aggregation

2. **✅ Market Depth Information**
   - Multiple seller listings per card
   - Can calculate min/max/avg from listings
   - Better price reliability indicators

3. **✅ Potential Historical Data**
   - Order transaction prices (if accessible)
   - Can build price history over time
   - Real transaction data (not just listings)

4. **✅ Good Rate Limits**
   - 200 requests per 10 seconds
   - Allows frequent data collection
   - Better than many other APIs

#### Limitations

1. **⚠️ Blueprint Matching Required**
   - Need to map cards to CardTrader blueprints
   - May require manual mapping for some cards
   - Expansion codes may differ

2. **⚠️ Historical Data Availability**
   - Orders may only show your own transactions
   - May not have access to all marketplace history
   - Need to build history over time

3. **⚠️ API Key Required**
   - Requires CardTrader account and API token
   - Need to manage authentication

#### Data Quality: ⭐⭐⭐⭐ (Very Good - Excellent addition)

**Impact on Charting:**
- ✅ More marketplace coverage = better price aggregation
- ✅ Market depth data = more reliable prices
- ✅ EUR market data = international price comparison
- ✅ Potential transaction history = historical data source

### 4. **Maximize Scryfall API Usage**

#### Current Usage
- Collecting current prices every 5 minutes
- Inventory cards every 2 minutes

#### Improvements

##### Option A: Scryfall Price History Endpoint
- **What**: Check if Scryfall API has price history endpoints
- **Benefits**: 
  - Direct historical data from API
  - No need to parse bulk files
  - Real-time access
- **Check**: Review Scryfall API docs for `/cards/{id}/prices` or similar

##### Option B: Scryfall Card Objects
- **What**: Card objects include `prices` with `usd`, `usd_foil`, `eur`, etc.
- **Benefits**:
  - Multiple marketplace prices in one call
  - Historical data may be embedded
  - Better than current single-price approach
- **Implementation**: Extract all price fields from card objects

#### Data Quality: ⭐⭐⭐⭐ (Very Good - Maximize current source)

### 4. **Additional Context Data (From Scryfall)**

#### Set Release Dates & Rotation Dates
- **What**: Standard rotation dates, set release dates
- **Benefits**:
  - Can identify price jumps due to format changes
  - Better trend analysis
  - Context for price movements
- **Sources**: Scryfall API (already available in card data)
- **Implementation**: Extract from `released_at`, `legalities` fields
- **Impact**: Better chart interpretation and ML features

#### Card Metadata for Better Aggregation
- **What**: Rarity, set, format legality
- **Benefits**:
  - Can create sub-indices (e.g., "Rare cards index")
  - Filter by format for more relevant comparisons
  - Weight by rarity for better market representation
- **Sources**: Scryfall API (already available)
- **Impact**: More accurate and relevant indices

## Recommended Improvements

### 1. **Implement Data Interpolation**

**Approach**: Forward-fill or linear interpolation for missing time buckets

```python
# Pseudo-code for interpolation
def interpolate_missing_points(points, bucket_size):
    # Fill gaps with forward-fill or linear interpolation
    # Ensure continuous time series
    filled_points = []
    for i, point in enumerate(points):
        filled_points.append(point)
        if i < len(points) - 1:
            gap = (points[i+1].timestamp - point.timestamp) / bucket_size
            if gap > 1:
                # Interpolate missing buckets
                for j in range(1, gap):
                    interpolated_value = linear_interpolate(
                        point.value, points[i+1].value, j/gap
                    )
                    filled_points.append({
                        'timestamp': point.timestamp + j * bucket_size,
                        'value': interpolated_value
                    })
    return filled_points
```

**Benefits**:
- Smooth, continuous chart lines
- No visible gaps
- Better user experience

### 2. **Improve Normalization Strategy**

**Current**: Market index uses median of recent 25%, inventory uses first point

**Recommended**: Use fixed base point (e.g., 30 days ago or start of range)

```python
# Use consistent base point
base_date = start_date  # Or start_date + 30 days for stability
base_query = select(func.avg(PriceSnapshot.price)).where(
    PriceSnapshot.snapshot_time >= base_date,
    PriceSnapshot.snapshot_time < base_date + timedelta(days=1)
)
base_value = await db.scalar(base_query)
```

**Benefits**:
- Consistent normalization across refreshes
- No jumps when new data arrives
- Predictable index behavior

### 3. **Separate Charts by Currency (EUR/USD)** ⭐ **USER REQUESTED**

**Approach**: Create separate chart endpoints and queries filtered by currency

**Implementation Strategy:**

#### Option A: Currency Parameter in Existing Endpoints (Recommended)
```python
@router.get("/index")
async def get_market_index(
    range: str = Query("7d", regex="^(7d|30d|90d|1y)$"),
    currency: str = Query(None, regex="^(USD|EUR)$"),  # NEW: Filter by currency
    db: AsyncSession = Depends(get_db),
):
    """
    Get market index data, optionally filtered by currency.
    
    If currency is specified, only returns data for that currency.
    If not specified, returns aggregated data (current behavior).
    """
    # ... existing bucket logic ...
    
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
    
    # ... rest of logic ...
    
    return {
        "range": range,
        "currency": currency or "ALL",  # Indicate which currency
        "points": points,
        "isMockData": False,
    }
```

#### Option B: Separate Endpoints for Each Currency
```python
@router.get("/index/usd")
async def get_market_index_usd(...):
    """USD-specific market index."""
    return await get_market_index(range=range, currency="USD", db=db)

@router.get("/index/eur")
async def get_market_index_eur(...):
    """EUR-specific market index."""
    return await get_market_index(range=range, currency="EUR", db=db)
```

#### Option C: Return Both Currencies in Single Response (Best for Comparison)
```python
@router.get("/index")
async def get_market_index(
    range: str = Query("7d", regex="^(7d|30d|90d|1y)$"),
    separate_currencies: bool = Query(False),  # NEW: Return separate currency data
    db: AsyncSession = Depends(get_db),
):
    """
    Get market index data.
    
    If separate_currencies=True, returns separate indices for USD and EUR.
    If False, returns aggregated index (current behavior).
    """
    if separate_currencies:
        # Get USD index
        usd_points = await _get_currency_index("USD", range, db)
        
        # Get EUR index
        eur_points = await _get_currency_index("EUR", range, db)
        
        return {
            "range": range,
            "currencies": {
                "USD": {
                    "points": usd_points,
                    "currency": "USD",
                },
                "EUR": {
                    "points": eur_points,
                    "currency": "EUR",
                }
            },
            "isMockData": False,
        }
    else:
        # Current aggregated behavior
        # ... existing logic ...
```

**Helper Function:**
```python
async def _get_currency_index(
    currency: str,
    range: str,
    db: AsyncSession
) -> list[dict]:
    """Get index points for a specific currency."""
    # ... bucket logic ...
    
    query = select(
        bucket_expr.label("bucket_time"),
        func.avg(PriceSnapshot.price).label("avg_price"),
    ).where(
        PriceSnapshot.snapshot_time >= start_date,
        PriceSnapshot.currency == currency,  # Filter by currency
        PriceSnapshot.price.isnot(None),
        PriceSnapshot.price > 0,
    ).group_by(bucket_expr).order_by(bucket_expr)
    
    # ... normalization logic ...
    return points
```

**Frontend Implementation:**
```typescript
// MarketIndexChart.tsx - Add currency toggle
const [selectedCurrency, setSelectedCurrency] = useState<'ALL' | 'USD' | 'EUR'>('ALL');

// Fetch data with currency filter
const { data: marketIndex } = useQuery({
  queryKey: ['market-index', marketIndexRange, selectedCurrency],
  queryFn: () => getMarketIndex(marketIndexRange, selectedCurrency),
});

// Display separate lines or toggle
{selectedCurrency === 'ALL' ? (
  // Show aggregated line
) : (
  // Show currency-specific line
)}
```

**Benefits**:
- ✅ **Currency Clarity**: No mixing USD and EUR prices
- ✅ **Regional Insights**: See US vs European market trends
- ✅ **Accurate Comparisons**: Compare markets in their native currencies
- ✅ **No Conversion Needed**: Each currency chart uses its own base
- ✅ **Better Trading Decisions**: See which market offers better prices

**For Inventory Charts:**
```python
@router.get("/market-index")
async def get_inventory_market_index(
    current_user: CurrentUser,
    range: str = Query("7d", regex="^(7d|30d|90d|1y)$"),
    currency: str = Query(None, regex="^(USD|EUR)$"),  # NEW
    db: AsyncSession = Depends(get_db),
):
    # ... existing logic ...
    
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
    
    # ... rest of logic ...
```

### 4. **Separate Marketplace Data**

**Approach**: Create separate indices per marketplace, then aggregate

```python
# Calculate index per marketplace
marketplace_indices = {}
for marketplace in marketplaces:
    marketplace_data = get_bucketed_prices(marketplace_id)
    marketplace_indices[marketplace.slug] = normalize_index(marketplace_data)

# Weighted average across marketplaces
final_index = weighted_average(marketplace_indices, weights)
```

**Benefits**:
- Avoids currency mixing issues
- Can show marketplace-specific trends
- More accurate aggregation

### 4. **Implement Moving Averages**

**Approach**: Add moving average lines to smooth out volatility

```python
# Calculate 7-day and 30-day moving averages
def calculate_moving_averages(points, window):
    ma_points = []
    for i in range(len(points)):
        window_start = max(0, i - window)
        window_points = points[window_start:i+1]
        ma_value = sum(p.value for p in window_points) / len(window_points)
        ma_points.append({
            'timestamp': points[i].timestamp,
            'value': ma_value
        })
    return ma_points
```

**Benefits**:
- Smoother chart appearance
- Better trend visualization
- Reduces impact of outliers

### 5. **Data Quality Indicators**

**Approach**: Track and display data completeness

```python
# Calculate data quality score
def calculate_data_quality(points, expected_points):
    completeness = len(points) / expected_points
    freshness = (now - max(p.timestamp for p in points)).total_seconds()
    quality_score = completeness * (1 - min(freshness / 86400, 1))
    return quality_score
```

**Benefits**:
- Users know when charts are reliable
- Can flag low-quality data
- Better decision-making

### 6. **Optimize Bucket Sizes**

**Current**: Fixed buckets (30min, 1hr, 4hr, daily)

**Recommended**: Dynamic buckets based on data density

```python
# Calculate optimal bucket size based on data availability
def calculate_optimal_bucket(start_date, end_date, data_points):
    total_seconds = (end_date - start_date).total_seconds()
    optimal_bucket = total_seconds / min(data_points, 100)  # Max 100 points
    # Round to nearest reasonable interval
    return round_to_interval(optimal_bucket)
```

**Benefits**:
- Better data utilization
- Fewer empty buckets
- More consistent chart density

### 7. **Remove or Flag Synthetic Data**

**Approach**: Either remove backfilling or clearly mark synthetic data

```python
# Add flag to price snapshots
class PriceSnapshot(Base):
    is_synthetic: Mapped[bool] = mapped_column(default=False)
    
# In chart response
{
    "points": [...],
    "isMockData": False,
    "syntheticDataPoints": count_synthetic_points(points),
    "dataQuality": calculate_quality(points)
}
```

**Benefits**:
- Transparency for users
- Better ML training (can exclude synthetic)
- More accurate charts

## Implementation Priority

### High Priority (Immediate Impact)
1. ✅ **Separate charts by currency (EUR/USD)** - ⭐ **USER REQUESTED** - Fixes currency mixing
2. ✅ **Implement interpolation** - Fixes choppy charts immediately
3. ✅ **Improve normalization** - Prevents index jumps
4. ✅ **Separate marketplace data** - More accurate aggregation

### Medium Priority (Better Data Quality)
4. ✅ **Add moving averages** - Smoother visualization
5. ✅ **Optimize bucket sizes** - Better data utilization
6. ✅ **Flag synthetic data** - Transparency

### Low Priority (Enhanced Features)
7. ✅ **Data quality indicators** - User awareness
8. ✅ **Enhanced historical sources** - Better long-term data

## Data Ingestion Recommendations (MTGJSON, Scryfall & CardTrader)

### Immediate Improvements (No New Sources Required)

1. **Maximize Scryfall API Usage**
   - ✅ Already collecting inventory cards every 2min (good)
   - ✅ Collecting all cards every 5min (good)
   - **Enhancement**: Extract all price fields (usd, usd_foil, eur, eur_foil, tix) from card objects
   - **Enhancement**: Check for any historical price endpoints in Scryfall API

2. **Remove or Reduce Synthetic Backfilling**
   - Replace hash-based backfilling with interpolation
   - Use forward-fill or linear interpolation for gaps
   - Mark any remaining synthetic data clearly

3. **Implement Forward-Fill for Missing Buckets**
   - Fill gaps with last known value (forward-fill)
   - Or use linear interpolation between known points
   - Ensures continuous chart lines

4. **Add Data Quality Tracking**
   - Track data completeness per card
   - Identify gaps in historical data
   - Display quality indicators to users

### High-Priority Data Source Improvements

1. **⭐ CardTrader API Integration** (New High-Impact Addition)

#### Overview
- **What**: Integrate CardTrader marketplace API for prices
- **Benefits**: 
  - Additional marketplace (EUR market focus)
  - Market depth data (multiple listings per card)
  - Potential transaction history from orders
  - Excellent rate limits (200 req/10s)
- **Impact**: ⭐⭐⭐⭐ Adds European market data and market depth

#### Implementation Steps

**Step 1: Create CardTrader Adapter**
```python
# backend/app/services/ingestion/adapters/cardtrader.py
class CardTraderAdapter(MarketplaceAdapter):
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.cardtrader.com/api/v2"
        self.rate_limit = 200 / 10  # 200 requests per 10 seconds
    
    async def fetch_price(self, card_name: str, set_code: str, ...):
        # Get blueprint ID
        blueprint_id = await self._find_blueprint(card_name, set_code)
        
        # Get marketplace products
        products = await self._get_marketplace_products(blueprint_id)
        
        # Calculate prices from listings
        return self._calculate_prices_from_products(products)
```

**Step 2: Blueprint Mapping System**
- Create `cardtrader_blueprints` table to map cards to blueprint IDs
- Build initial mapping from expansions and card names
- Update mapping as new cards are added

**Step 3: Price Collection Task**
- Add CardTrader to price collection cycle
- Collect marketplace product prices (current listings)
- Extract transaction prices from orders (historical data)
- Store with proper marketplace separation

**Step 4: Integration with Existing System**
- Add CardTrader marketplace to database
- Include in price aggregation queries
- Separate EUR prices from USD prices in charts

2. **⭐ Scryfall Bulk Data Integration** (Highest Impact for Historical Data)

#### Overview
- **What**: Download and parse Scryfall bulk data files daily
- **Benefits**: 
  - Historical price data beyond API limits
  - Daily updates (better than MTGJSON weekly)
  - Complete card database with prices
  - Free, no API key required
- **Impact**: ⭐⭐⭐⭐ Significantly improves historical data coverage

#### Implementation Details

**Step 1: Bulk Data Discovery**
```python
# Scryfall bulk data endpoint
BULK_DATA_URL = "https://api.scryfall.com/bulk-data"

# Available files:
# - default_cards.json (most recent printings)
# - all_cards.json (all printings, larger file)
# - oracle_cards.json (unique cards, no printings)
```

**Step 2: Download Strategy**
```python
async def download_scryfall_bulk_data():
    # 1. Get bulk data manifest
    async with httpx.AsyncClient() as client:
        response = await client.get(BULK_DATA_URL)
        manifest = response.json()
    
    # 2. Find default_cards or all_cards file
    for file_info in manifest['data']:
        if file_info['type'] in ['default_cards', 'all_cards']:
            download_uri = file_info['download_uri']
            # Download and process
            await download_and_process_bulk_file(download_uri)
```

**Step 3: Extract Historical Prices**
```python
async def process_bulk_card(card_data: dict, db: AsyncSession):
    """
    Extract prices from Scryfall card object.
    
    Scryfall card objects contain:
    - prices.usd (current USD price)
    - prices.usd_foil (current USD foil price)
    - prices.eur (current EUR price)
    - prices.eur_foil (current EUR foil price)
    - prices.tix (current MTGO price)
    - And potentially historical data in price_objects
    """
    card_id = get_or_create_card(card_data, db)
    
    # Extract current prices
    prices = card_data.get('prices', {})
    
    # Map to marketplaces
    marketplace_map = {
        'usd': ('tcgplayer', 'TCGPlayer'),
        'eur': ('cardmarket', 'Cardmarket'),
        'tix': ('mtgo', 'MTGO'),
    }
    
    for price_key, (slug, name) in marketplace_map.items():
        price_value = prices.get(price_key)
        if price_value and float(price_value) > 0:
            # Create price snapshot with bulk data timestamp
            snapshot_time = parse_scryfall_timestamp(card_data.get('updated_at'))
            create_price_snapshot(card_id, slug, price_value, snapshot_time, db)
```

**Step 4: Historical Data Extraction**
```python
# Check if Scryfall bulk data includes historical prices
# If available, extract from price_objects or similar fields
# Otherwise, use bulk data timestamps to build history over time
# by comparing daily downloads

async def build_price_history_from_bulk_downloads():
    """
    Strategy: Download bulk data daily and compare prices.
    This builds historical price data over time.
    """
    # Store daily snapshots from bulk downloads
    # Compare prices day-over-day to build history
    # More reliable than synthetic backfilling
```

**Step 5: Celery Task Integration**
```python
@shared_task(bind=True, max_retries=3)
def download_scryfall_bulk_data_task(self):
    """
    Daily task to download and process Scryfall bulk data.
    Runs after comprehensive seeding to fill historical gaps.
    """
    return run_async(_download_scryfall_bulk_data_async())

# Schedule in celery_app.py:
# 'download-scryfall-bulk': {
#     'task': 'app.tasks.data_seeding.download_scryfall_bulk_data_task',
#     'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
# }
```

**Step 6: Storage Strategy**
- Store bulk data snapshots with `source='scryfall_bulk'` flag
- Use bulk data for historical backfill (replace synthetic data)
- Merge with API data (API for real-time, bulk for history)
- Track data freshness per card

**Benefits of This Approach:**
1. ✅ No API rate limits (bulk download, not API calls)
2. ✅ Complete historical data (all cards in one file)
3. ✅ Daily updates (better than MTGJSON weekly)
4. ✅ Free (no API key required)
5. ✅ Reliable (official Scryfall data)

2. **Enhanced MTGJSON Parsing**
   - **What**: Better extraction of historical data from AllPrintings.json
   - **Benefits**:
     - Extract all available historical points (not just 90 days)
     - Parse multiple marketplace prices separately
     - Better timestamp handling
   - **Implementation**:
     - Enhance `MTGJSONAdapter.fetch_price_history()`
     - Extract all date keys from price objects
     - Store with proper marketplace separation
   - **Impact**: ⭐⭐⭐ Better utilization of existing data

3. **MTGJSON Version History**
   - **What**: Download and process older AllPrintings.json versions
   - **Benefits**:
     - Reconstruct longer price history
     - Build historical database from archives
     - Extend beyond 90-day limit
   - **Implementation**:
     - Download archived versions from MTGJSON releases
     - Process and merge historical data
     - Store with version metadata
   - **Impact**: ⭐⭐⭐ Extends historical coverage

### Context Data Enhancements (From Existing Sources)

1. **Set Release Dates & Rotation Dates** (From Scryfall)
   - Extract `released_at` and `legalities` from Scryfall card data
   - Use for better chart interpretation
   - Context for price movements
   - **Impact**: Better understanding of price trends

2. **Card Metadata for Better Aggregation** (From Scryfall)
   - Use rarity, set, format legality for sub-indices
   - Filter by format for relevant comparisons
   - Weight by rarity for market representation
   - **Impact**: More accurate and relevant indices

### Training Data Enhancements (Using Available Data)

1. **Price Spread Analysis** (From Scryfall)
   - Compare USD vs EUR prices (marketplace differences)
   - Compare normal vs foil prices
   - Use as features for ML models
   - **Impact**: Better price prediction features

2. **Format Legality Trends** (From Scryfall)
   - Track when cards become legal/banned in formats
   - Correlate with price movements
   - Use as ML features
   - **Impact**: Better understanding of price drivers

3. **Set Release Context** (From Scryfall)
   - Days since set release
   - Standard rotation proximity
   - Use as temporal features
   - **Impact**: Better time-series modeling

## Conclusion

The current charting issues stem from:
1. **Sparse historical data** (weekly MTGJSON + daily Scryfall gaps)
2. **Synthetic backfilled data** creating artificial patterns
3. **No interpolation** leaving gaps in charts
4. **Inconsistent normalization** causing index jumps
5. **Marketplace mixing** without proper handling

### Immediate Fixes (No New Data Sources Required)
These can be implemented immediately and will significantly improve chart quality:
1. ✅ **Implement interpolation** - Fill gaps with forward-fill or linear interpolation
2. ✅ **Improve normalization** - Use fixed base point for consistency
3. ✅ **Separate marketplace data** - Aggregate per marketplace, then combine
4. ✅ **Remove synthetic backfilling** - Replace with interpolation
5. ✅ **Add moving averages** - Smooth out volatility

### High-Impact Data Improvements (Using Only MTGJSON & Scryfall)
1. ⭐ **Scryfall Bulk Data Integration** - Highest priority
   - Download bulk data files daily
   - Extract historical prices from bulk files
   - Significantly extends historical coverage
   - Free, no API key required

2. **Enhanced MTGJSON Parsing** - Better utilization
   - Extract all available historical points
   - Parse multiple marketplaces separately
   - Better timestamp handling

3. **MTGJSON Version History** - Extend coverage
   - Process archived versions
   - Reconstruct longer price history
   - Build comprehensive historical database

### Key Insights

1. **CardTrader API is a valuable addition** - Provides European market data (EUR), market depth information, and potential transaction history. Excellent rate limits make it practical for frequent collection.

2. **Scryfall Bulk Data is the historical game-changer** - Provides historical price data that the API doesn't expose, is updated daily, and is completely free. This single addition would dramatically improve chart quality without requiring any new API keys or paid services.

3. **Three-source strategy** - Combining CardTrader (EUR market + depth), Scryfall API (USD market + real-time), and Scryfall Bulk (historical) provides comprehensive coverage.

### Implementation Roadmap

**Phase 1: Immediate Fixes (Week 1)**
- ⭐ **Separate charts by currency (EUR/USD)** - USER REQUESTED
- Implement interpolation and normalization fixes (immediate impact)
- Remove synthetic backfilling
- Add marketplace separation in aggregation

**Phase 2: CardTrader Integration (Week 2)**
- Create CardTrader adapter
- Build blueprint mapping system
- Integrate marketplace price collection
- Add to price collection cycle

**Phase 3: Scryfall Bulk Data (Week 3)**
- Integrate Scryfall bulk data download and parsing
- Extract historical prices from bulk files
- Replace synthetic data with real historical data

**Phase 4: Enhanced Data Sources (Week 4)**
- Enhance MTGJSON parsing and add version history support
- Optimize CardTrader order data collection (if available)
- Add moving averages, data quality indicators

**Phase 5: Chart Improvements (Week 5)**
- Implement interpolation in chart endpoints
- Add marketplace-specific indices
- Improve normalization strategy
- Add data quality indicators to frontend

This approach maximizes chart quality improvements using three data sources:
- **CardTrader**: European market + market depth
- **Scryfall API**: USD market + real-time updates
- **Scryfall Bulk**: Historical data
- **MTGJSON**: Additional historical coverage

