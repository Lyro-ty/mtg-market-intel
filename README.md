# Dualcaster Deals

A production-ready web application for Magic: The Gathering card market intelligence, featuring:

- 🔐 **Secure user authentication** - Personal accounts with isolated inventory data
- 📊 **Multi-marketplace price tracking** - Collects data from TCGPlayer, Cardmarket, Card Kingdom, and more
- 📈 **Price analytics & forecasting** - Moving averages, volatility, momentum indicators
- 🤖 **AI-powered recommendations** - Buy/Sell/Hold signals with clear rationales
- 📉 **Cross-market arbitrage detection** - Identify pricing discrepancies
- 📦 **Personal inventory management** - Track your collection with profit/loss analytics
- 🎯 **Modern web UI** - Dashboard, search, charts, recommendations, and inventory

**Live at: [dualcasterdeals.com](https://dualcasterdeals.com)**

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
│   Dashboard │ Search │ Inventory │ Recommendations │ Settings    │
│   Login │ Register │ User Profile                                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend API (FastAPI)                       │
│   REST Endpoints │ JWT Authentication │ Rate Limiting            │
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
│   Users │ Cards │ Prices │ Metrics │ Signals │ Recommendations   │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy, Alembic
- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS, Recharts
- **Database**: PostgreSQL 16
- **Task Queue**: Celery + Redis
- **Authentication**: JWT tokens, bcrypt password hashing
- **AI**: OpenAI/Anthropic API (with mock fallback)
- **Containerization**: Docker, docker-compose
- **Production**: Nginx, Let's Encrypt SSL

---

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
cp env.example .env
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
- Seed initial data (popular MTG cards with 30-day mock price history)
- Start the FastAPI backend
- Start the Next.js frontend
- Start Celery workers and scheduler

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API**: http://localhost:8000

### 5. Create an Account

1. Click "Create account" in the sidebar
2. Register with email, username, and password
3. Start adding cards to your inventory!

---

## 🔐 User Authentication

Dualcaster Deals features a complete user authentication system:

### Features

- **Secure Registration** - Email, username, password with strength requirements
- **JWT Authentication** - Stateless tokens with 24-hour expiration
- **Password Security** - bcrypt hashing with cost factor 12
- **Account Protection** - Lockout after 5 failed attempts
- **User-Isolated Data** - Each user's inventory is completely private

### Password Requirements

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit

### API Authentication

Include the JWT token in the Authorization header:

```bash
Authorization: Bearer <your_token>
```

### Auth Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Create new account |
| `/auth/login` | POST | Get access token |
| `/auth/me` | GET | Get current user |
| `/auth/me` | PATCH | Update profile |
| `/auth/change-password` | POST | Change password |
| `/auth/logout` | POST | Logout (client-side) |

---

## Docker Compose Commands

### Essential Commands

```bash
# Start all services (first time or after pulling updates)
docker compose up --build

# Start in background (detached mode)
docker compose up -d

# Stop all services
docker compose down

# Stop and remove volumes (DELETES ALL DATA)
docker compose down -v

# View logs (all services)
docker compose logs -f

# View logs for specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f worker
```

### Rebuilding After Code Changes

```bash
# Rebuild a specific service (recommended for development)
docker compose build backend
docker compose build frontend

# Rebuild with no cache (forces fresh install of dependencies)
docker compose build --no-cache backend
docker compose build --no-cache frontend

# Rebuild and restart
docker compose up --build backend
docker compose up --build frontend

# Full rebuild of everything (nuclear option)
docker compose build --no-cache
docker compose up -d
```

### Running Commands Inside Containers

```bash
# Access backend shell
docker compose exec backend bash

# Access database
docker compose exec db psql -U mtg_user -d mtg_market_intel

# Run migrations manually
docker compose exec backend alembic upgrade head

# Run seed script
docker compose exec backend python -m app.scripts.seed_data
```

### Triggering Tasks Manually

```bash
# Trigger full marketplace scrape
docker compose exec worker celery -A app.tasks.celery_app call app.tasks.ingestion.scrape_all_marketplaces

# Trigger inventory-only scrape (faster, just your cards)
docker compose exec worker celery -A app.tasks.celery_app call app.tasks.ingestion.scrape_inventory_cards

# Trigger analytics
docker compose exec worker celery -A app.tasks.celery_app call app.tasks.analytics.run_analytics

# Trigger recommendation generation
docker compose exec worker celery -A app.tasks.celery_app call app.tasks.recommendations.generate_recommendations
```

---

## Features

### 📦 Personal Inventory Management

Track your MTG collection with detailed profit/loss analytics. **Each user's inventory is private and isolated.**

**Features:**
- **Import from CSV or plaintext** - Supports common formats like "4x Lightning Bolt (MMA) NM"
- **Track acquisition cost** - Know exactly what you paid
- **Real-time valuations** - Current market prices across all marketplaces
- **Profit/loss tracking** - See your gains and losses at a glance
- **Condition tracking** - Mint, NM, LP, MP, HP, Damaged
- **Foil support** - Track foil and non-foil separately
- **Aggressive recommendations** - Faster, more actionable signals for YOUR cards

**Import Formats Supported:**

Plaintext:
```
4x Lightning Bolt
2 Black Lotus [FOIL]
1x Tarmogoyf (MMA) NM
Force of Will - Alliances - LP
```

CSV:
```csv
card_name,set_code,quantity,condition,foil,price
Lightning Bolt,M21,4,NM,false,2.50
Black Lotus,LEA,1,LP,false,50000.00
```

**Quick Add:** You can also add cards directly from search results using the "Add to Inventory" button on the card detail page.

### 📊 Multi-Marketplace Price Tracking

Real-time price data from major MTG marketplaces:
- **TCGPlayer** (USD) - US market prices
- **Cardmarket** (EUR) - European market prices  
- **Card Kingdom** (USD) - Estimated based on typical markup

Price data is fetched via Scryfall's aggregated pricing API, which includes TCGPlayer and Cardmarket prices.

### 🤖 AI-Powered Recommendations

Two recommendation engines:

| Engine | Purpose | Thresholds | Frequency |
|--------|---------|------------|-----------|
| **Market Recommendations** | General market signals | Conservative | Every 6 hours |
| **Inventory Recommendations** | Your collection | Aggressive | Every 15 min |

Inventory recommendations use:
- Lower ROI thresholds (5% vs 10%)
- Shorter time horizons (3-14 days vs 7-30 days)
- Urgency levels (Critical, High, Normal, Low)
- Profit from acquisition price calculations

---

## Automated Tasks Schedule

The scheduler runs these tasks automatically:

| Task | Frequency | Description |
|------|-----------|-------------|
| **Inventory Scrape** | Every 15 min | Scrapes prices for cards in your inventory only |
| **Full Marketplace Scrape** | Every 30 min | Scrapes all cards (inventory cards first, then others) |
| **Analytics** | Every hour | Calculates metrics, signals, price changes |
| **Recommendations** | Every 6 hours | Generates buy/sell/hold recommendations |
| **Card Catalog Sync** | Daily at 2 AM | Syncs card data from Scryfall |

### Customizing Task Frequency

Set these environment variables in `.env` or `docker-compose.yml`:

```yaml
environment:
  - SCRAPE_INTERVAL_MINUTES=30      # Full scrape interval
  - ANALYTICS_INTERVAL_HOURS=1      # Analytics interval
  - RECOMMENDATIONS_INTERVAL_HOURS=6 # Recommendations interval
```

Inventory scraping runs every 15 minutes (hardcoded for responsiveness).

---

## API Endpoints

### Health Check
- `GET /health` - Service health status

### Authentication
- `POST /auth/register` - Create new account
- `POST /auth/login` - Login and get token
- `GET /auth/me` - Get current user
- `PATCH /auth/me` - Update profile
- `POST /auth/change-password` - Change password
- `POST /auth/logout` - Logout

### Cards
- `GET /cards/search?q=...` - Search cards by name
- `GET /cards/{id}` - Get card details
- `POST /cards/{id}/refresh` - Force a data refresh
- `GET /cards/{id}/prices` - Get current prices across marketplaces
- `GET /cards/{id}/history` - Get price history
- `GET /cards/{id}/signals` - Get analytics signals

### Inventory (Requires Authentication)
- `POST /inventory/import` - Import inventory from CSV/plaintext
- `GET /inventory` - List inventory items (with filtering/pagination)
- `POST /inventory` - Add a single item to inventory
- `GET /inventory/{id}` - Get inventory item details
- `PATCH /inventory/{id}` - Update inventory item
- `DELETE /inventory/{id}` - Remove from inventory
- `GET /inventory/analytics` - Get inventory analytics dashboard
- `GET /inventory/recommendations/list` - Get aggressive recommendations
- `POST /inventory/scrape-prices` - Trigger immediate price refresh
- `POST /inventory/refresh-valuations` - Refresh all valuations
- `POST /inventory/run-recommendations` - Generate recommendations

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

---

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete production deployment instructions.

### Quick Overview

1. **Server Setup**: Install Docker on your server
2. **DNS**: Point dualcasterdeals.com to your server
3. **Environment**: Copy `env.production.example` to `.env.production`
4. **SSL**: Get certificates via Let's Encrypt
5. **Deploy**: `docker compose -f docker-compose.production.yml up -d`

### Security Features

- HTTPS enforced with TLS 1.2+
- Security headers (HSTS, CSP, X-Frame-Options)
- Rate limiting on API and auth endpoints
- bcrypt password hashing (cost factor 12)
- JWT tokens with expiration
- Account lockout protection
- User data isolation

See [SECURITY_REVIEW.md](SECURITY_REVIEW.md) for the full security audit.

---

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

### Windows + WSL Notes

- Open your WSL distro (`wsl -d Ubuntu` for example) and run all `docker`/`make` commands there
- If you need to launch a compose command from PowerShell, prefix it with `wsl -e`, e.g. `wsl -e docker compose up -d`
- The repo is shared between Windows and WSL via `/mnt/c/...`

---

## Importing the Scryfall Database

The importer streams the bulk download so you can ingest 90k+ records without exhausting memory.

```bash
# Import one card per Oracle ID (~30k cards)
make import-scryfall

# Import every printing (~90k cards). Expect ~10-15 minutes.
make import-scryfall-all

# Increase the batch size for faster commits
make import-scryfall-all SCRYFALL_BATCH_SIZE=2000

# Re-use an existing download
docker compose exec backend python -m app.scripts.import_scryfall \
  --type all_cards --skip-download --batch-size 2000
```

### Resetting the Database

```bash
# Stop services and delete volumes (removes all data)
docker compose down -v

# Bring services back up (will re-run migrations and seed)
docker compose up -d
```

### Restoring 30-day Demo Price History

The seed script generates synthetic historical data for demo purposes:

```bash
# Generate 30 days of synthetic history
make seed-demo-prices

# Target specific marketplaces
make seed-demo-prices CARD_LIMIT=400 PRICE_HISTORY_DAYS=45 MARKETPLACES="tcgplayer cardmarket cardkingdom"
```

---

## Troubleshooting

### Frontend won't build

```bash
# Check for TypeScript errors
docker compose logs frontend

# Rebuild with no cache
docker compose build --no-cache frontend
docker compose up frontend
```

### Backend migration errors

```bash
# Check for multiple heads
docker compose exec backend alembic heads

# If multiple heads, merge them or specify target
docker compose exec backend alembic upgrade heads
```

### Scraping not working

```bash
# Check worker logs
docker compose logs worker -f

# Manually trigger a scrape
docker compose exec worker celery -A app.tasks.celery_app call app.tasks.ingestion.scrape_all_marketplaces

# Check if marketplaces are enabled
docker compose exec db psql -U mtg_user -d mtg_market_intel -c "SELECT slug, is_enabled FROM marketplaces"
```

### Dashboard shows "No data"

This usually means the analytics haven't run yet:

```bash
# Trigger analytics manually
docker compose exec worker celery -A app.tasks.celery_app call app.tasks.analytics.run_analytics

# Or wait for the scheduled task (runs hourly)
```

### Container won't start

```bash
# Check what's wrong
docker compose logs <service_name>

# Common fix: rebuild
docker compose build --no-cache <service_name>
docker compose up -d
```

### Authentication Issues

```bash
# Check if migrations ran
docker compose exec backend alembic current

# Re-run auth migration if needed
docker compose exec backend alembic upgrade head

# Check user in database
docker compose exec db psql -U mtg_user -d mtg_market_intel -c "SELECT id, email, username, is_active FROM users"
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_DEBUG` | Enable debug mode | `true` |
| `SECRET_KEY` | Application secret key (JWT signing) | Required |
| `DOMAIN` | Production domain | `localhost` |
| `FRONTEND_URL` | Frontend URL for CORS | `http://localhost:3000` |
| `POSTGRES_*` | Database configuration | See .env.example |
| `REDIS_*` | Redis configuration | See .env.example |
| `LLM_PROVIDER` | AI provider (openai/anthropic/mock) | `mock` |
| `OPENAI_API_KEY` | OpenAI API key | Optional |
| `ANTHROPIC_API_KEY` | Anthropic API key | Optional |
| `SCRAPE_INTERVAL_MINUTES` | Scraping frequency | `30` |
| `ANALYTICS_INTERVAL_HOURS` | Analytics frequency | `1` |
| `RECOMMENDATIONS_INTERVAL_HOURS` | Recommendations frequency | `6` |

---

## Project Structure

```
dualcaster-deals/
├── backend/
│   ├── alembic/              # Database migrations
│   ├── app/
│   │   ├── api/              # FastAPI routes
│   │   │   ├── deps.py               # Auth dependencies
│   │   │   └── routes/
│   │   │       ├── auth.py           # Authentication endpoints
│   │   │       ├── cards.py
│   │   │       ├── inventory.py      # User-scoped inventory
│   │   │       ├── recommendations.py
│   │   │       └── ...
│   │   ├── core/             # Configuration, logging
│   │   ├── db/               # Database setup
│   │   ├── models/           # SQLAlchemy models
│   │   │   ├── user.py               # User model
│   │   │   ├── card.py
│   │   │   ├── inventory.py          # Inventory with user_id
│   │   │   └── ...
│   │   ├── schemas/          # Pydantic schemas
│   │   │   ├── auth.py               # Auth schemas
│   │   │   ├── inventory.py
│   │   │   └── ...
│   │   ├── services/         # Business logic
│   │   │   ├── auth.py               # Auth service
│   │   │   ├── agents/
│   │   │   │   ├── analytics.py
│   │   │   │   ├── recommendation.py
│   │   │   │   └── inventory_recommendation.py
│   │   │   ├── ingestion/    # Marketplace adapters
│   │   │   └── llm/          # LLM client abstraction
│   │   ├── tasks/            # Celery tasks
│   │   │   ├── ingestion.py  # Includes inventory scraping
│   │   │   └── ...
│   │   └── scripts/          # Seed scripts
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── login/        # Login page
│   │   │   ├── register/     # Registration page
│   │   │   ├── inventory/    # Protected inventory page
│   │   │   └── ...
│   │   ├── components/
│   │   │   ├── auth/         # Auth components
│   │   │   ├── layout/       # Layout components
│   │   │   ├── inventory/    # Inventory components
│   │   │   └── ui/           # UI components (with auth)
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx  # Auth state management
│   │   ├── lib/              # API client, utilities
│   │   └── types/            # TypeScript types
│   ├── __tests__/
│   ├── Dockerfile
│   ├── Dockerfile.production
│   └── package.json
├── nginx/
│   └── nginx.conf            # Production reverse proxy
├── docker-compose.yml
├── docker-compose.production.yml
├── Makefile
├── env.example
├── env.production.example
├── DEPLOYMENT.md
├── SECURITY_REVIEW.md
└── README.md
```

---

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
