# MCP Server Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a comprehensive MCP server for development assistance with 49 tools and 8 resources.

**Architecture:** Python MCP server in `backend/mcp_server/` using direct database access for introspection and httpx for API calls. Write operations restricted to dev mode + test user.

**Tech Stack:** Python MCP SDK, SQLAlchemy (async), httpx, Redis, structlog

**Worktree:** `/home/lyro/mtg-market-intel/.worktrees/mcp-server`

---

## Phase 1: Foundation (Sequential - Must Complete First)

### Task 1.1: Add MCP Dependency

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add mcp package**

Add to `backend/requirements.txt` after the Utilities section:

```
# MCP Server
mcp>=1.0.0
```

**Step 2: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat(mcp): add mcp dependency"
```

---

### Task 1.2: Create Directory Structure

**Files:**
- Create: `backend/mcp_server/__init__.py`
- Create: `backend/mcp_server/tools/__init__.py`
- Create: `backend/mcp_server/resources/__init__.py`
- Create: `backend/mcp_server/utils/__init__.py`

**Step 1: Create directories and init files**

```bash
mkdir -p backend/mcp_server/tools
mkdir -p backend/mcp_server/resources
mkdir -p backend/mcp_server/utils
mkdir -p backend/mcp_server/logs
touch backend/mcp_server/__init__.py
touch backend/mcp_server/tools/__init__.py
touch backend/mcp_server/resources/__init__.py
touch backend/mcp_server/utils/__init__.py
```

**Step 2: Add package docstrings**

`backend/mcp_server/__init__.py`:
```python
"""
MCP Server for MTG Market Intelligence.

Provides development tools for querying cards, prices, schemas, and system health.
"""

__version__ = "0.1.0"
```

**Step 3: Commit**

```bash
git add backend/mcp_server/
git commit -m "feat(mcp): create directory structure"
```

---

### Task 1.3: Implement Configuration

**Files:**
- Create: `backend/mcp_server/config.py`

**Step 1: Create config module**

`backend/mcp_server/config.py`:
```python
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
```

**Step 2: Commit**

```bash
git add backend/mcp_server/config.py
git commit -m "feat(mcp): add configuration module"
```

---

### Task 1.4: Implement Database Utility

**Files:**
- Create: `backend/mcp_server/utils/db.py`

**Step 1: Create database utility**

`backend/mcp_server/utils/db.py`:
```python
"""
Database connection utilities for MCP server.

Provides async database access independent of the main app.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from mcp_server.config import config


# Create engine lazily to avoid connection at import time
_engine = None
_session_maker = None


def get_engine():
    """Get or create the async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            config.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_maker():
    """Get or create the session maker."""
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_maker


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def execute_query(query: str, params: dict | None = None) -> list[dict[str, Any]]:
    """Execute a read-only SQL query and return results as dicts."""
    # Safety: only allow SELECT queries
    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed")

    async with get_db_session() as session:
        result = await session.execute(text(query), params or {})
        rows = result.fetchall()
        columns = result.keys()
        return [dict(zip(columns, row)) for row in rows]


async def get_table_names() -> list[str]:
    """Get all table names in the database."""
    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """
    rows = await execute_query(query)
    return [row["table_name"] for row in rows]


async def get_table_columns(table_name: str) -> list[dict[str, Any]]:
    """Get column information for a table."""
    query = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :table_name
        ORDER BY ordinal_position
    """
    return await execute_query(query, {"table_name": table_name})


async def get_row_count(table_name: str) -> int:
    """Get approximate row count for a table."""
    # Use reltuples for speed on large tables
    query = """
        SELECT reltuples::bigint as count
        FROM pg_class
        WHERE relname = :table_name
    """
    rows = await execute_query(query, {"table_name": table_name})
    if rows:
        return rows[0]["count"]
    return 0


async def check_connection() -> dict[str, Any]:
    """Check database connectivity and return status."""
    import time
    start = time.time()
    try:
        async with get_db_session() as session:
            result = await session.execute(text("SELECT 1"))
            result.fetchone()
        latency_ms = (time.time() - start) * 1000
        return {
            "connected": True,
            "latency_ms": round(latency_ms, 2),
            "database_url": config.database_url.split("@")[-1],  # Hide credentials
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }
```

**Step 2: Commit**

```bash
git add backend/mcp_server/utils/db.py
git commit -m "feat(mcp): add database utility"
```

---

### Task 1.5: Implement API Client Utility

**Files:**
- Create: `backend/mcp_server/utils/api.py`

**Step 1: Create API client utility**

`backend/mcp_server/utils/api.py`:
```python
"""
HTTP API client for MCP server.

Makes requests to the FastAPI backend for operations that should go through business logic.
"""
from typing import Any
import httpx

from mcp_server.config import config


class APIClient:
    """Async HTTP client for the FastAPI backend."""

    def __init__(self):
        self.base_url = config.api_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        """Make a GET request to the API."""
        client = await self._get_client()
        response = await client.get(f"/api{path}", params=params)
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, json: dict | None = None) -> dict[str, Any]:
        """Make a POST request to the API."""
        client = await self._get_client()
        response = await client.post(f"/api{path}", json=json)
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> dict[str, Any]:
        """Check API health."""
        try:
            client = await self._get_client()
            response = await client.get("/api/health")
            return {
                "healthy": response.status_code == 200,
                "status_code": response.status_code,
                "base_url": self.base_url,
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "base_url": self.base_url,
            }


# Global client instance
api_client = APIClient()
```

**Step 2: Commit**

```bash
git add backend/mcp_server/utils/api.py
git commit -m "feat(mcp): add API client utility"
```

---

### Task 1.6: Implement Write Logging Utility

**Files:**
- Create: `backend/mcp_server/utils/logging.py`

**Step 1: Create logging utility**

`backend/mcp_server/utils/logging.py`:
```python
"""
Write operation logging for MCP server.

Logs all write operations to file and console for audit trail.
"""
import os
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
```

**Step 2: Commit**

```bash
git add backend/mcp_server/utils/logging.py
git commit -m "feat(mcp): add write operation logging"
```

---

### Task 1.7: Update Utils __init__.py

**Files:**
- Modify: `backend/mcp_server/utils/__init__.py`

**Step 1: Export utilities**

`backend/mcp_server/utils/__init__.py`:
```python
"""MCP Server utilities."""
from mcp_server.utils.db import (
    get_db_session,
    execute_query,
    get_table_names,
    get_table_columns,
    get_row_count,
    check_connection,
)
from mcp_server.utils.api import api_client
from mcp_server.utils.logging import (
    log_write_operation,
    require_dev_mode,
    require_test_user,
)

__all__ = [
    "get_db_session",
    "execute_query",
    "get_table_names",
    "get_table_columns",
    "get_row_count",
    "check_connection",
    "api_client",
    "log_write_operation",
    "require_dev_mode",
    "require_test_user",
]
```

**Step 2: Commit**

```bash
git add backend/mcp_server/utils/__init__.py
git commit -m "feat(mcp): export utilities from package"
```

---

## Phase 2: Core Tools (Can Run in Parallel)

### Task 2.1: Implement Card Tools

**Files:**
- Create: `backend/mcp_server/tools/cards.py`

**Step 1: Create card tools**

`backend/mcp_server/tools/cards.py`:
```python
"""
Card lookup tools for MCP server.

Provides tools to search and retrieve card information.
"""
from typing import Any
from mcp_server.utils import execute_query, api_client


async def get_card_by_id(card_id: int) -> dict[str, Any]:
    """
    Fetch a card by its database ID.

    Args:
        card_id: The database ID of the card

    Returns:
        Card object with name, set, prices, etc.
    """
    query = """
        SELECT
            c.id, c.name, c.set_code, c.set_name, c.collector_number,
            c.scryfall_id, c.oracle_id, c.rarity, c.mana_cost, c.cmc,
            c.type_line, c.oracle_text, c.colors, c.color_identity,
            c.power, c.toughness, c.image_uri_small, c.image_uri_normal,
            c.scryfall_price_usd, c.scryfall_price_usd_foil,
            c.legalities, c.edhrec_rank, c.reserved_list
        FROM cards c
        WHERE c.id = :card_id
    """
    rows = await execute_query(query, {"card_id": card_id})
    if not rows:
        return {"error": f"Card with ID {card_id} not found"}
    return rows[0]


async def get_card_by_name(name: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Search for cards by name (fuzzy match).

    Args:
        name: Card name to search for
        limit: Maximum number of results (default 10)

    Returns:
        List of matching cards
    """
    query = """
        SELECT
            id, name, set_code, set_name, rarity, mana_cost, type_line,
            scryfall_price_usd, image_uri_small
        FROM cards
        WHERE name ILIKE :pattern
        ORDER BY
            CASE WHEN name ILIKE :exact THEN 0 ELSE 1 END,
            name
        LIMIT :limit
    """
    pattern = f"%{name}%"
    exact = name
    rows = await execute_query(query, {"pattern": pattern, "exact": exact, "limit": limit})
    return rows


async def get_card_by_scryfall_id(scryfall_id: str) -> dict[str, Any]:
    """
    Fetch a card by its Scryfall UUID.

    Args:
        scryfall_id: The Scryfall UUID of the card

    Returns:
        Card object
    """
    query = """
        SELECT
            id, name, set_code, set_name, collector_number,
            scryfall_id, oracle_id, rarity, mana_cost, cmc,
            type_line, oracle_text, colors, color_identity,
            scryfall_price_usd, scryfall_price_usd_foil, legalities
        FROM cards
        WHERE scryfall_id = :scryfall_id
    """
    rows = await execute_query(query, {"scryfall_id": scryfall_id})
    if not rows:
        return {"error": f"Card with Scryfall ID {scryfall_id} not found"}
    return rows[0]


async def search_cards(
    colors: str | None = None,
    card_type: str | None = None,
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    rarity: str | None = None,
    set_code: str | None = None,
    format_legal: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Search cards with filters.

    Args:
        colors: Color filter (e.g., "W", "UB", "WUBRG")
        card_type: Type filter (e.g., "Creature", "Instant")
        cmc_min: Minimum converted mana cost
        cmc_max: Maximum converted mana cost
        rarity: Rarity filter (common, uncommon, rare, mythic)
        set_code: Set code filter (e.g., "MKM", "ONE")
        format_legal: Format legality filter (e.g., "modern", "commander")
        limit: Maximum results (default 20)
        offset: Pagination offset

    Returns:
        Paginated list of matching cards with total count
    """
    conditions = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if colors:
        # Match cards containing these colors
        for i, color in enumerate(colors.upper()):
            if color in "WUBRG":
                conditions.append(f"colors::text ILIKE :color{i}")
                params[f"color{i}"] = f"%{color}%"

    if card_type:
        conditions.append("type_line ILIKE :card_type")
        params["card_type"] = f"%{card_type}%"

    if cmc_min is not None:
        conditions.append("cmc >= :cmc_min")
        params["cmc_min"] = cmc_min

    if cmc_max is not None:
        conditions.append("cmc <= :cmc_max")
        params["cmc_max"] = cmc_max

    if rarity:
        conditions.append("rarity = :rarity")
        params["rarity"] = rarity.lower()

    if set_code:
        conditions.append("set_code = :set_code")
        params["set_code"] = set_code.lower()

    if format_legal:
        conditions.append(f"legalities->>'{format_legal.lower()}' = 'legal'")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Get total count
    count_query = f"SELECT COUNT(*) as count FROM cards WHERE {where_clause}"
    count_result = await execute_query(count_query, params)
    total = count_result[0]["count"] if count_result else 0

    # Get results
    query = f"""
        SELECT
            id, name, set_code, set_name, rarity, mana_cost, cmc,
            type_line, colors, scryfall_price_usd, image_uri_small
        FROM cards
        WHERE {where_clause}
        ORDER BY name
        LIMIT :limit OFFSET :offset
    """
    rows = await execute_query(query, params)

    return {
        "cards": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_random_cards(count: int = 5) -> list[dict[str, Any]]:
    """
    Get random cards (useful for testing).

    Args:
        count: Number of random cards to return (default 5, max 20)

    Returns:
        List of random cards
    """
    count = min(count, 20)  # Cap at 20
    query = """
        SELECT
            id, name, set_code, set_name, rarity, mana_cost, type_line,
            scryfall_price_usd, image_uri_small
        FROM cards
        ORDER BY RANDOM()
        LIMIT :count
    """
    return await execute_query(query, {"count": count})
```

**Step 2: Commit**

```bash
git add backend/mcp_server/tools/cards.py
git commit -m "feat(mcp): add card lookup tools"
```

---

### Task 2.2: Implement Price Tools

**Files:**
- Create: `backend/mcp_server/tools/prices.py`

**Step 1: Create price tools**

`backend/mcp_server/tools/prices.py`:
```python
"""
Price data tools for MCP server.

Provides tools to query price data and market analytics.
"""
from typing import Any
from datetime import datetime, timedelta, timezone
from mcp_server.utils import execute_query, api_client


async def get_current_price(card_id: int) -> dict[str, Any]:
    """
    Get current price for a card across all marketplaces.

    Args:
        card_id: The database ID of the card

    Returns:
        Price breakdown by marketplace and condition
    """
    # Get card info first
    card_query = """
        SELECT name, set_code, scryfall_price_usd, scryfall_price_usd_foil
        FROM cards WHERE id = :card_id
    """
    card_rows = await execute_query(card_query, {"card_id": card_id})
    if not card_rows:
        return {"error": f"Card with ID {card_id} not found"}

    card = card_rows[0]

    # Get latest price snapshots
    price_query = """
        SELECT
            m.name as marketplace,
            ps.price,
            ps.currency,
            ps.condition,
            ps.is_foil,
            ps.time
        FROM price_snapshots ps
        JOIN marketplaces m ON ps.marketplace_id = m.id
        WHERE ps.card_id = :card_id
        AND ps.time >= NOW() - INTERVAL '24 hours'
        ORDER BY ps.time DESC
        LIMIT 20
    """
    prices = await execute_query(price_query, {"card_id": card_id})

    return {
        "card_id": card_id,
        "name": card["name"],
        "set_code": card["set_code"],
        "scryfall_price_usd": card["scryfall_price_usd"],
        "scryfall_price_usd_foil": card["scryfall_price_usd_foil"],
        "recent_prices": prices,
    }


async def get_price_history(
    card_id: int,
    days: int = 30,
    condition: str | None = None,
    is_foil: bool | None = None,
) -> dict[str, Any]:
    """
    Get historical prices for a card.

    Args:
        card_id: The database ID of the card
        days: Number of days of history (default 30)
        condition: Filter by condition (NEAR_MINT, LIGHTLY_PLAYED, etc.)
        is_foil: Filter by foil status

    Returns:
        Time-series price data
    """
    conditions = ["ps.card_id = :card_id", "ps.time >= NOW() - :interval::interval"]
    params: dict[str, Any] = {"card_id": card_id, "interval": f"{days} days"}

    if condition:
        conditions.append("ps.condition = :condition")
        params["condition"] = condition

    if is_foil is not None:
        conditions.append("ps.is_foil = :is_foil")
        params["is_foil"] = is_foil

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            DATE_TRUNC('day', ps.time) as date,
            m.name as marketplace,
            AVG(ps.price) as avg_price,
            MIN(ps.price) as min_price,
            MAX(ps.price) as max_price,
            COUNT(*) as samples
        FROM price_snapshots ps
        JOIN marketplaces m ON ps.marketplace_id = m.id
        WHERE {where_clause}
        GROUP BY DATE_TRUNC('day', ps.time), m.name
        ORDER BY date DESC, marketplace
    """
    rows = await execute_query(query, params)

    return {
        "card_id": card_id,
        "days": days,
        "condition": condition,
        "is_foil": is_foil,
        "history": rows,
    }


async def get_top_movers(window: str = "24h", limit: int = 10) -> dict[str, Any]:
    """
    Get top gaining and losing cards.

    Args:
        window: Time window ("24h" or "7d")
        limit: Number of cards per category (default 10)

    Returns:
        Top gainers and losers with percentage changes
    """
    try:
        # Use the API endpoint for this
        result = await api_client.get("/market/top-movers", params={"window": window, "limit": limit})
        return result
    except Exception as e:
        # Fall back to direct query
        interval = "1 day" if window == "24h" else "7 days"

        query = """
            WITH price_changes AS (
                SELECT
                    c.id,
                    c.name,
                    c.set_code,
                    c.scryfall_price_usd as current_price,
                    LAG(c.scryfall_price_usd) OVER (PARTITION BY c.id ORDER BY c.updated_at) as prev_price
                FROM cards c
                WHERE c.scryfall_price_usd IS NOT NULL
                AND c.scryfall_price_usd > 0.5
            )
            SELECT
                id, name, set_code, current_price,
                (current_price - prev_price) / NULLIF(prev_price, 0) * 100 as pct_change
            FROM price_changes
            WHERE prev_price IS NOT NULL
            ORDER BY pct_change DESC
            LIMIT :limit
        """
        gainers = await execute_query(query, {"limit": limit})

        query_losers = query.replace("ORDER BY pct_change DESC", "ORDER BY pct_change ASC")
        losers = await execute_query(query_losers, {"limit": limit})

        return {
            "window": window,
            "gainers": gainers,
            "losers": losers,
        }


async def get_market_overview() -> dict[str, Any]:
    """
    Get market-wide statistics.

    Returns:
        Total cards, price snapshots, average prices, etc.
    """
    try:
        return await api_client.get("/market/overview")
    except Exception:
        # Fall back to direct queries
        stats_query = """
            SELECT
                (SELECT COUNT(*) FROM cards) as total_cards,
                (SELECT COUNT(*) FROM cards WHERE scryfall_price_usd IS NOT NULL) as priced_cards,
                (SELECT COUNT(*) FROM price_snapshots WHERE time >= NOW() - INTERVAL '24 hours') as snapshots_24h,
                (SELECT AVG(scryfall_price_usd) FROM cards WHERE scryfall_price_usd IS NOT NULL) as avg_price,
                (SELECT COUNT(*) FROM marketplaces WHERE is_enabled = true) as active_marketplaces
        """
        rows = await execute_query(stats_query)
        return rows[0] if rows else {}


async def get_market_index(range: str = "30d") -> dict[str, Any]:
    """
    Get market index trend.

    Args:
        range: Time range ("7d", "30d", "90d", "1y")

    Returns:
        Normalized market index values over time
    """
    try:
        return await api_client.get("/market/index", params={"range": range})
    except Exception as e:
        return {"error": str(e), "range": range}
```

**Step 2: Commit**

```bash
git add backend/mcp_server/tools/prices.py
git commit -m "feat(mcp): add price data tools"
```

---

### Task 2.3: Implement Schema Tools

**Files:**
- Create: `backend/mcp_server/tools/schema.py`

**Step 1: Create schema tools**

`backend/mcp_server/tools/schema.py`:
```python
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
```

**Step 2: Commit**

```bash
git add backend/mcp_server/tools/schema.py
git commit -m "feat(mcp): add schema introspection tools"
```

---

### Task 2.4: Implement Database Tools

**Files:**
- Create: `backend/mcp_server/tools/database.py`

**Step 1: Create database tools**

`backend/mcp_server/tools/database.py`:
```python
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
```

**Step 2: Commit**

```bash
git add backend/mcp_server/tools/database.py
git commit -m "feat(mcp): add database query tools"
```

---

### Task 2.5: Implement Health Tools

**Files:**
- Create: `backend/mcp_server/tools/health.py`

**Step 1: Create health tools**

`backend/mcp_server/tools/health.py`:
```python
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
```

**Step 2: Commit**

```bash
git add backend/mcp_server/tools/health.py
git commit -m "feat(mcp): add health check tools"
```

---

### Task 2.6: Implement Logs & Tasks Tools

**Files:**
- Create: `backend/mcp_server/tools/logs.py`
- Create: `backend/mcp_server/tools/tasks.py`

**Step 1: Create logs tools**

`backend/mcp_server/tools/logs.py`:
```python
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
```

**Step 2: Create tasks tools**

`backend/mcp_server/tools/tasks.py`:
```python
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
```

**Step 3: Commit**

```bash
git add backend/mcp_server/tools/logs.py backend/mcp_server/tools/tasks.py
git commit -m "feat(mcp): add logs and task tools"
```

---

### Task 2.7: Implement Cache Tools

**Files:**
- Create: `backend/mcp_server/tools/cache.py`

**Step 1: Create cache tools**

`backend/mcp_server/tools/cache.py`:
```python
"""
Redis cache tools for MCP server.

Provides tools to inspect and manage the Redis cache.
"""
from typing import Any
import os
import redis.asyncio as redis

from mcp_server.utils import log_write_operation, require_dev_mode


def get_redis_client():
    """Get Redis client from environment."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url)


async def list_cache_keys(pattern: str = "*", limit: int = 100) -> dict[str, Any]:
    """
    List Redis keys matching a pattern.

    Args:
        pattern: Key pattern (default "*" for all)
        limit: Maximum keys to return (default 100)

    Returns:
        List of matching key names
    """
    try:
        client = get_redis_client()
        keys = []
        async for key in client.scan_iter(match=pattern, count=limit):
            keys.append(key.decode() if isinstance(key, bytes) else key)
            if len(keys) >= limit:
                break
        await client.aclose()

        return {
            "pattern": pattern,
            "count": len(keys),
            "keys": keys,
            "truncated": len(keys) >= limit,
        }
    except Exception as e:
        return {"error": str(e)}


async def get_cache_value(key: str) -> dict[str, Any]:
    """
    Get value for a specific cache key.

    Args:
        key: Redis key name

    Returns:
        Cached value and metadata
    """
    try:
        client = get_redis_client()

        # Get type first
        key_type = await client.type(key)
        key_type = key_type.decode() if isinstance(key_type, bytes) else key_type

        # Get TTL
        ttl = await client.ttl(key)

        # Get value based on type
        if key_type == "string":
            value = await client.get(key)
            value = value.decode() if isinstance(value, bytes) else value
        elif key_type == "hash":
            value = await client.hgetall(key)
            value = {k.decode(): v.decode() for k, v in value.items()}
        elif key_type == "list":
            value = await client.lrange(key, 0, 100)
            value = [v.decode() if isinstance(v, bytes) else v for v in value]
        elif key_type == "set":
            value = await client.smembers(key)
            value = [v.decode() if isinstance(v, bytes) else v for v in value]
        elif key_type == "none":
            await client.aclose()
            return {"error": f"Key '{key}' not found"}
        else:
            value = f"<{key_type} type not supported>"

        await client.aclose()

        return {
            "key": key,
            "type": key_type,
            "ttl": ttl if ttl > 0 else "no expiry" if ttl == -1 else "expired",
            "value": value,
        }
    except Exception as e:
        return {"error": str(e)}


async def get_cache_stats() -> dict[str, Any]:
    """
    Get Redis cache statistics.

    Returns:
        Memory usage, hit/miss stats, etc.
    """
    try:
        client = get_redis_client()

        info = await client.info()
        memory = await client.info("memory")
        stats = await client.info("stats")

        await client.aclose()

        return {
            "redis_version": info.get("redis_version"),
            "uptime_seconds": info.get("uptime_in_seconds"),
            "connected_clients": info.get("connected_clients"),
            "used_memory_human": memory.get("used_memory_human"),
            "used_memory_peak_human": memory.get("used_memory_peak_human"),
            "total_connections_received": stats.get("total_connections_received"),
            "total_commands_processed": stats.get("total_commands_processed"),
            "keyspace_hits": stats.get("keyspace_hits"),
            "keyspace_misses": stats.get("keyspace_misses"),
        }
    except Exception as e:
        return {"error": str(e)}


async def write_clear_cache(pattern: str = "*", confirm: bool = False) -> dict[str, Any]:
    """
    Clear Redis cache keys matching a pattern.

    WARNING: This deletes cached data.

    Args:
        pattern: Key pattern to delete (default "*" for all)
        confirm: Must be True to actually delete

    Returns:
        Number of keys deleted
    """
    require_dev_mode("write_clear_cache")

    if not confirm:
        # Show what would be deleted
        keys_result = await list_cache_keys(pattern, limit=20)
        return {
            "warning": "This will delete cache keys matching the pattern",
            "pattern": pattern,
            "sample_keys": keys_result.get("keys", []),
            "usage": "Set confirm=True to actually delete",
        }

    log_write_operation("write_clear_cache", {"pattern": pattern})

    try:
        client = get_redis_client()
        deleted = 0

        async for key in client.scan_iter(match=pattern):
            await client.delete(key)
            deleted += 1

        await client.aclose()

        return {
            "success": True,
            "pattern": pattern,
            "deleted_count": deleted,
        }
    except Exception as e:
        return {"error": str(e)}


async def write_invalidate_cache_key(key: str) -> dict[str, Any]:
    """
    Delete a specific cache key.

    Args:
        key: Redis key to delete

    Returns:
        Deletion result
    """
    require_dev_mode("write_invalidate_cache_key")
    log_write_operation("write_invalidate_cache_key", {"key": key})

    try:
        client = get_redis_client()
        deleted = await client.delete(key)
        await client.aclose()

        return {
            "success": True,
            "key": key,
            "deleted": deleted > 0,
        }
    except Exception as e:
        return {"error": str(e)}
```

**Step 2: Commit**

```bash
git add backend/mcp_server/tools/cache.py
git commit -m "feat(mcp): add cache tools"
```

---

### Task 2.8: Implement Inventory Tools

**Files:**
- Create: `backend/mcp_server/tools/inventory.py`

**Step 1: Create inventory tools**

`backend/mcp_server/tools/inventory.py`:
```python
"""
Inventory tools for MCP server.

Provides tools to query and manage user inventory.
Write operations are restricted to dev mode + test user only.
"""
from typing import Any

from mcp_server.utils import execute_query, api_client, log_write_operation, require_dev_mode, require_test_user
from mcp_server.config import config


async def list_inventory(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """
    List inventory items for a user.

    Args:
        user_id: User ID to list inventory for
        limit: Maximum items to return
        offset: Pagination offset

    Returns:
        Paginated inventory list
    """
    query = """
        SELECT
            i.id,
            i.card_id,
            c.name as card_name,
            c.set_code,
            i.quantity,
            i.condition,
            i.is_foil,
            i.acquisition_price,
            i.acquisition_date,
            c.scryfall_price_usd as current_price
        FROM inventory_items i
        JOIN cards c ON i.card_id = c.id
        WHERE i.user_id = :user_id
        ORDER BY c.name
        LIMIT :limit OFFSET :offset
    """

    rows = await execute_query(query, {"user_id": user_id, "limit": limit, "offset": offset})

    # Get total count
    count_query = "SELECT COUNT(*) as count FROM inventory_items WHERE user_id = :user_id"
    count_result = await execute_query(count_query, {"user_id": user_id})
    total = count_result[0]["count"] if count_result else 0

    return {
        "user_id": user_id,
        "items": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_inventory_item(item_id: int) -> dict[str, Any]:
    """
    Get a specific inventory item.

    Args:
        item_id: Inventory item ID

    Returns:
        Item details with current value
    """
    query = """
        SELECT
            i.*,
            c.name as card_name,
            c.set_code,
            c.set_name,
            c.rarity,
            c.scryfall_price_usd as current_price,
            c.scryfall_price_usd_foil as current_price_foil,
            c.image_uri_small
        FROM inventory_items i
        JOIN cards c ON i.card_id = c.id
        WHERE i.id = :item_id
    """

    rows = await execute_query(query, {"item_id": item_id})
    if not rows:
        return {"error": f"Inventory item {item_id} not found"}

    item = rows[0]

    # Calculate current value
    current_price = item.get("current_price_foil") if item.get("is_foil") else item.get("current_price")
    quantity = item.get("quantity", 1)
    acquisition_price = item.get("acquisition_price", 0)

    item["current_value"] = (current_price or 0) * quantity
    item["total_cost"] = (acquisition_price or 0) * quantity
    item["profit_loss"] = item["current_value"] - item["total_cost"]

    return item


async def get_portfolio_value(user_id: int) -> dict[str, Any]:
    """
    Get total portfolio value and performance for a user.

    Args:
        user_id: User ID

    Returns:
        Portfolio value, cost, and profit/loss
    """
    query = """
        SELECT
            COUNT(*) as total_items,
            SUM(i.quantity) as total_cards,
            SUM(
                i.quantity * COALESCE(
                    CASE WHEN i.is_foil THEN c.scryfall_price_usd_foil ELSE c.scryfall_price_usd END,
                    0
                )
            ) as current_value,
            SUM(i.quantity * COALESCE(i.acquisition_price, 0)) as total_cost
        FROM inventory_items i
        JOIN cards c ON i.card_id = c.id
        WHERE i.user_id = :user_id
    """

    rows = await execute_query(query, {"user_id": user_id})
    if not rows or rows[0]["total_items"] == 0:
        return {
            "user_id": user_id,
            "total_items": 0,
            "total_cards": 0,
            "current_value": 0,
            "total_cost": 0,
            "profit_loss": 0,
            "profit_loss_pct": 0,
        }

    result = rows[0]
    current_value = float(result["current_value"] or 0)
    total_cost = float(result["total_cost"] or 0)
    profit_loss = current_value - total_cost
    profit_loss_pct = (profit_loss / total_cost * 100) if total_cost > 0 else 0

    return {
        "user_id": user_id,
        "total_items": result["total_items"],
        "total_cards": result["total_cards"],
        "current_value": round(current_value, 2),
        "total_cost": round(total_cost, 2),
        "profit_loss": round(profit_loss, 2),
        "profit_loss_pct": round(profit_loss_pct, 2),
    }


async def write_add_inventory_item(
    user_id: int,
    card_id: int,
    quantity: int = 1,
    condition: str = "NEAR_MINT",
    is_foil: bool = False,
    acquisition_price: float | None = None,
) -> dict[str, Any]:
    """
    Add a card to user's inventory.

    RESTRICTED: Only works in dev mode for test user.

    Args:
        user_id: User ID (must match test user)
        card_id: Card to add
        quantity: Number of copies
        condition: Card condition
        is_foil: Whether card is foil
        acquisition_price: Price paid per copy

    Returns:
        Created inventory item
    """
    require_dev_mode("write_add_inventory_item")
    require_test_user("write_add_inventory_item", user_id)

    log_write_operation("write_add_inventory_item", {
        "user_id": user_id,
        "card_id": card_id,
        "quantity": quantity,
        "condition": condition,
        "is_foil": is_foil,
    })

    # Use API to add item
    try:
        result = await api_client.post("/inventory", json={
            "card_id": card_id,
            "quantity": quantity,
            "condition": condition,
            "is_foil": is_foil,
            "acquisition_price": acquisition_price,
        })
        return result
    except Exception as e:
        return {"error": str(e)}


async def write_remove_inventory_item(user_id: int, item_id: int) -> dict[str, Any]:
    """
    Remove an item from user's inventory.

    RESTRICTED: Only works in dev mode for test user.

    Args:
        user_id: User ID (must match test user)
        item_id: Inventory item ID to remove

    Returns:
        Deletion result
    """
    require_dev_mode("write_remove_inventory_item")
    require_test_user("write_remove_inventory_item", user_id)

    log_write_operation("write_remove_inventory_item", {
        "user_id": user_id,
        "item_id": item_id,
    })

    # Verify item belongs to user first
    item = await get_inventory_item(item_id)
    if "error" in item:
        return item
    if item.get("user_id") != user_id:
        return {"error": "Item does not belong to specified user"}

    # This would need a DELETE endpoint - for now return info
    return {
        "note": "DELETE endpoint needed for removal",
        "item_id": item_id,
        "would_delete": item,
    }


async def write_update_inventory_item(
    user_id: int,
    item_id: int,
    quantity: int | None = None,
    condition: str | None = None,
) -> dict[str, Any]:
    """
    Update an inventory item.

    RESTRICTED: Only works in dev mode for test user.

    Args:
        user_id: User ID (must match test user)
        item_id: Inventory item ID
        quantity: New quantity (optional)
        condition: New condition (optional)

    Returns:
        Updated item
    """
    require_dev_mode("write_update_inventory_item")
    require_test_user("write_update_inventory_item", user_id)

    log_write_operation("write_update_inventory_item", {
        "user_id": user_id,
        "item_id": item_id,
        "quantity": quantity,
        "condition": condition,
    })

    # This would need a PATCH endpoint
    return {
        "note": "PATCH endpoint needed for updates",
        "item_id": item_id,
        "updates": {"quantity": quantity, "condition": condition},
    }
```

**Step 2: Commit**

```bash
git add backend/mcp_server/tools/inventory.py
git commit -m "feat(mcp): add inventory tools with write safety"
```

---

### Task 2.9: Implement Recommendations Tools

**Files:**
- Create: `backend/mcp_server/tools/recommendations.py`

**Step 1: Create recommendations tools**

`backend/mcp_server/tools/recommendations.py`:
```python
"""
Recommendations and signals tools for MCP server.

Provides tools to query trading recommendations and analytics signals.
"""
from typing import Any
from mcp_server.utils import execute_query, api_client


async def get_recommendations(
    action: str | None = None,
    min_confidence: float | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Get trading recommendations.

    Args:
        action: Filter by action (BUY, SELL, HOLD)
        min_confidence: Minimum confidence score (0-1)
        limit: Maximum recommendations to return

    Returns:
        List of recommendations with rationale
    """
    try:
        params = {"limit": limit}
        if action:
            params["action"] = action.upper()
        if min_confidence:
            params["min_confidence"] = min_confidence

        return await api_client.get("/recommendations", params=params)
    except Exception:
        # Fall back to direct query
        conditions = ["r.is_active = true"]
        query_params: dict[str, Any] = {"limit": limit}

        if action:
            conditions.append("r.action = :action")
            query_params["action"] = action.upper()

        if min_confidence:
            conditions.append("r.confidence >= :min_confidence")
            query_params["min_confidence"] = min_confidence

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                r.id,
                r.card_id,
                c.name as card_name,
                c.set_code,
                r.action,
                r.confidence,
                r.target_price,
                r.current_price,
                r.potential_profit_pct,
                r.rationale,
                r.created_at
            FROM recommendations r
            JOIN cards c ON r.card_id = c.id
            WHERE {where_clause}
            ORDER BY r.confidence DESC, r.potential_profit_pct DESC
            LIMIT :limit
        """

        rows = await execute_query(query, query_params)
        return {"recommendations": rows}


async def get_signals(
    card_id: int | None = None,
    signal_type: str | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """
    Get analytics signals.

    Args:
        card_id: Filter by specific card
        signal_type: Filter by type (momentum_up, volatility_high, etc.)
        days: Number of days of signals to retrieve

    Returns:
        List of signals with confidence scores
    """
    conditions = ["s.date >= CURRENT_DATE - :days::interval"]
    params: dict[str, Any] = {"days": f"{days} days"}

    if card_id:
        conditions.append("s.card_id = :card_id")
        params["card_id"] = card_id

    if signal_type:
        conditions.append("s.signal_type = :signal_type")
        params["signal_type"] = signal_type

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            s.id,
            s.card_id,
            c.name as card_name,
            s.signal_type,
            s.value,
            s.confidence,
            s.llm_insight,
            s.date
        FROM signals s
        JOIN cards c ON s.card_id = c.id
        WHERE {where_clause}
        ORDER BY s.date DESC, s.confidence DESC
        LIMIT 50
    """

    rows = await execute_query(query, params)

    # Get signal type summary if no specific card
    if not card_id:
        summary_query = f"""
            SELECT
                signal_type,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence
            FROM signals s
            WHERE {where_clause}
            GROUP BY signal_type
            ORDER BY count DESC
        """
        summary = await execute_query(summary_query, params)
    else:
        summary = None

    return {
        "signals": rows,
        "summary": summary,
        "filters": {
            "card_id": card_id,
            "signal_type": signal_type,
            "days": days,
        }
    }
```

**Step 2: Commit**

```bash
git add backend/mcp_server/tools/recommendations.py
git commit -m "feat(mcp): add recommendations and signals tools"
```

---

### Task 2.10: Implement Documentation Tools

**Files:**
- Create: `backend/mcp_server/tools/docs.py`

**Step 1: Create documentation tools**

`backend/mcp_server/tools/docs.py`:
```python
"""
Documentation access tools for MCP server.

Provides tools to read project documentation and design docs.
"""
from typing import Any
from pathlib import Path

from mcp_server.config import config


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(config.project_root)


async def get_design_docs() -> dict[str, Any]:
    """
    List all design documents in docs/plans/.

    Returns:
        List of design docs with names and first lines
    """
    docs_dir = get_project_root() / "docs" / "plans"

    if not docs_dir.exists():
        return {"error": "docs/plans/ directory not found"}

    docs = []
    for file_path in sorted(docs_dir.glob("*.md")):
        # Read first few lines for summary
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()[:5]
                title = lines[0].strip().lstrip("#").strip() if lines else file_path.stem

            docs.append({
                "filename": file_path.name,
                "title": title,
                "path": str(file_path.relative_to(get_project_root())),
            })
        except Exception as e:
            docs.append({
                "filename": file_path.name,
                "error": str(e),
            })

    return {
        "count": len(docs),
        "documents": docs,
    }


async def read_design_doc(filename: str) -> dict[str, Any]:
    """
    Read a specific design document.

    Args:
        filename: Name of the document (with or without .md extension)

    Returns:
        Document content
    """
    if not filename.endswith(".md"):
        filename += ".md"

    file_path = get_project_root() / "docs" / "plans" / filename

    if not file_path.exists():
        # Try to find similar files
        docs_dir = get_project_root() / "docs" / "plans"
        similar = [f.name for f in docs_dir.glob("*.md") if filename.replace(".md", "") in f.name]
        return {
            "error": f"Document '{filename}' not found",
            "similar": similar,
        }

    try:
        content = file_path.read_text()
        return {
            "filename": filename,
            "path": str(file_path.relative_to(get_project_root())),
            "content": content,
            "lines": len(content.split("\n")),
        }
    except Exception as e:
        return {"error": str(e)}


async def get_claude_md() -> dict[str, Any]:
    """
    Read the CLAUDE.md project instructions file.

    Returns:
        CLAUDE.md content
    """
    file_path = get_project_root() / "CLAUDE.md"

    if not file_path.exists():
        return {"error": "CLAUDE.md not found"}

    try:
        content = file_path.read_text()
        return {
            "filename": "CLAUDE.md",
            "content": content,
            "lines": len(content.split("\n")),
        }
    except Exception as e:
        return {"error": str(e)}
```

**Step 2: Commit**

```bash
git add backend/mcp_server/tools/docs.py
git commit -m "feat(mcp): add documentation access tools"
```

---

## Phase 3: Integration (Sequential)

### Task 3.1: Update Tools __init__.py

**Files:**
- Modify: `backend/mcp_server/tools/__init__.py`

**Step 1: Export all tools**

`backend/mcp_server/tools/__init__.py`:
```python
"""MCP Server tools - all available tool functions."""

# Card tools
from mcp_server.tools.cards import (
    get_card_by_id,
    get_card_by_name,
    get_card_by_scryfall_id,
    search_cards,
    get_random_cards,
)

# Price tools
from mcp_server.tools.prices import (
    get_current_price,
    get_price_history,
    get_top_movers,
    get_market_overview,
    get_market_index,
)

# Schema tools
from mcp_server.tools.schema import (
    list_tables,
    describe_table,
    get_model_schema,
    get_api_endpoints,
    describe_endpoint,
)

# Database tools
from mcp_server.tools.database import (
    run_query,
    count_records,
    get_sample_records,
    write_run_migration,
)

# Health tools
from mcp_server.tools.health import (
    check_db_connection,
    check_redis_connection,
    check_containers,
    get_data_freshness,
    get_environment,
    get_migration_status,
)

# Log tools
from mcp_server.tools.logs import (
    get_container_logs,
    get_recent_errors,
)

# Task tools
from mcp_server.tools.tasks import (
    list_celery_tasks,
    get_task_history,
    trigger_price_collection,
    trigger_analytics,
    trigger_recommendations,
    trigger_scryfall_import,
)

# Cache tools
from mcp_server.tools.cache import (
    list_cache_keys,
    get_cache_value,
    get_cache_stats,
    write_clear_cache,
    write_invalidate_cache_key,
)

# Inventory tools
from mcp_server.tools.inventory import (
    list_inventory,
    get_inventory_item,
    get_portfolio_value,
    write_add_inventory_item,
    write_remove_inventory_item,
    write_update_inventory_item,
)

# Recommendations tools
from mcp_server.tools.recommendations import (
    get_recommendations,
    get_signals,
)

# Documentation tools
from mcp_server.tools.docs import (
    get_design_docs,
    read_design_doc,
    get_claude_md,
)

__all__ = [
    # Cards
    "get_card_by_id",
    "get_card_by_name",
    "get_card_by_scryfall_id",
    "search_cards",
    "get_random_cards",
    # Prices
    "get_current_price",
    "get_price_history",
    "get_top_movers",
    "get_market_overview",
    "get_market_index",
    # Schema
    "list_tables",
    "describe_table",
    "get_model_schema",
    "get_api_endpoints",
    "describe_endpoint",
    # Database
    "run_query",
    "count_records",
    "get_sample_records",
    "write_run_migration",
    # Health
    "check_db_connection",
    "check_redis_connection",
    "check_containers",
    "get_data_freshness",
    "get_environment",
    "get_migration_status",
    # Logs
    "get_container_logs",
    "get_recent_errors",
    # Tasks
    "list_celery_tasks",
    "get_task_history",
    "trigger_price_collection",
    "trigger_analytics",
    "trigger_recommendations",
    "trigger_scryfall_import",
    # Cache
    "list_cache_keys",
    "get_cache_value",
    "get_cache_stats",
    "write_clear_cache",
    "write_invalidate_cache_key",
    # Inventory
    "list_inventory",
    "get_inventory_item",
    "get_portfolio_value",
    "write_add_inventory_item",
    "write_remove_inventory_item",
    "write_update_inventory_item",
    # Recommendations
    "get_recommendations",
    "get_signals",
    # Docs
    "get_design_docs",
    "read_design_doc",
    "get_claude_md",
]
```

**Step 2: Commit**

```bash
git add backend/mcp_server/tools/__init__.py
git commit -m "feat(mcp): export all tools from package"
```

---

### Task 3.2: Implement MCP Resources

**Files:**
- Create: `backend/mcp_server/resources/static.py`
- Modify: `backend/mcp_server/resources/__init__.py`

**Step 1: Create resources module**

`backend/mcp_server/resources/static.py`:
```python
"""
Static MCP resources for MTG Market Intelligence.

Resources provide context that Claude can read automatically.
"""
from typing import Any
import json

from mcp_server.tools.schema import list_tables, get_api_endpoints
from mcp_server.tools.health import get_environment, get_data_freshness
from mcp_server.tools.docs import get_claude_md, get_design_docs
from mcp_server.utils import execute_query


async def get_schema_tables_resource() -> str:
    """Get database tables as a resource."""
    tables = await list_tables()
    return json.dumps(tables, indent=2, default=str)


async def get_schema_models_resource() -> str:
    """Get SQLAlchemy model information as a resource."""
    # Get table columns for key models
    key_tables = ["cards", "price_snapshots", "inventory_items", "recommendations", "signals", "users"]
    models = {}

    for table in key_tables:
        try:
            from mcp_server.tools.schema import describe_table
            info = await describe_table(table)
            models[table] = info
        except Exception as e:
            models[table] = {"error": str(e)}

    return json.dumps(models, indent=2, default=str)


async def get_schema_api_resource() -> str:
    """Get OpenAPI spec as a resource."""
    spec = await get_api_endpoints()
    return json.dumps(spec, indent=2, default=str)


async def get_docs_claude_md_resource() -> str:
    """Get CLAUDE.md content as a resource."""
    result = await get_claude_md()
    return result.get("content", json.dumps(result))


async def get_docs_plans_resource() -> str:
    """Get list of design documents as a resource."""
    result = await get_design_docs()
    return json.dumps(result, indent=2, default=str)


async def get_config_marketplaces_resource() -> str:
    """Get marketplace configuration as a resource."""
    query = "SELECT id, name, slug, is_enabled, default_currency FROM marketplaces ORDER BY name"
    try:
        rows = await execute_query(query)
        return json.dumps(rows, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def get_config_environment_resource() -> str:
    """Get environment configuration as a resource."""
    result = await get_environment()
    return json.dumps(result, indent=2, default=str)


async def get_stats_overview_resource() -> str:
    """Get quick stats overview as a resource."""
    query = """
        SELECT
            (SELECT COUNT(*) FROM cards) as total_cards,
            (SELECT COUNT(*) FROM cards WHERE scryfall_price_usd IS NOT NULL) as priced_cards,
            (SELECT COUNT(*) FROM price_snapshots) as total_snapshots,
            (SELECT COUNT(*) FROM users) as total_users,
            (SELECT COUNT(*) FROM inventory_items) as total_inventory_items,
            (SELECT COUNT(*) FROM recommendations WHERE is_active = true) as active_recommendations
    """
    try:
        rows = await execute_query(query)
        stats = rows[0] if rows else {}

        # Add freshness info
        freshness = await get_data_freshness()
        stats["data_freshness"] = freshness

        return json.dumps(stats, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# Resource registry
RESOURCES = {
    "mtg://schema/tables": {
        "name": "Database Tables",
        "description": "All database tables with row counts",
        "mimeType": "application/json",
        "handler": get_schema_tables_resource,
    },
    "mtg://schema/models": {
        "name": "Database Models",
        "description": "Key SQLAlchemy model definitions",
        "mimeType": "application/json",
        "handler": get_schema_models_resource,
    },
    "mtg://schema/api": {
        "name": "API Schema",
        "description": "OpenAPI specification",
        "mimeType": "application/json",
        "handler": get_schema_api_resource,
    },
    "mtg://docs/claude-md": {
        "name": "CLAUDE.md",
        "description": "Project instructions for Claude",
        "mimeType": "text/markdown",
        "handler": get_docs_claude_md_resource,
    },
    "mtg://docs/plans": {
        "name": "Design Documents",
        "description": "List of design docs in docs/plans/",
        "mimeType": "application/json",
        "handler": get_docs_plans_resource,
    },
    "mtg://config/marketplaces": {
        "name": "Marketplaces",
        "description": "Configured marketplace sources",
        "mimeType": "application/json",
        "handler": get_config_marketplaces_resource,
    },
    "mtg://config/environment": {
        "name": "Environment",
        "description": "Current environment configuration",
        "mimeType": "application/json",
        "handler": get_config_environment_resource,
    },
    "mtg://stats/overview": {
        "name": "Stats Overview",
        "description": "Quick statistics snapshot",
        "mimeType": "application/json",
        "handler": get_stats_overview_resource,
    },
}
```

**Step 2: Update resources __init__.py**

`backend/mcp_server/resources/__init__.py`:
```python
"""MCP Server resources."""
from mcp_server.resources.static import RESOURCES

__all__ = ["RESOURCES"]
```

**Step 3: Commit**

```bash
git add backend/mcp_server/resources/
git commit -m "feat(mcp): add MCP resources"
```

---

### Task 3.3: Implement Main Server

**Files:**
- Create: `backend/mcp_server/server.py`

**Step 1: Create main server module**

`backend/mcp_server/server.py`:
```python
"""
MCP Server for MTG Market Intelligence.

Main entry point for the MCP server.
Run with: python -m mcp_server.server
"""
import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
    ResourceContents,
    TextResourceContents,
)

from mcp_server.config import config
from mcp_server.resources import RESOURCES
from mcp_server import tools as tool_module


# Create the MCP server
server = Server("mtg-intel")


# Tool definitions with their metadata
TOOL_DEFINITIONS = [
    # Card tools
    Tool(name="get_card_by_id", description="Fetch a card by its database ID", inputSchema={
        "type": "object",
        "properties": {"card_id": {"type": "integer", "description": "The database ID of the card"}},
        "required": ["card_id"],
    }),
    Tool(name="get_card_by_name", description="Search for cards by name (fuzzy match)", inputSchema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Card name to search for"},
            "limit": {"type": "integer", "description": "Maximum results (default 10)", "default": 10},
        },
        "required": ["name"],
    }),
    Tool(name="get_card_by_scryfall_id", description="Fetch a card by its Scryfall UUID", inputSchema={
        "type": "object",
        "properties": {"scryfall_id": {"type": "string", "description": "Scryfall UUID"}},
        "required": ["scryfall_id"],
    }),
    Tool(name="search_cards", description="Search cards with filters (colors, type, CMC, format, rarity)", inputSchema={
        "type": "object",
        "properties": {
            "colors": {"type": "string", "description": "Color filter (e.g., 'W', 'UB', 'WUBRG')"},
            "card_type": {"type": "string", "description": "Type filter (e.g., 'Creature', 'Instant')"},
            "cmc_min": {"type": "number", "description": "Minimum CMC"},
            "cmc_max": {"type": "number", "description": "Maximum CMC"},
            "rarity": {"type": "string", "description": "Rarity (common, uncommon, rare, mythic)"},
            "set_code": {"type": "string", "description": "Set code (e.g., 'MKM', 'ONE')"},
            "format_legal": {"type": "string", "description": "Format legality (e.g., 'modern', 'commander')"},
            "limit": {"type": "integer", "default": 20},
            "offset": {"type": "integer", "default": 0},
        },
    }),
    Tool(name="get_random_cards", description="Get random cards (useful for testing)", inputSchema={
        "type": "object",
        "properties": {"count": {"type": "integer", "description": "Number of cards (default 5, max 20)", "default": 5}},
    }),

    # Price tools
    Tool(name="get_current_price", description="Get current price for a card across marketplaces", inputSchema={
        "type": "object",
        "properties": {"card_id": {"type": "integer", "description": "Card database ID"}},
        "required": ["card_id"],
    }),
    Tool(name="get_price_history", description="Get historical prices for a card", inputSchema={
        "type": "object",
        "properties": {
            "card_id": {"type": "integer", "description": "Card database ID"},
            "days": {"type": "integer", "description": "Days of history (default 30)", "default": 30},
            "condition": {"type": "string", "description": "Filter by condition"},
            "is_foil": {"type": "boolean", "description": "Filter by foil status"},
        },
        "required": ["card_id"],
    }),
    Tool(name="get_top_movers", description="Get top gaining and losing cards", inputSchema={
        "type": "object",
        "properties": {
            "window": {"type": "string", "description": "Time window ('24h' or '7d')", "default": "24h"},
            "limit": {"type": "integer", "description": "Cards per category", "default": 10},
        },
    }),
    Tool(name="get_market_overview", description="Get market-wide statistics", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_market_index", description="Get market index trend", inputSchema={
        "type": "object",
        "properties": {"range": {"type": "string", "description": "Time range (7d, 30d, 90d, 1y)", "default": "30d"}},
    }),

    # Schema tools
    Tool(name="list_tables", description="List all database tables with row counts", inputSchema={"type": "object", "properties": {}}),
    Tool(name="describe_table", description="Get column information for a table", inputSchema={
        "type": "object",
        "properties": {"table_name": {"type": "string", "description": "Name of the table"}},
        "required": ["table_name"],
    }),
    Tool(name="get_model_schema", description="Get Pydantic schema for a model", inputSchema={
        "type": "object",
        "properties": {"model_name": {"type": "string", "description": "Model name (e.g., 'Card', 'InventoryItem')"}},
        "required": ["model_name"],
    }),
    Tool(name="get_api_endpoints", description="List all API endpoints from OpenAPI spec", inputSchema={"type": "object", "properties": {}}),
    Tool(name="describe_endpoint", description="Get details for a specific API endpoint", inputSchema={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "API path (e.g., '/cards/{id}')"}},
        "required": ["path"],
    }),

    # Database tools
    Tool(name="run_query", description="Execute a read-only SQL query (SELECT only)", inputSchema={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "SQL SELECT query"}},
        "required": ["query"],
    }),
    Tool(name="count_records", description="Count records in a table", inputSchema={
        "type": "object",
        "properties": {
            "table_name": {"type": "string", "description": "Table name"},
            "where": {"type": "string", "description": "Optional WHERE clause (without 'WHERE')"},
        },
        "required": ["table_name"],
    }),
    Tool(name="get_sample_records", description="Get sample records from a table", inputSchema={
        "type": "object",
        "properties": {
            "table_name": {"type": "string", "description": "Table name"},
            "limit": {"type": "integer", "description": "Number of records (default 5, max 20)", "default": 5},
        },
        "required": ["table_name"],
    }),
    Tool(name="write_run_migration", description="[WRITE] Run pending Alembic migrations (dev only)", inputSchema={
        "type": "object",
        "properties": {"confirm": {"type": "boolean", "description": "Must be true to run", "default": False}},
    }),

    # Health tools
    Tool(name="check_db_connection", description="Test PostgreSQL connectivity", inputSchema={"type": "object", "properties": {}}),
    Tool(name="check_redis_connection", description="Test Redis connectivity", inputSchema={"type": "object", "properties": {}}),
    Tool(name="check_containers", description="Check Docker container status", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_data_freshness", description="Get data freshness per marketplace", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_environment", description="Get current environment configuration", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_migration_status", description="Get Alembic migration status", inputSchema={"type": "object", "properties": {}}),

    # Log tools
    Tool(name="get_container_logs", description="Get logs from a Docker container", inputSchema={
        "type": "object",
        "properties": {
            "container": {"type": "string", "description": "Container name", "default": "backend"},
            "lines": {"type": "integer", "description": "Lines to tail", "default": 100},
            "since": {"type": "string", "description": "Time filter (e.g., '1h', '30m')"},
        },
    }),
    Tool(name="get_recent_errors", description="Find recent errors in container logs", inputSchema={
        "type": "object",
        "properties": {
            "container": {"type": "string", "description": "Container name", "default": "backend"},
            "lines": {"type": "integer", "description": "Lines to search", "default": 500},
        },
    }),

    # Task tools
    Tool(name="list_celery_tasks", description="List registered Celery tasks", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_task_history", description="Get recent task executions", inputSchema={
        "type": "object",
        "properties": {"limit": {"type": "integer", "default": 10}},
    }),
    Tool(name="trigger_price_collection", description="[WRITE] Trigger price collection task (dev only)", inputSchema={
        "type": "object",
        "properties": {"marketplace": {"type": "string", "description": "Specific marketplace (optional)"}},
    }),
    Tool(name="trigger_analytics", description="[WRITE] Trigger analytics calculation (dev only)", inputSchema={"type": "object", "properties": {}}),
    Tool(name="trigger_recommendations", description="[WRITE] Trigger recommendations generation (dev only)", inputSchema={"type": "object", "properties": {}}),
    Tool(name="trigger_scryfall_import", description="[WRITE] Trigger Scryfall import (dev only)", inputSchema={
        "type": "object",
        "properties": {"full": {"type": "boolean", "description": "Full import (~90k cards)", "default": False}},
    }),

    # Cache tools
    Tool(name="list_cache_keys", description="List Redis cache keys", inputSchema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Key pattern", "default": "*"},
            "limit": {"type": "integer", "default": 100},
        },
    }),
    Tool(name="get_cache_value", description="Get value for a cache key", inputSchema={
        "type": "object",
        "properties": {"key": {"type": "string", "description": "Redis key"}},
        "required": ["key"],
    }),
    Tool(name="get_cache_stats", description="Get Redis cache statistics", inputSchema={"type": "object", "properties": {}}),
    Tool(name="write_clear_cache", description="[WRITE] Clear cache keys (dev only)", inputSchema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Key pattern", "default": "*"},
            "confirm": {"type": "boolean", "description": "Must be true to delete", "default": False},
        },
    }),
    Tool(name="write_invalidate_cache_key", description="[WRITE] Delete a cache key (dev only)", inputSchema={
        "type": "object",
        "properties": {"key": {"type": "string", "description": "Key to delete"}},
        "required": ["key"],
    }),

    # Inventory tools
    Tool(name="list_inventory", description="List inventory items for a user", inputSchema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "User ID"},
            "limit": {"type": "integer", "default": 20},
            "offset": {"type": "integer", "default": 0},
        },
        "required": ["user_id"],
    }),
    Tool(name="get_inventory_item", description="Get a specific inventory item", inputSchema={
        "type": "object",
        "properties": {"item_id": {"type": "integer", "description": "Inventory item ID"}},
        "required": ["item_id"],
    }),
    Tool(name="get_portfolio_value", description="Get portfolio value for a user", inputSchema={
        "type": "object",
        "properties": {"user_id": {"type": "integer", "description": "User ID"}},
        "required": ["user_id"],
    }),
    Tool(name="write_add_inventory_item", description="[WRITE] Add card to inventory (dev + test user only)", inputSchema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "User ID (must match test user)"},
            "card_id": {"type": "integer", "description": "Card ID"},
            "quantity": {"type": "integer", "default": 1},
            "condition": {"type": "string", "default": "NEAR_MINT"},
            "is_foil": {"type": "boolean", "default": False},
            "acquisition_price": {"type": "number"},
        },
        "required": ["user_id", "card_id"],
    }),
    Tool(name="write_remove_inventory_item", description="[WRITE] Remove item from inventory (dev + test user only)", inputSchema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "User ID (must match test user)"},
            "item_id": {"type": "integer", "description": "Item ID to remove"},
        },
        "required": ["user_id", "item_id"],
    }),
    Tool(name="write_update_inventory_item", description="[WRITE] Update inventory item (dev + test user only)", inputSchema={
        "type": "object",
        "properties": {
            "user_id": {"type": "integer", "description": "User ID (must match test user)"},
            "item_id": {"type": "integer", "description": "Item ID"},
            "quantity": {"type": "integer"},
            "condition": {"type": "string"},
        },
        "required": ["user_id", "item_id"],
    }),

    # Recommendations tools
    Tool(name="get_recommendations", description="Get trading recommendations", inputSchema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "Filter by action (BUY, SELL, HOLD)"},
            "min_confidence": {"type": "number", "description": "Minimum confidence (0-1)"},
            "limit": {"type": "integer", "default": 20},
        },
    }),
    Tool(name="get_signals", description="Get analytics signals", inputSchema={
        "type": "object",
        "properties": {
            "card_id": {"type": "integer", "description": "Filter by card"},
            "signal_type": {"type": "string", "description": "Filter by type"},
            "days": {"type": "integer", "description": "Days of signals", "default": 7},
        },
    }),

    # Documentation tools
    Tool(name="get_design_docs", description="List design documents in docs/plans/", inputSchema={"type": "object", "properties": {}}),
    Tool(name="read_design_doc", description="Read a specific design document", inputSchema={
        "type": "object",
        "properties": {"filename": {"type": "string", "description": "Document filename"}},
        "required": ["filename"],
    }),
    Tool(name="get_claude_md", description="Read CLAUDE.md project instructions", inputSchema={"type": "object", "properties": {}}),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of available tools."""
    return TOOL_DEFINITIONS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute a tool and return the result."""
    # Get the tool function from the tools module
    tool_func = getattr(tool_module, name, None)
    if tool_func is None:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    try:
        result = await tool_func(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


@server.list_resources()
async def list_resources() -> list[Resource]:
    """Return the list of available resources."""
    return [
        Resource(
            uri=uri,
            name=info["name"],
            description=info["description"],
            mimeType=info["mimeType"],
        )
        for uri, info in RESOURCES.items()
    ]


@server.read_resource()
async def read_resource(uri: str) -> ResourceContents:
    """Read a resource by URI."""
    if uri not in RESOURCES:
        raise ValueError(f"Unknown resource: {uri}")

    handler = RESOURCES[uri]["handler"]
    content = await handler()

    return TextResourceContents(
        uri=uri,
        mimeType=RESOURCES[uri]["mimeType"],
        text=content,
    )


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Commit**

```bash
git add backend/mcp_server/server.py
git commit -m "feat(mcp): implement main MCP server"
```

---

### Task 3.4: Create __main__.py for Module Execution

**Files:**
- Create: `backend/mcp_server/__main__.py`

**Step 1: Create __main__.py**

`backend/mcp_server/__main__.py`:
```python
"""Allow running as: python -m mcp_server"""
from mcp_server.server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Commit**

```bash
git add backend/mcp_server/__main__.py
git commit -m "feat(mcp): add __main__.py for module execution"
```

---

## Phase 4: Finalization

### Task 4.1: Verify Syntax and Imports

**Step 1: Run Python syntax check on all files**

```bash
cd /home/lyro/mtg-market-intel/.worktrees/mcp-server
python3 -m py_compile backend/mcp_server/config.py
python3 -m py_compile backend/mcp_server/utils/db.py
python3 -m py_compile backend/mcp_server/utils/api.py
python3 -m py_compile backend/mcp_server/utils/logging.py
python3 -m py_compile backend/mcp_server/tools/cards.py
python3 -m py_compile backend/mcp_server/tools/prices.py
python3 -m py_compile backend/mcp_server/tools/schema.py
python3 -m py_compile backend/mcp_server/tools/database.py
python3 -m py_compile backend/mcp_server/tools/health.py
python3 -m py_compile backend/mcp_server/tools/logs.py
python3 -m py_compile backend/mcp_server/tools/tasks.py
python3 -m py_compile backend/mcp_server/tools/cache.py
python3 -m py_compile backend/mcp_server/tools/inventory.py
python3 -m py_compile backend/mcp_server/tools/recommendations.py
python3 -m py_compile backend/mcp_server/tools/docs.py
python3 -m py_compile backend/mcp_server/resources/static.py
python3 -m py_compile backend/mcp_server/server.py
```

**Step 2: If errors, fix and re-check**

---

### Task 4.2: Test Basic Import

**Step 1: Test that the module can be imported**

```bash
cd /home/lyro/mtg-market-intel/.worktrees/mcp-server/backend
PYTHONPATH=. python3 -c "from mcp_server import tools; print('Tools:', len(tools.__all__))"
```

Expected output: `Tools: 39` (or similar count)

---

### Task 4.3: Final Commit

**Step 1: Commit any remaining changes**

```bash
git add -A
git commit -m "feat(mcp): complete MCP server implementation

- 49 tools across 10 categories (cards, prices, schema, database,
  health, logs, tasks, cache, inventory, recommendations, docs)
- 8 MCP resources for context
- Write safety: dev-only + test user for inventory writes
- All write operations logged to mcp_server/logs/writes.log

Ready for Claude Code integration via settings.json"
```

---

## Claude Code Integration

After implementation, add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "mtg-intel": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/home/lyro/mtg-market-intel/backend",
      "env": {
        "MTG_MCP_ENV": "dev",
        "MTG_MCP_DATABASE_URL": "postgresql+asyncpg://dualcaster_user:YOUR_PASSWORD@localhost:5432/dualcaster_deals",
        "MTG_MCP_TEST_USER_ID": "1",
        "REDIS_URL": "redis://localhost:6379/0"
      }
    }
  }
}
```

---

## Parallel Execution Guide

Tasks that can run in parallel (after Phase 1 completes):

**Batch 1:** Tasks 2.1, 2.2, 2.3, 2.4, 2.5 (Card, Price, Schema, Database, Health tools)

**Batch 2:** Tasks 2.6, 2.7, 2.8, 2.9, 2.10 (Logs/Tasks, Cache, Inventory, Recommendations, Docs tools)

**Sequential:** Phase 3 tasks must run in order after Phase 2 completes.
