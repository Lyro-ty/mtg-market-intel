# Dualcaster Deals

A production-ready web application for Magic: The Gathering card market intelligence, featuring:

- 🔐 **Secure Authentication** - Email + Google OAuth with session management
- 📊 **Multi-Marketplace Price Tracking** - Aggregated data from TCGPlayer, Cardmarket, Card Kingdom
- 📈 **Price Analytics & Forecasting** - Moving averages, volatility, momentum indicators
- 🤖 **AI-Powered Recommendations** - Buy/Sell/Hold signals with clear rationales
- 📦 **Personal Inventory Management** - Track your collection with profit/loss analytics
- 🗂️ **Collection Tracking** - Set completion progress and binder views
- 📝 **Want List** - Price targets with alerts and TCGPlayer affiliate links
- 🏆 **Tournament Data** - Meta analysis from TopDeck.gg
- 🔔 **Notifications** - Price alerts, ban detection, and market updates
- 📥 **Platform Imports** - Import from Moxfield, Archidekt, and Deckbox

**Live at: [dualcasterdeals.com](https://dualcasterdeals.com)**

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Frontend (Next.js 14)                      │
│   Dashboard │ Market │ Cards │ Inventory │ Collection │ Want List│
│   Tournaments │ Insights │ Recommendations │ Settings            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Backend API (FastAPI)                        │
│   REST + WebSocket │ JWT + OAuth │ Rate Limiting                 │
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
│                    PostgreSQL + Redis                            │
│   Users │ Cards │ Prices │ Collections │ Want Lists │ Portfolios │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy, Alembic, Celery
- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS, shadcn/ui
- **Database**: PostgreSQL 16
- **Cache/Queue**: Redis
- **Authentication**: JWT + Google OAuth
- **AI**: OpenAI/Anthropic API (with mock fallback)
- **Data Sources**: Scryfall API, MTGJSON, TopDeck.gg
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
# Edit .env with your settings
```

**Required for full functionality:**
- `SECRET_KEY` - JWT signing key
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` - Google OAuth (optional)
- `TOPDECK_API_KEY` - Tournament data (optional)

### 3. Start the Application

```bash
docker compose up --build
```

This will:
- Start PostgreSQL and Redis
- Run database migrations
- Import Scryfall card data (first run only)
- Start the FastAPI backend
- Start the Next.js frontend
- Start Celery workers and scheduler

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API**: http://localhost:8000/api

### 5. Create an Account

1. Click "Get Started" or "Sign up with Google"
2. Register with email/password or OAuth
3. Start building your collection!

---

## Features

### 🔐 Authentication

| Feature | Description |
|---------|-------------|
| Email/Password | bcrypt hashing, 24-hour JWT tokens |
| Google OAuth | One-click sign-in |
| Session Management | View and revoke active sessions |
| Account Protection | Lockout after failed attempts |

### 📦 Inventory Management

Track your MTG collection with detailed analytics:

- **Import from CSV or plaintext** - Supports common formats
- **Track acquisition cost** - Know exactly what you paid
- **Real-time valuations** - Current market prices
- **Profit/loss tracking** - See gains and losses at a glance
- **Condition pricing** - NM, LP, MP, HP, Damaged with accurate multipliers
- **Foil support** - Track foil and non-foil separately

**Import Formats:**
```
4x Lightning Bolt
2 Black Lotus [FOIL]
1x Tarmogoyf (MMA) NM
Force of Will - Alliances - LP
```

### 🗂️ Collection Tracking

- **Set completion progress** - Track how close you are to completing sets
- **Visual binder view** - See your collection as cards
- **Collection milestones** - Celebrate achievements
- **Stats dashboard** - Total cards, unique cards, set breakdown

### 📝 Want List

- **Price targets** - Set target prices for cards you want
- **Price alerts** - Get notified when prices drop
- **Priority levels** - Organize by importance
- **TCGPlayer links** - Affiliate links for easy purchasing

### 🏆 Tournament Data

Integration with TopDeck.gg for competitive insights:

- **Recent tournaments** - Browse results by format
- **Decklists** - View winning builds
- **Meta analysis** - Track popular cards
- **Attribution** - Full credit to TopDeck.gg

### 📥 Platform Imports

Import your collection from popular platforms:

- **Moxfield** - Direct import via username
- **Archidekt** - Deck and collection import
- **Deckbox** - CSV export import

### 🔔 Notifications

- **Price alerts** - When cards hit your targets
- **Ban detection** - When cards get banned or unbanned
- **Collection updates** - New set releases
- **Recommendations** - Actionable buy/sell signals

### 📊 Analytics

- **Moving averages** - 7-day and 30-day trends
- **Volatility metrics** - Identify unstable prices
- **Momentum indicators** - Catch breakouts
- **Cross-market arbitrage** - Find pricing discrepancies

---

## Automated Tasks

| Task | Frequency | Description |
|------|-----------|-------------|
| Scryfall Bulk Import | 12 hours | Full card database refresh |
| Inventory Price Refresh | 4 hours | Fresh prices for your cards |
| Analytics | 1 hour | Metrics and signal calculation |
| Recommendations | 6 hours | Buy/sell/hold signals |
| Tournament Sync | 6 hours | Latest TopDeck.gg data |
| Ban Detection | 24 hours | Check for legality changes |
| Set Sync | 24 hours | New set releases |
| Want List Check | 4 hours | Price target alerts |

---

## API Endpoints

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Create account |
| `/api/auth/login` | POST | Get access token |
| `/api/auth/me` | GET | Get current user |
| `/api/oauth/google/login` | GET | Start Google OAuth |

### Cards
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cards/search` | GET | Search cards |
| `/api/cards/{id}` | GET | Card details |
| `/api/cards/{id}/prices` | GET | Price data |
| `/api/cards/{id}/history` | GET | Price history |
| `/api/search/semantic` | GET | Semantic search |

### Inventory (Auth Required)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/inventory` | GET/POST | List/add items |
| `/api/inventory/import` | POST | Bulk import |
| `/api/inventory/analytics` | GET | Portfolio analytics |

### Collection (Auth Required)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/collection` | GET | Collection summary |
| `/api/collection/sets` | GET | Set completion stats |
| `/api/collection/cards` | GET | Cards in collection |

### Want List (Auth Required)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/want-list` | GET/POST | List/add wants |
| `/api/want-list/{id}` | PATCH/DELETE | Update/remove |

### Market
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/market/trends` | GET | Market trends |
| `/api/market/movers` | GET | Top gainers/losers |

### Tournaments
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tournaments` | GET | Recent tournaments |
| `/api/tournaments/{id}` | GET | Tournament details |

See full API documentation at http://localhost:8000/docs

---

## Development

### Make Commands

```bash
# Docker
make up              # Start all services
make up-build        # Build and start
make down            # Stop all services
make logs            # View logs
make logs-backend    # Backend logs only

# Database
make migrate         # Run migrations
make migrate-new     # Create new migration
make seed            # Seed initial data
make import-scryfall # Import ~30k cards
make db-shell        # PostgreSQL shell

# Testing
make test            # All tests
make test-backend    # Backend only
make test-frontend   # Frontend only

# Code Quality
make lint            # Run linters
make format          # Format code

# Manual Task Triggers
make trigger-scrape
make trigger-analytics
make trigger-recommendations
```

### Running Tests

```bash
# Backend
docker compose exec backend pytest -v
docker compose exec backend pytest tests/test_auth.py -v

# Frontend
docker compose exec frontend npm test
```

### Project Structure

```
dualcaster-deals/
├── backend/
│   ├── alembic/              # Database migrations
│   ├── app/
│   │   ├── api/routes/       # FastAPI endpoints
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   │   ├── auth.py
│   │   │   ├── pricing/
│   │   │   ├── tournaments/
│   │   │   ├── imports/
│   │   │   └── notifications.py
│   │   ├── tasks/            # Celery tasks
│   │   └── scripts/          # Utility scripts
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js pages
│   │   │   ├── (public)/     # Public pages
│   │   │   └── (protected)/  # Auth-required pages
│   │   ├── components/       # React components
│   │   ├── contexts/         # React contexts
│   │   └── lib/              # API client, utils
│   └── __tests__/
├── docs/
│   └── plans/                # Design documents
├── nginx/                    # Production config
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key | Required |
| `DOMAIN` | Production domain | `localhost` |
| `FRONTEND_URL` | Frontend URL for CORS | `http://localhost:3000` |
| `POSTGRES_*` | Database config | See .env.example |
| `REDIS_*` | Redis config | See .env.example |
| `GOOGLE_CLIENT_ID` | Google OAuth | Optional |
| `GOOGLE_CLIENT_SECRET` | Google OAuth | Optional |
| `TOPDECK_API_KEY` | TopDeck.gg API | Optional |
| `LLM_PROVIDER` | AI provider | `mock` |
| `OPENAI_API_KEY` | OpenAI API | Optional |
| `ANTHROPIC_API_KEY` | Anthropic API | Optional |

---

## Troubleshooting

### Frontend won't build
```bash
docker compose logs frontend
docker compose build --no-cache frontend
```

### Database migration errors
```bash
docker compose exec backend alembic heads
docker compose exec backend alembic upgrade heads
```

### Authentication issues
```bash
docker compose exec backend alembic current
docker compose exec db psql -U dualcaster_user -d dualcaster_deals \
  -c "SELECT id, email, username FROM users"
```

### Data not showing
```bash
# Trigger analytics manually
make trigger-analytics

# Check if cards are imported
docker compose exec db psql -U dualcaster_user -d dualcaster_deals \
  -c "SELECT COUNT(*) FROM cards"
```

---

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete instructions.

### Quick Overview

1. Point DNS to your server
2. Copy `env.production.example` to `.env.production`
3. Get SSL certificates via Let's Encrypt
4. Run `docker compose -f docker-compose.production.yml up -d`

### Security Features

- HTTPS with TLS 1.2+
- Security headers (HSTS, CSP, X-Frame-Options)
- Rate limiting on API endpoints
- bcrypt password hashing
- JWT with expiration
- OAuth state validation
- User data isolation

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

## Credits

- Card data from [Scryfall](https://scryfall.com)
- Tournament data from [TopDeck.gg](https://topdeck.gg)
- Icons from [game-icons.net](https://game-icons.net)
