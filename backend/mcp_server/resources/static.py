"""
Static MCP resources for MTG Market Intelligence.

Resources provide context that Claude can read automatically.
"""
from typing import Any
import json

from mcp_server.tools.schema import list_tables, get_api_endpoints
from mcp_server.tools.health import get_environment, get_data_freshness
from mcp_server.tools.docs import get_claude_md, get_design_docs
from mcp_server.utils import execute_query


async def get_schema_tables_resource() -> str:
    """Get database tables as a resource."""
    tables = await list_tables()
    return json.dumps(tables, indent=2, default=str)


async def get_schema_models_resource() -> str:
    """Get SQLAlchemy model information as a resource."""
    # Get table columns for key models
    key_tables = ["cards", "price_snapshots", "inventory_items", "recommendations", "signals", "users"]
    models = {}

    for table in key_tables:
        try:
            from mcp_server.tools.schema import describe_table
            info = await describe_table(table)
            models[table] = info
        except Exception as e:
            models[table] = {"error": str(e)}

    return json.dumps(models, indent=2, default=str)


async def get_schema_api_resource() -> str:
    """Get OpenAPI spec as a resource."""
    spec = await get_api_endpoints()
    return json.dumps(spec, indent=2, default=str)


async def get_docs_claude_md_resource() -> str:
    """Get CLAUDE.md content as a resource."""
    result = await get_claude_md()
    return result.get("content", json.dumps(result))


async def get_docs_plans_resource() -> str:
    """Get list of design documents as a resource."""
    result = await get_design_docs()
    return json.dumps(result, indent=2, default=str)


async def get_config_marketplaces_resource() -> str:
    """Get marketplace configuration as a resource."""
    query = "SELECT id, name, slug, is_enabled, default_currency FROM marketplaces ORDER BY name"
    try:
        rows = await execute_query(query)
        return json.dumps(rows, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def get_config_environment_resource() -> str:
    """Get environment configuration as a resource."""
    result = await get_environment()
    return json.dumps(result, indent=2, default=str)


async def get_stats_overview_resource() -> str:
    """Get quick stats overview as a resource."""
    query = """
        SELECT
            (SELECT COUNT(*) FROM cards) as total_cards,
            (SELECT COUNT(*) FROM cards WHERE scryfall_price_usd IS NOT NULL) as priced_cards,
            (SELECT COUNT(*) FROM price_snapshots) as total_snapshots,
            (SELECT COUNT(*) FROM users) as total_users,
            (SELECT COUNT(*) FROM inventory_items) as total_inventory_items,
            (SELECT COUNT(*) FROM recommendations WHERE is_active = true) as active_recommendations
    """
    try:
        rows = await execute_query(query)
        stats = rows[0] if rows else {}

        # Add freshness info
        freshness = await get_data_freshness()
        stats["data_freshness"] = freshness

        return json.dumps(stats, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# Resource registry
RESOURCES = {
    "mtg://schema/tables": {
        "name": "Database Tables",
        "description": "All database tables with row counts",
        "mimeType": "application/json",
        "handler": get_schema_tables_resource,
    },
    "mtg://schema/models": {
        "name": "Database Models",
        "description": "Key SQLAlchemy model definitions",
        "mimeType": "application/json",
        "handler": get_schema_models_resource,
    },
    "mtg://schema/api": {
        "name": "API Schema",
        "description": "OpenAPI specification",
        "mimeType": "application/json",
        "handler": get_schema_api_resource,
    },
    "mtg://docs/claude-md": {
        "name": "CLAUDE.md",
        "description": "Project instructions for Claude",
        "mimeType": "text/markdown",
        "handler": get_docs_claude_md_resource,
    },
    "mtg://docs/plans": {
        "name": "Design Documents",
        "description": "List of design docs in docs/plans/",
        "mimeType": "application/json",
        "handler": get_docs_plans_resource,
    },
    "mtg://config/marketplaces": {
        "name": "Marketplaces",
        "description": "Configured marketplace sources",
        "mimeType": "application/json",
        "handler": get_config_marketplaces_resource,
    },
    "mtg://config/environment": {
        "name": "Environment",
        "description": "Current environment configuration",
        "mimeType": "application/json",
        "handler": get_config_environment_resource,
    },
    "mtg://stats/overview": {
        "name": "Stats Overview",
        "description": "Quick statistics snapshot",
        "mimeType": "application/json",
        "handler": get_stats_overview_resource,
    },
}
