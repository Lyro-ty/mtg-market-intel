# Production Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the platform advertisement-ready with security hardening, SEO optimization, recommendation accuracy display, command palette, and notification infrastructure.

**Architecture:** Security fixes use Redis for short-lived auth codes, SEO uses Next.js metadata API with dynamic OG images, command palette uses shadcn/ui Command component, notifications use VAPID-based web push with pywebpush and email digests via Celery.

**Tech Stack:** FastAPI, Next.js 14, Redis, pywebpush, shadcn/ui Command, Celery Beat

---

## Phase 1: Security Fixes

### Task 1.1: Authorization Code Exchange - Backend

**Files:**
- Modify: `backend/app/api/routes/oauth.py`
- Create: `backend/tests/api/test_oauth_exchange.py`

**Step 1: Write the failing test**

```python
# backend/tests/api/test_oauth_exchange.py
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_exchange_code_success(client: AsyncClient, test_user):
    """Test exchanging a valid auth code for a token."""
    # Mock Redis with a stored code
    with patch("app.api.routes.oauth.redis_client") as mock_redis:
        mock_redis.getdel = AsyncMock(return_value='{"user_id": 1, "access_token": "jwt_token_here"}')

        response = await client.post(
            "/api/auth/exchange",
            json={"code": "valid_auth_code"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_exchange_code_invalid(client: AsyncClient):
    """Test exchanging an invalid/expired auth code."""
    with patch("app.api.routes.oauth.redis_client") as mock_redis:
        mock_redis.getdel = AsyncMock(return_value=None)

        response = await client.post(
            "/api/auth/exchange",
            json={"code": "invalid_code"}
        )

        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/api/test_oauth_exchange.py -v`
Expected: FAIL with route not found or missing exchange endpoint

**Step 3: Write the exchange endpoint**

```python
# backend/app/api/routes/oauth.py - Add to existing file
import json
from pydantic import BaseModel

class ExchangeRequest(BaseModel):
    code: str

@router.post("/exchange")
async def exchange_code(request: ExchangeRequest):
    """Exchange authorization code for JWT token."""
    from app.core.redis import redis_client

    # Retrieve and delete (one-time use)
    data = await redis_client.getdel(f"auth_code:{request.code}")

    if not data:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    payload = json.loads(data)
    return {"access_token": payload["access_token"], "token_type": "bearer"}
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/api/test_oauth_exchange.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/api/routes/oauth.py backend/tests/api/test_oauth_exchange.py
git commit -m "feat(auth): add authorization code exchange endpoint"
```

---

### Task 1.2: OAuth Callback - Use Auth Code Instead of Token

**Files:**
- Modify: `backend/app/api/routes/oauth.py`
- Modify: `backend/tests/api/test_oauth_exchange.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/api/test_oauth_exchange.py
import secrets

@pytest.mark.asyncio
async def test_google_callback_returns_code_not_token(client: AsyncClient):
    """Test that OAuth callback returns auth code in redirect, not token."""
    with patch("app.api.routes.oauth.google_oauth") as mock_oauth:
        mock_oauth.authorize_access_token = AsyncMock(return_value={
            "userinfo": {"email": "test@example.com", "name": "Test User"}
        })

        with patch("app.api.routes.oauth.redis_client") as mock_redis:
            mock_redis.setex = AsyncMock()

            response = await client.get(
                "/api/auth/google/callback?code=google_code&state=state",
                follow_redirects=False
            )

            # Should redirect with code param, NOT token
            assert response.status_code == 307
            location = response.headers["location"]
            assert "code=" in location
            assert "token=" not in location
            assert "access_token=" not in location
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/api/test_oauth_exchange.py::test_google_callback_returns_code_not_token -v`
Expected: FAIL - current implementation returns token in URL

**Step 3: Modify the callback to use auth code**

```python
# backend/app/api/routes/oauth.py - Modify google_callback function
import secrets

@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        token = await google_oauth.authorize_access_token(request)
    except Exception as e:
        logger.error(f"OAuth error: {e}")
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=oauth_failed")

    user_info = token.get("userinfo")
    if not user_info:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=no_user_info")

    email = user_info.get("email")
    name = user_info.get("name", email.split("@")[0])

    # Get or create user
    user = await get_or_create_oauth_user(db, email, name, "google")

    # Create JWT token
    access_token = create_access_token(data={"sub": str(user.id)})

    # Generate short-lived auth code
    auth_code = secrets.token_urlsafe(32)

    # Store in Redis with 30-second TTL
    from app.core.redis import redis_client
    await redis_client.setex(
        f"auth_code:{auth_code}",
        30,  # 30 seconds
        json.dumps({"user_id": user.id, "access_token": access_token})
    )

    # Redirect with code (not token)
    return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?code={auth_code}")
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/api/test_oauth_exchange.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/api/routes/oauth.py backend/tests/api/test_oauth_exchange.py
git commit -m "feat(auth): use auth code exchange instead of token in URL"
```

---

### Task 1.3: Frontend Auth Callback - Exchange Code

**Files:**
- Modify: `frontend/src/app/auth/callback/page.tsx`

**Step 1: Read current implementation**

Run: `cat frontend/src/app/auth/callback/page.tsx`

**Step 2: Update to exchange code for token**

```typescript
// frontend/src/app/auth/callback/page.tsx
'use client';

import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Loader2 } from 'lucide-react';

export default function AuthCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get('code');
    const errorParam = searchParams.get('error');

    if (errorParam) {
      setError(errorParam);
      setTimeout(() => router.push('/login?error=auth_failed'), 2000);
      return;
    }

    if (code) {
      exchangeCode(code);
    } else {
      setError('No authorization code received');
      setTimeout(() => router.push('/login'), 2000);
    }
  }, [searchParams]);

  async function exchangeCode(code: string) {
    try {
      const response = await fetch('/api/auth/exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Exchange failed');
      }

      const { access_token } = await response.json();
      login(access_token);
      router.push('/dashboard');
    } catch (err) {
      console.error('Auth exchange failed:', err);
      setError('Authentication failed. Please try again.');
      setTimeout(() => router.push('/login?error=exchange_failed'), 2000);
    }
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-2">Authentication Error</p>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-accent" />
        <p className="text-muted-foreground">Completing sign in...</p>
      </div>
    </div>
  );
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/app/auth/callback/page.tsx
git commit -m "feat(auth): exchange auth code for token on callback"
```

---

### Task 1.4: WebSocket Authentication via Message

**Files:**
- Modify: `backend/app/api/routes/websocket.py`
- Modify: `frontend/src/contexts/WebSocketContext.tsx`

**Step 1: Update backend WebSocket handler**

```python
# backend/app/api/routes/websocket.py
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from app.services.auth import verify_token

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        # Wait for auth message (5 second timeout)
        try:
            auth_message = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            await websocket.close(code=4002, reason="Auth timeout")
            return

        if auth_message.get("type") != "auth":
            await websocket.close(code=4001, reason="Expected auth message")
            return

        token = auth_message.get("token")
        if not token:
            await websocket.close(code=4003, reason="No token provided")
            return

        # Verify token
        try:
            user = await verify_token(token)
        except Exception:
            await websocket.close(code=4003, reason="Invalid token")
            return

        if not user:
            await websocket.close(code=4003, reason="Invalid token")
            return

        # Send auth success
        await websocket.send_json({"type": "auth_success", "user_id": user.id})

        # Handle authenticated connection
        await handle_authenticated_connection(websocket, user)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass
```

**Step 2: Update frontend WebSocket context**

```typescript
// frontend/src/contexts/WebSocketContext.tsx - Update connect function
const connect = useCallback(() => {
  if (wsRef.current?.readyState === WebSocket.OPEN) return;

  const token = getAccessToken();
  if (!token) return;

  // Connect WITHOUT token in URL
  const ws = new WebSocket(WS_URL);
  wsRef.current = ws;

  ws.onopen = () => {
    // Send auth as first message
    ws.send(JSON.stringify({
      type: 'auth',
      token: token
    }));
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      if (data.type === 'auth_success') {
        setIsConnected(true);
        setIsAuthenticated(true);
        reconnectAttemptsRef.current = 0;
        return;
      }

      // Handle other message types...
      handleMessage(data);
    } catch (err) {
      // Non-JSON message, ignore
    }
  };

  ws.onclose = (event) => {
    setIsConnected(false);
    setIsAuthenticated(false);

    // Don't reconnect on auth failures
    if (event.code >= 4001 && event.code <= 4003) {
      return;
    }

    // Reconnect with backoff
    if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
      const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
      reconnectAttemptsRef.current++;
      setTimeout(connect, delay);
    }
  };

  ws.onerror = () => {
    // Error handling done in onclose
  };
}, []);
```

**Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add backend/app/api/routes/websocket.py frontend/src/contexts/WebSocketContext.tsx
git commit -m "feat(auth): WebSocket auth via message instead of URL"
```

---

### Task 1.5: Random Password for OAuth Users

**Files:**
- Modify: `backend/app/services/auth.py`
- Create: `backend/tests/services/test_oauth_password.py`

**Step 1: Write the failing test**

```python
# backend/tests/services/test_oauth_password.py
import pytest
from app.services.auth import get_or_create_oauth_user, verify_password

@pytest.mark.asyncio
async def test_oauth_user_has_unusable_password(db_session):
    """OAuth users should have a random password that can't be guessed."""
    user = await get_or_create_oauth_user(
        db=db_session,
        email="oauth@example.com",
        name="OAuth User",
        provider="google"
    )

    # Password should be set (not empty)
    assert user.hashed_password is not None
    assert len(user.hashed_password) > 0

    # Common passwords should not work
    assert not verify_password("", user.hashed_password)
    assert not verify_password("password", user.hashed_password)
    assert not verify_password("oauth@example.com", user.hashed_password)
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/services/test_oauth_password.py -v`
Expected: FAIL (if current implementation uses empty password)

**Step 3: Update OAuth user creation**

```python
# backend/app/services/auth.py - Update get_or_create_oauth_user
import secrets

async def get_or_create_oauth_user(
    db: AsyncSession,
    email: str,
    name: str,
    provider: str
) -> User:
    """Get existing user or create new OAuth user with random password."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        # Update OAuth provider if not set
        if not user.oauth_provider:
            user.oauth_provider = provider
            await db.commit()
        return user

    # Create new user with random unusable password
    random_password = secrets.token_urlsafe(32)

    user = User(
        email=email,
        username=name or email.split("@")[0],
        hashed_password=get_password_hash(random_password),
        oauth_provider=provider,
        is_active=True,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/services/test_oauth_password.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/auth.py backend/tests/services/test_oauth_password.py
git commit -m "feat(auth): set random unusable password for OAuth users"
```

---

### Task 1.6: Username Validation

**Files:**
- Modify: `backend/app/schemas/user.py`
- Create: `backend/tests/schemas/test_username_validation.py`

**Step 1: Write the failing test**

```python
# backend/tests/schemas/test_username_validation.py
import pytest
from pydantic import ValidationError
from app.schemas.user import UserCreate

def test_valid_usernames():
    """Test that valid usernames are accepted."""
    valid_names = ["user123", "test_user", "my-name", "ABC123"]
    for name in valid_names:
        user = UserCreate(email="test@example.com", username=name, password="password123")
        assert user.username == name


def test_invalid_username_characters():
    """Test that usernames with invalid characters are rejected."""
    invalid_names = ["user@name", "test user", "name!", "hello#world"]
    for name in invalid_names:
        with pytest.raises(ValidationError) as exc:
            UserCreate(email="test@example.com", username=name, password="password123")
        assert "letters, numbers, underscores, and hyphens" in str(exc.value)


def test_username_boundary_characters():
    """Test that usernames can't start/end with _ or -."""
    invalid_names = ["_username", "username_", "-username", "username-"]
    for name in invalid_names:
        with pytest.raises(ValidationError) as exc:
            UserCreate(email="test@example.com", username=name, password="password123")
        assert "start or end" in str(exc.value)


def test_username_length():
    """Test username length constraints."""
    # Too short
    with pytest.raises(ValidationError):
        UserCreate(email="test@example.com", username="ab", password="password123")

    # Too long
    with pytest.raises(ValidationError):
        UserCreate(email="test@example.com", username="a" * 31, password="password123")

    # Just right
    UserCreate(email="test@example.com", username="abc", password="password123")
    UserCreate(email="test@example.com", username="a" * 30, password="password123")
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/schemas/test_username_validation.py -v`
Expected: FAIL - no validation currently

**Step 3: Add username validation**

```python
# backend/app/schemas/user.py
import re
from pydantic import BaseModel, EmailStr, Field, field_validator

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=8)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        if v.startswith(('_', '-')) or v.endswith(('_', '-')):
            raise ValueError('Username cannot start or end with underscore or hyphen')
        return v
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/schemas/test_username_validation.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/schemas/user.py backend/tests/schemas/test_username_validation.py
git commit -m "feat(auth): add username validation with character constraints"
```

---

## Phase 2: SEO Metadata

### Task 2.1: Static Page Metadata - Landing

**Files:**
- Modify: `frontend/src/app/page.tsx`

**Step 1: Read current implementation**

Run: `head -50 frontend/src/app/page.tsx`

**Step 2: Add metadata export**

```typescript
// frontend/src/app/page.tsx - Add at top of file
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Dualcaster Deals - MTG Price Intelligence',
  description: 'Track Magic: The Gathering card prices across TCGPlayer, CardTrader, and more. Get buy/sell recommendations powered by market analytics.',
  keywords: ['MTG', 'Magic: The Gathering', 'card prices', 'TCGPlayer', 'price tracker', 'trading cards'],
  openGraph: {
    title: 'Dualcaster Deals - MTG Price Intelligence',
    description: 'Track MTG card prices and get AI-powered trading recommendations.',
    url: 'https://dualcasterdeals.com',
    siteName: 'Dualcaster Deals',
    images: [
      {
        url: '/og-home.png',
        width: 1200,
        height: 630,
        alt: 'Dualcaster Deals - MTG Price Intelligence',
      },
    ],
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Dualcaster Deals - MTG Price Intelligence',
    description: 'Track MTG card prices and get AI-powered trading recommendations.',
    images: ['/og-home.png'],
  },
  robots: {
    index: true,
    follow: true,
  },
};

// ... rest of component
```

**Step 3: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat(seo): add metadata to landing page"
```

---

### Task 2.2: Static Page Metadata - Login/Register

**Files:**
- Modify: `frontend/src/app/(public)/login/page.tsx`
- Modify: `frontend/src/app/(public)/register/page.tsx`

**Step 1: Add metadata to login page**

```typescript
// frontend/src/app/(public)/login/page.tsx - Add at top
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Login | Dualcaster Deals',
  description: 'Sign in to your Dualcaster Deals account to track MTG card prices and manage your collection.',
  robots: { index: false, follow: false },
};
```

**Step 2: Add metadata to register page**

```typescript
// frontend/src/app/(public)/register/page.tsx - Add at top
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Create Account | Dualcaster Deals',
  description: 'Sign up for Dualcaster Deals to track MTG card prices, get trading recommendations, and manage your collection.',
  robots: { index: true, follow: true },
};
```

**Step 3: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/app/(public)/login/page.tsx frontend/src/app/(public)/register/page.tsx
git commit -m "feat(seo): add metadata to login and register pages"
```

---

### Task 2.3: Dynamic Card Page Metadata

**Files:**
- Modify: `frontend/src/app/(public)/cards/[id]/page.tsx`

**Step 1: Read current implementation**

Run: `head -100 frontend/src/app/(public)/cards/[id]/page.tsx`

**Step 2: Add generateMetadata function**

```typescript
// frontend/src/app/(public)/cards/[id]/page.tsx - Add at top after imports
import type { Metadata } from 'next';

interface Props {
  params: { id: string };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  try {
    const response = await fetch(
      `${process.env.BACKEND_URL || 'http://localhost:8000'}/api/cards/${params.id}`,
      { next: { revalidate: 3600 } }  // Cache for 1 hour
    );

    if (!response.ok) {
      return { title: 'Card Not Found | Dualcaster Deals' };
    }

    const card = await response.json();
    const price = card.latest_price ? `$${card.latest_price.toFixed(2)}` : 'Price unavailable';
    const title = `${card.name} - ${price} | Dualcaster Deals`;
    const description = `${card.name} from ${card.set_name}. Current price: ${price}. View price history, market trends, and trading recommendations.`;

    return {
      title,
      description,
      openGraph: {
        title,
        description,
        url: `https://dualcasterdeals.com/cards/${card.id}`,
        images: [
          {
            url: `/api/og/card/${card.id}`,
            width: 1200,
            height: 630,
            alt: card.name,
          },
        ],
        type: 'website',
      },
      twitter: {
        card: 'summary_large_image',
        title,
        description,
        images: [`/api/og/card/${card.id}`],
      },
    };
  } catch (error) {
    return { title: 'Card | Dualcaster Deals' };
  }
}
```

**Step 3: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/app/(public)/cards/[id]/page.tsx
git commit -m "feat(seo): add dynamic metadata to card pages"
```

---

### Task 2.4: JSON-LD Structured Data Component

**Files:**
- Create: `frontend/src/components/seo/CardJsonLd.tsx`
- Modify: `frontend/src/app/(public)/cards/[id]/page.tsx`

**Step 1: Create the JSON-LD component**

```typescript
// frontend/src/components/seo/CardJsonLd.tsx
interface Card {
  id: number;
  name: string;
  set_name: string;
  rarity: string;
  mana_cost?: string;
  oracle_text?: string;
  type_line?: string;
  image_uri?: string;
  scryfall_id: string;
  latest_price?: number;
}

interface CardJsonLdProps {
  card: Card;
}

export function CardJsonLd({ card }: CardJsonLdProps) {
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: card.name,
    description: card.oracle_text || `${card.name} - ${card.type_line || 'Magic: The Gathering card'}`,
    image: card.image_uri,
    sku: card.scryfall_id,
    brand: {
      '@type': 'Brand',
      name: 'Magic: The Gathering',
    },
    ...(card.latest_price && {
      offers: {
        '@type': 'AggregateOffer',
        priceCurrency: 'USD',
        lowPrice: card.latest_price,
        highPrice: card.latest_price,
        offerCount: 1,
        availability: 'https://schema.org/InStock',
      },
    }),
    additionalProperty: [
      { '@type': 'PropertyValue', name: 'Set', value: card.set_name },
      { '@type': 'PropertyValue', name: 'Rarity', value: card.rarity },
      ...(card.mana_cost ? [{ '@type': 'PropertyValue', name: 'Mana Cost', value: card.mana_cost }] : []),
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}
```

**Step 2: Add to card page**

```typescript
// frontend/src/app/(public)/cards/[id]/page.tsx - Add import and usage
import { CardJsonLd } from '@/components/seo/CardJsonLd';

// In the component return, add:
// <CardJsonLd card={card} />
```

**Step 3: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/components/seo/CardJsonLd.tsx frontend/src/app/(public)/cards/[id]/page.tsx
git commit -m "feat(seo): add JSON-LD structured data for card pages"
```

---

### Task 2.5: Dynamic OG Image Generation

**Files:**
- Create: `frontend/src/app/api/og/card/[id]/route.tsx`

**Step 1: Create the OG image route**

```typescript
// frontend/src/app/api/og/card/[id]/route.tsx
import { ImageResponse } from 'next/og';

export const runtime = 'edge';

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const response = await fetch(
      `${process.env.BACKEND_URL || 'http://localhost:8000'}/api/cards/${params.id}`
    );

    if (!response.ok) {
      return new Response('Card not found', { status: 404 });
    }

    const card = await response.json();
    const price = card.latest_price ? `$${card.latest_price.toFixed(2)}` : 'N/A';

    return new ImageResponse(
      (
        <div
          style={{
            display: 'flex',
            width: '100%',
            height: '100%',
            backgroundColor: '#0C0C10',
            padding: 60,
          }}
        >
          {/* Card image */}
          <div style={{ display: 'flex', marginRight: 60 }}>
            {card.image_uri ? (
              <img
                src={card.image_uri}
                alt={card.name}
                style={{
                  width: 300,
                  height: 420,
                  borderRadius: 16,
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                }}
              />
            ) : (
              <div
                style={{
                  width: 300,
                  height: 420,
                  borderRadius: 16,
                  backgroundColor: '#1C1C24',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#6B7280',
                  fontSize: 24,
                }}
              >
                No Image
              </div>
            )}
          </div>

          {/* Card info */}
          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', flex: 1 }}>
            <div style={{ fontSize: 48, fontWeight: 'bold', color: '#FFFFFF', marginBottom: 16 }}>
              {card.name}
            </div>
            <div style={{ fontSize: 28, color: '#9CA3AF', marginBottom: 32 }}>
              {card.set_name} - {card.rarity}
            </div>
            <div style={{ fontSize: 64, fontWeight: 'bold', color: '#22C55E' }}>
              {price}
            </div>
            <div style={{ fontSize: 24, color: '#6B7280', marginTop: 32 }}>
              dualcasterdeals.com
            </div>
          </div>
        </div>
      ),
      {
        width: 1200,
        height: 630,
      }
    );
  } catch (error) {
    return new Response('Error generating image', { status: 500 });
  }
}
```

**Step 2: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/app/api/og/card/[id]/route.tsx
git commit -m "feat(seo): add dynamic OG image generation for card pages"
```

---

### Task 2.6: Sitemap Generation

**Files:**
- Create: `frontend/src/app/sitemap.ts`

**Step 1: Create the sitemap**

```typescript
// frontend/src/app/sitemap.ts
import type { MetadataRoute } from 'next';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || 'https://dualcasterdeals.com';

  // Static pages
  const staticPages: MetadataRoute.Sitemap = [
    {
      url: baseUrl,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1,
    },
    {
      url: `${baseUrl}/login`,
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.5,
    },
    {
      url: `${baseUrl}/register`,
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.5,
    },
    {
      url: `${baseUrl}/cards`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.9,
    },
    {
      url: `${baseUrl}/market`,
      lastModified: new Date(),
      changeFrequency: 'hourly',
      priority: 0.8,
    },
  ];

  // Fetch top cards for dynamic pages
  let cardPages: MetadataRoute.Sitemap = [];
  try {
    const response = await fetch(
      `${process.env.BACKEND_URL || 'http://localhost:8000'}/api/cards?sort=-price&limit=1000`,
      { next: { revalidate: 86400 } }  // Revalidate daily
    );

    if (response.ok) {
      const data = await response.json();
      const cards = data.items || data;

      cardPages = cards.map((card: { id: number; updated_at?: string }) => ({
        url: `${baseUrl}/cards/${card.id}`,
        lastModified: card.updated_at ? new Date(card.updated_at) : new Date(),
        changeFrequency: 'daily' as const,
        priority: 0.7,
      }));
    }
  } catch (error) {
    console.error('Failed to fetch cards for sitemap:', error);
  }

  return [...staticPages, ...cardPages];
}
```

**Step 2: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/app/sitemap.ts
git commit -m "feat(seo): add sitemap generation with static and card pages"
```

---

## Phase 3: Recommendation Accuracy Display

### Task 3.1: Accuracy Badge Component

**Files:**
- Create: `frontend/src/components/recommendations/AccuracyBadge.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/recommendations/AccuracyBadge.tsx
import { Badge } from '@/components/ui/badge';
import { CheckCircle, TrendingUp, XCircle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AccuracyBadgeProps {
  accuracy: number | null;
  isPeak?: boolean;
  className?: string;
}

export function AccuracyBadge({ accuracy, isPeak = false, className }: AccuracyBadgeProps) {
  if (accuracy === null) {
    return (
      <Badge variant="secondary" className={cn('text-xs', className)}>
        <Clock className="w-3 h-3 mr-1" />
        Pending
      </Badge>
    );
  }

  const { bgColor, textColor, Icon, label } = getAccuracyDisplay(accuracy);

  return (
    <Badge className={cn('text-xs', bgColor, textColor, className)}>
      <Icon className="w-3 h-3 mr-1" />
      {isPeak ? 'Peak ' : ''}{Math.round(accuracy * 100)}%
      <span className="ml-1 opacity-75">{label}</span>
    </Badge>
  );
}

function getAccuracyDisplay(accuracy: number) {
  if (accuracy >= 0.9) {
    return {
      bgColor: 'bg-green-500/20',
      textColor: 'text-green-400',
      Icon: CheckCircle,
      label: 'Hit target',
    };
  } else if (accuracy >= 0.5) {
    return {
      bgColor: 'bg-yellow-500/20',
      textColor: 'text-yellow-400',
      Icon: TrendingUp,
      label: 'Partial',
    };
  } else {
    return {
      bgColor: 'bg-red-500/20',
      textColor: 'text-red-400',
      Icon: XCircle,
      label: 'Missed',
    };
  }
}
```

**Step 2: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/recommendations/AccuracyBadge.tsx
git commit -m "feat(recommendations): add AccuracyBadge component"
```

---

### Task 3.2: Outcome Stats Section

**Files:**
- Create: `frontend/src/components/recommendations/OutcomeStats.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/recommendations/OutcomeStats.tsx
'use client';

import { ToggleLeft, ToggleRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { AccuracyBadge } from './AccuracyBadge';
import { formatRelativeTime, formatDate } from '@/lib/utils';

interface Recommendation {
  outcomeEvaluatedAt: string | null;
  outcomePriceEnd: number | null;
  outcomePricePeak: number | null;
  outcomePricePeakAt: string | null;
  accuracyScoreEnd: number | null;
  accuracyScorePeak: number | null;
  actualProfitPctEnd: number | null;
  actualProfitPctPeak: number | null;
}

interface OutcomeStatsProps {
  recommendation: Recommendation;
  showPeak: boolean;
  onToggle: () => void;
}

export function OutcomeStats({ recommendation, showPeak, onToggle }: OutcomeStatsProps) {
  if (!recommendation.outcomeEvaluatedAt) {
    return null;
  }

  const accuracy = showPeak ? recommendation.accuracyScorePeak : recommendation.accuracyScoreEnd;
  const price = showPeak ? recommendation.outcomePricePeak : recommendation.outcomePriceEnd;
  const profit = showPeak ? recommendation.actualProfitPctPeak : recommendation.actualProfitPctEnd;

  return (
    <div className="border-t border-border pt-3 mt-3 space-y-2">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Evaluated {formatRelativeTime(recommendation.outcomeEvaluatedAt)}</span>

        {/* Peak/End Toggle */}
        <button
          onClick={onToggle}
          className="flex items-center gap-1 px-2 py-1 rounded bg-muted hover:bg-muted/80 transition-colors"
        >
          {showPeak ? (
            <ToggleRight className="w-3 h-3 text-accent" />
          ) : (
            <ToggleLeft className="w-3 h-3" />
          )}
          <span>{showPeak ? 'Peak' : 'End'}</span>
        </button>
      </div>

      <div className="grid grid-cols-3 gap-2 text-sm">
        <div>
          <div className="text-muted-foreground text-xs">Price</div>
          <div className="font-medium">${price?.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs">Result</div>
          <div className={cn('font-medium', (profit ?? 0) >= 0 ? 'text-green-400' : 'text-red-400')}>
            {(profit ?? 0) >= 0 ? '+' : ''}{profit?.toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs">Accuracy</div>
          <AccuracyBadge accuracy={accuracy} isPeak={showPeak} />
        </div>
      </div>

      {/* Peak info when showing end */}
      {!showPeak &&
       recommendation.accuracyScorePeak !== null &&
       recommendation.accuracyScoreEnd !== null &&
       recommendation.accuracyScorePeak > recommendation.accuracyScoreEnd && (
        <div className="text-xs text-muted-foreground italic">
          Peak accuracy was {Math.round(recommendation.accuracyScorePeak * 100)}%
          {recommendation.outcomePricePeakAt && (
            <> on {formatDate(recommendation.outcomePricePeakAt)}</>
          )}
        </div>
      )}
    </div>
  );
}
```

**Step 2: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/recommendations/OutcomeStats.tsx
git commit -m "feat(recommendations): add OutcomeStats component with peak/end toggle"
```

---

### Task 3.3: Confidence Calibration Indicator

**Files:**
- Create: `frontend/src/components/recommendations/ConfidenceCalibration.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/recommendations/ConfidenceCalibration.tsx
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface CalibrationStats {
  highConfidenceAccuracy: number;
  lowConfidenceAccuracy: number;
  totalEvaluated: number;
}

interface ConfidenceCalibrationProps {
  stats: CalibrationStats;
}

export function ConfidenceCalibration({ stats }: ConfidenceCalibrationProps) {
  const isCalibrated = stats.highConfidenceAccuracy > stats.lowConfidenceAccuracy;
  const difference = Math.abs(stats.highConfidenceAccuracy - stats.lowConfidenceAccuracy);

  return (
    <Card className="p-4">
      <h3 className="text-sm font-medium mb-3">Confidence Calibration</h3>

      <div className="space-y-3">
        <div className="flex justify-between items-center text-sm">
          <span className="text-muted-foreground">High confidence (&gt;80%)</span>
          <span className="font-medium">{Math.round(stats.highConfidenceAccuracy * 100)}% accurate</span>
        </div>

        <div className="flex justify-between items-center text-sm">
          <span className="text-muted-foreground">Low confidence (&lt;50%)</span>
          <span className="font-medium">{Math.round(stats.lowConfidenceAccuracy * 100)}% accurate</span>
        </div>

        {/* Visual bar comparison */}
        <div className="space-y-1">
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all"
              style={{ width: `${stats.highConfidenceAccuracy * 100}%` }}
            />
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-yellow-500 transition-all"
              style={{ width: `${stats.lowConfidenceAccuracy * 100}%` }}
            />
          </div>
        </div>

        <div className={cn(
          'text-xs p-2 rounded',
          isCalibrated ? 'bg-green-500/10 text-green-400' : 'bg-yellow-500/10 text-yellow-400'
        )}>
          {isCalibrated
            ? `Confidence scores are well-calibrated (${Math.round(difference * 100)}% difference)`
            : 'Confidence needs recalibration'}
        </div>
      </div>

      <div className="text-xs text-muted-foreground mt-3">
        Based on {stats.totalEvaluated.toLocaleString()} evaluated recommendations
      </div>
    </Card>
  );
}
```

**Step 2: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/recommendations/ConfidenceCalibration.tsx
git commit -m "feat(recommendations): add ConfidenceCalibration indicator component"
```

---

### Task 3.4: Recent Hits Ticker

**Files:**
- Create: `frontend/src/components/recommendations/RecentHitsTicker.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/recommendations/RecentHitsTicker.tsx
import { CheckCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { formatRelativeTime } from '@/lib/utils';

interface RecentHit {
  cardName: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  accuracy: number;
  profit: number;
  evaluatedAt: string;
}

interface RecentHitsTickerProps {
  hits: RecentHit[];
}

export function RecentHitsTicker({ hits }: RecentHitsTickerProps) {
  // Filter to only show hits with accuracy >= 0.8
  const successfulHits = hits.filter(h => h.accuracy >= 0.8);

  if (successfulHits.length === 0) return null;

  return (
    <div className="overflow-hidden bg-green-500/5 border-y border-green-500/20 py-2">
      <div className="animate-scroll-x flex gap-8 whitespace-nowrap">
        {/* First set */}
        {successfulHits.map((hit, i) => (
          <TickerItem key={i} hit={hit} />
        ))}
        {/* Duplicate for seamless loop */}
        {successfulHits.map((hit, i) => (
          <TickerItem key={`dup-${i}`} hit={hit} />
        ))}
      </div>
    </div>
  );
}

function TickerItem({ hit }: { hit: RecentHit }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
      <span className="font-medium">{hit.cardName}</span>
      <Badge variant="outline" className="text-xs">
        {hit.action}
      </Badge>
      <span className="text-green-400">+{hit.profit.toFixed(1)}%</span>
      <span className="text-muted-foreground text-xs">
        {formatRelativeTime(hit.evaluatedAt)}
      </span>
    </div>
  );
}
```

**Step 2: Add CSS animation**

```css
/* Add to frontend/src/app/globals.css */
@keyframes scroll-x {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(-50%);
  }
}

.animate-scroll-x {
  animation: scroll-x 30s linear infinite;
}

.animate-scroll-x:hover {
  animation-play-state: paused;
}
```

**Step 3: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/components/recommendations/RecentHitsTicker.tsx frontend/src/app/globals.css
git commit -m "feat(recommendations): add RecentHitsTicker scrolling component"
```

---

### Task 3.5: Integrate Accuracy Display into Recommendation Cards

**Files:**
- Modify: `frontend/src/components/recommendations/RecommendationCard.tsx`

**Step 1: Read current implementation**

Run: `cat frontend/src/components/recommendations/RecommendationCard.tsx`

**Step 2: Add outcome stats integration**

```typescript
// frontend/src/components/recommendations/RecommendationCard.tsx
'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { AccuracyBadge } from './AccuracyBadge';
import { OutcomeStats } from './OutcomeStats';
// ... other imports

interface RecommendationCardProps {
  recommendation: Recommendation;
}

export function RecommendationCard({ recommendation }: RecommendationCardProps) {
  const [showPeak, setShowPeak] = useState(false);

  return (
    <Card className="p-4">
      {/* Header with action badge and accuracy */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Badge variant={getActionVariant(recommendation.action)}>
            {recommendation.action}
          </Badge>
          <span className="font-medium">{recommendation.card_name}</span>
        </div>

        {/* Show accuracy badge if evaluated */}
        {recommendation.outcomeEvaluatedAt && (
          <AccuracyBadge accuracy={recommendation.accuracyScoreEnd} />
        )}
      </div>

      {/* Target and confidence */}
      <div className="text-sm text-muted-foreground mb-2">
        Target: ${recommendation.target_price?.toFixed(2)} |
        Confidence: {Math.round(recommendation.confidence * 100)}%
      </div>

      {/* Signals/reasoning */}
      {recommendation.signals && recommendation.signals.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {recommendation.signals.slice(0, 3).map((signal, i) => (
            <Badge key={i} variant="secondary" className="text-xs">
              {signal}
            </Badge>
          ))}
        </div>
      )}

      {/* Outcome Stats Section */}
      <OutcomeStats
        recommendation={recommendation}
        showPeak={showPeak}
        onToggle={() => setShowPeak(!showPeak)}
      />
    </Card>
  );
}
```

**Step 3: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/components/recommendations/RecommendationCard.tsx
git commit -m "feat(recommendations): integrate accuracy display into recommendation cards"
```

---

## Phase 4: Command Palette

### Task 4.1: Install shadcn/ui Command Component

**Step 1: Install the component**

Run: `cd frontend && npx shadcn@latest add command dialog`

**Step 2: Verify installation**

Run: `ls frontend/src/components/ui/command.tsx frontend/src/components/ui/dialog.tsx`
Expected: Both files exist

**Step 3: Commit**

```bash
git add frontend/src/components/ui/command.tsx frontend/src/components/ui/dialog.tsx frontend/package.json frontend/package-lock.json
git commit -m "chore: add shadcn/ui command and dialog components"
```

---

### Task 4.2: Search Query Parser

**Files:**
- Create: `frontend/src/lib/search/parseSearchQuery.ts`

**Step 1: Create the parser**

```typescript
// frontend/src/lib/search/parseSearchQuery.ts
export interface SearchParams {
  name?: string;
  setCode?: string;
  cardType?: string;
  priceMin?: number;
  priceMax?: number;
  rarity?: string;
  colors?: string;
}

export function parseSearchQuery(query: string): SearchParams {
  const params: SearchParams = {};

  // Define operator patterns
  const operators: Record<string, RegExp> = {
    set: /set:(\w+)/i,
    type: /type:(\w+)/i,
    price: /price:([<>]?\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?)/i,
    rarity: /rarity:(\w+)/i,
    color: /color:([wubrgc]+)/i,
  };

  let remaining = query;

  // Parse set:
  const setMatch = query.match(operators.set);
  if (setMatch) {
    params.setCode = setMatch[1].toUpperCase();
    remaining = remaining.replace(setMatch[0], '');
  }

  // Parse type:
  const typeMatch = query.match(operators.type);
  if (typeMatch) {
    params.cardType = typeMatch[1];
    remaining = remaining.replace(typeMatch[0], '');
  }

  // Parse price:
  const priceMatch = query.match(operators.price);
  if (priceMatch) {
    const priceStr = priceMatch[1];
    if (priceStr.includes('-')) {
      const [min, max] = priceStr.split('-').map(Number);
      params.priceMin = min;
      params.priceMax = max;
    } else if (priceStr.startsWith('<')) {
      params.priceMax = Number(priceStr.slice(1));
    } else if (priceStr.startsWith('>')) {
      params.priceMin = Number(priceStr.slice(1));
    } else {
      // Exact price (with 10% tolerance)
      const price = Number(priceStr);
      params.priceMin = price * 0.9;
      params.priceMax = price * 1.1;
    }
    remaining = remaining.replace(priceMatch[0], '');
  }

  // Parse rarity:
  const rarityMatch = query.match(operators.rarity);
  if (rarityMatch) {
    params.rarity = rarityMatch[1].toLowerCase();
    remaining = remaining.replace(rarityMatch[0], '');
  }

  // Parse color:
  const colorMatch = query.match(operators.color);
  if (colorMatch) {
    params.colors = colorMatch[1].toUpperCase();
    remaining = remaining.replace(colorMatch[0], '');
  }

  // Remaining text is the name search
  const nameQuery = remaining.trim();
  if (nameQuery) {
    params.name = nameQuery;
  }

  return params;
}
```

**Step 2: Add tests**

```typescript
// frontend/src/lib/search/__tests__/parseSearchQuery.test.ts
import { parseSearchQuery } from '../parseSearchQuery';

describe('parseSearchQuery', () => {
  it('parses simple name query', () => {
    expect(parseSearchQuery('lightning bolt')).toEqual({ name: 'lightning bolt' });
  });

  it('parses set operator', () => {
    expect(parseSearchQuery('force set:MH2')).toEqual({
      name: 'force',
      setCode: 'MH2'
    });
  });

  it('parses price range', () => {
    expect(parseSearchQuery('price:10-50')).toEqual({
      priceMin: 10,
      priceMax: 50
    });
  });

  it('parses price greater than', () => {
    expect(parseSearchQuery('price:>100')).toEqual({ priceMin: 100 });
  });

  it('parses multiple operators', () => {
    expect(parseSearchQuery('dragon set:M21 rarity:mythic color:R')).toEqual({
      name: 'dragon',
      setCode: 'M21',
      rarity: 'mythic',
      colors: 'R',
    });
  });
});
```

**Step 3: Verify tests pass**

Run: `cd frontend && npm test -- --testPathPattern=parseSearchQuery`
Expected: All tests pass

**Step 4: Commit**

```bash
git add frontend/src/lib/search/parseSearchQuery.ts frontend/src/lib/search/__tests__/parseSearchQuery.test.ts
git commit -m "feat(search): add search query parser with operators"
```

---

### Task 4.3: Card Preview Component

**Files:**
- Create: `frontend/src/components/command/CardPreview.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/command/CardPreview.tsx
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface Card {
  id: number;
  name: string;
  set_code: string;
  set_name: string;
  rarity: string;
  type_line?: string;
  oracle_text?: string;
  image_uri?: string;
  latest_price?: number;
  price_change_24h?: number;
}

interface CardPreviewProps {
  card: Card;
  className?: string;
}

export function CardPreview({ card, className }: CardPreviewProps) {
  return (
    <div className={cn(
      'w-72 bg-surface border border-border rounded-lg shadow-xl p-4',
      className
    )}>
      {card.image_uri ? (
        <img
          src={card.image_uri}
          alt={card.name}
          className="w-full rounded-lg mb-3"
        />
      ) : (
        <div className="w-full h-64 bg-muted rounded-lg mb-3 flex items-center justify-center text-muted-foreground">
          No Image
        </div>
      )}

      <h3 className="font-bold text-lg">{card.name}</h3>
      <p className="text-sm text-muted-foreground mb-2">{card.type_line}</p>

      <div className="flex justify-between items-center mb-2">
        <span className="text-2xl font-bold text-accent">
          ${card.latest_price?.toFixed(2) || 'N/A'}
        </span>
        {card.price_change_24h !== undefined && card.price_change_24h !== null && (
          <span className={cn(
            'text-sm',
            card.price_change_24h >= 0 ? 'text-green-400' : 'text-red-400'
          )}>
            {card.price_change_24h >= 0 ? '+' : ''}{card.price_change_24h.toFixed(1)}%
          </span>
        )}
      </div>

      {card.oracle_text && (
        <p className="text-xs text-muted-foreground line-clamp-3 mb-3">
          {card.oracle_text}
        </p>
      )}

      <div className="flex gap-2">
        <Badge variant="outline">{card.set_code}</Badge>
        <Badge variant="outline" className={getRarityColor(card.rarity)}>
          {card.rarity}
        </Badge>
      </div>
    </div>
  );
}

function getRarityColor(rarity: string): string {
  switch (rarity.toLowerCase()) {
    case 'mythic':
      return 'text-orange-400 border-orange-400';
    case 'rare':
      return 'text-yellow-400 border-yellow-400';
    case 'uncommon':
      return 'text-gray-300 border-gray-300';
    default:
      return '';
  }
}
```

**Step 2: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/command/CardPreview.tsx
git commit -m "feat(command): add CardPreview component"
```

---

### Task 4.4: Command Palette Component

**Files:**
- Create: `frontend/src/components/command/CommandPalette.tsx`

**Step 1: Create the component**

```typescript
// frontend/src/components/command/CommandPalette.tsx
'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from '@/components/ui/command';
import {
  Home,
  Search,
  Library,
  TrendingUp,
  BarChart,
  Settings,
  Zap,
  History,
  Star,
  Copy,
} from 'lucide-react';
import { useDebounce } from '@/hooks/useDebounce';
import { parseSearchQuery } from '@/lib/search/parseSearchQuery';
import { CardPreview } from './CardPreview';
import { searchCards } from '@/lib/api/cards';
import { toast } from '@/hooks/useToast';

interface Card {
  id: number;
  name: string;
  set_code: string;
  set_name: string;
  rarity: string;
  image_uri?: string;
  latest_price?: number;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Card[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [previewCard, setPreviewCard] = useState<Card | null>(null);
  const router = useRouter();

  const debouncedQuery = useDebounce(query, 200);

  // Global keyboard shortcut
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };

    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  // Search with operators
  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < 2) {
      setSearchResults([]);
      return;
    }

    const search = async () => {
      setIsSearching(true);
      try {
        const params = parseSearchQuery(debouncedQuery);
        const results = await searchCards(params);
        setSearchResults(results.items || results);
      } catch (error) {
        console.error('Search failed:', error);
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    };

    search();
  }, [debouncedQuery]);

  const navigationCommands = [
    { name: 'Dashboard', shortcut: 'G D', path: '/dashboard', icon: Home },
    { name: 'Cards', shortcut: 'G C', path: '/cards', icon: Search },
    { name: 'Inventory', shortcut: 'G I', path: '/inventory', icon: Library },
    { name: 'Recommendations', shortcut: 'G R', path: '/recommendations', icon: TrendingUp },
    { name: 'Market', shortcut: 'G M', path: '/market', icon: BarChart },
    { name: 'Settings', shortcut: 'G S', path: '/settings', icon: Settings },
  ];

  const handleSelect = (card: Card) => {
    router.push(`/cards/${card.id}`);
    setOpen(false);
  };

  const copyToClipboard = (text: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    toast({ title: 'Copied to clipboard' });
  };

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder="Search cards, navigate, or type a command..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>
          {isSearching ? 'Searching...' : 'No results found. Try set:MH2 or price:>50'}
        </CommandEmpty>

        {/* Search Results */}
        {searchResults.length > 0 && (
          <CommandGroup heading="Cards">
            {searchResults.slice(0, 8).map((card) => (
              <CommandItem
                key={card.id}
                onSelect={() => handleSelect(card)}
                onMouseEnter={() => setPreviewCard(card)}
                onMouseLeave={() => setPreviewCard(null)}
                className="flex items-center justify-between"
              >
                <div className="flex items-center gap-2">
                  {card.image_uri && (
                    <img
                      src={card.image_uri}
                      alt={card.name}
                      className="w-8 h-11 rounded object-cover"
                    />
                  )}
                  <div>
                    <div className="font-medium">{card.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {card.set_name} - {card.rarity}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">
                    ${card.latest_price?.toFixed(2)}
                  </span>
                  <button
                    onClick={(e) => copyToClipboard(card.name, e)}
                    className="p-1 hover:bg-muted rounded"
                  >
                    <Copy className="w-3 h-3" />
                  </button>
                </div>
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        <CommandSeparator />

        {/* Navigation */}
        <CommandGroup heading="Navigation">
          {navigationCommands.map((cmd) => (
            <CommandItem
              key={cmd.path}
              onSelect={() => {
                router.push(cmd.path);
                setOpen(false);
              }}
            >
              <cmd.icon className="mr-2 h-4 w-4" />
              {cmd.name}
              <CommandShortcut>{cmd.shortcut}</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>

      {/* Card Preview Panel */}
      {previewCard && (
        <div className="absolute right-full mr-2 top-0">
          <CardPreview card={previewCard} />
        </div>
      )}
    </CommandDialog>
  );
}
```

**Step 2: Add useDebounce hook if not exists**

```typescript
// frontend/src/hooks/useDebounce.ts
import { useState, useEffect } from 'react';

export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}
```

**Step 3: Add to layout**

```typescript
// frontend/src/app/layout.tsx - Add CommandPalette to providers
import { CommandPalette } from '@/components/command/CommandPalette';

// In the layout, add:
// <CommandPalette />
```

**Step 4: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 5: Commit**

```bash
git add frontend/src/components/command/CommandPalette.tsx frontend/src/hooks/useDebounce.ts frontend/src/app/layout.tsx
git commit -m "feat(command): add full command palette with search and navigation"
```

---

### Task 4.5: Keyboard Shortcuts Hook

**Files:**
- Create: `frontend/src/hooks/useKeyboardShortcuts.ts`
- Modify: `frontend/src/app/layout.tsx`

**Step 1: Create the hook**

```typescript
// frontend/src/hooks/useKeyboardShortcuts.ts
'use client';

import { useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';

export function useKeyboardShortcuts() {
  const router = useRouter();

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Ignore if typing in an input
    if (
      e.target instanceof HTMLInputElement ||
      e.target instanceof HTMLTextAreaElement ||
      (e.target as HTMLElement).isContentEditable
    ) {
      return;
    }

    // G + key for navigation (vim-style)
    if (e.key === 'g' && !e.metaKey && !e.ctrlKey) {
      const handleNavKey = (navEvent: KeyboardEvent) => {
        const routes: Record<string, string> = {
          d: '/dashboard',
          c: '/cards',
          i: '/inventory',
          r: '/recommendations',
          m: '/market',
          s: '/settings',
        };

        const route = routes[navEvent.key.toLowerCase()];
        if (route) {
          navEvent.preventDefault();
          router.push(route);
        }

        document.removeEventListener('keydown', handleNavKey);
      };

      document.addEventListener('keydown', handleNavKey, { once: true });

      // Timeout to reset if no second key pressed
      setTimeout(() => {
        document.removeEventListener('keydown', handleNavKey);
      }, 1000);
    }

    // ? for help (show shortcuts modal)
    if (e.key === '?' && !e.metaKey && !e.ctrlKey && e.shiftKey) {
      e.preventDefault();
      // Dispatch custom event for shortcuts modal
      window.dispatchEvent(new CustomEvent('show-shortcuts-help'));
    }
  }, [router]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}
```

**Step 2: Create KeyboardShortcutsProvider**

```typescript
// frontend/src/components/KeyboardShortcutsProvider.tsx
'use client';

import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';

export function KeyboardShortcutsProvider({ children }: { children: React.ReactNode }) {
  useKeyboardShortcuts();
  return <>{children}</>;
}
```

**Step 3: Add to layout**

```typescript
// frontend/src/app/layout.tsx - Wrap with provider
import { KeyboardShortcutsProvider } from '@/components/KeyboardShortcutsProvider';

// Wrap children with:
// <KeyboardShortcutsProvider>
//   {children}
// </KeyboardShortcutsProvider>
```

**Step 4: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 5: Commit**

```bash
git add frontend/src/hooks/useKeyboardShortcuts.ts frontend/src/components/KeyboardShortcutsProvider.tsx frontend/src/app/layout.tsx
git commit -m "feat(shortcuts): add vim-style keyboard navigation shortcuts"
```

---

## Phase 5: Cleanup & Monitoring

### Task 5.1: Create Logger Utility

**Files:**
- Create: `frontend/src/lib/logger.ts`

**Step 1: Create the logger**

```typescript
// frontend/src/lib/logger.ts
const isDev = process.env.NODE_ENV === 'development';

export const logger = {
  debug: (...args: unknown[]) => {
    if (isDev) console.debug('[DEBUG]', ...args);
  },
  info: (...args: unknown[]) => {
    if (isDev) console.info('[INFO]', ...args);
  },
  warn: (...args: unknown[]) => {
    console.warn('[WARN]', ...args);
  },
  error: (...args: unknown[]) => {
    console.error('[ERROR]', ...args);
    // In production, could send to Sentry here
  },
};
```

**Step 2: Commit**

```bash
git add frontend/src/lib/logger.ts
git commit -m "feat: add logger utility for production-safe logging"
```

---

### Task 5.2: Remove Console.log Statements

**Files:**
- Modify: `frontend/src/contexts/WebSocketContext.tsx`
- Modify: `frontend/src/app/(public)/cards/[id]/page.tsx`
- Modify: `frontend/src/components/pwa/ServiceWorkerRegistration.tsx`
- Modify: `frontend/src/components/pwa/InstallPrompt.tsx`
- Modify: `frontend/src/components/layout/NotificationBell.tsx`

**Step 1: Find all console.log statements**

Run: `grep -rn "console.log" frontend/src --include="*.tsx" --include="*.ts" | grep -v node_modules | grep -v ".test."`

**Step 2: Replace with logger or remove**

For each file:
- Import logger: `import { logger } from '@/lib/logger';`
- Replace `console.log` with `logger.debug` or `logger.info`
- Replace `console.error` with `logger.error`
- Remove debug logs that aren't needed

**Step 3: Verify no console.log remains in production code**

Run: `grep -rn "console.log" frontend/src --include="*.tsx" --include="*.ts" | grep -v node_modules | grep -v ".test." | wc -l`
Expected: 0

**Step 4: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 5: Commit**

```bash
git add frontend/src/
git commit -m "chore: remove console.log statements, use logger utility"
```

---

### Task 5.3: Health Check Endpoint Enhancement

**Files:**
- Modify: `backend/app/api/routes/health.py`

**Step 1: Read current implementation**

Run: `cat backend/app/api/routes/health.py`

**Step 2: Enhance with component checks**

```python
# backend/app/api/routes/health.py
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.redis import redis_client

router = APIRouter()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint for monitoring."""
    components = {}

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        components["database"] = "healthy"
    except Exception as e:
        components["database"] = f"unhealthy: {str(e)[:50]}"

    # Check Redis
    try:
        await redis_client.ping()
        components["redis"] = "healthy"
    except Exception as e:
        components["redis"] = f"unhealthy: {str(e)[:50]}"

    # Overall status
    all_healthy = all(v == "healthy" for v in components.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": components,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",  # Could read from package
    }
```

**Step 3: Commit**

```bash
git add backend/app/api/routes/health.py
git commit -m "feat: enhance health check endpoint with component status"
```

---

## Phase 6: Notification Suite

### Task 6.1: Push Subscriptions Migration

**Files:**
- Create: `backend/alembic/versions/YYYYMMDD_add_push_subscriptions.py`

**Step 1: Create the migration**

Run: `docker compose exec backend alembic revision -m "add_push_subscriptions"`

**Step 2: Edit the migration**

```python
# backend/alembic/versions/YYYYMMDD_add_push_subscriptions.py
"""add_push_subscriptions

Revision ID: xxx
Revises: xxx
Create Date: xxx
"""
from alembic import op
import sqlalchemy as sa

revision = 'xxx'
down_revision = 'xxx'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'push_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.Text(), nullable=False),
        sa.Column('p256dh_key', sa.String(255), nullable=False),
        sa.Column('auth_key', sa.String(255), nullable=False),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('endpoint'),
    )
    op.create_index('ix_push_subscriptions_user_id', 'push_subscriptions', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_push_subscriptions_user_id')
    op.drop_table('push_subscriptions')
```

**Step 3: Run migration**

Run: `docker compose exec backend alembic upgrade head`

**Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(db): add push_subscriptions table"
```

---

### Task 6.2: Add Notification Preferences to User Model

**Files:**
- Create: `backend/alembic/versions/YYYYMMDD_add_notification_preferences.py`
- Modify: `backend/app/models/user.py`

**Step 1: Create the migration**

Run: `docker compose exec backend alembic revision -m "add_notification_preferences"`

**Step 2: Edit the migration**

```python
"""add_notification_preferences

Revision ID: xxx
Revises: xxx
Create Date: xxx
"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column('users', sa.Column('notify_price_alerts', sa.Boolean(), server_default='true'))
    op.add_column('users', sa.Column('notify_recommendations', sa.Boolean(), server_default='true'))
    op.add_column('users', sa.Column('notify_portfolio_updates', sa.Boolean(), server_default='true'))
    op.add_column('users', sa.Column('email_digest_frequency', sa.String(20), server_default='daily'))
    op.add_column('users', sa.Column('push_enabled', sa.Boolean(), server_default='true'))
    op.add_column('users', sa.Column('sound_enabled', sa.Boolean(), server_default='true'))


def downgrade() -> None:
    op.drop_column('users', 'sound_enabled')
    op.drop_column('users', 'push_enabled')
    op.drop_column('users', 'email_digest_frequency')
    op.drop_column('users', 'notify_portfolio_updates')
    op.drop_column('users', 'notify_recommendations')
    op.drop_column('users', 'notify_price_alerts')
```

**Step 3: Update User model**

```python
# backend/app/models/user.py - Add columns
class User(Base):
    # ... existing columns ...

    # Notification preferences
    notify_price_alerts = Column(Boolean, default=True, server_default='true')
    notify_recommendations = Column(Boolean, default=True, server_default='true')
    notify_portfolio_updates = Column(Boolean, default=True, server_default='true')
    email_digest_frequency = Column(String(20), default='daily', server_default='daily')
    push_enabled = Column(Boolean, default=True, server_default='true')
    sound_enabled = Column(Boolean, default=True, server_default='true')

    # Relationships
    push_subscriptions = relationship("PushSubscription", back_populates="user", cascade="all, delete-orphan")
```

**Step 4: Run migration**

Run: `docker compose exec backend alembic upgrade head`

**Step 5: Commit**

```bash
git add backend/alembic/versions/ backend/app/models/user.py
git commit -m "feat(db): add notification preferences to users table"
```

---

### Task 6.3: Push Subscription Model

**Files:**
- Create: `backend/app/models/push_subscription.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Create the model**

```python
# backend/app/models/push_subscription.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh_key = Column(String(255), nullable=False)
    auth_key = Column(String(255), nullable=False)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="push_subscriptions")
```

**Step 2: Add to models init**

```python
# backend/app/models/__init__.py - Add import
from app.models.push_subscription import PushSubscription
```

**Step 3: Commit**

```bash
git add backend/app/models/push_subscription.py backend/app/models/__init__.py
git commit -m "feat: add PushSubscription model"
```

---

### Task 6.4: Install pywebpush

**Step 1: Add to requirements**

```bash
echo "pywebpush>=2.0.0" >> backend/requirements.txt
```

**Step 2: Install**

Run: `docker compose exec backend pip install pywebpush`

**Step 3: Add VAPID config to settings**

```python
# backend/app/core/config.py - Add to Settings class
VAPID_PUBLIC_KEY: str = ""
VAPID_PRIVATE_KEY: str = ""
VAPID_EMAIL: str = "admin@dualcasterdeals.com"
```

**Step 4: Commit**

```bash
git add backend/requirements.txt backend/app/core/config.py
git commit -m "feat: add pywebpush dependency and VAPID config"
```

---

### Task 6.5: Push Notification Service

**Files:**
- Create: `backend/app/services/push_notifications.py`

**Step 1: Create the service**

```python
# backend/app/services/push_notifications.py
import json
import logging
from datetime import datetime
from pywebpush import webpush, WebPushException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)

async def send_push_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    body: str,
    data: dict | None = None,
    icon: str = "/icons/icon-192.png",
    badge: str = "/icons/badge-72.png",
) -> int:
    """
    Send push notification to all user's subscribed devices.
    Returns number of successfully sent notifications.
    """
    if not settings.VAPID_PRIVATE_KEY:
        logger.warning("VAPID keys not configured, skipping push notification")
        return 0

    result = await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )
    subscriptions = result.scalars().all()

    if not subscriptions:
        return 0

    payload = json.dumps({
        "title": title,
        "body": body,
        "icon": icon,
        "badge": badge,
        "data": data or {},
        "timestamp": datetime.utcnow().isoformat(),
    })

    failed_subscription_ids = []
    success_count = 0

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh_key,
                        "auth": sub.auth_key,
                    }
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": f"mailto:{settings.VAPID_EMAIL}"
                }
            )

            # Update last used timestamp
            sub.last_used_at = datetime.utcnow()
            success_count += 1

        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                # Subscription expired/invalid
                failed_subscription_ids.append(sub.id)
            else:
                logger.error(f"Push failed for subscription {sub.id}: {e}")

    # Remove failed subscriptions
    if failed_subscription_ids:
        await db.execute(
            delete(PushSubscription).where(PushSubscription.id.in_(failed_subscription_ids))
        )
        logger.info(f"Removed {len(failed_subscription_ids)} expired push subscriptions")

    await db.commit()
    return success_count
```

**Step 2: Commit**

```bash
git add backend/app/services/push_notifications.py
git commit -m "feat: add push notification service with pywebpush"
```

---

### Task 6.6: Notification API Routes

**Files:**
- Create: `backend/app/api/routes/notifications.py`
- Create: `backend/app/schemas/notification.py`
- Modify: `backend/app/api/__init__.py`

**Step 1: Create schemas**

```python
# backend/app/schemas/notification.py
from pydantic import BaseModel
from typing import Optional

class PushKeys(BaseModel):
    p256dh: str
    auth: str

class PushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: PushKeys
    user_agent: Optional[str] = None

class NotificationPreferences(BaseModel):
    priceAlerts: bool
    recommendations: bool
    portfolioUpdates: bool
    emailDigestFrequency: str  # none, daily, weekly
    pushEnabled: bool
    soundEnabled: bool
```

**Step 2: Create routes**

```python
# backend/app/api/routes/notifications.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.push_subscription import PushSubscription
from app.schemas.notification import PushSubscriptionCreate, NotificationPreferences

router = APIRouter()

@router.post("/push/subscribe")
async def subscribe_push(
    subscription: PushSubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register a push notification subscription."""
    # Check if subscription already exists
    result = await db.execute(
        select(PushSubscription).where(
            PushSubscription.endpoint == subscription.endpoint
        )
    )
    if result.scalar_one_or_none():
        return {"status": "already_subscribed"}

    new_sub = PushSubscription(
        user_id=current_user.id,
        endpoint=subscription.endpoint,
        p256dh_key=subscription.keys.p256dh,
        auth_key=subscription.keys.auth,
        user_agent=subscription.user_agent,
    )
    db.add(new_sub)
    await db.commit()

    return {"status": "subscribed"}


@router.delete("/push/unsubscribe")
async def unsubscribe_push(
    endpoint: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a push notification subscription."""
    await db.execute(
        delete(PushSubscription).where(
            PushSubscription.endpoint == endpoint,
            PushSubscription.user_id == current_user.id
        )
    )
    await db.commit()

    return {"status": "unsubscribed"}


@router.get("/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
):
    """Get user's notification preferences."""
    return NotificationPreferences(
        priceAlerts=current_user.notify_price_alerts,
        recommendations=current_user.notify_recommendations,
        portfolioUpdates=current_user.notify_portfolio_updates,
        emailDigestFrequency=current_user.email_digest_frequency,
        pushEnabled=current_user.push_enabled,
        soundEnabled=current_user.sound_enabled,
    )


@router.put("/preferences")
async def update_notification_preferences(
    preferences: NotificationPreferences,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user's notification preferences."""
    current_user.notify_price_alerts = preferences.priceAlerts
    current_user.notify_recommendations = preferences.recommendations
    current_user.notify_portfolio_updates = preferences.portfolioUpdates
    current_user.email_digest_frequency = preferences.emailDigestFrequency
    current_user.push_enabled = preferences.pushEnabled
    current_user.sound_enabled = preferences.soundEnabled

    await db.commit()

    return {"status": "updated"}
```

**Step 3: Register router**

```python
# backend/app/api/__init__.py - Add import and include
from app.api.routes import notifications
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
```

**Step 4: Commit**

```bash
git add backend/app/api/routes/notifications.py backend/app/schemas/notification.py backend/app/api/__init__.py
git commit -m "feat: add notification API routes"
```

---

### Task 6.7: Frontend Push Subscription Logic

**Files:**
- Create: `frontend/src/lib/pushNotifications.ts`

**Step 1: Create the push subscription module**

```typescript
// frontend/src/lib/pushNotifications.ts

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

function arrayBufferToBase64(buffer: ArrayBuffer | null): string {
  if (!buffer) return '';
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}

export async function subscribeToPush(token: string): Promise<boolean> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    console.warn('Push notifications not supported');
    return false;
  }

  const vapidKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
  if (!vapidKey) {
    console.warn('VAPID public key not configured');
    return false;
  }

  try {
    const registration = await navigator.serviceWorker.ready;

    // Check existing subscription
    let subscription = await registration.pushManager.getSubscription();

    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      });
    }

    // Send to backend
    const response = await fetch('/api/notifications/push/subscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        endpoint: subscription.endpoint,
        keys: {
          p256dh: arrayBufferToBase64(subscription.getKey('p256dh')),
          auth: arrayBufferToBase64(subscription.getKey('auth')),
        },
        userAgent: navigator.userAgent,
      }),
    });

    return response.ok;
  } catch (error) {
    console.error('Failed to subscribe to push:', error);
    return false;
  }
}

export async function unsubscribeFromPush(token: string): Promise<boolean> {
  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();

    if (subscription) {
      await subscription.unsubscribe();

      await fetch(`/api/notifications/push/unsubscribe?endpoint=${encodeURIComponent(subscription.endpoint)}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
    }

    return true;
  } catch (error) {
    console.error('Failed to unsubscribe from push:', error);
    return false;
  }
}

export async function isPushSubscribed(): Promise<boolean> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    return false;
  }

  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    return subscription !== null;
  } catch {
    return false;
  }
}
```

**Step 2: Commit**

```bash
git add frontend/src/lib/pushNotifications.ts
git commit -m "feat: add frontend push subscription logic"
```

---

### Task 6.8: Service Worker Push Handler

**Files:**
- Modify: `frontend/public/sw.js`

**Step 1: Add push handlers to service worker**

```javascript
// frontend/public/sw.js - Add these handlers

self.addEventListener('push', (event) => {
  const data = event.data?.json() || {};

  const options = {
    body: data.body || 'New notification from Dualcaster Deals',
    icon: data.icon || '/icons/icon-192.png',
    badge: data.badge || '/icons/badge-72.png',
    vibrate: [200, 100, 200],
    data: data.data || {},
    actions: data.actions || [],
    tag: data.tag || 'default',
    renotify: true,
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'Dualcaster Deals', options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const url = event.notification.data?.url || '/dashboard';

  event.waitUntil(
    clients.matchAll({ type: 'window' }).then((clientList) => {
      // Check if a window is already open
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      // Open new window
      return clients.openWindow(url);
    })
  );
});
```

**Step 2: Commit**

```bash
git add frontend/public/sw.js
git commit -m "feat: add push notification handlers to service worker"
```

---

### Task 6.9: Notification Preferences Settings Page

**Files:**
- Create: `frontend/src/app/(protected)/settings/notifications/page.tsx`

**Step 1: Create the settings page**

```typescript
// frontend/src/app/(protected)/settings/notifications/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Bell, Mail, Volume2, Smartphone } from 'lucide-react';
import { subscribeToPush, unsubscribeFromPush, isPushSubscribed } from '@/lib/pushNotifications';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from '@/hooks/useToast';

interface NotificationPreferences {
  priceAlerts: boolean;
  recommendations: boolean;
  portfolioUpdates: boolean;
  emailDigestFrequency: string;
  pushEnabled: boolean;
  soundEnabled: boolean;
}

export default function NotificationSettingsPage() {
  const { token } = useAuth();
  const [preferences, setPreferences] = useState<NotificationPreferences>({
    priceAlerts: true,
    recommendations: true,
    portfolioUpdates: true,
    emailDigestFrequency: 'daily',
    pushEnabled: true,
    soundEnabled: true,
  });
  const [isPushSupported, setIsPushSupported] = useState(false);
  const [isPushActive, setIsPushActive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setIsPushSupported('PushManager' in window);
    fetchPreferences();
    checkPushStatus();
  }, []);

  async function fetchPreferences() {
    try {
      const response = await fetch('/api/notifications/preferences', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setPreferences(data);
      }
    } catch (error) {
      console.error('Failed to fetch preferences:', error);
    } finally {
      setLoading(false);
    }
  }

  async function checkPushStatus() {
    const subscribed = await isPushSubscribed();
    setIsPushActive(subscribed);
  }

  async function handlePushToggle(enabled: boolean) {
    if (!token) return;

    if (enabled) {
      const success = await subscribeToPush(token);
      if (!success) {
        toast({ title: 'Failed to enable push notifications', variant: 'destructive' });
        return;
      }
      setIsPushActive(true);
    } else {
      await unsubscribeFromPush(token);
      setIsPushActive(false);
    }

    setPreferences(prev => ({ ...prev, pushEnabled: enabled }));
  }

  async function savePreferences() {
    setSaving(true);
    try {
      const response = await fetch('/api/notifications/preferences', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(preferences),
      });

      if (response.ok) {
        toast({ title: 'Preferences saved' });
      } else {
        throw new Error('Failed to save');
      }
    } catch (error) {
      toast({ title: 'Failed to save preferences', variant: 'destructive' });
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="container max-w-2xl py-8">Loading...</div>;
  }

  return (
    <div className="container max-w-2xl py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Notification Settings</h1>
        <p className="text-muted-foreground">
          Manage how and when you receive notifications
        </p>
      </div>

      {/* Notification Types */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notification Types
          </CardTitle>
          <CardDescription>
            Choose what you want to be notified about
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Price Alerts</div>
              <div className="text-sm text-muted-foreground">
                Get notified when cards hit your target prices
              </div>
            </div>
            <Switch
              checked={preferences.priceAlerts}
              onCheckedChange={(checked) =>
                setPreferences(prev => ({ ...prev, priceAlerts: checked }))
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Trading Recommendations</div>
              <div className="text-sm text-muted-foreground">
                New buy/sell signals for your inventory
              </div>
            </div>
            <Switch
              checked={preferences.recommendations}
              onCheckedChange={(checked) =>
                setPreferences(prev => ({ ...prev, recommendations: checked }))
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Portfolio Updates</div>
              <div className="text-sm text-muted-foreground">
                Significant changes to your collection value
              </div>
            </div>
            <Switch
              checked={preferences.portfolioUpdates}
              onCheckedChange={(checked) =>
                setPreferences(prev => ({ ...prev, portfolioUpdates: checked }))
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* Delivery Methods */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Smartphone className="h-5 w-5" />
            Delivery Methods
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Push Notifications</div>
              <div className="text-sm text-muted-foreground">
                Instant alerts on your device
              </div>
            </div>
            <Switch
              checked={preferences.pushEnabled && isPushActive}
              onCheckedChange={handlePushToggle}
              disabled={!isPushSupported}
            />
          </div>
          {!isPushSupported && (
            <p className="text-sm text-yellow-500">
              Push notifications are not supported in this browser
            </p>
          )}

          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium flex items-center gap-2">
                <Volume2 className="h-4 w-4" />
                Sound & Vibration
              </div>
              <div className="text-sm text-muted-foreground">
                Audio feedback for notifications
              </div>
            </div>
            <Switch
              checked={preferences.soundEnabled}
              onCheckedChange={(checked) =>
                setPreferences(prev => ({ ...prev, soundEnabled: checked }))
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* Email Digests */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Email Digests
          </CardTitle>
          <CardDescription>
            Summary emails with your market activity
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Digest Frequency</div>
              <div className="text-sm text-muted-foreground">
                How often to receive email summaries
              </div>
            </div>
            <Select
              value={preferences.emailDigestFrequency}
              onValueChange={(value) =>
                setPreferences(prev => ({ ...prev, emailDigestFrequency: value }))
              }
            >
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Never</SelectItem>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Button
        onClick={savePreferences}
        disabled={saving}
        className="w-full"
      >
        {saving ? 'Saving...' : 'Save Preferences'}
      </Button>
    </div>
  );
}
```

**Step 2: Verify build succeeds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/app/(protected)/settings/notifications/page.tsx
git commit -m "feat: add notification preferences settings page"
```

---

### Task 6.10: Email Digest Celery Task

**Files:**
- Create: `backend/app/tasks/notifications.py`
- Modify: `backend/app/tasks/celery_app.py`

**Step 1: Create the notification tasks**

```python
# backend/app/tasks/notifications.py
import logging
from datetime import datetime, timedelta
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)

@shared_task
def send_daily_digests():
    """Send daily email digests to subscribed users."""
    db = SessionLocal()

    try:
        result = db.execute(
            select(User).where(User.email_digest_frequency == "daily")
        )
        users = result.scalars().all()

        sent_count = 0
        for user in users:
            digest = generate_digest(db, user, days=1)

            if digest and digest.get('has_content'):
                # TODO: Implement actual email sending (SendGrid/SES)
                logger.info(f"Would send daily digest to {user.email}")
                sent_count += 1

        logger.info(f"Processed {len(users)} users, sent {sent_count} daily digests")
        return {"processed": len(users), "sent": sent_count}

    finally:
        db.close()


@shared_task
def send_weekly_digests():
    """Send weekly email digests to subscribed users."""
    db = SessionLocal()

    try:
        result = db.execute(
            select(User).where(User.email_digest_frequency == "weekly")
        )
        users = result.scalars().all()

        sent_count = 0
        for user in users:
            digest = generate_digest(db, user, days=7)

            if digest and digest.get('has_content'):
                # TODO: Implement actual email sending
                logger.info(f"Would send weekly digest to {user.email}")
                sent_count += 1

        logger.info(f"Processed {len(users)} users, sent {sent_count} weekly digests")
        return {"processed": len(users), "sent": sent_count}

    finally:
        db.close()


def generate_digest(db: Session, user: User, days: int = 1) -> dict:
    """Generate digest content for a user."""
    since = datetime.utcnow() - timedelta(days=days)

    # Placeholder - would query actual data
    return {
        "has_content": False,  # Set to True when there's content to send
        "portfolio_change": None,
        "price_alerts_triggered": [],
        "new_recommendations": [],
        "top_movers": [],
    }
```

**Step 2: Register in Celery beat**

```python
# backend/app/tasks/celery_app.py - Add to beat_schedule
from celery.schedules import crontab

beat_schedule = {
    # ... existing tasks ...

    "send-daily-digests": {
        "task": "app.tasks.notifications.send_daily_digests",
        "schedule": crontab(hour=8, minute=0),  # 8 AM UTC
        "options": {"queue": "default"},
    },
    "send-weekly-digests": {
        "task": "app.tasks.notifications.send_weekly_digests",
        "schedule": crontab(day_of_week=1, hour=8, minute=0),  # Monday 8 AM
        "options": {"queue": "default"},
    },
}
```

**Step 3: Commit**

```bash
git add backend/app/tasks/notifications.py backend/app/tasks/celery_app.py
git commit -m "feat: add email digest Celery tasks"
```

---

## Final Verification

### Verification Checklist

After completing all tasks, verify:

**Security:**
- [ ] OAuth callback no longer exposes token in URL
- [ ] Auth code exchange works end-to-end
- [ ] WebSocket connects with message-based auth
- [ ] OAuth users have non-empty passwords

**SEO:**
- [ ] Landing page has proper metadata
- [ ] Card pages have dynamic metadata
- [ ] OG images generate correctly
- [ ] Sitemap accessible at /sitemap.xml

**Recommendations:**
- [ ] Accuracy badges display on evaluated recommendations
- [ ] Peak/End toggle works
- [ ] Calibration indicator shows correct data

**Command Palette:**
- [ ] Cmd+K opens palette
- [ ] Search with operators works
- [ ] Navigation shortcuts work (G D, G C, etc.)

**Notifications:**
- [ ] Push subscription saves to database
- [ ] Service worker receives push events
- [ ] Settings page saves preferences

**Cleanup:**
- [ ] No console.log in production build
- [ ] Health endpoint returns component status

---

## Execution

Plan complete and saved to `docs/plans/2025-12-30-production-polish-plan.md`.

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
