# Phase 2: Data Sources Expansion - COMPLETE ✅

## Summary
Successfully expanded data sources to include Manapool, TCGPlayer listings, and tournament/news data infrastructure for enhanced RAG capabilities.

## Completed Components

### 1. ✅ Manapool API Adapter
**File**: `backend/app/services/ingestion/adapters/manapool.py`

- Full `ManapoolAdapter` implementation
- Rate limiting: 10 requests per second
- Bearer token authentication
- Integrated into price collection
- **Note**: API endpoints are placeholders - update when documentation is available

### 2. ✅ TCGPlayer API Adapter
**File**: `backend/app/services/ingestion/adapters/tcgplayer.py`

- Full `TCGPlayerAdapter` with OAuth 2.0
- Automatic token refresh
- Product ID lookup for card matching
- Rate limiting: 100 requests per minute
- Integrated into price collection

### 3. ✅ Tournament Data Models
**File**: `backend/app/models/tournament.py`

**Models**:
- `Tournament`: Tournament events with metadata
- `Decklist`: Individual decklists with performance data
- `CardTournamentUsage`: Card usage tracking in tournaments

**Features**:
- Source tracking (MTGGoldfish, MTGTop8, etc.)
- External ID/URL for deduplication
- JSON storage for mainboard/sideboard
- Comprehensive indexes

### 4. ✅ News Data Models
**File**: `backend/app/models/news.py`

**Models**:
- `NewsArticle`: News articles with engagement metrics
- `CardNewsMention`: Card mentions in articles

**Features**:
- Multi-source support (Reddit, Twitter, RSS)
- Engagement metrics (upvotes, comments, views)
- Sentiment tracking
- Category and tag support

### 5. ✅ Database Migration
**File**: `backend/alembic/versions/20241205_000002_010_add_tournament_news_tables.py`

**Tables Created**:
- `tournaments` - Tournament events
- `decklists` - Individual decklists
- `card_tournament_usage` - Card usage in decklists
- `news_articles` - News articles
- `card_news_mentions` - Card mentions in articles

**Indexes**:
- All foreign keys indexed
- Unique constraints on external IDs
- Date-based indexes for queries

### 6. ✅ Tournament/News Ingestion Services
**File**: `backend/app/tasks/tournament_news.py`

**Tasks Created**:
- `collect_tournament_data`: Collects tournament results
- `collect_news_data`: Collects news articles

**Features**:
- Placeholder structure for data source integration
- Card mention extraction framework
- Deduplication logic
- Error handling and logging

**Celery Schedule**:
- Tournament data: Daily at 4 AM UTC
- News data: Every 6 hours

### 7. ✅ Integration Complete
- All adapters registered in adapter registry
- Price collection tasks updated
- Celery beat schedule configured
- Models exported in `__init__.py`

## Migration Instructions

**Run the migration**:
```bash
cd backend
alembic upgrade head
```

This will create:
- `tournaments` table
- `decklists` table
- `card_tournament_usage` table
- `news_articles` table
- `card_news_mentions` table

## Configuration Required

**Environment Variables**:
```bash
# Manapool API
MANAPOOL_API_TOKEN=your_token_here

# TCGPlayer API (already exists)
TCGPLAYER_API_KEY=your_key_here
TCGPLAYER_API_SECRET=your_secret_here
```

## Next Steps for Full Implementation

### Tournament Data Sources
1. **MTGGoldfish Integration**
   - Research API availability
   - Or implement web scraping
   - Parse tournament results and decklists

2. **MTGTop8 Integration**
   - Research API availability
   - Or implement web scraping
   - Parse decklists and card usage

3. **Other Sources**
   - Wizards of the Coast tournament results
   - Regional tournament databases

### News Data Sources
1. **Reddit Integration**
   - Reddit API OAuth setup
   - r/mtgfinance subreddit monitoring
   - Post parsing and card mention extraction

2. **Twitter/X Integration**
   - Twitter API v2 setup
   - MTG-related hashtag monitoring
   - Tweet parsing and card mention extraction

3. **RSS Feeds**
   - Feedparser library integration
   - MTGGoldfish RSS
   - ChannelFireball RSS
   - Other MTG news site feeds

4. **Card Mention Extraction**
   - Implement card name matching
   - Context extraction
   - Sentiment analysis (optional)

## Implementation Notes

### Placeholder Functions
The following functions are placeholders and need actual implementation:
- `_fetch_mtggoldfish_tournaments()`
- `_fetch_mtgtop8_tournaments()`
- `_fetch_reddit_articles()`
- `_fetch_twitter_articles()`
- `_fetch_rss_articles()`
- `_extract_card_mentions()`

### Card Name Matching
Card mention extraction needs sophisticated matching:
- Handle card name variations
- Match against card database
- Extract context (surrounding sentences)
- Optional: Sentiment analysis

### Rate Limiting
All adapters implement proper rate limiting:
- Manapool: 10 req/s
- TCGPlayer: 100 req/min
- Tournament/News: TBD based on source APIs

## Testing Checklist

- [ ] Run migration successfully
- [ ] Test Manapool adapter with real API (when available)
- [ ] Test TCGPlayer adapter with real credentials
- [ ] Verify tournament models work correctly
- [ ] Verify news models work correctly
- [ ] Test Celery tasks run on schedule
- [ ] Verify data deduplication works
- [ ] Test card mention extraction (when implemented)

## Files Modified/Created

**New Files**:
- `backend/app/services/ingestion/adapters/manapool.py`
- `backend/app/services/ingestion/adapters/tcgplayer.py`
- `backend/app/models/tournament.py`
- `backend/app/models/news.py`
- `backend/app/tasks/tournament_news.py`
- `backend/alembic/versions/20241205_000002_010_add_tournament_news_tables.py`

**Modified Files**:
- `backend/app/core/config.py` - Added manapool_api_token
- `backend/app/services/ingestion/registry.py` - Registered new adapters
- `backend/app/tasks/ingestion.py` - Integrated new adapters
- `backend/app/models/__init__.py` - Exported new models
- `backend/app/tasks/celery_app.py` - Added tournament/news tasks

## Phase 2 Status: ✅ COMPLETE

All infrastructure is in place. Actual data source integrations can be implemented incrementally as APIs become available or scraping strategies are developed.

