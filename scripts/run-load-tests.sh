#!/bin/bash
# Load testing script using k6
#
# Prerequisites:
#   - k6 installed: https://k6.io/docs/get-started/installation/
#   - Backend running at BASE_URL (default: http://localhost:8000)
#
# Usage:
#   ./scripts/run-load-tests.sh                                    # Run all tests
#   ./scripts/run-load-tests.sh cards                              # Run only card search test
#   ./scripts/run-load-tests.sh market                             # Run only market overview test
#   BASE_URL=https://staging.example.com ./scripts/run-load-tests.sh  # Custom URL

set -e

BASE_URL=${BASE_URL:-"http://localhost:8000"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if k6 is installed
if ! command -v k6 &> /dev/null; then
    echo "Error: k6 is not installed."
    echo "Install it from: https://k6.io/docs/get-started/installation/"
    exit 1
fi

# Check if backend is reachable
echo "Checking backend connectivity at $BASE_URL..."
if ! curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/health" | grep -q "200"; then
    echo "Warning: Backend health check failed. Tests may not run correctly."
    echo "Make sure the backend is running at $BASE_URL"
fi

echo ""
echo "Running load tests against $BASE_URL"
echo "=================================="

run_cards_test() {
    echo ""
    echo "[Card Search Load Test]"
    echo "Testing: GET /api/cards/search"
    echo "Stages: 10 VUs (30s) -> 50 VUs (1m) -> 100 VUs (30s) -> ramp down (30s)"
    echo ""
    k6 run --env BASE_URL="$BASE_URL" "$PROJECT_ROOT/backend/tests/load/cards_search.js"
}

run_market_test() {
    echo ""
    echo "[Market Overview Load Test]"
    echo "Testing: GET /api/market/overview"
    echo "Stages: 100 VUs (1m) -> steady (2m) -> ramp down (30s)"
    echo ""
    k6 run --env BASE_URL="$BASE_URL" "$PROJECT_ROOT/backend/tests/load/market_overview.js"
}

case "${1:-all}" in
    cards)
        run_cards_test
        ;;
    market)
        run_market_test
        ;;
    all)
        run_cards_test
        echo ""
        run_market_test
        ;;
    *)
        echo "Usage: $0 [cards|market|all]"
        echo "  cards  - Run card search load test only"
        echo "  market - Run market overview load test only"
        echo "  all    - Run all load tests (default)"
        exit 1
        ;;
esac

echo ""
echo "=================================="
echo "Load tests complete!"
echo ""
echo "Results summary saved by k6. For detailed HTML reports, run with:"
echo "  k6 run --out json=results.json <test-file>"
echo "  Then use k6-reporter or k6-html-reporter to generate HTML."
