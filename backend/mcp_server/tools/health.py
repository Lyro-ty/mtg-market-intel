"""
System health tools for MCP server.

Provides tools to check system status and connectivity.
"""
from typing import Any
import subprocess
import redis.asyncio as redis

from mcp_server.utils import check_connection, api_client, execute_query
from mcp_server.config import config


async def check_db_connection() -> dict[str, Any]:
    """
    Test PostgreSQL database connectivity.

    Returns:
        Connection status and latency
    """
    return await check_connection()


async def check_redis_connection() -> dict[str, Any]:
    """
    Test Redis connectivity.

    Returns:
        Connection status
    """
    try:
        # Parse Redis URL from environment or use default
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        client = redis.from_url(redis_url)
        await client.ping()
        info = await client.info("server")
        await client.aclose()

        return {
            "connected": True,
            "redis_version": info.get("redis_version"),
            "redis_url": redis_url.split("@")[-1],  # Hide password if present
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }


async def check_containers() -> dict[str, Any]:
    """
    Check Docker container status.

    Returns:
        List of containers with their state
    """
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            cwd=config.project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return {"error": result.stderr or "Failed to get container status"}

        import json
        containers = []
        for line in result.stdout.strip().split("\n"):
            if line:
                try:
                    containers.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        return {
            "containers": containers,
            "count": len(containers),
        }
    except FileNotFoundError:
        return {"error": "Docker not found"}
    except Exception as e:
        return {"error": str(e)}


async def get_data_freshness() -> dict[str, Any]:
    """
    Get data freshness information.

    Returns:
        Last update timestamps per marketplace
    """
    query = """
        SELECT
            m.name as marketplace,
            MAX(ps.time) as last_update,
            COUNT(*) as snapshots_24h
        FROM price_snapshots ps
        JOIN marketplaces m ON ps.marketplace_id = m.id
        WHERE ps.time >= NOW() - INTERVAL '24 hours'
        GROUP BY m.name
        ORDER BY last_update DESC
    """

    try:
        rows = await execute_query(query)

        # Also get overall stats
        overall_query = """
            SELECT
                MIN(time) as oldest_24h,
                MAX(time) as newest,
                COUNT(*) as total_24h
            FROM price_snapshots
            WHERE time >= NOW() - INTERVAL '24 hours'
        """
        overall = await execute_query(overall_query)

        return {
            "by_marketplace": rows,
            "overall": overall[0] if overall else {},
        }
    except Exception as e:
        return {"error": str(e)}


async def get_environment() -> dict[str, Any]:
    """
    Get current environment configuration.

    Returns:
        Environment details (sanitized)
    """
    return {
        "environment": config.env.value,
        "is_dev": config.is_dev,
        "api_url": config.api_url,
        "database_host": config.database_url.split("@")[-1].split("/")[0] if "@" in config.database_url else "localhost",
        "test_user_id": config.test_user_id,
        "log_writes": config.log_writes,
        "project_root": config.project_root,
    }


async def get_migration_status() -> dict[str, Any]:
    """
    Get Alembic migration status.

    Returns:
        Current revision and pending migrations
    """
    try:
        # Get current revision
        current = subprocess.run(
            ["alembic", "current"],
            cwd=f"{config.project_root}/backend",
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Get head revision
        head = subprocess.run(
            ["alembic", "heads"],
            cwd=f"{config.project_root}/backend",
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Check for pending
        history = subprocess.run(
            ["alembic", "history", "-r", "current:head"],
            cwd=f"{config.project_root}/backend",
            capture_output=True,
            text=True,
            timeout=10,
        )

        return {
            "current": current.stdout.strip(),
            "head": head.stdout.strip(),
            "pending": history.stdout.strip() if history.stdout.strip() else "No pending migrations",
        }
    except Exception as e:
        return {"error": str(e)}
