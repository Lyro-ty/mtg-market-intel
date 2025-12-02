# Comprehensive Data Seeding System

## Overview
Implemented a comprehensive data seeding system that pulls current and historical price data for ALL cards on startup and at regular intervals. This ensures dashboard charts have real, up-to-date data for 30d/90d/6m/1y time ranges.

## Architecture

### Data Sources
1. **Scryfall**: Current/real-time prices for all cards
2. **MTGJSON**: Historical price data (weekly intervals, ~90 days back)

### Seeding Strategy

#### Phase 1: Startup Seeding
- Runs automatically when application starts
- Pulls current prices from Scryfall for ALL cards
- Pulls historical data from MTGJSON (30d/90d/6m/1y where available)
- Combines and stores in database
- Ensures dashboard has data immediately

#### Phase 2: Periodic Updates
- **Comprehensive Seeding**: Every 6 hours (refreshes historical data)
- **Current Prices**: Every 5 minutes (real-time updates)
- **Inventory Prices**: Every 2 minutes (highest priority)

## Implementation

### New Task: `seed_comprehensive_price_data`

**Location**: `backend/app/tasks/data_seeding.py`

**What it does**:
1. Gets ALL cards from database
2. Pulls current prices from Scryfall (all cards)
3. Pulls historical data from MTGJSON (30d/90d/6m/1y)
4. Combines and stores in database
5. Ensures data quality for ML training

**Key Features**:
- Processes all cards (no limits)
- Handles rate limiting (Scryfall: 100ms, MTGJSON: 1s)
- Batch processing for memory efficiency
- Error handling per card (doesn't fail entire batch)
- Progress logging

### Startup Integration

**Location**: `backend/app/main.py`

**On Startup**:
1. Comprehensive data seeding (current + historical)
2. Regular price collection (continues after seeding)
3. Analytics (runs after data is available)
4. Recommendations (runs after analytics)

### Celery Schedule

**Location**: `backend/app/tasks/celery_app.py`

**Schedule**:
- `seed-comprehensive-data`: Every 6 hours
- `collect-price-data`: Every 5 minutes
- `collect-inventory-prices`: Every 2 minutes
- `import-mtgjson-historical`: Daily at 3 AM (backup)

## Dashboard Integration

### Frontend Auto-Refresh

**Location**: `frontend/src/app/page.tsx`

**Refresh Intervals**:
- Market Overview: Every 2 minutes
- Market Index: Every 2 minutes
- Top Movers: Every 2 minutes
- Volume by Format: Every 5 minutes
- Color Distribution: Every 5 minutes

All queries use `refetchIntervalInBackground: true` to continue refreshing when tab is inactive.

### API Endpoints

All dashboard endpoints use real data from `PriceSnapshot` table:

1. **Market Index** (`/api/market/index`):
   - Uses time-bucketed price snapshots
   - Supports 7d/30d/90d/1y ranges
   - Real data from database

2. **Market Overview** (`/api/market/overview`):
   - Uses price snapshots for volume calculations
   - Real-time stats from database

3. **Top Movers** (`/api/market/top-movers`):
   - Uses `MetricsCardsDaily` (computed from snapshots)
   - Real price change data

4. **Volume by Format** (`/api/market/volume-by-format`):
   - Uses price snapshots aggregated by format
   - Real volume data

5. **Color Distribution** (`/api/market/color-distribution`):
   - Uses price snapshots aggregated by color
   - Real distribution data

## Data Quality for ML Training

### Price Snapshots
- Current prices: Updated every 5 minutes (2 minutes for inventory)
- Historical prices: Updated every 6 hours (comprehensive seeding)
- Data freshness: All data < 24 hours old (stale threshold)

### Training Data Export
- Exports use `PriceSnapshot` data
- Includes both current and historical snapshots
- Combines card vectors with snapshot metadata
- Suitable for time-series models

## Benefits

1. **Real-Time Data**: Dashboard shows live prices updated every 2-5 minutes
2. **Historical Context**: 30d/90d/6m/1y charts have real historical data
3. **ML Training Ready**: Comprehensive data suitable for buy/hold/sell predictions
4. **Startup Ready**: Data available immediately on application start
5. **Scalable**: Handles all cards in database efficiently

## Monitoring

### Logs
- Seeding progress logged every 100 cards
- Error logging per card (doesn't stop entire process)
- Summary statistics on completion

### Metrics
- Cards processed
- Current snapshots created
- Historical snapshots created
- Total snapshots
- Error count

## Future Enhancements

1. **WebSocket Updates**: Real-time push updates for dashboard
2. **Data Quality Scores**: Track data completeness per card
3. **Incremental Updates**: Only update cards with stale data
4. **Parallel Processing**: Process cards in parallel batches
5. **Extended History**: Integrate more historical data sources

