# Frontend Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the MTG Market Intel frontend into a polished, MTG-themed experience with 5 mana color themes, toast notifications, skeleton loaders, micro-animations, dashboard, onboarding, and accessibility foundations.

**Architecture:** React Context for theming and toasts, CSS custom properties for dynamic color switching, custom SVG icon components, semantic HTML with ARIA labels for accessibility.

**Tech Stack:** Next.js 14, React 18, Tailwind CSS, Lucide React (base icons), custom MTG SVG icons, Recharts

**Design Reference:** `docs/plans/2025-12-25-frontend-redesign-design.md`

---

## Phase 1: Visual Identity

### Task 1: Create Theme Context and Provider

**Files:**
- Create: `frontend/src/contexts/ThemeContext.tsx`
- Modify: `frontend/src/app/layout.tsx`

**Step 1: Create ThemeContext with mana color definitions**

```tsx
// frontend/src/contexts/ThemeContext.tsx
'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

export type ManaTheme = 'white' | 'blue' | 'black' | 'red' | 'green';

interface ThemeColors {
  primary: string;
  glow: string;
  muted: string;
}

const THEME_COLORS: Record<ManaTheme, ThemeColors> = {
  white: { primary: '248 246 216', glow: '255 254 245', muted: '201 198 165' },
  blue: { primary: '14 104 171', glow: '30 144 255', muted: '10 74 122' },
  black: { primary: '139 92 246', glow: '167 139 250', muted: '109 40 217' },
  red: { primary: '220 38 38', glow: '239 68 68', muted: '153 27 27' },
  green: { primary: '22 163 74', glow: '34 197 94', muted: '21 128 61' },
};

interface ThemeContextType {
  theme: ManaTheme;
  setTheme: (theme: ManaTheme) => void;
  colors: ThemeColors;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ManaTheme>('blue');

  useEffect(() => {
    const stored = localStorage.getItem('mana-theme') as ManaTheme | null;
    if (stored && THEME_COLORS[stored]) {
      setThemeState(stored);
    }
  }, []);

  useEffect(() => {
    const colors = THEME_COLORS[theme];
    document.documentElement.style.setProperty('--accent', colors.primary);
    document.documentElement.style.setProperty('--accent-glow', colors.glow);
    document.documentElement.style.setProperty('--accent-muted', colors.muted);
    localStorage.setItem('mana-theme', theme);
  }, [theme]);

  const setTheme = (newTheme: ManaTheme) => {
    setThemeState(newTheme);
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme, colors: THEME_COLORS[theme] }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
```

**Step 2: Update globals.css with accent CSS variables**

Modify `frontend/src/app/globals.css` - add after existing dark mode variables:

```css
:root {
  /* Accent colors - updated dynamically by ThemeContext */
  --accent: 14 104 171; /* Default: blue */
  --accent-glow: 30 144 255;
  --accent-muted: 10 74 122;
}
```

**Step 3: Wrap app with ThemeProvider**

Modify `frontend/src/app/layout.tsx` - import and wrap:

```tsx
import { ThemeProvider } from '@/contexts/ThemeContext';

// In the body, wrap children:
<ThemeProvider>
  {children}
</ThemeProvider>
```

**Step 4: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 5: Commit**

```bash
git add frontend/src/contexts/ThemeContext.tsx frontend/src/app/globals.css frontend/src/app/layout.tsx
git commit -m "feat: add mana theme context with 5 color palettes"
```

---

### Task 2: Create Theme Picker Component

**Files:**
- Create: `frontend/src/components/ui/ThemePicker.tsx`

**Step 1: Create ThemePicker component**

```tsx
// frontend/src/components/ui/ThemePicker.tsx
'use client';

import { useTheme, ManaTheme } from '@/contexts/ThemeContext';
import { cn } from '@/lib/utils';

const MANA_ORBS: { theme: ManaTheme; label: string; bgClass: string }[] = [
  { theme: 'white', label: 'White', bgClass: 'bg-[#F8F6D8]' },
  { theme: 'blue', label: 'Blue', bgClass: 'bg-[#0E68AB]' },
  { theme: 'black', label: 'Black', bgClass: 'bg-[#8B5CF6]' },
  { theme: 'red', label: 'Red', bgClass: 'bg-[#DC2626]' },
  { theme: 'green', label: 'Green', bgClass: 'bg-[#16A34A]' },
];

export function ThemePicker() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex flex-col gap-3">
      <span className="text-sm font-medium text-[rgb(var(--foreground))]">
        Mana Theme
      </span>
      <div className="flex gap-4">
        {MANA_ORBS.map((orb) => (
          <button
            key={orb.theme}
            onClick={() => setTheme(orb.theme)}
            className={cn(
              'flex flex-col items-center gap-2 group'
            )}
            aria-label={`Select ${orb.label} theme`}
            aria-pressed={theme === orb.theme}
          >
            <div
              className={cn(
                'w-10 h-10 rounded-full transition-all duration-200',
                orb.bgClass,
                theme === orb.theme
                  ? 'ring-2 ring-offset-2 ring-offset-[rgb(var(--background))] ring-[rgb(var(--accent))] scale-110 shadow-[0_0_20px_rgba(var(--accent-glow),0.5)]'
                  : 'hover:scale-105 hover:shadow-[0_0_15px_rgba(var(--accent-glow),0.3)]'
              )}
            />
            <span
              className={cn(
                'text-xs transition-colors',
                theme === orb.theme
                  ? 'text-[rgb(var(--accent))]'
                  : 'text-[rgb(var(--muted-foreground))] group-hover:text-[rgb(var(--foreground))]'
              )}
            >
              {orb.label}
            </span>
            {theme === orb.theme && (
              <div className="w-6 h-0.5 bg-[rgb(var(--accent))] rounded-full" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/ui/ThemePicker.tsx
git commit -m "feat: add ThemePicker component with mana orbs"
```

---

### Task 3: Add Theme Picker to Settings Page

**Files:**
- Modify: `frontend/src/app/settings/page.tsx`

**Step 1: Import and add ThemePicker to settings**

Add import at top:
```tsx
import { ThemePicker } from '@/components/ui/ThemePicker';
```

Add new section before Marketplaces section (after the opening of the main content area):

```tsx
{/* Appearance Section */}
<Card>
  <CardHeader>
    <CardTitle>Appearance</CardTitle>
    <CardDescription>Customize your visual experience</CardDescription>
  </CardHeader>
  <CardContent>
    <ThemePicker />
  </CardContent>
</Card>
```

**Step 2: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/app/settings/page.tsx
git commit -m "feat: add theme picker to settings page"
```

---

### Task 4: Update Button Component with Accent Colors

**Files:**
- Modify: `frontend/src/components/ui/Button.tsx`

**Step 1: Update Button variants to use accent colors**

Replace the primary variant styles:

```tsx
const variants = {
  primary:
    'bg-[rgb(var(--accent))] text-white hover:bg-[rgb(var(--accent-glow))] hover:shadow-[0_0_20px_rgba(var(--accent-glow),0.4)] hover:scale-[1.02] active:scale-[0.98] transition-all duration-200',
  secondary:
    'bg-transparent border border-[rgb(var(--accent))] text-[rgb(var(--accent))] hover:bg-[rgba(var(--accent),0.1)] transition-all duration-200',
  ghost:
    'bg-transparent text-[rgb(var(--accent))] hover:underline transition-all duration-200',
  danger:
    'bg-red-600 text-white hover:bg-red-500 hover:shadow-[0_0_20px_rgba(239,68,68,0.4)] hover:scale-[1.02] active:scale-[0.98] transition-all duration-200',
};
```

**Step 2: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/ui/Button.tsx
git commit -m "feat: update Button with accent colors and hover effects"
```

---

### Task 5: Update Card Component with Accent Hover

**Files:**
- Modify: `frontend/src/components/ui/Card.tsx`

**Step 1: Add hover effects to Card component**

Update the Card component's className:

```tsx
export function Card({ className, children }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-6',
        'transition-all duration-200',
        'hover:border-[rgba(var(--accent),0.3)] hover:shadow-[0_0_20px_rgba(var(--accent),0.1)]',
        className
      )}
    >
      {children}
    </div>
  );
}
```

**Step 2: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/ui/Card.tsx
git commit -m "feat: add accent hover effects to Card component"
```

---

### Task 6: Update Input Component with Accent Focus

**Files:**
- Modify: `frontend/src/components/ui/Input.tsx`

**Step 1: Update Input focus styles**

Update the input className to use accent colors on focus:

```tsx
className={cn(
  'w-full rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--background))] px-4 py-2',
  'text-[rgb(var(--foreground))] placeholder:text-[rgb(var(--muted-foreground))]',
  'transition-all duration-200',
  'focus:border-[rgb(var(--accent))] focus:outline-none focus:ring-2 focus:ring-[rgba(var(--accent),0.3)] focus:shadow-[0_0_10px_rgba(var(--accent-glow),0.2)]',
  'disabled:opacity-50 disabled:cursor-not-allowed',
  className
)}
```

**Step 2: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/ui/Input.tsx
git commit -m "feat: add accent focus styles to Input component"
```

---

### Task 7: Update Navigation with Accent Active State

**Files:**
- Modify: `frontend/src/components/layout/TopNav.tsx`

**Step 1: Update active link styles to use accent**

Find the NavLink styling and update to use accent colors:

```tsx
// Update active state styling
const isActive = pathname === href;

// In the className:
className={cn(
  'flex items-center gap-2 px-3 py-2 rounded-lg transition-all duration-200',
  isActive
    ? 'text-[rgb(var(--accent))] bg-[rgba(var(--accent),0.1)]'
    : 'text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] hover:bg-[rgba(var(--accent),0.05)]'
)}
```

**Step 2: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/layout/TopNav.tsx
git commit -m "feat: update navigation with accent active states"
```

---

### Task 8: Update Badge Component with Accent Variant

**Files:**
- Modify: `frontend/src/components/ui/Badge.tsx`

**Step 1: Add accent variant to Badge**

Add accent to the variants object:

```tsx
const variants = {
  default: 'bg-[rgb(var(--secondary))] text-[rgb(var(--foreground))]',
  accent: 'bg-[rgba(var(--accent),0.2)] text-[rgb(var(--accent))] border border-[rgba(var(--accent),0.3)]',
  success: 'bg-green-500/20 text-green-400 border border-green-500/30',
  warning: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  danger: 'bg-red-500/20 text-red-400 border border-red-500/30',
  info: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
};
```

**Step 2: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/ui/Badge.tsx
git commit -m "feat: add accent variant to Badge component"
```

---

## Phase 2: Feedback & Polish

### Task 9: Create Toast Context and Provider

**Files:**
- Create: `frontend/src/contexts/ToastContext.tsx`
- Create: `frontend/src/components/ui/Toast.tsx`

**Step 1: Create Toast types and context**

```tsx
// frontend/src/contexts/ToastContext.tsx
'use client';

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  description?: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface ToastContextType {
  toasts: Toast[];
  toast: {
    success: (message: string, options?: Partial<Omit<Toast, 'id' | 'type' | 'message'>>) => void;
    error: (message: string, options?: Partial<Omit<Toast, 'id' | 'type' | 'message'>>) => void;
    warning: (message: string, options?: Partial<Omit<Toast, 'id' | 'type' | 'message'>>) => void;
    info: (message: string, options?: Partial<Omit<Toast, 'id' | 'type' | 'message'>>) => void;
  };
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((type: ToastType, message: string, options?: Partial<Omit<Toast, 'id' | 'type' | 'message'>>) => {
    const id = Math.random().toString(36).substring(2, 9);
    const duration = options?.duration ?? (type === 'error' ? 0 : 4000);

    const newToast: Toast = {
      id,
      type,
      message,
      ...options,
      duration,
    };

    setToasts((prev) => [...prev, newToast].slice(-3)); // Max 3 toasts

    if (duration > 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, duration);
    }
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = {
    success: (message: string, options?: Partial<Omit<Toast, 'id' | 'type' | 'message'>>) => addToast('success', message, options),
    error: (message: string, options?: Partial<Omit<Toast, 'id' | 'type' | 'message'>>) => addToast('error', message, options),
    warning: (message: string, options?: Partial<Omit<Toast, 'id' | 'type' | 'message'>>) => addToast('warning', message, options),
    info: (message: string, options?: Partial<Omit<Toast, 'id' | 'type' | 'message'>>) => addToast('info', message, options),
  };

  return (
    <ToastContext.Provider value={{ toasts, toast, dismissToast }}>
      {children}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}
```

**Step 2: Create Toast component**

```tsx
// frontend/src/components/ui/Toast.tsx
'use client';

import { useToast, Toast as ToastType } from '@/contexts/ToastContext';
import { X, CheckCircle, XCircle, AlertTriangle, Info } from 'lucide-react';
import { cn } from '@/lib/utils';

const TOAST_ICONS = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const TOAST_STYLES = {
  success: 'border-green-500/30 bg-green-500/10',
  error: 'border-red-500/30 bg-red-500/10',
  warning: 'border-amber-500/30 bg-amber-500/10',
  info: 'border-[rgba(var(--accent),0.3)] bg-[rgba(var(--accent),0.1)]',
};

const TOAST_ICON_STYLES = {
  success: 'text-green-400',
  error: 'text-red-400',
  warning: 'text-amber-400',
  info: 'text-[rgb(var(--accent))]',
};

function ToastItem({ toast }: { toast: ToastType }) {
  const { dismissToast } = useToast();
  const Icon = TOAST_ICONS[toast.type];

  return (
    <div
      className={cn(
        'flex items-start gap-3 p-4 rounded-lg border shadow-lg backdrop-blur-sm',
        'animate-in slide-in-from-right fade-in duration-200',
        TOAST_STYLES[toast.type]
      )}
      role={toast.type === 'error' ? 'alert' : 'status'}
    >
      <Icon className={cn('w-5 h-5 flex-shrink-0 mt-0.5', TOAST_ICON_STYLES[toast.type])} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[rgb(var(--foreground))]">{toast.message}</p>
        {toast.description && (
          <p className="text-xs text-[rgb(var(--muted-foreground))] mt-1">{toast.description}</p>
        )}
        {toast.action && (
          <button
            onClick={() => {
              toast.action?.onClick();
              dismissToast(toast.id);
            }}
            className="text-xs font-medium text-[rgb(var(--accent))] hover:underline mt-2"
          >
            {toast.action.label}
          </button>
        )}
      </div>
      <button
        onClick={() => dismissToast(toast.id)}
        className="text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] transition-colors"
        aria-label="Dismiss"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const { toasts } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
```

**Step 3: Add ToastProvider and ToastContainer to layout**

Modify `frontend/src/app/layout.tsx`:

```tsx
import { ToastProvider } from '@/contexts/ToastContext';
import { ToastContainer } from '@/components/ui/Toast';

// Wrap with ToastProvider and add ToastContainer:
<ThemeProvider>
  <ToastProvider>
    {children}
    <ToastContainer />
  </ToastProvider>
</ThemeProvider>
```

**Step 4: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add frontend/src/contexts/ToastContext.tsx frontend/src/components/ui/Toast.tsx frontend/src/app/layout.tsx
git commit -m "feat: add toast notification system"
```

---

### Task 10: Create Skeleton Components

**Files:**
- Create: `frontend/src/components/ui/Skeleton.tsx`

**Step 1: Create Skeleton base and variants**

```tsx
// frontend/src/components/ui/Skeleton.tsx
import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-lg bg-[rgb(var(--secondary))]',
        'relative overflow-hidden',
        'after:absolute after:inset-0 after:translate-x-[-100%]',
        'after:bg-gradient-to-r after:from-transparent after:via-[rgba(var(--accent),0.05)] after:to-transparent',
        'after:animate-[shimmer_1.5s_infinite]',
        className
      )}
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-4">
      <Skeleton className="h-40 w-full mb-4" />
      <Skeleton className="h-4 w-3/4 mb-2" />
      <Skeleton className="h-4 w-1/2 mb-4" />
      <div className="flex justify-between">
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-6 w-16" />
      </div>
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 p-4 border-b border-[rgb(var(--border))]">
      <Skeleton className="h-10 w-10 rounded-full" />
      <div className="flex-1">
        <Skeleton className="h-4 w-1/3 mb-2" />
        <Skeleton className="h-3 w-1/4" />
      </div>
      <Skeleton className="h-6 w-20" />
    </div>
  );
}

export function SkeletonStats() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-4">
          <Skeleton className="h-3 w-20 mb-2" />
          <Skeleton className="h-8 w-24" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonChart() {
  return (
    <div className="rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-4">
      <Skeleton className="h-4 w-32 mb-4" />
      <div className="h-64 flex items-end gap-1">
        {[...Array(12)].map((_, i) => (
          <Skeleton
            key={i}
            className="flex-1"
            style={{ height: `${30 + Math.random() * 70}%` }}
          />
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Add shimmer keyframe to globals.css**

Add to `frontend/src/app/globals.css`:

```css
@keyframes shimmer {
  100% {
    transform: translateX(100%);
  }
}
```

**Step 3: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/components/ui/Skeleton.tsx frontend/src/app/globals.css
git commit -m "feat: add skeleton loading components with shimmer"
```

---

### Task 11: Add Page Transition Animation

**Files:**
- Modify: `frontend/src/app/globals.css`
- Create: `frontend/src/components/ui/PageTransition.tsx`

**Step 1: Add page transition styles to globals.css**

```css
/* Page transitions */
.page-enter {
  animation: pageEnter 0.15s ease-out;
}

@keyframes pageEnter {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Respect reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

**Step 2: Create PageTransition wrapper**

```tsx
// frontend/src/components/ui/PageTransition.tsx
'use client';

import { ReactNode } from 'react';

interface PageTransitionProps {
  children: ReactNode;
}

export function PageTransition({ children }: PageTransitionProps) {
  return <div className="page-enter">{children}</div>;
}
```

**Step 3: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/app/globals.css frontend/src/components/ui/PageTransition.tsx
git commit -m "feat: add page transition animations with reduced motion support"
```

---

## Phase 3: Structure & Flow

### Task 12: Create Dashboard Page

**Files:**
- Create: `frontend/src/app/dashboard/page.tsx`
- Modify: `frontend/src/components/layout/TopNav.tsx` (add dashboard link)

**Step 1: Create Dashboard page**

```tsx
// frontend/src/app/dashboard/page.tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { SkeletonStats, SkeletonChart } from '@/components/ui/Skeleton';
import { PageTransition } from '@/components/ui/PageTransition';
import { MarketIndexChart } from '@/components/charts/MarketIndexChart';
import { TrendingUp, TrendingDown, AlertTriangle, DollarSign, Plus, RefreshCw, BarChart3 } from 'lucide-react';
import { formatCurrency, formatPercent } from '@/lib/utils';
import { getInventoryAnalytics, getInventoryMarketIndex, getInventoryTopMovers } from '@/lib/api';
import Link from 'next/link';

export default function DashboardPage() {
  const { user } = useAuth();

  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['inventory-analytics'],
    queryFn: getInventoryAnalytics,
  });

  const { data: marketIndex, isLoading: indexLoading } = useQuery({
    queryKey: ['inventory-market-index', '30d'],
    queryFn: () => getInventoryMarketIndex('30d'),
  });

  const { data: topMovers, isLoading: moversLoading } = useQuery({
    queryKey: ['inventory-top-movers'],
    queryFn: () => getInventoryTopMovers('24h'),
  });

  const isLoading = analyticsLoading || indexLoading || moversLoading;
  const isEmpty = !analytics?.total_cards || analytics.total_cards === 0;

  return (
    <PageTransition>
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-[rgb(var(--foreground))]">
              Welcome back{user?.display_name ? `, ${user.display_name}` : ''}
            </h1>
            <p className="text-[rgb(var(--muted-foreground))]">
              Here&apos;s your portfolio overview
            </p>
          </div>
          <div className="flex gap-2">
            <Link href="/inventory">
              <Button variant="secondary" className="flex items-center gap-2">
                <Plus className="w-4 h-4" />
                Add Cards
              </Button>
            </Link>
          </div>
        </div>

        {isEmpty && !isLoading ? (
          /* Empty State */
          <Card className="text-center py-12">
            <CardContent>
              <div className="max-w-md mx-auto">
                <div className="w-16 h-16 rounded-full bg-[rgba(var(--accent),0.1)] flex items-center justify-center mx-auto mb-4">
                  <BarChart3 className="w-8 h-8 text-[rgb(var(--accent))]" />
                </div>
                <h2 className="text-xl font-semibold mb-2">Let&apos;s get started!</h2>
                <p className="text-[rgb(var(--muted-foreground))] mb-6">
                  Import your collection to see your portfolio value, get price alerts, and receive trading recommendations.
                </p>
                <div className="flex gap-3 justify-center">
                  <Link href="/inventory">
                    <Button>Import Cards</Button>
                  </Link>
                  <Link href="/cards">
                    <Button variant="secondary">Browse Cards First</Button>
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Stats Row */}
            {isLoading ? (
              <SkeletonStats />
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-[rgb(var(--muted-foreground))] mb-1">
                      <DollarSign className="w-4 h-4" />
                      <span className="text-sm">Portfolio Value</span>
                    </div>
                    <p className="text-2xl font-bold">{formatCurrency(analytics?.total_value || 0)}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-[rgb(var(--muted-foreground))] mb-1">
                      <TrendingUp className="w-4 h-4" />
                      <span className="text-sm">Profit/Loss</span>
                    </div>
                    <p className={`text-2xl font-bold ${(analytics?.total_profit_loss || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {formatCurrency(analytics?.total_profit_loss || 0)}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-[rgb(var(--muted-foreground))] mb-1">
                      <BarChart3 className="w-4 h-4" />
                      <span className="text-sm">Total Cards</span>
                    </div>
                    <p className="text-2xl font-bold">{analytics?.total_cards || 0}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 text-[rgb(var(--muted-foreground))] mb-1">
                      <AlertTriangle className="w-4 h-4" />
                      <span className="text-sm">Critical Alerts</span>
                    </div>
                    <p className="text-2xl font-bold text-amber-400">{analytics?.critical_alerts || 0}</p>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* Chart and Top Movers */}
            <div className="grid md:grid-cols-3 gap-6 mb-8">
              <div className="md:col-span-2">
                {indexLoading ? (
                  <SkeletonChart />
                ) : (
                  <Card>
                    <CardHeader>
                      <CardTitle>Portfolio Trend (30d)</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {marketIndex && <MarketIndexChart data={marketIndex} />}
                    </CardContent>
                  </Card>
                )}
              </div>
              <Card>
                <CardHeader>
                  <CardTitle>Top Movers Today</CardTitle>
                </CardHeader>
                <CardContent>
                  {moversLoading ? (
                    <div className="space-y-3">
                      {[...Array(5)].map((_, i) => (
                        <div key={i} className="flex justify-between">
                          <div className="h-4 w-24 bg-[rgb(var(--secondary))] rounded animate-pulse" />
                          <div className="h-4 w-12 bg-[rgb(var(--secondary))] rounded animate-pulse" />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {topMovers?.gainers?.slice(0, 3).map((card: any) => (
                        <div key={card.card_id} className="flex justify-between items-center">
                          <span className="text-sm truncate">{card.card_name}</span>
                          <span className="text-green-400 text-sm flex items-center gap-1">
                            <TrendingUp className="w-3 h-3" />
                            {formatPercent(card.change_pct)}
                          </span>
                        </div>
                      ))}
                      {topMovers?.losers?.slice(0, 2).map((card: any) => (
                        <div key={card.card_id} className="flex justify-between items-center">
                          <span className="text-sm truncate">{card.card_name}</span>
                          <span className="text-red-400 text-sm flex items-center gap-1">
                            <TrendingDown className="w-3 h-3" />
                            {formatPercent(card.change_pct)}
                          </span>
                        </div>
                      ))}
                      {(!topMovers?.gainers?.length && !topMovers?.losers?.length) && (
                        <p className="text-[rgb(var(--muted-foreground))] text-sm">No movers today</p>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Quick Actions */}
            <Card>
              <CardHeader>
                <CardTitle>Quick Actions</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-3">
                  <Link href="/inventory">
                    <Button className="flex items-center gap-2">
                      <Plus className="w-4 h-4" />
                      Add Cards
                    </Button>
                  </Link>
                  <Link href="/recommendations">
                    <Button variant="secondary" className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4" />
                      View Recommendations
                    </Button>
                  </Link>
                  <Link href="/cards">
                    <Button variant="secondary" className="flex items-center gap-2">
                      <BarChart3 className="w-4 h-4" />
                      Browse Market
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </PageTransition>
  );
}
```

**Step 2: Update TopNav to include Dashboard link and make it the home for logged-in users**

Update navigation items array in TopNav.tsx to include Dashboard:

```tsx
const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/cards', label: 'Search Cards', icon: Search },
  { href: '/inventory', label: 'My Inventory', icon: Package, requiresAuth: true },
  { href: '/recommendations', label: 'Recommendations', icon: TrendingUp },
  { href: '/settings', label: 'Settings', icon: Settings },
];
```

Add LayoutDashboard to imports.

**Step 3: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/app/dashboard/page.tsx frontend/src/components/layout/TopNav.tsx
git commit -m "feat: add dashboard page with portfolio overview"
```

---

### Task 13: Create Welcome Modal for Onboarding

**Files:**
- Create: `frontend/src/components/onboarding/WelcomeModal.tsx`
- Modify: `frontend/src/app/layout.tsx`

**Step 1: Create WelcomeModal component**

```tsx
// frontend/src/components/onboarding/WelcomeModal.tsx
'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme, ManaTheme } from '@/contexts/ThemeContext';
import { Button } from '@/components/ui/Button';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

const MANA_ORBS: { theme: ManaTheme; label: string; bgClass: string }[] = [
  { theme: 'white', label: 'White', bgClass: 'bg-[#F8F6D8]' },
  { theme: 'blue', label: 'Blue', bgClass: 'bg-[#0E68AB]' },
  { theme: 'black', label: 'Black', bgClass: 'bg-[#8B5CF6]' },
  { theme: 'red', label: 'Red', bgClass: 'bg-[#DC2626]' },
  { theme: 'green', label: 'Green', bgClass: 'bg-[#16A34A]' },
];

export function WelcomeModal() {
  const [isOpen, setIsOpen] = useState(false);
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();

  useEffect(() => {
    if (user) {
      const hasSeenWelcome = localStorage.getItem('has-seen-welcome');
      if (!hasSeenWelcome) {
        setIsOpen(true);
      }
    }
  }, [user]);

  const handleClose = () => {
    localStorage.setItem('has-seen-welcome', 'true');
    setIsOpen(false);
  };

  const handleGetStarted = () => {
    handleClose();
    window.location.href = '/dashboard';
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div
        className="relative bg-[rgb(var(--card))] border border-[rgb(var(--border))] rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl animate-in zoom-in-95 fade-in duration-200"
        role="dialog"
        aria-modal="true"
        aria-labelledby="welcome-title"
      >
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] transition-colors"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="text-center mb-6">
          <div className="w-12 h-12 rounded-full bg-[rgba(var(--accent),0.2)] flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">✨</span>
          </div>
          <h2 id="welcome-title" className="text-2xl font-bold text-[rgb(var(--foreground))] mb-2">
            Welcome to Dualcaster Deals
          </h2>
          <p className="text-[rgb(var(--muted-foreground))]">
            Your MTG market intelligence companion. Track prices, spot opportunities, and make smarter trades.
          </p>
        </div>

        {/* Theme Picker */}
        <div className="bg-[rgb(var(--background))] rounded-xl p-6 mb-6">
          <p className="text-sm font-medium text-[rgb(var(--foreground))] mb-4 text-center">
            Pick your mana
          </p>
          <div className="flex justify-center gap-4">
            {MANA_ORBS.map((orb) => (
              <button
                key={orb.theme}
                onClick={() => setTheme(orb.theme)}
                className="flex flex-col items-center gap-2 group"
                aria-label={`Select ${orb.label} theme`}
                aria-pressed={theme === orb.theme}
              >
                <div
                  className={cn(
                    'w-12 h-12 rounded-full transition-all duration-200',
                    orb.bgClass,
                    theme === orb.theme
                      ? 'ring-2 ring-offset-2 ring-offset-[rgb(var(--background))] ring-[rgb(var(--accent))] scale-110 shadow-[0_0_20px_rgba(var(--accent-glow),0.5)]'
                      : 'hover:scale-105'
                  )}
                />
                <span
                  className={cn(
                    'text-xs transition-colors',
                    theme === orb.theme
                      ? 'text-[rgb(var(--accent))]'
                      : 'text-[rgb(var(--muted-foreground))]'
                  )}
                >
                  {orb.label}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <Button onClick={handleGetStarted} className="w-full">
            Get Started
          </Button>
          <button
            onClick={handleClose}
            className="text-sm text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] transition-colors"
          >
            Skip for now
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Add WelcomeModal to layout**

Modify `frontend/src/app/layout.tsx` to include WelcomeModal:

```tsx
import { WelcomeModal } from '@/components/onboarding/WelcomeModal';

// Inside the providers, add:
<WelcomeModal />
```

**Step 3: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/components/onboarding/WelcomeModal.tsx frontend/src/app/layout.tsx
git commit -m "feat: add welcome modal with theme picker for onboarding"
```

---

## Phase 4: Accessibility & Mobile

### Task 14: Add Semantic HTML Structure

**Files:**
- Modify: `frontend/src/components/layout/AppLayout.tsx`
- Modify: `frontend/src/components/layout/TopNav.tsx`

**Step 1: Update AppLayout with semantic elements**

```tsx
// Wrap main content in <main> element with proper landmark
<main id="main-content" role="main">
  {children}
</main>
```

**Step 2: Update TopNav with semantic nav and skip link**

Add at the very beginning of the component return:

```tsx
<>
  {/* Skip to main content link */}
  <a
    href="#main-content"
    className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-[rgb(var(--accent))] focus:text-white focus:rounded-lg"
  >
    Skip to main content
  </a>
  <header>
    <nav role="navigation" aria-label="Main navigation">
      {/* existing nav content */}
    </nav>
  </header>
</>
```

**Step 3: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/components/layout/AppLayout.tsx frontend/src/components/layout/TopNav.tsx
git commit -m "feat: add semantic HTML structure and skip link"
```

---

### Task 15: Add ARIA Labels to Icon Buttons

**Files:**
- Audit and update all components with icon-only buttons

**Step 1: Update common icon button patterns**

Add `aria-label` to all icon-only buttons throughout the codebase. Common patterns:

```tsx
// Close buttons
<button aria-label="Close" ...>
  <X className="w-4 h-4" />
</button>

// Menu toggle
<button aria-label={isOpen ? "Close menu" : "Open menu"} ...>
  <Menu className="w-6 h-6" />
</button>

// Refresh buttons
<button aria-label="Refresh data" ...>
  <RefreshCw className="w-4 h-4" />
</button>
```

**Step 2: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: add ARIA labels to icon-only buttons"
```

---

### Task 16: Create Mobile Bottom Navigation

**Files:**
- Create: `frontend/src/components/layout/BottomNav.tsx`
- Modify: `frontend/src/app/layout.tsx`

**Step 1: Create BottomNav component**

```tsx
// frontend/src/components/layout/BottomNav.tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Search, Package, TrendingUp, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';

const navItems = [
  { href: '/dashboard', label: 'Home', icon: LayoutDashboard },
  { href: '/cards', label: 'Search', icon: Search },
  { href: '/inventory', label: 'Inventory', icon: Package, requiresAuth: true },
  { href: '/recommendations', label: 'Recs', icon: TrendingUp },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export function BottomNav() {
  const pathname = usePathname();
  const { user } = useAuth();

  // Hide on auth pages
  if (pathname === '/login' || pathname === '/register' || pathname === '/') {
    return null;
  }

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 bg-[rgb(var(--card))] border-t border-[rgb(var(--border))] md:hidden"
      role="navigation"
      aria-label="Mobile navigation"
    >
      <div className="flex justify-around items-center h-16 px-2">
        {navItems.map((item) => {
          if (item.requiresAuth && !user) return null;

          const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex flex-col items-center justify-center gap-1 px-3 py-2 rounded-lg transition-all min-w-[64px]',
                isActive
                  ? 'text-[rgb(var(--accent))]'
                  : 'text-[rgb(var(--muted-foreground))]'
              )}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon className={cn('w-5 h-5', isActive && 'drop-shadow-[0_0_8px_rgba(var(--accent-glow),0.5)]')} />
              <span className="text-xs">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
```

**Step 2: Add BottomNav to layout and add bottom padding to main content**

Modify `frontend/src/app/layout.tsx`:

```tsx
import { BottomNav } from '@/components/layout/BottomNav';

// Add BottomNav and padding for mobile:
<div className="pb-16 md:pb-0">
  {children}
</div>
<BottomNav />
```

**Step 3: Verify build passes**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/components/layout/BottomNav.tsx frontend/src/app/layout.tsx
git commit -m "feat: add mobile bottom navigation"
```

---

### Task 17: Final Integration Test

**Step 1: Build the complete frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds with all routes

**Step 2: Run linter**

Run: `cd frontend && npm run lint`
Expected: No errors (warnings acceptable)

**Step 3: Create final commit if any uncommitted changes**

```bash
git add -A
git status
# If changes exist:
git commit -m "chore: final cleanup and integration"
```

**Step 4: Verify branch is ready**

```bash
git log --oneline -10
```

Expected: Clean commit history with all Phase 1-4 features

---

## Summary

This implementation plan covers:

1. **Phase 1 (Visual Identity):** Theme context, theme picker, accent colors on all components
2. **Phase 2 (Feedback):** Toast system, skeleton loaders, page transitions
3. **Phase 3 (Structure):** Dashboard, onboarding modal
4. **Phase 4 (A11y/Mobile):** Semantic HTML, ARIA labels, bottom navigation

Each task is atomic and commits frequently. The plan assumes TDD where applicable but focuses on integration given the UI-heavy nature.
