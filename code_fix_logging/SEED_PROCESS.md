# Seed Process Documentation

## Overview

The seed process runs automatically on application startup to ensure the database has comprehensive price data for all cards. This enables the charts and analytics to work immediately after startup.

## Workflow

The seed process follows this workflow:

1. **Collect Scryfall Card Names**
   - Cards are already in the database (sourced from Scryfall)
   - The seed process gets all cards from the database
   - These cards have Scryfall IDs, names, set codes, and collector numbers

2. **Match MTGJSON Card Names to Scryfall Cards**
   - For each card, the process matches it to MTGJSON data by:
     - Card name (case-insensitive)
     - Set code
     - Collector number
   - MTGJSON provides historical price data going back ~90 days

3. **Generate 30-Day History Using MTGJSON Data**
   - Fetches 30 days of historical price data from MTGJSON
   - MTGJSON provides weekly price intervals
   - Prices are stored by marketplace (TCGPlayer for USD, Cardmarket for EUR)

4. **Collect Current Prices from CardTrader (Optional)**
   - If CardTrader API token is configured, collects current prices
   - CardTrader provides European market data (EUR)
   - Note: CardTrader doesn't provide historical data, only current prices

## Implementation

### Location
- **Task**: `backend/app/tasks/data_seeding.py`
- **Function**: `seed_comprehensive_price_data()`
- **Startup Integration**: `backend/app/main.py` (lifespan handler)

### Phases

#### Phase 1: Get All Cards
- Queries all cards from the database
- Cards are sourced from Scryfall (canonical source)

#### Phase 2: Collect Current Prices from Scryfall
- Fetches current prices for all cards from Scryfall
- Scryfall provides prices from multiple marketplaces:
  - TCGPlayer (USD)
  - Cardmarket (EUR)
  - MTGO (TIX)
- Creates price snapshots with current timestamp

#### Phase 3: Match MTGJSON and Collect 30-Day History
- For each card, matches to MTGJSON data by name, set_code, and collector_number
- Fetches 30 days of historical price data
- MTGJSON provides weekly intervals (not daily)
- Stores historical snapshots with their original timestamps
- Prices are mapped to marketplaces based on currency:
  - USD → TCGPlayer
  - EUR → Cardmarket

#### Phase 4: Collect CardTrader Current Prices (Optional)
- Only runs if `CARDTRADER_API_TOKEN` is configured
- Fetches current prices from CardTrader for all cards
- CardTrader provides European market data (EUR)
- Creates price snapshots with current timestamp
- Note: CardTrader doesn't have historical data API

#### Phase 5: Commit All Changes
- Commits all price snapshots to the database
- Logs summary statistics

## Startup Integration

The seed process is automatically triggered on application startup:

```python
# backend/app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... startup code ...
    
    # Phase 1: Comprehensive data seeding (current + historical for all cards)
    seeding_task = seed_comprehensive_price_data.delay()
    
    # ... other startup tasks ...
```

The task runs asynchronously in the background, so the API is available immediately while seeding happens.

## Configuration

### Required
- Database with cards already seeded (from Scryfall)
- MTGJSON adapter (no API key needed, uses public data)

### Optional
- `CARDTRADER_API_TOKEN`: Enables CardTrader price collection

## Data Sources

### Scryfall
- **Type**: Current prices
- **Marketplaces**: TCGPlayer (USD), Cardmarket (EUR), MTGO (TIX)
- **Update Frequency**: Daily
- **Rate Limit**: 75ms between requests

### MTGJSON
- **Type**: Historical prices (30-day focus for startup)
- **Marketplaces**: TCGPlayer (USD), Cardmarket (EUR)
- **Update Frequency**: Weekly intervals
- **Historical Range**: ~90 days available
- **Rate Limit**: 1 second between requests

### CardTrader
- **Type**: Current prices only
- **Marketplace**: CardTrader (EUR)
- **Update Frequency**: Real-time
- **Rate Limit**: 200 requests per 10 seconds
- **Note**: No historical data available

## Results

After seeding completes, the database will have:
- Current prices from Scryfall for all cards
- 30-day historical prices from MTGJSON (where available)
- Current prices from CardTrader (if configured)

This ensures:
- Charts have data immediately after startup
- Market index calculations work
- Inventory valuations are accurate
- Analytics have sufficient data

## Monitoring

The seed process logs progress and results:
- Cards processed
- Snapshots created (by source)
- Errors encountered
- Total duration

Check logs for:
- `"Starting comprehensive price data seeding"`
- `"Phase 2: Collecting current prices from Scryfall"`
- `"Phase 3: Matching MTGJSON cards to Scryfall cards"`
- `"Phase 4: Collecting current prices from CardTrader"` (if enabled)
- `"Comprehensive price data seeding completed"`

## Periodic Updates

The seed process also runs periodically:
- **Every 6 hours**: Full comprehensive seeding (refreshes historical data)
- **Every 5 minutes**: Current price collection (incremental updates)

This is configured in `backend/app/tasks/celery_app.py`.

