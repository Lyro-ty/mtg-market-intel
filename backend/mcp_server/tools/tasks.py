"""
Celery task tools for MCP server.

Provides tools to inspect and trigger background tasks.
"""
from typing import Any
import subprocess

from mcp_server.utils import log_write_operation, require_dev_mode
from mcp_server.config import config


async def list_celery_tasks() -> dict[str, Any]:
    """
    List registered Celery tasks.

    Returns:
        Task names and their schedules
    """
    # Known tasks from the codebase
    tasks = [
        {
            "name": "app.tasks.ingestion.collect_price_data",
            "schedule": "Every 30 minutes",
            "description": "Collect prices from Scryfall/marketplaces",
        },
        {
            "name": "app.tasks.ingestion.collect_inventory_prices",
            "schedule": "Every 15 minutes",
            "description": "Collect prices for user inventory cards",
        },
        {
            "name": "app.tasks.analytics.run_analytics",
            "schedule": "Every 1 hour",
            "description": "Calculate metrics and signals",
        },
        {
            "name": "app.tasks.recommendations.generate_recommendations",
            "schedule": "Every 6 hours",
            "description": "Generate trading recommendations",
        },
        {
            "name": "app.tasks.ingestion.import_scryfall_cards",
            "schedule": "On demand",
            "description": "Import card catalog from Scryfall",
        },
    ]

    return {"tasks": tasks}


async def get_task_history(limit: int = 10) -> dict[str, Any]:
    """
    Get recent Celery task executions.

    Args:
        limit: Number of recent tasks to show

    Returns:
        Recent task runs with status
    """
    # This would require Celery Flower or task result backend inspection
    # For now, return info about how to check
    return {
        "note": "Task history requires Celery Flower or result backend inspection",
        "suggestion": "Check backend logs with: docker compose logs worker --tail=100",
        "flower_url": "http://localhost:5555 (if Flower is running)",
    }


async def trigger_price_collection(marketplace: str | None = None) -> dict[str, Any]:
    """
    Trigger price collection task.

    Args:
        marketplace: Specific marketplace to collect from (optional)

    Returns:
        Task trigger result
    """
    require_dev_mode("trigger_price_collection")
    log_write_operation("trigger_price_collection", {"marketplace": marketplace})

    try:
        cmd = ["docker", "compose", "exec", "-T", "backend",
               "python", "-c",
               "from app.tasks.ingestion import collect_price_data; collect_price_data.delay()"]

        result = subprocess.run(
            cmd,
            cwd=config.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        return {
            "triggered": result.returncode == 0,
            "task": "collect_price_data",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as e:
        return {"error": str(e)}


async def trigger_analytics() -> dict[str, Any]:
    """
    Trigger analytics calculation task.

    Returns:
        Task trigger result
    """
    require_dev_mode("trigger_analytics")
    log_write_operation("trigger_analytics", {})

    try:
        cmd = ["docker", "compose", "exec", "-T", "backend",
               "python", "-c",
               "from app.tasks.analytics import run_analytics; run_analytics.delay()"]

        result = subprocess.run(
            cmd,
            cwd=config.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        return {
            "triggered": result.returncode == 0,
            "task": "run_analytics",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as e:
        return {"error": str(e)}


async def trigger_recommendations() -> dict[str, Any]:
    """
    Trigger recommendations generation task.

    Returns:
        Task trigger result
    """
    require_dev_mode("trigger_recommendations")
    log_write_operation("trigger_recommendations", {})

    try:
        cmd = ["docker", "compose", "exec", "-T", "backend",
               "python", "-c",
               "from app.tasks.recommendations import generate_recommendations; generate_recommendations.delay()"]

        result = subprocess.run(
            cmd,
            cwd=config.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        return {
            "triggered": result.returncode == 0,
            "task": "generate_recommendations",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as e:
        return {"error": str(e)}


async def trigger_scryfall_import(full: bool = False) -> dict[str, Any]:
    """
    Trigger Scryfall card import.

    Args:
        full: If True, import all printings (~90k cards). Otherwise default cards (~30k).

    Returns:
        Task trigger result
    """
    require_dev_mode("trigger_scryfall_import")
    log_write_operation("trigger_scryfall_import", {"full": full})

    make_target = "import-scryfall-all" if full else "import-scryfall"

    try:
        result = subprocess.run(
            ["make", make_target],
            cwd=config.project_root,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for large imports
        )

        return {
            "triggered": result.returncode == 0,
            "task": "import_scryfall",
            "full_import": full,
            "stdout": result.stdout[-1000:] if result.stdout else "",  # Last 1000 chars
            "stderr": result.stderr[-500:] if result.stderr else "",
        }
    except Exception as e:
        return {"error": str(e)}
