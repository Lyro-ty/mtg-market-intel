# Phase 2: Data Sources Expansion - IN PROGRESS

## Summary
Expanding data sources to include Manapool, TCGPlayer listings, and tournament/news data for enhanced RAG capabilities.

## Completed

### 1. ✅ Manapool API Adapter
**File**: `backend/app/services/ingestion/adapters/manapool.py`

- Created `ManapoolAdapter` class implementing `MarketplaceAdapter` interface
- Supports `fetch_listings()`, `fetch_price()`, and `search_cards()` methods
- Rate limiting: 10 requests per second
- Authentication: Bearer token (configurable)
- **Note**: API endpoints are placeholders - actual API documentation needed to finalize

**Configuration**:
- Added `manapool_api_token` to `settings`
- Registered in adapter registry
- Integrated into price collection tasks

### 2. ✅ TCGPlayer API Adapter
**File**: `backend/app/services/ingestion/adapters/tcgplayer.py`

- Created `TCGPlayerAdapter` class with OAuth 2.0 authentication
- Implements client credentials flow for token management
- Supports `fetch_listings()`, `fetch_price()`, and `search_cards()` methods
- Rate limiting: 100 requests per minute
- Product ID lookup for card matching
- Automatic token refresh on expiration

**Configuration**:
- Uses existing `tcgplayer_api_key` and `tcgplayer_api_secret` from settings
- Registered in adapter registry
- Integrated into price collection tasks

### 3. ✅ Tournament Data Models
**File**: `backend/app/models/tournament.py`

**Models Created**:
- `Tournament`: Tournament events (Standard, Modern, Legacy, etc.)
  - Fields: name, event_type, format, location, organizer, dates, player count
  - Source tracking: MTGGoldfish, MTGTop8, etc.
  - External ID/URL for deduplication
  
- `Decklist`: Individual decklists from tournaments
  - Fields: player_name, deck_name, archetype, placement, record
  - Mainboard/sideboard stored as JSON
  - Links to tournament and cards
  
- `CardTournamentUsage`: Card usage in decklists
  - Tracks mainboard/sideboard quantities
  - Links cards to decklists for popularity metrics

**Indexes**:
- Tournament start_date, source, external_id+source (unique)
- Decklist tournament+placement
- CardTournamentUsage card+decklist (unique)

### 4. ✅ News Data Models
**File**: `backend/app/models/news.py`

**Models Created**:
- `NewsArticle`: News articles and market updates
  - Fields: title, summary, content, source, author, category, tags
  - Engagement metrics: upvotes, comments, views
  - Published date and external references
  
- `CardNewsMention`: Card mentions in articles
  - Tracks mention count and context
  - Sentiment analysis (positive/negative/neutral)
  - Links cards to articles for relevance tracking

**Indexes**:
- News published_at, source+external_id (unique), category
- CardNewsMention card+article (unique)

### 5. ✅ Integration into Price Collection
**File**: `backend/app/tasks/ingestion.py`

- Added Manapool price collection to `_collect_price_data_async()`
- Added TCGPlayer price collection to `_collect_price_data_async()`
- Created helper functions: `_get_or_create_manapool_marketplace()`, `_get_or_create_tcgplayer_marketplace()`
- Both adapters use upsert pattern to prevent race conditions
- Rate limiting and error handling implemented

## Pending

### 6. ⏳ Tournament Data Ingestion
**Needed**:
- Create ingestion service for tournament data
- Sources to integrate:
  - MTGGoldfish tournament results
  - MTGTop8 decklists
  - Other tournament result sources
- Parse decklists and extract card usage
- Link cards to tournaments via `CardTournamentUsage`

### 7. ⏳ News Data Ingestion
**Needed**:
- Create ingestion service for news articles
- Sources to integrate:
  - Reddit r/mtgfinance (via Reddit API or RSS)
  - Twitter/X mentions (via API)
  - MTG news sites (RSS feeds)
  - Other relevant sources
- Extract card mentions from articles
- Sentiment analysis for mentions
- Link cards to articles via `CardNewsMention`

### 8. ⏳ Database Migration
**Needed**:
- Create Alembic migration for new tables:
  - `tournaments`
  - `decklists`
  - `card_tournament_usage`
  - `news_articles`
  - `card_news_mentions`
- Add indexes as defined in models
- Test migration on development database

## Next Steps

1. **Create migration** for tournament/news models
2. **Implement tournament ingestion service** (MTGGoldfish/MTGTop8)
3. **Implement news ingestion service** (Reddit/Twitter/RSS)
4. **Add Celery tasks** for periodic tournament/news collection
5. **Test adapters** with actual API credentials
6. **Update vectorization** to include tournament/news data (Phase 3)

## Configuration Required

**Environment Variables**:
```bash
# Manapool API
MANAPOOL_API_TOKEN=your_token_here

# TCGPlayer API (already exists)
TCGPLAYER_API_KEY=your_key_here
TCGPLAYER_API_SECRET=your_secret_here
```

## Notes

- **Manapool API**: Actual API endpoints need to be verified and updated once documentation is available
- **TCGPlayer API**: OAuth flow is implemented, but product ID matching may need refinement
- **Tournament/News**: Ingestion services are placeholders - actual data sources need to be identified and integrated
- **Rate Limiting**: All adapters implement proper rate limiting to respect API limits

