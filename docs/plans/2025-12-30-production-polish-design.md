# Production Polish Design

**Date:** 2025-12-30
**Status:** Draft
**Author:** Claude + User

## Overview

Final production polish to make the platform advertisement-ready. Covers security hardening, SEO optimization, UI enhancements, and notification infrastructure.

### Goals
- Fix remaining security vulnerabilities (OAuth token exposure, WebSocket auth)
- Maximize SEO for card pages and discoverability
- Surface recommendation accuracy data to build user trust
- Add power-user command palette for efficient navigation
- Complete notification infrastructure (push + email)
- Clean up console.log statements and add monitoring

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| OAuth security | Authorization code exchange | Tokens never in URL/history, 30s TTL prevents replay |
| WebSocket auth | Token in first message | Avoids query string exposure in logs |
| OAuth password | Random 32-char unusable | Blocks password login for OAuth users |
| SEO approach | Hybrid static + dynamic | Static for landing/auth, dynamic for cards/market |
| Structured data | JSON-LD | Best for Google rich snippets, easy to maintain |
| OG images | Dynamic generation | Eye-catching card previews drive social clicks |
| Accuracy display | Card integration + history | Immediate feedback + detailed analysis |
| Command palette | Full command center | Power users expect comprehensive shortcuts |
| Notifications | Full suite (push + email) | Multiple channels for different urgency levels |

---

## Section 1: Security Fixes

### 1.1 Authorization Code Exchange

**Problem:** OAuth callback currently passes JWT token in URL, exposing it in browser history and server logs.

**Solution:** Two-step exchange with temporary authorization code.

```
Current (insecure):
  Google → /auth/callback?token=eyJhbG... → Frontend stores token

New (secure):
  Google → /auth/callback?code=abc123 → Frontend exchanges code for token
```

**Backend Implementation:**

```python
# backend/app/api/routes/oauth.py

import secrets
from app.core.redis import redis_client

@router.get("/google/callback")
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    # ... existing OAuth flow to get user ...

    # Generate short-lived auth code
    auth_code = secrets.token_urlsafe(32)

    # Store in Redis with 30-second TTL
    await redis_client.setex(
        f"auth_code:{auth_code}",
        30,  # 30 seconds
        json.dumps({"user_id": user.id, "access_token": access_token})
    )

    # Redirect with code (not token)
    return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?code={auth_code}")


@router.post("/exchange")
async def exchange_code(code: str = Body(..., embed=True)):
    """Exchange authorization code for JWT token."""
    # Retrieve and delete (one-time use)
    data = await redis_client.getdel(f"auth_code:{code}")

    if not data:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    payload = json.loads(data)
    return {"access_token": payload["access_token"], "token_type": "bearer"}
```

**Frontend Implementation:**

```typescript
// frontend/src/app/auth/callback/page.tsx

export default function AuthCallback() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { login } = useAuth();

  useEffect(() => {
    const code = searchParams.get('code');
    if (code) {
      exchangeCode(code);
    }
  }, [searchParams]);

  async function exchangeCode(code: string) {
    try {
      const response = await fetch('/api/auth/exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });

      if (!response.ok) throw new Error('Exchange failed');

      const { access_token } = await response.json();
      login(access_token);
      router.push('/dashboard');
    } catch (error) {
      router.push('/login?error=auth_failed');
    }
  }

  return <LoadingSpinner message="Completing sign in..." />;
}
```

### 1.2 WebSocket Authentication Fix

**Problem:** Token currently passed in WebSocket URL query string, visible in logs.

**Solution:** Send token as first message after connection.

```python
# backend/app/api/routes/websocket.py

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        # Wait for auth message (5 second timeout)
        auth_message = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=5.0
        )

        if auth_message.get("type") != "auth":
            await websocket.close(code=4001, reason="Expected auth message")
            return

        token = auth_message.get("token")
        user = await verify_token(token)

        if not user:
            await websocket.close(code=4003, reason="Invalid token")
            return

        # Authenticated - proceed with normal message handling
        await websocket.send_json({"type": "auth_success"})
        await handle_authenticated_connection(websocket, user)

    except asyncio.TimeoutError:
        await websocket.close(code=4002, reason="Auth timeout")
```

```typescript
// frontend/src/contexts/WebSocketContext.tsx

function connect() {
  const ws = new WebSocket(WS_URL);  // No token in URL

  ws.onopen = () => {
    // Send auth as first message
    ws.send(JSON.stringify({
      type: 'auth',
      token: getAccessToken()
    }));
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'auth_success') {
      setIsAuthenticated(true);
    }
    // ... handle other messages
  };
}
```

### 1.3 OAuth User Password

**Problem:** OAuth users created with empty password could theoretically be exploited.

**Solution:** Set random unusable password on OAuth user creation.

```python
# backend/app/services/auth.py

import secrets

async def get_or_create_oauth_user(email: str, provider: str, ...):
    user = await get_user_by_email(db, email)

    if not user:
        # Generate random password that can never be used
        random_password = secrets.token_urlsafe(32)

        user = User(
            email=email,
            hashed_password=get_password_hash(random_password),
            oauth_provider=provider,
            # ... other fields
        )
```

### 1.4 Username Validation

**Problem:** Usernames could contain invalid characters or be too short/long.

**Solution:** Add validation schema.

```python
# backend/app/schemas/user.py

from pydantic import Field, field_validator
import re

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        if v.startswith(('_', '-')) or v.endswith(('_', '-')):
            raise ValueError('Username cannot start or end with underscore or hyphen')
        return v
```

---

## Section 2: SEO Metadata

### 2.1 Static Page Metadata

**Landing, Login, Register pages:**

```typescript
// frontend/src/app/page.tsx

import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Dualcaster Deals - MTG Price Intelligence',
  description: 'Track Magic: The Gathering card prices across TCGPlayer, CardTrader, and more. Get buy/sell recommendations powered by market analytics.',
  keywords: ['MTG', 'Magic: The Gathering', 'card prices', 'TCGPlayer', 'price tracker'],
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
```

### 2.2 Dynamic Card Page Metadata

```typescript
// frontend/src/app/(public)/cards/[id]/page.tsx

import type { Metadata } from 'next';
import { getCard } from '@/lib/api/cards';

interface Props {
  params: { id: string };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const card = await getCard(parseInt(params.id));

  if (!card) {
    return { title: 'Card Not Found' };
  }

  const price = card.latestPrice ? `$${card.latestPrice.toFixed(2)}` : 'Price unavailable';
  const title = `${card.name} - ${price} | Dualcaster Deals`;
  const description = `${card.name} from ${card.setName}. Current price: ${price}. View price history, market trends, and trading recommendations.`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `https://dualcasterdeals.com/cards/${card.id}`,
      images: [
        {
          url: `/api/og/card/${card.id}`,  // Dynamic OG image
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
}
```

### 2.3 JSON-LD Structured Data

```typescript
// frontend/src/components/seo/CardJsonLd.tsx

interface CardJsonLdProps {
  card: Card;
}

export function CardJsonLd({ card }: CardJsonLdProps) {
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: card.name,
    description: card.oracleText || `${card.name} - ${card.typeLine}`,
    image: card.imageUri,
    sku: card.scryfallId,
    brand: {
      '@type': 'Brand',
      name: 'Magic: The Gathering',
    },
    offers: card.latestPrice ? {
      '@type': 'AggregateOffer',
      priceCurrency: 'USD',
      lowPrice: card.latestPrice,
      highPrice: card.latestPrice,
      offerCount: 1,
      availability: 'https://schema.org/InStock',
    } : undefined,
    additionalProperty: [
      { '@type': 'PropertyValue', name: 'Set', value: card.setName },
      { '@type': 'PropertyValue', name: 'Rarity', value: card.rarity },
      { '@type': 'PropertyValue', name: 'Mana Cost', value: card.manaCost },
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}

// Usage in card page:
// <CardJsonLd card={card} />
```

### 2.4 Dynamic OG Image Generation

```typescript
// frontend/src/app/api/og/card/[id]/route.tsx

import { ImageResponse } from 'next/og';
import { getCard } from '@/lib/api/cards';

export const runtime = 'edge';

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const card = await getCard(parseInt(params.id));

  if (!card) {
    return new Response('Card not found', { status: 404 });
  }

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
          <img
            src={card.imageUri}
            alt={card.name}
            style={{
              width: 300,
              height: 420,
              borderRadius: 16,
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            }}
          />
        </div>

        {/* Card info */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <div style={{ fontSize: 48, fontWeight: 'bold', color: '#FFFFFF', marginBottom: 16 }}>
            {card.name}
          </div>
          <div style={{ fontSize: 28, color: '#9CA3AF', marginBottom: 32 }}>
            {card.setName} - {card.rarity}
          </div>
          <div style={{ fontSize: 64, fontWeight: 'bold', color: '#22C55E' }}>
            ${card.latestPrice?.toFixed(2) || 'N/A'}
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
}
```

### 2.5 Sitemap Generation

```typescript
// frontend/src/app/sitemap.ts

import type { MetadataRoute } from 'next';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = 'https://dualcasterdeals.com';

  // Static pages
  const staticPages = [
    { url: baseUrl, lastModified: new Date(), changeFrequency: 'daily' as const, priority: 1 },
    { url: `${baseUrl}/login`, lastModified: new Date(), changeFrequency: 'monthly' as const, priority: 0.5 },
    { url: `${baseUrl}/register`, lastModified: new Date(), changeFrequency: 'monthly' as const, priority: 0.5 },
    { url: `${baseUrl}/cards`, lastModified: new Date(), changeFrequency: 'daily' as const, priority: 0.9 },
    { url: `${baseUrl}/market`, lastModified: new Date(), changeFrequency: 'hourly' as const, priority: 0.8 },
  ];

  // Dynamic card pages (fetch top cards by popularity/price)
  const topCards = await fetchTopCards(1000);  // Top 1000 cards
  const cardPages = topCards.map((card) => ({
    url: `${baseUrl}/cards/${card.id}`,
    lastModified: card.updatedAt,
    changeFrequency: 'daily' as const,
    priority: 0.7,
  }));

  return [...staticPages, ...cardPages];
}

async function fetchTopCards(limit: number) {
  // Fetch from API - prioritize high-value and popular cards
  const response = await fetch(
    `${process.env.BACKEND_URL}/api/cards?sort=-price&limit=${limit}`,
    { next: { revalidate: 86400 } }  // Revalidate daily
  );
  return response.json();
}
```

---

## Section 3: Recommendation Accuracy Display

### 3.1 Accuracy Badges on Recommendation Cards

```typescript
// frontend/src/components/recommendations/AccuracyBadge.tsx

interface AccuracyBadgeProps {
  accuracy: number | null;
  isPeak?: boolean;
}

export function AccuracyBadge({ accuracy, isPeak = false }: AccuracyBadgeProps) {
  if (accuracy === null) {
    return (
      <Badge variant="secondary" className="text-xs">
        <Clock className="w-3 h-3 mr-1" />
        Pending
      </Badge>
    );
  }

  const { color, icon: Icon, label } = getAccuracyDisplay(accuracy);

  return (
    <Badge className={cn('text-xs', color)}>
      <Icon className="w-3 h-3 mr-1" />
      {isPeak ? 'Peak ' : ''}{Math.round(accuracy * 100)}%
      <span className="ml-1 text-xs opacity-75">{label}</span>
    </Badge>
  );
}

function getAccuracyDisplay(accuracy: number) {
  if (accuracy >= 0.9) {
    return { color: 'bg-green-500/20 text-green-400', icon: CheckCircle, label: 'Hit target' };
  } else if (accuracy >= 0.5) {
    return { color: 'bg-yellow-500/20 text-yellow-400', icon: TrendingUp, label: 'Partial' };
  } else {
    return { color: 'bg-red-500/20 text-red-400', icon: XCircle, label: 'Missed' };
  }
}
```

### 3.2 Outcome Stats Section

```typescript
// frontend/src/components/recommendations/OutcomeStats.tsx

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
          <ToggleLeft className={cn('w-3 h-3', showPeak && 'text-accent')} />
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
          <div className={cn('font-medium', profit >= 0 ? 'text-green-400' : 'text-red-400')}>
            {profit >= 0 ? '+' : ''}{profit?.toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="text-muted-foreground text-xs">Accuracy</div>
          <AccuracyBadge accuracy={accuracy} isPeak={showPeak} />
        </div>
      </div>

      {/* Peak info when showing end */}
      {!showPeak && recommendation.accuracyScorePeak > recommendation.accuracyScoreEnd && (
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

### 3.3 Confidence Calibration Indicator

Shows whether high-confidence recommendations actually perform better:

```typescript
// frontend/src/components/recommendations/ConfidenceCalibration.tsx

interface ConfidenceCalibrationProps {
  stats: {
    highConfidenceAccuracy: number;  // avg accuracy for confidence > 0.8
    lowConfidenceAccuracy: number;   // avg accuracy for confidence < 0.5
    totalEvaluated: number;
  };
}

export function ConfidenceCalibration({ stats }: ConfidenceCalibrationProps) {
  const isCalibrated = stats.highConfidenceAccuracy > stats.lowConfidenceAccuracy;

  return (
    <Card className="p-4">
      <h3 className="text-sm font-medium mb-2">Confidence Calibration</h3>
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span>High confidence (&gt;80%)</span>
          <span className="font-medium">{Math.round(stats.highConfidenceAccuracy * 100)}% accurate</span>
        </div>
        <div className="flex justify-between text-sm">
          <span>Low confidence (&lt;50%)</span>
          <span className="font-medium">{Math.round(stats.lowConfidenceAccuracy * 100)}% accurate</span>
        </div>
        <div className={cn(
          'text-xs mt-2 p-2 rounded',
          isCalibrated ? 'bg-green-500/10 text-green-400' : 'bg-yellow-500/10 text-yellow-400'
        )}>
          {isCalibrated
            ? 'Confidence scores are well-calibrated'
            : 'Confidence needs recalibration'}
        </div>
      </div>
      <div className="text-xs text-muted-foreground mt-2">
        Based on {stats.totalEvaluated} evaluated recommendations
      </div>
    </Card>
  );
}
```

### 3.4 Recent Hits Ticker

Scrolling banner of recently successful predictions:

```typescript
// frontend/src/components/recommendations/RecentHitsTicker.tsx

interface RecentHit {
  cardName: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  accuracy: number;
  profit: number;
  evaluatedAt: string;
}

export function RecentHitsTicker({ hits }: { hits: RecentHit[] }) {
  // Filter to only show hits with accuracy >= 0.8
  const successfulHits = hits.filter(h => h.accuracy >= 0.8);

  if (successfulHits.length === 0) return null;

  return (
    <div className="overflow-hidden bg-green-500/5 border-y border-green-500/20 py-2">
      <div className="animate-scroll-x flex gap-8 whitespace-nowrap">
        {successfulHits.map((hit, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <CheckCircle className="w-4 h-4 text-green-400" />
            <span className="font-medium">{hit.cardName}</span>
            <Badge variant="outline" className="text-xs">
              {hit.action}
            </Badge>
            <span className="text-green-400">+{hit.profit.toFixed(1)}%</span>
            <span className="text-muted-foreground text-xs">
              {formatRelativeTime(hit.evaluatedAt)}
            </span>
          </div>
        ))}
        {/* Duplicate for seamless loop */}
        {successfulHits.map((hit, i) => (
          <div key={`dup-${i}`} className="flex items-center gap-2 text-sm">
            <CheckCircle className="w-4 h-4 text-green-400" />
            <span className="font-medium">{hit.cardName}</span>
            <Badge variant="outline" className="text-xs">
              {hit.action}
            </Badge>
            <span className="text-green-400">+{hit.profit.toFixed(1)}%</span>
            <span className="text-muted-foreground text-xs">
              {formatRelativeTime(hit.evaluatedAt)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## Section 4: Command Palette

### 4.1 Core Command Palette Component

Using shadcn/ui `<Command>` component:

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
import { useDebounce } from '@/hooks/useDebounce';
import { searchCards } from '@/lib/api/cards';
import { CardPreview } from './CardPreview';

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Card[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [previewCard, setPreviewCard] = useState<Card | null>(null);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [favorites, setFavorites] = useState<Card[]>([]);
  const router = useRouter();

  const debouncedQuery = useDebounce(query, 200);

  // Global keyboard shortcut
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
      // Escape to close
      if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };

    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, [open]);

  // Search with operators
  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < 2) {
      setSearchResults([]);
      return;
    }

    const search = async () => {
      setIsSearching(true);
      const params = parseSearchQuery(debouncedQuery);
      const results = await searchCards(params);
      setSearchResults(results);
      setIsSearching(false);
    };

    search();
  }, [debouncedQuery]);

  // Navigation shortcuts
  const navigationCommands = [
    { name: 'Dashboard', shortcut: 'G D', path: '/dashboard', icon: Home },
    { name: 'Cards', shortcut: 'G C', path: '/cards', icon: Search },
    { name: 'Inventory', shortcut: 'G I', path: '/inventory', icon: Library },
    { name: 'Recommendations', shortcut: 'G R', path: '/recommendations', icon: TrendingUp },
    { name: 'Market', shortcut: 'G M', path: '/market', icon: BarChart },
    { name: 'Settings', shortcut: 'G S', path: '/settings', icon: Settings },
  ];

  // Action commands
  const actionCommands = [
    { name: 'Add Card to Inventory', shortcut: 'A', action: () => openAddModal() },
    { name: 'Import Collection', shortcut: 'I', action: () => router.push('/imports') },
    { name: 'Export Inventory', shortcut: 'E', action: () => exportInventory() },
    { name: 'Refresh Prices', shortcut: 'R', action: () => refreshPrices() },
    { name: 'Toggle Theme', shortcut: 'T', action: () => toggleTheme() },
  ];

  const handleSelect = (card: Card) => {
    addToRecent(card.name);
    router.push(`/cards/${card.id}`);
    setOpen(false);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
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
          {isSearching ? 'Searching...' : 'No results found.'}
        </CommandEmpty>

        {/* Recent Searches */}
        {!query && recentSearches.length > 0 && (
          <CommandGroup heading="Recent">
            {recentSearches.slice(0, 3).map((search) => (
              <CommandItem key={search} onSelect={() => setQuery(search)}>
                <History className="mr-2 h-4 w-4" />
                {search}
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        {/* Favorites */}
        {!query && favorites.length > 0 && (
          <CommandGroup heading="Favorites">
            {favorites.slice(0, 5).map((card) => (
              <CommandItem key={card.id} onSelect={() => handleSelect(card)}>
                <Star className="mr-2 h-4 w-4 text-yellow-400" />
                {card.name}
                <span className="ml-auto text-xs text-muted-foreground">
                  ${card.latestPrice?.toFixed(2)}
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        {/* Search Results */}
        {searchResults.length > 0 && (
          <CommandGroup heading="Cards">
            {searchResults.slice(0, 8).map((card) => (
              <CommandItem
                key={card.id}
                onSelect={() => handleSelect(card)}
                onMouseEnter={() => setPreviewCard(card)}
                onMouseLeave={() => setPreviewCard(null)}
              >
                <div className="flex items-center gap-2">
                  {card.imageUri && (
                    <img
                      src={card.imageUri}
                      alt={card.name}
                      className="w-8 h-11 rounded object-cover"
                    />
                  )}
                  <div>
                    <div className="font-medium">{card.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {card.setName} - {card.rarity}
                    </div>
                  </div>
                </div>
                <div className="ml-auto flex items-center gap-2">
                  <span className="text-sm font-medium">
                    ${card.latestPrice?.toFixed(2)}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      copyToClipboard(card.name);
                    }}
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

        {/* Actions */}
        <CommandGroup heading="Actions">
          {actionCommands.map((cmd) => (
            <CommandItem
              key={cmd.name}
              onSelect={() => {
                cmd.action();
                setOpen(false);
              }}
            >
              <Zap className="mr-2 h-4 w-4" />
              {cmd.name}
              <CommandShortcut>{cmd.shortcut}</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>

      {/* Card Preview Panel */}
      {previewCard && (
        <CardPreview card={previewCard} className="absolute right-full mr-2 top-0" />
      )}
    </CommandDialog>
  );
}
```

### 4.2 Search Operators Parser

```typescript
// frontend/src/lib/search/parseSearchQuery.ts

interface SearchParams {
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

  // Extract operators
  const operators: Record<string, RegExp> = {
    set: /set:(\w+)/i,
    type: /type:(\w+)/i,
    price: /price:([<>]?\d+(?:-\d+)?)/i,
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

// Examples:
// "force set:MH2 rarity:mythic" → { name: "force", setCode: "MH2", rarity: "mythic" }
// "price:>50 type:creature" → { priceMin: 50, cardType: "creature" }
// "lightning bolt price:1-5" → { name: "lightning bolt", priceMin: 1, priceMax: 5 }
```

### 4.3 Card Preview Component

```typescript
// frontend/src/components/command/CardPreview.tsx

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
      <img
        src={card.imageUri}
        alt={card.name}
        className="w-full rounded-lg mb-3"
      />
      <h3 className="font-bold text-lg">{card.name}</h3>
      <p className="text-sm text-muted-foreground mb-2">{card.typeLine}</p>

      <div className="flex justify-between items-center mb-2">
        <span className="text-2xl font-bold text-accent">
          ${card.latestPrice?.toFixed(2)}
        </span>
        {card.priceChange24h && (
          <span className={cn(
            'text-sm',
            card.priceChange24h >= 0 ? 'text-green-400' : 'text-red-400'
          )}>
            {card.priceChange24h >= 0 ? '+' : ''}{card.priceChange24h.toFixed(1)}%
          </span>
        )}
      </div>

      {card.oracleText && (
        <p className="text-xs text-muted-foreground line-clamp-3">
          {card.oracleText}
        </p>
      )}

      <div className="flex gap-2 mt-3">
        <Badge variant="outline">{card.setCode}</Badge>
        <Badge variant="outline" className={getRarityColor(card.rarity)}>
          {card.rarity}
        </Badge>
      </div>
    </div>
  );
}
```

### 4.4 Keyboard Shortcuts Hook

```typescript
// frontend/src/hooks/useKeyboardShortcuts.ts

import { useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';

export function useKeyboardShortcuts() {
  const router = useRouter();

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Ignore if typing in an input
    if (
      e.target instanceof HTMLInputElement ||
      e.target instanceof HTMLTextAreaElement
    ) {
      return;
    }

    // G + key for navigation
    if (e.key === 'g') {
      const handleNavKey = (navEvent: KeyboardEvent) => {
        const routes: Record<string, string> = {
          d: '/dashboard',
          c: '/cards',
          i: '/inventory',
          r: '/recommendations',
          m: '/market',
          s: '/settings',
        };

        if (routes[navEvent.key]) {
          navEvent.preventDefault();
          router.push(routes[navEvent.key]);
        }

        document.removeEventListener('keydown', handleNavKey);
      };

      document.addEventListener('keydown', handleNavKey, { once: true });

      // Timeout to reset
      setTimeout(() => {
        document.removeEventListener('keydown', handleNavKey);
      }, 1000);
    }

    // Single key shortcuts
    if (e.key === '?' && !e.metaKey && !e.ctrlKey) {
      // Show keyboard shortcuts help
      openShortcutsModal();
    }
  }, [router]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}
```

---

## Section 5: Cleanup & Monitoring

### 5.1 Console.log Removal

Remove all console.log statements from production code:

**Files to clean:**
- `frontend/src/contexts/WebSocketContext.tsx` (lines 172, 178, 200, 203)
- `frontend/src/app/(public)/cards/[id]/page.tsx` (line 147)
- `frontend/src/components/pwa/ServiceWorkerRegistration.tsx` (lines 13, 16)
- `frontend/src/components/pwa/InstallPrompt.tsx` (line 49)
- `frontend/src/components/layout/NotificationBell.tsx` (lines 203, 223, 242)

Replace with proper error handling or remove entirely. For debugging purposes, use a logger utility:

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
    // In production, could send to error tracking service
  },
};
```

### 5.2 UptimeRobot Monitoring

Set up external monitoring for:

| Endpoint | Check Type | Interval |
|----------|------------|----------|
| `https://dualcasterdeals.com` | HTTP | 5 min |
| `https://dualcasterdeals.com/api/health` | HTTP | 5 min |
| `https://api.dualcasterdeals.com/health` | HTTP | 5 min (if separate) |

**Health endpoint response:**

```python
# backend/app/api/routes/health.py

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint for monitoring."""
    try:
        # Check database
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    try:
        # Check Redis
        await redis_client.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"

    healthy = db_status == "healthy" and redis_status == "healthy"

    return {
        "status": "healthy" if healthy else "degraded",
        "database": db_status,
        "redis": redis_status,
        "timestamp": datetime.utcnow().isoformat(),
    }
```

---

## Section 6: Notification Suite

### 6.1 Database Model

```python
# backend/app/models/push_subscription.py

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.db.base import Base

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh_key = Column(String(255), nullable=False)
    auth_key = Column(String(255), nullable=False)
    user_agent = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="push_subscriptions")
```

```python
# Update backend/app/models/user.py

class User(Base):
    # ... existing fields ...

    # Notification preferences
    notify_price_alerts = Column(Boolean, default=True)
    notify_recommendations = Column(Boolean, default=True)
    notify_portfolio_updates = Column(Boolean, default=True)
    email_digest_frequency = Column(String(20), default="daily")  # none, daily, weekly
    push_enabled = Column(Boolean, default=True)
    sound_enabled = Column(Boolean, default=True)

    push_subscriptions = relationship("PushSubscription", back_populates="user")
```

### 6.2 VAPID Key Generation

```bash
# Generate VAPID keys (run once)
npx web-push generate-vapid-keys

# Add to .env:
# VAPID_PUBLIC_KEY=BGxV...
# VAPID_PRIVATE_KEY=uHYj...
# VAPID_EMAIL=admin@dualcasterdeals.com
```

### 6.3 Push Notification Service

```python
# backend/app/services/push_notifications.py

from pywebpush import webpush, WebPushException
from app.core.config import settings
from app.models.push_subscription import PushSubscription
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

async def send_push_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    body: str,
    data: dict | None = None,
    icon: str = "/icons/icon-192.png",
    badge: str = "/icons/badge-72.png",
):
    """Send push notification to all user's subscribed devices."""

    result = await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )
    subscriptions = result.scalars().all()

    payload = json.dumps({
        "title": title,
        "body": body,
        "icon": icon,
        "badge": badge,
        "data": data or {},
        "timestamp": datetime.utcnow().isoformat(),
    })

    failed_subscriptions = []

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

            # Update last used
            sub.last_used_at = datetime.utcnow()

        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                # Subscription expired/invalid - mark for removal
                failed_subscriptions.append(sub.id)
            else:
                logger.error(f"Push failed for {sub.id}: {e}")

    # Remove failed subscriptions
    if failed_subscriptions:
        await db.execute(
            delete(PushSubscription).where(PushSubscription.id.in_(failed_subscriptions))
        )

    await db.commit()
```

### 6.4 Push Subscription API

```python
# backend/app/api/routes/notifications.py

from fastapi import APIRouter, Depends, HTTPException
from app.schemas.notification import PushSubscriptionCreate, NotificationPreferences
from app.api.deps import get_current_user, get_db

router = APIRouter()

@router.post("/push/subscribe")
async def subscribe_push(
    subscription: PushSubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register a push notification subscription."""

    # Check if subscription already exists
    existing = await db.execute(
        select(PushSubscription).where(
            PushSubscription.endpoint == subscription.endpoint
        )
    )
    if existing.scalar_one_or_none():
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
    return {
        "priceAlerts": current_user.notify_price_alerts,
        "recommendations": current_user.notify_recommendations,
        "portfolioUpdates": current_user.notify_portfolio_updates,
        "emailDigestFrequency": current_user.email_digest_frequency,
        "pushEnabled": current_user.push_enabled,
        "soundEnabled": current_user.sound_enabled,
    }


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

### 6.5 Frontend Push Subscription

```typescript
// frontend/src/lib/pushNotifications.ts

const VAPID_PUBLIC_KEY = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY!;

export async function subscribeToPush(): Promise<boolean> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    console.warn('Push notifications not supported');
    return false;
  }

  try {
    const registration = await navigator.serviceWorker.ready;

    // Check existing subscription
    let subscription = await registration.pushManager.getSubscription();

    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      });
    }

    // Send to backend
    const response = await fetch('/api/notifications/push/subscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getAccessToken()}`,
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

export async function unsubscribeFromPush(): Promise<boolean> {
  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();

    if (subscription) {
      await subscription.unsubscribe();

      await fetch('/api/notifications/push/unsubscribe', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getAccessToken()}`,
        },
        body: JSON.stringify({ endpoint: subscription.endpoint }),
      });
    }

    return true;
  } catch (error) {
    console.error('Failed to unsubscribe from push:', error);
    return false;
  }
}
```

### 6.6 Service Worker Push Handler

```javascript
// frontend/public/sw.js (additions)

self.addEventListener('push', (event) => {
  const data = event.data?.json() || {};

  const options = {
    body: data.body || 'New notification',
    icon: data.icon || '/icons/icon-192.png',
    badge: data.badge || '/icons/badge-72.png',
    vibrate: [200, 100, 200],  // Vibration pattern
    data: data.data || {},
    actions: data.actions || [],
    tag: data.tag || 'default',  // Group similar notifications
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
      // Focus existing window or open new
      for (const client of clientList) {
        if (client.url.includes(url) && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
```

### 6.7 Email Digest Task

```python
# backend/app/tasks/notifications.py

from celery import shared_task
from app.db.session import get_db_sync
from app.services.email import send_email
from app.models.user import User
from sqlalchemy import select

@shared_task
def send_daily_digests():
    """Send daily email digests to subscribed users."""
    db = get_db_sync()

    try:
        # Get users with daily digest enabled
        result = db.execute(
            select(User).where(User.email_digest_frequency == "daily")
        )
        users = result.scalars().all()

        for user in users:
            digest_content = generate_digest(db, user)

            if digest_content:  # Only send if there's content
                send_email(
                    to=user.email,
                    subject="Your Daily MTG Market Digest",
                    template="daily_digest",
                    context={
                        "user": user,
                        "digest": digest_content,
                    }
                )

    finally:
        db.close()


def generate_digest(db, user):
    """Generate digest content for a user."""
    # Get portfolio changes
    portfolio_changes = get_portfolio_changes_24h(db, user.id)

    # Get triggered price alerts
    triggered_alerts = get_triggered_alerts_24h(db, user.id)

    # Get new recommendations
    new_recommendations = get_new_recommendations_24h(db, user.id)

    # Get top movers in user's inventory
    inventory_movers = get_inventory_movers_24h(db, user.id)

    if not any([portfolio_changes, triggered_alerts, new_recommendations, inventory_movers]):
        return None

    return {
        "portfolio_changes": portfolio_changes,
        "triggered_alerts": triggered_alerts,
        "new_recommendations": new_recommendations[:5],
        "inventory_movers": inventory_movers[:10],
    }
```

### 6.8 Celery Beat Schedule

```python
# backend/app/tasks/celery_app.py

beat_schedule = {
    # ... existing tasks ...

    "send-daily-digests": {
        "task": "app.tasks.notifications.send_daily_digests",
        "schedule": crontab(hour=8, minute=0),  # 8 AM UTC
        "options": {"queue": "notifications"},
    },
    "send-weekly-digests": {
        "task": "app.tasks.notifications.send_weekly_digests",
        "schedule": crontab(day_of_week=1, hour=8, minute=0),  # Monday 8 AM
        "options": {"queue": "notifications"},
    },
}
```

### 6.9 Notification Preferences UI

```typescript
// frontend/src/app/(protected)/settings/notifications/page.tsx

'use client';

import { useState, useEffect } from 'react';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Bell, Mail, Volume2, Smartphone } from 'lucide-react';
import { subscribeToPush, unsubscribeFromPush } from '@/lib/pushNotifications';

export default function NotificationSettingsPage() {
  const [preferences, setPreferences] = useState({
    priceAlerts: true,
    recommendations: true,
    portfolioUpdates: true,
    emailDigestFrequency: 'daily',
    pushEnabled: true,
    soundEnabled: true,
  });
  const [isPushSupported, setIsPushSupported] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setIsPushSupported('PushManager' in window);
    fetchPreferences();
  }, []);

  const handlePushToggle = async (enabled: boolean) => {
    if (enabled) {
      const success = await subscribeToPush();
      if (!success) {
        toast.error('Failed to enable push notifications');
        return;
      }
    } else {
      await unsubscribeFromPush();
    }
    setPreferences(prev => ({ ...prev, pushEnabled: enabled }));
    await savePreferences({ ...preferences, pushEnabled: enabled });
  };

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
              checked={preferences.pushEnabled}
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
        onClick={() => savePreferences(preferences)}
        disabled={saving}
        className="w-full"
      >
        {saving ? 'Saving...' : 'Save Preferences'}
      </Button>
    </div>
  );
}
```

---

## Section 7: Rate Limiting & Error Boundaries

### 7.1 API Rate Limiting with slowapi

```python
# backend/app/core/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Default limits
DEFAULT_LIMIT = "100/minute"
SEARCH_LIMIT = "30/minute"
AUTH_LIMIT = "10/minute"
```

```python
# backend/app/main.py - Add to FastAPI app
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

```python
# backend/app/api/routes/cards.py - Apply to routes
from app.core.rate_limit import limiter, SEARCH_LIMIT

@router.get("/search")
@limiter.limit(SEARCH_LIMIT)
async def search_cards(request: Request, ...):
    ...
```

### 7.2 React Error Boundaries

```typescript
// frontend/src/components/ErrorBoundary.tsx
'use client';

import { Component, ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { AlertTriangle } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log to Sentry
    console.error('Error boundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-8">
          <AlertTriangle className="h-12 w-12 text-yellow-500 mb-4" />
          <h2 className="text-xl font-semibold mb-2">Something went wrong</h2>
          <p className="text-muted-foreground mb-4 text-center max-w-md">
            We encountered an unexpected error. Please try refreshing the page.
          </p>
          <Button onClick={() => window.location.reload()}>
            Refresh Page
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
```

---

## Section 8: Legal & Analytics

### 8.1 Terms of Service Page

```typescript
// frontend/src/app/(public)/terms/page.tsx
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Terms of Service | Dualcaster Deals',
  robots: { index: true, follow: true },
};

export default function TermsPage() {
  return (
    <div className="container max-w-3xl py-12">
      <h1 className="text-3xl font-bold mb-8">Terms of Service</h1>

      <div className="prose prose-invert max-w-none">
        <p className="text-muted-foreground">Last updated: December 2024</p>

        <h2>1. Acceptance of Terms</h2>
        <p>
          By accessing Dualcaster Deals, you agree to be bound by these Terms of Service.
          If you do not agree, please do not use our service.
        </p>

        <h2>2. Description of Service</h2>
        <p>
          Dualcaster Deals provides Magic: The Gathering card price tracking,
          portfolio management, and trading recommendations. Price data is aggregated
          from third-party sources and may not reflect real-time market conditions.
        </p>

        <h2>3. No Financial Advice</h2>
        <p>
          Trading recommendations are for informational purposes only and do not
          constitute financial advice. You are solely responsible for your trading decisions.
        </p>

        <h2>4. User Accounts</h2>
        <p>
          You are responsible for maintaining the confidentiality of your account.
          You agree to notify us immediately of any unauthorized access.
        </p>

        <h2>5. Intellectual Property</h2>
        <p>
          Magic: The Gathering is a trademark of Wizards of the Coast LLC.
          Card images and data are used under fair use for price tracking purposes.
        </p>

        <h2>6. Limitation of Liability</h2>
        <p>
          We are not liable for any losses arising from your use of our service,
          including but not limited to trading losses based on our recommendations.
        </p>

        <h2>7. Changes to Terms</h2>
        <p>
          We may update these terms at any time. Continued use after changes
          constitutes acceptance of the new terms.
        </p>

        <h2>8. Contact</h2>
        <p>
          Questions about these terms? Contact us at legal@dualcasterdeals.com.
        </p>
      </div>
    </div>
  );
}
```

### 8.2 Privacy Policy Page

```typescript
// frontend/src/app/(public)/privacy/page.tsx
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Privacy Policy | Dualcaster Deals',
  robots: { index: true, follow: true },
};

export default function PrivacyPage() {
  return (
    <div className="container max-w-3xl py-12">
      <h1 className="text-3xl font-bold mb-8">Privacy Policy</h1>

      <div className="prose prose-invert max-w-none">
        <p className="text-muted-foreground">Last updated: December 2024</p>

        <h2>1. Information We Collect</h2>
        <p>We collect:</p>
        <ul>
          <li>Account information (email, username)</li>
          <li>Collection/inventory data you provide</li>
          <li>Usage analytics (pages visited, features used)</li>
          <li>Device information for push notifications</li>
        </ul>

        <h2>2. How We Use Your Information</h2>
        <ul>
          <li>Provide portfolio tracking and recommendations</li>
          <li>Send notifications you've opted into</li>
          <li>Improve our service through analytics</li>
          <li>Communicate service updates</li>
        </ul>

        <h2>3. Data Sharing</h2>
        <p>
          We do not sell your personal data. We may share anonymized,
          aggregated data for market analysis purposes.
        </p>

        <h2>4. Third-Party Services</h2>
        <p>We use:</p>
        <ul>
          <li>Google OAuth for authentication</li>
          <li>Sentry for error tracking</li>
          <li>Analytics for usage tracking</li>
        </ul>

        <h2>5. Data Retention</h2>
        <p>
          We retain your data while your account is active. You may request
          deletion at any time through account settings.
        </p>

        <h2>6. Your Rights</h2>
        <p>You have the right to:</p>
        <ul>
          <li>Access your personal data</li>
          <li>Correct inaccurate data</li>
          <li>Request deletion of your data</li>
          <li>Export your data</li>
        </ul>

        <h2>7. Security</h2>
        <p>
          We use industry-standard security measures including encryption,
          secure authentication, and regular security audits.
        </p>

        <h2>8. Contact</h2>
        <p>
          Privacy questions? Contact us at privacy@dualcasterdeals.com.
        </p>
      </div>
    </div>
  );
}
```

### 8.3 Analytics Integration

Using Plausible (privacy-friendly, no cookie banner needed):

```typescript
// frontend/src/components/Analytics.tsx
'use client';

import Script from 'next/script';

export function Analytics() {
  if (process.env.NODE_ENV !== 'production') return null;

  return (
    <Script
      defer
      data-domain="dualcasterdeals.com"
      src="https://plausible.io/js/script.js"
    />
  );
}
```

```typescript
// frontend/src/app/layout.tsx - Add to layout
import { Analytics } from '@/components/Analytics';

// In the body:
// <Analytics />
```

**Custom event tracking:**

```typescript
// frontend/src/lib/analytics.ts
declare global {
  interface Window {
    plausible?: (event: string, options?: { props?: Record<string, string> }) => void;
  }
}

export function trackEvent(event: string, props?: Record<string, string>) {
  if (typeof window !== 'undefined' && window.plausible) {
    window.plausible(event, { props });
  }
}

// Usage:
// trackEvent('Card Viewed', { cardId: '123', cardName: 'Force of Will' });
// trackEvent('Recommendation Acted', { action: 'BUY', confidence: 'high' });
```

---

## Implementation Tasks

### Phase 1: Security (4 tasks)
1. Implement authorization code exchange for OAuth
2. Fix WebSocket authentication to use message-based auth
3. Set random password for OAuth users
4. Add username validation schema

### Phase 2: SEO (5 tasks)
5. Add static metadata to landing/login/register pages
6. Implement generateMetadata for card pages
7. Create CardJsonLd component for structured data
8. Build dynamic OG image generation API route
9. Create sitemap.ts with top cards

### Phase 3: Recommendation UI (5 tasks)
10. Create AccuracyBadge component
11. Build OutcomeStats section with peak/end toggle
12. Add ConfidenceCalibration indicator
13. Create RecentHitsTicker component
14. Integrate accuracy displays into recommendation cards

### Phase 4: Command Palette (4 tasks)
15. Install shadcn/ui command component
16. Build CommandPalette with search, navigation, actions
17. Implement search operators parser
18. Add CardPreview component and keyboard shortcuts hook

### Phase 5: Cleanup & Stability (5 tasks)
19. Remove console.log statements, add logger utility
20. Configure UptimeRobot monitoring
21. Add API rate limiting with slowapi
22. Add React error boundaries

### Phase 6: Notifications (9 tasks)
23. Create push_subscriptions migration
24. Add notification preferences to User model
25. Generate VAPID keys and add to config
26. Build push notification service with pywebpush
27. Create notification API routes
28. Implement frontend push subscription logic
29. Update service worker with push handler
30. Create email digest Celery task
31. Build notification preferences settings page

### Phase 7: Legal & Analytics (2 tasks)
32. Create Terms of Service and Privacy Policy pages
33. Add analytics script (Plausible or GA4)

**Total: 33 tasks**

---

## Success Criteria

- [ ] OAuth tokens never appear in browser history or logs
- [ ] WebSocket connections authenticated via message, not URL
- [ ] All public pages have proper OG metadata
- [ ] Card pages show in Google rich snippets (verify with structured data testing tool)
- [ ] Users can see accuracy scores on all evaluated recommendations
- [ ] Command palette opens with Cmd+K, supports search operators
- [ ] No console.log statements in production build
- [ ] UptimeRobot sends alerts on downtime
- [ ] Users can receive push notifications on mobile/desktop
- [ ] Email digests arrive on schedule
- [ ] API rate limiting blocks excessive requests (100/min default)
- [ ] React errors show friendly error boundary, not white screen
- [ ] Terms and Privacy pages accessible from footer
- [ ] Analytics tracking page views and key events

---

## Dependencies

**Backend:**
- `pywebpush` - Web push notifications
- `slowapi` - Rate limiting for FastAPI
- Already have: `redis`, `celery`, `fastapi`

**Frontend:**
- `@radix-ui/react-dialog` - For command palette (already via shadcn)
- Already have: `cmdk` (shadcn command), next.js

**Infrastructure:**
- VAPID keys for push notifications
- SMTP credentials for email digests (SendGrid or AWS SES recommended)
- UptimeRobot account (free tier sufficient)
- Analytics account (Plausible Cloud or self-hosted, or GA4)
