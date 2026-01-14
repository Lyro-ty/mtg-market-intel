"""
Implementation status and code quality tools.

Tools for validating implementation against design docs,
finding missing tests, and checking code quality.
"""
import os
import re
from pathlib import Path
from typing import Any

from mcp_server.utils.db import execute_query


# Base paths
PROJECT_ROOT = Path("/root/mtg-market-intel/mtg-market-intel")
BACKEND_ROOT = PROJECT_ROOT / "backend"
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


async def get_implementation_status() -> dict[str, Any]:
    """
    Get implementation status overview.

    Returns counts of routes, models, tests, and identifies gaps.
    """
    status = {
        "routes": {"count": 0, "files": []},
        "models": {"count": 0, "files": []},
        "schemas": {"count": 0, "files": []},
        "tests": {"count": 0, "files": []},
        "frontend_pages": {"count": 0, "files": []},
        "celery_tasks": {"count": 0, "files": []},
        "gaps": [],
    }

    # Count route files
    routes_dir = BACKEND_ROOT / "app" / "api" / "routes"
    if routes_dir.exists():
        route_files = list(routes_dir.glob("*.py"))
        status["routes"]["files"] = [f.stem for f in route_files if f.stem != "__init__"]
        status["routes"]["count"] = len(status["routes"]["files"])

    # Count model files
    models_dir = BACKEND_ROOT / "app" / "models"
    if models_dir.exists():
        model_files = list(models_dir.glob("*.py"))
        status["models"]["files"] = [f.stem for f in model_files if f.stem not in ["__init__", "base"]]
        status["models"]["count"] = len(status["models"]["files"])

    # Count schema files
    schemas_dir = BACKEND_ROOT / "app" / "schemas"
    if schemas_dir.exists():
        schema_files = list(schemas_dir.glob("*.py"))
        status["schemas"]["files"] = [f.stem for f in schema_files if f.stem != "__init__"]
        status["schemas"]["count"] = len(status["schemas"]["files"])

    # Count test files
    tests_dir = BACKEND_ROOT / "tests"
    if tests_dir.exists():
        test_files = list(tests_dir.rglob("test_*.py"))
        status["tests"]["files"] = [str(f.relative_to(tests_dir)) for f in test_files]
        status["tests"]["count"] = len(status["tests"]["files"])

    # Count frontend pages
    app_dir = FRONTEND_ROOT / "src" / "app"
    if app_dir.exists():
        page_files = list(app_dir.rglob("page.tsx"))
        status["frontend_pages"]["files"] = [
            str(f.parent.relative_to(app_dir)) for f in page_files
        ]
        status["frontend_pages"]["count"] = len(status["frontend_pages"]["files"])

    # Count Celery task files
    tasks_dir = BACKEND_ROOT / "app" / "tasks"
    if tasks_dir.exists():
        task_files = list(tasks_dir.glob("*.py"))
        status["celery_tasks"]["files"] = [
            f.stem for f in task_files
            if f.stem not in ["__init__", "celery_app", "utils", "error_handlers"]
        ]
        status["celery_tasks"]["count"] = len(status["celery_tasks"]["files"])

    # Find gaps: routes without tests
    route_names = set(status["routes"]["files"])
    test_names = set()
    for t in status["tests"]["files"]:
        if t.startswith("api/test_"):
            test_names.add(t.replace("api/test_", "").replace(".py", ""))

    routes_without_tests = route_names - test_names
    if routes_without_tests:
        status["gaps"].append({
            "type": "missing_tests",
            "description": f"Routes without tests: {', '.join(sorted(routes_without_tests))}",
        })

    # Find gaps: models without schemas
    model_names = set(status["models"]["files"])
    schema_names = set(status["schemas"]["files"])
    models_without_schemas = model_names - schema_names
    if models_without_schemas:
        status["gaps"].append({
            "type": "missing_schemas",
            "description": f"Models without schemas: {', '.join(sorted(models_without_schemas))}",
        })

    return status


async def list_missing_tests() -> dict[str, Any]:
    """
    Find routes and services that lack test coverage.

    Returns list of files that should have tests but don't.
    """
    missing = {
        "routes_without_tests": [],
        "services_without_tests": [],
        "tasks_without_tests": [],
    }

    # Get route files
    routes_dir = BACKEND_ROOT / "app" / "api" / "routes"
    tests_api_dir = BACKEND_ROOT / "tests" / "api"

    if routes_dir.exists():
        for route_file in routes_dir.glob("*.py"):
            if route_file.stem == "__init__":
                continue
            test_file = tests_api_dir / f"test_{route_file.stem}.py"
            if not test_file.exists():
                missing["routes_without_tests"].append(route_file.stem)

    # Get service files
    services_dir = BACKEND_ROOT / "app" / "services"
    tests_services_dir = BACKEND_ROOT / "tests" / "services"

    if services_dir.exists():
        for service_file in services_dir.glob("*.py"):
            if service_file.stem == "__init__":
                continue
            test_file = tests_services_dir / f"test_{service_file.stem}.py"
            if not test_file.exists():
                missing["services_without_tests"].append(service_file.stem)

    # Get task files
    tasks_dir = BACKEND_ROOT / "app" / "tasks"
    tests_tasks_dir = BACKEND_ROOT / "tests" / "tasks"

    if tasks_dir.exists():
        for task_file in tasks_dir.glob("*.py"):
            if task_file.stem in ["__init__", "celery_app", "utils", "error_handlers"]:
                continue
            test_file = tests_tasks_dir / f"test_{task_file.stem}.py"
            if not test_file.exists():
                missing["tasks_without_tests"].append(task_file.stem)

    return missing


async def get_schema_differences() -> dict[str, Any]:
    """
    Compare backend Pydantic schemas with SQLAlchemy models.

    Returns fields that exist in models but not schemas, and vice versa.
    """
    differences = []

    models_dir = BACKEND_ROOT / "app" / "models"
    schemas_dir = BACKEND_ROOT / "app" / "schemas"

    if not models_dir.exists() or not schemas_dir.exists():
        return {"error": "Models or schemas directory not found"}

    # Simple pattern matching for field names
    model_field_pattern = re.compile(r"(\w+):\s*Mapped\[")
    schema_field_pattern = re.compile(r"^\s+(\w+):\s*(?:int|str|float|bool|datetime|Decimal|list|dict|Optional)", re.MULTILINE)

    for model_file in models_dir.glob("*.py"):
        if model_file.stem in ["__init__", "base"]:
            continue

        schema_file = schemas_dir / f"{model_file.stem}.py"
        if not schema_file.exists():
            differences.append({
                "model": model_file.stem,
                "issue": "no_schema_file",
                "description": f"No schema file for model: {model_file.stem}",
            })
            continue

        # Extract fields from model
        model_content = model_file.read_text()
        model_fields = set(model_field_pattern.findall(model_content))

        # Extract fields from schema
        schema_content = schema_file.read_text()
        schema_fields = set(schema_field_pattern.findall(schema_content))

        # Ignore common fields that might differ
        ignore_fields = {"id", "created_at", "updated_at", "password", "hashed_password"}
        model_fields -= ignore_fields
        schema_fields -= ignore_fields

        # Find differences
        in_model_not_schema = model_fields - schema_fields
        in_schema_not_model = schema_fields - model_fields

        if in_model_not_schema or in_schema_not_model:
            differences.append({
                "model": model_file.stem,
                "in_model_not_schema": list(in_model_not_schema),
                "in_schema_not_model": list(in_schema_not_model),
            })

    return {"differences": differences, "count": len(differences)}


async def analyze_dead_letter_queue() -> dict[str, Any]:
    """
    Analyze failed Celery tasks in the dead letter queue.

    Returns summary of failed tasks with error patterns.
    """
    # Query Redis for DLQ contents (if configured)
    # This is a placeholder - actual implementation depends on Redis setup

    query = """
    SELECT
        name,
        status,
        COUNT(*) as count,
        MAX(date_done) as last_occurred
    FROM celery_taskmeta
    WHERE status = 'FAILURE'
    GROUP BY name, status
    ORDER BY count DESC
    LIMIT 20
    """

    try:
        rows = await execute_query(query)
        return {
            "failed_tasks": [
                {
                    "task_name": row["name"],
                    "failure_count": row["count"],
                    "last_occurred": str(row["last_occurred"]) if row["last_occurred"] else None,
                }
                for row in rows
            ],
            "total_failures": sum(row["count"] for row in rows),
        }
    except Exception as e:
        # Table might not exist
        return {
            "error": f"Could not query task metadata: {str(e)}",
            "note": "Celery task result backend may not be configured",
        }


async def get_signal_coverage() -> dict[str, Any]:
    """
    Get coverage of signal types in the analytics system.

    Returns which signal types exist and their counts.
    """
    query = """
    SELECT
        signal_type,
        COUNT(*) as count,
        MIN(created_at) as first_seen,
        MAX(created_at) as last_seen
    FROM signals
    GROUP BY signal_type
    ORDER BY count DESC
    """

    expected_signals = [
        "PRICE_SPIKE",
        "PRICE_DROP",
        "META_SPIKE",
        "META_DROP",
        "SUPPLY_LOW",
        "SUPPLY_HIGH",
        "ARBITRAGE_OPPORTUNITY",
        "PREDICTION_UP",
        "PREDICTION_DOWN",
    ]

    try:
        rows = await execute_query(query)
        existing = {row["signal_type"]: row for row in rows}

        coverage = []
        for signal_type in expected_signals:
            if signal_type in existing:
                row = existing[signal_type]
                coverage.append({
                    "signal_type": signal_type,
                    "status": "active",
                    "count": row["count"],
                    "first_seen": str(row["first_seen"]) if row["first_seen"] else None,
                    "last_seen": str(row["last_seen"]) if row["last_seen"] else None,
                })
            else:
                coverage.append({
                    "signal_type": signal_type,
                    "status": "missing",
                    "count": 0,
                })

        # Add any unexpected signals found
        for signal_type, row in existing.items():
            if signal_type not in expected_signals:
                coverage.append({
                    "signal_type": signal_type,
                    "status": "unexpected",
                    "count": row["count"],
                    "first_seen": str(row["first_seen"]) if row["first_seen"] else None,
                    "last_seen": str(row["last_seen"]) if row["last_seen"] else None,
                })

        missing_count = len([c for c in coverage if c["status"] == "missing"])
        active_count = len([c for c in coverage if c["status"] == "active"])

        return {
            "coverage": coverage,
            "summary": {
                "active": active_count,
                "missing": missing_count,
                "total_expected": len(expected_signals),
                "coverage_percent": round(active_count / len(expected_signals) * 100, 1),
            },
        }
    except Exception as e:
        return {"error": str(e)}


async def get_empty_tables() -> dict[str, Any]:
    """
    Find database tables with zero rows.

    Useful for identifying data gaps.
    """
    query = """
    SELECT
        schemaname,
        relname as table_name,
        n_live_tup as row_count
    FROM pg_stat_user_tables
    WHERE n_live_tup = 0
    ORDER BY relname
    """

    try:
        rows = await execute_query(query)
        return {
            "empty_tables": [
                {"table": row["table_name"], "schema": row["schemaname"]}
                for row in rows
            ],
            "count": len(rows),
        }
    except Exception as e:
        return {"error": str(e)}
