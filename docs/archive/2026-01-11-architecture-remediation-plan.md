# Architecture Remediation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 16 critical architecture flaws spanning data integrity, security, performance, and reliability.

**Architecture:** Phased approach prioritizing data integrity and security first, then performance and reliability. Each phase is independently deployable. Circuit breaker pattern for external APIs, cursor-based pagination for scale, proper transaction boundaries for consistency.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL/TimescaleDB, Redis, Celery, httpx, pytest

---

## Phase Overview

| Phase | Focus | Tasks | Risk if Skipped |
|-------|-------|-------|-----------------|
| 1 | Data Integrity | 1-3 | Data corruption, orphaned records |
| 2 | Security | 4-7 | IDOR attacks, malicious uploads, session hijacking |
| 3 | Performance | 8-12 | Database death at scale, N+1 query storms |
| 4 | Reliability | 13-16 | Cascading failures, silent data loss |
| 5 | Testing | 17-19 | Unknown failure modes, CI blind spots |

---

## Phase 1: Data Integrity (Critical)

### Task 1: Complete Listing to PriceSnapshot Migration

**Problem:** Deprecated `Listing` model still has active relationship from `Card`, creating data model ambiguity.

**Files:**
- Modify: `backend/app/models/card.py:95-96`
- Modify: `backend/app/models/__init__.py:16,66-100`
- Modify: `backend/app/models/marketplace.py:45-52`
- Delete: `backend/app/models/listing.py`
- Create: `backend/alembic/versions/xxxx_drop_listing_table.py`
- Test: `backend/tests/models/test_listing_removal.py`

**Step 1: Audit Listing usage**

Run:
```bash
grep -r "Listing" backend/app --include="*.py" | grep -v "__pycache__" | grep -v "CardListing"
```

Verify only these files reference it:
- `models/__init__.py` (deprecation wrapper)
- `models/card.py` (relationship)
- `models/marketplace.py` (relationship)
- `models/listing.py` (definition)

**Step 2: Write test verifying Card works without Listing relationship**

```python
# backend/tests/models/test_listing_removal.py
import pytest
from sqlalchemy import select
from app.models import Card, PriceSnapshot

@pytest.mark.asyncio
async def test_card_price_snapshots_relationship(db_session, test_card):
    """Card should use price_snapshots, not listings."""
    # Verify relationship exists
    assert hasattr(Card, 'price_snapshots')

    # Verify we can query through relationship
    result = await db_session.execute(
        select(Card).where(Card.id == test_card.id)
    )
    card = result.scalar_one()

    # Access should not raise
    _ = card.price_snapshots


@pytest.mark.asyncio
async def test_card_has_no_listings_relationship(db_session):
    """Card should NOT have listings relationship after migration."""
    assert not hasattr(Card, 'listings'), "Listing relationship should be removed"
```

**Step 3: Run test to verify it fails**

```bash
docker compose exec backend pytest tests/models/test_listing_removal.py -v
```

Expected: FAIL on `test_card_has_no_listings_relationship` (listings still exists)

**Step 4: Remove Listing relationship from Card model**

```python
# backend/app/models/card.py - DELETE lines 95-96
# Remove this:
# listings: Mapped[list["Listing"]] = relationship(
#     "Listing", back_populates="card", cascade="all, delete-orphan"
# )
```

**Step 5: Remove Listing relationship from Marketplace model**

```python
# backend/app/models/marketplace.py - DELETE the listings relationship
# Remove:
# listings: Mapped[list["Listing"]] = relationship(
#     "Listing", back_populates="marketplace", cascade="all, delete-orphan"
# )
```

**Step 6: Remove deprecation wrapper and Listing from __init__.py**

```python
# backend/app/models/__init__.py
# DELETE lines 16 (import), 66-100 (deprecation wrapper), and "Listing" from __all__
```

**Step 7: Create migration to drop listings table**

```bash
docker compose exec backend alembic revision --autogenerate -m "drop_listing_table"
```

Then edit the generated migration:

```python
# backend/alembic/versions/xxxx_drop_listing_table.py
def upgrade():
    # Drop indexes first
    op.drop_index('ix_listings_card_marketplace', table_name='listings')
    op.drop_index('ix_listings_price', table_name='listings')
    op.drop_index('ix_listings_last_seen', table_name='listings')

    # Drop the table
    op.drop_table('listings')


def downgrade():
    # Recreation is complex - recommend against downgrade
    raise NotImplementedError("Listing table removal cannot be reversed")
```

**Step 8: Run tests**

```bash
docker compose exec backend pytest tests/models/test_listing_removal.py -v
```

Expected: PASS

**Step 9: Delete listing.py model file**

```bash
rm backend/app/models/listing.py
```

**Step 10: Run full test suite**

```bash
docker compose exec backend pytest tests/ -v --tb=short
```

**Step 11: Commit**

```bash
git add -A
git commit -m "feat: complete Listing to PriceSnapshot migration

- Remove Listing relationship from Card and Marketplace models
- Remove deprecation wrapper from models/__init__.py
- Add migration to drop listings table
- Delete listing.py model file

BREAKING: Listing model no longer exists. Use PriceSnapshot for all price data.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 2: Add Proper Transaction Boundaries

**Problem:** `db.flush()` without transaction scope can leave partial data on failure.

**Files:**
- Modify: `backend/app/services/ingestion/bulk_ops.py:470-533`
- Create: `backend/app/db/transaction.py`
- Test: `backend/tests/db/test_transactions.py`

**Step 1: Create transaction context manager**

```python
# backend/app/db/transaction.py
"""
Transaction management utilities.

Provides context managers for explicit transaction boundaries
to prevent partial commits on multi-step operations.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger()


@asynccontextmanager
async def atomic(db: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """
    Execute operations atomically - all or nothing.

    Usage:
        async with atomic(db) as session:
            session.add(obj1)
            session.add(obj2)
            # Auto-commits on success, auto-rollbacks on exception

    Args:
        db: SQLAlchemy async session

    Yields:
        The same session for chaining

    Raises:
        Exception: Re-raises any exception after rollback
    """
    try:
        yield db
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("Transaction rolled back", error=str(e), exc_info=True)
        raise


@asynccontextmanager
async def savepoint(db: AsyncSession, name: str = "sp") -> AsyncGenerator[AsyncSession, None]:
    """
    Create a savepoint for partial rollback capability.

    Usage:
        async with savepoint(db, "batch_insert") as session:
            # If this fails, only this block rolls back
            session.add(obj)

    Args:
        db: SQLAlchemy async session
        name: Savepoint name for debugging

    Yields:
        The same session
    """
    async with db.begin_nested():
        try:
            yield db
        except Exception as e:
            logger.warning(f"Savepoint {name} rolled back", error=str(e))
            raise
```

**Step 2: Write test for atomic transactions**

```python
# backend/tests/db/test_transactions.py
import pytest
from sqlalchemy import select

from app.db.transaction import atomic, savepoint
from app.models import Card


@pytest.mark.asyncio
async def test_atomic_commits_on_success(db_session):
    """Atomic context commits all changes on success."""
    async with atomic(db_session) as session:
        card = Card(
            scryfall_id="test-atomic-123",
            name="Test Atomic Card",
            set_code="TST",
        )
        session.add(card)

    # Verify committed
    result = await db_session.execute(
        select(Card).where(Card.scryfall_id == "test-atomic-123")
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_atomic_rollbacks_on_failure(db_session):
    """Atomic context rolls back all changes on exception."""
    with pytest.raises(ValueError):
        async with atomic(db_session) as session:
            card = Card(
                scryfall_id="test-rollback-123",
                name="Test Rollback Card",
                set_code="TST",
            )
            session.add(card)
            await session.flush()  # Write to DB
            raise ValueError("Simulated failure")

    # Verify rolled back
    result = await db_session.execute(
        select(Card).where(Card.scryfall_id == "test-rollback-123")
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_savepoint_partial_rollback(db_session):
    """Savepoint allows partial rollback within transaction."""
    # First card succeeds
    card1 = Card(
        scryfall_id="test-sp-success-123",
        name="Success Card",
        set_code="TST",
    )
    db_session.add(card1)
    await db_session.flush()

    # Second card in savepoint fails
    try:
        async with savepoint(db_session, "failing_batch"):
            card2 = Card(
                scryfall_id="test-sp-fail-123",
                name="Fail Card",
                set_code="TST",
            )
            db_session.add(card2)
            await db_session.flush()
            raise ValueError("Batch failed")
    except ValueError:
        pass  # Expected

    await db_session.commit()

    # First card committed, second rolled back
    result1 = await db_session.execute(
        select(Card).where(Card.scryfall_id == "test-sp-success-123")
    )
    assert result1.scalar_one_or_none() is not None

    result2 = await db_session.execute(
        select(Card).where(Card.scryfall_id == "test-sp-fail-123")
    )
    assert result2.scalar_one_or_none() is None
```

**Step 3: Run tests**

```bash
docker compose exec backend pytest tests/db/test_transactions.py -v
```

**Step 4: Refactor ensure_card_exists to use atomic**

```python
# backend/app/services/ingestion/bulk_ops.py
# Add import at top:
from app.db.transaction import atomic, savepoint

# Modify ensure_card_exists (around line 470):
async def ensure_card_exists(
    db: AsyncSession,
    card_data: dict,
) -> int | None:
    """
    Ensure a card exists in the database before importing prices.

    Uses atomic transaction to prevent orphaned card records.
    """
    import json
    from app.models import Card

    scryfall_id = card_data.get("id") or card_data.get("scryfall_id")
    if not scryfall_id:
        logger.warning("Cannot ensure card exists: no scryfall_id provided")
        return None

    # Check if card exists (read-only, no transaction needed)
    result = await db.execute(
        select(Card.id).where(Card.scryfall_id == scryfall_id)
    )
    card_id = result.scalar_one_or_none()

    if card_id:
        return card_id

    # Card doesn't exist - create it atomically
    name = card_data.get("name")
    set_code = card_data.get("set") or card_data.get("set_code")

    if not name or not set_code:
        logger.warning(
            "Cannot create card: missing required fields",
            scryfall_id=scryfall_id,
        )
        return None

    try:
        async with savepoint(db, f"create_card_{scryfall_id}"):
            # ... rest of card creation logic stays the same
            # but now uses savepoint instead of bare flush
            card = Card(
                scryfall_id=scryfall_id,
                name=name,
                set_code=set_code,
                # ... other fields
            )
            db.add(card)
            await db.flush()

            logger.info("Created new card", card_id=card.id, name=name)
            return card.id

    except Exception as e:
        logger.error("Failed to create card", scryfall_id=scryfall_id, error=str(e))
        return None
```

**Step 5: Run full test suite**

```bash
docker compose exec backend pytest tests/ -v --tb=short
```

**Step 6: Commit**

```bash
git add backend/app/db/transaction.py backend/app/services/ingestion/bulk_ops.py backend/tests/db/
git commit -m "feat: add transaction context managers for atomic operations

- Add atomic() for all-or-nothing transactions
- Add savepoint() for partial rollback capability
- Refactor ensure_card_exists to use savepoint
- Add comprehensive transaction tests

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 3: Fix Redis Singleton Race Condition

**Problem:** Double-checked locking pattern has TOCTOU race in async Python.

**Files:**
- Modify: `backend/app/api/deps.py:120-177`
- Test: `backend/tests/api/test_redis_singleton.py`

**Step 1: Write test for concurrent Redis access**

```python
# backend/tests/api/test_redis_singleton.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.api.deps import get_redis, _reset_redis_client


@pytest.fixture(autouse=True)
def reset_redis():
    """Reset Redis singleton before each test."""
    _reset_redis_client()
    yield
    _reset_redis_client()


@pytest.mark.asyncio
async def test_redis_singleton_returns_same_instance():
    """Multiple calls should return the same Redis client."""
    with patch("app.api.deps.Redis") as mock_redis_cls:
        mock_client = AsyncMock()
        mock_redis_cls.return_value = mock_client

        client1 = await get_redis()
        client2 = await get_redis()

        assert client1 is client2
        assert mock_redis_cls.call_count == 1  # Only created once


@pytest.mark.asyncio
async def test_redis_singleton_concurrent_access():
    """Concurrent access should not create multiple clients."""
    call_count = 0

    async def slow_redis_init(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # Simulate slow initialization
        return AsyncMock()

    with patch("app.api.deps.Redis", side_effect=slow_redis_init):
        # Launch 10 concurrent requests
        tasks = [get_redis() for _ in range(10)]
        clients = await asyncio.gather(*tasks)

        # All should get the same client
        assert all(c is clients[0] for c in clients)
        # Only one initialization should have happened
        assert call_count == 1
```

**Step 2: Refactor Redis singleton to use asyncio.Lock properly**

```python
# backend/app/api/deps.py - Replace lines 120-177

import asyncio
from typing import Optional
from redis.asyncio import Redis, ConnectionPool
from app.core.config import settings

# Module-level singleton state
_redis_client: Optional[Redis] = None
_redis_lock = asyncio.Lock()
_redis_init_task: Optional[asyncio.Task] = None


def _reset_redis_client() -> None:
    """Reset Redis client for testing. Do not use in production."""
    global _redis_client, _redis_init_task
    _redis_client = None
    _redis_init_task = None


async def _create_redis_client() -> Redis:
    """Create and configure Redis client."""
    pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=20,
        decode_responses=True,
    )
    return Redis(connection_pool=pool)


async def get_redis() -> Redis:
    """
    Get Redis client singleton.

    Thread-safe initialization using asyncio.Lock.
    All concurrent callers wait for the same initialization.

    Returns:
        Configured Redis client
    """
    global _redis_client, _redis_init_task

    # Fast path: already initialized
    if _redis_client is not None:
        return _redis_client

    # Slow path: need to initialize
    async with _redis_lock:
        # Check again after acquiring lock (another task may have initialized)
        if _redis_client is not None:
            return _redis_client

        # We're the first - create the client
        _redis_client = await _create_redis_client()
        return _redis_client


async def close_redis() -> None:
    """Close Redis connection pool. Call on application shutdown."""
    global _redis_client

    async with _redis_lock:
        if _redis_client is not None:
            await _redis_client.close()
            _redis_client = None
```

**Step 3: Run tests**

```bash
docker compose exec backend pytest tests/api/test_redis_singleton.py -v
```

**Step 4: Commit**

```bash
git add backend/app/api/deps.py backend/tests/api/test_redis_singleton.py
git commit -m "fix: eliminate Redis singleton TOCTOU race condition

- Simplify to single lock acquisition pattern
- Add _reset_redis_client() for test isolation
- Add concurrent access test
- Remove unnecessary double-check outside lock

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Phase 2: Security Hardening

### Task 4: Comprehensive IDOR Audit and Rate-Limited ID Enumeration Protection

**Problem:** `validate_id_list()` caps at 1000 IDs but doesn't prevent enumeration attacks.

**Files:**
- Create: `backend/app/api/middleware/enumeration_protection.py`
- Modify: `backend/app/api/utils/validation.py`
- Test: `backend/tests/security/test_enumeration_protection.py`

**Step 1: Create enumeration protection middleware**

```python
# backend/app/api/middleware/enumeration_protection.py
"""
Protection against ID enumeration attacks.

Tracks failed resource access attempts and implements
exponential backoff for suspicious patterns.
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import structlog
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()

# Configuration
MAX_NOT_FOUND_PER_WINDOW = 10  # Max 404s before rate limiting
WINDOW_SECONDS = 60  # Window for tracking
BLOCK_SECONDS = 300  # Block duration after threshold


@dataclass
class AccessPattern:
    """Track access patterns for a user/IP."""
    not_found_count: int = 0
    window_start: float = field(default_factory=time.time)
    blocked_until: Optional[float] = None

    def is_blocked(self) -> bool:
        if self.blocked_until is None:
            return False
        if time.time() > self.blocked_until:
            self.blocked_until = None
            return False
        return True

    def record_not_found(self) -> bool:
        """Record a 404 and return True if should block."""
        now = time.time()

        # Reset window if expired
        if now - self.window_start > WINDOW_SECONDS:
            self.not_found_count = 0
            self.window_start = now

        self.not_found_count += 1

        if self.not_found_count >= MAX_NOT_FOUND_PER_WINDOW:
            self.blocked_until = now + BLOCK_SECONDS
            return True
        return False


class EnumerationProtectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to detect and block ID enumeration attacks.

    Tracks 404 responses per user/IP and blocks after threshold.
    """

    def __init__(self, app, redis_client=None):
        super().__init__(app)
        self._patterns: dict[str, AccessPattern] = defaultdict(AccessPattern)
        self._redis = redis_client  # Optional Redis for distributed tracking

    def _get_client_key(self, request: Request) -> str:
        """Get unique key for client (user_id or IP)."""
        # Prefer user ID if authenticated
        if hasattr(request.state, "user") and request.state.user:
            return f"user:{request.state.user.id}"

        # Fall back to IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    async def dispatch(self, request: Request, call_next):
        client_key = self._get_client_key(request)
        pattern = self._patterns[client_key]

        # Check if blocked
        if pattern.is_blocked():
            logger.warning(
                "Blocked potential enumeration attack",
                client_key=client_key,
                blocked_until=pattern.blocked_until,
            )
            raise HTTPException(
                status_code=429,
                detail="Too many failed requests. Please try again later.",
            )

        response = await call_next(request)

        # Track 404s on resource endpoints
        if response.status_code == 404:
            # Only track on ID-based endpoints
            path = request.url.path
            if any(seg.isdigit() for seg in path.split("/")):
                should_block = pattern.record_not_found()
                if should_block:
                    logger.warning(
                        "Enumeration threshold exceeded",
                        client_key=client_key,
                        count=pattern.not_found_count,
                    )

        return response
```

**Step 2: Write tests**

```python
# backend/tests/security/test_enumeration_protection.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from starlette.testclient import TestClient

from app.api.middleware.enumeration_protection import (
    EnumerationProtectionMiddleware,
    AccessPattern,
    MAX_NOT_FOUND_PER_WINDOW,
)


def test_access_pattern_blocks_after_threshold():
    """Pattern should block after MAX_NOT_FOUND_PER_WINDOW 404s."""
    pattern = AccessPattern()

    for i in range(MAX_NOT_FOUND_PER_WINDOW - 1):
        assert not pattern.record_not_found()
        assert not pattern.is_blocked()

    # This one should trigger block
    assert pattern.record_not_found()
    assert pattern.is_blocked()


def test_access_pattern_window_reset():
    """Pattern should reset after window expires."""
    pattern = AccessPattern()
    pattern.window_start = 0  # Expired window

    # Should reset and not immediately block
    assert not pattern.record_not_found()
    assert pattern.not_found_count == 1
```

**Step 3: Register middleware in main.py**

```python
# backend/app/main.py - Add after other middleware
from app.api.middleware.enumeration_protection import EnumerationProtectionMiddleware

app.add_middleware(EnumerationProtectionMiddleware)
```

**Step 4: Run tests and commit**

```bash
docker compose exec backend pytest tests/security/ -v
git add backend/app/api/middleware/enumeration_protection.py backend/tests/security/
git commit -m "feat: add enumeration attack protection middleware

- Track 404 responses per user/IP
- Block after 10 not-found responses in 60 seconds
- 5 minute block duration
- Log suspicious patterns

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 5: Add Magic Byte File Validation

**Problem:** File upload only checks content-type header and extension, not actual content.

**Files:**
- Modify: `backend/app/api/routes/imports.py:75-155`
- Create: `backend/app/api/utils/file_validation.py`
- Test: `backend/tests/security/test_file_validation.py`

**Step 1: Create file validation utility**

```python
# backend/app/api/utils/file_validation.py
"""
File content validation utilities.

Validates file contents beyond just extension/content-type,
including magic byte detection and content analysis.
"""
import csv
import io
from typing import Tuple

import structlog

logger = structlog.get_logger()

# Magic bytes for common file types we want to REJECT
DANGEROUS_MAGIC_BYTES = {
    b"MZ": "Windows executable",
    b"\x7fELF": "Linux executable",
    b"PK\x03\x04": "ZIP archive (could contain executables)",
    b"\x00\x00\x01\x00": "ICO file",
    b"GIF87a": "GIF image",
    b"GIF89a": "GIF image",
    b"\xff\xd8\xff": "JPEG image",
    b"\x89PNG": "PNG image",
    b"%PDF": "PDF document",
    b"Rar!": "RAR archive",
    b"\x1f\x8b": "GZIP archive",
}


def detect_dangerous_content(content: bytes) -> Tuple[bool, str]:
    """
    Check if content appears to be a dangerous file type.

    Args:
        content: Raw file bytes

    Returns:
        Tuple of (is_dangerous, reason)
    """
    for magic, file_type in DANGEROUS_MAGIC_BYTES.items():
        if content.startswith(magic):
            return True, f"File appears to be {file_type}"
    return False, ""


def validate_csv_structure(content: str, max_columns: int = 50) -> Tuple[bool, str]:
    """
    Validate that content is actually valid CSV.

    Args:
        content: Decoded file content
        max_columns: Maximum allowed columns

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        reader = csv.reader(io.StringIO(content))

        # Check header row
        header = next(reader, None)
        if not header:
            return False, "CSV file is empty"

        if len(header) > max_columns:
            return False, f"Too many columns ({len(header)} > {max_columns})"

        # Validate a few rows
        row_count = 0
        for row in reader:
            row_count += 1
            if row_count > 10:
                break  # Only validate first 10 rows

            if len(row) != len(header):
                logger.warning(
                    "CSV row column mismatch",
                    expected=len(header),
                    actual=len(row),
                    row=row_count,
                )

        return True, ""

    except csv.Error as e:
        return False, f"Invalid CSV format: {e}"


def validate_import_file(content: bytes) -> Tuple[bool, str]:
    """
    Full validation for import files.

    Checks:
    1. Not a dangerous file type (magic bytes)
    2. Valid UTF-8 encoding
    3. Valid CSV structure

    Args:
        content: Raw file bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check magic bytes
    is_dangerous, reason = detect_dangerous_content(content)
    if is_dangerous:
        logger.warning("Rejected dangerous file upload", reason=reason)
        return False, reason

    # Validate UTF-8
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError as e:
        return False, f"File is not valid UTF-8: {e}"

    # Validate CSV structure
    is_valid, error = validate_csv_structure(decoded)
    if not is_valid:
        return False, error

    return True, ""
```

**Step 2: Write tests**

```python
# backend/tests/security/test_file_validation.py
import pytest
from app.api.utils.file_validation import (
    detect_dangerous_content,
    validate_csv_structure,
    validate_import_file,
)


class TestDangerousContentDetection:
    def test_detects_windows_executable(self):
        content = b"MZ\x90\x00\x03\x00\x00\x00"  # PE header start
        is_dangerous, reason = detect_dangerous_content(content)
        assert is_dangerous
        assert "executable" in reason.lower()

    def test_detects_linux_executable(self):
        content = b"\x7fELF\x02\x01\x01\x00"  # ELF header
        is_dangerous, reason = detect_dangerous_content(content)
        assert is_dangerous
        assert "executable" in reason.lower()

    def test_detects_zip_archive(self):
        content = b"PK\x03\x04\x14\x00\x00\x00"  # ZIP header
        is_dangerous, reason = detect_dangerous_content(content)
        assert is_dangerous
        assert "ZIP" in reason

    def test_allows_csv_content(self):
        content = b"name,quantity,price\nLightning Bolt,4,2.50"
        is_dangerous, _ = detect_dangerous_content(content)
        assert not is_dangerous


class TestCsvValidation:
    def test_valid_csv(self):
        content = "name,quantity,price\nLightning Bolt,4,2.50\nCounterspell,2,1.00"
        is_valid, error = validate_csv_structure(content)
        assert is_valid
        assert error == ""

    def test_empty_csv_rejected(self):
        content = ""
        is_valid, error = validate_csv_structure(content)
        assert not is_valid
        assert "empty" in error.lower()

    def test_too_many_columns_rejected(self):
        content = ",".join([f"col{i}" for i in range(100)])
        is_valid, error = validate_csv_structure(content, max_columns=50)
        assert not is_valid
        assert "columns" in error.lower()


class TestFullValidation:
    def test_valid_csv_file(self):
        content = b"name,quantity\nBolt,4"
        is_valid, error = validate_import_file(content)
        assert is_valid

    def test_executable_rejected(self):
        content = b"MZ\x90\x00" + b"name,qty\ntest,1"
        is_valid, error = validate_import_file(content)
        assert not is_valid
        assert "executable" in error.lower()

    def test_invalid_utf8_rejected(self):
        content = b"\xff\xfe name,qty"  # Invalid UTF-8
        is_valid, error = validate_import_file(content)
        assert not is_valid
        assert "UTF-8" in error
```

**Step 3: Update imports.py to use new validation**

```python
# backend/app/api/routes/imports.py - Add import and modify upload_import_file
from app.api.utils.file_validation import validate_import_file

@router.post("/upload", response_model=ImportJobResponse)
async def upload_import_file(
    file: UploadFile = File(...),
    platform: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJobResponse:
    # ... platform validation ...

    # Read file content
    content = await file.read()

    # File size check
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Full content validation (magic bytes + UTF-8 + CSV structure)
    is_valid, error = validate_import_file(content)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid file: {error}")

    # Continue with import...
    decoded_content = content.decode("utf-8")
    # ...
```

**Step 4: Run tests and commit**

```bash
docker compose exec backend pytest tests/security/test_file_validation.py -v
git add backend/app/api/utils/file_validation.py backend/app/api/routes/imports.py backend/tests/security/
git commit -m "feat: add magic byte validation for file uploads

- Detect dangerous file types (executables, archives, images)
- Validate CSV structure beyond extension check
- Add comprehensive security tests

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 6: Implement JWT Token Revocation

**Problem:** No way to invalidate tokens on password change or logout.

**Files:**
- Create: `backend/app/services/token_blacklist.py`
- Modify: `backend/app/services/auth.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/api/routes/auth.py`
- Test: `backend/tests/security/test_token_revocation.py`

**Step 1: Create token blacklist service**

```python
# backend/app/services/token_blacklist.py
"""
JWT Token Blacklist Service.

Stores revoked JTIs in Redis for fast lookup.
Tokens are automatically expired based on their original TTL.
"""
from datetime import datetime, timezone
from typing import Optional

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger()

# Redis key prefix for blacklisted tokens
BLACKLIST_PREFIX = "token_blacklist:"


class TokenBlacklistService:
    """
    Service for managing revoked JWT tokens.

    Uses Redis for distributed blacklist storage.
    """

    def __init__(self, redis: Redis):
        self.redis = redis

    async def revoke_token(self, jti: str, expires_at: datetime) -> bool:
        """
        Add a token to the blacklist.

        Args:
            jti: JWT ID to revoke
            expires_at: When the token naturally expires

        Returns:
            True if successfully blacklisted
        """
        key = f"{BLACKLIST_PREFIX}{jti}"

        # Calculate TTL (keep in blacklist until token would expire anyway)
        now = datetime.now(timezone.utc)
        ttl_seconds = int((expires_at - now).total_seconds())

        if ttl_seconds <= 0:
            # Token already expired, no need to blacklist
            return True

        try:
            await self.redis.setex(key, ttl_seconds, "revoked")
            logger.info("Token revoked", jti=jti, ttl_seconds=ttl_seconds)
            return True
        except Exception as e:
            logger.error("Failed to revoke token", jti=jti, error=str(e))
            return False

    async def is_revoked(self, jti: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            jti: JWT ID to check

        Returns:
            True if token is revoked
        """
        key = f"{BLACKLIST_PREFIX}{jti}"

        try:
            exists = await self.redis.exists(key)
            return bool(exists)
        except Exception as e:
            logger.error("Failed to check token blacklist", jti=jti, error=str(e))
            # Fail open to prevent lockout, but log for monitoring
            return False

    async def revoke_all_user_tokens(self, user_id: int) -> bool:
        """
        Revoke all tokens for a user (e.g., on password change).

        Note: This requires tracking active tokens per user,
        which we don't currently do. For now, just log the intent.
        A full implementation would use a user_tokens set in Redis.

        Args:
            user_id: User whose tokens to revoke

        Returns:
            True if successful
        """
        # TODO: Implement user token tracking for full revocation
        logger.info("User token revocation requested", user_id=user_id)
        return True
```

**Step 2: Modify auth.py to include JTI in tokens**

```python
# backend/app/services/auth.py - Ensure JTI is included (already present per research)
# Add this function if not present:

def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate an access token.

    Returns:
        Token payload dict with 'sub', 'exp', 'jti' or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

**Step 3: Modify deps.py to check blacklist**

```python
# backend/app/api/deps.py - Modify get_current_user
from app.services.token_blacklist import TokenBlacklistService

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    """Get current user from JWT, checking blacklist."""
    token = credentials.credentials

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Check token blacklist
    jti = payload.get("jti")
    if jti:
        blacklist = TokenBlacklistService(redis)
        if await blacklist.is_revoked(jti):
            raise HTTPException(status_code=401, detail="Token has been revoked")

    # ... rest of user lookup ...
```

**Step 4: Add logout endpoint**

```python
# backend/app/api/routes/auth.py - Add logout endpoint
from datetime import datetime, timezone
from app.services.token_blacklist import TokenBlacklistService

@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    redis: Redis = Depends(get_redis),
):
    """
    Logout by revoking the current token.
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    jti = payload.get("jti")
    exp = payload.get("exp")

    if jti and exp:
        blacklist = TokenBlacklistService(redis)
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
        await blacklist.revoke_token(jti, expires_at)

    return {"message": "Successfully logged out"}
```

**Step 5: Write tests and commit**

```python
# backend/tests/security/test_token_revocation.py
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from app.services.token_blacklist import TokenBlacklistService


@pytest.mark.asyncio
async def test_revoke_token():
    """Token should be marked as revoked."""
    mock_redis = AsyncMock()
    service = TokenBlacklistService(mock_redis)

    jti = "test-jti-123"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    result = await service.revoke_token(jti, expires_at)

    assert result is True
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_is_revoked_returns_true_for_blacklisted():
    """is_revoked should return True for blacklisted tokens."""
    mock_redis = AsyncMock()
    mock_redis.exists.return_value = 1
    service = TokenBlacklistService(mock_redis)

    result = await service.is_revoked("blacklisted-jti")

    assert result is True


@pytest.mark.asyncio
async def test_is_revoked_returns_false_for_valid():
    """is_revoked should return False for valid tokens."""
    mock_redis = AsyncMock()
    mock_redis.exists.return_value = 0
    service = TokenBlacklistService(mock_redis)

    result = await service.is_revoked("valid-jti")

    assert result is False
```

```bash
docker compose exec backend pytest tests/security/test_token_revocation.py -v
git add backend/app/services/token_blacklist.py backend/app/api/routes/auth.py backend/tests/security/
git commit -m "feat: implement JWT token revocation via Redis blacklist

- Add TokenBlacklistService for distributed token revocation
- Check blacklist on every authenticated request
- Add /logout endpoint to revoke current token
- Tokens auto-expire from blacklist based on original TTL

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 7: Fix API Contract - Eliminate Null Price Values

**Problem:** API returns null for price fields, requiring `safeToFixed()` band-aid on frontend.

**Files:**
- Modify: `backend/app/schemas/card.py`
- Modify: `backend/app/api/routes/cards.py`
- Modify: `frontend/src/types/index.ts`
- Test: `backend/tests/api/test_card_schema.py`

**Step 1: Update Pydantic schema to use default values**

```python
# backend/app/schemas/card.py - Update price fields
from pydantic import BaseModel, Field
from decimal import Decimal

class CardPriceResponse(BaseModel):
    """Card price response with guaranteed non-null values."""

    price: Decimal = Field(default=Decimal("0.00"))
    price_low: Decimal = Field(default=Decimal("0.00"))
    price_mid: Decimal = Field(default=Decimal("0.00"))
    price_high: Decimal = Field(default=Decimal("0.00"))
    price_market: Decimal = Field(default=Decimal("0.00"))

    # Add a flag to indicate if price data is available
    has_price_data: bool = False

    class Config:
        from_attributes = True


class CardDetailResponse(BaseModel):
    """Full card response with prices."""
    id: int
    name: str
    set_code: str
    # ... other fields ...

    # Prices guaranteed non-null
    current_price: Decimal = Field(default=Decimal("0.00"))
    price_change_24h: Decimal = Field(default=Decimal("0.00"))
    price_change_7d: Decimal = Field(default=Decimal("0.00"))
    has_price_data: bool = False
```

**Step 2: Update route to populate defaults**

```python
# backend/app/api/routes/cards.py - Ensure defaults are set
@router.get("/{card_id}", response_model=CardDetailResponse)
async def get_card(card_id: int, db: AsyncSession = Depends(get_db)):
    card = await get_card_by_id(db, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Get latest price snapshot
    price_data = await get_latest_price(db, card_id)

    return CardDetailResponse(
        id=card.id,
        name=card.name,
        set_code=card.set_code,
        # ... other fields ...
        current_price=price_data.price if price_data else Decimal("0.00"),
        price_change_24h=price_data.change_24h if price_data else Decimal("0.00"),
        price_change_7d=price_data.change_7d if price_data else Decimal("0.00"),
        has_price_data=price_data is not None,
    )
```

**Step 3: Update frontend types**

```typescript
// frontend/src/types/index.ts
export interface CardPrice {
  price: number;  // Always a number, defaults to 0
  price_low: number;
  price_mid: number;
  price_high: number;
  price_market: number;
  has_price_data: boolean;  // Check this before displaying
}

// Usage in component:
// {card.has_price_data ? card.price.toFixed(2) : 'N/A'}
```

**Step 4: Remove safeToFixed usage where API guarantees values**

```typescript
// frontend/src/lib/utils.ts - Keep safeToFixed but add deprecation
/**
 * @deprecated Use has_price_data check instead for API values.
 * Only needed for computed values that might be null.
 */
export function safeToFixed(value: number | null | undefined, digits: number = 2): string {
  // ...
}
```

**Step 5: Test and commit**

```bash
docker compose exec backend pytest tests/api/test_card_schema.py -v
git add backend/app/schemas/ backend/app/api/routes/cards.py frontend/src/types/
git commit -m "fix: guarantee non-null price values in API responses

- Add default values for all price fields in schemas
- Add has_price_data flag to indicate data availability
- Update frontend types to reflect non-nullable prices
- Deprecate safeToFixed for API values

BREAKING: Price fields now return 0.00 instead of null.
Check has_price_data before displaying prices.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Phase 3: Performance & Scalability

### Task 8: Implement Cursor-Based Pagination

**Problem:** Offset pagination degrades as data grows; `?offset=100000` scans 100k rows.

**Files:**
- Create: `backend/app/api/utils/pagination.py`
- Modify: `backend/app/api/routes/cards.py`
- Modify: `backend/app/api/routes/inventory.py`
- Test: `backend/tests/api/test_pagination.py`

**Step 1: Create cursor pagination utility**

```python
# backend/app/api/utils/pagination.py
"""
Cursor-based pagination utilities.

Provides efficient pagination for large datasets using
encoded cursors instead of offset/limit.
"""
import base64
import json
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select, and_, or_

T = TypeVar("T")


def encode_cursor(data: dict) -> str:
    """Encode cursor data to URL-safe string."""
    json_str = json.dumps(data, sort_keys=True, default=str)
    return base64.urlsafe_b64encode(json_str.encode()).decode()


def decode_cursor(cursor: str) -> dict:
    """Decode cursor string to data dict."""
    try:
        json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
        return json.loads(json_str)
    except Exception:
        return {}


class CursorPage(BaseModel, Generic[T]):
    """Paginated response with cursor navigation."""
    items: list[T]
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None
    has_more: bool = False
    total_count: Optional[int] = None  # Only if explicitly requested


def apply_cursor_pagination(
    query: Select,
    cursor: Optional[str],
    limit: int,
    order_column,  # SQLAlchemy column
    id_column,     # For tiebreaker
    descending: bool = True,
) -> Select:
    """
    Apply cursor-based pagination to a SQLAlchemy query.

    Uses (order_column, id) for stable ordering with tiebreaker.

    Args:
        query: Base query
        cursor: Encoded cursor string (or None for first page)
        limit: Items per page
        order_column: Primary sort column
        id_column: Tiebreaker column (usually primary key)
        descending: Sort direction

    Returns:
        Modified query with pagination applied
    """
    if cursor:
        cursor_data = decode_cursor(cursor)
        cursor_value = cursor_data.get("v")
        cursor_id = cursor_data.get("id")

        if cursor_value is not None and cursor_id is not None:
            if descending:
                # For DESC: get items < cursor OR (== cursor AND id < cursor_id)
                query = query.where(
                    or_(
                        order_column < cursor_value,
                        and_(
                            order_column == cursor_value,
                            id_column < cursor_id,
                        ),
                    )
                )
            else:
                # For ASC: get items > cursor OR (== cursor AND id > cursor_id)
                query = query.where(
                    or_(
                        order_column > cursor_value,
                        and_(
                            order_column == cursor_value,
                            id_column > cursor_id,
                        ),
                    )
                )

    # Apply ordering
    if descending:
        query = query.order_by(order_column.desc(), id_column.desc())
    else:
        query = query.order_by(order_column.asc(), id_column.asc())

    # Fetch one extra to determine has_more
    query = query.limit(limit + 1)

    return query


def build_cursor_response(
    items: list,
    limit: int,
    order_attr: str,
    id_attr: str = "id",
) -> tuple[list, Optional[str], bool]:
    """
    Build cursor response from query results.

    Args:
        items: Query results (may have limit+1 items)
        limit: Requested limit
        order_attr: Attribute name for order value
        id_attr: Attribute name for ID

    Returns:
        (items, next_cursor, has_more)
    """
    has_more = len(items) > limit
    items = items[:limit]  # Trim extra item

    next_cursor = None
    if has_more and items:
        last_item = items[-1]
        cursor_data = {
            "v": getattr(last_item, order_attr),
            "id": getattr(last_item, id_attr),
        }
        next_cursor = encode_cursor(cursor_data)

    return items, next_cursor, has_more
```

**Step 2: Update cards search to use cursor pagination**

```python
# backend/app/api/routes/cards.py
from app.api.utils.pagination import (
    apply_cursor_pagination,
    build_cursor_response,
    CursorPage,
)

@router.get("/search", response_model=CursorPage[CardSearchResult])
async def search_cards(
    q: str = Query(..., min_length=1),
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name", regex="^(name|price|set_code)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search cards with cursor-based pagination.

    Use the returned next_cursor for subsequent pages.
    """
    base_query = select(Card).where(Card.name.ilike(f"%{q}%"))

    # Determine sort column
    sort_column = getattr(Card, sort_by)

    # Apply cursor pagination
    query = apply_cursor_pagination(
        base_query,
        cursor=cursor,
        limit=limit,
        order_column=sort_column,
        id_column=Card.id,
        descending=(sort_by == "price"),
    )

    result = await db.execute(query)
    items = list(result.scalars().all())

    # Build response
    items, next_cursor, has_more = build_cursor_response(
        items, limit, order_attr=sort_by
    )

    return CursorPage(
        items=[CardSearchResult.from_orm(c) for c in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )
```

**Step 3: Write tests**

```python
# backend/tests/api/test_pagination.py
import pytest
from app.api.utils.pagination import (
    encode_cursor,
    decode_cursor,
    build_cursor_response,
)


def test_cursor_encode_decode_roundtrip():
    """Cursor should survive encode/decode."""
    data = {"v": "2025-01-01", "id": 123}
    encoded = encode_cursor(data)
    decoded = decode_cursor(encoded)
    assert decoded == data


def test_build_cursor_response_with_more():
    """Should return cursor when more items exist."""

    class FakeItem:
        def __init__(self, id, name):
            self.id = id
            self.name = name

    items = [FakeItem(i, f"Item {i}") for i in range(11)]  # 11 items

    result_items, cursor, has_more = build_cursor_response(
        items, limit=10, order_attr="name"
    )

    assert len(result_items) == 10
    assert has_more is True
    assert cursor is not None


def test_build_cursor_response_last_page():
    """Should not return cursor on last page."""

    class FakeItem:
        def __init__(self, id, name):
            self.id = id
            self.name = name

    items = [FakeItem(i, f"Item {i}") for i in range(5)]  # Only 5 items

    result_items, cursor, has_more = build_cursor_response(
        items, limit=10, order_attr="name"
    )

    assert len(result_items) == 5
    assert has_more is False
    assert cursor is None
```

**Step 4: Run tests and commit**

```bash
docker compose exec backend pytest tests/api/test_pagination.py -v
git add backend/app/api/utils/pagination.py backend/app/api/routes/cards.py backend/tests/api/
git commit -m "feat: implement cursor-based pagination

- Add cursor encode/decode utilities
- Add apply_cursor_pagination for SQLAlchemy queries
- Update card search to use cursor pagination
- Maintains stable ordering with (sort_column, id) tiebreaker

BREAKING: /cards/search now returns CursorPage instead of offset-based response.
Use next_cursor parameter instead of offset.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 9: Fix N+1 Query Problem with Eager Loading

**Problem:** Lazy-loaded relationships cause N+1 queries on list endpoints.

**Files:**
- Modify: `backend/app/api/routes/inventory.py`
- Modify: `backend/app/api/routes/want_list.py`
- Modify: `backend/app/api/routes/recommendations.py`
- Test: `backend/tests/performance/test_query_count.py`

**Step 1: Create query counting test utility**

```python
# backend/tests/performance/test_query_count.py
"""
Tests to verify N+1 queries are eliminated.
"""
import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.models import Card, InventoryItem


class QueryCounter:
    """Count SQL queries executed."""

    def __init__(self):
        self.count = 0
        self.queries = []

    def callback(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1
        self.queries.append(statement[:100])

    def __enter__(self):
        event.listen(Engine, "before_cursor_execute", self.callback)
        return self

    def __exit__(self, *args):
        event.remove(Engine, "before_cursor_execute", self.callback)


@pytest.mark.asyncio
async def test_inventory_list_no_n_plus_one(client, auth_headers, test_inventory_item):
    """Listing inventory should not cause N+1 queries."""
    with QueryCounter() as counter:
        response = await client.get("/api/inventory", headers=auth_headers)

    assert response.status_code == 200
    # Should be max 2-3 queries: count + fetch (+ optional auth)
    assert counter.count <= 3, f"Too many queries: {counter.queries}"


@pytest.mark.asyncio
async def test_want_list_no_n_plus_one(client, auth_headers, test_want_list_item):
    """Listing want list should not cause N+1 queries."""
    with QueryCounter() as counter:
        response = await client.get("/api/want-list", headers=auth_headers)

    assert response.status_code == 200
    assert counter.count <= 3, f"Too many queries: {counter.queries}"
```

**Step 2: Add eager loading to inventory route**

```python
# backend/app/api/routes/inventory.py
from sqlalchemy.orm import selectinload

@router.get("", response_model=InventoryListResponse)
async def list_inventory(
    # ... params ...
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    query = (
        select(InventoryItem)
        .where(InventoryItem.user_id == current_user.id)
        .options(
            selectinload(InventoryItem.card),  # Eager load card
            selectinload(InventoryItem.card).selectinload(Card.price_snapshots),  # And prices
        )
        .order_by(InventoryItem.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    # ...
```

**Step 3: Add eager loading to want_list route**

```python
# backend/app/api/routes/want_list.py
from sqlalchemy.orm import selectinload

@router.get("")
async def list_want_list_items(
    # ... params ...
):
    query = (
        select(WantListItem)
        .where(WantListItem.user_id == current_user.id)
        .options(selectinload(WantListItem.card))  # Eager load card
        .order_by(WantListItem.priority.desc())
        # ...
    )
```

**Step 4: Add eager loading to recommendations route**

```python
# backend/app/api/routes/recommendations.py
from sqlalchemy.orm import selectinload, joinedload

@router.get("")
async def list_recommendations(
    # ... params ...
):
    query = (
        select(Recommendation)
        .options(
            joinedload(Recommendation.card),  # Always need card
            joinedload(Recommendation.marketplace),
        )
        # ...
    )
```

**Step 5: Run performance tests and commit**

```bash
docker compose exec backend pytest tests/performance/test_query_count.py -v
git add backend/app/api/routes/ backend/tests/performance/
git commit -m "perf: eliminate N+1 queries with eager loading

- Add selectinload to inventory list endpoint
- Add selectinload to want list endpoint
- Add joinedload to recommendations endpoint
- Add query count tests to prevent regression

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 10: Add Query Limits and Index Hints for Aggregations

**Problem:** Aggregation queries scan full tables even with limits on results.

**Files:**
- Modify: `backend/app/api/routes/market.py`
- Create: `backend/alembic/versions/xxxx_add_market_indexes.py`

**Step 1: Add optimized indexes for market queries**

```python
# backend/alembic/versions/xxxx_add_market_indexes.py
"""Add indexes for market aggregation queries."""

def upgrade():
    # Index for top movers query (price change lookups)
    op.create_index(
        "ix_price_snapshots_time_card_price",
        "price_snapshots",
        ["time", "card_id", "price"],
        postgresql_where="currency = 'USD'",
    )

    # Index for recent activity (last 24h queries)
    op.create_index(
        "ix_price_snapshots_recent",
        "price_snapshots",
        ["time DESC", "marketplace_id"],
        postgresql_where="time > NOW() - INTERVAL '7 days'",
    )


def downgrade():
    op.drop_index("ix_price_snapshots_time_card_price")
    op.drop_index("ix_price_snapshots_recent")
```

**Step 2: Add materialized view for top movers (optional but recommended)**

```python
# backend/app/api/routes/market.py
# Add early termination and limits to aggregation

@router.get("/top-movers")
async def get_top_movers(
    window: str = Query("24h", regex="^(24h|7d|30d)$"),
    limit: int = Query(10, ge=1, le=50),  # Hard cap at 50
    db: AsyncSession = Depends(get_db),
):
    """
    Get top price movers with optimized query.

    Uses subquery with limit to avoid full table scan.
    """
    # Subquery to get only cards with recent activity
    recent_cards = (
        select(PriceSnapshot.card_id)
        .where(PriceSnapshot.time >= func.now() - text(f"INTERVAL '{window}'"))
        .distinct()
        .limit(10000)  # Cap candidate pool
        .subquery()
    )

    # Main query only considers recent cards
    query = (
        select(...)
        .where(Card.id.in_(select(recent_cards.c.card_id)))
        .order_by(...)
        .limit(limit)
    )
```

**Step 3: Commit**

```bash
docker compose exec backend alembic upgrade head
git add backend/alembic/versions/ backend/app/api/routes/market.py
git commit -m "perf: optimize market aggregation queries

- Add partial indexes for common market queries
- Cap candidate pool in top movers to 10k cards
- Add hard limit of 50 results

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 11: Optimize PriceSnapshot Composite Key

**Problem:** 6-column composite PK has high write overhead.

**Files:**
- Analyze current performance
- Create: `backend/alembic/versions/xxxx_add_snapshot_id.py` (if needed)

**Step 1: Analyze current write performance**

```bash
# Check current index sizes and write latency
docker compose exec db psql -U dualcaster_user -d dualcaster_deals -c "
SELECT
    indexrelname as index_name,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE relname = 'price_snapshots'
ORDER BY pg_relation_size(indexrelid) DESC;
"
```

**Step 2: If write latency is problematic, add surrogate key**

```python
# backend/alembic/versions/xxxx_add_snapshot_id.py
"""Add surrogate key to price_snapshots for faster writes."""

def upgrade():
    # Add auto-increment ID
    op.add_column(
        "price_snapshots",
        sa.Column("id", sa.BigInteger, autoincrement=True),
    )

    # Create unique constraint on natural key (keeps data integrity)
    op.create_unique_constraint(
        "uq_price_snapshots_natural_key",
        "price_snapshots",
        ["time", "card_id", "marketplace_id", "condition", "is_foil", "language"],
    )

    # Note: Changing PK on TimescaleDB hypertable requires special handling
    # This adds ID for future use without changing PK


def downgrade():
    op.drop_constraint("uq_price_snapshots_natural_key", "price_snapshots")
    op.drop_column("price_snapshots", "id")
```

**Step 3: Document decision**

If analysis shows acceptable performance, document why we're keeping the composite key:

```markdown
# Decision: Keep Composite Primary Key on price_snapshots

**Date:** 2026-01-11
**Status:** Decided - Keep Current

## Context
The price_snapshots table uses a 6-column composite primary key.

## Analysis
- Current write latency: Xms average
- Index size: X MB
- TimescaleDB chunking mitigates scan overhead
- Compression after 7 days reduces storage

## Decision
Keep composite PK because:
1. Natural key ensures data integrity without application logic
2. TimescaleDB handles it efficiently with chunk exclusion
3. Adding surrogate key would require ON CONFLICT handling changes

## Monitoring
- Alert if write latency > 100ms
- Review quarterly with data growth
```

---

### Task 12: Add Celery Task Backpressure

**Problem:** Tasks can queue unbounded if execution takes longer than schedule interval.

**Files:**
- Modify: `backend/app/tasks/analytics.py`
- Create: `backend/app/tasks/utils/backpressure.py`

**Step 1: Create backpressure utility**

```python
# backend/app/tasks/utils/backpressure.py
"""
Celery task backpressure utilities.

Prevents task queue buildup by checking if previous
instance is still running before accepting new work.
"""
import functools
from typing import Callable

from redis import Redis
import structlog

logger = structlog.get_logger()

# Lock timeout should be > max expected task duration
DEFAULT_LOCK_TIMEOUT = 3600  # 1 hour


def single_instance(
    lock_name: str,
    timeout: int = DEFAULT_LOCK_TIMEOUT,
    redis_url: str = None,
):
    """
    Decorator to ensure only one instance of a task runs at a time.

    Usage:
        @shared_task
        @single_instance("analytics_lock")
        def run_analytics():
            ...

    Args:
        lock_name: Unique name for the lock
        timeout: Lock auto-expire time (prevents deadlock)
        redis_url: Redis URL (uses settings if not provided)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from app.core.config import settings

            redis = Redis.from_url(redis_url or settings.redis_url)
            lock_key = f"celery_lock:{lock_name}"

            # Try to acquire lock
            acquired = redis.set(lock_key, "1", nx=True, ex=timeout)

            if not acquired:
                logger.warning(
                    "Task skipped - previous instance still running",
                    task=func.__name__,
                    lock=lock_name,
                )
                return {"status": "skipped", "reason": "previous_running"}

            try:
                return func(*args, **kwargs)
            finally:
                # Release lock
                redis.delete(lock_key)

        return wrapper
    return decorator


def check_queue_depth(queue_name: str, max_depth: int = 100) -> bool:
    """
    Check if queue has too many pending tasks.

    Args:
        queue_name: Celery queue name
        max_depth: Maximum allowed pending tasks

    Returns:
        True if queue depth is acceptable
    """
    from app.core.config import settings

    redis = Redis.from_url(settings.redis_url)
    depth = redis.llen(queue_name)

    if depth > max_depth:
        logger.warning(
            "Queue depth exceeded",
            queue=queue_name,
            depth=depth,
            max=max_depth,
        )
        return False
    return True
```

**Step 2: Apply to analytics task**

```python
# backend/app/tasks/analytics.py
from app.tasks.utils.backpressure import single_instance

@shared_task(bind=True, max_retries=2, default_retry_delay=300)
@single_instance("market_analytics", timeout=1800)  # 30 min timeout
def run_market_analytics(self, batch_size: int = 2000, target_date: str | None = None):
    """
    Run analytics for market cards.

    Only one instance runs at a time. If previous run is still
    executing, this invocation is skipped.
    """
    # ... rest of implementation ...
```

**Step 3: Test and commit**

```python
# backend/tests/tasks/test_backpressure.py
import pytest
from unittest.mock import MagicMock, patch

from app.tasks.utils.backpressure import single_instance


def test_single_instance_blocks_concurrent():
    """Second call should be skipped while first is running."""
    mock_redis = MagicMock()
    mock_redis.set.side_effect = [True, False]  # First succeeds, second fails

    @single_instance("test_lock", redis_url="redis://fake")
    def my_task():
        return "executed"

    with patch("app.tasks.utils.backpressure.Redis.from_url", return_value=mock_redis):
        result1 = my_task()
        result2 = my_task()

    assert result1 == "executed"
    assert result2["status"] == "skipped"
```

```bash
git add backend/app/tasks/utils/backpressure.py backend/app/tasks/analytics.py backend/tests/tasks/
git commit -m "feat: add Celery task backpressure controls

- Add single_instance decorator for exclusive task execution
- Add check_queue_depth for monitoring
- Apply to market analytics task
- Prevents unbounded queue growth

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Phase 4: Reliability

### Task 13: Implement Circuit Breaker for External APIs

**Problem:** External API failures cause cascading timeouts.

**Files:**
- Create: `backend/app/core/circuit_breaker.py`
- Modify: `backend/app/services/tournaments/topdeck_client.py`
- Modify: `backend/app/services/ingestion/adapters/tcgplayer.py`

**Step 1: Create circuit breaker implementation**

```python
# backend/app/core/circuit_breaker.py
"""
Circuit breaker pattern for external service calls.

Prevents cascading failures by failing fast when a service
is unhealthy, with automatic recovery attempts.
"""
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for external service calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service unhealthy, fail fast without calling
    - HALF_OPEN: Testing if service recovered

    Usage:
        breaker = CircuitBreaker(name="tcgplayer")

        async with breaker:
            result = await external_api_call()
    """
    name: str
    failure_threshold: int = 5       # Failures before opening
    recovery_timeout: float = 30.0   # Seconds before trying half-open
    half_open_requests: int = 3      # Successful requests to close

    # State
    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = field(default=0)
    success_count: int = field(default=0)
    last_failure_time: Optional[float] = field(default=None)

    async def __aenter__(self):
        if self.state == CircuitState.OPEN:
            # Check if we should try half-open
            if self._should_attempt_recovery():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info(f"Circuit {self.name} entering half-open state")
            else:
                raise CircuitOpenError(
                    f"Circuit {self.name} is open. "
                    f"Retry after {self._time_until_recovery():.1f}s"
                )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._record_failure()
        else:
            self._record_success()
        return False  # Don't suppress exceptions

    def _should_attempt_recovery(self) -> bool:
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _time_until_recovery(self) -> float:
        if self.last_failure_time is None:
            return 0
        elapsed = time.time() - self.last_failure_time
        return max(0, self.recovery_timeout - elapsed)

    def _record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery test - back to open
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit {self.name} reopened after half-open failure")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit {self.name} opened after {self.failure_count} failures"
            )

    def _record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_requests:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit {self.name} closed after successful recovery")
        else:
            # Reset failure count on success in closed state
            self.failure_count = 0


class CircuitOpenError(Exception):
    """Raised when circuit is open and request should fail fast."""
    pass


# Global circuit breakers for external services
_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name=name, **kwargs)
    return _breakers[name]
```

**Step 2: Apply to TopDeck client**

```python
# backend/app/services/tournaments/topdeck_client.py
from app.core.circuit_breaker import get_circuit_breaker, CircuitOpenError

class TopDeckClient:
    def __init__(self):
        self._circuit = get_circuit_breaker(
            "topdeck",
            failure_threshold=3,
            recovery_timeout=60,
        )

    async def _request(self, endpoint: str, method: str, **kwargs):
        try:
            async with self._circuit:
                response = await self._client.request(method, endpoint, **kwargs)
                # ... handle response ...
                return response
        except CircuitOpenError:
            logger.warning("TopDeck circuit open, failing fast")
            raise TopDeckAPIError("Service temporarily unavailable")
```

**Step 3: Apply to TCGPlayer adapter**

```python
# backend/app/services/ingestion/adapters/tcgplayer.py
from app.core.circuit_breaker import get_circuit_breaker, CircuitOpenError

class TCGPlayerAdapter:
    def __init__(self):
        self._circuit = get_circuit_breaker(
            "tcgplayer",
            failure_threshold=5,
            recovery_timeout=120,
        )

    async def fetch_prices(self, card_ids: list[int]):
        try:
            async with self._circuit:
                # ... existing implementation ...
        except CircuitOpenError:
            logger.warning("TCGPlayer circuit open")
            return []  # Return empty, don't block ingestion
```

**Step 4: Test and commit**

```python
# backend/tests/core/test_circuit_breaker.py
import pytest
from app.core.circuit_breaker import CircuitBreaker, CircuitState, CircuitOpenError


@pytest.mark.asyncio
async def test_circuit_opens_after_failures():
    """Circuit should open after failure threshold."""
    breaker = CircuitBreaker(name="test", failure_threshold=2)

    # First failure
    async with breaker:
        pass
    breaker._record_failure()

    # Second failure - should open
    async with breaker:
        pass
    breaker._record_failure()

    assert breaker.state == CircuitState.OPEN

    # Next call should fail fast
    with pytest.raises(CircuitOpenError):
        async with breaker:
            pass


@pytest.mark.asyncio
async def test_circuit_recovers():
    """Circuit should recover after timeout."""
    breaker = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0)

    # Open the circuit
    breaker._record_failure()
    assert breaker.state == CircuitState.OPEN

    # Should transition to half-open (recovery_timeout=0)
    async with breaker:
        pass

    assert breaker.state == CircuitState.HALF_OPEN
```

```bash
git add backend/app/core/circuit_breaker.py backend/app/services/tournaments/ backend/app/services/ingestion/adapters/ backend/tests/core/
git commit -m "feat: implement circuit breaker for external APIs

- Add CircuitBreaker class with CLOSED/OPEN/HALF_OPEN states
- Apply to TopDeck.gg client
- Apply to TCGPlayer adapter
- Fail fast when services are unhealthy
- Auto-recovery after timeout

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 14: Add Celery Dead Letter Queue

**Problem:** Failed tasks disappear after max retries.

**Files:**
- Modify: `backend/app/tasks/celery_app.py`
- Create: `backend/app/tasks/error_handlers.py`

**Step 1: Create error handler with DLQ**

```python
# backend/app/tasks/error_handlers.py
"""
Celery task error handling with dead letter queue.

Failed tasks are preserved for investigation and manual retry.
"""
import json
from datetime import datetime, timezone

import structlog
from celery import Task
from celery.exceptions import MaxRetriesExceededError

logger = structlog.get_logger()

# Redis key for dead letter queue
DLQ_KEY = "celery:dead_letter_queue"


class TaskWithDLQ(Task):
    """
    Base task class that sends failed tasks to dead letter queue.

    Usage:
        @celery_app.task(base=TaskWithDLQ, max_retries=3)
        def my_task():
            ...
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails after all retries."""
        from app.core.config import settings
        import redis

        logger.error(
            "Task failed permanently",
            task_id=task_id,
            task_name=self.name,
            args=args,
            kwargs=kwargs,
            error=str(exc),
        )

        # Add to dead letter queue
        try:
            r = redis.from_url(settings.redis_url)

            dlq_entry = {
                "task_id": task_id,
                "task_name": self.name,
                "args": args,
                "kwargs": kwargs,
                "error": str(exc),
                "traceback": str(einfo),
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }

            r.lpush(DLQ_KEY, json.dumps(dlq_entry))
            r.ltrim(DLQ_KEY, 0, 999)  # Keep last 1000 failures

            logger.info("Task added to DLQ", task_id=task_id)

        except Exception as e:
            logger.error("Failed to add task to DLQ", error=str(e))

        super().on_failure(exc, task_id, args, kwargs, einfo)


def get_dlq_entries(limit: int = 100) -> list[dict]:
    """Get entries from dead letter queue."""
    from app.core.config import settings
    import redis

    r = redis.from_url(settings.redis_url)
    entries = r.lrange(DLQ_KEY, 0, limit - 1)
    return [json.loads(e) for e in entries]


def retry_dlq_entry(index: int) -> bool:
    """Retry a specific DLQ entry by index."""
    from app.core.config import settings
    from app.tasks.celery_app import celery_app
    import redis

    r = redis.from_url(settings.redis_url)
    entry_json = r.lindex(DLQ_KEY, index)

    if not entry_json:
        return False

    entry = json.loads(entry_json)
    task = celery_app.tasks.get(entry["task_name"])

    if not task:
        logger.error("Task not found for DLQ retry", task_name=entry["task_name"])
        return False

    # Resubmit task
    task.apply_async(args=entry["args"], kwargs=entry["kwargs"])

    # Remove from DLQ
    r.lrem(DLQ_KEY, 1, entry_json)

    logger.info("DLQ entry retried", task_id=entry["task_id"])
    return True
```

**Step 2: Update celery_app to use base class**

```python
# backend/app/tasks/celery_app.py
from app.tasks.error_handlers import TaskWithDLQ

celery_app = Celery(
    "mtg_market_intel",
    task_cls=TaskWithDLQ,  # Use DLQ-enabled base class
    # ... other config ...
)
```

**Step 3: Add admin endpoint to view DLQ**

```python
# backend/app/api/routes/admin.py
from app.tasks.error_handlers import get_dlq_entries, retry_dlq_entry

@router.get("/dlq", response_model=list[DLQEntry])
async def list_dead_letter_queue(
    limit: int = Query(100, le=1000),
    _: AdminUser = Depends(get_admin_user),
):
    """List failed tasks in dead letter queue."""
    return get_dlq_entries(limit)


@router.post("/dlq/{index}/retry")
async def retry_dead_letter(
    index: int,
    _: AdminUser = Depends(get_admin_user),
):
    """Retry a failed task from the dead letter queue."""
    success = retry_dlq_entry(index)
    if not success:
        raise HTTPException(404, "DLQ entry not found")
    return {"status": "retried"}
```

**Step 4: Commit**

```bash
git add backend/app/tasks/error_handlers.py backend/app/tasks/celery_app.py backend/app/api/routes/admin.py
git commit -m "feat: add dead letter queue for failed Celery tasks

- Create TaskWithDLQ base class for all tasks
- Failed tasks saved to Redis DLQ with full context
- Admin endpoints to view and retry DLQ entries
- Keeps last 1000 failures for investigation

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 15: Add Read Replica Support for Discord Bot

**Problem:** Discord bot queries can impact main database performance.

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/db/session.py`
- Modify: `backend/app/api/routes/bot.py`

**Step 1: Add replica URL to config**

```python
# backend/app/core/config.py
class Settings(BaseSettings):
    # ... existing settings ...

    # Database URLs
    database_url: str
    database_replica_url: Optional[str] = None  # Read replica for heavy queries
```

**Step 2: Create replica session maker**

```python
# backend/app/db/session.py
from app.core.config import settings

# Primary database (read-write)
engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

# Read replica (if configured)
replica_engine = None
replica_session_maker = None

if settings.database_replica_url:
    replica_engine = create_async_engine(
        settings.database_replica_url,
        echo=False,
        pool_pre_ping=True,
    )
    replica_session_maker = async_sessionmaker(
        replica_engine,
        expire_on_commit=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get primary database session."""
    async with async_session_maker() as session:
        yield session


async def get_replica_db() -> AsyncGenerator[AsyncSession, None]:
    """Get read replica session (falls back to primary if not configured)."""
    if replica_session_maker:
        async with replica_session_maker() as session:
            yield session
    else:
        async with async_session_maker() as session:
            yield session
```

**Step 3: Update bot routes to use replica**

```python
# backend/app/api/routes/bot.py
from app.db.session import get_replica_db

@router.get("/users/{user_id}/portfolio", response_model=PortfolioSummary)
async def get_user_portfolio(
    user_id: int,
    _: BotAuth,
    db: AsyncSession = Depends(get_replica_db),  # Use replica
):
    """Get portfolio summary - uses read replica if available."""
    # ... implementation unchanged ...
```

**Step 4: Document configuration**

```markdown
# .env.example update
# Read replica for Discord bot (optional)
DATABASE_REPLICA_URL=postgresql+asyncpg://user:pass@replica-host:5432/db
```

**Step 5: Commit**

```bash
git add backend/app/core/config.py backend/app/db/session.py backend/app/api/routes/bot.py
git commit -m "feat: add read replica support for Discord bot

- Add DATABASE_REPLICA_URL config option
- Create get_replica_db dependency
- Bot endpoints use replica if configured
- Falls back to primary if no replica

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Phase 5: Testing & Observability

### Task 16: Add PostgreSQL Test Container

**Problem:** Integration tests skip on SQLite, missing PostgreSQL-specific issues.

**Files:**
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/integration/conftest.py`
- Modify: `docker-compose.test.yml`

**Step 1: Create test-specific docker-compose**

```yaml
# docker-compose.test.yml
version: "3.8"

services:
  test-db:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_pass
      POSTGRES_DB: test_db
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user -d test_db"]
      interval: 5s
      timeout: 5s
      retries: 5
```

**Step 2: Create integration test conftest**

```python
# backend/tests/integration/conftest.py
"""
Fixtures for integration tests that require PostgreSQL.
"""
import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Integration tests require PostgreSQL
INTEGRATION_DB_URL = os.getenv(
    "INTEGRATION_DATABASE_URL",
    "postgresql+asyncpg://test_user:test_pass@localhost:5433/test_db"
)


@pytest.fixture(scope="session")
def integration_db_url():
    """Get integration test database URL."""
    return INTEGRATION_DB_URL


@pytest_asyncio.fixture(scope="function")
async def pg_engine(integration_db_url):
    """Create PostgreSQL engine for integration tests."""
    engine = create_async_engine(integration_db_url, echo=False)

    # Create tables
    from app.db.base import Base
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def pg_session(pg_engine) -> AsyncSession:
    """Create PostgreSQL session for integration tests."""
    session_maker = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session
        await session.rollback()
```

**Step 3: Update integration tests to use new fixtures**

```python
# backend/tests/integration/test_composite_keys.py
# Remove the skipif and use pg_session fixture

@pytest.mark.integration
class TestCompositeKeyInsert:
    async def test_insert_single_snapshot(self, pg_session):
        """Test inserting a single price snapshot."""
        # ... test using pg_session ...
```

**Step 4: Add pytest marker and CI script**

```ini
# backend/pytest.ini
[pytest]
markers =
    integration: marks tests as integration tests (require PostgreSQL)
```

```bash
# scripts/run-integration-tests.sh
#!/bin/bash
set -e

# Start test database
docker compose -f docker-compose.test.yml up -d test-db

# Wait for database
echo "Waiting for test database..."
sleep 5

# Run integration tests
INTEGRATION_DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5433/test_db" \
    pytest tests/integration -v -m integration

# Cleanup
docker compose -f docker-compose.test.yml down
```

**Step 5: Commit**

```bash
git add docker-compose.test.yml backend/tests/integration/conftest.py backend/pytest.ini scripts/
git commit -m "feat: add PostgreSQL test container for integration tests

- Add docker-compose.test.yml with TimescaleDB
- Create integration test fixtures with pg_session
- Add 'integration' pytest marker
- Add run-integration-tests.sh script

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 17: Add Load Testing with k6

**Problem:** No performance baselines or load testing.

**Files:**
- Create: `backend/tests/load/cards_search.js`
- Create: `backend/tests/load/market_overview.js`
- Create: `scripts/run-load-tests.sh`

**Step 1: Create k6 test for card search**

```javascript
// backend/tests/load/cards_search.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const searchDuration = new Trend('search_duration');

export const options = {
  stages: [
    { duration: '30s', target: 10 },   // Ramp up
    { duration: '1m', target: 50 },    // Steady state
    { duration: '30s', target: 100 },  // Peak
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% under 500ms
    errors: ['rate<0.01'],              // <1% errors
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const SEARCH_TERMS = ['lightning', 'bolt', 'counterspell', 'black lotus', 'force of will'];

export default function () {
  const term = SEARCH_TERMS[Math.floor(Math.random() * SEARCH_TERMS.length)];

  const res = http.get(`${BASE_URL}/api/cards/search?q=${term}&limit=20`);

  searchDuration.add(res.timings.duration);

  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'has results': (r) => JSON.parse(r.body).cards.length > 0,
  });

  errorRate.add(!success);

  sleep(1);
}
```

**Step 2: Create k6 test for market overview**

```javascript
// backend/tests/load/market_overview.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 100 },
    { duration: '2m', target: 100 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000'],  // Market overview can be slower
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  const res = http.get(`${BASE_URL}/api/market/overview`);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'has metrics': (r) => {
      const body = JSON.parse(r.body);
      return body.totalCardsTracked > 0;
    },
  });

  sleep(2);
}
```

**Step 3: Create run script**

```bash
#!/bin/bash
# scripts/run-load-tests.sh

set -e

BASE_URL=${BASE_URL:-"http://localhost:8000"}

echo "Running load tests against $BASE_URL"
echo "=================================="

echo "\n[1/2] Card Search Load Test"
k6 run --env BASE_URL=$BASE_URL backend/tests/load/cards_search.js

echo "\n[2/2] Market Overview Load Test"
k6 run --env BASE_URL=$BASE_URL backend/tests/load/market_overview.js

echo "\n=================================="
echo "Load tests complete!"
```

**Step 4: Document performance baselines**

```markdown
# docs/performance-baselines.md

# Performance Baselines

Last updated: 2026-01-11

## Test Environment
- Database: PostgreSQL 15 + TimescaleDB
- Cards in database: ~100,000
- Price snapshots: ~275,000

## API Latency (p95)

| Endpoint | Target | Baseline |
|----------|--------|----------|
| GET /cards/search | <500ms | TBD |
| GET /market/overview | <1000ms | TBD |
| GET /cards/{id} | <200ms | TBD |
| GET /inventory | <500ms | TBD |

## Throughput

| Endpoint | Target RPS | Baseline |
|----------|------------|----------|
| Card search | 100 | TBD |
| Market overview | 50 | TBD |

Run `scripts/run-load-tests.sh` to update baselines.
```

**Step 5: Commit**

```bash
git add backend/tests/load/ scripts/run-load-tests.sh docs/performance-baselines.md
git commit -m "feat: add k6 load tests with performance baselines

- Add card search load test
- Add market overview load test
- Document target latency and throughput
- Add run-load-tests.sh script

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 18: Add Distributed Tracing

**Problem:** Hard to debug latency issues across services.

**Files:**
- Create: `backend/app/core/tracing.py`
- Modify: `backend/app/main.py`

**Step 1: Create tracing configuration**

```python
# backend/app/core/tracing.py
"""
Distributed tracing with OpenTelemetry.

Traces requests across API, database, Redis, and Celery.
"""
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import settings


def setup_tracing(app):
    """
    Configure OpenTelemetry tracing for the application.

    Requires OTLP_ENDPOINT env var for exporting traces.
    """
    if not settings.otlp_endpoint:
        return  # Tracing disabled

    # Configure resource
    resource = Resource.create({
        "service.name": "mtg-market-intel",
        "service.version": "1.0.0",
        "deployment.environment": settings.environment,
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Configure exporter
    exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    # Set as global provider
    trace.set_tracer_provider(provider)

    # Instrument libraries
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument()
    RedisInstrumentor().instrument()
    CeleryInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
```

**Step 2: Add to main.py**

```python
# backend/app/main.py
from app.core.tracing import setup_tracing

app = FastAPI(...)

# Setup tracing (no-op if OTLP_ENDPOINT not configured)
setup_tracing(app)
```

**Step 3: Add config**

```python
# backend/app/core/config.py
class Settings(BaseSettings):
    # ... existing ...

    # Tracing
    otlp_endpoint: Optional[str] = None  # e.g., "http://jaeger:4317"
    environment: str = "development"
```

**Step 4: Document setup**

```markdown
# docs/tracing.md

# Distributed Tracing Setup

## Local Development (Jaeger)

```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest
```

Then set in `.env`:
```
OTLP_ENDPOINT=http://localhost:4317
```

View traces at http://localhost:16686

## Production

Configure OTLP_ENDPOINT to your tracing backend (Jaeger, Tempo, etc.)
```

**Step 5: Commit**

```bash
git add backend/app/core/tracing.py backend/app/main.py docs/tracing.md requirements.txt
git commit -m "feat: add OpenTelemetry distributed tracing

- Configure tracing for FastAPI, SQLAlchemy, Redis, Celery, httpx
- Export to OTLP-compatible backends (Jaeger, Tempo, etc.)
- Disabled by default (set OTLP_ENDPOINT to enable)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 19: Add Health Check Dashboard Endpoint

**Problem:** No comprehensive health status for monitoring.

**Files:**
- Create: `backend/app/api/routes/health_detailed.py`

**Step 1: Create detailed health endpoint**

```python
# backend/app/api/routes/health_detailed.py
"""
Detailed health check endpoint for monitoring dashboards.

Checks all dependencies and returns detailed status.
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_redis

router = APIRouter(tags=["health"])


class DependencyHealth(BaseModel):
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    latency_ms: float
    message: Optional[str] = None


class DetailedHealthResponse(BaseModel):
    status: str
    timestamp: datetime
    uptime_seconds: float
    dependencies: list[DependencyHealth]


# Track startup time
_startup_time = time.time()


async def check_database(db: AsyncSession) -> DependencyHealth:
    """Check database connectivity."""
    start = time.time()
    try:
        await db.execute(text("SELECT 1"))
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="database",
            status="healthy" if latency < 100 else "degraded",
            latency_ms=latency,
        )
    except Exception as e:
        return DependencyHealth(
            name="database",
            status="unhealthy",
            latency_ms=-1,
            message=str(e),
        )


async def check_redis(redis) -> DependencyHealth:
    """Check Redis connectivity."""
    start = time.time()
    try:
        await redis.ping()
        latency = (time.time() - start) * 1000
        return DependencyHealth(
            name="redis",
            status="healthy" if latency < 50 else "degraded",
            latency_ms=latency,
        )
    except Exception as e:
        return DependencyHealth(
            name="redis",
            status="unhealthy",
            latency_ms=-1,
            message=str(e),
        )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
):
    """
    Detailed health check for monitoring.

    Checks all dependencies and returns latency metrics.
    """
    # Check dependencies in parallel
    db_health, redis_health = await asyncio.gather(
        check_database(db),
        check_redis(redis),
    )

    dependencies = [db_health, redis_health]

    # Determine overall status
    if any(d.status == "unhealthy" for d in dependencies):
        overall_status = "unhealthy"
    elif any(d.status == "degraded" for d in dependencies):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return DetailedHealthResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=time.time() - _startup_time,
        dependencies=dependencies,
    )
```

**Step 2: Register route**

```python
# backend/app/api/__init__.py
from app.api.routes.health_detailed import router as health_detailed_router

api_router.include_router(health_detailed_router)
```

**Step 3: Commit**

```bash
git add backend/app/api/routes/health_detailed.py
git commit -m "feat: add detailed health check endpoint

- Check database and Redis connectivity
- Report latency metrics per dependency
- Classify status as healthy/degraded/unhealthy
- Track uptime for monitoring

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Summary

| Phase | Tasks | Estimated Effort |
|-------|-------|-----------------|
| 1: Data Integrity | 3 | Medium |
| 2: Security | 4 | Medium |
| 3: Performance | 5 | High |
| 4: Reliability | 3 | Medium |
| 5: Testing | 4 | Medium |

**Total: 19 tasks**

### Execution Order

**Week 1: Critical fixes**
- Task 1: Listing migration
- Task 2: Transaction boundaries
- Task 3: Redis singleton

**Week 2: Security**
- Task 4: Enumeration protection
- Task 5: File validation
- Task 6: Token revocation
- Task 7: API contract fix

**Week 3: Performance**
- Task 8: Cursor pagination
- Task 9: N+1 queries
- Task 10: Query optimization
- Task 11: PriceSnapshot analysis
- Task 12: Backpressure

**Week 4: Reliability & Testing**
- Task 13: Circuit breaker
- Task 14: Dead letter queue
- Task 15: Read replica
- Task 16: PostgreSQL tests
- Task 17: Load testing
- Task 18: Tracing
- Task 19: Health checks

---

**Plan complete and saved to `docs/plans/2026-01-11-architecture-remediation-plan.md`.**

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
