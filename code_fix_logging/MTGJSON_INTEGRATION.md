# MTGJSON Integration Guide

## Overview

MTGJSON has been integrated into the system to supplement our real-time scrapers with historical price data. This provides valuable training data for time-series models and trend analysis.

## What MTGJSON Provides

- **Historical Price Data**: Weekly price intervals going back ~3 months
- **Multiple Marketplaces**: TCGPlayer and Cardmarket price data
- **Comprehensive Coverage**: All cards in MTGJSON's AllPrintings dataset

## What MTGJSON Does NOT Provide

- ❌ Individual listings (condition, seller, quantity)
- ❌ Real-time prices (updates are weekly)
- ❌ All marketplaces (only TCGPlayer and Cardmarket)

**Therefore, MTGJSON supplements but does NOT replace our scrapers.**

## Architecture

### Components

1. **MTGJSONAdapter** (`backend/app/services/ingestion/adapters/mtgjson.py`)
   - Downloads and caches MTGJSON data files
   - Parses historical price data from AllPrintings.json
   - Provides `fetch_price_history()` method

2. **Import Task** (`backend/app/tasks/ingestion.py`)
   - `import_mtgjson_historical_prices` - Celery task to import historical data
   - Creates price snapshots with historical timestamps
   - Prioritizes inventory cards

3. **Training Data Export** (`backend/app/scripts/export_training_data.py`)
   - Exports historical prices as JSON files
   - Provides time-series format for model training
   - Includes historical price metadata in feature_info.json

## Usage

### 1. Import Historical Prices

Run the Celery task to import MTGJSON historical price data:

```python
from app.tasks.ingestion import import_mtgjson_historical_prices

# Import for all cards (up to 1000, prioritizing inventory)
result = import_mtgjson_historical_prices.delay(days=90)

# Import for specific cards
result = import_mtgjson_historical_prices.delay(card_ids=[1, 2, 3], days=90)
```

### 2. Schedule Regular Imports

Add to your Celery Beat schedule (in `celery_app.py`):

```python
from celery.schedules import crontab

beat_schedule = {
    'import-mtgjson-historical-prices': {
        'task': 'app.tasks.ingestion.import_mtgjson_historical_prices',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'kwargs': {'days': 90},
    },
}
```

### 3. Export Training Data with Historical Prices

```bash
# Export with historical prices included (default)
python -m app.scripts.export_training_data data/training 5

# Export without historical prices
python -m app.scripts.export_training_data data/training 5 --no-historical
```

The export will create:
- `historical_prices.json` - Full price history per card
- `historical_prices_timeseries.json` - Time-series format for models

### 4. Use MTGJSON Adapter Directly

```python
from app.services.ingestion import get_adapter

adapter = get_adapter("mtgjson")

# Fetch historical prices for a card
historical_prices = await adapter.fetch_price_history(
    card_name="Lightning Bolt",
    set_code="M21",
    collector_number="161",
    days=90,
)

# Each price has a timestamp
for price in historical_prices:
    print(f"{price.snapshot_time}: ${price.price}")
```

## Data Structure

### Price Snapshots

Historical prices are stored in the `price_snapshots` table with:
- `marketplace_id` pointing to the MTGJSON marketplace
- `snapshot_time` set to the historical date (not current time)
- `price` and `price_foil` from MTGJSON data
- `currency` (USD for TCGPlayer, EUR for Cardmarket)

### Training Data Format

**historical_prices.json:**
```json
[
  {
    "card_id": 123,
    "card_name": "Lightning Bolt",
    "set_code": "M21",
    "prices": [
      {
        "snapshot_time": "2024-01-01T00:00:00",
        "price": 0.25,
        "currency": "USD",
        "price_foil": null
      },
      ...
    ]
  }
]
```

**historical_prices_timeseries.json:**
```json
{
  "123": {
    "timestamps": ["2024-01-01T00:00:00", ...],
    "prices": [0.25, ...],
    "prices_foil": []
  }
}
```

## Caching

MTGJSON data files are cached locally in `data/mtgjson_cache/`:
- Files are cached for 24 hours
- Automatically decompressed if gzipped
- Reduces API calls and improves performance

## Limitations

1. **Update Frequency**: MTGJSON updates weekly, not real-time
2. **Historical Depth**: Only ~3 months of history available
3. **Marketplace Coverage**: Only TCGPlayer and Cardmarket (not Card Kingdom)
4. **No Individual Listings**: Only aggregated prices, no condition/seller data

## Best Practices

1. **Run imports during off-peak hours** (MTGJSON files are large)
2. **Prioritize inventory cards** (already implemented)
3. **Cache data locally** (already implemented)
4. **Combine with real-time scrapers** for comprehensive coverage
5. **Use for training time-series models** to predict price trends

## Troubleshooting

### No historical prices imported

- Check if MTGJSON marketplace exists in database
- Verify adapter can download AllPrintings.json
- Check cache directory permissions (`data/mtgjson_cache/`)

### Import is slow

- MTGJSON files are large (several GB)
- Consider limiting to inventory cards only
- Run during off-peak hours

### Missing price data

- MTGJSON may not have prices for all cards
- Some older cards may not have historical data
- Check MTGJSON's coverage for specific sets

## Future Enhancements

- [ ] Support for MTGGraphQL API (when available)
- [ ] Incremental updates (only fetch new data)
- [ ] Support for more marketplaces if MTGJSON adds them
- [ ] Integration with price prediction models

