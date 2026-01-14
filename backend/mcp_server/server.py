"""
MCP Server for MTG Market Intelligence.

Main entry point for the MCP server.
Run with: python -m mcp_server.server
"""
import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
    ResourceContents,
    TextResourceContents,
)

from mcp_server.config import config
from mcp_server.resources import RESOURCES
from mcp_server import tools as tool_module


# Create the MCP server
server = Server("mtg-intel")


# Tool definitions with their metadata
TOOL_DEFINITIONS = [
    # Card tools
    Tool(name="get_card_by_id", description="Fetch a card by its database ID", inputSchema={
        "type": "object",
        "properties": {"card_id": {"type": "integer", "description": "The database ID of the card"}},
        "required": ["card_id"],
    }),
    Tool(name="get_card_by_name", description="Search for cards by name (fuzzy match)", inputSchema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Card name to search for"},
            "limit": {"type": "integer", "description": "Maximum results (default 10)", "default": 10},
        },
        "required": ["name"],
    }),
    Tool(name="get_card_by_scryfall_id", description="Fetch a card by its Scryfall UUID", inputSchema={
        "type": "object",
        "properties": {"scryfall_id": {"type": "string", "description": "Scryfall UUID"}},
        "required": ["scryfall_id"],
    }),
    Tool(name="search_cards", description="Search cards with filters (colors, type, CMC, format, rarity)", inputSchema={
        "type": "object",
        "properties": {
            "colors": {"type": "string", "description": "Color filter (e.g., 'W', 'UB', 'WUBRG')"},
            "card_type": {"type": "string", "description": "Type filter (e.g., 'Creature', 'Instant')"},
            "cmc_min": {"type": "number", "description": "Minimum CMC"},
            "cmc_max": {"type": "number", "description": "Maximum CMC"},
            "rarity": {"type": "string", "description": "Rarity (common, uncommon, rare, mythic)"},
            "set_code": {"type": "string", "description": "Set code (e.g., 'MKM', 'ONE')"},
            "format_legal": {"type": "string", "description": "Format legality (e.g., 'modern', 'commander')"},
            "limit": {"type": "integer", "default": 20},
            "offset": {"type": "integer", "default": 0},
        },
    }),
    Tool(name="get_random_cards", description="Get random cards (useful for testing)", inputSchema={
        "type": "object",
        "properties": {"count": {"type": "integer", "description": "Number of cards (default 5, max 20)", "default": 5}},
    }),

    # Price tools
    Tool(name="get_current_price", description="Get current price for a card across marketplaces", inputSchema={
        "type": "object",
        "properties": {"card_id": {"type": "integer", "description": "Card database ID"}},
        "required": ["card_id"],
    }),
    Tool(name="get_price_history", description="Get historical prices for a card", inputSchema={
        "type": "object",
        "properties": {
            "card_id": {"type": "integer", "description": "Card database ID"},
            "days": {"type": "integer", "description": "Days of history (default 30)", "default": 30},
            "condition": {"type": "string", "description": "Filter by condition"},
            "is_foil": {"type": "boolean", "description": "Filter by foil status"},
        },
        "required": ["card_id"],
    }),
    Tool(name="get_top_movers", description="Get top gaining and losing cards", inputSchema={
        "type": "object",
        "properties": {
            "window": {"type": "string", "description": "Time window ('24h' or '7d')", "default": "24h"},
            "limit": {"type": "integer", "description": "Cards per category", "default": 10},
        },
    }),
    Tool(name="get_market_overview", description="Get market-wide statistics", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_market_index", description="Get market index trend", inputSchema={
        "type": "object",
        "properties": {"range": {"type": "string", "description": "Time range (7d, 30d, 90d, 1y)", "default": "30d"}},
    }),

    # Schema tools
    Tool(name="list_tables", description="List all database tables with row counts", inputSchema={"type": "object", "properties": {}}),
    Tool(name="describe_table", description="Get column information for a table", inputSchema={
        "type": "object",
        "properties": {"table_name": {"type": "string", "description": "Name of the table"}},
        "required": ["table_name"],
    }),
    Tool(name="get_model_schema", description="Get Pydantic schema for a model", inputSchema={
        "type": "object",
        "properties": {"model_name": {"type": "string", "description": "Model name (e.g., 'Card', 'InventoryItem')"}},
        "required": ["model_name"],
    }),
    Tool(name="get_api_endpoints", description="List all API endpoints from OpenAPI spec", inputSchema={"type": "object", "properties": {}}),
    Tool(name="describe_endpoint", description="Get details for a specific API endpoint", inputSchema={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "API path (e.g., '/cards/{id}')"}},
        "required": ["path"],
    }),

    # Database tools
    Tool(name="run_query", description="Execute a read-only SQL query (SELECT only)", inputSchema={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "SQL SELECT query"}},
        "required": ["query"],
    }),
    Tool(name="count_records", description="Count records in a table", inputSchema={
        "type": "object",
        "properties": {
            "table_name": {"type": "string", "description": "Table name"},
            "where": {"type": "string", "description": "Optional WHERE clause (without 'WHERE')"},
        },
        "required": ["table_name"],
    }),
    Tool(name="get_sample_records", description="Get sample records from a table", inputSchema={
        "type": "object",
        "properties": {
            "table_name": {"type": "string", "description": "Table name"},
            "limit": {"type": "integer", "description": "Number of records (default 5, max 20)", "default": 5},
        },
        "required": ["table_name"],
    }),
    Tool(name="write_run_migration", description="[WRITE] Run pending Alembic migrations (dev only)", inputSchema={
        "type": "object",
        "properties": {"confirm": {"type": "boolean", "description": "Must be true to run", "default": False}},
    }),

    # Health tools
    Tool(name="check_db_connection", description="Test PostgreSQL connectivity", inputSchema={"type": "object", "properties": {}}),
    Tool(name="check_redis_connection", description="Test Redis connectivity", inputSchema={"type": "object", "properties": {}}),
    Tool(name="check_containers", description="Check Docker container status", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_data_freshness", description="Get data freshness per marketplace", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_environment", description="Get current environment configuration", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_migration_status", description="Get Alembic migration status", inputSchema={"type": "object", "properties": {}}),

    # Log tools
    Tool(name="get_container_logs", description="Get logs from a Docker container", inputSchema={
        "type": "object",
        "properties": {
            "container": {"type": "string", "description": "Container name", "default": "backend"},
            "lines": {"type": "integer", "description": "Lines to tail", "default": 100},
            "since": {"type": "string", "description": "Time filter (e.g., '1h', '30m')"},
        },
    }),
    Tool(name="get_recent_errors", description="Find recent errors in container logs", inputSchema={
        "type": "object",
        "properties": {
            "container": {"type": "string", "description": "Container name", "default": "backend"},
            "lines": {"type": "integer", "description": "Lines to search", "default": 500},
        },
    }),

    # Task tools
    Tool(name="list_celery_tasks", description="List registered Celery tasks", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_task_history", description="Get recent task executions", inputSchema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "default": 10}},
    }),
    Tool(name="trigger_price_collection", description="[WRITE] Trigger price collection task (dev only)", inputSchema={
        "type": "object",
        "properties": {"marketplace": {"type": "string", "description": "Specific marketplace (optional)"}},
    }),
    Tool(name="trigger_analytics", description="[WRITE] Trigger analytics calculation (dev only)", inputSchema={"type": "object", "properties": {}}),
    Tool(name="trigger_recommendations", description="[WRITE] Trigger recommendations generation (dev only)", inputSchema={"type": "object", "properties": {}}),
    Tool(name="trigger_scryfall_import", description="[WRITE] Trigger Scryfall import (dev only)", inputSchema={
        "type": "object",
        "properties": {"full": {"type": "boolean", "description": "Full import (~90k cards)", "default": False}},
    }),

    # Cache tools
    Tool(name="list_cache_keys", description="List Redis cache keys", inputSchema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Key pattern", "default": "*"},
            "limit": {"type": "integer", "default": 100},
        },
    }),
    Tool(name="get_cache_value", description="Get value for a cache key", inputSchema={
        "type": "object",
        "properties": {"key": {"type": "string", "description": "Redis key"}},
        "required": ["key"],
    }),
    Tool(name="get_cache_stats", description="Get Redis cache statistics", inputSchema={"type": "object", "properties": {}}),
    Tool(name="write_clear_cache", description="[WRITE] Clear cache keys (dev only)", inputSchema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Key pattern", "default": "*"},
            "confirm": {"type": "boolean", "description": "Must be true to delete", "default": False},
        },
    }),
    Tool(name="write_invalidate_cache_key", description="[WRITE] Delete a cache key (dev only)", inputSchema={
        "type": "object",
        "properties": {"key": {"type": "string", "description": "Key to delete"}},
        "required": ["key"],
    }),

    # Inventory tools
    Tool(name="list_inventory", description="List inventory items for a user", inputSchema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "User ID"},
            "limit": {"type": "integer", "default": 20},
            "offset": {"type": "integer", "default": 0},
        },
        "required": ["user_id"],
    }),
    Tool(name="get_inventory_item", description="Get a specific inventory item", inputSchema={
        "type": "object",
        "properties": {"item_id": {"type": "integer", "description": "Inventory item ID"}},
        "required": ["item_id"],
    }),
    Tool(name="get_portfolio_value", description="Get portfolio value for a user", inputSchema={
        "type": "object",
        "properties": {"user_id": {"type": "integer", "description": "User ID"}},
        "required": ["user_id"],
    }),
    Tool(name="write_add_inventory_item", description="[WRITE] Add card to inventory (dev + test user only)", inputSchema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "User ID (must match test user)"},
            "card_id": {"type": "integer", "description": "Card ID"},
            "quantity": {"type": "integer", "default": 1},
            "condition": {"type": "string", "default": "NEAR_MINT"},
            "is_foil": {"type": "boolean", "default": False},
            "acquisition_price": {"type": "number"},
        },
        "required": ["user_id", "card_id"],
    }),
    Tool(name="write_remove_inventory_item", description="[WRITE] Remove item from inventory (dev + test user only)", inputSchema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "User ID (must match test user)"},
            "item_id": {"type": "integer", "description": "Item ID to remove"},
        },
        "required": ["user_id", "item_id"],
    }),
    Tool(name="write_update_inventory_item", description="[WRITE] Update inventory item (dev + test user only)", inputSchema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "User ID (must match test user)"},
            "item_id": {"type": "integer", "description": "Item ID"},
            "quantity": {"type": "integer"},
            "condition": {"type": "string"},
        },
        "required": ["user_id", "item_id"],
    }),

    # Recommendations tools
    Tool(name="get_recommendations", description="Get trading recommendations", inputSchema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "Filter by action (BUY, SELL, HOLD)"},
            "min_confidence": {"type": "number", "description": "Minimum confidence (0-1)"},
            "limit": {"type": "integer", "default": 20},
        },
    }),
    Tool(name="get_signals", description="Get analytics signals", inputSchema={
        "type": "object",
        "properties": {
            "card_id": {"type": "integer", "description": "Filter by card"},
            "signal_type": {"type": "string", "description": "Filter by type"},
            "days": {"type": "integer", "description": "Days of signals", "default": 7},
        },
    }),

    # Documentation tools
    Tool(name="get_design_docs", description="List design documents in docs/plans/", inputSchema={"type": "object", "properties": {}}),
    Tool(name="read_design_doc", description="Read a specific design document", inputSchema={
        "type": "object",
        "properties": {"filename": {"type": "string", "description": "Document filename"}},
        "required": ["filename"],
    }),
    Tool(name="get_claude_md", description="Read CLAUDE.md project instructions", inputSchema={"type": "object", "properties": {}}),

    # Implementation validation tools
    Tool(name="get_implementation_status", description="Get overview of implementation status (routes, models, tests, gaps)", inputSchema={"type": "object", "properties": {}}),
    Tool(name="list_missing_tests", description="Find routes, services, and tasks without test coverage", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_schema_differences", description="Compare Pydantic schemas vs SQLAlchemy models to find mismatches", inputSchema={"type": "object", "properties": {}}),
    Tool(name="analyze_dead_letter_queue", description="Analyze failed Celery tasks and error patterns", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_signal_coverage", description="Get coverage of analytics signal types (which exist vs expected)", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_empty_tables", description="Find database tables with zero rows (data gaps)", inputSchema={"type": "object", "properties": {}}),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of available tools."""
    return TOOL_DEFINITIONS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute a tool and return the result."""
    # Get the tool function from the tools module
    tool_func = getattr(tool_module, name, None)
    if tool_func is None:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    try:
        result = await tool_func(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


@server.list_resources()
async def list_resources() -> list[Resource]:
    """Return the list of available resources."""
    return [
        Resource(
            uri=uri,
            name=info["name"],
            description=info["description"],
            mimeType=info["mimeType"],
        )
        for uri, info in RESOURCES.items()
    ]


@server.read_resource()
async def read_resource(uri: str) -> ResourceContents:
    """Read a resource by URI."""
    if uri not in RESOURCES:
        raise ValueError(f"Unknown resource: {uri}")

    handler = RESOURCES[uri]["handler"]
    content = await handler()

    return TextResourceContents(
        uri=uri,
        mimeType=RESOURCES[uri]["mimeType"],
        text=content,
    )


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
