# MCP Server Design for MTG Market Intelligence

**Date:** 2025-12-29
**Status:** Approved
**Author:** Claude + User

## Overview

A comprehensive MCP (Model Context Protocol) server for the Dualcaster Deals application, designed to make Claude Code development more accurate by providing direct access to data, schemas, and system health.

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python | Matches backend stack, reuses SQLAlchemy models directly |
| Connection | Hybrid (DB + API) | DB for introspection, API for business logic operations |
| Write safety | Dev-only + test user | Inventory writes restricted to dev mode AND test user only |
| Location | `backend/mcp_server/` | Alongside existing backend code for easy imports |

## Architecture

```
backend/mcp_server/
├── __init__.py
├── server.py           # Main MCP server entry point
├── config.py           # Environment/connection configuration
├── tools/
│   ├── __init__.py
│   ├── cards.py        # Card lookup tools
│   ├── prices.py       # Price data tools
│   ├── schema.py       # Schema introspection tools
│   ├── database.py     # Raw SQL query tools
│   ├── health.py       # System health tools
│   ├── inventory.py    # Inventory operations
│   ├── recommendations.py
│   ├── tasks.py        # Celery task tools
│   ├── logs.py         # Log access tools
│   ├── cache.py        # Redis tools
│   └── docs.py         # Documentation access
├── resources/
│   ├── __init__.py
│   └── static.py       # Static resources (schemas, docs)
└── utils/
    ├── __init__.py
    ├── db.py           # Database connection helper
    ├── api.py          # HTTP client for API calls
    └── logging.py      # Write operation logging
```

### Connection Modes

- `dev` → `localhost:5432` + `localhost:8000`
- `prod` → production DB + `dualcasterdeals.com/api`

Configured via environment variable `MTG_MCP_ENV=dev|prod`

### Write Operation Safety

- All write tools prefixed with `write_` or `trigger_`
- Logging to `mcp_server/logs/writes.log` with timestamp, tool, parameters
- Console warning output before execution
- Inventory writes require BOTH:
  - `MTG_MCP_ENV=dev`
  - Operation on `MTG_MCP_TEST_USER_ID` only

## Tool Catalog

### Card Tools (Read)

| Tool | Description | Returns |
|------|-------------|---------|
| `get_card_by_id` | Fetch card by database ID | Full card object with current price |
| `get_card_by_name` | Fuzzy search by name | List of matching cards |
| `get_card_by_scryfall_id` | Lookup by Scryfall UUID | Card object |
| `search_cards` | Search with filters (colors, type, CMC, format, rarity) | Paginated card list |
| `get_random_cards` | Get N random cards (useful for testing) | List of cards |

### Price Tools (Read)

| Tool | Description | Returns |
|------|-------------|---------|
| `get_current_price` | Current price for a card across marketplaces | Price breakdown by marketplace/condition |
| `get_price_history` | Historical prices with time range | Time-series data |
| `get_top_movers` | Top gainers/losers (24h or 7d) | Ranked card list with % change |
| `get_market_overview` | Market-wide stats | Total cards, volume, avg price change |
| `get_market_index` | Market index trend | Normalized index values over time |

### Schema Tools (Read)

| Tool | Description | Returns |
|------|-------------|---------|
| `list_tables` | All database tables | Table names with row counts |
| `describe_table` | Column details for a table | Column name, type, nullable, constraints |
| `get_model_schema` | Pydantic schema for a model | JSON Schema |
| `get_api_endpoints` | List all API routes | Path, method, description |
| `describe_endpoint` | Details for specific endpoint | Request/response schemas, params |

### Database Tools (Read)

| Tool | Description | Returns |
|------|-------------|---------|
| `run_query` | Execute read-only SQL (SELECT only) | Query results as JSON |
| `count_records` | Count rows in table with optional WHERE | Integer count |
| `get_sample_records` | Get N sample rows from any table | Row data |

### Health & System Tools (Read)

| Tool | Description | Returns |
|------|-------------|---------|
| `check_db_connection` | Test PostgreSQL connectivity | Connection status, latency |
| `check_redis_connection` | Test Redis connectivity | Connection status |
| `check_containers` | Docker container status | List of containers with state |
| `get_data_freshness` | Latest price snapshot timestamps | Per-marketplace freshness |
| `get_environment` | Current env (dev/prod) and config | Environment details |
| `get_migration_status` | Alembic migration state | Current head, pending migrations |

### Logs & Tasks Tools (Read)

| Tool | Description | Returns |
|------|-------------|---------|
| `get_container_logs` | Tail logs from a container | Recent log lines |
| `get_recent_errors` | Filter logs for errors/exceptions | Error entries with context |
| `list_celery_tasks` | Registered Celery tasks | Task names and schedules |
| `get_task_history` | Recent task executions | Task name, status, duration |

### Cache Tools (Read)

| Tool | Description | Returns |
|------|-------------|---------|
| `list_cache_keys` | Redis keys matching pattern | Key names |
| `get_cache_value` | Get value for a cache key | Cached data |
| `get_cache_stats` | Redis memory/hit stats | Cache statistics |

### Documentation Tools (Read)

| Tool | Description | Returns |
|------|-------------|---------|
| `get_design_docs` | List docs in `docs/plans/` | File names and summaries |
| `read_design_doc` | Read a specific design doc | Markdown content |
| `get_claude_md` | Read CLAUDE.md | Project instructions |

### Inventory Tools (Read)

| Tool | Description | Returns |
|------|-------------|---------|
| `list_inventory` | List user's inventory items | Paginated inventory list |
| `get_inventory_item` | Get specific inventory item | Item details with current value |
| `get_portfolio_value` | Total portfolio value and performance | Value, cost, profit/loss |

### Recommendations Tools (Read)

| Tool | Description | Returns |
|------|-------------|---------|
| `get_recommendations` | Get trading recommendations | List with action, confidence, rationale |
| `get_signals` | Get analytics signals for a card | Signal type, value, confidence |

### Inventory Tools (Write) - DEV + TEST USER ONLY

| Tool | Description | Safety |
|------|-------------|--------|
| `write_add_inventory_item` | Add card to user inventory | Logs card_id, quantity, user |
| `write_remove_inventory_item` | Remove from inventory | Logs item_id |
| `write_update_inventory_item` | Update quantity/condition | Logs changes |

### Cache Tools (Write)

| Tool | Description | Safety |
|------|-------------|--------|
| `write_clear_cache` | Clear Redis cache (all or pattern) | Requires confirmation param |
| `write_invalidate_cache_key` | Delete specific cache key | Logs key name |

### Task Triggers (Write)

| Tool | Description | Safety |
|------|-------------|--------|
| `trigger_price_collection` | Start price collection task | Logs trigger source |
| `trigger_analytics` | Run analytics calculation | Logs trigger source |
| `trigger_recommendations` | Generate recommendations | Logs trigger source |
| `trigger_scryfall_import` | Import cards from Scryfall | Logs scope (bulk/single) |

### Database Tools (Write)

| Tool | Description | Safety |
|------|-------------|--------|
| `write_run_migration` | Run pending Alembic migrations | Requires explicit confirmation |

## MCP Resources

| Resource URI | Description | Content |
|--------------|-------------|---------|
| `mtg://schema/tables` | All database tables | Table names, row counts, relationships |
| `mtg://schema/models` | SQLAlchemy model definitions | Field names, types, constraints |
| `mtg://schema/api` | OpenAPI spec | Full API schema from FastAPI |
| `mtg://docs/claude-md` | CLAUDE.md content | Project instructions |
| `mtg://docs/plans` | List of design documents | File names in `docs/plans/` |
| `mtg://config/marketplaces` | Active marketplaces | Name, slug, enabled status |
| `mtg://config/environment` | Current environment | Dev/prod, connection details |
| `mtg://stats/overview` | Quick stats snapshot | Card count, price snapshots, users |

## Configuration

### Environment Variables

```bash
# Required
MTG_MCP_ENV=dev                          # dev or prod
MTG_MCP_DATABASE_URL=postgresql+asyncpg://...  # Direct DB connection

# Optional
MTG_MCP_API_URL=http://localhost:8000    # API base URL (defaults based on env)
MTG_MCP_TEST_USER_ID=1                   # Test user for inventory writes
MTG_MCP_LOG_WRITES=true                  # Log all write operations
```

### Claude Code Integration

In `~/.claude/settings.json` or project `.claude/settings.json`:

```json
{
  "mcpServers": {
    "mtg-intel": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/home/lyro/mtg-market-intel/backend",
      "env": {
        "MTG_MCP_ENV": "dev",
        "MTG_MCP_DATABASE_URL": "postgresql+asyncpg://dualcaster_user:password@localhost:5432/dualcaster_deals",
        "MTG_MCP_TEST_USER_ID": "1"
      }
    }
  }
}
```

## Dependencies

Add to `backend/requirements.txt`:
```
mcp>=1.0.0
```

## Tool Summary

| Category | Read | Write | Total |
|----------|------|-------|-------|
| Cards | 5 | 0 | 5 |
| Prices | 5 | 0 | 5 |
| Schema | 5 | 0 | 5 |
| Database | 3 | 1 | 4 |
| Health | 6 | 0 | 6 |
| Logs & Tasks | 4 | 4 | 8 |
| Cache | 3 | 2 | 5 |
| Inventory | 3 | 3 | 6 |
| Recommendations | 2 | 0 | 2 |
| Docs | 3 | 0 | 3 |
| **Total** | **39** | **10** | **49** |

Plus 8 resources.

## Implementation Tasks

1. Set up `backend/mcp_server/` directory structure
2. Implement `config.py` with environment handling
3. Implement `utils/db.py` with async PostgreSQL connection
4. Implement `utils/api.py` with httpx async client
5. Implement `utils/logging.py` for write operation logging
6. Implement card tools
7. Implement price tools
8. Implement schema introspection tools
9. Implement database query tools
10. Implement health check tools
11. Implement logs and task tools
12. Implement cache tools
13. Implement inventory tools (with safety checks)
14. Implement recommendations tools
15. Implement documentation tools
16. Implement MCP resources
17. Implement main `server.py` entry point
18. Add `mcp` to requirements.txt
19. Update `.gitignore` for logs and local config
20. Test with Claude Code integration
