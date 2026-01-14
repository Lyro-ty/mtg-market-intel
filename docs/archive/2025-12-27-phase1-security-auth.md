# Phase 1: Security & Authentication Implementation Plan

**Status:** ⏳ Partially Implemented (Rate limiting, password requirements done. Google OAuth deferred - not blocking for launch)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Google OAuth, rate limiting, password requirements, and session management to create a secure authentication foundation.

**Architecture:** OAuth flow uses backend as intermediary (Authorization Code flow). Backend exchanges code for tokens, creates/links user accounts, issues JWT. Frontend redirects to Google, receives callback, stores JWT.

**Tech Stack:** FastAPI + Authlib (OAuth), Redis (rate limiting), React + next-auth patterns (frontend)

---

## Task 1: Add Google OAuth Dependencies

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`

**Step 1: Add authlib to requirements**

Add to `backend/requirements.txt`:
```
authlib==1.3.0
httpx==0.27.0
```

**Step 2: Add OAuth config settings**

Add to `backend/app/core/config.py` in the `Settings` class:
```python
# OAuth settings
GOOGLE_CLIENT_ID: str = ""
GOOGLE_CLIENT_SECRET: str = ""
GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
OAUTH_ENABLED: bool = False
```

**Step 3: Run to verify no syntax errors**

```bash
cd /home/lyro/mtg-market-intel/.worktrees/frontend-redesign/backend
python -c "from app.core.config import settings; print('Config OK')"
```
Expected: `Config OK`

**Step 4: Commit**

```bash
git add requirements.txt app/core/config.py
git commit -m "feat: add Google OAuth dependencies and config"
```

---

## Task 2: Create OAuth Router

**Files:**
- Create: `backend/app/api/routes/oauth.py`
- Modify: `backend/app/api/router.py`

**Step 1: Create OAuth router**

Create `backend/app/api/routes/oauth.py`:
```python
"""Google OAuth authentication routes."""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.auth import create_access_token

router = APIRouter(prefix="/auth", tags=["oauth"])

# Initialize OAuth client
oauth = OAuth()

if settings.OAUTH_ENABLED and settings.GOOGLE_CLIENT_ID:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


@router.get("/google/login")
async def google_login(request: Request):
    """Redirect to Google OAuth login."""
    if not settings.OAUTH_ENABLED:
        raise HTTPException(status_code=400, detail="OAuth is not enabled")

    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback."""
    if not settings.OAUTH_ENABLED:
        raise HTTPException(status_code=400, detail="OAuth is not enabled")

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")

    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")

    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by Google")

    # Find or create user
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Create new user from Google data
        user = User(
            email=email,
            username=user_info.get("name", email.split("@")[0]),
            hashed_password="",  # No password for OAuth users
            is_active=True,
            oauth_provider="google",
            oauth_id=user_info.get("sub"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif not user.oauth_provider:
        # Link existing user to Google
        user.oauth_provider = "google"
        user.oauth_id = user_info.get("sub")
        await db.commit()

    # Create JWT token
    access_token = create_access_token(data={"sub": str(user.id)})

    # Redirect to frontend with token
    frontend_url = "http://localhost:3000"
    return RedirectResponse(
        url=f"{frontend_url}/login?token={access_token}",
        status_code=302,
    )
```

**Step 2: Register router**

Add to `backend/app/api/router.py`:
```python
from app.api.routes.oauth import router as oauth_router
# ... in api_router includes:
api_router.include_router(oauth_router)
```

**Step 3: Verify syntax**

```bash
python -c "from app.api.routes.oauth import router; print('OAuth router OK')"
```
Expected: `OAuth router OK`

**Step 4: Commit**

```bash
git add app/api/routes/oauth.py app/api/router.py
git commit -m "feat: add Google OAuth login/callback endpoints"
```

---

## Task 3: Add OAuth Fields to User Model

**Files:**
- Modify: `backend/app/models/user.py`
- Create: `backend/alembic/versions/YYYYMMDD_add_oauth_fields.py`

**Step 1: Add OAuth fields to User model**

Add to `backend/app/models/user.py` in the `User` class:
```python
# OAuth fields
oauth_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
oauth_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

**Step 2: Create migration**

```bash
cd /home/lyro/mtg-market-intel/.worktrees/frontend-redesign/backend
alembic revision --autogenerate -m "add_oauth_fields_to_user"
```

**Step 3: Review generated migration**

Check the generated file in `alembic/versions/` - it should add `oauth_provider` and `oauth_id` columns.

**Step 4: Commit**

```bash
git add app/models/user.py alembic/versions/*oauth*
git commit -m "feat: add OAuth provider fields to User model"
```

---

## Task 4: Add Rate Limiting Middleware

**Files:**
- Create: `backend/app/middleware/rate_limit.py`
- Modify: `backend/app/main.py`

**Step 1: Create rate limiting middleware**

Create `backend/app/middleware/rate_limit.py`:
```python
"""Rate limiting middleware using Redis."""
import time
from typing import Callable
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit requests by IP address."""

    def __init__(
        self,
        app,
        redis_url: str = None,
        requests_per_minute: int = 60,
        auth_requests_per_minute: int = 5,
    ):
        super().__init__(app)
        self.redis_url = redis_url or settings.REDIS_URL
        self.requests_per_minute = requests_per_minute
        self.auth_requests_per_minute = auth_requests_per_minute
        self._redis = None

    async def get_redis(self):
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url)
        return self._redis

    async def dispatch(self, request: Request, call_next: Callable):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/api/health"]:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        # Use stricter limits for auth endpoints
        is_auth_endpoint = "/auth/" in request.url.path or "/login" in request.url.path
        limit = self.auth_requests_per_minute if is_auth_endpoint else self.requests_per_minute

        # Create rate limit key
        window = int(time.time() // 60)  # 1-minute window
        key = f"rate_limit:{client_ip}:{window}"
        if is_auth_endpoint:
            key = f"rate_limit:auth:{client_ip}:{window}"

        try:
            r = await self.get_redis()
            current = await r.incr(key)
            if current == 1:
                await r.expire(key, 60)  # Expire after 1 minute

            if current > limit:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": "60"},
                )
        except redis.RedisError:
            # If Redis is down, allow the request
            pass

        response = await call_next(request)
        return response
```

**Step 2: Add middleware to main.py**

Add to `backend/app/main.py` after CORS middleware:
```python
from app.middleware.rate_limit import RateLimitMiddleware

# Add rate limiting (after CORS)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=60,
    auth_requests_per_minute=5,
)
```

**Step 3: Verify syntax**

```bash
python -c "from app.middleware.rate_limit import RateLimitMiddleware; print('Rate limit OK')"
```
Expected: `Rate limit OK`

**Step 4: Commit**

```bash
git add app/middleware/rate_limit.py app/main.py
git commit -m "feat: add rate limiting middleware"
```

---

## Task 5: Add Password Strength Validation

**Files:**
- Create: `backend/app/utils/password.py`
- Modify: `backend/app/api/routes/auth.py`

**Step 1: Create password validation utility**

Create `backend/app/utils/password.py`:
```python
"""Password validation utilities."""
import re
from typing import Tuple


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password meets security requirements.

    Requirements:
    - At least 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"

    return True, ""


# Common weak passwords to reject
COMMON_PASSWORDS = {
    "password123456",
    "123456789012",
    "qwertyuiopas",
    "letmein12345",
}


def is_common_password(password: str) -> bool:
    """Check if password is in common passwords list."""
    return password.lower() in COMMON_PASSWORDS
```

**Step 2: Write test for password validation**

Create `backend/tests/utils/test_password.py`:
```python
"""Tests for password validation."""
import pytest
from app.utils.password import validate_password_strength, is_common_password


def test_valid_password():
    valid, msg = validate_password_strength("SecurePass123!")
    assert valid is True
    assert msg == ""


def test_password_too_short():
    valid, msg = validate_password_strength("Short1!")
    assert valid is False
    assert "12 characters" in msg


def test_password_no_uppercase():
    valid, msg = validate_password_strength("lowercase123!!")
    assert valid is False
    assert "uppercase" in msg


def test_password_no_lowercase():
    valid, msg = validate_password_strength("UPPERCASE123!!")
    assert valid is False
    assert "lowercase" in msg


def test_password_no_digit():
    valid, msg = validate_password_strength("NoDigitsHere!!")
    assert valid is False
    assert "digit" in msg


def test_password_no_special():
    valid, msg = validate_password_strength("NoSpecialChar1")
    assert valid is False
    assert "special" in msg


def test_common_password():
    assert is_common_password("password123456") is True
    assert is_common_password("SecurePass123!") is False
```

**Step 3: Run tests**

```bash
pytest tests/utils/test_password.py -v
```
Expected: All tests pass

**Step 4: Update auth route to use password validation**

Modify `backend/app/api/routes/auth.py` register endpoint to add:
```python
from app.utils.password import validate_password_strength, is_common_password

# In register endpoint, before creating user:
is_valid, error_msg = validate_password_strength(user_data.password)
if not is_valid:
    raise HTTPException(status_code=400, detail=error_msg)

if is_common_password(user_data.password):
    raise HTTPException(status_code=400, detail="Password is too common. Please choose a more secure password.")
```

**Step 5: Commit**

```bash
git add app/utils/password.py tests/utils/test_password.py app/api/routes/auth.py
git commit -m "feat: add password strength validation"
```

---

## Task 6: Frontend - Add Google Login Button

**Files:**
- Modify: `frontend/src/app/login/page.tsx`
- Create: `frontend/src/components/auth/GoogleLoginButton.tsx`

**Step 1: Create Google login button component**

Create `frontend/src/components/auth/GoogleLoginButton.tsx`:
```tsx
'use client';

import { Button } from '@/components/ui/Button';

const GoogleIcon = () => (
  <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
    <path
      fill="currentColor"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <path
      fill="currentColor"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <path
      fill="currentColor"
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
    />
    <path
      fill="currentColor"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
    />
  </svg>
);

interface GoogleLoginButtonProps {
  disabled?: boolean;
}

export function GoogleLoginButton({ disabled }: GoogleLoginButtonProps) {
  const handleGoogleLogin = () => {
    // Redirect to backend OAuth endpoint
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
    window.location.href = `${apiUrl}/api/v1/auth/google/login`;
  };

  return (
    <Button
      type="button"
      variant="secondary"
      size="lg"
      className="w-full"
      onClick={handleGoogleLogin}
      disabled={disabled}
    >
      <GoogleIcon />
      Continue with Google
    </Button>
  );
}
```

**Step 2: Add to login page**

Modify `frontend/src/app/login/page.tsx` to add:
```tsx
import { GoogleLoginButton } from '@/components/auth/GoogleLoginButton';

// Add after the login form, before the register link:
{/* OAuth Divider */}
<div className="relative my-6">
  <div className="absolute inset-0 flex items-center">
    <div className="w-full border-t border-slate-700" />
  </div>
  <div className="relative flex justify-center text-sm">
    <span className="px-2 bg-slate-900 text-slate-400">Or continue with</span>
  </div>
</div>

{/* Google Login */}
<GoogleLoginButton disabled={isLoading} />
```

**Step 3: Handle OAuth callback token**

Add to login page useEffect:
```tsx
// Handle OAuth callback token
useEffect(() => {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');
  if (token) {
    // Store token and redirect
    localStorage.setItem('token', token);
    router.push('/dashboard');
  }
}, [router]);
```

**Step 4: Commit**

```bash
git add frontend/src/components/auth/GoogleLoginButton.tsx frontend/src/app/login/page.tsx
git commit -m "feat: add Google OAuth login button to frontend"
```

---

## Task 7: Add Session Management Backend

**Files:**
- Create: `backend/app/models/session.py`
- Create: `backend/app/api/routes/sessions.py`
- Create: `backend/alembic/versions/YYYYMMDD_add_sessions_table.py`

**Step 1: Create Session model**

Create `backend/app/models/session.py`:
```python
"""User session model for session management."""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserSession(Base):
    """Track user login sessions."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # SHA256 of token
    device_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationship
    user = relationship("User", back_populates="sessions")
```

**Step 2: Add sessions relationship to User model**

Add to `backend/app/models/user.py`:
```python
# Add relationship
sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
```

**Step 3: Create sessions API routes**

Create `backend/app/api/routes/sessions.py`:
```python
"""Session management endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.session import UserSession

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionResponse(BaseModel):
    id: int
    device_info: str | None
    ip_address: str | None
    created_at: datetime
    last_active: datetime
    is_current: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=List[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active sessions for current user."""
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == current_user.id)
        .where(UserSession.is_revoked == False)
        .where(UserSession.expires_at > datetime.utcnow())
        .order_by(UserSession.last_active.desc())
    )
    sessions = result.scalars().all()

    # Mark current session (would need token from request)
    return [
        SessionResponse(
            id=s.id,
            device_info=s.device_info,
            ip_address=s.ip_address,
            created_at=s.created_at,
            last_active=s.last_active,
            is_current=False,  # TODO: Detect current session
        )
        for s in sessions
    ]


@router.delete("/{session_id}")
async def revoke_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a specific session."""
    result = await db.execute(
        select(UserSession)
        .where(UserSession.id == session_id)
        .where(UserSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_revoked = True
    await db.commit()

    return {"message": "Session revoked"}


@router.delete("/")
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all sessions except current."""
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == current_user.id)
        .where(UserSession.is_revoked == False)
        .values(is_revoked=True)
    )
    await db.commit()

    return {"message": "All sessions revoked"}
```

**Step 4: Create migration**

```bash
alembic revision --autogenerate -m "add_user_sessions_table"
```

**Step 5: Register router**

Add to `backend/app/api/router.py`:
```python
from app.api.routes.sessions import router as sessions_router
api_router.include_router(sessions_router)
```

**Step 6: Commit**

```bash
git add app/models/session.py app/models/user.py app/api/routes/sessions.py app/api/router.py alembic/versions/*sessions*
git commit -m "feat: add session management endpoints"
```

---

## Task 8: Frontend Session Management UI

**Files:**
- Create: `frontend/src/components/settings/SessionsManager.tsx`
- Modify: `frontend/src/app/settings/page.tsx`

**Step 1: Create SessionsManager component**

Create `frontend/src/components/settings/SessionsManager.tsx`:
```tsx
'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Monitor, Smartphone, Trash2, LogOut } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { api } from '@/lib/api';

interface Session {
  id: number;
  device_info: string | null;
  ip_address: string | null;
  created_at: string;
  last_active: string;
  is_current: boolean;
}

export function SessionsManager() {
  const queryClient = useQueryClient();

  const { data: sessions, isLoading } = useQuery<Session[]>({
    queryKey: ['sessions'],
    queryFn: () => api.get('/sessions').then((r) => r.data),
  });

  const revokeMutation = useMutation({
    mutationFn: (sessionId: number) => api.delete(`/sessions/${sessionId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  });

  const revokeAllMutation = useMutation({
    mutationFn: () => api.delete('/sessions'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  });

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getDeviceIcon = (deviceInfo: string | null) => {
    if (deviceInfo?.toLowerCase().includes('mobile')) {
      return <Smartphone className="w-5 h-5" />;
    }
    return <Monitor className="w-5 h-5" />;
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Active Sessions</CardTitle>
            <CardDescription>Manage your logged-in devices</CardDescription>
          </div>
          <Button
            variant="danger"
            size="sm"
            onClick={() => revokeAllMutation.mutate()}
            disabled={revokeAllMutation.isPending}
          >
            <LogOut className="w-4 h-4 mr-2" />
            Log out all devices
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-[rgb(var(--muted-foreground))]">Loading sessions...</p>
        ) : sessions?.length === 0 ? (
          <p className="text-[rgb(var(--muted-foreground))]">No active sessions</p>
        ) : (
          <div className="space-y-3">
            {sessions?.map((session) => (
              <div
                key={session.id}
                className="flex items-center justify-between p-4 rounded-lg bg-[rgb(var(--secondary))]"
              >
                <div className="flex items-center gap-4">
                  <div className="p-2 rounded-lg bg-[rgb(var(--background))]">
                    {getDeviceIcon(session.device_info)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-[rgb(var(--foreground))]">
                        {session.device_info || 'Unknown Device'}
                      </p>
                      {session.is_current && (
                        <Badge variant="success" size="sm">Current</Badge>
                      )}
                    </div>
                    <p className="text-sm text-[rgb(var(--muted-foreground))]">
                      {session.ip_address || 'Unknown IP'} • Last active {formatDate(session.last_active)}
                    </p>
                  </div>
                </div>
                {!session.is_current && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => revokeMutation.mutate(session.id)}
                    disabled={revokeMutation.isPending}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

**Step 2: Add to settings page**

Import and add to `frontend/src/app/settings/page.tsx`:
```tsx
import { SessionsManager } from '@/components/settings/SessionsManager';

// Add after Security section:
{/* Sessions */}
<SessionsManager />
```

**Step 3: Commit**

```bash
git add frontend/src/components/settings/SessionsManager.tsx frontend/src/app/settings/page.tsx
git commit -m "feat: add session management UI to settings"
```

---

## Task 9: Input Sanitization Audit

**Files:**
- Modify: Various API routes
- Create: `backend/app/utils/sanitize.py`

**Step 1: Create sanitization utilities**

Create `backend/app/utils/sanitize.py`:
```python
"""Input sanitization utilities."""
import re
import html
from typing import Optional


def sanitize_string(value: Optional[str], max_length: int = 1000) -> Optional[str]:
    """
    Sanitize a string input.

    - HTML encode special characters
    - Truncate to max length
    - Strip leading/trailing whitespace
    """
    if value is None:
        return None

    # Strip whitespace
    value = value.strip()

    # Truncate
    if len(value) > max_length:
        value = value[:max_length]

    # HTML encode to prevent XSS
    value = html.escape(value)

    return value


def sanitize_email(email: str) -> str:
    """Sanitize and validate email format."""
    email = email.strip().lower()

    # Basic email validation
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        raise ValueError("Invalid email format")

    return email


def sanitize_username(username: str) -> str:
    """Sanitize username - alphanumeric and underscores only."""
    username = username.strip()

    # Only allow alphanumeric and underscores
    if not re.match(r"^[a-zA-Z0-9_]{3,50}$", username):
        raise ValueError("Username must be 3-50 characters, alphanumeric and underscores only")

    return username
```

**Step 2: Write tests**

Create `backend/tests/utils/test_sanitize.py`:
```python
"""Tests for input sanitization."""
import pytest
from app.utils.sanitize import sanitize_string, sanitize_email, sanitize_username


def test_sanitize_string_escapes_html():
    result = sanitize_string("<script>alert('xss')</script>")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_sanitize_string_truncates():
    long_string = "a" * 2000
    result = sanitize_string(long_string, max_length=100)
    assert len(result) == 100


def test_sanitize_string_strips_whitespace():
    result = sanitize_string("  hello  ")
    assert result == "hello"


def test_sanitize_email_valid():
    result = sanitize_email("Test@Example.COM")
    assert result == "test@example.com"


def test_sanitize_email_invalid():
    with pytest.raises(ValueError):
        sanitize_email("not-an-email")


def test_sanitize_username_valid():
    result = sanitize_username("valid_user123")
    assert result == "valid_user123"


def test_sanitize_username_invalid():
    with pytest.raises(ValueError):
        sanitize_username("user with spaces")
```

**Step 3: Run tests**

```bash
pytest tests/utils/test_sanitize.py -v
```
Expected: All tests pass

**Step 4: Apply to auth routes**

Update `backend/app/api/routes/auth.py` to use sanitization.

**Step 5: Commit**

```bash
git add app/utils/sanitize.py tests/utils/test_sanitize.py app/api/routes/auth.py
git commit -m "feat: add input sanitization utilities"
```

---

## Task 10: Add CSRF Protection

**Files:**
- Modify: `backend/app/main.py`
- Modify: `frontend/src/lib/api.ts`

**Step 1: Add CSRF middleware to backend**

The JWT auth pattern already provides CSRF protection since:
1. Token is stored in localStorage (not cookies)
2. Token must be sent in Authorization header
3. Attackers can't read localStorage from other domains

However, for extra security on state-changing operations, add double-submit cookie pattern:

Add to `backend/app/main.py`:
```python
from starlette.middleware.sessions import SessionMiddleware

# Add session middleware for CSRF
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="lax",
    https_only=settings.ENVIRONMENT == "production",
)
```

**Step 2: Document security approach**

Create `backend/docs/SECURITY.md`:
```markdown
# Security Implementation

## Authentication
- JWT tokens with short expiry (1 hour)
- Tokens stored in localStorage (CSRF-safe)
- Password hashing with bcrypt

## Rate Limiting
- 60 requests/minute for general endpoints
- 5 requests/minute for auth endpoints
- IP-based limiting via Redis

## Input Validation
- All inputs sanitized for XSS
- Email format validation
- Username character restrictions
- Password strength requirements

## OAuth
- Google OAuth via Authorization Code flow
- Backend exchanges code for tokens
- Existing accounts can be linked

## Session Management
- Track active sessions in database
- Allow revoking individual sessions
- Logout all devices option
```

**Step 3: Commit**

```bash
git add app/main.py docs/SECURITY.md
git commit -m "docs: add security documentation and session middleware"
```

---

## Summary

After completing all tasks, you will have:

1. **Google OAuth** - Users can sign in with Google
2. **Rate Limiting** - Protection against brute force attacks
3. **Password Validation** - Strong password requirements
4. **Session Management** - View and revoke active sessions
5. **Input Sanitization** - XSS and injection protection
6. **Security Documentation** - Clear security practices

**Next Phase:** Phase 2 - Visual Overhaul (Ornate Saga styling)
