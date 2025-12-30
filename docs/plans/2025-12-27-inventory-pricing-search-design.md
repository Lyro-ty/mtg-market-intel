# Inventory, Pricing & Search System Redesign

**Date:** 2025-12-27
**Status:** ✅ Implemented (2025-12-28)
**Scope:** Refactor pricing ingestion, fix inventory valuations, add semantic search, integrate tournament data

---

## Problem Statement

The current inventory system has several issues:

1. **Top Gainers/Losers doesn't work** - Relies on stale `MetricsCardsDaily` table
2. **Value Index is meaningless** - Uses arbitrary first data point as base
3. **Stale pricing data** - `refresh_valuations` is manual, no fallback for missing data
4. **No condition/foil pricing** - Only "all conditions" shows data
5. **Complex ingestion pipeline** - Multiple overlapping adapters and tasks, unclear what works
6. **No tournament/meta data** - Missing competitive context for recommendations
7. **Basic search** - Text redirect only, no semantic understanding

---

## Solution Overview

### Pricing: Layered Freshness (Option B)

```
Every 12 hours (on startup + scheduled):
├── Download Scryfall bulk data (~500MB)
├── Update all 79k card prices (NM, foil/non-foil)
└── Recalculate all inventory valuations

Every 4 hours (inventory cards only):
├── Fetch fresh prices from Scryfall API
└── ~1000 cards = ~2 minutes at rate limit

Every 6 hours (condition pricing):
├── Fetch TCGPlayer prices for inventory cards > $5
└── Apply multipliers for cards ≤ $5
```

### Condition Pricing: Hybrid Approach

| Card Value | Source | Method |
|------------|--------|--------|
| > $5 | TCGPlayer API | Real market prices by condition |
| ≤ $5 | Calculated | Apply multipliers to NM price |

**Condition Multipliers (TCGPlayer standard):**
- Near Mint: 100%
- Lightly Played: 87%
- Moderately Played: 72%
- Heavily Played: 55%
- Damaged: 35%

---

## Data Flow

### Pricing Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                  PRICING DATA SOURCES                    │
└─────────────────────────────────────────────────────────┘

LAYER 1 - Bulk Baseline (Every 12 hours):
┌──────────────────┐
│ Scryfall Bulk    │──→ All 79k cards
│ default_cards    │    NM prices only (USD, EUR)
│ (~500MB)         │    Foil + Non-foil
└──────────────────┘

LAYER 2 - Inventory Refresh (Every 4 hours):
┌──────────────────┐
│ Scryfall API     │──→ Cards in user inventories only
│ /cards/:id       │    Fresh NM prices
│ (10 req/s)       │    ~2 min for 1000 cards
└──────────────────┘

LAYER 3 - Condition Pricing (Every 6 hours):
┌──────────────────┐
│ TCGPlayer API    │──→ Inventory cards > $5 value
│ (100 req/min)    │    Actual condition prices
└──────────────────┘
         │
         ▼
┌──────────────────┐
│ Condition        │──→ Cards ≤ $5 value
│ Multipliers      │    LP=87%, MP=72%, HP=55%, DMG=35%
└──────────────────┘
```

### Staleness Rules

| Data Age | Action |
|----------|--------|
| < 4 hours | Use cached |
| 4-12 hours | Queue for refresh |
| > 12 hours | Refresh on access |

---

## Inventory Valuations & Charts

### Valuation Calculation

Each `InventoryItem` gets valued based on its specific attributes:

```python
# Example inventory item
inventory_item:
  card_id: 12345
  quantity: 4
  condition: LIGHTLY_PLAYED
  is_foil: true

# Valuation logic
1. Get base price from latest price_snapshot (foil=true, NM)
2. Apply condition multiplier (LP = 0.87)
3. current_value = base_price × 0.87
4. total_value = current_value × quantity
5. profit_loss = (current_value - acquisition_price) × quantity
```

### Charts That Update Automatically

| Chart | Data Source | Updates When |
|-------|-------------|--------------|
| **Total Portfolio Value** | SUM(current_value × quantity) | Any price change |
| **Value Distribution** | Group by price buckets | Any price change |
| **Top Gainers** | Compare current vs 24h ago price | Price snapshot created |
| **Top Losers** | Compare current vs 24h ago price | Price snapshot created |
| **Condition Breakdown** | Group by condition, sum values | Valuation refresh |
| **Profit/Loss by Card** | current_value - acquisition_price | Any price change |

### Fixed Top Gainers/Losers

```python
# OLD (broken): Used stale MetricsCardsDaily
# NEW: Direct price_snapshot comparison

def get_top_movers(user_id, window="24h"):
    inventory_cards = get_user_inventory_card_ids(user_id)

    now_prices = get_latest_prices(inventory_cards)
    past_prices = get_prices_at(inventory_cards, now - window)

    changes = []
    for card_id in inventory_cards:
        if card_id in now_prices and card_id in past_prices:
            pct_change = (now - past) / past * 100
            changes.append((card_id, pct_change))

    gainers = sorted(changes, key=lambda x: x[1], reverse=True)[:5]
    losers = sorted(changes, key=lambda x: x[1])[:5]

    return {"gainers": gainers, "losers": losers}
```

### Fixed Value Index

```python
# OLD (broken): First data point as base → meaningless over time
# NEW: Acquisition cost as base → shows actual portfolio performance

index_value = (current_portfolio_value / total_acquisition_cost) × 100

# Example:
# - You spent $500 total on cards
# - They're now worth $650
# - Index = 130 (you're up 30%)
```

---

## Tournament Data Integration

### Data Model

```sql
Tournament
├── id (topdeck TID)
├── name
├── format (Modern, Pioneer, Standard, etc.)
├── date
├── player_count
├── location (city, venue, coordinates)
├── swiss_rounds, top_cut_size
└── topdeck_url (for attribution link)

TournamentStanding
├── tournament_id (FK)
├── player_name
├── player_id (topdeck ID)
├── rank (final placement)
├── wins, losses, draws
├── win_rate
└── decklist_id (FK, nullable)

Decklist
├── id
├── tournament_id (FK)
├── player_id
├── archetype_name (inferred or provided)
└── created_at

DecklistCard
├── decklist_id (FK)
├── card_id (FK to cards table)
├── quantity
├── section (mainboard, sideboard, commander)
└── (composite PK: decklist_id, card_id, section)

CardMetaStats
├── card_id
├── format
├── period (7d, 30d, 90d)
├── deck_inclusion_rate  # % of decks running this card
├── avg_copies           # Average copies when included
├── top8_rate            # % of top 8 decks with this card
├── win_rate_delta       # Does this card correlate with winning?
└── updated_at
```

### Ingestion Schedule

```
Every 6 hours:
├── Fetch recent tournaments (last 7 days)
│   POST /v2/tournaments { game: "Magic: The Gathering", last: 7 }
│
├── For each tournament with decklists:
│   GET /v2/tournaments/{TID}/standings
│   └── Parse deckObj for card names/quantities
│
├── Match card names to cards table
│   └── Fuzzy match for slight naming differences
│
└── Calculate meta statistics:
    └── Card popularity by format (% of decks running card)
```

### Attribution Page

Route: `/tournaments`

Required attribution: `Data provided by <a href="https://topdeck.gg">TopDeck.gg</a>`

```
┌─────────────────────────────────────────────────────────┐
│  Tournament Results              Data provided by TopDeck.gg  │
├─────────────────────────────────────────────────────────┤
│  [Format Filter ▼] [Date Range ▼] [Search...]           │
├─────────────────────────────────────────────────────────┤
│  🏆 SCG Con Dallas - Modern (127 players)               │
│     Dec 21, 2024 · Dallas, TX                           │
│     1st: PlayerName - Boros Energy [View Decklist →]    │
│     2nd: PlayerName - 4c Omnath                         │
│     ...                                                 │
└─────────────────────────────────────────────────────────┘
```

---

## Semantic Search

### Card Fields for Embedding

**Existing fields:**
- `name`, `oracle_text`, `type_line`, `mana_cost`, `colors`, `color_identity`
- `power`, `toughness`, `rarity`, `legalities`

**New fields to add:**
```python
keywords: Mapped[Optional[str]]      # JSON array: ["Flying", "Haste", "Trample"]
flavor_text: Mapped[Optional[str]]   # For thematic searches
edhrec_rank: Mapped[Optional[int]]   # Commander popularity (lower = more popular)
reserved_list: Mapped[bool]          # Reserved List status
meta_score: Mapped[Optional[float]]  # Weighted tournament presence (0-100)
```

### Embedding Strategy

```
Text to embed (concatenated):
"{name}. {type_line}. {oracle_text}. Keywords: {keywords}. {flavor_text}"

Model: all-MiniLM-L6-v2 (already in use)
Dimension: 384
Storage: card_feature_vectors table (already exists)
```

### Search Use Cases

| Query | Matches On |
|-------|-----------|
| "cards like Lightning Bolt" | oracle_text similarity (direct damage) |
| "blue card draw" | colors + oracle_text ("draw") |
| "flying creatures under 3 mana" | keywords + type_line + cmc |
| "popular in Modern" | meta_score + legalities |
| "Reserved List investments" | reserved_list + price trends |

### Search Integration Across Pages

| Page | Scope | Behavior |
|------|-------|----------|
| **Landing** (`/`) | `cards` | Semantic search, instant results dropdown |
| **Cards** (`/cards`) | `cards` | Full search with filters |
| **Inventory** (`/inventory`) | `inventory` | Search only user's collection |
| **Card Detail** (`/cards/[id]`) | `cards` | "Similar cards" section |
| **Tournaments** (`/tournaments`) | `decklists` | Search decks by archetype, cards, player |

---

## Simplified Architecture

### What Gets Removed

```
DELETED - Complex/Broken Components:
├── app/services/ingestion/adapters/manapool.py    # Never implemented
├── app/services/ingestion/adapters/mtgjson.py     # Redundant with Scryfall
├── app/tasks/data_seeding.py                      # Overlapping tasks
├── MetricsCardsDaily dependency for valuations    # Use PriceSnapshot directly
├── Interpolation/gap-filling logic                # Unnecessary complexity
└── Multiple overlapping Celery schedules          # Consolidate
```

### New/Refactored Components

```
backend/
├── app/
│   ├── services/
│   │   ├── pricing/
│   │   │   ├── __init__.py
│   │   │   ├── bulk_import.py        # Scryfall bulk download + parse
│   │   │   ├── live_refresh.py       # Scryfall API for inventory cards
│   │   │   ├── condition_pricing.py  # TCGPlayer + multiplier logic
│   │   │   └── valuation.py          # Calculate inventory values
│   │   │
│   │   ├── search/
│   │   │   ├── __init__.py
│   │   │   ├── semantic.py           # Vector similarity search
│   │   │   ├── filters.py            # Keyword/attribute filtering
│   │   │   └── autocomplete.py       # Fast prefix matching
│   │   │
│   │   └── tournaments/
│   │       ├── __init__.py
│   │       ├── topdeck_client.py     # TopDeck.gg API client
│   │       ├── ingestion.py          # Fetch + parse tournaments
│   │       └── meta_stats.py         # Calculate card popularity
│   │
│   ├── tasks/
│   │   ├── pricing.py                # 3 tasks: bulk, inventory, conditions
│   │   ├── tournaments.py            # Tournament ingestion task
│   │   └── search.py                 # Embedding refresh task
│   │
│   └── api/routes/
│       ├── search.py                 # Unified search endpoint
│       └── tournaments.py            # Tournament/meta endpoints

frontend/
├── src/
│   ├── app/
│   │   └── tournaments/
│   │       └── page.tsx              # Tournament results + attribution
│   │
│   └── components/
│       └── search/
│           ├── SearchAutocomplete.tsx
│           └── SearchFilters.tsx
```

### Database Migrations

```sql
-- Add fields to cards table
ALTER TABLE cards ADD COLUMN keywords TEXT;
ALTER TABLE cards ADD COLUMN flavor_text TEXT;
ALTER TABLE cards ADD COLUMN edhrec_rank INTEGER;
ALTER TABLE cards ADD COLUMN reserved_list BOOLEAN DEFAULT FALSE;
ALTER TABLE cards ADD COLUMN meta_score FLOAT;

-- Tournament tables
CREATE TABLE tournaments (...);
CREATE TABLE tournament_standings (...);
CREATE TABLE decklists (...);
CREATE TABLE decklist_cards (...);
CREATE TABLE card_meta_stats (...);

-- Add source tracking to price_snapshots
ALTER TABLE price_snapshots ADD COLUMN source VARCHAR(20);
-- Values: 'bulk', 'api', 'tcgplayer', 'calculated'
```

---

## Task Scheduling

### New Celery Beat Schedule

```python
CELERY_BEAT_SCHEDULE = {

    # PRICING TASKS

    "pricing-bulk-refresh": {
        "task": "app.tasks.pricing.bulk_refresh",
        "schedule": crontab(hour="*/12"),  # Every 12 hours
        # Downloads Scryfall bulk data, updates all 79k cards
        # Also runs on startup if stale
    },

    "pricing-inventory-refresh": {
        "task": "app.tasks.pricing.inventory_refresh",
        "schedule": crontab(hour="*/4"),  # Every 4 hours
        # Fetches fresh Scryfall API prices for inventory cards only
    },

    "pricing-condition-refresh": {
        "task": "app.tasks.pricing.condition_refresh",
        "schedule": crontab(hour="*/6"),  # Every 6 hours
        # Fetches TCGPlayer condition prices for cards >$5
        # Applies multipliers for cards ≤$5
    },

    # TOURNAMENT TASKS

    "tournaments-ingest": {
        "task": "app.tasks.tournaments.ingest_recent",
        "schedule": crontab(hour="*/6"),  # Every 6 hours
        # Fetches last 7 days of tournaments from TopDeck.gg
    },

    # SEARCH TASKS

    "search-refresh-embeddings": {
        "task": "app.tasks.search.refresh_embeddings",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
        # Re-embeds cards that changed (incremental)
    },
}
```

### Startup Tasks

```python
async def startup():
    # Check if bulk data is stale (>12 hours old)
    last_bulk = await get_last_bulk_refresh_time()
    if last_bulk is None or (now - last_bulk) > timedelta(hours=12):
        bulk_refresh.delay()

    # Check for cards without embeddings
    unembedded_count = await count_cards_without_embeddings()
    if unembedded_count > 0:
        refresh_embeddings.delay()
```

### Task Flow

```
bulk_refresh (every 12h)
    │
    ├──→ Updates price_snapshots for all cards
    └──→ Triggers: inventory_valuation_update

inventory_refresh (every 4h)
    │
    ├──→ Gets card IDs from all user inventories
    ├──→ Fetches fresh prices from Scryfall API
    └──→ Triggers: inventory_valuation_update

condition_refresh (every 6h)
    │
    ├──→ Gets inventory cards with value > $5
    ├──→ Fetches TCGPlayer condition prices
    ├──→ Applies multipliers for cards ≤ $5
    └──→ Triggers: inventory_valuation_update

tournaments_ingest (every 6h)
    │
    ├──→ Fetches recent tournaments from TopDeck.gg
    ├──→ Matches decklist cards to cards table
    └──→ Updates cards.meta_score
```

### Removed Schedules

```
DELETED:
├── collect-price-data (every 5 min)
├── collect-inventory-prices (every 2 min)
├── import-mtgjson-historical (daily)
├── seed-comprehensive-data (every 6h)
├── download-scryfall-bulk (daily 2 AM)
├── sync-card-data (daily 2 AM)
└── bulk-vectorize-cards (daily 11 PM)
```

---

## API Endpoints

### Search API

```
GET /api/v1/search
    ?q=lightning bolt
    &scope=cards|inventory|all
    &filters[colors]=R
    &filters[format]=Modern
    &filters[type]=Instant
    &filters[cmc_min]=1
    &filters[cmc_max]=3
    &filters[price_min]=5
    &filters[price_max]=50
    &sort=relevance|price|name
    &limit=20
    &offset=0

GET /api/v1/search/autocomplete
    ?q=light
    &limit=5

GET /api/v1/cards/{id}/similar
    ?limit=10
```

### Pricing API

```
GET /api/v1/cards/{id}/prices
    ?conditions=all|NM|LP|MP
    &include_history=true

POST /api/v1/inventory/refresh
    # Force refresh prices for current user's inventory
```

### Inventory API

```
GET /api/v1/inventory/summary
GET /api/v1/inventory/top-movers?window=24h|7d
GET /api/v1/inventory/analytics
```

### Tournament API

```
GET /api/v1/tournaments
    ?format=Modern
    ?days=7
    ?min_players=32

GET /api/v1/tournaments/{id}
GET /api/v1/tournaments/{id}/decklists/{decklist_id}

GET /api/v1/meta/cards
    ?format=Modern
    ?period=30d

GET /api/v1/cards/{id}/meta
```

---

## Implementation Phases

### Phase 1: Core Pricing (Foundation)

1.1 Database migrations
- Add source column to price_snapshots
- Add new card fields (keywords, flavor_text, edhrec_rank, etc.)
- Create tournament tables

1.2 Pricing services
- `pricing/bulk_import.py`
- `pricing/live_refresh.py`
- `pricing/condition_pricing.py`
- `pricing/valuation.py`

1.3 Celery tasks
- `pricing.bulk_refresh`
- `pricing.inventory_refresh`
- `pricing.condition_refresh`

1.4 Fix inventory endpoints
- `/inventory/top-movers`
- `/inventory/summary`
- `/inventory/analytics`

1.5 Verify with tests

### Phase 2: Tournament Integration

2.1 TopDeck client
2.2 Tournament ingestion
2.3 API endpoints
2.4 Frontend tournaments page with attribution

### Phase 3: Semantic Search

3.1 Search services
3.2 Embedding refresh
3.3 API endpoints
3.4 Frontend SearchAutocomplete component
3.5 Update all search areas (landing, cards, inventory)

### Phase 4: Cleanup & Polish

4.1 Remove deprecated code
4.2 Add monitoring/alerts
4.3 Update documentation

---

## Summary

| Component | Current State | After Refactor |
|-----------|--------------|----------------|
| **Price Sources** | 5 adapters, unclear which work | 2 sources: Scryfall (bulk+API), TCGPlayer |
| **Update Frequency** | Multiple overlapping (2-30 min) | 3 clear tasks (4h/6h/12h) |
| **Top Gainers/Losers** | Broken (stale MetricsCardsDaily) | Works (direct price comparison) |
| **Value Index** | Meaningless (arbitrary base) | Meaningful (acquisition cost base) |
| **Condition Pricing** | No data | TCGPlayer + multipliers |
| **Search** | Basic text redirect | Semantic + autocomplete everywhere |
| **Tournament Data** | None | TopDeck.gg with attribution |
| **Task Count** | 7+ overlapping | 5 clear tasks |
