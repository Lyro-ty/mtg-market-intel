# API Call Structure: TCGPlayer and CardTrader

This document explains how API calls are structured for TCGPlayer and CardTrader, and common issues that might prevent data from populating.

## Overview

Both APIs are integrated through adapter classes that handle authentication, rate limiting, and data transformation. The adapters are called from scheduled ingestion tasks that run periodically to collect price data.

---

## TCGPlayer API Structure

### Configuration
- **Base URL**: `https://api.tcgplayer.com`
- **Auth URL**: `https://api.tcgplayer.com/token`
- **Rate Limit**: 100 requests per minute
- **Authentication**: OAuth 2.0 Client Credentials Flow

### Environment Variables
```bash
TCGPLAYER_API_KEY=your_client_id_here
TCGPLAYER_API_SECRET=your_client_secret_here
```

### API Call Flow

#### 1. Authentication (`_get_auth_token`)
```python
# Location: backend/app/services/ingestion/adapters/tcgplayer.py:91-148

# Step 1: Check if token is still valid (cached for ~55 minutes)
if self._auth_token and self._token_expires_at:
    if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
        return self._auth_token

# Step 2: Request new token using Basic Auth
credentials = f"{api_key}:{api_secret}"
encoded_credentials = base64.b64encode(credentials.encode()).decode()

POST https://api.tcgplayer.com/token
Headers:
  Authorization: Basic {base64_encoded_credentials}
  Content-Type: application/x-www-form-urlencoded
Body:
  grant_type=client_credentials

# Response contains:
# - access_token: Bearer token for subsequent requests
# - expires_in: Token lifetime (typically 3600 seconds)
```

#### 2. Finding Product ID (`_find_product_id`)
```python
# Location: backend/app/services/ingestion/adapters/tcgplayer.py:216-287

# TCGPlayer uses product IDs, not card names directly
GET https://api.tcgplayer.com/catalog/products?productName={card_name}&limit=100
Headers:
  Authorization: Bearer {access_token}

# Response structure:
{
  "results": [
    {
      "productId": 12345,
      "name": "Card Name",
      "groupId": 123,  # Set ID
      "number": "001"   # Collector number
    }
  ]
}

# Matching logic:
# 1. Try exact name match + collector number
# 2. Fall back to fuzzy name match
# 3. Return first result if no exact match
```

#### 3. Fetching Prices (`fetch_price`)
```python
# Location: backend/app/services/ingestion/adapters/tcgplayer.py:400-484

# Step 1: Find product ID (see above)
product_id = await self._find_product_id(card_name, set_code, collector_number)

# Step 2: Get pricing data
GET https://api.tcgplayer.com/pricing/product/{product_id}
Headers:
  Authorization: Bearer {access_token}

# Response structure:
{
  "results": [
    {
      "lowPrice": 1.25,
      "highPrice": 2.50,
      "marketPrice": 1.75,
      "isFoil": false,
      "subTypeName": "Near Mint",
      "quantity": 100
    }
  ]
}

# Step 3: Aggregate prices
# - Separates foil and non-foil prices
# - Calculates average, min, max
# - Returns CardPrice object
```

### Integration Point
```python
# Location: backend/app/tasks/ingestion.py:656-743

# Check if credentials are configured
if settings.tcgplayer_api_key and settings.tcgplayer_api_secret:
    # Create adapter
    tcgplayer = TCGPlayerAdapter(tcgplayer_config)
    
    # For each card, fetch price
    price_data = await tcgplayer.fetch_price(
        card_name=card.name,
        set_code=card.set_code,
        collector_number=card.collector_number,
        scryfall_id=card.scryfall_id,
    )
    
    # Save to database if price > 0
    if price_data and price_data.price > 0:
        await _upsert_price_snapshot(...)
```

---

## CardTrader API Structure

### Configuration
- **Base URL**: `https://api.cardtrader.com/api/v2`
- **Rate Limit**: 10 requests per second
- **Authentication**: Bearer Token (JWT)

### Environment Variables
```bash
CARDTRADER_API_TOKEN=your_jwt_token_here
```

### API Call Flow

#### 1. Authentication
```python
# Location: backend/app/services/ingestion/adapters/cardtrader.py:66-79

# CardTrader uses a JWT token directly (no OAuth flow)
# Token is passed in Authorization header for all requests

Headers:
  Authorization: Bearer {jwt_token}
```

#### 2. Finding Blueprint ID (`_find_blueprint`)
```python
# Location: backend/app/services/ingestion/adapters/cardtrader.py:111-303

# CardTrader uses "blueprints" instead of product IDs
# Process requires multiple API calls:

# Step 1: Find expansion (set) by set code
GET https://api.cardtrader.com/api/v2/expansions
Headers:
  Authorization: Bearer {jwt_token}

# Response structure:
[
  {
    "id": 123,
    "code": "M21",
    "name": "Core Set 2021"
  }
]

# Step 2: Get blueprints for the expansion (with pagination)
GET https://api.cardtrader.com/api/v2/blueprints?expansion_id={expansion_id}&limit=1000&page=1
Headers:
  Authorization: Bearer {jwt_token}

# Response structure:
[
  {
    "id": 45678,
    "name": "Card Name",
    "number": "001",
    "expansion_id": 123
  }
]

# Step 3: Match card by name and collector number
# - Exact name match preferred
# - Falls back to partial match if collector number matches
```

#### 3. Fetching Marketplace Products (`_get_marketplace_products`)
```python
# Location: backend/app/services/ingestion/adapters/cardtrader.py:305-395

GET https://api.cardtrader.com/api/v2/marketplace/products?blueprint_id={blueprint_id}&limit=100&language=en
Headers:
  Authorization: Bearer {jwt_token}

# Response structure:
[
  {
    "id": 789,
    "seller_price": {
      "cents": 125,  # Price in cents
      "currency": "USD"
    },
    "condition": "NM",
    "mtg_foil": false,
    "quantity": 1,
    "language": "en"
  }
]

# Note: Currency filtering is done client-side
# API doesn't support currency parameter directly
```

#### 4. Fetching Prices (`fetch_price`)
```python
# Location: backend/app/services/ingestion/adapters/cardtrader.py:568-664

# Step 1: Find blueprint ID (see above)
blueprint_id = await self._find_blueprint(card_name, set_code, collector_number)

# Step 2: Get marketplace products
products = await self._get_marketplace_products(
    blueprint_id,
    language="en",
    currency="USD"  # Filtered client-side
)

# Step 3: Calculate aggregate prices
# - Extracts prices from seller_price.cents
# - Filters by currency (USD)
# - Calculates average, min, max
# - Separates foil prices
```

### Integration Point
```python
# Location: backend/app/tasks/ingestion.py:474-566

# Check if token is configured
if settings.cardtrader_api_token:
    # Create adapter
    cardtrader = CardTraderAdapter(cardtrader_config)
    
    # For each card, fetch price
    price_data = await cardtrader.fetch_price(
        card_name=card.name,
        set_code=card.set_code,
        collector_number=card.collector_number,
        scryfall_id=card.scryfall_id,
    )
    
    # Save to database if price > 0
    if price_data and price_data.price > 0:
        await _upsert_price_snapshot(...)
```

---

## Common Issues Preventing Data Population

### 1. Missing or Invalid API Tokens

**Symptoms:**
- No data appears in database
- Logs show "API token not configured" or "authentication failed"

**TCGPlayer:**
- Check `TCGPLAYER_API_KEY` and `TCGPLAYER_API_SECRET` are set in `.env`
- Verify credentials are valid Partner API credentials (not regular account credentials)
- Check logs for authentication errors (status 401)

**CardTrader:**
- Check `CARDTRADER_API_TOKEN` is set in `.env`
- Verify token is a valid JWT token from CardTrader Full API
- Token should be obtained from CardTrader developer dashboard

**Debug:**
```python
# Check settings are loaded correctly
from app.core.config import settings
print(f"TCGPlayer Key: {settings.tcgplayer_api_key[:10]}...")  # First 10 chars
print(f"TCGPlayer Secret: {bool(settings.tcgplayer_api_secret)}")  # True/False
print(f"CardTrader Token: {settings.cardtrader_api_token[:10]}...")  # First 10 chars
```

### 2. Product/Blueprint Not Found

**Symptoms:**
- Some cards have data, others don't
- Logs show "product not found" or "blueprint not found"

**TCGPlayer:**
- Product matching relies on fuzzy name matching
- Set code matching may fail if TCGPlayer uses different set codes
- Collector number matching helps but isn't always available

**CardTrader:**
- Expansion (set) lookup may fail if CardTrader uses different set codes
- Blueprint matching requires exact or close name match
- Not all cards have CardTrader blueprints (this is expected)

**Debug:**
- Check logs for specific card names that fail
- Verify set codes match between your data and API
- Try searching manually in TCGPlayer/CardTrader websites

### 3. Rate Limiting Issues

**Symptoms:**
- Intermittent failures
- 429 status codes in logs
- Timeouts

**TCGPlayer:**
- Rate limit: 100 requests/minute
- Code enforces 0.6s delay between requests
- Window-based rate limiting implemented

**CardTrader:**
- Rate limit: 10 requests/second
- Code enforces 0.1s delay between requests
- Window-based rate limiting implemented

**Debug:**
- Check logs for "rate limit reached" messages
- Verify rate limiting code is working correctly
- Consider reducing batch sizes if processing many cards

### 4. Currency Filtering Issues

**Symptoms:**
- CardTrader data appears but in wrong currency
- No USD listings found

**CardTrader:**
- Currency filtering is done client-side (API doesn't support it)
- Code filters by `seller_price.currency` field
- If no USD products exist, no data will be saved

**Debug:**
- Check if products exist but are in EUR
- Verify currency filtering logic in `_get_marketplace_products`
- Check logs for "No USD listings found" messages

### 5. Database Issues

**Symptoms:**
- API calls succeed but no data in database
- Snapshots not being created

**Common Causes:**
- Database connection issues
- Transaction not committed
- Duplicate prevention logic preventing saves
- Marketplace not created in database

**Debug:**
```python
# Check if marketplace exists
from app.models.marketplace import Marketplace
marketplace = await db.execute(
    select(Marketplace).where(Marketplace.slug == "tcgplayer")
)
print(f"TCGPlayer marketplace: {marketplace.scalar_one_or_none()}")

# Check recent snapshots
from app.models.price_snapshot import PriceSnapshot
recent = await db.execute(
    select(PriceSnapshot)
    .where(PriceSnapshot.marketplace_id == marketplace_id)
    .order_by(PriceSnapshot.snapshot_time.desc())
    .limit(10)
)
print(f"Recent snapshots: {recent.scalars().all()}")
```

### 6. Task Not Running

**Symptoms:**
- No API calls being made at all
- No logs from ingestion task

**Check:**
- Verify Celery worker is running
- Check scheduled task configuration in `celery_app.py`
- Verify task is being triggered (check Celery logs)
- Check if task is enabled in settings

---

## Debugging Steps

1. **Check Environment Variables**
   ```bash
   # In backend directory
   python -c "from app.core.config import settings; print(f'TCGPlayer: {bool(settings.tcgplayer_api_key)}'); print(f'CardTrader: {bool(settings.cardtrader_api_token)}')"
   ```

2. **Test API Authentication**
   ```python
   # TCGPlayer
   from app.services.ingestion.adapters.tcgplayer import TCGPlayerAdapter
   adapter = TCGPlayerAdapter()
   token = await adapter._get_auth_token()
   print(f"Token: {token[:20]}..." if token else "Failed")
   
   # CardTrader
   from app.services.ingestion.adapters.cardtrader import CardTraderAdapter
   adapter = CardTraderAdapter()
   # Token is already set, test by making a request
   ```

3. **Test Single Card Fetch**
   ```python
   # TCGPlayer
   price = await tcgplayer.fetch_price(
       card_name="Lightning Bolt",
       set_code="M21",
       collector_number="161"
   )
   print(f"Price: {price.price if price else 'Not found'}")
   
   # CardTrader
   price = await cardtrader.fetch_price(
       card_name="Lightning Bolt",
       set_code="M21",
       collector_number="161"
   )
   print(f"Price: {price.price if price else 'Not found'}")
   ```

4. **Check Logs**
   - Look for authentication errors
   - Check for "product not found" or "blueprint not found" messages
   - Verify rate limiting is working
   - Check for database errors

5. **Verify Database**
   - Check if marketplaces exist
   - Check if snapshots are being created
   - Verify data is in correct format

---

## Key Files

- **TCGPlayer Adapter**: `backend/app/services/ingestion/adapters/tcgplayer.py`
- **CardTrader Adapter**: `backend/app/services/ingestion/adapters/cardtrader.py`
- **Ingestion Task**: `backend/app/tasks/ingestion.py` (lines 656-743 for TCGPlayer, 474-566 for CardTrader)
- **Configuration**: `backend/app/core/config.py` (lines 66-67 for TCGPlayer, 72 for CardTrader)
- **Base Adapter**: `backend/app/services/ingestion/base.py`

---

## Next Steps

If data still isn't populating after checking the above:

1. Enable debug logging to see detailed API responses
2. Test API calls manually using curl/Postman
3. Verify API credentials are correct and have proper permissions
4. Check if specific cards are failing (may be matching issues)
5. Review database to see if snapshots are being created but not displayed

