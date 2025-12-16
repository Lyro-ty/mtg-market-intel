# Potential Issues with TCGPlayer and CardTrader API Integrations

This document identifies specific bugs and potential issues that could prevent data from populating.

## 🔴 Critical Issues

### 1. **TCGPlayer: Set Code Not Used in Product Matching** (BUG)

**Location**: `backend/app/services/ingestion/adapters/tcgplayer.py:252-267`

**Problem**: The `_find_product_id` method retrieves `groupId` (set identifier) but **never uses it** to match against the `set_code` parameter. This means:

- If the same card name exists in multiple sets, it might return the wrong product
- The first matching card name is returned regardless of set
- This can cause incorrect pricing data to be stored

**Current Code**:
```python
# Line 256: Gets groupId but never uses it!
product_set = product.get("groupId")  # TCGPlayer uses groupId for sets

# Line 259: Only matches by name, ignores set_code
if card_name.upper() in product_name or product_name in card_name.upper():
    # Returns product without checking if set matches
    return product.get("productId")
```

**Impact**: High - Can cause wrong prices for cards with same name in different sets (e.g., "Lightning Bolt" in multiple sets).

**Fix Needed**: Add set matching logic using `groupId`. However, this requires mapping TCGPlayer `groupId` to our `set_code`, which may not be straightforward.

---

### 2. **CardTrader: Expansion Lookup Not Cached** (Performance Issue)

**Location**: `backend/app/services/ingestion/adapters/cardtrader.py:130-171`

**Problem**: The expansion (set) lookup happens **on every single card fetch**. This means:

- For 1000 cards, it makes 1000+ API calls to `/expansions`
- This is extremely inefficient and slow
- Rate limiting will be hit frequently
- API quota will be consumed quickly

**Current Flow**:
```
For each card:
  1. Call GET /expansions (1000+ times!)
  2. Find expansion by set_code
  3. Call GET /blueprints?expansion_id=X
  4. Match card by name
```

**Impact**: High - Causes excessive API calls, slow performance, and potential rate limit issues.

**Fix Needed**: Cache expansion list in memory or database, refresh periodically (e.g., once per hour).

---

### 3. **CardTrader: Currency Filtering Too Strict**

**Location**: `backend/app/services/ingestion/adapters/cardtrader.py:350-365`

**Problem**: If a product doesn't have currency information in the expected format, it's **silently skipped**:

```python
# If no currency info, skip (can't verify)
# Line 365: Products without currency are discarded
```

This means:
- Products with valid prices but missing currency fields are ignored
- If API response format changes, all products might be filtered out
- No fallback to default currency

**Impact**: Medium - May cause valid products to be missed if API response format differs.

**Fix Needed**: Add fallback logic or better error handling when currency is missing.

---

## 🟡 Medium Priority Issues

### 4. **TCGPlayer: Fallback to First Result Without Validation**

**Location**: `backend/app/services/ingestion/adapters/tcgplayer.py:269-276`

**Problem**: If no exact match is found, the code returns the **first result** without any validation:

```python
# If no exact match, return first result
if results:
    return results[0].get("productId")  # Could be completely wrong card!
```

**Impact**: Medium - Can return wrong product if search returns multiple results.

**Fix Needed**: Add validation or return None if no good match found.

---

### 5. **CardTrader: Blueprint Pagination May Miss Data**

**Location**: `backend/app/services/ingestion/adapters/cardtrader.py:203-214`

**Problem**: The pagination logic has multiple exit conditions that might cause early termination:

```python
# Check if there are more pages
if isinstance(blueprints_data, dict):
    has_more = blueprints_data.get("has_more", False)
    total = blueprints_data.get("total")
    if not has_more or (total and len(blueprints) >= total):
        break  # Might exit too early if API doesn't report has_more correctly
```

**Impact**: Medium - May miss cards if API pagination metadata is incorrect.

**Fix Needed**: More robust pagination logic with better validation.

---

### 6. **Both: Error Handling Swallows Important Errors**

**Location**: Multiple locations in both adapters

**Problem**: Exceptions are caught and logged, but the actual error details might not be sufficient:

```python
except Exception as e:
    logger.warning("Error finding TCGPlayer product ID", error=str(e))
    return None  # Returns None, caller doesn't know why it failed
```

**Impact**: Medium - Makes debugging difficult when things go wrong.

**Fix Needed**: More detailed error logging, including response bodies for API errors.

---

### 7. **TCGPlayer: No Retry Logic for Transient Failures**

**Location**: `backend/app/services/ingestion/adapters/tcgplayer.py:180-214`

**Problem**: If an API call fails (network error, 500 error, etc.), it fails immediately without retry:

```python
response = await client.request(method, endpoint, **kwargs)
# If 401, retry once. But no retry for 500, 503, network errors, etc.
```

**Impact**: Medium - Transient failures cause permanent data gaps.

**Fix Needed**: Add retry logic with exponential backoff for 5xx errors and network failures.

---

### 8. **CardTrader: No Validation of API Response Structure**

**Location**: `backend/app/services/ingestion/adapters/cardtrader.py:132-142`

**Problem**: The code assumes API responses are in a specific format, but doesn't validate:

```python
if isinstance(expansions_data, dict) and "data" in expansions_data:
    expansions = expansions_data["data"]
elif isinstance(expansions_data, list):
    expansions = expansions_data
else:
    expansions = []  # Silently fails if format is unexpected
```

**Impact**: Low-Medium - If API changes response format, code fails silently.

**Fix Needed**: Add validation and better error messages for unexpected formats.

---

## 🟢 Low Priority Issues

### 9. **Both: Rate Limiting May Not Be Accurate**

**Location**: Both adapters have rate limiting logic

**Problem**: Rate limiting uses time-based windows, but:
- Clock skew between requests might cause issues
- Concurrent requests might not be properly limited
- Rate limit windows might reset at wrong times

**Impact**: Low - May cause occasional rate limit violations.

---

### 10. **CardTrader: Language Filter May Not Work**

**Location**: `backend/app/services/ingestion/adapters/cardtrader.py:327`

**Problem**: The API is called with `language=en` parameter, but:
- API documentation might not support this parameter
- If unsupported, all languages are returned and filtered client-side
- This wastes bandwidth and processing

**Impact**: Low - Inefficient but functional.

---

### 11. **TCGPlayer: Token Refresh Logic May Have Race Condition**

**Location**: `backend/app/services/ingestion/adapters/tcgplayer.py:204-212`

**Problem**: If multiple requests happen simultaneously and token expires:
- Multiple token refresh requests might be made
- No locking mechanism to prevent concurrent refreshes

**Impact**: Low - May cause extra API calls but shouldn't break functionality.

---

## 🔍 Debugging Recommendations

### Check These First:

1. **Verify API Credentials Are Actually Being Used**
   ```python
   # Add to ingestion task
   logger.info("TCGPlayer credentials check", 
               has_key=bool(settings.tcgplayer_api_key),
               has_secret=bool(settings.tcgplayer_api_secret),
               key_prefix=settings.tcgplayer_api_key[:5] if settings.tcgplayer_api_key else None)
   ```

2. **Test Authentication Separately**
   ```python
   # Test TCGPlayer auth
   adapter = TCGPlayerAdapter()
   token = await adapter._get_auth_token()
   print(f"Token obtained: {bool(token)}")
   
   # Test CardTrader (token should already be set)
   adapter = CardTraderAdapter()
   client = await adapter._get_client()
   response = await client.get("/expansions")
   print(f"CardTrader test: {response.status_code}")
   ```

3. **Check for Silent Failures**
   - Look for cards that should have data but don't
   - Check logs for "product not found" or "blueprint not found" messages
   - Verify if errors are being swallowed

4. **Verify Set Code Matching**
   - Test with a card that exists in multiple sets
   - Check if the wrong set's price is being returned
   - Verify TCGPlayer groupId mapping

5. **Monitor API Response Formats**
   - Log actual API responses for failed cases
   - Check if response structure matches expectations
   - Verify currency fields are present in CardTrader responses

---

## 🛠️ Quick Fixes to Try

### Fix 1: Add Set Code Validation to TCGPlayer (Partial Fix)

```python
# In _find_product_id, after line 256
product_set = product.get("groupId")

# Add validation (requires groupId to set_code mapping)
# For now, at least log when set doesn't match
if product_set:
    # TODO: Map groupId to set_code for proper validation
    logger.debug("Product set groupId", group_id=product_set, set_code=set_code)
```

### Fix 2: Cache CardTrader Expansions

```python
# Add class-level cache
class CardTraderAdapter(MarketplaceAdapter):
    _expansions_cache: dict[str, int] | None = None
    _expansions_cache_time: datetime | None = None
    
    async def _get_expansion_id_cached(self, set_code: str) -> int | None:
        # Refresh cache every hour
        if (self._expansions_cache is None or 
            self._expansions_cache_time is None or
            (datetime.utcnow() - self._expansions_cache_time).total_seconds() > 3600):
            # Fetch and cache expansions
            ...
        
        return self._expansions_cache.get(set_code.upper())
```

### Fix 3: Better Error Logging

```python
# Add response body to error logs
except httpx.HTTPStatusError as e:
    error_body = ""
    try:
        error_body = e.response.text[:500]  # First 500 chars
    except:
        pass
    logger.error(
        "TCGPlayer API error",
        status=e.response.status_code,
        url=str(e.request.url),
        error_body=error_body,
        card_name=card_name
    )
```

---

## 📊 Expected Behavior vs Actual

### TCGPlayer Expected Flow:
1. ✅ Authenticate → Get Bearer token
2. ❌ Search products → **Should filter by set, but doesn't**
3. ✅ Get pricing → Should work if product ID is correct
4. ✅ Save to database → Should work

### CardTrader Expected Flow:
1. ✅ Use JWT token → Should work
2. ❌ Find expansion → **Happens on every card (inefficient)**
3. ✅ Find blueprint → Should work
4. ✅ Get products → Should work, but currency filtering might be too strict
5. ✅ Save to database → Should work

---

## 🎯 Most Likely Causes of No Data

Based on the issues above, here are the most likely reasons data isn't populating:

1. **TCGPlayer**: Wrong products being matched (due to missing set validation) → Wrong or no prices
2. **CardTrader**: Expansion lookup failing or taking too long → No blueprints found
3. **CardTrader**: Currency filtering too strict → Products filtered out even if they exist
4. **Both**: API credentials not actually being loaded from environment
5. **Both**: Errors being silently swallowed → No indication of what's wrong

---

## Next Steps

1. **Immediate**: Add detailed logging to see what's actually happening
2. **Short-term**: Fix the TCGPlayer set matching issue
3. **Short-term**: Cache CardTrader expansions
4. **Medium-term**: Add retry logic and better error handling
5. **Long-term**: Add integration tests for both adapters

