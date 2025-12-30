"""
MCP Server configuration.

Reads environment variables for database, API, and safety settings.
"""
import os
from dataclasses import dataclass
from enum import Enum


class Environment(str, Enum):
    DEV = "dev"
    PROD = "prod"


@dataclass
class MCPConfig:
    """MCP Server configuration."""

    env: Environment
    database_url: str
    api_url: str
    test_user_id: int | None
    log_writes: bool
    project_root: str

    @property
    def is_dev(self) -> bool:
        return self.env == Environment.DEV

    @property
    def can_write_inventory(self) -> bool:
        """Check if inventory writes are allowed (dev mode + test user configured)."""
        return self.is_dev and self.test_user_id is not None


def load_config() -> MCPConfig:
    """Load configuration from environment variables."""
    env_str = os.getenv("MTG_MCP_ENV", "dev").lower()
    env = Environment.DEV if env_str == "dev" else Environment.PROD

    # Database URL is required
    database_url = os.getenv("MTG_MCP_DATABASE_URL")
    if not database_url:
        # Fall back to constructing from parts
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        user = os.getenv("POSTGRES_USER", "dualcaster_user")
        password = os.getenv("POSTGRES_PASSWORD", "")
        db = os.getenv("POSTGRES_DB", "dualcaster_deals")
        database_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

    # API URL defaults based on environment
    default_api = "http://localhost:8000" if env == Environment.DEV else "https://dualcasterdeals.com"
    api_url = os.getenv("MTG_MCP_API_URL", default_api)

    # Test user for inventory writes (only works in dev)
    test_user_id_str = os.getenv("MTG_MCP_TEST_USER_ID")
    test_user_id = int(test_user_id_str) if test_user_id_str else None

    # Logging
    log_writes = os.getenv("MTG_MCP_LOG_WRITES", "true").lower() in ("true", "1", "yes")

    # Project root (for reading docs, etc.)
    project_root = os.getenv("MTG_MCP_PROJECT_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    return MCPConfig(
        env=env,
        database_url=database_url,
        api_url=api_url,
        test_user_id=test_user_id,
        log_writes=log_writes,
        project_root=project_root,
    )


# Global config instance
config = load_config()
