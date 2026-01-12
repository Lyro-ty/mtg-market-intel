# Performance Baselines

Last updated: 2026-01-11

## Test Environment

- **Backend**: FastAPI + SQLAlchemy (async)
- **Database**: PostgreSQL 15 + TimescaleDB
- **Cache**: Redis for response caching
- **Cards in database**: ~100,000
- **Price snapshots**: ~275,000

## API Latency Targets (p95)

| Endpoint | Target | Baseline | Notes |
|----------|--------|----------|-------|
| GET /api/cards/search | <500ms | TBD | Includes ILIKE pattern matching |
| GET /api/market/overview | <1000ms | TBD | Complex aggregations, cached |
| GET /api/cards/{id} | <200ms | TBD | Single card lookup |
| GET /api/cards/{id}/price-history | <500ms | TBD | TimescaleDB time-series query |
| GET /api/inventory | <500ms | TBD | User-scoped, paginated |
| GET /api/recommendations | <500ms | TBD | Cached recommendations |

## Throughput Targets

| Endpoint | Target RPS | Baseline | Notes |
|----------|------------|----------|-------|
| Card search | 100 | TBD | Most common user action |
| Market overview | 50 | TBD | Dashboard landing, cached |
| Card detail | 200 | TBD | Lightweight query |
| Inventory list | 50 | TBD | Authenticated only |

## Load Test Scenarios

### Card Search Test (`cards_search.js`)

Simulates users searching for cards with varying load:

| Stage | Duration | Virtual Users | Purpose |
|-------|----------|---------------|---------|
| Ramp up | 30s | 0 -> 10 | Warm up |
| Steady | 1m | 10 -> 50 | Normal load |
| Peak | 30s | 50 -> 100 | Stress test |
| Ramp down | 30s | 100 -> 0 | Cool down |

**Thresholds:**
- p95 latency < 500ms
- Error rate < 1%

### Market Overview Test (`market_overview.js`)

Simulates dashboard traffic:

| Stage | Duration | Virtual Users | Purpose |
|-------|----------|---------------|---------|
| Ramp up | 1m | 0 -> 100 | Gradual increase |
| Steady | 2m | 100 | Sustained load |
| Ramp down | 30s | 100 -> 0 | Cool down |

**Thresholds:**
- p95 latency < 1000ms (allows for cache misses)
- Error rate < 1%

## Running Load Tests

### Prerequisites

Install k6: https://k6.io/docs/get-started/installation/

```bash
# macOS
brew install k6

# Ubuntu/Debian
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6

# Docker
docker pull grafana/k6
```

### Running Tests

```bash
# Run all load tests (default: http://localhost:8000)
./scripts/run-load-tests.sh

# Run specific test
./scripts/run-load-tests.sh cards
./scripts/run-load-tests.sh market

# Custom base URL (e.g., staging environment)
BASE_URL=https://staging.example.com ./scripts/run-load-tests.sh

# Run with Docker (no local k6 install needed)
docker run --rm -i --network=host grafana/k6 run - < backend/tests/load/cards_search.js
```

### Generating Reports

```bash
# JSON output for further analysis
k6 run --out json=results.json backend/tests/load/cards_search.js

# InfluxDB output (for Grafana dashboards)
k6 run --out influxdb=http://localhost:8086/k6 backend/tests/load/cards_search.js
```

## Optimization Strategies

### Database

- [ ] Add GIN index for card name search
- [ ] Use materialized views for market overview
- [ ] Connection pooling tuning (PgBouncer)

### Caching

- [x] Redis caching for market overview (5 min TTL)
- [ ] Cache card search results for common terms
- [ ] CDN for static assets

### Application

- [ ] Connection pool size optimization
- [ ] Query result streaming for large datasets
- [ ] Rate limiting per user

## Historical Results

Track baseline measurements here after running tests:

| Date | Test | p50 | p95 | p99 | Max RPS | Notes |
|------|------|-----|-----|-----|---------|-------|
| TBD | Card Search | - | - | - | - | Initial baseline |
| TBD | Market Overview | - | - | - | - | Initial baseline |

## Alerting Thresholds

Suggested monitoring alerts:

| Metric | Warning | Critical |
|--------|---------|----------|
| API p95 latency | >750ms | >1500ms |
| Error rate | >0.5% | >2% |
| Database connections | >80% pool | >95% pool |
| Redis memory | >70% | >90% |
