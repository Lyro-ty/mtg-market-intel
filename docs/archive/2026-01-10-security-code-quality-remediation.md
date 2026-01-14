# Security & Code Quality Remediation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical security vulnerabilities, edge cases, and code quality issues identified in the security audit.

**Architecture:** Phase-based remediation starting with critical security fixes, then edge cases, then code quality. Each fix includes tests and follows fail-secure principles.

**Tech Stack:** FastAPI, SQLAlchemy, Redis, React/TypeScript, pytest

---

## Phase 1: Critical Security Fixes

### Task 1: Rate Limiting - Fail Closed on Redis Failure

**Files:**
- Modify: `backend/app/middleware/rate_limit.py:78-80`
- Create: `backend/tests/test_rate_limit.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_rate_limit.py
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.middleware.rate_limit import RateLimitMiddleware


@pytest.fixture
def test_app():
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        redis_url="redis://localhost:6379/0",
        requests_per_minute=60,
        auth_requests_per_minute=5,
    )

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    return app


def test_rate_limit_fails_closed_on_redis_error(test_app):
    """Rate limiting should deny requests when Redis is unavailable."""
    with patch.object(
        RateLimitMiddleware,
        'get_redis',
        side_effect=Exception("Redis connection failed")
    ):
        client = TestClient(test_app)
        response = client.get("/test")

        # Should return 503 Service Unavailable, NOT 200
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"].lower()
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/test_rate_limit.py::test_rate_limit_fails_closed_on_redis_error -v`
Expected: FAIL - currently returns 200 (fails open)

**Step 3: Implement fail-closed rate limiting**

```python
# backend/app/middleware/rate_limit.py - Replace lines 63-83
        try:
            r = await self.get_redis()
            # Use pipelining to avoid race condition between INCR and EXPIRE
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)
            results = await pipe.execute()
            current = results[0]

            if current > limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."},
                    headers={"Retry-After": "60"},
                )
        except redis.RedisError as e:
            # SECURITY: Fail closed - deny request if rate limiting unavailable
            # This prevents brute force attacks when Redis is down
            import structlog
            logger = structlog.get_logger()
            logger.error("Rate limiting unavailable - denying request", error=str(e))
            return JSONResponse(
                status_code=503,
                content={"detail": "Service temporarily unavailable. Please try again later."},
                headers={"Retry-After": "30"},
            )
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/test_rate_limit.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/middleware/rate_limit.py backend/tests/test_rate_limit.py
git commit -m "$(cat <<'EOF'
fix(security): rate limiting fails closed when Redis unavailable

Previously rate limiting would fail open, allowing unlimited requests
when Redis was unavailable. This created a security vulnerability
where attackers could brute force credentials by taking down Redis.

Now returns 503 Service Unavailable when rate limiting is unavailable.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Token Blacklist - Remove Unsafe In-Memory Fallback

**Files:**
- Modify: `backend/app/core/token_blacklist.py`
- Create: `backend/tests/test_token_blacklist.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_token_blacklist.py
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.core.token_blacklist import TokenBlacklist


def test_blacklist_fails_when_redis_unavailable():
    """Token blacklist should return False (not blacklisted) is UNSAFE when Redis fails.
    Instead, we should fail secure by returning True (treat as blacklisted)."""
    blacklist = TokenBlacklist()

    # Force Redis to fail
    with patch.object(blacklist, '_get_redis', return_value=None):
        # Try to add a token
        jti = "test-token-123"
        expires = datetime.now(timezone.utc) + timedelta(hours=1)

        # Add should indicate failure
        result = blacklist.add(jti, expires)
        assert result is False, "add() should return False when Redis unavailable"

        # is_blacklisted should fail-secure (assume blacklisted when unsure)
        result = blacklist.is_blacklisted(jti)
        assert result is True, "is_blacklisted() should return True when Redis unavailable (fail secure)"
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/test_token_blacklist.py::test_blacklist_fails_when_redis_unavailable -v`
Expected: FAIL - currently uses in-memory fallback

**Step 3: Implement fail-secure token blacklist**

```python
# backend/app/core/token_blacklist.py - Full replacement
"""
Token blacklist for secure JWT invalidation.

Implements a Redis-based token blacklist. When Redis is unavailable,
operations fail secure - tokens are treated as potentially blacklisted.
"""
import structlog
from datetime import datetime, timezone
from typing import Optional

import redis

from app.core.config import settings

logger = structlog.get_logger()


class TokenBlacklist:
    """
    Token blacklist implementation using Redis.

    SECURITY: No in-memory fallback. When Redis is unavailable:
    - add() returns False (failed to blacklist)
    - is_blacklisted() returns True (fail secure - assume token invalid)
    """

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._initialized = False
        self._redis_available = False

    def _get_redis(self) -> Optional[redis.Redis]:
        """Get Redis connection, initializing if needed."""
        if self._initialized:
            return self._redis if self._redis_available else None

        try:
            self._redis = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            # Test connection
            self._redis.ping()
            self._redis_available = True
            logger.info("Token blacklist connected to Redis")
        except Exception as e:
            logger.error(
                "Token blacklist Redis connection failed - tokens will be treated as invalid",
                error=str(e)
            )
            self._redis = None
            self._redis_available = False

        self._initialized = True
        return self._redis if self._redis_available else None

    def add(self, jti: str, expires_at: datetime) -> bool:
        """
        Add a token JTI to the blacklist.

        Args:
            jti: JWT ID (unique token identifier)
            expires_at: Token expiration time

        Returns:
            True if successfully blacklisted, False if failed
        """
        # Calculate TTL
        now = datetime.now(timezone.utc)
        ttl_seconds = int((expires_at - now).total_seconds())

        if ttl_seconds <= 0:
            # Token already expired, no need to blacklist
            return True

        redis_client = self._get_redis()
        if not redis_client:
            logger.warning("Cannot blacklist token - Redis unavailable", jti=jti)
            return False

        try:
            key = f"token_blacklist:{jti}"
            redis_client.setex(key, ttl_seconds, "1")
            logger.debug("Token blacklisted in Redis", jti=jti, ttl=ttl_seconds)
            return True
        except Exception as e:
            logger.error("Failed to blacklist token in Redis", error=str(e), jti=jti)
            return False

    def is_blacklisted(self, jti: str) -> bool:
        """
        Check if a token JTI is blacklisted.

        SECURITY: Fails secure - if Redis unavailable, returns True
        (assumes token is blacklisted to prevent unauthorized access).

        Args:
            jti: JWT ID to check

        Returns:
            True if token is blacklisted OR if check failed (fail secure)
        """
        redis_client = self._get_redis()
        if not redis_client:
            # SECURITY: Fail secure - treat as blacklisted when we can't verify
            logger.warning(
                "Cannot verify token blacklist status - Redis unavailable, treating as blacklisted",
                jti=jti
            )
            return True

        try:
            key = f"token_blacklist:{jti}"
            return redis_client.exists(key) > 0
        except Exception as e:
            # SECURITY: Fail secure on error
            logger.warning(
                "Failed to check Redis blacklist - treating as blacklisted",
                error=str(e),
                jti=jti
            )
            return True


# Global blacklist instance
_token_blacklist = TokenBlacklist()


def get_token_blacklist() -> TokenBlacklist:
    """Get the token blacklist instance."""
    return _token_blacklist
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/test_token_blacklist.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/token_blacklist.py backend/tests/test_token_blacklist.py
git commit -m "$(cat <<'EOF'
fix(security): remove unsafe in-memory token blacklist fallback

BREAKING: Token blacklist no longer has in-memory fallback.

When Redis is unavailable:
- add() returns False (blacklist failed)
- is_blacklisted() returns True (fail secure)

This prevents session fixation where logged-out tokens could still
be used on workers that hadn't received the blacklist update.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: OAuth URL Encoding Fix

**Files:**
- Modify: `backend/app/api/routes/oauth.py:56`
- Test: `backend/tests/test_oauth.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_oauth.py
import pytest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from app.main import app


def test_google_oauth_url_properly_encoded():
    """OAuth URLs should use proper URL encoding for special characters."""
    with patch('app.api.routes.oauth.settings') as mock_settings:
        mock_settings.OAUTH_ENABLED = True
        mock_settings.GOOGLE_CLIENT_ID = "test+client&id=special"
        mock_settings.GOOGLE_REDIRECT_URI = "http://localhost/callback?extra=param"
        mock_settings.redis_url = "redis://localhost:6379/0"

        with patch('app.api.routes.oauth.get_redis') as mock_redis:
            mock_redis.return_value = MagicMock()

            client = TestClient(app, follow_redirects=False)
            response = client.get("/api/oauth/google/login")

            assert response.status_code == 307
            location = response.headers["location"]

            # Parse the URL and verify encoding
            parsed = urlparse(location)
            params = parse_qs(parsed.query)

            # The client_id should be properly encoded
            # With improper encoding, & would break the URL
            assert "client_id" in params
            assert params["client_id"][0] == "test+client&id=special"
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/test_oauth.py::test_google_oauth_url_properly_encoded -v`
Expected: FAIL - URL params not properly encoded

**Step 3: Fix OAuth URL encoding**

```python
# backend/app/api/routes/oauth.py - Replace line 56
    # Line 55-58: Replace manual string building with urlencode
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    query_string = urlencode(params)  # Use imported urlencode instead of manual join

    return RedirectResponse(url=f"{auth_url}?{query_string}")
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/test_oauth.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/api/routes/oauth.py backend/tests/test_oauth.py
git commit -m "$(cat <<'EOF'
fix(security): use urlencode for OAuth URL parameters

urlencode was imported but not used. Special characters in OAuth
parameters could break authentication or enable injection.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Fix Bare except Clause

**Files:**
- Modify: `backend/app/api/routes/portfolio.py:271`

**Step 1: Identify the issue**

The bare `except:` at line 271 catches everything including KeyboardInterrupt and SystemExit.

**Step 2: Fix with specific exception**

```python
# backend/app/api/routes/portfolio.py - Replace line 271
            except (json.JSONDecodeError, TypeError, KeyError):
                legalities = {}
```

**Step 3: Run existing tests**

Run: `docker compose exec backend pytest tests/ -k portfolio -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/api/routes/portfolio.py
git commit -m "$(cat <<'EOF'
fix: replace bare except with specific exceptions in portfolio

Bare except: catches KeyboardInterrupt, SystemExit, and memory errors
which hides bugs and prevents proper cleanup.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Implement Refresh Token Rotation

**Files:**
- Modify: `backend/app/services/auth.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/api/routes/auth.py`
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/test_refresh_tokens.py`

**Step 1: Add config settings**

```python
# backend/app/core/config.py - Add after line 28
    jwt_access_token_expire_minutes: int = 15  # Short-lived access tokens
    jwt_refresh_token_expire_days: int = 7  # Longer-lived refresh tokens
```

**Step 2: Add refresh token schema**

```python
# backend/app/schemas/auth.py - Add new schemas
class RefreshTokenRequest(BaseModel):
    """Request to refresh access token."""
    refresh_token: str


class TokenResponse(BaseModel):
    """Response containing both access and refresh tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires
```

**Step 3: Implement refresh token creation and validation**

```python
# backend/app/services/auth.py - Add new functions

def create_refresh_token(user_id: int) -> str:
    """
    Create a refresh token for token rotation.

    Refresh tokens are longer-lived and used only to get new access tokens.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    jti = str(uuid.uuid4())

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "refresh",
    }

    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_refresh_token(token: str) -> Optional[TokenPayload]:
    """
    Decode and validate a refresh token.

    Returns None if invalid or if it's not a refresh token type.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)

        if token_data.type != "refresh":
            logger.warning("Token is not a refresh token", token_type=token_data.type)
            return None

        # Check if refresh token is blacklisted
        if token_data.jti:
            blacklist = get_token_blacklist()
            if blacklist.is_blacklisted(token_data.jti):
                logger.warning("Refresh token is blacklisted", jti=token_data.jti)
                return None

        return token_data
    except JWTError as e:
        logger.warning("Refresh token decode error", error=str(e))
        return None


def create_token_pair(user_id: int) -> tuple[str, str, int]:
    """
    Create an access/refresh token pair.

    Returns:
        Tuple of (access_token, refresh_token, expires_in_seconds)
    """
    access_token = create_access_token(
        user_id,
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    refresh_token = create_refresh_token(user_id)
    expires_in = settings.jwt_access_token_expire_minutes * 60

    return access_token, refresh_token, expires_in
```

**Step 4: Add refresh endpoint**

```python
# backend/app/api/routes/auth.py - Add new endpoint

@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a refresh token for a new access/refresh token pair.

    The old refresh token is blacklisted to prevent reuse (rotation).
    """
    token_data = decode_refresh_token(request.refresh_token)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Verify user still exists and is active
    user_id = int(token_data.sub)
    user = await get_user_by_id(db, user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Blacklist the old refresh token (rotation)
    blacklist_token(request.refresh_token)

    # Create new token pair
    access_token, refresh_token, expires_in = create_token_pair(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )
```

**Step 5: Update login endpoint to return token pair**

```python
# backend/app/api/routes/auth.py - Modify login endpoint response
    # Replace single token creation with token pair
    access_token, refresh_token, expires_in = create_token_pair(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )
```

**Step 6: Write tests**

```python
# backend/tests/test_refresh_tokens.py
import pytest
from datetime import datetime, timezone, timedelta

from app.services.auth import (
    create_token_pair,
    decode_refresh_token,
    blacklist_token,
)


def test_create_token_pair_returns_both_tokens():
    """Token pair should include access and refresh tokens."""
    access, refresh, expires_in = create_token_pair(user_id=123)

    assert access is not None
    assert refresh is not None
    assert expires_in > 0
    assert access != refresh


def test_refresh_token_has_correct_type():
    """Refresh token should have type='refresh'."""
    _, refresh, _ = create_token_pair(user_id=123)
    payload = decode_refresh_token(refresh)

    assert payload is not None
    assert payload.type == "refresh"


def test_blacklisted_refresh_token_rejected():
    """Blacklisted refresh tokens should be rejected."""
    _, refresh, _ = create_token_pair(user_id=123)

    # Token should be valid initially
    assert decode_refresh_token(refresh) is not None

    # Blacklist it
    blacklist_token(refresh)

    # Now it should be rejected
    assert decode_refresh_token(refresh) is None
```

**Step 7: Run tests**

Run: `docker compose exec backend pytest tests/test_refresh_tokens.py -v`
Expected: PASS

**Step 8: Commit**

```bash
git add backend/app/services/auth.py backend/app/schemas/auth.py \
    backend/app/api/routes/auth.py backend/app/core/config.py \
    backend/tests/test_refresh_tokens.py
git commit -m "$(cat <<'EOF'
feat(security): implement refresh token rotation

- Access tokens now expire in 15 minutes (was 24 hours)
- Refresh tokens valid for 7 days
- Refresh tokens are rotated on use (old one blacklisted)
- Login returns both access and refresh tokens

This limits the window for stolen token abuse and enables
detection of token theft through rotation.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Phase 2: Edge Cases & Input Validation

### Task 6: Search Input Length Validation

**Files:**
- Modify: `backend/app/api/routes/inventory.py`
- Modify: `backend/app/api/routes/cards.py` (search endpoints)

**Step 1: Add validation constants**

```python
# backend/app/core/constants.py (create new file)
"""Application-wide constants."""

# Input validation limits
MAX_SEARCH_LENGTH = 200  # Maximum characters for search queries
MAX_IDS_PER_REQUEST = 500  # Maximum IDs in .in_() queries
MAX_PAGE_SIZE = 100  # Maximum items per page
```

**Step 2: Add search validation to inventory**

```python
# backend/app/api/routes/inventory.py - Add after line 385 (search parameter)
    # Validate search input
    if search:
        if len(search) > MAX_SEARCH_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Search query too long. Maximum {MAX_SEARCH_LENGTH} characters.",
            )
        # Escape SQL wildcard characters in user input
        search = search.replace("%", r"\%").replace("_", r"\_")
```

**Step 3: Commit**

```bash
git add backend/app/core/constants.py backend/app/api/routes/inventory.py
git commit -m "$(cat <<'EOF'
fix: add search input length validation

Prevents DoS via megabyte-long search strings and SQL wildcard abuse.
Search queries limited to 200 characters with wildcards escaped.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Fix Frontend .toFixed() Null Checks

**Files:**
- Modify: Multiple frontend files (see grep results)

**Step 1: Create safe formatting utility**

```typescript
// frontend/src/lib/format.ts
/**
 * Safely format a number with toFixed, returning fallback for null/undefined.
 */
export function safeToFixed(
  value: number | null | undefined,
  decimals: number = 2,
  fallback: string = '-'
): string {
  if (value === null || value === undefined || isNaN(value)) {
    return fallback;
  }
  return value.toFixed(decimals);
}

/**
 * Format a percentage value safely.
 */
export function formatPercent(
  value: number | null | undefined,
  decimals: number = 1,
  includeSign: boolean = false
): string {
  if (value === null || value === undefined || isNaN(value)) {
    return '-';
  }
  const sign = includeSign && value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Format a currency value safely.
 */
export function formatCurrency(
  value: number | null | undefined,
  decimals: number = 2
): string {
  if (value === null || value === undefined || isNaN(value)) {
    return '-';
  }
  return `$${value.toFixed(decimals)}`;
}
```

**Step 2: Update components to use safe formatters**

Example fix for `frontend/src/app/(protected)/spreads/page.tsx:94`:

```typescript
// Before:
{opportunity.spread_pct.toFixed(1)}% spread

// After:
{formatPercent(opportunity.spread_pct, 1)} spread
```

**Step 3: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No new errors

**Step 4: Commit**

```bash
git add frontend/src/lib/format.ts frontend/src/app/ frontend/src/components/
git commit -m "$(cat <<'EOF'
fix: add null checks for toFixed calls in frontend

Created safe formatting utilities (safeToFixed, formatPercent, formatCurrency)
that handle null/undefined values gracefully.

Prevents "Cannot read property 'toFixed' of null" runtime errors.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Fix Auto-Commit on Session Close

**Files:**
- Modify: `backend/app/db/session.py`

**Step 1: Remove auto-commit**

```python
# backend/app/db/session.py - Replace get_db function
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.

    IMPORTANT: This does NOT auto-commit. Routes must explicitly commit.
    On exception, the session is rolled back.
    """
    async with async_session_maker() as session:
        try:
            yield session
            # NOTE: No auto-commit - routes must explicitly call await db.commit()
        except Exception as e:
            await session.rollback()
            logger.error(
                "Database session error - rolled back",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
```

**Step 2: Audit routes for missing commits**

Run grep to find routes that modify data but may not commit:
```bash
grep -r "db.add\|db.delete" backend/app/api/routes/ | grep -v "db.commit"
```

**Step 3: Add commits where needed**

Each route that adds/deletes should have explicit `await db.commit()`.

**Step 4: Commit**

```bash
git add backend/app/db/session.py
git commit -m "$(cat <<'EOF'
fix: remove auto-commit from database session dependency

Auto-commit on session close caused unintended writes when routes
only meant to read data but accidentally modified objects.

Routes must now explicitly call db.commit() to persist changes.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Fix Redis Singleton Race Condition

**Files:**
- Modify: `backend/app/api/deps.py`

**Step 1: Implement thread-safe singleton with connection pool**

```python
# backend/app/api/deps.py - Replace Redis singleton code (lines 119-132)
import asyncio
from redis.asyncio import ConnectionPool, Redis

# Redis connection pool and client
_redis_pool: ConnectionPool | None = None
_redis_client: Redis | None = None
_redis_lock = asyncio.Lock()


async def get_redis() -> Redis:
    """
    Get the async Redis client with connection pooling.

    Thread-safe initialization using asyncio.Lock.
    """
    global _redis_pool, _redis_client

    if _redis_client is not None:
        return _redis_client

    async with _redis_lock:
        # Double-check after acquiring lock
        if _redis_client is not None:
            return _redis_client

        _redis_pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
        _redis_client = Redis(connection_pool=_redis_pool)

    return _redis_client


async def close_redis() -> None:
    """Close Redis connections on shutdown."""
    global _redis_pool, _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
    if _redis_pool:
        await _redis_pool.disconnect()
        _redis_pool = None
```

**Step 2: Register shutdown handler in main.py**

```python
# backend/app/main.py - Add to shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    from app.api.deps import close_redis
    await close_redis()
```

**Step 3: Commit**

```bash
git add backend/app/api/deps.py backend/app/main.py
git commit -m "$(cat <<'EOF'
fix: thread-safe Redis singleton with connection pooling

- Use asyncio.Lock to prevent race condition during initialization
- Configure connection pool (max 20 connections)
- Add proper shutdown cleanup

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Add Limits to .in_() Queries

**Files:**
- Modify: Routes that accept unbounded ID lists
- Create: `backend/app/api/utils/validation.py`

**Step 1: Create validation utility**

```python
# backend/app/api/utils/validation.py
from fastapi import HTTPException, status
from typing import List, TypeVar

from app.core.constants import MAX_IDS_PER_REQUEST

T = TypeVar('T')


def validate_id_list(ids: List[T], param_name: str = "ids") -> List[T]:
    """
    Validate that an ID list doesn't exceed the maximum allowed.

    Raises HTTPException 400 if too many IDs provided.
    """
    if len(ids) > MAX_IDS_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many {param_name}. Maximum {MAX_IDS_PER_REQUEST} allowed.",
        )
    return ids
```

**Step 2: Apply to routes accepting ID lists**

Example for `backend/app/api/routes/quotes.py:589`:

```python
# Before:
TradingPost.id.in_(data.trading_post_ids)

# After:
validate_id_list(data.trading_post_ids, "trading_post_ids")
# ... then use in query
TradingPost.id.in_(data.trading_post_ids)
```

**Step 3: Commit**

```bash
git add backend/app/api/utils/validation.py backend/app/api/routes/
git commit -m "$(cat <<'EOF'
fix: add limits to .in_() queries to prevent DoS

Users could pass 100,000+ IDs causing database performance issues.
Now limited to 500 IDs per request.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: IDOR Audit and Fixes

**Files:**
- Audit: All routes with `db.get(Model, user_provided_id)`
- Fix: Routes missing ownership verification

**Step 1: Create ownership verification utilities**

```python
# backend/app/api/utils/ownership.py
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User


async def verify_ownership(
    db: AsyncSession,
    model_class,
    item_id: int,
    user: User,
    user_id_field: str = "user_id",
) -> any:
    """
    Fetch an item and verify the current user owns it.

    Raises 404 if not found or not owned by user.
    Returns the item if ownership verified.
    """
    item = await db.get(model_class, item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    if getattr(item, user_id_field) != user.id:
        # Return 404 to not leak existence of other users' items
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    return item
```

**Step 2: Audit routes (document findings)**

Routes to audit:
- `/api/inventory/{item_id}` - Has ownership check
- `/api/want-list/{item_id}` - Needs audit
- `/api/quotes/{quote_id}` - Needs audit
- `/api/imports/{job_id}` - Needs audit

**Step 3: Apply fixes where needed**

**Step 4: Commit**

```bash
git add backend/app/api/utils/ownership.py backend/app/api/routes/
git commit -m "$(cat <<'EOF'
fix(security): add ownership verification to prevent IDOR

Created verify_ownership utility and applied to routes that
access user-owned resources by ID.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: File Upload Content-Type Validation

**Files:**
- Modify: `backend/app/api/routes/imports.py`

**Step 1: Add MIME type validation**

```python
# backend/app/api/routes/imports.py - Add after line 96 (filename check)
    # Validate content type
    allowed_content_types = [
        "text/csv",
        "text/plain",
        "application/csv",
        "application/vnd.ms-excel",
    ]

    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Expected CSV, got {file.content_type}",
        )

    # Additional magic bytes check for CSV (should start with printable chars)
    content = await file.read()
    await file.seek(0)  # Reset file pointer

    # Check first 1KB for non-printable characters (except common whitespace)
    sample = content[:1024]
    try:
        sample.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File contains invalid characters. Must be UTF-8 text.",
        )
```

**Step 2: Commit**

```bash
git add backend/app/api/routes/imports.py
git commit -m "$(cat <<'EOF'
fix: add content-type validation for file uploads

Validates MIME type and checks for UTF-8 encoding to prevent
upload of malicious binary files.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Phase 3: Code Quality

### Task 13: Add Request ID Correlation

**Files:**
- Create: `backend/app/middleware/request_id.py`
- Modify: `backend/app/main.py`

**Step 1: Create request ID middleware**

```python
# backend/app/middleware/request_id.py
"""Request ID middleware for distributed tracing."""
import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import structlog


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request for tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Use X-Request-ID header if provided, otherwise generate
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Store in request state for access in routes
        request.state.request_id = request_id

        response = await call_next(request)

        # Add to response headers
        response.headers["X-Request-ID"] = request_id

        return response
```

**Step 2: Register middleware in main.py**

```python
# backend/app/main.py - Add before other middleware
from app.middleware.request_id import RequestIdMiddleware
app.add_middleware(RequestIdMiddleware)
```

**Step 3: Commit**

```bash
git add backend/app/middleware/request_id.py backend/app/main.py
git commit -m "$(cat <<'EOF'
feat: add request ID middleware for distributed tracing

Each request gets a unique ID (or uses X-Request-ID header).
ID is bound to structlog context and returned in response headers.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: Centralize Timeout Configuration

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: Files with hardcoded timeouts

**Step 1: Add timeout settings to config**

```python
# backend/app/core/config.py - Add timeout settings
    # Timeouts (in seconds)
    db_query_timeout: int = 25
    redis_socket_timeout: int = 5
    external_api_timeout: int = 30
    celery_task_timeout: int = 300
```

**Step 2: Replace hardcoded timeouts**

Find and replace hardcoded values with `settings.db_query_timeout`, etc.

**Step 3: Commit**

```bash
git add backend/app/core/config.py backend/app/
git commit -m "$(cat <<'EOF'
refactor: centralize timeout configuration

Moved hardcoded timeouts to config.py for easier tuning:
- db_query_timeout: 25s
- redis_socket_timeout: 5s
- external_api_timeout: 30s
- celery_task_timeout: 300s

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: Fix Broad Exception Handlers (High Priority)

**Files:**
- Modify: Files with `except Exception as e:` that should be specific

**Step 1: Categorize exception handlers**

Priority fixes (hiding bugs):
1. Routes that catch Exception and return generic 500
2. Business logic that swallows exceptions silently

Acceptable (logging/cleanup):
- Top-level task error handlers
- Graceful degradation paths

**Step 2: Fix high-priority handlers**

Example pattern to apply:

```python
# Before:
except Exception as e:
    logger.error("Error", error=str(e))
    return {"error": "Something went wrong"}

# After:
except (ValueError, KeyError) as e:
    logger.warning("Invalid data", error=str(e))
    raise HTTPException(status_code=400, detail=str(e))
except sqlalchemy.exc.SQLAlchemyError as e:
    logger.error("Database error", error=str(e))
    raise HTTPException(status_code=500, detail="Database error")
```

**Step 3: Run linter**

Run: `docker compose exec backend ruff check backend/app/`
Expected: Reduced warnings

**Step 4: Commit**

```bash
git add backend/app/
git commit -m "$(cat <<'EOF'
refactor: replace broad exception handlers with specific types

Replaced generic except Exception with specific exception types
in routes and business logic to improve error visibility.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: Run Linter and Fix Warnings

**Files:**
- All backend Python files

**Step 1: Run ruff with auto-fix**

Run: `docker compose exec backend ruff check --fix backend/app/`

**Step 2: Review and commit fixes**

```bash
git add backend/app/
git commit -m "$(cat <<'EOF'
chore: fix linting warnings (unused imports, formatting)

Applied ruff auto-fixes for:
- Unused imports
- Line length
- Formatting issues

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Summary

| Phase | Task | Priority | Estimated Complexity |
|-------|------|----------|---------------------|
| 1 | Rate limiting fail-closed | Critical | Low |
| 1 | Token blacklist fail-secure | Critical | Medium |
| 1 | OAuth URL encoding | Critical | Low |
| 1 | Bare except fix | Critical | Low |
| 1 | Refresh token rotation | Critical | High |
| 2 | Search input validation | High | Low |
| 2 | Frontend null checks | High | Medium |
| 2 | Auto-commit removal | High | Medium |
| 2 | Redis singleton fix | High | Low |
| 2 | .in_() query limits | High | Medium |
| 2 | IDOR audit | High | High |
| 2 | File upload validation | High | Low |
| 3 | Request ID middleware | Medium | Low |
| 3 | Timeout centralization | Medium | Medium |
| 3 | Exception handler fixes | Medium | High |
| 3 | Lint warning fixes | Low | Low |

**Total: 16 tasks across 3 phases**

---

## Testing Checklist

After completing all tasks:

1. [ ] Run full backend test suite: `make test-backend`
2. [ ] Run frontend type check: `cd frontend && npx tsc --noEmit`
3. [ ] Run frontend tests: `make test-frontend`
4. [ ] Manual testing of auth flow with new tokens
5. [ ] Verify rate limiting behavior with Redis down
6. [ ] Check request IDs in logs
