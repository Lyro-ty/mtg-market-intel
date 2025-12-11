# Pricing Update Time Breakdown

## Overview

This document provides a detailed breakdown of how long it takes to process all cards and update pricing information in the MTG Market Intel system.

## Processing Workflow

The system updates card pricing through two main tasks:

1. **`collect_price_data`** - Regular price collection (runs every 5 minutes)
2. **`seed_comprehensive_price_data`** - Comprehensive seeding (runs on startup or manually)

Both tasks follow a similar multi-phase approach:

### Phase 1: Card Selection
- Prioritizes inventory cards first
- Then processes cards without recent data (stale >24 hours)
- Finally processes cards with recent data

### Phase 2: Scryfall Current Prices
- Fetches current prices from Scryfall API
- Gets prices for multiple marketplaces: TCGPlayer (USD), Cardmarket (EUR), MTGO (TIX)
- Creates price snapshots for each marketplace/currency

### Phase 3: MTGJSON Historical Prices (Optional)
- Downloads AllPrintings.json.gz once (~30-60 seconds)
- Processes historical price data from cache (no additional API calls)
- Creates historical snapshots going back 30-90 days

### Phase 4: CardTrader Prices (Optional)
- Only runs if `CARDTRADER_API_TOKEN` is configured
- Fetches current prices from CardTrader API (European market)
- Creates price snapshots

## Rate Limits

### Scryfall API
- **Rate Limit**: 75ms between requests (configurable via `SCRYFALL_RATE_LIMIT_MS`)
- **Effective Rate**: ~13.3 requests/second
- **Concurrent Requests**: Limited to 5 concurrent requests (semaphore)
- **API Calls per Card**: 1 call per card (via `fetch_all_marketplace_prices`)
- **Retry Logic**: Exponential backoff on 429 errors (max 60s wait)

### MTGJSON
- **Initial Download**: 1 request to download AllPrintings.json.gz (~30-60 seconds)
- **After Download**: All processing is from cached data (no rate limit)
- **Processing Speed**: Limited by database write speed, not API rate limits

### CardTrader API (Optional)
- **Rate Limit**: 200 requests per 10 seconds (~20 requests/second)
- **Per-Request Delay**: 0.05 seconds between requests
- **API Calls per Card**: 1 call per card
- **Note**: Only runs if API token is configured

## Time Estimates by Card Count

### Small Database (100-1,000 cards)

**Phase 2: Scryfall Current Prices**
- 1,000 cards × 0.075s = **75 seconds (~1.25 minutes)**
- Note: With 5 concurrent requests, actual time may be slightly less

**Phase 3: MTGJSON Historical (if enabled)**
- Download AllPrintings.json.gz: **30-60 seconds**
- Process 1,000 cards from cache: **~30-60 seconds** (database writes)
- **Total: ~1-2 minutes**

**Phase 4: CardTrader (if enabled)**
- 1,000 cards × 0.05s = **50 seconds (~0.8 minutes)**

**Total Estimated Time:**
- Scryfall only: **~1.25 minutes**
- Scryfall + MTGJSON: **~2.5-3.5 minutes**
- All sources: **~3-4 minutes**

---

### Medium Database (1,000-10,000 cards)

**Phase 2: Scryfall Current Prices**
- 10,000 cards × 0.075s = **750 seconds (~12.5 minutes)**
- With concurrent requests: **~10-12 minutes** (estimated)

**Phase 3: MTGJSON Historical (if enabled)**
- Download AllPrintings.json.gz: **30-60 seconds**
- Process 10,000 cards from cache: **~5-10 minutes** (database writes)
- **Total: ~6-11 minutes**

**Phase 4: CardTrader (if enabled)**
- 10,000 cards × 0.05s = **500 seconds (~8.3 minutes)**

**Total Estimated Time:**
- Scryfall only: **~10-12 minutes**
- Scryfall + MTGJSON: **~16-23 minutes**
- All sources: **~24-31 minutes**

---

### Large Database (10,000-50,000 cards)

**Phase 2: Scryfall Current Prices**
- 50,000 cards × 0.075s = **3,750 seconds (~62.5 minutes = ~1 hour)**
- With concurrent requests: **~50-60 minutes** (estimated)

**Phase 3: MTGJSON Historical (if enabled)**
- Download AllPrintings.json.gz: **30-60 seconds**
- Process 50,000 cards from cache: **~25-50 minutes** (database writes)
- **Total: ~26-51 minutes**

**Phase 4: CardTrader (if enabled)**
- 50,000 cards × 0.05s = **2,500 seconds (~41.7 minutes)**

**Total Estimated Time:**
- Scryfall only: **~50-60 minutes (~1 hour)**
- Scryfall + MTGJSON: **~76-111 minutes (~1.3-1.9 hours)**
- All sources: **~118-153 minutes (~2-2.5 hours)**

---

### Very Large Database (50,000-100,000 cards)

**Phase 2: Scryfall Current Prices**
- 100,000 cards × 0.075s = **7,500 seconds (~125 minutes = ~2.1 hours)**
- With concurrent requests: **~100-120 minutes (~1.7-2 hours)** (estimated)

**Phase 3: MTGJSON Historical (if enabled)**
- Download AllPrintings.json.gz: **30-60 seconds**
- Process 100,000 cards from cache: **~50-100 minutes** (database writes)
- **Total: ~51-101 minutes (~0.9-1.7 hours)**

**Phase 4: CardTrader (if enabled)**
- 100,000 cards × 0.05s = **5,000 seconds (~83.3 minutes = ~1.4 hours)**

**Total Estimated Time:**
- Scryfall only: **~1.7-2 hours**
- Scryfall + MTGJSON: **~2.6-3.7 hours**
- All sources: **~4-5 hours**

---

### Extremely Large Database (100,000+ cards)

**Phase 2: Scryfall Current Prices**
- 200,000 cards × 0.075s = **15,000 seconds (~250 minutes = ~4.2 hours)**
- With concurrent requests: **~200-240 minutes (~3.3-4 hours)** (estimated)

**Phase 3: MTGJSON Historical (if enabled)**
- Download AllPrintings.json.gz: **30-60 seconds**
- Process 200,000 cards from cache: **~100-200 minutes** (database writes)
- **Total: ~101-201 minutes (~1.7-3.4 hours)**

**Phase 4: CardTrader (if enabled)**
- 200,000 cards × 0.05s = **10,000 seconds (~166.7 minutes = ~2.8 hours)**

**Total Estimated Time:**
- Scryfall only: **~3.3-4 hours**
- Scryfall + MTGJSON: **~5-7.4 hours**
- All sources: **~8-10 hours**

## Factors That Affect Processing Time

### 1. Number of Cards
- **Linear relationship**: More cards = proportionally more time
- Formula: `time = (card_count × rate_limit_seconds) / concurrent_requests`

### 2. Network Speed
- Affects MTGJSON bulk file download time (30-60 seconds typical)
- Can affect Scryfall API response times (usually minimal)

### 3. Database Performance
- Write speed affects total processing time
- Periodic flushes (every 100 cards) add small overhead
- Large databases may need larger connection pool sizes

### 4. API Rate Limits
- Scryfall: 75ms between requests (configurable)
- CardTrader: 200 requests per 10 seconds
- Rate limit violations trigger retries with exponential backoff (adds delay)

### 5. Error Handling
- Failed requests trigger retries (exponential backoff: 2^retry_count seconds)
- Maximum retry wait: 60 seconds
- Network errors add additional delays

### 6. Concurrent Processing
- Scryfall adapter uses semaphore to limit to 5 concurrent requests
- This allows some parallelization while respecting rate limits
- Actual speedup depends on network latency

### 7. Data Freshness Checks
- Cards with recent snapshots (<24 hours) may be skipped
- This reduces processing time for cards that don't need updates

### 8. CardTrader Availability
- Only runs if `CARDTRADER_API_TOKEN` is configured
- Some cards may not have CardTrader data (blueprint mapping may not exist)
- Non-fatal errors are logged but don't stop processing

## Optimization Strategies

### 1. Use Bulk Data Downloads
- Scryfall provides bulk data files that can be downloaded once
- Use `download_scryfall_bulk_data_task` for faster initial seeding
- Processes cards from downloaded file (no API rate limits)

### 2. Prioritize Inventory Cards
- The system already prioritizes inventory cards
- These are processed first and updated more frequently (every 2 minutes)

### 3. Stagger Processing
- Regular updates run every 5 minutes (not all cards at once)
- Only processes cards with stale data (>24 hours old)
- Reduces load and ensures fresh data for active cards

### 4. Run During Off-Peak Hours
- Large database updates are resource-intensive
- Schedule comprehensive seeding during low-traffic periods

### 5. Monitor Celery Workers
- Ensure workers have enough CPU and memory
- Multiple workers can process different card batches in parallel

### 6. Database Optimization
- Ensure proper indexes on `price_snapshots` table
- Consider larger connection pool for high-card-count databases
- Monitor database write performance

## Monitoring Progress

The system logs progress at key points:

### Phase 2 (Scryfall)
- Every 100 cards: `"Price collection progress"`
- Completion: `"Phase 2 complete: Current prices collected"`

### Phase 3 (MTGJSON)
- Every batch (50 cards): `"Historical batch complete"`
- Completion: `"Phase 3 complete: Historical prices collected"`

### Phase 4 (CardTrader)
- Every 100 cards: Flush to database
- Completion: `"Phase 4 complete: CardTrader prices collected"`

### Final Summary
- `"Comprehensive price data seeding completed"` with full statistics

## Typical Scenarios

### Development/Testing (100-1,000 cards)
- **Time**: 3-5 minutes (all sources)
- **Frequency**: Can run frequently without impact

### Production Standard (10,000-30,000 cards)
- **Time**: 30-90 minutes (all sources)
- **Frequency**: 
  - Regular updates: Every 5 minutes (stale cards only)
  - Comprehensive seeding: Daily or on-demand

### Production Large (50,000+ cards)
- **Time**: 2-5 hours (all sources)
- **Frequency**:
  - Regular updates: Every 5 minutes (stale cards only)
  - Comprehensive seeding: Weekly or on-demand
  - Consider using bulk data downloads for initial seeding

## Real-World Considerations

### Incremental Updates
- The system uses incremental updates (only stale cards)
- Most production runs process only a subset of cards
- Actual runtime is often much less than full database estimates

### Error Recovery
- Failed cards are logged but don't stop processing
- Retries happen automatically with exponential backoff
- Check logs for `"errors"` array in results

### Resource Usage
- CPU: Moderate (mostly I/O bound)
- Memory: Low to moderate (depends on batch sizes)
- Network: High (many API calls)
- Database: Moderate (many writes)

## Conclusion

Processing time scales linearly with the number of cards. For most production scenarios:

- **Small databases (<1,000 cards)**: Minutes
- **Medium databases (1,000-10,000 cards)**: 10-30 minutes
- **Large databases (10,000-50,000 cards)**: 1-2 hours
- **Very large databases (50,000+ cards)**: 2-5 hours

The system is designed to handle incremental updates efficiently, so regular runs typically process only a small subset of cards, keeping actual runtime much lower than full database estimates.


