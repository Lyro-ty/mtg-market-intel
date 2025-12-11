# Ingestion/RAG Implementation Plan

## Overview
Comprehensive plan to fix bugs, expand vectorization, and implement RAG retrieval for 105k cards with 3-5ms search performance.

## Current State Analysis

### ✅ What's Working
- Scryfall bulk data download (needs streaming parser fix)
- CardTrader API adapter exists
- Basic vectorization (card attributes only)
- PostgreSQL storage

### ❌ What Needs Fixing
1. **CardTrader not showing in charts** - Marketplace mapping issue
2. **No RAG retrieval** - Vectors created but not used
3. **Limited vectorization** - Only card attributes, missing price history/signals
4. **Synthetic backfill data** - Should use real MTGJSON data
5. **Race conditions** - Multiple tasks can create duplicate snapshots
6. **Memory issues** - Bulk data loads entire file into memory
7. **Missing APIs** - Manapool adapter needed
8. **No tournament/news data** - Need to find and integrate sources

## Implementation Phases

### Phase 1: Critical Bug Fixes (Priority 1)
**Goal**: Fix existing issues before expanding

1. **Fix CardTrader chart display**
   - Verify marketplace slug mapping
   - Check chart query filters
   - Ensure CardTrader snapshots are included in chart data

2. **Fix Scryfall bulk data processing**
   - Replace memory-intensive JSON parsing with ijson streaming
   - Process cards in batches without loading entire file
   - Filter to physical cards only (exclude MTGO)

3. **Remove synthetic backfill**
   - Remove `_backfill_historical_snapshots_for_charting` synthetic data
   - Ensure MTGJSON 30-day history is properly used
   - Use interpolation in chart endpoints for gaps

4. **Fix race conditions**
   - Add database-level unique constraints for snapshots
   - Use upsert patterns instead of check-then-insert
   - Add proper transaction boundaries

5. **Fix vectorization bugs**
   - Fix marketplace ID mapping (remove modulo)
   - Fix color parsing (handle JSON string vs list)
   - Fix price normalization (handle >$22k cards)

### Phase 2: Data Source Integration (Priority 2)
**Goal**: Add missing APIs and data sources

1. **Create Manapool API adapter**
   - Research Manapool API documentation
   - Create adapter following existing pattern
   - Integrate into price collection tasks

2. **Add TCGPlayer API integration**
   - User will configure credentials
   - Create/update adapter for listings
   - Integrate into collection pipeline

3. **Find and integrate tournament/news sources**
   - Research available APIs:
     - MTGGoldfish tournament results
     - MTGTop8 tournament data
     - Reddit r/mtgfinance API
     - Twitter/X API for news
     - RSS feeds from MTG sites
   - Create data models for tournament/news
   - Create ingestion tasks

4. **Fix Scryfall bulk processing**
   - Filter to physical cards (exclude digital)
   - Process only USD/EUR prices (exclude TIX)
   - Use streaming parser for large files

### Phase 3: Expand Vectorization (Priority 3)
**Goal**: Include all data in vectors for comprehensive RAG

1. **Add price history to vectors**
   - Include 30-day time-series (daily prices)
   - Normalize and aggregate (min/max/avg/trend)
   - Add volatility metrics
   - Add momentum indicators

2. **Add market signals to vectors**
   - Include all signal types (momentum, volatility, trend)
   - Add signal confidence scores
   - Include signal timestamps

3. **Add popularity metrics**
   - Tournament play frequency
   - News mentions count
   - Search frequency (if available)
   - Inventory ownership count

4. **Add tournament/news embeddings**
   - Embed tournament results text
   - Embed news article summaries
   - Include relevance scores

5. **Update vector dimensions**
   - Current: ~395 dims (card attributes)
   - Expanded: ~1000+ dims (with price history + signals)
   - Consider separate vectors for different use cases

### Phase 4: RAG Retrieval Implementation (Priority 4)
**Goal**: Fast similarity search (3-5ms) for 105k cards

1. **Add pgvector extension**
   - Install pgvector in PostgreSQL
   - Create migration to add vector column
   - Add HNSW index for fast search

2. **Create retrieval service**
   - Similarity search by card ID
   - Semantic search by query text
   - Weighted similarity (text vs numerical features)
   - Filter by set, rarity, price range, etc.

3. **Add API endpoints**
   - `/api/cards/{card_id}/similar` - Find similar cards
   - `/api/cards/search` - Semantic search by any attribute
   - `/api/recommendations/{card_id}/similar` - Similar cards for recommendations

4. **Integrate into recommendations**
   - Use vector similarity as confidence signal
   - Find similar cards and use their price history
   - Combine with existing signals

5. **Optimize for 3-5ms performance**
   - Use HNSW index in pgvector
   - Cache frequently accessed vectors
   - Batch similarity queries when possible

### Phase 5: Search Integration (Priority 5)
**Goal**: Semantic search in frontend search bars

1. **Backend search endpoint**
   - `/api/cards/search?q={query}`
   - Search by any card attribute
   - Return ranked results with similarity scores

2. **Frontend integration**
   - Update landing page search
   - Update cards page search
   - Update inventory search
   - Add autocomplete/suggestions

## Technical Decisions

### Vector Storage
- **Primary**: PostgreSQL with pgvector extension
- **Reason**: Backportable, fast with HNSW, single database
- **Migration**: Add vector column to existing tables

### Vector Dimensions
- **Card Vector**: ~1000 dims (attributes + price history + signals)
- **Separate vectors**: Consider separate vectors for different search types
- **Text embedding**: Keep 384-dim from all-MiniLM-L6-v2

### Similarity Search
- **Method**: Cosine similarity on full vectors
- **Weighting**: Configurable weights for different feature groups
- **Index**: HNSW (Hierarchical Navigable Small World) in pgvector

### Performance Targets
- **Search latency**: 3-5ms for 105k cards
- **Batch processing**: 1000 cards per batch
- **Memory usage**: Stream large files, don't load entirely

## Implementation Order

1. **Week 1**: Phase 1 (Bug Fixes)
2. **Week 2**: Phase 2 (Data Sources)
3. **Week 3**: Phase 3 (Vector Expansion)
4. **Week 4**: Phase 4 (RAG Retrieval)
5. **Week 5**: Phase 5 (Search Integration)

## Success Metrics

- ✅ CardTrader data appears in charts
- ✅ No synthetic data in database
- ✅ All 105k cards have comprehensive vectors
- ✅ Similarity search < 5ms
- ✅ Semantic search works in all search bars
- ✅ Recommendations use vector similarity

