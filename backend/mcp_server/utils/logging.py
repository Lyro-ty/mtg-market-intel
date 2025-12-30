"""
Write operation logging for MCP server.

Logs all write operations to file and console for audit trail.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_server.config import config


def get_log_path() -> Path:
    """Get the path to the write log file."""
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir / "writes.log"


def log_write_operation(
    tool_name: str,
    parameters: dict[str, Any],
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Log a write operation to file and console."""
    if not config.log_writes:
        return

    timestamp = datetime.now(timezone.utc).isoformat()

    log_entry = {
        "timestamp": timestamp,
        "environment": config.env.value,
        "tool": tool_name,
        "parameters": parameters,
        "result": result,
        "error": error,
    }

    # Console warning
    warning_msg = f"[MCP WRITE] {timestamp} - {tool_name}"
    print(f"\033[93m{warning_msg}\033[0m", file=sys.stderr)

    # File log
    log_path = get_log_path()
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def require_dev_mode(tool_name: str) -> None:
    """Raise an error if not in dev mode."""
    if not config.is_dev:
        raise PermissionError(
            f"Tool '{tool_name}' is only available in dev mode. "
            f"Current environment: {config.env.value}"
        )


def require_test_user(tool_name: str, user_id: int) -> None:
    """Raise an error if user is not the test user."""
    if config.test_user_id is None:
        raise PermissionError(
            f"Tool '{tool_name}' requires MTG_MCP_TEST_USER_ID to be set."
        )
    if user_id != config.test_user_id:
        raise PermissionError(
            f"Tool '{tool_name}' can only operate on test user (ID: {config.test_user_id}). "
            f"Attempted user ID: {user_id}"
        )
