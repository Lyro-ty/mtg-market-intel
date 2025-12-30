"""
Schema introspection tools for MCP server.

Provides tools to inspect database schema and API structure.
"""
from typing import Any
import json
from pathlib import Path

from mcp_server.utils import get_table_names, get_table_columns, get_row_count, api_client
from mcp_server.config import config


async def list_tables() -> list[dict[str, Any]]:
    """
    List all database tables with row counts.

    Returns:
        List of tables with name and approximate row count
    """
    tables = await get_table_names()
    result = []
    for table in tables:
        count = await get_row_count(table)
        result.append({
            "table_name": table,
            "row_count": count,
        })
    return sorted(result, key=lambda x: x["table_name"])


async def describe_table(table_name: str) -> dict[str, Any]:
    """
    Get detailed column information for a table.

    Args:
        table_name: Name of the table to describe

    Returns:
        Table schema with columns, types, and constraints
    """
    columns = await get_table_columns(table_name)
    if not columns:
        return {"error": f"Table '{table_name}' not found"}

    count = await get_row_count(table_name)

    return {
        "table_name": table_name,
        "row_count": count,
        "columns": columns,
    }


async def get_model_schema(model_name: str) -> dict[str, Any]:
    """
    Get Pydantic schema for a model/endpoint.

    Args:
        model_name: Name of the model (e.g., "Card", "InventoryItem")

    Returns:
        JSON Schema for the model
    """
    # Try to get from OpenAPI spec
    try:
        openapi = await get_api_endpoints()
        if "components" in openapi and "schemas" in openapi["components"]:
            schemas = openapi["components"]["schemas"]
            # Try exact match first
            if model_name in schemas:
                return schemas[model_name]
            # Try case-insensitive match
            for name, schema in schemas.items():
                if name.lower() == model_name.lower():
                    return {name: schema}
            # List available schemas if not found
            return {
                "error": f"Schema '{model_name}' not found",
                "available_schemas": list(schemas.keys())[:20],
            }
    except Exception as e:
        return {"error": f"Failed to get schema: {str(e)}"}


async def get_api_endpoints() -> dict[str, Any]:
    """
    Get all API endpoints from OpenAPI spec.

    Returns:
        OpenAPI specification or list of endpoints
    """
    try:
        # Get OpenAPI spec from the API
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{config.api_url}/openapi.json")
            if response.status_code == 200:
                return response.json()
    except Exception:
        pass

    # Fall back to listing known endpoints
    return {
        "note": "Could not fetch OpenAPI spec, listing known endpoints",
        "endpoints": [
            {"path": "/api/cards", "methods": ["GET"], "description": "List/search cards"},
            {"path": "/api/cards/{id}", "methods": ["GET"], "description": "Get card by ID"},
            {"path": "/api/cards/{id}/prices", "methods": ["GET"], "description": "Get card prices"},
            {"path": "/api/cards/{id}/history", "methods": ["GET"], "description": "Get price history"},
            {"path": "/api/inventory", "methods": ["GET", "POST"], "description": "User inventory"},
            {"path": "/api/recommendations", "methods": ["GET"], "description": "Trading recommendations"},
            {"path": "/api/market/overview", "methods": ["GET"], "description": "Market stats"},
            {"path": "/api/market/top-movers", "methods": ["GET"], "description": "Top gaining/losing cards"},
            {"path": "/api/search", "methods": ["GET"], "description": "Semantic search"},
            {"path": "/api/health", "methods": ["GET"], "description": "Health check"},
        ]
    }


async def describe_endpoint(path: str) -> dict[str, Any]:
    """
    Get detailed information about a specific API endpoint.

    Args:
        path: API path (e.g., "/cards/{id}")

    Returns:
        Endpoint details including request/response schemas
    """
    openapi = await get_api_endpoints()

    if "paths" not in openapi:
        return {"error": "Could not fetch OpenAPI spec"}

    # Normalize path
    if not path.startswith("/"):
        path = "/" + path
    if not path.startswith("/api"):
        path = "/api" + path

    paths = openapi.get("paths", {})

    # Try exact match
    if path in paths:
        return {"path": path, "operations": paths[path]}

    # Try without /api prefix
    alt_path = path.replace("/api", "", 1)
    if alt_path in paths:
        return {"path": alt_path, "operations": paths[alt_path]}

    # List similar paths
    similar = [p for p in paths.keys() if path.split("/")[-1] in p]
    return {
        "error": f"Endpoint '{path}' not found",
        "similar_paths": similar[:10],
    }
