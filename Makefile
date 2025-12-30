.PHONY: up down build logs restart migrate seed seed-demo-prices test test-backend test-frontend lint clean help

SCRYFALL_BATCH_SIZE ?= 1000
CARD_LIMIT ?= 250
PRICE_HISTORY_DAYS ?= 30

ifdef MARKETPLACES
MARKETPLACE_FLAGS := --marketplaces $(MARKETPLACES)
else
MARKETPLACE_FLAGS :=
endif

# Default target
help:
	@echo "MTG Market Intel - Available Commands"
	@echo "======================================"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make build        - Build all containers"
	@echo "  make restart      - Restart all services"
	@echo "  make logs         - View logs from all services"
	@echo "  make logs-backend - View backend logs"
	@echo "  make logs-worker  - View worker logs"
	@echo ""
	@echo "Database Commands:"
	@echo "  make migrate          - Run database migrations"
	@echo "  make seed             - Seed the database with initial data"
	@echo "  make seed-demo-prices - Generate synthetic 30-day price history"
	@echo "  make import-scryfall  - Import Scryfall card database (~30k cards)"
	@echo "  make import-scryfall-all - Import ALL printings (~90k cards)"
	@echo "  make db-shell         - Open psql shell"
	@echo ""
	@echo "Testing Commands:"
	@echo "  make test         - Run all tests"
	@echo "  make test-backend - Run backend tests only"
	@echo "  make test-frontend- Run frontend tests only"
	@echo ""
	@echo "Development Commands:"
	@echo "  make lint         - Run linters"
	@echo "  make generate-types - Generate TypeScript types from OpenAPI"
	@echo "  make clean        - Remove all containers and volumes"
	@echo "  make shell        - Open a shell in the backend container"

# Docker commands
up:
	docker compose up -d

up-build:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-worker:
	docker compose logs -f worker

logs-scheduler:
	docker compose logs -f scheduler

# Database commands
migrate:
	docker compose exec backend alembic upgrade head

migrate-new:
	@read -p "Migration message: " msg; \
	docker compose exec backend alembic revision --autogenerate -m "$$msg"

seed:
	docker compose exec backend python -m app.scripts.seed_data

seed-demo-prices:
	@echo "Generating synthetic price history for demo/testing..."
	docker compose exec backend python -m app.scripts.generate_demo_price_history --card-limit $(CARD_LIMIT) --days $(PRICE_HISTORY_DAYS) $(MARKETPLACE_FLAGS)

import-scryfall:
	@echo "Importing Scryfall card database (default_cards)..."
	docker compose exec backend python -m app.scripts.import_scryfall --type default_cards --batch-size $(SCRYFALL_BATCH_SIZE)

import-scryfall-all:
	@echo "Importing ALL Scryfall card printings (this will take a while)..."
	docker compose exec backend python -m app.scripts.import_scryfall --type all_cards --batch-size $(SCRYFALL_BATCH_SIZE)

db-shell:
	docker compose exec db psql -U mtg_user -d mtg_market_intel

# Testing commands
test: test-backend test-frontend

test-backend:
	docker compose exec backend pytest -v

test-frontend:
	docker compose exec frontend npm test

# Development commands
lint:
	docker compose exec backend ruff check .
	docker compose exec frontend npm run lint

format:
	docker compose exec backend ruff format .

generate-types:
	@echo "Generating TypeScript types from OpenAPI schema..."
	cd frontend && npm run generate-types
	@echo "Types generated at frontend/src/types/api.generated.ts"

clean:
	docker compose down -v --rmi local
	docker system prune -f

shell:
	docker compose exec backend /bin/sh

# Manual task triggers
trigger-scrape:
	docker compose exec backend python -c "from app.tasks.ingestion import scrape_all_marketplaces; scrape_all_marketplaces.delay()"

trigger-analytics:
	docker compose exec backend python -c "from app.tasks.analytics import run_analytics; run_analytics.delay()"

trigger-recommendations:
	docker compose exec backend python -c "from app.tasks.recommendations import generate_recommendations; generate_recommendations.delay()"

