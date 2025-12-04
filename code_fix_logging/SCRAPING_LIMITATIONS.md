# Web Scraping Limitations & Solutions

## Current Status

All three marketplace scrapers are experiencing issues due to modern web architecture:

### TCGPlayer
- **Issue**: Search results are JavaScript-rendered
- **Symptom**: "No product links found on TCGPlayer search page"
- **Root Cause**: Product links are loaded via JavaScript after initial page load
- **Impact**: Cannot extract individual seller listings

### Cardmarket
- **Issue**: HTTP 403 Forbidden errors
- **Symptom**: "HTTP error fetching page", status: 403
- **Root Cause**: Bot detection/anti-scraping measures
- **Impact**: Cannot access Cardmarket pages

### Card Kingdom
- **Issue**: Similar JavaScript rendering
- **Impact**: May not find listings on search pages

## Why This Happens

Modern e-commerce sites use:
1. **JavaScript rendering** - Content loaded dynamically after page load
2. **Bot detection** - Blocks automated requests
3. **Rate limiting** - Prevents bulk scraping
4. **Dynamic selectors** - HTML structure changes frequently

Our current scraping approach uses `selectolax` which only parses static HTML. It cannot execute JavaScript, so dynamically loaded content is invisible.

## Solutions

### Option 1: Use Official APIs (Recommended)
**Best long-term solution**

- **TCGPlayer API**: Requires API credentials
  - Provides structured data
  - More reliable than scraping
  - Rate limits but no blocking
  
- **Cardmarket API**: Requires API credentials
  - Official API access
  - Structured data format
  - Better than scraping

**Implementation**: Add API adapters alongside scrapers

### Option 2: Headless Browser (Complex)
**Use Selenium/Playwright to execute JavaScript**

Pros:
- Can access JavaScript-rendered content
- More reliable for modern sites

Cons:
- Much slower (browser overhead)
- Higher resource usage
- More complex to maintain
- Still vulnerable to bot detection

**Implementation**: Would require adding `playwright` or `selenium` to dependencies

### Option 3: Accept Limitations (Current Approach)
**Use Scryfall price data as primary source**

- Scryfall already aggregates prices from TCGPlayer and Cardmarket
- We get price snapshots (which work)
- Individual listings are a "nice to have" but not critical
- Focus on price trends rather than individual listings

**Current Status**: 
- ✅ Price snapshots work (via Scryfall)
- ❌ Individual listings don't work (JavaScript-rendered)

### Option 4: Hybrid Approach
**Combine Scryfall + Limited Scraping**

1. Use Scryfall for price data (reliable)
2. Try scraping for listings (may fail)
3. When scraping fails, create "virtual" listings from Scryfall price data
4. Document that listings are estimates, not actual seller listings

## Recommendations

### Short Term
1. **Accept that listings are optional** - Price snapshots are the primary data source
2. **Use Scryfall data** - Already working and reliable
3. **Document limitations** - Make it clear that listings may not always be available

### Medium Term
1. **Get API credentials** - TCGPlayer and Cardmarket offer APIs
2. **Implement API adapters** - More reliable than scraping
3. **Keep scrapers as fallback** - For when APIs are unavailable

### Long Term
1. **Consider headless browser** - Only if APIs aren't available
2. **Focus on price data** - Individual listings are less critical for market intelligence
3. **Use MTGJSON** - For historical price data (already implemented)

## Current Workaround

The system already works with:
- ✅ **Price snapshots** from Scryfall (aggregated marketplace prices)
- ✅ **Historical prices** from MTGJSON
- ✅ **Price trends** and analytics

Individual listings are a bonus feature, but the core functionality (price tracking, trends, recommendations) works without them.

## Next Steps

1. **Test if APIs are available** - Check if you have/can get TCGPlayer/Cardmarket API access
2. **Decide priority** - Are individual listings critical, or is price data enough?
3. **Consider alternatives** - Use Scryfall + MTGJSON as primary data sources

