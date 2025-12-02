# Scraper Removal and Refactoring Summary

## Overview
Removed all web scrapers (TCGPlayer, Cardmarket, Card Kingdom) and refactored the system to use **Scryfall** and **MTGJSON** as primary data sources. This provides:
- **Free, reliable API access** (no scraping, no bot detection issues)
- **Aggressive data collection** (every 2-5 minutes for fresh data)
- **Historical price data** from MTGJSON
- **Better data quality** from aggregated sources

## Key Changes

### 1. Removed Web Scrapers
- **Deleted files:**
  - `backend/app/services/ingestion/adapters/tcgplayer.py`
  - `backend/app/services/ingestion/adapters/cardmarket.py`
  - `backend/app/services/ingestion/adapters/cardkingdom.py`

- **Updated registry:** Only Scryfall, MTGJSON, and Mock adapters remain

### 2. New Aggressive Price Collection System

#### Tasks (Celery Beat Schedule)
- **`collect_price_data`**: Runs every **5 minutes** - collects prices for all cards
- **`collect_inventory_prices`**: Runs every **2 minutes** - prioritizes inventory cards
- **`import_mtgjson_historical_prices`**: Runs daily at 3 AM - imports historical data

#### Data Collection Strategy
- **Scryfall**: Real-time aggregated prices (TCGPlayer USD, Cardmarket EUR, MTGO tix)
- **MTGJSON**: Historical weekly price data (3 months back)
- **Staleness threshold**: Data older than 24 hours is considered stale
- **No individual listings**: Focus on aggregated price snapshots

### 3. Updated Ingestion Tasks

**Before:**
- `scrape_all_marketplaces()` - scraped listings from multiple marketplaces
- `scrape_inventory_cards()` - scraped listings for inventory cards

**After:**
- `collect_price_data()` - collects price snapshots from Scryfall for all cards
- `collect_inventory_prices()` - aggressively updates inventory card prices (every 2 min)

### 4. Updated API Routes

**`/cards/{id}/refresh`**:
- Removed scraper logic
- Now only fetches Scryfall price data
- Creates price snapshots (not individual listings)

**Market Overview**:
- Updated to use `PriceSnapshot` instead of `Listing` for volume calculations
- Estimates volume from price snapshots and `num_listings` field

### 5. Updated Training Data Export

**Before:**
- Exported `ListingFeatureVector` data
- Required minimum listings per card

**After:**
- Exports `PriceSnapshot` data with combined feature vectors
- Combines card vectors with snapshot metadata (price, timestamp, marketplace)
- Includes historical prices from MTGJSON

### 6. Enhanced Scryfall Adapter

Added `_parse_all_price_data()` method to extract prices from multiple marketplaces:
- USD (TCGPlayer)
- EUR (Cardmarket)
- TIX (MTGO)

## Data Flow

### Price Collection
```
Scryfall API → Price Snapshots → Database
MTGJSON → Historical Price Snapshots → Database
```

### Training Data
```
Card Feature Vectors + Price Snapshots → Combined Feature Vectors → Training Export
```

## Benefits

1. **Reliability**: No more bot detection, 403 errors, or selector breakage
2. **Speed**: API calls are faster than web scraping
3. **Frequency**: Can collect data every 2-5 minutes (vs 30 minutes before)
4. **Historical Data**: MTGJSON provides 3 months of weekly price history
5. **Scalability**: Can collect prices for ALL cards, not just inventory
6. **Cost**: Free APIs (Scryfall rate limit: 50-100ms between requests)

## Migration Notes

- Existing `Listing` records remain in database but are no longer updated
- `PriceSnapshot` is now the primary data source
- Analytics and recommendations now use price snapshots
- Training data export uses snapshot vectors instead of listing vectors

## Configuration

Price collection frequency is configured in `backend/app/tasks/celery_app.py`:
- All cards: Every 5 minutes
- Inventory cards: Every 2 minutes
- Historical data: Daily at 3 AM

## Next Steps

1. Monitor price collection logs to ensure data freshness
2. Verify analytics are working with price snapshot data
3. Update frontend if it references listing counts (now uses snapshots)
4. Consider adding more Scryfall price sources (if available)

