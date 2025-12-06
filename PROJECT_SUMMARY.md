# Dualcaster Deals - Complete Project Summary

## Overview

**Dualcaster Deals** (also known as MTG Market Intel) is a production-ready web application for Magic: The Gathering card market intelligence. It provides comprehensive price tracking, analytics, and AI-powered trading recommendations across multiple marketplaces. The application is live at [dualcasterdeals.com](https://dualcasterdeals.com).

## Core Purpose

The application helps MTG card collectors and traders:
- Track card prices across multiple marketplaces in real-time
- Manage personal inventory with profit/loss analytics
- Receive AI-powered buy/sell/hold recommendations
- Identify arbitrage opportunities across markets
- Analyze market trends and price movements
- Make data-driven trading decisions

## Key Features

### 1. Multi-Marketplace Price Tracking
- **Real-time price data** from major MTG marketplaces:
  - **TCGPlayer** (USD) - US market prices
  - **Cardmarket** (EUR) - European market prices
  - **Card Kingdom** (USD) - Estimated pricing
  - **MTGO** (TIX) - Online platform prices
- Price data collected via **Scryfall API** (aggregated pricing) and **MTGJSON** (historical data)
- No web scraping - uses free, reliable APIs only
- Aggressive collection schedule: every 2-5 minutes for fresh data

### 2. Personal Inventory Management
- **User-scoped inventory** - Each user's collection is completely private and isolated
- **Import capabilities**:
  - CSV import with structured data
  - Plaintext import (e.g., "4x Lightning Bolt (MMA) NM")
  - Quick add from card search results
- **Tracking features**:
  - Quantity, condition (Mint, NM, LP, MP, HP, Damaged)
  - Foil/non-foil support
  - Acquisition price, date, and source
  - Real-time current valuations
  - Profit/loss calculations
  - Value change percentages
- **Analytics dashboard** showing total collection value, gains/losses, and trends

### 3. AI-Powered Recommendations
Two recommendation engines with different strategies:

**Market Recommendations** (Conservative):
- General market signals for all tracked cards
- Runs every 6 hours
- Higher ROI thresholds (10%+)
- Longer time horizons (7-30 days)
- Focus on significant market opportunities

**Inventory Recommendations** (Aggressive):
- Personalized recommendations for user's collection
- Runs every 15 minutes
- Lower ROI thresholds (5%+)
- Shorter time horizons (3-14 days)
- Urgency levels (Critical, High, Normal, Low)
- Profit calculations from acquisition price
- Actionable sell signals when cards appreciate

Both engines provide:
- Buy/Sell/Hold actions with confidence scores
- Price targets and potential profit percentages
- Detailed rationales explaining the recommendation
- Suggested marketplaces and listing prices

### 4. Price Analytics & Forecasting
- **Moving averages** (7-day, 30-day, 90-day)
- **Volatility indicators** - Price stability metrics
- **Momentum indicators** - Trend direction and strength
- **Price change tracking** - 24h, 7d, 30d, 90d changes
- **Volume analysis** - Trading volume trends
- **Market signals** - Technical indicators (breakouts, reversals, etc.)

### 5. Cross-Market Arbitrage Detection
- Identifies pricing discrepancies across marketplaces
- Highlights opportunities to buy low and sell high
- Currency conversion support (USD/EUR)
- Real-time price comparisons

### 6. Modern Web Dashboard
- **Market overview** with key statistics:
  - Total cards tracked
  - 24h trade volume
  - Average price changes
  - Active formats tracked
- **Market index chart** - Aggregate price trends over time
- **Top movers** - Biggest gainers and losers (24h)
- **Color distribution** - Market composition by card colors
- **Card search** with filtering and sorting
- **Price history charts** for individual cards
- **Recommendations feed** with filtering options

### 7. Secure User Authentication
- **JWT-based authentication** with 24-hour token expiration
- **Secure registration** with password strength requirements:
  - Minimum 8 characters
  - At least one uppercase, lowercase, and digit
- **bcrypt password hashing** (cost factor 12)
- **Account lockout protection** (5 failed attempts)
- **User profile management** - Update email, username, password
- **Complete data isolation** - Each user's inventory is private

## Architecture

### System Components

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
│   Inventory │ Listings │ Price Snapshots │ Feature Vectors      │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend:**
- **Python 3.12** - Core language
- **FastAPI** - Modern async web framework
- **SQLAlchemy 2.0** - ORM with async support
- **Alembic** - Database migrations
- **PostgreSQL 16** - Primary database
- **Celery** - Distributed task queue
- **Redis** - Message broker and caching
- **Pydantic** - Data validation and settings
- **Structlog** - Structured logging

**Frontend:**
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first styling
- **Recharts** - Data visualization
- **TanStack Query** - Data fetching and caching
- **Lucide React** - Icon library

**AI/ML:**
- **OpenAI API** - GPT-4o-mini for recommendations
- **Anthropic API** - Claude 3 Haiku (alternative)
- **Sentence Transformers** - Card vectorization for similarity
- **Mock LLM** - Fallback for development/testing

**Infrastructure:**
- **Docker & Docker Compose** - Containerization
- **Nginx** - Reverse proxy (production)
- **Let's Encrypt** - SSL certificates
- **Cloudflare Tunnel** - Secure tunneling (optional)

### Data Sources

**Primary Sources:**
1. **Scryfall API** - Card catalog and aggregated pricing
   - Real-time prices from TCGPlayer, Cardmarket, MTGO
   - Card metadata, images, legality information
   - Rate limit: ~10 requests/second (75ms between requests)

2. **MTGJSON** - Historical price data
   - Weekly price history going back months
   - Bulk data downloads for comprehensive coverage
   - Used for trend analysis and forecasting

**No Web Scraping:**
- All data collection uses official APIs
- Reliable, maintainable, and respectful of rate limits
- No bot detection issues or HTML parsing

## Database Schema

### Core Models

**Users:**
- Authentication credentials
- Profile information
- Settings and preferences

**Cards:**
- Scryfall card data (name, set, collector number, etc.)
- Card characteristics (mana cost, type, colors, etc.)
- Images and metadata
- Relationships to prices, listings, recommendations

**Marketplaces:**
- TCGPlayer, Cardmarket, Card Kingdom, etc.
- Configuration (API endpoints, rate limits, currencies)
- Enable/disable status

**Price Snapshots:**
- Historical price records
- Marketplace-specific pricing
- Timestamped for trend analysis

**Listings:**
- Individual card listings from marketplaces
- Price, condition, quantity, seller info
- Used for detailed market analysis

**Inventory Items:**
- User-owned cards
- Acquisition details (price, date, source)
- Current valuations and profit/loss
- Condition and quantity tracking

**Metrics:**
- Daily aggregated metrics per card
- Moving averages, volatility, volume
- Computed signals and indicators

**Signals:**
- Technical analysis signals
- Breakouts, reversals, momentum changes
- Used to generate recommendations

**Recommendations:**
- Market-wide recommendations (BUY/SELL/HOLD)
- Confidence scores and price targets
- Rationales and time horizons

**Inventory Recommendations:**
- Aggressive recommendations for user's collection
- Urgency levels and ROI calculations
- Suggested listing prices

**Feature Vectors:**
- Vector embeddings for card similarity
- Used for recommendation enhancement

## Automated Task Schedule

The system runs several scheduled tasks via Celery Beat:

| Task | Frequency | Description |
|------|-----------|-------------|
| **Inventory Price Collection** | Every 15 min | Updates prices for cards in user inventories |
| **Full Price Collection** | Every 5 min | Collects prices for all tracked cards |
| **Analytics** | Every hour | Calculates metrics, signals, and price changes |
| **Market Recommendations** | Every 6 hours | Generates conservative market-wide recommendations |
| **Inventory Recommendations** | Every 15 min | Generates aggressive recommendations for user collections |
| **Card Catalog Sync** | Daily at 2 AM | Syncs card data from Scryfall |
| **MTGJSON Historical Import** | Daily at 3 AM | Imports historical price data |

## API Endpoints

### Authentication
- `POST /api/auth/register` - Create new account
- `POST /api/auth/login` - Get JWT token
- `GET /api/auth/me` - Get current user
- `PATCH /api/auth/me` - Update profile
- `POST /api/auth/change-password` - Change password

### Cards
- `GET /api/cards/search?q=...` - Search cards
- `GET /api/cards/{id}` - Get card details
- `POST /api/cards/{id}/refresh` - Force price refresh
- `GET /api/cards/{id}/prices` - Get current prices
- `GET /api/cards/{id}/history` - Get price history
- `GET /api/cards/{id}/signals` - Get analytics signals

### Inventory (Authenticated)
- `POST /api/inventory/import` - Import from CSV/plaintext
- `GET /api/inventory` - List inventory items
- `POST /api/inventory` - Add single item
- `GET /api/inventory/{id}` - Get item details
- `PATCH /api/inventory/{id}` - Update item
- `DELETE /api/inventory/{id}` - Remove item
- `GET /api/inventory/analytics` - Get inventory analytics
- `GET /api/inventory/recommendations/list` - Get recommendations

### Recommendations
- `GET /api/recommendations` - Get trading recommendations
- `GET /api/recommendations/{id}` - Get specific recommendation
- `GET /api/recommendations/card/{card_id}` - Get card recommendations

### Dashboard
- `GET /api/dashboard/summary` - Get market overview metrics
- `GET /api/dashboard/market-index` - Get market index data
- `GET /api/dashboard/top-movers` - Get top gainers/losers
- `GET /api/dashboard/color-distribution` - Get color distribution

### Settings
- `GET /api/settings` - Get application settings
- `PUT /api/settings` - Update settings

## Security Features

- **HTTPS enforced** with TLS 1.2+
- **Security headers** (HSTS, CSP, X-Frame-Options)
- **Rate limiting** on API and auth endpoints
- **bcrypt password hashing** (cost factor 12)
- **JWT tokens** with expiration
- **Account lockout protection** (5 failed attempts)
- **User data isolation** - Complete privacy between users
- **CORS protection** - Configured origins only
- **SQL injection protection** - Parameterized queries via SQLAlchemy
- **Input validation** - Pydantic schemas for all inputs

## Development & Deployment

### Development Setup
1. Clone repository
2. Copy `env.example` to `.env`
3. Run `docker compose up --build`
4. Access frontend at http://localhost:3000
5. API docs at http://localhost:8000/docs

### Production Deployment
- Docker Compose with production configuration
- Nginx reverse proxy with SSL
- Environment-based configuration
- Health checks and monitoring
- Automated migrations on startup

### Key Scripts
- `seed_data.py` - Initial data seeding
- `import_scryfall.py` - Import card catalog
- `seed_mtgjson_historical.py` - Import historical prices
- `generate_demo_price_history.py` - Generate synthetic data
- `export_training_data.py` - Export ML training data

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
│   │   │   ├── llm/          # LLM client abstraction
│   │   │   └── vectorization/ # Card vectorization
│   │   ├── tasks/            # Celery tasks
│   │   └── scripts/          # Seed scripts
│   ├── tests/                # Test suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js pages
│   │   ├── components/       # React components
│   │   ├── contexts/         # React contexts (Auth)
│   │   ├── lib/              # Utilities, API client
│   │   └── types/            # TypeScript types
│   └── package.json
├── nginx/                     # Production reverse proxy
├── docker-compose.yml         # Development setup
├── docker-compose.production.yml
└── README.md
```

## Key Workflows

### Price Data Collection
1. **Scheduled task** triggers price collection
2. **Prioritize inventory cards** - User's cards collected first
3. **Fetch from Scryfall** - Get aggregated prices (TCGPlayer, Cardmarket)
4. **Create price snapshots** - Store historical records
5. **Update listings** - Store individual marketplace listings
6. **Mark stale data** - Flag data older than 24 hours

### Analytics Processing
1. **Calculate metrics** - Moving averages, volatility, volume
2. **Generate signals** - Technical indicators (breakouts, reversals)
3. **Compute price changes** - 24h, 7d, 30d, 90d changes
4. **Store daily metrics** - Aggregate per card per day
5. **Generate insights** - Market trends and patterns

### Recommendation Generation
1. **Analyze signals** - Review technical indicators
2. **Calculate ROI** - Potential profit percentages
3. **LLM analysis** - Generate rationales using AI
4. **Score confidence** - Assign confidence levels
5. **Filter by thresholds** - Only show actionable recommendations
6. **Store recommendations** - Save with expiration dates

### Inventory Valuation
1. **Fetch current prices** - Get latest marketplace prices
2. **Apply condition multipliers** - Adjust for card condition
3. **Calculate total value** - Sum all inventory items
4. **Compute profit/loss** - Compare to acquisition prices
5. **Update valuations** - Store in inventory items
6. **Generate recommendations** - Aggressive signals for user's cards

## Data Flow

1. **Ingestion** → Price data collected from Scryfall/MTGJSON
2. **Storage** → Price snapshots and listings stored in PostgreSQL
3. **Analytics** → Metrics and signals computed from price history
4. **Recommendations** → AI agents generate trading signals
5. **API** → FastAPI serves data to frontend
6. **Frontend** → Next.js displays data with charts and dashboards
7. **User Actions** → Inventory updates, searches, recommendations viewed

## Scalability Considerations

- **Async operations** - FastAPI async endpoints for concurrent requests
- **Task queue** - Celery distributes heavy work across workers
- **Database indexing** - Optimized queries with proper indexes
- **Connection pooling** - SQLAlchemy connection pool management
- **Caching** - Redis for session data and task results
- **Rate limiting** - Protects APIs from abuse
- **Horizontal scaling** - Can add more Celery workers as needed

## Future Enhancements

Potential areas for expansion:
- Additional marketplace integrations
- Advanced ML models for price prediction
- Portfolio optimization algorithms
- Social features (sharing collections, following traders)
- Mobile app (React Native)
- Real-time notifications for price alerts
- Advanced charting with technical indicators
- Export capabilities (CSV, PDF reports)

## License

MIT License - See LICENSE file for details.

---

**Live Application:** [dualcasterdeals.com](https://dualcasterdeals.com)  
**Status:** Production-ready, actively maintained


