"""
Database query tools for MCP server.

Provides tools to run read-only SQL queries and inspect data.
"""
from typing import Any
from mcp_server.utils import execute_query, log_write_operation, require_dev_mode
from mcp_server.config import config
import subprocess


async def run_query(query: str) -> dict[str, Any]:
    """
    Execute a read-only SQL query.

    Args:
        query: SQL SELECT query to execute

    Returns:
        Query results as list of dicts
    """
    try:
        results = await execute_query(query)
        return {
            "success": True,
            "row_count": len(results),
            "rows": results[:100],  # Cap at 100 rows
            "truncated": len(results) > 100,
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Query failed: {str(e)}"}


async def count_records(table_name: str, where: str | None = None) -> dict[str, Any]:
    """
    Count records in a table with optional WHERE clause.

    Args:
        table_name: Name of the table
        where: Optional WHERE clause (without 'WHERE' keyword)

    Returns:
        Record count
    """
    # Validate table name (prevent SQL injection)
    if not table_name.replace("_", "").isalnum():
        return {"error": "Invalid table name"}

    query = f"SELECT COUNT(*) as count FROM {table_name}"
    if where:
        query += f" WHERE {where}"

    try:
        results = await execute_query(query)
        return {
            "table": table_name,
            "where": where,
            "count": results[0]["count"] if results else 0,
        }
    except Exception as e:
        return {"error": str(e)}


async def get_sample_records(table_name: str, limit: int = 5) -> dict[str, Any]:
    """
    Get sample records from a table.

    Args:
        table_name: Name of the table
        limit: Number of records (default 5, max 20)

    Returns:
        Sample records
    """
    # Validate table name
    if not table_name.replace("_", "").isalnum():
        return {"error": "Invalid table name"}

    limit = min(limit, 20)
    query = f"SELECT * FROM {table_name} LIMIT {limit}"

    try:
        results = await execute_query(query)
        return {
            "table": table_name,
            "sample_size": len(results),
            "rows": results,
        }
    except Exception as e:
        return {"error": str(e)}


async def write_run_migration(confirm: bool = False) -> dict[str, Any]:
    """
    Run pending Alembic migrations.

    WARNING: This modifies the database schema.

    Args:
        confirm: Must be True to actually run migrations

    Returns:
        Migration result
    """
    require_dev_mode("write_run_migration")

    if not confirm:
        return {
            "error": "Migration requires explicit confirmation",
            "usage": "Set confirm=True to run migrations",
        }

    log_write_operation("write_run_migration", {"confirm": confirm})

    try:
        # Run alembic upgrade head
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=str(config.project_root) + "/backend",
            capture_output=True,
            text=True,
            timeout=60,
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
