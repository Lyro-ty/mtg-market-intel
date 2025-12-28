# Phase 2: Visual Overhaul - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the entire Dualcaster Deals frontend using shadcn/ui components with an "Ornate Saga" MTG-themed decorative layer.

**Architecture:** shadcn/ui provides accessible, customizable primitives. We layer MTG theming on top: Cinzel typography, gold borders, custom fantasy icons, 5 mana color themes. Hybrid navigation with collapsible sidebar + slim header.

**Tech Stack:** Next.js 14, shadcn/ui, Tailwind CSS, Radix UI, Recharts, Cinzel + Inter fonts, game-icons.net SVGs

**Design Reference:** `docs/plans/2025-12-28-phase2-visual-overhaul-design.md`

**Worktree:** `/home/lyro/mtg-market-intel/.worktrees/phase2-visual-overhaul`

---

## Phase 2a: Foundation Setup

### Task 1: Initialize shadcn/ui

**Files:**
- Create: `frontend/components.json`
- Modify: `frontend/tailwind.config.ts`
- Modify: `frontend/src/app/globals.css`
- Create: `frontend/src/lib/utils.ts`

**Step 1: Initialize shadcn**

```bash
cd frontend
npx shadcn@latest init
```

When prompted:
- Style: Default
- Base color: Slate
- CSS variables: Yes
- tailwind.config location: tailwind.config.ts
- Components location: src/components/ui
- Utils location: src/lib/utils

**Step 2: Verify components.json created**

```bash
cat components.json
```

Expected: JSON config file with paths configured

**Step 3: Verify build passes**

```bash
npm run build
```

Expected: Build succeeds

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: initialize shadcn/ui"
```

---

### Task 2: Configure Custom Color System

**Files:**
- Modify: `frontend/src/app/globals.css`

**Step 1: Replace CSS variables with Ornate Saga colors**

Replace the `:root` and `.dark` sections in globals.css with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* Base dark theme (always dark) */
    --background: 12 12 16;
    --foreground: 245 245 245;

    --card: 20 20 26;
    --card-foreground: 245 245 245;

    --popover: 20 20 26;
    --popover-foreground: 245 245 245;

    --primary: 14 104 171;
    --primary-foreground: 255 255 255;

    --secondary: 28 28 36;
    --secondary-foreground: 245 245 245;

    --muted: 28 28 36;
    --muted-foreground: 163 163 163;

    --accent: 14 104 171;
    --accent-foreground: 255 255 255;

    --destructive: 239 68 68;
    --destructive-foreground: 255 255 255;

    --border: 42 42 53;
    --input: 42 42 53;
    --ring: 14 104 171;

    --radius: 0.5rem;

    /* Mana accent (dynamic via ThemeContext) */
    --accent-glow: 30 144 255;
    --accent-muted: 10 74 122;

    /* Magic colors (from logo) */
    --magic-purple: 139 92 246;
    --magic-green: 34 197 94;
    --magic-gold: 212 175 55;

    /* Exotic accents */
    --ethereal-cyan: 34 211 238;
    --void-indigo: 99 102 241;
    --astral-pink: 244 114 182;

    /* Metallic (rarity) */
    --bronze: 205 127 50;
    --silver: 192 192 192;
    --gold: 212 175 55;
    --mythic-orange: 255 103 0;

    /* Elemental */
    --fire-core: 251 146 60;
    --fire-edge: 220 38 38;
    --ice-core: 147 197 253;
    --ice-edge: 59 130 246;

    /* Semantic */
    --success: 34 197 94;
    --warning: 251 191 36;
    --info: 59 130 246;

    /* Chart colors */
    --chart-1: 139 92 246;
    --chart-2: 34 197 94;
    --chart-3: 251 191 36;
    --chart-4: 239 68 68;
    --chart-5: 59 130 246;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}
```

**Step 2: Verify build passes**

```bash
npm run build
```

Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "feat: configure Ornate Saga color system"
```

---

### Task 3: Add Custom Fonts

**Files:**
- Create: `frontend/src/app/fonts.css`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/tailwind.config.ts`

**Step 1: Create fonts.css**

```css
/* frontend/src/app/fonts.css */
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500;600;700&family=Cinzel+Decorative:wght@400;700&family=Inter:wght@400;500;600;700&display=swap');
```

**Step 2: Import fonts in layout.tsx**

Add at top of `frontend/src/app/layout.tsx`:

```tsx
import './fonts.css';
```

**Step 3: Update tailwind.config.ts**

Add to the `theme.extend` section:

```ts
fontFamily: {
  display: ['Cinzel Decorative', 'serif'],
  heading: ['Cinzel', 'serif'],
  sans: ['Inter', 'sans-serif'],
},
```

**Step 4: Verify build passes**

```bash
npm run build
```

**Step 5: Commit**

```bash
git add frontend/src/app/fonts.css frontend/src/app/layout.tsx frontend/tailwind.config.ts
git commit -m "feat: add Cinzel and Inter font families"
```

---

### Task 4: Install Core shadcn Components

**Files:**
- Create: Multiple files in `frontend/src/components/ui/`

**Step 1: Install essential components**

```bash
cd frontend
npx shadcn@latest add button card input label badge skeleton dialog dropdown-menu select tabs table tooltip avatar separator scroll-area
```

**Step 2: Verify components created**

```bash
ls src/components/ui/
```

Expected: See button.tsx, card.tsx, input.tsx, etc.

**Step 3: Verify build passes**

```bash
npm run build
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: install core shadcn components"
```

---

### Task 5: Create Theme Config

**Files:**
- Create: `frontend/src/config/theme.config.ts`
- Modify: `frontend/src/contexts/ThemeContext.tsx`

**Step 1: Create theme config**

```ts
// frontend/src/config/theme.config.ts
export const MANA_THEMES = {
  white: {
    accent: '248 246 216',
    glow: '255 254 245',
    muted: '201 198 165',
    name: 'Plains',
    hex: '#F8F6D8',
  },
  blue: {
    accent: '14 104 171',
    glow: '30 144 255',
    muted: '10 74 122',
    name: 'Island',
    hex: '#0E68AB',
  },
  black: {
    accent: '139 92 246',
    glow: '167 139 250',
    muted: '109 40 217',
    name: 'Swamp',
    hex: '#8B5CF6',
  },
  red: {
    accent: '220 38 38',
    glow: '239 68 68',
    muted: '153 27 27',
    name: 'Mountain',
    hex: '#DC2626',
  },
  green: {
    accent: '22 163 74',
    glow: '34 197 94',
    muted: '21 128 61',
    name: 'Forest',
    hex: '#16A34A',
  },
} as const;

export type ManaTheme = keyof typeof MANA_THEMES;

export const DEFAULT_THEME: ManaTheme = 'blue';
```

**Step 2: Update ThemeContext to use config**

Update `frontend/src/contexts/ThemeContext.tsx` to import and use `MANA_THEMES` from the config file instead of inline definitions.

**Step 3: Verify build passes**

```bash
npm run build
```

**Step 4: Commit**

```bash
git add frontend/src/config/theme.config.ts frontend/src/contexts/ThemeContext.tsx
git commit -m "feat: centralize theme config with mana themes"
```

---

## Phase 2b: Layout Shell

### Task 6: Install Sidebar Components

**Files:**
- Create: `frontend/src/components/ui/sidebar.tsx`
- Create: `frontend/src/components/ui/sheet.tsx`

**Step 1: Install sidebar and sheet**

```bash
cd frontend
npx shadcn@latest add sidebar sheet
```

**Step 2: Verify installation**

```bash
ls src/components/ui/sidebar.tsx src/components/ui/sheet.tsx
```

**Step 3: Verify build passes**

```bash
npm run build
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: install shadcn sidebar and sheet components"
```

---

### Task 7: Create Navigation Config

**Files:**
- Create: `frontend/src/config/navigation.config.ts`

**Step 1: Create navigation config**

```ts
// frontend/src/config/navigation.config.ts
import {
  LayoutDashboard,
  Search,
  Package,
  Star,
  TrendingUp,
  Lightbulb,
  BarChart3,
  Trophy,
  Settings,
  HelpCircle,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  requiresAuth?: boolean;
  badge?: string;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const mainNavItems: NavItem[] = [
  { title: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, requiresAuth: true },
  { title: 'Market', href: '/market', icon: BarChart3 },
  { title: 'Cards', href: '/cards', icon: Search },
  { title: 'Tournaments', href: '/tournaments', icon: Trophy },
];

export const collectionNavItems: NavItem[] = [
  { title: 'Inventory', href: '/inventory', icon: Package, requiresAuth: true },
  { title: 'Collection', href: '/collection', icon: Package, requiresAuth: true },
  { title: 'Want List', href: '/want-list', icon: Star, requiresAuth: true },
];

export const insightsNavItems: NavItem[] = [
  { title: 'Recommendations', href: '/recommendations', icon: TrendingUp, requiresAuth: true },
  { title: 'Insights', href: '/insights', icon: Lightbulb, requiresAuth: true },
];

export const bottomNavItems: NavItem[] = [
  { title: 'Settings', href: '/settings', icon: Settings, requiresAuth: true },
  { title: 'Help', href: '/help', icon: HelpCircle },
];
```

**Step 2: Verify build passes**

```bash
npm run build
```

**Step 3: Commit**

```bash
git add frontend/src/config/navigation.config.ts
git commit -m "feat: create navigation config with all routes"
```

---

### Task 8: Create App Sidebar

**Files:**
- Create: `frontend/src/components/layout/app-sidebar.tsx`
- Create: `frontend/src/components/layout/nav-main.tsx`
- Create: `frontend/src/components/layout/nav-user.tsx`

**Step 1: Create nav-main.tsx**

```tsx
// frontend/src/components/layout/nav-main.tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { type NavItem } from '@/config/navigation.config';
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar';
import { cn } from '@/lib/utils';

interface NavMainProps {
  items: NavItem[];
  label?: string;
}

export function NavMain({ items, label }: NavMainProps) {
  const pathname = usePathname();

  return (
    <SidebarGroup>
      {label && <SidebarGroupLabel>{label}</SidebarGroupLabel>}
      <SidebarMenu>
        {items.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
          return (
            <SidebarMenuItem key={item.href}>
              <SidebarMenuButton asChild isActive={isActive}>
                <Link href={item.href}>
                  <item.icon className={cn(
                    'h-4 w-4',
                    isActive && 'text-[rgb(var(--accent))]'
                  )} />
                  <span>{item.title}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          );
        })}
      </SidebarMenu>
    </SidebarGroup>
  );
}
```

**Step 2: Create nav-user.tsx**

```tsx
// frontend/src/components/layout/nav-user.tsx
'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar';
import { ChevronsUpDown, LogOut, Settings, User } from 'lucide-react';
import Link from 'next/link';

export function NavUser() {
  const { user, logout } = useAuth();

  if (!user) return null;

  const initials = user.display_name
    ? user.display_name.split(' ').map(n => n[0]).join('').toUpperCase()
    : user.email[0].toUpperCase();

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <Avatar className="h-8 w-8">
                <AvatarFallback className="bg-[rgb(var(--accent))] text-white">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">{user.display_name || 'User'}</span>
                <span className="truncate text-xs text-muted-foreground">{user.email}</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-[--radix-dropdown-menu-trigger-width] min-w-56"
            side="bottom"
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="bg-[rgb(var(--accent))] text-white">
                    {initials}
                  </AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">{user.display_name || 'User'}</span>
                  <span className="truncate text-xs text-muted-foreground">{user.email}</span>
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/settings">
                <Settings className="mr-2 h-4 w-4" />
                Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout}>
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
```

**Step 3: Create app-sidebar.tsx**

```tsx
// frontend/src/components/layout/app-sidebar.tsx
'use client';

import * as React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from '@/components/ui/sidebar';
import { NavMain } from './nav-main';
import { NavUser } from './nav-user';
import {
  mainNavItems,
  collectionNavItems,
  insightsNavItems,
  bottomNavItems,
} from '@/config/navigation.config';
import { useAuth } from '@/contexts/AuthContext';

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { user } = useAuth();

  // Filter items based on auth
  const filterItems = (items: typeof mainNavItems) =>
    items.filter(item => !item.requiresAuth || user);

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <Link href={user ? '/dashboard' : '/'} className="flex items-center gap-2 px-2 py-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[rgb(var(--accent))]">
            <span className="font-display text-sm font-bold text-white">DD</span>
          </div>
          <span className="font-heading text-lg font-semibold group-data-[collapsible=icon]:hidden">
            Dualcaster
          </span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={filterItems(mainNavItems)} />
        {user && (
          <>
            <NavMain items={filterItems(collectionNavItems)} label="Collection" />
            <NavMain items={filterItems(insightsNavItems)} label="Insights" />
          </>
        )}
        <NavMain items={filterItems(bottomNavItems)} label="Support" />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
```

**Step 4: Verify build passes**

```bash
npm run build
```

**Step 5: Commit**

```bash
git add frontend/src/components/layout/
git commit -m "feat: create app sidebar with navigation"
```

---

### Task 9: Create Site Header

**Files:**
- Create: `frontend/src/components/layout/site-header.tsx`
- Install: command component for search

**Step 1: Install command component**

```bash
npx shadcn@latest add command
```

**Step 2: Create site-header.tsx**

```tsx
// frontend/src/components/layout/site-header.tsx
'use client';

import { Bell, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { Separator } from '@/components/ui/separator';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

export function SiteHeader() {
  const { user } = useAuth();

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-4" />

      {/* Search */}
      <div className="flex-1">
        <Button
          variant="outline"
          className="w-full max-w-sm justify-start text-muted-foreground"
          onClick={() => {
            // TODO: Open command palette
          }}
        >
          <Search className="mr-2 h-4 w-4" />
          <span>Search cards...</span>
          <kbd className="pointer-events-none ml-auto hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100 sm:flex">
            <span className="text-xs">⌘</span>K
          </kbd>
        </Button>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-2">
        {user && (
          <Button variant="ghost" size="icon" className="relative">
            <Bell className="h-4 w-4" />
            <span className="sr-only">Notifications</span>
          </Button>
        )}
        {!user && (
          <div className="flex items-center gap-2">
            <Button variant="ghost" asChild>
              <Link href="/login">Login</Link>
            </Button>
            <Button asChild>
              <Link href="/register">Get Started</Link>
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
```

**Step 3: Verify build passes**

```bash
npm run build
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: create site header with search and notifications"
```

---

### Task 10: Create Protected Layout with Sidebar

**Files:**
- Create: `frontend/src/app/(protected)/layout.tsx`
- Modify: Move existing protected pages into route group

**Step 1: Create protected layout**

```tsx
// frontend/src/app/(protected)/layout.tsx
'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import { AppSidebar } from '@/components/layout/app-sidebar';
import { SiteHeader } from '@/components/layout/site-header';
import { useAuth } from '@/contexts/AuthContext';

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/login');
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <SiteHeader />
        <main className="flex-1 p-6">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
```

**Step 2: Move protected pages into (protected) route group**

Move these files:
- `dashboard/page.tsx` → `(protected)/dashboard/page.tsx`
- `inventory/page.tsx` → `(protected)/inventory/page.tsx`
- `recommendations/page.tsx` → `(protected)/recommendations/page.tsx`
- `settings/page.tsx` → `(protected)/settings/page.tsx`

**Step 3: Verify build passes**

```bash
npm run build
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: create protected layout with sidebar shell"
```

---

## Phase 2c: Ornate Layer

### Task 11: Create Ornate Card Component

**Files:**
- Create: `frontend/src/components/ornate/ornate-card.tsx`
- Create: `frontend/src/components/ornate/flourish.tsx`

**Step 1: Create flourish.tsx**

```tsx
// frontend/src/components/ornate/flourish.tsx
import { cn } from '@/lib/utils';

interface FlourishProps {
  position: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
  className?: string;
}

export function Flourish({ position, className }: FlourishProps) {
  const positionClasses = {
    'top-left': 'top-1 left-1',
    'top-right': 'top-1 right-1 rotate-90',
    'bottom-left': 'bottom-1 left-1 -rotate-90',
    'bottom-right': 'bottom-1 right-1 rotate-180',
  };

  return (
    <svg
      className={cn(
        'absolute w-4 h-4 text-[rgb(var(--magic-gold))]/40',
        positionClasses[position],
        className
      )}
      viewBox="0 0 24 24"
      fill="currentColor"
    >
      <path d="M2 2 C2 12, 12 12, 12 22 L12 12 L22 12 C12 12, 12 2, 2 2Z" />
    </svg>
  );
}
```

**Step 2: Create ornate-card.tsx**

```tsx
// frontend/src/components/ornate/ornate-card.tsx
import { cn } from '@/lib/utils';
import { Flourish } from './flourish';

export type CardRarity = 'common' | 'uncommon' | 'rare' | 'mythic';

interface OrnateCardProps {
  children: React.ReactNode;
  rarity?: CardRarity;
  className?: string;
  hover?: boolean;
}

const rarityBorders: Record<CardRarity, string> = {
  common: 'border-[rgb(var(--border))]',
  uncommon: 'border-[rgb(var(--silver))]/40',
  rare: 'border-[rgb(var(--gold))]/50',
  mythic: 'border-[rgb(var(--mythic-orange))]/50',
};

const rarityGlows: Record<CardRarity, string> = {
  common: '',
  uncommon: 'hover:shadow-[0_0_15px_rgb(var(--silver)/0.2)]',
  rare: 'hover:shadow-[0_0_20px_rgb(var(--gold)/0.3)]',
  mythic: 'hover:shadow-[0_0_25px_rgb(var(--mythic-orange)/0.4)]',
};

export function OrnateCard({
  children,
  rarity = 'common',
  className,
  hover = true,
}: OrnateCardProps) {
  const showFlourishes = rarity === 'rare' || rarity === 'mythic';

  return (
    <div
      className={cn(
        'relative rounded-lg bg-[rgb(var(--card))] overflow-hidden',
        'transition-all duration-200',
        hover && 'hover:scale-[1.01]',
        hover && rarityGlows[rarity],
        className
      )}
    >
      {/* Outer border */}
      <div className="absolute inset-0 rounded-lg border border-[rgb(var(--border))]" />

      {/* Inner accent border */}
      <div
        className={cn(
          'absolute inset-[3px] rounded-md border',
          rarityBorders[rarity]
        )}
      />

      {/* Corner flourishes */}
      {showFlourishes && (
        <>
          <Flourish position="top-left" />
          <Flourish position="top-right" />
          <Flourish position="bottom-left" />
          <Flourish position="bottom-right" />
        </>
      )}

      {/* Content */}
      <div className="relative p-4">{children}</div>
    </div>
  );
}
```

**Step 3: Verify build passes**

```bash
npm run build
```

**Step 4: Commit**

```bash
git add frontend/src/components/ornate/
git commit -m "feat: create ornate card with rarity borders and flourishes"
```

---

### Task 12: Create Ornate Divider and Page Header

**Files:**
- Create: `frontend/src/components/ornate/divider.tsx`
- Create: `frontend/src/components/ornate/page-header.tsx`

**Step 1: Create divider.tsx**

```tsx
// frontend/src/components/ornate/divider.tsx
import { cn } from '@/lib/utils';

interface OrnateDividerProps {
  className?: string;
}

export function OrnateDivider({ className }: OrnateDividerProps) {
  return (
    <div className={cn('flex items-center gap-4 my-8', className)}>
      <div className="flex-1 h-px bg-gradient-to-r from-transparent via-[rgb(var(--magic-gold))]/30 to-transparent" />
      <svg
        className="w-4 h-4 text-[rgb(var(--magic-gold))]/50"
        viewBox="0 0 24 24"
        fill="currentColor"
      >
        <path d="M12 2L2 12l10 10 10-10L12 2z" />
      </svg>
      <div className="flex-1 h-px bg-gradient-to-r from-transparent via-[rgb(var(--magic-gold))]/30 to-transparent" />
    </div>
  );
}
```

**Step 2: Create page-header.tsx**

```tsx
// frontend/src/components/ornate/page-header.tsx
import { cn } from '@/lib/utils';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
  className?: string;
}

export function PageHeader({ title, subtitle, children, className }: PageHeaderProps) {
  return (
    <div className={cn('relative mb-8 pb-6', className)}>
      {/* Background glow */}
      <div className="absolute inset-0 bg-gradient-to-b from-[rgb(var(--accent))]/5 to-transparent rounded-lg" />

      <div className="relative flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl md:text-4xl text-foreground tracking-wide">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-2 text-muted-foreground">{subtitle}</p>
          )}
        </div>
        {children && <div className="flex items-center gap-2">{children}</div>}
      </div>

      {/* Bottom gradient line */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-[rgb(var(--accent))]/50 via-[rgb(var(--magic-gold))]/30 to-transparent" />
    </div>
  );
}
```

**Step 3: Verify build passes**

```bash
npm run build
```

**Step 4: Commit**

```bash
git add frontend/src/components/ornate/
git commit -m "feat: create ornate divider and page header"
```

---

### Task 13: Add Texture CSS Classes

**Files:**
- Create: `frontend/src/styles/ornate.css`
- Modify: `frontend/src/app/layout.tsx`

**Step 1: Create ornate.css**

```css
/* frontend/src/styles/ornate.css */

/* Subtle noise overlay */
.texture-noise {
  position: relative;
}
.texture-noise::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  opacity: 0.03;
  pointer-events: none;
  mix-blend-mode: overlay;
  border-radius: inherit;
}

/* Parchment effect */
.texture-parchment {
  background:
    radial-gradient(ellipse at center, transparent 0%, rgb(var(--background)) 70%),
    linear-gradient(
      180deg,
      rgb(var(--card)) 0%,
      rgb(var(--secondary)) 50%,
      rgb(var(--card)) 100%
    );
}

/* Vignette */
.vignette {
  box-shadow: inset 0 0 150px 50px rgb(var(--background));
}

/* Glow effects */
.glow-accent {
  transition: box-shadow 0.2s ease;
}
.glow-accent:hover {
  box-shadow:
    0 0 20px rgb(var(--accent) / 0.15),
    0 0 40px rgb(var(--accent) / 0.1);
}

.glow-magic {
  box-shadow:
    0 0 10px rgb(var(--magic-purple) / 0.3),
    0 0 20px rgb(var(--magic-green) / 0.2);
}

.glow-gold {
  box-shadow:
    0 0 15px rgb(var(--magic-gold) / 0.3),
    inset 0 0 15px rgb(var(--magic-gold) / 0.1);
}

/* Foil shimmer */
.foil-shimmer {
  background: linear-gradient(
    125deg,
    rgb(255 0 128) 0%,
    rgb(0 255 255) 25%,
    rgb(255 255 0) 50%,
    rgb(0 255 255) 75%,
    rgb(255 0 128) 100%
  );
  background-size: 400% 400%;
  animation: shimmer 8s ease infinite;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

@keyframes shimmer {
  0%, 100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

/* Fire gradient for price spikes */
.gradient-fire {
  background: linear-gradient(
    90deg,
    rgb(var(--fire-edge)) 0%,
    rgb(var(--fire-core)) 100%
  );
}

/* Ice gradient for price drops */
.gradient-ice {
  background: linear-gradient(
    90deg,
    rgb(var(--ice-edge)) 0%,
    rgb(var(--ice-core)) 100%
  );
}

/* Arcane gradient (logo colors) */
.gradient-arcane {
  background: linear-gradient(
    135deg,
    rgb(var(--magic-purple)) 0%,
    rgb(var(--magic-green)) 100%
  );
}
```

**Step 2: Import in layout.tsx**

Add to `frontend/src/app/layout.tsx`:

```tsx
import '@/styles/ornate.css';
```

**Step 3: Verify build passes**

```bash
npm run build
```

**Step 4: Commit**

```bash
git add frontend/src/styles/ornate.css frontend/src/app/layout.tsx
git commit -m "feat: add ornate texture and glow CSS classes"
```

---

### Task 14: Create Price Change Components

**Files:**
- Create: `frontend/src/components/ornate/price-change.tsx`
- Create: `frontend/src/components/ornate/rarity-badge.tsx`

**Step 1: Create price-change.tsx**

```tsx
// frontend/src/components/ornate/price-change.tsx
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PriceChangeProps {
  value: number;
  format?: 'percent' | 'currency';
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  className?: string;
}

export function PriceChange({
  value,
  format = 'percent',
  size = 'md',
  showIcon = true,
  className,
}: PriceChangeProps) {
  const isPositive = value > 0;
  const isNegative = value < 0;
  const isNeutral = value === 0;

  const sizeClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  const formatted =
    format === 'percent'
      ? `${isPositive ? '+' : ''}${value.toFixed(1)}%`
      : `${isPositive ? '+' : ''}$${Math.abs(value).toFixed(2)}`;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 font-medium',
        sizeClasses[size],
        isPositive && 'text-[rgb(var(--success))]',
        isNegative && 'text-[rgb(var(--destructive))]',
        isNeutral && 'text-muted-foreground',
        className
      )}
    >
      {showIcon && (
        <>
          {isPositive && <TrendingUp className={iconSizes[size]} />}
          {isNegative && <TrendingDown className={iconSizes[size]} />}
          {isNeutral && <Minus className={iconSizes[size]} />}
        </>
      )}
      {formatted}
    </span>
  );
}
```

**Step 2: Create rarity-badge.tsx**

```tsx
// frontend/src/components/ornate/rarity-badge.tsx
import { cn } from '@/lib/utils';
import { type CardRarity } from './ornate-card';

interface RarityBadgeProps {
  rarity: CardRarity;
  className?: string;
}

const rarityStyles: Record<CardRarity, string> = {
  common: 'bg-[rgb(var(--border))] text-muted-foreground',
  uncommon: 'bg-[rgb(var(--silver))]/20 text-[rgb(var(--silver))] border-[rgb(var(--silver))]/30',
  rare: 'bg-[rgb(var(--gold))]/20 text-[rgb(var(--gold))] border-[rgb(var(--gold))]/30',
  mythic: 'bg-[rgb(var(--mythic-orange))]/20 text-[rgb(var(--mythic-orange))] border-[rgb(var(--mythic-orange))]/30',
};

const rarityLabels: Record<CardRarity, string> = {
  common: 'Common',
  uncommon: 'Uncommon',
  rare: 'Rare',
  mythic: 'Mythic',
};

export function RarityBadge({ rarity, className }: RarityBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border',
        rarityStyles[rarity],
        className
      )}
    >
      {rarityLabels[rarity]}
    </span>
  );
}
```

**Step 3: Verify build passes**

```bash
npm run build
```

**Step 4: Commit**

```bash
git add frontend/src/components/ornate/
git commit -m "feat: create price change and rarity badge components"
```

---

### Task 15: Download and Setup Custom Icons

**Files:**
- Create: `frontend/src/components/icons/index.tsx`
- Create: Multiple icon files

**Step 1: Create icon wrapper and first icons**

```tsx
// frontend/src/components/icons/index.tsx
export { IconDashboard } from './dashboard';
export { IconSearch } from './search';
export { IconInventory } from './inventory';
export { IconCollection } from './collection';
export { IconWantList } from './want-list';
export { IconSettings } from './settings';
export { IconBuy } from './buy';
export { IconSell } from './sell';
export { IconHold } from './hold';
export { IconPriceUp } from './price-up';
export { IconPriceDown } from './price-down';
export { IconImport } from './import';
export { IconExport } from './export';
export { IconFilter } from './filter';
export { IconRefresh } from './refresh';
export { IconAlert } from './alert';
```

**Step 2: Create sample icon (dashboard - treasure chest style)**

```tsx
// frontend/src/components/icons/dashboard.tsx
import { cn } from '@/lib/utils';

interface IconProps {
  className?: string;
}

export function IconDashboard({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 512 512"
      fill="currentColor"
      className={cn('w-5 h-5', className)}
    >
      {/* Simplified treasure chest / dashboard icon */}
      <path d="M256 32C132.3 32 32 132.3 32 256s100.3 224 224 224 224-100.3 224-224S379.7 32 256 32zm0 64c88.4 0 160 71.6 160 160s-71.6 160-160 160S96 344.4 96 256 167.6 96 256 96zm0 32c-70.7 0-128 57.3-128 128s57.3 128 128 128 128-57.3 128-128-57.3-128-128-128zm0 48a80 80 0 110 160 80 80 0 010-160z" />
    </svg>
  );
}
```

**Note:** Full icon set will be downloaded from game-icons.net and converted to React components. For now, create placeholder icons that use currentColor for theme support.

**Step 3: Create remaining placeholder icons**

Create similar files for each icon in the index. Each should:
- Accept `className` prop
- Use `fill="currentColor"` for theme support
- Default to `w-5 h-5` size

**Step 4: Verify build passes**

```bash
npm run build
```

**Step 5: Commit**

```bash
git add frontend/src/components/icons/
git commit -m "feat: create custom icon components with theme support"
```

---

## Phase 2d: Page Rebuilds

### Task 16: Rebuild Landing Page

**Files:**
- Create: `frontend/src/app/(public)/layout.tsx`
- Modify: `frontend/src/app/page.tsx` → Move to `frontend/src/app/(public)/page.tsx`
- Create: `frontend/src/components/features/landing/hero.tsx`
- Create: `frontend/src/components/features/landing/features-grid.tsx`
- Create: `frontend/src/components/layout/public-header.tsx`
- Create: `frontend/src/components/layout/footer.tsx`

**Step 1: Create public layout**

```tsx
// frontend/src/app/(public)/layout.tsx
import { PublicHeader } from '@/components/layout/public-header';
import { Footer } from '@/components/layout/footer';

export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <PublicHeader />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}
```

**Step 2: Create public header**

```tsx
// frontend/src/components/layout/public-header.tsx
'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';

export function PublicHeader() {
  const { user } = useAuth();

  return (
    <header className="border-b border-border">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[rgb(var(--accent))]">
            <span className="font-display text-sm font-bold text-white">DD</span>
          </div>
          <span className="font-heading text-xl font-semibold">Dualcaster Deals</span>
        </Link>

        <nav className="hidden md:flex items-center gap-6">
          <Link href="/market" className="text-muted-foreground hover:text-foreground transition-colors">
            Market
          </Link>
          <Link href="/cards" className="text-muted-foreground hover:text-foreground transition-colors">
            Cards
          </Link>
          <Link href="/tournaments" className="text-muted-foreground hover:text-foreground transition-colors">
            Tournaments
          </Link>
        </nav>

        <div className="flex items-center gap-2">
          {user ? (
            <Button asChild>
              <Link href="/dashboard">Dashboard</Link>
            </Button>
          ) : (
            <>
              <Button variant="ghost" asChild>
                <Link href="/login">Login</Link>
              </Button>
              <Button asChild>
                <Link href="/register">Get Started</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
```

**Step 3: Create footer**

```tsx
// frontend/src/components/layout/footer.tsx
import Link from 'next/link';
import { OrnateDivider } from '@/components/ornate/divider';

export function Footer() {
  return (
    <footer className="border-t border-border bg-card">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div>
            <h4 className="font-heading text-sm font-semibold mb-4">Product</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/market" className="hover:text-foreground">Market</Link></li>
              <li><Link href="/cards" className="hover:text-foreground">Card Search</Link></li>
              <li><Link href="/tournaments" className="hover:text-foreground">Tournaments</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="font-heading text-sm font-semibold mb-4">Company</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/about" className="hover:text-foreground">About</Link></li>
              <li><Link href="/contact" className="hover:text-foreground">Contact</Link></li>
              <li><Link href="/changelog" className="hover:text-foreground">Changelog</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="font-heading text-sm font-semibold mb-4">Support</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/help" className="hover:text-foreground">Help & FAQ</Link></li>
              <li><a href="mailto:support@dualcasterdeals.com" className="hover:text-foreground">Email Support</a></li>
            </ul>
          </div>
          <div>
            <h4 className="font-heading text-sm font-semibold mb-4">Legal</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/privacy" className="hover:text-foreground">Privacy Policy</Link></li>
              <li><Link href="/terms" className="hover:text-foreground">Terms of Service</Link></li>
              <li><Link href="/attributions" className="hover:text-foreground">Attributions</Link></li>
            </ul>
          </div>
        </div>

        <OrnateDivider className="my-8" />

        <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-muted-foreground">
          <p>&copy; 2025 Dualcaster Deals. Not affiliated with Wizards of the Coast.</p>
          <a href="mailto:support@dualcasterdeals.com" className="hover:text-[rgb(var(--accent))]">
            support@dualcasterdeals.com
          </a>
        </div>
      </div>
    </footer>
  );
}
```

**Step 4: Create hero component**

```tsx
// frontend/src/components/features/landing/hero.tsx
'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Search } from 'lucide-react';

export function Hero() {
  return (
    <section className="relative py-20 md:py-32">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-[rgb(var(--accent))]/5 via-transparent to-transparent" />

      <div className="relative max-w-4xl mx-auto px-6 text-center">
        <h1 className="font-display text-4xl md:text-6xl font-bold tracking-wide mb-6">
          Make Smarter{' '}
          <span className="text-[rgb(var(--accent))]">MTG Market</span>{' '}
          Decisions
        </h1>

        <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
          Accurate pricing data. Real-time alerts. Know exactly when to buy, sell, or hold.
        </p>

        {/* Search bar */}
        <div className="max-w-xl mx-auto mb-8">
          <Link href="/cards">
            <div className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border bg-card hover:border-[rgb(var(--accent))]/50 transition-colors cursor-pointer">
              <Search className="w-5 h-5 text-muted-foreground" />
              <span className="text-muted-foreground">Search any card...</span>
            </div>
          </Link>
        </div>

        {/* Stats */}
        <div className="flex flex-wrap justify-center gap-8 text-sm text-muted-foreground mb-8">
          <span>90,000+ cards tracked</span>
          <span>Live prices</span>
          <span>Tournament meta</span>
        </div>

        {/* CTA */}
        <div className="flex flex-wrap justify-center gap-4">
          <Button size="lg" asChild>
            <Link href="/register">Get Started Free</Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <Link href="/market">View Market</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
```

**Step 5: Create landing page**

```tsx
// frontend/src/app/(public)/page.tsx
import { Hero } from '@/components/features/landing/hero';

export default function LandingPage() {
  return (
    <>
      <Hero />
      {/* Additional sections will be added: Features, Live Data Preview, CTA */}
    </>
  );
}
```

**Step 6: Verify build passes**

```bash
npm run build
```

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: rebuild landing page with public layout and hero"
```

---

**[CONTINUED IN SUBSEQUENT TASKS...]**

The plan continues with:
- Tasks 17-18: Login/Register pages
- Tasks 19-22: Dashboard, Cards, Inventory rebuilds
- Tasks 23-26: New pages (Collection, Want List, Insights, Market)
- Task 27: Settings rebuild
- Tasks 28-32: Support pages (About, Contact, Help, Legal, Error pages)
- Tasks 33-35: Polish (animations, responsive, accessibility)

---

## Execution Notes

**Total Tasks:** 35
**Estimated Time:** 2-3 sessions with subagent-driven development

**Testing Strategy:**
- Each task ends with `npm run build` verification
- Visual testing in browser after major components
- Lighthouse audit at end of Phase 2f

**Commit Frequency:**
- One commit per task
- Clear commit messages with `feat:`, `fix:`, `refactor:` prefixes
