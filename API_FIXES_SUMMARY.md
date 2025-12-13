# API Integration Fixes Summary

This document summarizes the fixes applied to TCGPlayer and CardTrader API integrations based on official documentation.

## CardTrader API Fixes

### 1. Fixed Rate Limit ✅
**Issue**: Code was using 10 requests per second, but API documentation states **200 requests per 10 seconds**.

**Fix**:
- Updated `RATE_LIMIT_REQUESTS` from 10 to 200
- Updated `RATE_LIMIT_WINDOW` from 1 second to 10 seconds
- Updated `rate_limit_seconds` from 0.1s to 0.05s (200/10 = 0.05s between requests)
- Updated all references in `ingestion.py` and adapter

**Files Changed**:
- `backend/app/services/ingestion/adapters/cardtrader.py`
- `backend/app/tasks/ingestion.py` (4 locations)

### 2. Fixed Blueprints Endpoint ✅
**Issue**: Code was using `/blueprints` endpoint, but API documentation specifies `/blueprints/export`.

**Fix**:
- Changed endpoint from `/blueprints` to `/blueprints/export`
- Removed pagination logic (endpoint returns all blueprints for an expansion)
- Simplified response handling per documentation

**Files Changed**:
- `backend/app/services/ingestion/adapters/cardtrader.py`

### 3. Added Expansion Caching ✅
**Issue**: Expansions were being fetched on every single card lookup, causing excessive API calls.

**Fix**:
- Added `_expansions_cache` and `_expansions_cache_time` class variables
- Created `_get_expansions_cached()` method that caches expansions for 1 hour
- Cache maps set codes to expansion IDs for fast lookups
- Reduces API calls from N (one per card) to 1 per hour

**Files Changed**:
- `backend/app/services/ingestion/adapters/cardtrader.py`

### 4. Improved Blueprint Matching ✅
**Issue**: Matching logic was too simplistic and might miss valid matches.

**Fix**:
- Implemented scoring system for matches:
  - Exact name match: 100 points
  - Partial name match: 50 points
  - Collector number match: +30 points bonus
  - Collector number mismatch: -20 points penalty
- Returns best match with score >= 50
- Immediate return for perfect matches (score >= 130)

**Files Changed**:
- `backend/app/services/ingestion/adapters/cardtrader.py`

## TCGPlayer API Fixes

### 1. Improved Product Matching ✅
**Issue**: Code was returning first result without proper validation, and set code wasn't being used effectively.

**Fix**:
- Implemented scoring system similar to CardTrader:
  - Exact name match: 100 points
  - Partial name match: 50 points
  - Collector number match: +50 points bonus
  - Collector number mismatch: -30 points penalty
- Returns best match with score >= 50
- Immediate return for perfect matches (score >= 150)
- Better logging with match scores

**Note**: TCGPlayer uses `groupId` (numeric) for sets, not set codes. We can't directly match set codes, but improved name + collector matching helps.

**Files Changed**:
- `backend/app/services/ingestion/adapters/tcgplayer.py`

### 2. Added Retry Logic ✅
**Issue**: No retry logic for transient failures (network errors, 5xx errors).

**Fix**:
- Added `max_retries` parameter (default: 3)
- Exponential backoff: 1s, 2s, 4s
- Retries on:
  - Network errors (`httpx.NetworkError`)
  - Timeout errors (`httpx.TimeoutException`)
  - 5xx server errors
- Automatic token refresh on 401 errors (already existed, now more robust)

**Files Changed**:
- `backend/app/services/ingestion/adapters/tcgplayer.py`

## Documentation References

All fixes are based on official API documentation:

- **CardTrader**: https://www.cardtrader.com/docs/api/full/reference
  - Rate limit: "200 requests per 10 seconds"
  - Blueprints endpoint: `GET /blueprints/export?expansion_id={id}`
  - Expansions endpoint: `GET /expansions` (returns array)

- **TCGPlayer**: https://docs.tcgplayer.com/reference/pricing
  - Rate limit: 100 requests per minute (unchanged)
  - Pricing endpoint: `GET /pricing/product/{productId}` (unchanged)

## Expected Improvements

1. **Performance**: 
   - CardTrader expansion caching reduces API calls significantly
   - Better rate limiting prevents hitting limits

2. **Accuracy**:
   - Improved matching reduces false positives
   - Better scoring ensures correct products/blueprints are selected

3. **Reliability**:
   - Retry logic handles transient failures
   - Better error handling and logging

4. **Compliance**:
   - Rate limits now match API documentation
   - Endpoints match API specification

## Testing Recommendations

1. **CardTrader**:
   - Test with cards from different sets
   - Verify expansion cache is working (check logs)
   - Test rate limiting doesn't cause issues
   - Verify blueprint matching finds correct cards

2. **TCGPlayer**:
   - Test with cards that exist in multiple sets
   - Verify matching selects correct product
   - Test retry logic with network issues
   - Verify token refresh works correctly

## Migration Notes

No database migrations required. These are code-only changes.

The adapters will automatically:
- Use new rate limits on next run
- Cache expansions on first card lookup
- Use improved matching immediately
- Retry failed requests automatically

## Next Steps

1. Monitor logs for any issues with new matching logic
2. Verify data quality improves (correct products/blueprints)
3. Check rate limiting is working correctly
4. Monitor API quota usage (should be more efficient)

