"""
Log access tools for MCP server.

Provides tools to read container logs and find errors.
"""
from typing import Any
import subprocess
import re

from mcp_server.config import config


async def get_container_logs(
    container: str = "backend",
    lines: int = 100,
    since: str | None = None,
) -> dict[str, Any]:
    """
    Get logs from a Docker container.

    Args:
        container: Container name (backend, frontend, worker, db, redis)
        lines: Number of lines to tail (default 100)
        since: Time filter (e.g., "1h", "30m", "2023-01-01")

    Returns:
        Log lines from the container
    """
    cmd = ["docker", "compose", "logs", "--tail", str(lines)]
    if since:
        cmd.extend(["--since", since])
    cmd.append(container)

    try:
        result = subprocess.run(
            cmd,
            cwd=config.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        return {
            "container": container,
            "lines": lines,
            "logs": result.stdout,
            "stderr": result.stderr if result.returncode != 0 else None,
        }
    except Exception as e:
        return {"error": str(e)}


async def get_recent_errors(
    container: str = "backend",
    lines: int = 500,
) -> dict[str, Any]:
    """
    Find recent errors in container logs.

    Args:
        container: Container name
        lines: Number of lines to search through

    Returns:
        Error entries with context
    """
    logs_result = await get_container_logs(container, lines)
    if "error" in logs_result:
        return logs_result

    log_text = logs_result.get("logs", "")

    # Find error patterns
    error_patterns = [
        r"(?i)error[:\s].*",
        r"(?i)exception[:\s].*",
        r"(?i)traceback.*",
        r"(?i)failed[:\s].*",
        r"(?i)fatal[:\s].*",
    ]

    errors = []
    lines_list = log_text.split("\n")

    for i, line in enumerate(lines_list):
        for pattern in error_patterns:
            if re.search(pattern, line):
                # Get context (2 lines before, 2 after)
                start = max(0, i - 2)
                end = min(len(lines_list), i + 3)
                context = "\n".join(lines_list[start:end])
                errors.append({
                    "line_number": i,
                    "match": line.strip(),
                    "context": context,
                })
                break

    return {
        "container": container,
        "error_count": len(errors),
        "errors": errors[:20],  # Limit to 20 errors
    }
