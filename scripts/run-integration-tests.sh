#!/bin/bash
set -e

# Integration test runner for MTG Market Intel
# Starts a PostgreSQL/TimescaleDB container and runs integration tests

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Cleanup function
cleanup() {
    echo "Cleaning up..."
    docker compose -f docker-compose.test.yml down --volumes --remove-orphans 2>/dev/null || true
}

# Always cleanup on exit
trap cleanup EXIT

# Start test database
echo "Starting test database..."
docker compose -f docker-compose.test.yml up -d test-db

# Wait for database
echo "Waiting for test database..."
DATABASE_READY=false
for i in {1..30}; do
    if docker compose -f docker-compose.test.yml exec -T test-db pg_isready -U test_user -d test_db > /dev/null 2>&1; then
        echo "Database ready!"
        DATABASE_READY=true
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 1
done

if [ "$DATABASE_READY" = false ]; then
    echo "ERROR: Database failed to become ready after 30 seconds"
    exit 1
fi

# Run integration tests
# Pass env var to container with -e flag (use test-db as hostname since tests run inside backend container)
echo "Running integration tests..."
docker compose exec -e INTEGRATION_DATABASE_URL="postgresql+asyncpg://test_user:test_pass@test-db:5432/test_db" \
    backend pytest tests/integration -v -m integration

echo "Integration tests completed successfully!"
