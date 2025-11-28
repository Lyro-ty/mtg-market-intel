# MTG Market Intel

A production-ready web application for Magic: The Gathering card market intelligence, featuring:

- 📊 **Multi-marketplace price tracking** - Collects data from TCGPlayer, Cardmarket, Card Kingdom, and more
- 📈 **Price analytics & forecasting** - Moving averages, volatility, momentum indicators
- 🤖 **AI-powered recommendations** - Buy/Sell/Hold signals with clear rationales
- 📉 **Cross-market arbitrage detection** - Identify pricing discrepancies
- 🎯 **Modern web UI** - Dashboard, search, charts, and recommendations

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
│   Dashboard │ Card Search │ Recommendations │ Settings           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend API (FastAPI)                       │
│   REST Endpoints │ Authentication │ Rate Limiting                │
└─────────────────────────────────────────────────────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Ingestion      │  │  Analytics      │  │  Recommendation │
│  Agent          │  │  Agent          │  │  Agent          │
│  (Celery)       │  │  (Celery)       │  │  (Celery)       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                           │
│   Cards │ Listings │ Prices │ Metrics │ Signals │ Recommendations│
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy, Alembic
- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS, Recharts
- **Database**: PostgreSQL 16
- **Task Queue**: Celery + Redis
- **AI**: OpenAI/Anthropic API (with mock fallback)
- **Containerization**: Docker, docker-compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/mtg-market-intel.git
cd mtg-market-intel
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings (API keys are optional for demo)
```

### 3. Start the Application

```bash
docker compose up --build
```

This will:
- Start PostgreSQL database
- Start Redis
- Run database migrations
- Seed initial data (popular MTG cards)
- Start the FastAPI backend
- Start the Next.js frontend
- Start Celery workers and scheduler

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API**: http://localhost:8000

### Windows + WSL Notes

- Open your WSL distro (`wsl -d Ubuntu` for example) and run all `docker`/`make` commands there so the Linux Docker CLI can be found.
- If you need to launch a compose command from PowerShell, prefix it with `wsl -e`, e.g. `wsl -e docker compose up -d`.
- The repo is shared between Windows and WSL via `/mnt/c/...`, so you can edit files in Windows but build/run inside WSL without copying anything.

## Development

### Using Make Commands

```bash
# Start all services
make up

# Start with rebuild
make up-build

# Stop all services
make down

# View logs
make logs

# Run database migrations
make migrate

# Seed database
make seed

# Run tests
make test

# Access backend shell
make shell

# Trigger manual scrape
make trigger-scrape

# Trigger analytics
make trigger-analytics
```

### Running Tests

```bash
# Backend tests
make test-backend

# Frontend tests
make test-frontend

# Or manually:
docker compose exec backend pytest -v
docker compose exec frontend npm test
```

## Importing the Scryfall Database

The importer streams the bulk download so you can ingest 90k+ records without exhausting memory and it automatically detects gzipped payloads that Scryfall may return.

```bash
# Import one card per Oracle ID (~30k cards)
make import-scryfall

# Import every printing (~90k cards). Expect ~10-15 minutes depending on bandwidth.
make import-scryfall-all

# Increase the batch size for faster commits on beefier machines
make import-scryfall-all SCRYFALL_BATCH_SIZE=2000

# Re-use an existing download instead of pulling ~600MB again
docker compose exec backend python -m app.scripts.import_scryfall \
  --type all_cards --skip-download --batch-size 2000

# Limit imports to a specific language (defaults to English)
docker compose exec backend python -m app.scripts.import_scryfall \
  --type all_cards --language en

# Import all languages explicitly
docker compose exec backend python -m app.scripts.import_scryfall \
  --type all_cards --language ""
```

While the import is running you will see a `Processed: <n>` counter update in-place so you can monitor long jobs.

### Resetting the Database

To completely wipe Postgres (useful before re-importing with new flags):

```bash
# Stop services and delete volumes (removes the DB data directory)
docker compose down -v

# Bring services back up and re-run migrations/seeds
docker compose up -d db backend
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed_data
```

Alternatively, truncate the tables without dropping the volume:

```bash
docker compose exec db psql -U mtg_user -d mtg_market_intel <<'SQL'
TRUNCATE price_snapshots, listings, metrics_cards_daily, signals,
         recommendations, cards
RESTART IDENTITY CASCADE;
SQL
```

Then re-run the importer (e.g., `make import-scryfall-all --language en`).

### Restoring 30-day Demo Price History

The full Scryfall import only persists the card catalog (plus the current TCGPlayer/Cardmarket snapshot Scryfall exposes). The earlier 150-card demo dataset showed 30-day charts and Card Kingdom prices because the seed script generated synthetic history in addition to importing the cards.

Use the demo history generator after a bulk import to recreate that experience:

```bash
# Generate 30 days of synthetic history for 250 cards across all enabled marketplaces
make seed-demo-prices

# Target specific marketplaces and a larger card sample
make seed-demo-prices CARD_LIMIT=400 PRICE_HISTORY_DAYS=45 MARKETPLACES="tcgplayer cardmarket cardkingdom"
```

The script:
- backfills a rolling random-walk price curve for each card/marketplace pair
- includes Card Kingdom (and any other enabled marketplace) so UI comparisons stay populated
- purges overlapping snapshots for the selected cards before inserting fresh demo data (use `MARKETPLACES="..."` and `CARD_LIMIT` to keep the volume manageable)

You only need to run this in demo/dev environments. In production you would rely on the ingestion Celery tasks plus real marketplace adapters to accumulate organic history over time.

## API Endpoints

### Health Check
- `GET /health` - Service health status

### Cards
- `GET /cards/search?q=...` - Search cards by name
- `GET /cards/{id}` - Get card details
- `POST /cards/{id}/refresh` - Force a data refresh (prices, metrics, recommendations). The frontend detail page now includes a "Refresh data" button that calls this endpoint and shows when a background refresh is running.
- `GET /cards/{id}/prices` - Get current prices across marketplaces
- `GET /cards/{id}/history` - Get price history
- `GET /cards/{id}/signals` - Get analytics signals

### Recommendations
- `GET /recommendations` - Get trading recommendations (filterable)
- `GET /recommendations/{id}` - Get specific recommendation
- `GET /recommendations/card/{card_id}` - Get recommendations for a card

### Dashboard
- `GET /dashboard/summary` - Get dashboard metrics

### Settings
- `GET /settings` - Get application settings
- `PUT /settings` - Update settings

### Marketplaces
- `GET /marketplaces` - List marketplaces
- `PATCH /marketplaces/{id}/toggle` - Toggle marketplace enabled status

## Adding a New Marketplace Adapter

1. Create a new adapter file in `backend/app/services/ingestion/adapters/`:

```python
# backend/app/services/ingestion/adapters/newmarket.py
from app.services.ingestion.base import MarketplaceAdapter, AdapterConfig, CardListing, CardPrice

class NewMarketAdapter(MarketplaceAdapter):
    @property
    def marketplace_name(self) -> str:
        return "New Market"
    
    @property
    def marketplace_slug(self) -> str:
        return "newmarket"
    
    async def fetch_listings(self, card_name, set_code, scryfall_id, limit):
        # Implementation
        pass
    
    async def fetch_price(self, card_name, set_code, collector_number, scryfall_id):
        # Implementation
        pass
    
    async def search_cards(self, query, limit):
        # Implementation
        pass
```

2. Register in `backend/app/services/ingestion/registry.py`:

```python
from app.services.ingestion.adapters.newmarket import NewMarketAdapter

_ADAPTER_REGISTRY["newmarket"] = NewMarketAdapter
```

3. Add marketplace to database via seed script or API.

## Example User Flows

### Search for a Card and View Prices

1. Go to **Search Cards** in the sidebar
2. Type a card name (e.g., "Lightning Bolt")
3. Click on a card to view its detail page
4. View current prices across all marketplaces
5. See the 30-day price history chart
6. Check any active signals and recommendations

### View Trading Recommendations

1. Go to **Recommendations** in the sidebar
2. Filter by action type (BUY/SELL/HOLD)
3. Sort by confidence or potential profit
4. Click on a card to see full details
5. Review the AI-generated rationale

### Configure Settings

1. Go to **Settings** in the sidebar
2. Enable/disable specific marketplaces
3. Adjust ROI and confidence thresholds
4. Set recommendation time horizons

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_DEBUG` | Enable debug mode | `true` |
| `SECRET_KEY` | Application secret key | Required |
| `POSTGRES_*` | Database configuration | See .env.example |
| `REDIS_*` | Redis configuration | See .env.example |
| `LLM_PROVIDER` | AI provider (openai/anthropic/mock) | `mock` |
| `OPENAI_API_KEY` | OpenAI API key | Optional |
| `ANTHROPIC_API_KEY` | Anthropic API key | Optional |
| `SCRAPE_INTERVAL_MINUTES` | Scraping frequency | `30` |
| `ANALYTICS_INTERVAL_HOURS` | Analytics frequency | `1` |

## Project Structure

```
mtg-market-intel/
├── backend/
│   ├── alembic/              # Database migrations
│   ├── app/
│   │   ├── api/              # FastAPI routes
│   │   ├── core/             # Configuration, logging
│   │   ├── db/               # Database setup
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   │   ├── agents/       # Analytics, recommendation agents
│   │   │   ├── ingestion/    # Marketplace adapters
│   │   │   └── llm/          # LLM client abstraction
│   │   ├── tasks/            # Celery tasks
│   │   └── scripts/          # Seed scripts
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js pages
│   │   ├── components/       # React components
│   │   ├── lib/              # API client, utilities
│   │   └── types/            # TypeScript types
│   ├── __tests__/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Support

For issues and feature requests, please use the GitHub Issues page.

