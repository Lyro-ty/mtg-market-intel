"""
Code quality agent.

Checks code patterns and suggests improvements.
"""
import re
from pathlib import Path
from typing import Any

from structlog import get_logger

logger = get_logger()


class CodeQualityAgent:
    """
    Agent for checking code quality patterns.

    Checks:
    - Anti-patterns (bare except, print statements, TODO comments)
    - Project conventions (async patterns, error handling)
    - Potential security issues (hardcoded secrets, SQL injection risks)
    """

    def __init__(self):
        self.project_root = Path("/root/mtg-market-intel/mtg-market-intel")
        self.backend_root = self.project_root / "backend"

    async def check_patterns(self, directory: str | None = None) -> dict[str, Any]:
        """
        Check code follows project conventions.

        Args:
            directory: Specific directory to check (defaults to backend/app)

        Returns:
            dict with pattern violations found
        """
        target_dir = Path(directory) if directory else (self.backend_root / "app")
        violations = []

        if not target_dir.exists():
            return {"error": f"Directory not found: {target_dir}"}

        for py_file in target_dir.rglob("*.py"):
            content = py_file.read_text()
            rel_path = str(py_file.relative_to(self.backend_root))

            # Check for async session usage without context manager
            if "AsyncSession" in content:
                if "async with" not in content and "async for" not in content:
                    if "session" in content.lower():
                        violations.append({
                            "file": rel_path,
                            "type": "async_pattern",
                            "message": "AsyncSession used without 'async with' context manager",
                        })

            # Check for missing error handling in routes
            if "/routes/" in str(py_file):
                if "@router" in content:
                    # Check if there's try/except in the file
                    if "try:" not in content and "HTTPException" not in content:
                        violations.append({
                            "file": rel_path,
                            "type": "error_handling",
                            "message": "Route file missing explicit error handling",
                        })

            # Check for proper logging
            if "print(" in content and "test_" not in py_file.name:
                violations.append({
                    "file": rel_path,
                    "type": "logging",
                    "message": "Using print() instead of logger",
                })

        return {
            "violations": violations[:50],  # Limit to 50
            "total_count": len(violations),
            "status": "clean" if len(violations) == 0 else "issues_found",
        }

    async def find_antipatterns(self) -> dict[str, Any]:
        """
        Find common anti-patterns in the codebase.

        Returns:
            dict with anti-pattern instances found
        """
        antipatterns = []
        app_dir = self.backend_root / "app"

        if not app_dir.exists():
            return {"error": "Backend app directory not found"}

        for py_file in app_dir.rglob("*.py"):
            content = py_file.read_text()
            rel_path = str(py_file.relative_to(self.backend_root))
            lines = content.split("\n")

            for i, line in enumerate(lines, 1):
                # Bare except
                if re.match(r"^\s*except\s*:\s*$", line):
                    antipatterns.append({
                        "file": rel_path,
                        "line": i,
                        "type": "bare_except",
                        "message": "Bare 'except:' catches all exceptions including KeyboardInterrupt",
                    })

                # Hardcoded secrets (simple check)
                if re.search(r"(password|secret|api_key|token)\s*=\s*['\"][^'\"]", line, re.I):
                    if "os.environ" not in line and "settings." not in line:
                        antipatterns.append({
                            "file": rel_path,
                            "line": i,
                            "type": "hardcoded_secret",
                            "message": "Possible hardcoded secret - use environment variable",
                        })

                # SQL injection risk
                if "f\"" in line or "f'" in line:
                    if "SELECT" in line.upper() or "INSERT" in line.upper() or "UPDATE" in line.upper():
                        antipatterns.append({
                            "file": rel_path,
                            "line": i,
                            "type": "sql_injection_risk",
                            "message": "F-string in SQL query - use parameterized queries",
                        })

        return {
            "antipatterns": antipatterns[:50],
            "total_count": len(antipatterns),
            "status": "clean" if len(antipatterns) == 0 else "issues_found",
        }

    async def count_todos(self) -> dict[str, Any]:
        """
        Count TODO/FIXME comments in the codebase.

        Returns:
            dict with TODO counts by file
        """
        todos = []
        app_dir = self.backend_root / "app"

        if not app_dir.exists():
            return {"error": "Backend app directory not found"}

        for py_file in app_dir.rglob("*.py"):
            content = py_file.read_text()
            rel_path = str(py_file.relative_to(self.backend_root))
            lines = content.split("\n")

            for i, line in enumerate(lines, 1):
                if "TODO" in line or "FIXME" in line or "XXX" in line:
                    # Extract the comment content
                    match = re.search(r"(TODO|FIXME|XXX)[:\s]*(.+)", line)
                    if match:
                        todos.append({
                            "file": rel_path,
                            "line": i,
                            "type": match.group(1),
                            "message": match.group(2).strip()[:100],
                        })

        return {
            "todos": todos[:100],
            "total_count": len(todos),
            "by_type": {
                "TODO": len([t for t in todos if t["type"] == "TODO"]),
                "FIXME": len([t for t in todos if t["type"] == "FIXME"]),
                "XXX": len([t for t in todos if t["type"] == "XXX"]),
            },
        }

    async def run_full_check(self) -> dict[str, Any]:
        """
        Run all code quality checks.
        """
        logger.info("running_code_quality_check")

        patterns = await self.check_patterns()
        antipatterns = await self.find_antipatterns()
        todos = await self.count_todos()

        total_issues = (
            patterns.get("total_count", 0) +
            antipatterns.get("total_count", 0)
        )

        if total_issues == 0:
            status = "excellent"
        elif total_issues <= 5:
            status = "good"
        elif total_issues <= 20:
            status = "acceptable"
        else:
            status = "needs_improvement"

        report = {
            "status": status,
            "total_issues": total_issues,
            "pattern_violations": patterns,
            "antipatterns": antipatterns,
            "todos": todos,
        }

        logger.info("code_quality_check_complete", status=status, issues=total_issues)
        return report
