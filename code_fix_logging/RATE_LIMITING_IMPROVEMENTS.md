# Rate Limiting Improvements

## Overview

We've enhanced the Scryfall adapter to better handle rate limits and prevent 429 errors. The improvements include:

1. **Retry Logic with Exponential Backoff** - Automatically retries failed requests
2. **Concurrent Request Limiting** - Limits simultaneous requests to prevent overwhelming the API
3. **Retry-After Header Support** - Respects server-specified wait times
4. **Timezone-Aware Datetimes** - Fixed timezone issues in rate limiting calculations

## Changes Made

### 1. Scryfall Adapter (`backend/app/services/ingestion/scryfall.py`)

#### Added Features:

- **Concurrent Request Semaphore**: Limits to 5 concurrent requests (Scryfall recommends 5-10)
- **Retry Logic**: Automatically retries 429 errors with exponential backoff
- **Retry-After Header Support**: Respects server-specified wait times from 429 responses
- **Improved Error Handling**: Better logging and error messages

#### Key Changes:

```python
# Before: Simple rate limiting, no retry
async def _request(self, endpoint: str, params: dict | None = None) -> dict | None:
    await self._rate_limit()
    response = await client.get(endpoint, params=params)
    response.raise_for_status()
    return response.json()

# After: Rate limiting + retry with exponential backoff
async def _request(
    self, 
    endpoint: str, 
    params: dict | None = None,
    retry_count: int = 0
) -> dict | None:
    async with self._concurrent_limit:  # Limit concurrent requests
        await self._rate_limit()
        response = await client.get(endpoint, params=params)
        
        if response.status_code == 429:
            # Handle rate limit with retry
            retry_after = response.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after else (2 ** retry_count)
            wait_seconds = min(wait_seconds, 60.0)  # Cap at 60 seconds
            
            if retry_count < self.config.max_retries:
                await asyncio.sleep(wait_seconds)
                return await self._request(endpoint, params, retry_count + 1)
```

### 2. Configuration

The adapter now uses settings from `config.py`:
- `scraper_max_retries`: Default 3 retries
- `scraper_backoff_factor`: Default 2.0 (exponential backoff)
- `scryfall_rate_limit_ms`: Default 100ms between requests

### 3. Timezone Fixes

Fixed `datetime.utcnow()` deprecation warnings:
- Changed to `datetime.now(timezone.utc)` for timezone-aware datetimes
- Ensures proper time calculations in rate limiting

## How It Works

### Rate Limiting Strategy

1. **Per-Request Rate Limiting**: 
   - Enforces minimum 100ms delay between requests (configurable)
   - Tracks last request time to ensure spacing

2. **Concurrent Request Limiting**:
   - Uses `asyncio.Semaphore(5)` to limit concurrent requests
   - Prevents overwhelming Scryfall's API

3. **429 Error Handling**:
   - Detects rate limit errors (429 status code)
   - Checks for `Retry-After` header from server
   - Uses exponential backoff if no header: 2^retry_count seconds
   - Caps maximum wait at 60 seconds
   - Retries up to `max_retries` times (default: 3)

### Example Flow

```
Request → Rate Limit Check → Make Request
                              ↓
                        429 Error?
                              ↓ Yes
                    Check Retry-After Header
                              ↓
                    Wait (exponential backoff)
                              ↓
                    Retry (up to max_retries)
                              ↓
                    Success or Final Error
```

## Benefits

1. **Reduced 429 Errors**: Automatic retry with backoff prevents most rate limit issues
2. **Better API Compliance**: Respects Scryfall's rate limits and recommendations
3. **Improved Reliability**: Requests that fail due to rate limits are automatically retried
4. **Better Logging**: More detailed logs for debugging rate limit issues
5. **Graceful Degradation**: Handles rate limits without crashing the application

## Configuration

You can adjust rate limiting behavior via environment variables:

```bash
# Minimum time between requests (milliseconds)
SCRYFALL_RATE_LIMIT_MS=100

# Maximum retries for failed requests
SCRAPER_MAX_RETRIES=3

# Exponential backoff factor
SCRAPER_BACKOFF_FACTOR=2.0
```

## Testing

To test the rate limiting:

1. **Monitor Logs**: Watch for retry messages
   ```bash
   docker logs dualcaster-backend | grep -i "rate limit\|retry"
   ```

2. **Check for 429 Errors**: Should see retries instead of failures
   ```bash
   docker logs dualcaster-backend | grep "429"
   ```

3. **Verify Success**: Requests should eventually succeed after retries

## Future Improvements

Potential enhancements:

1. **Distributed Rate Limiting**: Use Redis for rate limiting across multiple workers
2. **Adaptive Rate Limiting**: Adjust rate limits based on API response times
3. **Request Queuing**: Queue requests when rate limits are hit
4. **Circuit Breaker**: Temporarily stop requests if API is consistently rate limiting

## Related Files

- `backend/app/services/ingestion/scryfall.py` - Main adapter implementation
- `backend/app/core/config.py` - Configuration settings
- `backend/app/services/ingestion/base.py` - Base adapter class

