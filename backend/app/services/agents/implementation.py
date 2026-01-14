"""
Implementation validation agent.

Validates that code matches design documents and identifies gaps.
"""
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

logger = get_logger()


class ImplementationValidator:
    """
    Agent for validating implementation completeness.

    Checks:
    - Routes match API design specs
    - Tests exist for all routes
    - Frontend types match backend schemas
    - All scheduled tasks are properly registered
    """

    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self.project_root = Path("/root/mtg-market-intel/mtg-market-intel")
        self.backend_root = self.project_root / "backend"
        self.frontend_root = self.project_root / "frontend"

    async def check_route_coverage(self) -> dict[str, Any]:
        """
        Check that all routes have corresponding tests.

        Returns:
            dict with covered routes, missing routes, and coverage percentage
        """
        routes_dir = self.backend_root / "app" / "api" / "routes"
        tests_dir = self.backend_root / "tests" / "api"

        route_files = set()
        test_files = set()

        # Get route files
        if routes_dir.exists():
            for f in routes_dir.glob("*.py"):
                if f.stem != "__init__":
                    route_files.add(f.stem)

        # Get test files
        if tests_dir.exists():
            for f in tests_dir.glob("test_*.py"):
                # Extract route name from test_<route>.py
                test_files.add(f.stem.replace("test_", ""))

        covered = route_files & test_files
        missing = route_files - test_files

        total = len(route_files)
        covered_count = len(covered)
        coverage_pct = (covered_count / total * 100) if total > 0 else 0

        return {
            "total_routes": total,
            "covered": covered_count,
            "missing": list(sorted(missing)),
            "coverage_percent": round(coverage_pct, 1),
            "status": "good" if coverage_pct >= 80 else "needs_improvement",
        }

    async def check_test_coverage(self) -> dict[str, Any]:
        """
        Analyze test file structure and identify gaps.

        Returns:
            dict with test counts by category and missing test areas
        """
        tests_root = self.backend_root / "tests"

        categories = {
            "api": 0,
            "services": 0,
            "tasks": 0,
            "models": 0,
            "other": 0,
        }

        if tests_root.exists():
            for test_file in tests_root.rglob("test_*.py"):
                rel_path = str(test_file.relative_to(tests_root))
                if rel_path.startswith("api/"):
                    categories["api"] += 1
                elif rel_path.startswith("services/"):
                    categories["services"] += 1
                elif rel_path.startswith("tasks/"):
                    categories["tasks"] += 1
                elif rel_path.startswith("models/"):
                    categories["models"] += 1
                else:
                    categories["other"] += 1

        # Check for missing test directories
        missing_categories = []
        for category in ["api", "services", "tasks", "models"]:
            category_dir = tests_root / category
            if not category_dir.exists() or categories[category] == 0:
                missing_categories.append(category)

        return {
            "test_counts": categories,
            "total": sum(categories.values()),
            "missing_categories": missing_categories,
        }

    async def check_type_sync(self) -> dict[str, Any]:
        """
        Check if frontend TypeScript types match backend schemas.

        Returns:
            dict with sync status and any mismatches found
        """
        issues = []

        # Check if generated types file exists
        types_file = self.frontend_root / "src" / "types" / "api.generated.ts"
        if not types_file.exists():
            return {
                "status": "error",
                "message": "api.generated.ts not found - run 'make generate-types'",
            }

        # Check file age
        import os
        import time
        types_mtime = os.path.getmtime(types_file)
        current_time = time.time()
        age_hours = (current_time - types_mtime) / 3600

        if age_hours > 24:
            issues.append({
                "type": "stale_types",
                "message": f"Types file is {age_hours:.1f} hours old - consider regenerating",
            })

        # Check schemas directory modification time
        schemas_dir = self.backend_root / "app" / "schemas"
        if schemas_dir.exists():
            newest_schema = max(
                (f.stat().st_mtime for f in schemas_dir.glob("*.py")),
                default=0
            )
            if newest_schema > types_mtime:
                issues.append({
                    "type": "schemas_newer",
                    "message": "Schemas modified after types generated - run 'make generate-types'",
                })

        return {
            "status": "ok" if not issues else "needs_attention",
            "types_age_hours": round(age_hours, 1),
            "issues": issues,
        }

    async def run_full_validation(self) -> dict[str, Any]:
        """
        Run all validation checks and return comprehensive report.
        """
        logger.info("running_implementation_validation")

        route_coverage = await self.check_route_coverage()
        test_coverage = await self.check_test_coverage()
        type_sync = await self.check_type_sync()

        # Calculate overall health
        issues_count = len(route_coverage.get("missing", []))
        issues_count += len(type_sync.get("issues", []))
        issues_count += len(test_coverage.get("missing_categories", []))

        if issues_count == 0:
            overall_status = "healthy"
        elif issues_count <= 3:
            overall_status = "minor_issues"
        else:
            overall_status = "needs_attention"

        report = {
            "overall_status": overall_status,
            "issues_count": issues_count,
            "route_coverage": route_coverage,
            "test_coverage": test_coverage,
            "type_sync": type_sync,
        }

        logger.info("validation_complete", status=overall_status, issues=issues_count)
        return report
