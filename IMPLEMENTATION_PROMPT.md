# Comprehensive Implementation Prompt: Charting & Inventory Improvements

## Context & Application Overview

You are implementing improvements to an MTG Market Intelligence application that:
- Tracks Magic: The Gathering card prices across multiple marketplaces (TCGPlayer, Cardmarket, MTGO, CardTrader)
- Provides inventory management with real-time valuations
- Generates buy/hold/sell recommendations based on pricing trends
- Displays market-wide analytics and inventory-specific charts

**Current Tech Stack:**
- Backend: FastAPI (Python), SQLAlchemy (async), PostgreSQL
- Frontend: Next.js (React), TypeScript, Recharts
- Data Sources: Scryfall API, MTGJSON, CardTrader API
- Task Queue: Celery

**Key Models:**
- `PriceSnapshot`: Historical price data with `currency`, `price`, `price_foil`, `snapshot_time`
- `InventoryItem`: User inventory with `condition`, `is_foil`, `quantity`
- `Card`: Card metadata with `set_code`, `name`, `scryfall_id`
- `Marketplace`: Marketplace definitions

**Current Endpoints:**
- `GET /api/market/index` - Market index chart (aggregates all currencies)
- `GET /api/inventory/market-index` - Inventory-weighted index
- `GET /api/inventory` - List inventory (has basic search)
- `POST /api/inventory` - Create inventory item
- `PATCH /api/inventory/{item_id}` - Update inventory item ✅ (exists)
- `DELETE /api/inventory/{item_id}` - Delete inventory item ✅ (exists)

---

## Priority 1: Separate Charts by Currency (EUR/USD) ⭐ USER REQUESTED

### Problem
Current charts mix USD (TCGPlayer) and EUR (Cardmarket/CardTrader) prices, causing:
- Inaccurate indices (different scales)
- Hidden regional market differences
- Exchange rate noise

### Solution
Add currency filtering to chart endpoints with option to return both currencies separately.

### Implementation Tasks

#### Task 1.1: Update Market Index Endpoint
**File**: `backend/app/api/routes/market.py`

Add to `get_market_index()` function:
1. Add query parameters:
   - `currency: str = Query(None, regex="^(USD|EUR)$")` - Filter by currency
   - `separate_currencies: bool = Query(False)` - Return both currencies separately

2. Add helper function `_get_currency_index()`:
   ```python
   async def _get_currency_index(
       currency: str,
       start_date: datetime,
       bucket_expr,
       db: AsyncSession
   ) -> list[dict]:
       """Get index points for a specific currency."""
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
       
       # Execute query, normalize to base 100, return points
       # (Use same normalization logic as existing code)
   ```

3. Modify main query logic:
   - If `separate_currencies=True`: Call `_get_currency_index()` for USD and EUR, return both
   - If `currency` is specified: Add `.where(PriceSnapshot.currency == currency)` to query
   - If neither: Keep existing aggregated behavior (backward compatible)

4. Update return value to include currency info:
   ```python
   return {
       "range": range,
       "currency": currency or "ALL",
       "separate_currencies": separate_currencies,
       "points": points,  # If not separate_currencies
       "currencies": {  # If separate_currencies=True
           "USD": {"currency": "USD", "points": usd_points},
           "EUR": {"currency": "EUR", "points": eur_points},
       },
       "isMockData": False,
   }
   ```

#### Task 1.2: Update Inventory Market Index Endpoint
**File**: `backend/app/api/routes/inventory.py`

Apply same changes to `get_inventory_market_index()`:
1. Add same query parameters (`currency`, `separate_currencies`)
2. Add helper `_get_inventory_currency_index()` that filters by currency AND inventory cards
3. Apply currency filter to existing query if `currency` is specified
4. Return same structure as market index

#### Task 1.3: Update Frontend Types
**File**: `frontend/src/types/index.ts`

Update `MarketIndex` interface:
```typescript
export interface MarketIndex {
  range: '7d' | '30d' | '90d' | '1y';
  currency?: 'USD' | 'EUR' | 'ALL';
  separate_currencies?: boolean;
  points: Array<{
    timestamp: string;
    indexValue: number;
  }>;
  currencies?: {
    USD: {
      currency: 'USD';
      points: Array<{ timestamp: string; indexValue: number; }>;
    };
    EUR: {
      currency: 'EUR';
      points: Array<{ timestamp: string; indexValue: number; }>;
    };
  };
  isMockData: boolean;
}
```

#### Task 1.4: Update Frontend API Client
**File**: `frontend/src/lib/api.ts`

Update `getMarketIndex()` function:
```typescript
export async function getMarketIndex(
  range: '7d' | '30d' | '90d' | '1y',
  currency?: 'USD' | 'EUR',
  separateCurrencies: boolean = false
): Promise<MarketIndex> {
  const params = new URLSearchParams({ range });
  if (currency) params.append('currency', currency);
  if (separateCurrencies) params.append('separate_currencies', 'true');
  
  const response = await fetch(`/api/market/index?${params}`);
  if (!response.ok) throw new Error('Failed to fetch market index');
  return response.json();
}
```

#### Task 1.5: Update Frontend Chart Component
**File**: `frontend/src/components/charts/MarketIndexChart.tsx`

1. Add state for currency selection:
   ```typescript
   const [selectedCurrency, setSelectedCurrency] = useState<'ALL' | 'USD' | 'EUR'>('ALL');
   const [showSeparate, setShowSeparate] = useState(false);
   ```

2. Handle `separate_currencies` response:
   - If `data.separate_currencies && data.currencies`:
     - Transform USD and EUR points into chart data format
     - Display two lines: one for USD (blue), one for EUR (green)
     - Add toggle button to show/hide separate currencies

3. Handle single currency filter:
   - If `currency` is specified, show only that currency's line
   - Update chart title to indicate currency

4. Default behavior (backward compatible):
   - If no currency specified, show aggregated line (existing behavior)

**Testing:**
- Test `/api/market/index?range=7d&currency=USD`
- Test `/api/market/index?range=7d&currency=EUR`
- Test `/api/market/index?range=7d&separate_currencies=true`
- Test `/api/market/index?range=7d` (should work as before)
- Verify frontend displays correctly

---

## Priority 2: Implement Data Interpolation

### Problem
Charts have gaps when time buckets have no data, creating choppy/disconnected lines.

### Solution
Implement forward-fill or linear interpolation to fill missing time buckets.

### Implementation Tasks

#### Task 2.1: Create Interpolation Helper
**File**: `backend/app/api/routes/market.py` (or create `backend/app/core/charting.py`)

```python
def interpolate_missing_points(
    points: list[dict],
    start_date: datetime,
    end_date: datetime,
    bucket_minutes: int
) -> list[dict]:
    """
    Fill gaps in time series data using forward-fill or linear interpolation.
    
    Args:
        points: List of {timestamp: str, indexValue: float}
        start_date: Start of time range
        end_date: End of time range
        bucket_minutes: Bucket size in minutes
    
    Returns:
        Filled points list with no gaps
    """
    if not points:
        return []
    
    # Convert timestamps to datetime objects
    point_times = [(datetime.fromisoformat(p['timestamp']), p['indexValue']) for p in points]
    point_times.sort(key=lambda x: x[0])
    
    filled_points = []
    bucket_timedelta = timedelta(minutes=bucket_minutes)
    
    # Generate all expected buckets
    current_time = start_date
    point_idx = 0
    
    while current_time <= end_date:
        # Find closest point (before or at this time)
        while (point_idx < len(point_times) - 1 and 
               point_times[point_idx + 1][0] <= current_time):
            point_idx += 1
        
        if point_idx < len(point_times):
            point_time, point_value = point_times[point_idx]
            
            # If we have a point at or before this bucket, use it (forward-fill)
            if point_time <= current_time:
                filled_points.append({
                    'timestamp': current_time.isoformat(),
                    'indexValue': point_value
                })
            # If next point is close, interpolate
            elif point_idx < len(point_times) - 1:
                next_time, next_value = point_times[point_idx + 1]
                if next_time - current_time < bucket_timedelta * 2:
                    # Linear interpolation
                    time_diff = (current_time - point_time).total_seconds()
                    next_diff = (next_time - point_time).total_seconds()
                    if next_diff > 0:
                        ratio = time_diff / next_diff
                        interpolated = point_value + (next_value - point_value) * ratio
                        filled_points.append({
                            'timestamp': current_time.isoformat(),
                            'indexValue': round(interpolated, 2)
                        })
                else:
                    # Gap too large, use forward-fill
                    filled_points.append({
                        'timestamp': current_time.isoformat(),
                        'indexValue': point_value
                    })
            else:
                # Last point, forward-fill
                filled_points.append({
                    'timestamp': current_time.isoformat(),
                    'indexValue': point_value
                })
        else:
            # No more points, use last known value (forward-fill)
            if point_times:
                filled_points.append({
                    'timestamp': current_time.isoformat(),
                    'indexValue': point_times[-1][1]
                })
        
        current_time += bucket_timedelta
    
    return filled_points
```

#### Task 2.2: Apply Interpolation to Market Index
In `get_market_index()`, after generating points but before returning:
```python
# Apply interpolation to fill gaps
points = interpolate_missing_points(
    points,
    start_date,
    datetime.utcnow(),
    bucket_minutes
)
```

#### Task 2.3: Apply Interpolation to Inventory Index
Same approach in `get_inventory_market_index()`.

**Testing:**
- Verify charts have no gaps
- Test with sparse data (should fill gaps)
- Test with dense data (should not change)

---

## Priority 3: Improve Normalization Strategy

### Problem
- Market index uses median of recent 25% (can jump when new data arrives)
- Inventory index uses first point (inconsistent)
- Both cause index jumps that don't reflect actual price movements

### Solution
Use fixed base point (start of range or 30 days ago) for consistent normalization.

### Implementation Tasks

#### Task 3.1: Update Market Index Normalization
**File**: `backend/app/api/routes/market.py`

Replace current normalization logic:
```python
# OLD: Use median of recent 25%
recent_count = max(1, len(avg_prices) // 4)
recent_prices = sorted(avg_prices[-recent_count:])
base_value = recent_prices[len(recent_prices) // 2]

# NEW: Use fixed base point (start of range)
base_query = select(func.avg(PriceSnapshot.price)).where(
    PriceSnapshot.snapshot_time >= start_date,
    PriceSnapshot.snapshot_time < start_date + timedelta(days=1),
    PriceSnapshot.price.isnot(None),
    PriceSnapshot.price > 0,
)
if currency:
    base_query = base_query.where(PriceSnapshot.currency == currency)

base_value = await db.scalar(base_query) or avg_prices[0] if avg_prices else 100.0
```

#### Task 3.2: Update Inventory Index Normalization
**File**: `backend/app/api/routes/inventory.py`

Use same fixed base point approach instead of first point.

**Testing:**
- Verify index doesn't jump when refreshing
- Test with different ranges (should be consistent)
- Compare old vs new normalization

---

## Priority 4: Remove Synthetic Backfilling

### Problem
System generates fake prices using hash-based variation, contaminating charts and ML data.

### Solution
Remove or replace with interpolation. If keeping, clearly mark as synthetic.

### Implementation Tasks

#### Task 4.1: Remove Backfilling Logic
**Files to update:**
- `backend/app/tasks/data_seeding.py` (lines 340-395)
- `backend/app/api/routes/cards.py` (lines 817-848)

**Action**: Comment out or remove the backfilling code that generates synthetic prices.

**Alternative**: If you want to keep some backfilling:
1. Add `is_synthetic: bool` field to `PriceSnapshot` model (requires migration)
2. Mark all backfilled data with `is_synthetic=True`
3. Filter out synthetic data in chart queries: `.where(PriceSnapshot.is_synthetic == False)`

#### Task 4.2: Replace with Interpolation
Use the interpolation function (Priority 2) instead of backfilling.

**Testing:**
- Verify no synthetic data in charts
- Test with cards that have no historical data (should use interpolation)

---

## Priority 5: Enhanced Inventory Features

### Task 5.1: Export Inventory (CSV/Plain Text)
**File**: `backend/app/api/routes/inventory.py`

Add endpoint:
```python
@router.get("/export")
async def export_inventory(
    current_user: CurrentUser,
    format: str = Query("csv", regex="^(csv|txt)$"),
    db: AsyncSession = Depends(get_db),
):
    """Export user's inventory to CSV or plain text."""
    query = select(InventoryItem, Card).join(
        Card, InventoryItem.card_id == Card.id
    ).where(InventoryItem.user_id == current_user.id)
    
    result = await db.execute(query)
    items = result.all()
    
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Card Name", "Set", "Quantity", "Condition", "Foil", 
            "Language", "Acquisition Price", "Current Value", "Profit/Loss"
        ])
        for item, card in items:
            writer.writerow([
                card.name, card.set_code, item.quantity, item.condition,
                "Yes" if item.is_foil else "No", item.language,
                item.acquisition_price, item.current_value,
                item.profit_loss
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=inventory.csv"}
        )
    else:  # txt
        lines = []
        for item, card in items:
            lines.append(
                f"{item.quantity}x {card.name} [{card.set_code}] "
                f"{item.condition} {'FOIL' if item.is_foil else ''}"
            )
        return Response(
            content="\n".join(lines),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=inventory.txt"}
        )
```

### Task 5.2: Enhanced Inventory Search
**File**: `backend/app/api/routes/inventory.py`

Enhance `GET /api/inventory` endpoint:
```python
@router.get("", response_model=InventoryListResponse)
async def list_inventory(
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    set_code: Optional[str] = None,  # NEW
    condition: Optional[InventoryCondition] = None,  # NEW
    is_foil: Optional[bool] = None,  # NEW
    min_value: Optional[float] = None,  # NEW
    max_value: Optional[float] = None,  # NEW
    sort_by: str = Query("name", regex="^(name|value|quantity|date)$"),  # NEW
    sort_order: str = Query("asc", regex="^(asc|desc)$"),  # NEW
    db: AsyncSession = Depends(get_db),
):
    # Build query with filters
    query = select(InventoryItem, Card).join(
        Card, InventoryItem.card_id == Card.id
    ).where(InventoryItem.user_id == current_user.id)
    
    if search:
        query = query.where(Card.name.ilike(f"%{search}%"))
    
    if set_code:
        query = query.where(Card.set_code.ilike(f"%{set_code}%"))
    
    if condition:
        query = query.where(InventoryItem.condition == condition.value)
    
    if is_foil is not None:
        query = query.where(InventoryItem.is_foil == is_foil)
    
    if min_value:
        query = query.where(InventoryItem.current_value >= min_value)
    
    if max_value:
        query = query.where(InventoryItem.current_value <= max_value)
    
    # Add sorting
    if sort_by == "name":
        order_col = Card.name
    elif sort_by == "value":
        order_col = InventoryItem.current_value
    elif sort_by == "quantity":
        order_col = InventoryItem.quantity
    else:  # date
        order_col = InventoryItem.created_at
    
    if sort_order == "desc":
        query = query.order_by(desc(order_col))
    else:
        query = query.order_by(order_col)
    
    # Pagination and return
```

### Task 5.3: Enhanced Set Detection on Import
**File**: `backend/app/api/routes/inventory.py`

Enhance `parse_plaintext_line()` function:
```python
async def parse_plaintext_line_enhanced(line: str, db: AsyncSession) -> dict:
    """Enhanced parsing with set code validation."""
    result = {
        "quantity": 1,
        "card_name": "",
        "set_code": None,
        "condition": InventoryCondition.NEAR_MINT,
        "is_foil": False,
    }
    
    # Extract set code (existing pattern)
    set_match = re.search(r'[\(\[]([A-Z0-9]{2,6})[\)\]]', line, re.IGNORECASE)
    if set_match:
        potential_set = set_match.group(1).upper()
        
        # NEW: Validate against known sets
        set_query = select(Card.set_code).where(
            Card.set_code.ilike(f"%{potential_set}%")
        ).distinct().limit(5)
        set_result = await db.execute(set_query)
        known_sets = [row[0] for row in set_result.all()]
        
        if known_sets:
            # Use exact match if available, otherwise first match
            if potential_set in known_sets:
                result["set_code"] = potential_set
            else:
                result["set_code"] = known_sets[0]  # Best match
    
    # ... rest of parsing logic ...
    return result
```

### Task 5.4: Foil Pricing in Charts
**File**: `backend/app/api/routes/market.py` and `inventory.py`

Add foil filtering to chart queries:
```python
# Add parameter
is_foil: Optional[bool] = Query(None)

# In query
if is_foil is not None:
    # For foil prices, use price_foil field
    if is_foil:
        query = query.where(PriceSnapshot.price_foil.isnot(None))
        # Use price_foil instead of price in aggregation
        price_field = PriceSnapshot.price_foil
    else:
        query = query.where(PriceSnapshot.price_foil.is_(None))
        price_field = PriceSnapshot.price
else:
    price_field = PriceSnapshot.price

# Update aggregation to use price_field
query = select(
    bucket_expr.label("bucket_time"),
    func.avg(price_field).label("avg_price"),
    # ...
)
```

**Frontend**: Add foil/non-foil toggle to chart components.

---

## Priority 6: CardTrader API Integration

### Implementation Tasks

#### Task 6.1: Create CardTrader Adapter
**File**: `backend/app/services/ingestion/adapters/cardtrader.py`

```python
from app.services.ingestion.base import MarketplaceAdapter, CardPrice
import httpx

class CardTraderAdapter(MarketplaceAdapter):
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.cardtrader.com/api/v2"
        self.rate_limit = 200 / 10  # 200 requests per 10 seconds
        self._client = None
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """Fetch current marketplace prices from CardTrader."""
        # 1. Find blueprint ID (requires mapping)
        blueprint_id = await self._find_blueprint(card_name, set_code)
        if not blueprint_id:
            return None
        
        # 2. Get marketplace products
        products = await self._get_marketplace_products(blueprint_id)
        if not products:
            return None
        
        # 3. Calculate prices from listings
        prices = []
        for product in products:
            if product.get('seller_price'):
                price_cents = product['seller_price']['cents']
                currency = product['seller_price']['currency']
                price = price_cents / 100.0
                prices.append({'price': price, 'currency': currency})
        
        if not prices:
            return None
        
        # Calculate average, min, max
        avg_price = sum(p['price'] for p in prices) / len(prices)
        min_price = min(p['price'] for p in prices)
        max_price = max(p['price'] for p in prices)
        
        return CardPrice(
            card_name=card_name,
            set_code=set_code,
            collector_number=collector_number or "",
            price=avg_price,
            currency=prices[0]['currency'],  # Usually EUR
            price_low=min_price,
            price_high=max_price,
            num_listings=len(prices),
        )
    
    async def _find_blueprint(self, card_name: str, set_code: str) -> int | None:
        """Find CardTrader blueprint ID for a card."""
        # Implementation: Query blueprints endpoint or use cached mapping
        pass
    
    async def _get_marketplace_products(self, blueprint_id: int) -> list[dict]:
        """Get marketplace products for a blueprint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/marketplace/products",
                headers={"Authorization": f"Bearer {self.api_token}"},
                params={"blueprint_id": blueprint_id}
            )
            if response.status_code == 200:
                return response.json()
        return []
    
    async def close(self):
        """Cleanup."""
        if self._client:
            await self._client.aclose()
```

#### Task 6.2: Add CardTrader to Ingestion
**File**: `backend/app/tasks/ingestion.py`

Add CardTrader to price collection cycle:
```python
# In _collect_price_data_async()
cardtrader = CardTraderAdapter(settings.cardtrader_api_token)
cardtrader_marketplace = await _get_or_create_cardtrader_marketplace(db)

for card in cards:
    try:
        price_data = await cardtrader.fetch_price(
            card_name=card.name,
            set_code=card.set_code,
            collector_number=card.collector_number,
            scryfall_id=card.scryfall_id,
        )
        
        if price_data and price_data.price > 0:
            # Create price snapshot
            snapshot = PriceSnapshot(
                card_id=card.id,
                marketplace_id=cardtrader_marketplace.id,
                snapshot_time=datetime.utcnow(),
                price=price_data.price,
                currency=price_data.currency,
                min_price=price_data.price_low,
                max_price=price_data.price_high,
                num_listings=price_data.num_listings,
            )
            db.add(snapshot)
    except Exception as e:
        logger.warning("CardTrader price fetch failed", card_id=card.id, error=str(e))
```

#### Task 6.3: Blueprint Mapping System
Create table/model for CardTrader blueprint mappings:
```python
# Migration or new model
class CardTraderBlueprint(Base):
    __tablename__ = "cardtrader_blueprints"
    
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    blueprint_id: Mapped[int] = mapped_column(nullable=False, index=True)
    expansion_id: Mapped[int] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

Build initial mapping by querying CardTrader expansions and matching to cards.

---

## Priority 7: Scryfall Bulk Data Integration

### Implementation Tasks

#### Task 7.1: Create Bulk Data Download Task
**File**: `backend/app/tasks/data_seeding.py`

```python
@shared_task(bind=True, max_retries=3)
def download_scryfall_bulk_data_task(self):
    """Download and process Scryfall bulk data files."""
    return run_async(_download_scryfall_bulk_data_async())

async def _download_scryfall_bulk_data_async():
    """Download Scryfall bulk data and extract prices."""
    BULK_DATA_URL = "https://api.scryfall.com/bulk-data"
    
    async with httpx.AsyncClient() as client:
        # Get manifest
        response = await client.get(BULK_DATA_URL)
        manifest = response.json()
        
        # Find default_cards or all_cards file
        for file_info in manifest['data']:
            if file_info['type'] in ['default_cards', 'all_cards']:
                download_uri = file_info['download_uri']
                
                # Download file
                file_response = await client.get(download_uri)
                cards_data = file_response.json()
                
                # Process each card
                session_maker, engine = create_task_session_maker()
                async with session_maker() as db:
                    for card_data in cards_data:
                        await process_bulk_card(card_data, db)
                    await db.commit()
                await engine.dispose()

async def process_bulk_card(card_data: dict, db: AsyncSession):
    """Extract prices from Scryfall bulk card data."""
    # Get or create card
    card = await get_or_create_card_from_scryfall(card_data, db)
    
    # Extract prices
    prices = card_data.get('prices', {})
    marketplace_map = {
        'usd': ('tcgplayer', 'TCGPlayer', 'USD'),
        'eur': ('cardmarket', 'Cardmarket', 'EUR'),
        'tix': ('mtgo', 'MTGO', 'TIX'),
    }
    
    for price_key, (slug, name, currency) in marketplace_map.items():
        price_value = prices.get(price_key)
        if price_value and float(price_value) > 0:
            marketplace = await get_or_create_marketplace(slug, name, currency, db)
            
            # Check if snapshot exists
            existing = await db.scalar(
                select(PriceSnapshot).where(
                    PriceSnapshot.card_id == card.id,
                    PriceSnapshot.marketplace_id == marketplace.id,
                    PriceSnapshot.snapshot_time >= datetime.utcnow() - timedelta(hours=24)
                ).limit(1)
            )
            
            if not existing:
                snapshot = PriceSnapshot(
                    card_id=card.id,
                    marketplace_id=marketplace.id,
                    snapshot_time=parse_scryfall_timestamp(card_data.get('updated_at')),
                    price=float(price_value),
                    currency=currency,
                    price_foil=float(prices.get(f'{price_key}_foil', 0)) or None,
                )
                db.add(snapshot)
```

#### Task 7.2: Schedule Bulk Data Task
**File**: `backend/app/tasks/celery_app.py`

Add to Celery beat schedule:
```python
'download-scryfall-bulk': {
    'task': 'app.tasks.data_seeding.download_scryfall_bulk_data_task',
    'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
}
```

---

## Testing Requirements

### Unit Tests
1. Test currency filtering in queries
2. Test interpolation function with various gap scenarios
3. Test normalization with fixed base point
4. Test export functions (CSV and TXT)

### Integration Tests
1. Test market index endpoint with currency parameters
2. Test inventory index endpoint with currency parameters
3. Test CardTrader adapter (mock API responses)
4. Test Scryfall bulk data processing

### Manual Testing Checklist
- [ ] USD-only chart displays correctly
- [ ] EUR-only chart displays correctly
- [ ] Separate currencies chart shows both lines
- [ ] Charts have no gaps (interpolation working)
- [ ] Index doesn't jump on refresh (normalization fixed)
- [ ] Export inventory generates valid CSV/TXT
- [ ] Enhanced search filters work correctly
- [ ] Foil pricing toggle works
- [ ] CardTrader prices are collected and stored
- [ ] Scryfall bulk data is downloaded and processed

---

## Implementation Order

1. **Week 1**: Priority 1 (Currency Separation) + Priority 2 (Interpolation)
2. **Week 2**: Priority 3 (Normalization) + Priority 4 (Remove Backfilling)
3. **Week 3**: Priority 5 (Inventory Features)
4. **Week 4**: Priority 6 (CardTrader Integration)
5. **Week 5**: Priority 7 (Scryfall Bulk Data)

---

## Important Notes

1. **Backward Compatibility**: All changes must maintain backward compatibility. Existing API calls should continue to work.

2. **Database Migrations**: If adding new fields (e.g., `is_synthetic`), create Alembic migration.

3. **Error Handling**: All new code must have proper error handling and logging.

4. **Rate Limiting**: Respect API rate limits (CardTrader: 200/10s, Scryfall: 50-75ms between calls).

5. **Testing**: Write tests for all new functionality, especially chart endpoints.

6. **Documentation**: Update API documentation for new parameters.

---

## Success Criteria

- Charts display separate USD and EUR lines
- Charts have no gaps (smooth lines)
- Index values are stable (no jumps on refresh)
- No synthetic data in charts
- Inventory export works (CSV and TXT)
- Enhanced search filters work
- CardTrader prices are collected
- Scryfall bulk data provides historical coverage

---

## Questions to Resolve During Implementation

1. Should we keep aggregated index as default or make separate currencies default?
2. What exchange rate source should we use if we ever need currency conversion?
3. Should foil pricing be a separate chart or a toggle on existing charts?
4. How should we handle CardTrader blueprint mapping for cards not found?
5. Should Scryfall bulk data replace or supplement existing data collection?

---

This prompt provides comprehensive guidance for implementing all charting and inventory improvements. Follow the priority order and test thoroughly at each step.



