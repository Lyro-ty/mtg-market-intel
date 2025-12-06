# Docker Setup for Dualcaster Deals

This project uses a single `docker-compose.yml` file that works for both development and production, controlled by your `.env` file.

## Quick Start

1. **Copy the example environment file:**
   ```bash
   cp env.example .env
   ```

2. **Edit `.env` with your configuration:**
   - Set `SECRET_KEY` (generate with: `openssl rand -hex 32`)
   - Set database credentials
   - Set API keys (OpenAI, etc.)
   - Configure domain and URLs for production

3. **Start the services:**
   ```bash
   docker-compose up -d
   ```

## Development vs Production

The same `docker-compose.yml` works for both environments. Differences are controlled by your `.env` file:

### Development Setup

In your `.env` file:
- Set `API_DEBUG=true`
- Uncomment volume mounts in `docker-compose.yml` for hot reload:
  ```yaml
  volumes:
    - ./backend:/app
  ```
- Uncomment port mappings if you need local database access:
  ```yaml
  ports:
    - "5432:5432"  # PostgreSQL
    - "6379:6379"   # Redis
  ```

### Production Setup

In your `.env` file:
- Set `API_DEBUG=false`
- Keep volume mounts commented out (uses built images)
- Keep database/redis ports commented out (not exposed externally)
- Set `DOMAIN` and `FRONTEND_URL` to your production domain
- Set `CORS_ORIGINS` to your production domain
- Set `NEXT_PUBLIC_API_URL=/api` (uses Next.js rewrites)

## Environment Variables

All configuration is done through the `.env` file. Key variables:

- `COMPOSE_PROJECT_NAME` - Used for container names (default: `dualcaster`)
- `NETWORK_NAME` - Docker network name (default: `dualcaster-network`)
- `RESTART_POLICY` - Container restart policy (default: `always`)
- `API_DEBUG` - Enable debug mode (default: `false`)
- `SECRET_KEY` - Secret key for JWT tokens (REQUIRED)
- `POSTGRES_*` - Database configuration
- `DOMAIN` - Your domain (e.g., `dualcasterdeals.com`)
- `FRONTEND_URL` - Full frontend URL
- `CORS_ORIGINS` - Allowed CORS origins (JSON array format)

See `env.example` for all available options.

## Services

- **db** - PostgreSQL database
- **redis** - Redis for Celery
- **backend** - FastAPI backend API
- **worker** - Celery worker for background tasks
- **scheduler** - Celery beat scheduler
- **frontend** - Next.js frontend

## Building

```bash
# Build all services
docker-compose build

# Build specific service
docker-compose build backend
```

## Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f worker
```

## Database Migrations

Migrations run automatically on backend startup. To run manually:

```bash
docker-compose exec backend alembic upgrade head
```

## Troubleshooting

### Containers won't start
- Check `.env` file exists and has all required variables
- Check logs: `docker-compose logs`
- Verify database credentials match in `.env`

### Frontend can't connect to backend
- Check `NEXT_PUBLIC_API_URL` in `.env`
- For production, should be `/api` (uses Next.js rewrites)
- Check backend health: `curl http://localhost:8000/api/health`

### Database connection errors
- Verify `POSTGRES_*` variables in `.env` match database service
- Check database is healthy: `docker-compose ps db`
- Check database logs: `docker-compose logs db`

