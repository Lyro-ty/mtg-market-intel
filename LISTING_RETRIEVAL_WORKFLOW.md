# Listing Retrieval Workflow & Pipeline

## Current Workflow

### 1. **Scheduled Scraping** (Background Tasks)
- **Task**: `scrape_all_marketplaces()` (Celery task)
- **Frequency**: Scheduled via Celery Beat (default: every 30 minutes)
- **Process**:
  1. Gets all enabled marketplaces
  2. Prioritizes cards in user inventory
  3. Fills remaining slots (up to 2000 total cards)
  4. For each marketplace:
     - For each card:
       - Calls `adapter.fetch_price()` → Creates `PriceSnapshot`
       - Calls `adapter.fetch_listings(limit=100)` → Creates/Updates `Listing` records
  5. Logs summary: `listings_created`, `listings_updated`, `cards_with_listings`, `cards_without_listings`

### 2. **Manual Card Refresh** (API Endpoint)
- **Endpoint**: `POST /api/cards/{card_id}/refresh`
- **Process**:
  1. If `sync=True` (default): Calls `_sync_refresh_card()`
     - Fetches Scryfall price → Creates snapshot
     - For each enabled marketplace (excluding 'scryfall' and 'mock'):
       - Calls `adapter.fetch_listings(limit=100)`
       - Creates/updates listings
  2. If `sync=False`: Dispatches background tasks

### 3. **Adapter Implementation** (Web Scraping)
Each marketplace adapter (`TCGPlayerAdapter`, `CardKingdomAdapter`, `CardMarketAdapter`):
- Uses CSS selectors to find listings on marketplace websites
- Tries multiple selector strategies if first fails
- Extracts: price, condition, quantity, seller info, foil status
- Returns list of `CardListing` objects

### 4. **Listing Storage**
- **New listings**: Created with `last_seen_at = now()`
- **Existing listings**: Updated and `last_seen_at = now()` (matched by `external_id`)
- **No cleanup**: Old listings are NOT automatically deleted (they just have old `last_seen_at`)

## Why Only 54 Listings in 24 Hours?

### Potential Issues:

1. **CSS Selectors Not Matching** ⚠️
   - Marketplace websites may have changed structure
   - Selectors like `.product-listing`, `.listing-item` may not exist
   - Adapters return empty lists silently

2. **Rate Limiting Too Aggressive**
   - Each adapter has `rate_limit_seconds` (default: 1-2 seconds)
   - With 2000 cards × 3 marketplaces = 6000 requests
   - At 1 second/request = 100 minutes minimum
   - May be hitting rate limits or getting blocked

3. **Few Cards Being Scraped**
   - Only cards in inventory + up to 2000 others
   - If you have few cards in inventory, only those get scraped
   - Other cards may not be getting scraped frequently

4. **Adapters Failing Silently**
   - Errors are logged as warnings but don't stop the process
   - Failed scrapes return empty lists
   - No retry mechanism for failed adapters

5. **No Listing Cleanup**
   - Old listings stay in database forever
   - The "54 listings" might be counting only NEW listings created
   - Existing listings are updated, not counted as "new"

6. **Marketplace Filtering**
   - Only enabled marketplaces are scraped
   - 'scryfall' and 'mock' are excluded from manual refresh
   - If marketplaces are disabled, no listings retrieved

## Debugging Steps

### 1. Check Scraping Logs
```bash
docker logs dualcaster-worker --tail 500 | grep -i "listings\|scrape\|marketplace"
```

Look for:
- `listings_created` counts
- `cards_with_listings` vs `cards_without_listings`
- Error messages from adapters
- Rate limiting messages

### 2. Check Adapter Success Rate
The logs should show:
```
Marketplace scrape summary
  marketplace=tcgplayer
  cards_processed=200
  cards_with_listings=5
  cards_without_listings=195
  listings_created=12
  listings_updated=3
```

If `cards_without_listings` is high, adapters are failing.

### 3. Test Adapters Manually
```python
# In Python shell or script
from app.services.ingestion import get_adapter

adapter = get_adapter("tcgplayer", cached=False)
listings = await adapter.fetch_listings(
    card_name="Lightning Bolt",
    set_code="M21",
    limit=100
)
print(f"Found {len(listings)} listings")
```

### 4. Check Database
```sql
-- Count listings by marketplace
SELECT 
    m.name,
    COUNT(*) as total_listings,
    COUNT(CASE WHEN l.last_seen_at > NOW() - INTERVAL '24 hours' THEN 1 END) as recent_listings
FROM listings l
JOIN marketplaces m ON l.marketplace_id = m.id
GROUP BY m.name;

-- Check which cards have listings
SELECT 
    c.name,
    COUNT(DISTINCT l.id) as listing_count
FROM cards c
LEFT JOIN listings l ON c.id = l.card_id
GROUP BY c.name
ORDER BY listing_count DESC
LIMIT 20;
```

## Recommendations to Improve Listing Retrieval

### 1. **Add Better Logging**
- Log when adapters return empty lists
- Log selector matches/failures
- Log rate limit hits

### 2. **Add Listing Cleanup Task**
- Delete listings not seen in 7+ days
- Or mark them as inactive

### 3. **Improve Adapter Error Handling**
- Retry failed requests
- Try alternative selectors
- Fallback to different search strategies

### 4. **Increase Scraping Frequency**
- Reduce rate limits if possible
- Scrape in parallel (multiple cards at once)
- Prioritize popular cards more frequently

### 5. **Add Health Checks**
- Monitor adapter success rates
- Alert when success rate drops below threshold
- Track which marketplaces are working

### 6. **Consider API Alternatives**
- TCGPlayer has an API (if you have credentials)
- Cardmarket has an API (if you have credentials)
- APIs are more reliable than web scraping

## Quick Fixes

### 1. Check Which Marketplaces Are Enabled
```bash
docker exec dualcaster-backend python -c "
from app.db.session import async_session_maker
from app.models import Marketplace
from sqlalchemy import select
import asyncio

async def check():
    async with async_session_maker() as db:
        result = await db.execute(select(Marketplace).where(Marketplace.is_enabled == True))
        for mp in result.scalars().all():
            print(f'{mp.name} ({mp.slug}): enabled={mp.is_enabled}')

asyncio.run(check())
"
```

### 2. Trigger Manual Scrape and Watch Logs
```bash
# Trigger scrape
docker exec dualcaster-worker celery -A app.tasks.celery_app call app.tasks.ingestion.scrape_all_marketplaces

# Watch logs
docker logs dualcaster-worker -f | grep -i "listings\|scrape"
```

### 3. Test Single Card Refresh
```bash
# Get a card ID first, then:
curl -X POST "http://localhost:8000/api/cards/1/refresh?sync=true"
```

## Next Steps

1. **Check the logs** to see what's actually happening
2. **Test adapters manually** to see if they're working
3. **Check database** to see listing distribution
4. **Review marketplace selectors** - they may need updating
5. **Consider adding API support** if credentials are available

