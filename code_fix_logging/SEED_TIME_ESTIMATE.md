# Seed Process Time Estimate

## Rate Limits

### Scryfall
- **Rate Limit**: 75ms between requests (~13.3 requests/second)
- **Phase**: Current prices (Phase 2)
- **API Calls**: 1 per card

### MTGJSON
- **Rate Limit**: 1 second between requests (1 request/second)
- **Phase**: Historical prices (Phase 3)
- **API Calls**: Downloads AllPrintings.json.gz once (~30-60 seconds), then processes cards from memory
- **Note**: After initial download, card lookups are from cached data (no additional API calls)

### CardTrader (Optional)
- **Rate Limit**: 200 requests per 10 seconds (~20 requests/second, ~0.05s between requests)
- **Phase**: Current prices (Phase 4)
- **API Calls**: 1 per card (if API token configured)

## Time Estimates

### Small Database (100-1,000 cards)

**Phase 2: Scryfall Current Prices**
- 1,000 cards × 0.075s = **75 seconds (~1.25 minutes)**

**Phase 3: MTGJSON Historical**
- Download AllPrintings.json.gz: **30-60 seconds**
- Process 1,000 cards from cache: **~30-60 seconds** (no rate limit after download)
- **Total: ~1-2 minutes**

**Phase 4: CardTrader (if enabled)**
- 1,000 cards × 0.05s = **50 seconds (~0.8 minutes)**

**Total Estimated Time: 3-5 minutes**

---

### Medium Database (1,000-10,000 cards)

**Phase 2: Scryfall Current Prices**
- 10,000 cards × 0.075s = **750 seconds (~12.5 minutes)**

**Phase 3: MTGJSON Historical**
- Download AllPrintings.json.gz: **30-60 seconds**
- Process 10,000 cards from cache: **~5-10 minutes** (no rate limit after download)
- **Total: ~6-11 minutes**

**Phase 4: CardTrader (if enabled)**
- 10,000 cards × 0.05s = **500 seconds (~8.3 minutes)**

**Total Estimated Time: 27-32 minutes**

---

### Large Database (10,000-50,000 cards)

**Phase 2: Scryfall Current Prices**
- 50,000 cards × 0.075s = **3,750 seconds (~62.5 minutes = ~1 hour)**

**Phase 3: MTGJSON Historical**
- Download AllPrintings.json.gz: **30-60 seconds**
- Process 50,000 cards from cache: **~25-50 minutes** (no rate limit after download)
- **Total: ~26-51 minutes**

**Phase 4: CardTrader (if enabled)**
- 50,000 cards × 0.05s = **2,500 seconds (~41.7 minutes)**

**Total Estimated Time: 2-2.5 hours**

---

### Very Large Database (50,000+ cards)

**Phase 2: Scryfall Current Prices**
- 100,000 cards × 0.075s = **7,500 seconds (~125 minutes = ~2 hours)**

**Phase 3: MTGJSON Historical**
- Download AllPrintings.json.gz: **30-60 seconds**
- Process 100,000 cards from cache: **~50-100 minutes** (no rate limit after download)
- **Total: ~51-101 minutes**

**Phase 4: CardTrader (if enabled)**
- 100,000 cards × 0.05s = **5,000 seconds (~83.3 minutes = ~1.4 hours)**

**Total Estimated Time: 4-5 hours**

---

## Factors That Affect Time

1. **Number of Cards**: Linear relationship - more cards = more time
2. **Network Speed**: Affects MTGJSON download time
3. **Database Performance**: Write speed affects total time
4. **CardTrader**: Only runs if API token is configured
5. **Error Handling**: Failed requests may add retry delays
6. **Database Flushes**: Periodic flushes (every 100 cards) add small overhead

## Monitoring Progress

The seed process logs progress:
- Every 100 cards processed in Phase 2
- Every batch in Phase 3 (batch size: 50 cards)
- Summary at completion

Check logs for:
- `"Phase 2: Collecting current prices from Scryfall"`
- `"Phase 3: Matching MTGJSON cards to Scryfall cards"`
- `"Phase 4: Collecting current prices from CardTrader"` (if enabled)
- `"Comprehensive price data seeding completed"`

## Optimization Tips

1. **Start with fewer cards**: If you have many cards, consider seeding a subset first
2. **Run during off-peak hours**: The process is resource-intensive
3. **Monitor Celery workers**: Ensure workers have enough resources
4. **Check database connection pool**: Large databases may need larger pool sizes

## Typical Scenarios

- **Development/Testing**: 100-1,000 cards → **3-5 minutes**
- **Production (Standard)**: 10,000-30,000 cards → **30-90 minutes**
- **Production (Large)**: 50,000+ cards → **2-5 hours**

The seed process runs asynchronously in the background, so your API remains available during seeding.

