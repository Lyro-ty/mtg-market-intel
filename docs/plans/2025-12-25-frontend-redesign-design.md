# Frontend Redesign: MTG-Themed Visual Identity & UX Overhaul

**Date:** 2025-12-25
**Status:** Approved
**Scope:** Full frontend redesign with phased implementation

---

## Overview

Transform the current "rough draft" frontend into a polished, MTG-themed experience with:
- 5 mana color themes (dark mode only)
- Complete UX overhaul (toasts, skeletons, animations)
- New dashboard and onboarding flow
- Accessibility foundations
- Mobile-optimized experience
- Custom MTG icon set

---

## Design Decisions

### Theme Approach
- **Accent-only theming** — Mana colors as accents against neutral dark backgrounds
- **Dark mode only** — Better for extended use, makes mana colors pop
- **Instant switching** — Theme changes apply immediately, no page reload

---

## Section 1: MTG Color Theme System

### The Five Mana Palettes

| Theme | Primary Accent | Glow/Hover | Muted Accent |
|-------|---------------|------------|--------------|
| White | `#F8F6D8` (cream) | `#FFFEF5` | `#C9C6A5` |
| Blue | `#0E68AB` (ocean) | `#1E90FF` | `#0A4A7A` |
| Black | `#8B5CF6` (violet) | `#A78BFA` | `#6D28D9` |
| Red | `#DC2626` (crimson) | `#EF4444` | `#991B1B` |
| Green | `#16A34A` (emerald) | `#22C55E` | `#15803D` |

*Note: Black mana uses violet/purple — true black would be invisible on dark backgrounds.*

### Background System (shared across all themes)

| Layer | Color | Use |
|-------|-------|-----|
| Base | `#0C0C10` | Page background |
| Surface | `#14141A` | Cards, modals |
| Elevated | `#1C1C24` | Dropdowns, popovers |
| Border | `#2A2A35` | Subtle dividers |

### Accent Application

- **Buttons:** Solid accent with glow on hover
- **Links:** Accent color, brighter on hover
- **Active nav:** Accent underline/background tint
- **Charts:** Accent as primary data color
- **Badges:** Accent background with appropriate text contrast

---

## Section 2: Component Styling

### Buttons

**Primary:**
- Solid accent background
- Subtle gradient (accent → slightly darker)
- Glow on hover (`box-shadow: 0 0 20px accent/40%`)
- Scale 1.02 on hover, 0.98 on click

**Secondary:**
- Transparent with accent border
- Fill with accent/10% on hover

**Ghost:**
- Text-only in accent color
- Underline on hover

### Cards

- Background: Surface color (`#14141A`)
- Border: 1px solid border color, accent tint on hover
- Subtle accent glow on hover for interactive cards
- Optional thin accent top-border for highlighted cards

### Form Inputs

- Dark background (`#0C0C10`)
- Border transitions to accent on focus
- Accent-colored focus ring with glow

### Navigation

- Active: Accent underline (3px) + text in accent
- Inactive: Muted foreground
- Hover: Text brightens, subtle accent background tint

### Data Visualization

- Primary data: Accent color
- Secondary data: Muted gray (`#6B7280`)
- Positive change: Green (consistent)
- Negative change: Red (consistent)
- Grid lines: Very subtle (`#1F1F28`)

---

## Section 3: Toast Notification System

### Toast Types

| Type | Color | Icon | Use Case |
|------|-------|------|----------|
| Success | Green | Checkmark | Confirmations |
| Error | Red | X-circle | Failures |
| Warning | Amber | Alert | Partial issues |
| Info | Accent | Info | Status updates |

### Behavior

- **Position:** Bottom-right (desktop), bottom-center (mobile)
- **Stack:** Up to 3 visible
- **Duration:** 4 seconds default, errors persist
- **Dismissible:** Click X or swipe
- **Undo:** Destructive actions include 5-second undo window

### Animation

- Enter: Slide in from right + fade (200ms)
- Exit: Fade out + slide down (150ms)

### Implementation

```tsx
const { toast } = useToast();
toast.success("Card added to inventory");
toast.error("Import failed", { description: "Line 3: Card not found" });
```

### Toast Scenarios

**Inventory:**
- Card added/removed (+ Undo)
- Quantity updated
- Import complete/partial failure
- Export downloaded
- Valuations refreshed

**Recommendations:**
- Analysis running/complete
- Recommendation dismissed
- Critical alert

**Authentication:**
- Login/logout
- Session expiring (with action)
- Session expired

**Settings:**
- Settings saved
- Marketplace toggled
- Save failed

**Real-time:**
- Price updates
- Price alert triggered
- Connection lost/restored

---

## Section 4: Loading States & Skeletons

### Skeleton Components

| Content | Skeleton |
|---------|----------|
| Card grid | Card-shaped rectangles with image, title, price placeholders |
| Inventory list | Rows with avatar, text lines, price |
| Stats cards | Rounded rectangles matching layout |
| Charts | Rectangle with faint axis lines |
| Recommendations | Card with badge, text, button placeholders |

### Loading Hierarchy

1. **Initial load:** Full skeleton matching page layout
2. **Refetch:** Subtle indicator, content stays visible
3. **Action pending:** Button spinner, stays disabled
4. **Background sync:** No interruption, toast when complete

### Shimmer Animation

- Gradient sweep: transparent → accent/5% → transparent
- Duration: 1.5s infinite
- Picks up hint of current mana accent

---

## Section 5: Micro-Animations

### Page Transitions

- Enter: Fade in (150ms) + slide up (8px)
- Exit: Fade out (100ms)
- Tab switch: Crossfade

### Interactive Elements

| Element | Hover | Click |
|---------|-------|-------|
| Buttons | Scale 1.02, glow | Scale 0.98 |
| Cards | Border accent tint, lift shadow | Accent pulse |
| Links | Brighten, underline slides in | — |
| Nav items | Background tint fades in | Underline grows from center |

### Data Animations

- Numbers: Count up/down (500ms ease-out)
- Charts: Lines draw in, bars grow up
- Progress bars: Smooth width transitions

### Feedback Animations

- Success: Checkmark draws itself
- Error: Subtle shake
- Added: Slide in + highlight
- Removed: Fade + slide out

### Performance Rules

- Only animate `transform` and `opacity`
- Respect `prefers-reduced-motion`
- Keep under 300ms for interactions

---

## Section 6: Dashboard

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Welcome back, [Name]               [Quick Actions]         │
├─────────────────────────────────────────────────────────────┤
│  [Portfolio Value] [Today's Change] [Alerts] [Trend]        │
├─────────────────────────────────────────────────────────────┤
│  Portfolio Chart (30d)        │  Top Movers Today           │
├───────────────────────────────┼─────────────────────────────┤
│  Recent Recommendations       │  Quick Actions              │
└─────────────────────────────────────────────────────────────┘
```

### Sections

1. **Greeting + Quick Actions** — Personalized header
2. **Stats Row** — 4 key metrics at a glance
3. **Portfolio Chart** — 30-day trend
4. **Top Movers** — Cards with biggest swings
5. **Recommendations** — Top 3-5 actionable items
6. **Quick Actions** — Primary workflow buttons

### Empty State (new users)

Onboarding prompt with two paths:
- "Import my collection"
- "Browse cards first"

---

## Section 7: Onboarding Flow

### Step 1: Welcome Modal

- Appears once after first login
- Theme selection (5 mana orbs)
- "Get Started" + "Skip for now"

### Step 2: Dashboard Empty State

- Gentle prompt, not blocking
- Two paths: Import or Browse

### Step 3: Contextual Tooltips

| Page | Tooltip Target |
|------|----------------|
| Cards | Search bar |
| Inventory | Import button |
| Recommendations | First recommendation |
| Settings | Threshold sliders |

Each shows once, "Got it" to dismiss, never returns.

### Step 4: First Success

- Confetti animation (subtle, 2s)
- Celebratory toast
- Dashboard populates

### Escape Hatches

- Skip link always visible
- X to dismiss any modal/tooltip
- Dismissal persisted (no nagging)
- "Restart tour" in Settings

---

## Section 8: Accessibility

### Keyboard Navigation

- All elements focusable via Tab
- Visible focus rings (accent-colored)
- Escape closes modals/dropdowns
- Arrow keys in menus/tabs
- Modal focus trapping

### Semantic Structure

```html
<header> → Top navigation
<main>   → Page content
<nav>    → Navigation menus
<section> → Logical groups
<article> → Cards, items
```

### ARIA Labels

| Element | ARIA |
|---------|------|
| Icon buttons | `aria-label` |
| Loading states | `aria-live`, `aria-busy` |
| Toasts | `role="alert"` / `role="status"` |
| Modals | `role="dialog"`, `aria-modal` |
| Tabs | `role="tablist"`, `role="tab"`, `role="tabpanel"` |

### Focus Management

- Modal close → focus returns to trigger
- Item delete → focus moves to next item
- Page nav → focus to main content

### Additional

- Skip to main content link
- Form labels + `aria-describedby`
- 44px minimum touch targets
- `prefers-reduced-motion` support
- `prefers-contrast: more` support

---

## Section 9: Mobile Experience

### Navigation

Bottom tab bar for primary actions:

| Icon | Label |
|------|-------|
| Home | Dashboard |
| Search | Cards |
| Library | Inventory |
| Trending | Recommendations |
| Sliders | Settings |

### Touch Optimizations

- Pull to refresh
- Swipe left for actions
- Swipe between tabs
- Long press for preview
- 44px minimum targets

### Mobile Layouts

- Cards: Single column
- Charts: Full-width, taller
- Modals: Full-screen slide-up
- Tables: Horizontal scroll or card collapse
- Stats: 2x2 grid

### Performance

- Lazy load below fold
- Reduced chart data points
- Critical skeleton loaders

---

## Section 10: Custom MTG Icon Set

### Navigation Icons (5)

| Name | Description |
|------|-------------|
| home | Planeswalker Spark — 5-pointed spark |
| search | Scrying Eye — eye with circles |
| inventory | Stacked Tomes — cards at angle |
| recommendations | Oracle Scales — balanced scales |
| settings | Gear Rune — gear with runes |

### Mana Theme Orbs (5)

| Color | Symbol |
|-------|--------|
| White | Radiating sun |
| Blue | Water droplet |
| Black | Skull silhouette |
| Red | Flame |
| Green | Tree/leaf |

### Card & Trading Icons (10)

| Name | Use |
|------|-----|
| foil | Holographic diamond |
| rarity-common | Empty circle |
| rarity-uncommon | Half-filled diamond |
| rarity-rare | Filled gem |
| rarity-mythic | Flame gem |
| price-up | Arrow + coins |
| price-down | Inverted arrow + coins |
| alert | Cracked bell |
| buy | Hand receiving card |
| sell | Hand giving card |
| hold | Shield |

### Status & Action Icons (8)

| Name | Use |
|------|-----|
| import | Portal in (swirl) |
| export | Portal out |
| refresh | Cyclical runes |
| spark | Small spark |
| void | Dissolve particles |
| link | Chain links |
| filter | Sieve rune |
| sort | Stacked lines |

### Style Guide

- Stroke: 1.5px
- Viewbox: 24x24
- Single color, inherits `currentColor`
- Variants: Outline (default), Filled (active)

**Total: 28 custom icons**

---

## Section 11: Settings Page

### Structure

1. **Appearance** — Mana theme picker (5 orbs)
2. **Trading Preferences** — ROI, confidence, horizon, lookback sliders
3. **Marketplaces** — Enable/disable with API status
4. **Notifications** — Future (coming soon)
5. **Help & Data** — Restart tour, export, delete account

### Theme Picker Behavior

- Click orb → Instant switch
- Selected: Accent glow + underline
- Smooth transition (300ms)
- Saved to user profile

---

## Implementation Phases

### Phase 1: Visual Identity

| Feature | Scope |
|---------|-------|
| Theme system | CSS variables, context, persistence |
| Theme picker | Settings orb selector |
| Component restyling | All components with accents |
| Custom icons | 28-icon SVG set |
| Base animations | Hovers, feedback, page transitions |

### Phase 2: Feedback & Polish

| Feature | Scope |
|---------|-------|
| Toast system | Provider, hook, all scenarios |
| Skeleton loaders | All content types |
| Micro-animations | Numbers, charts, feedback |
| Loading states | Refetch, pending indicators |
| Reduced motion | Media query support |

### Phase 3: Structure & Flow

| Feature | Scope |
|---------|-------|
| Dashboard | New home with stats, chart, movers |
| Onboarding | Welcome modal, tooltips |
| Settings redesign | Full new layout |
| Empty states | Enhanced with CTAs |

### Phase 4: Accessibility & Mobile

| Feature | Scope |
|---------|-------|
| Semantic HTML | Proper landmarks |
| ARIA labels | All elements |
| Keyboard nav | Focus management, skip links |
| Bottom tab bar | Mobile nav |
| Touch gestures | Pull refresh, swipe |
| Mobile layouts | Responsive optimizations |

---

## Technical Notes

### Theme Implementation

```tsx
// ThemeContext.tsx
type ManaTheme = 'white' | 'blue' | 'black' | 'red' | 'green';

const ThemeContext = createContext<{
  theme: ManaTheme;
  setTheme: (theme: ManaTheme) => void;
}>();

// CSS variables updated on theme change
document.documentElement.style.setProperty('--accent', themeColors[theme].primary);
```

### Toast Implementation

```tsx
// ToastContext.tsx
const ToastContext = createContext<{
  toast: {
    success: (message: string, options?: ToastOptions) => void;
    error: (message: string, options?: ToastOptions) => void;
    warning: (message: string, options?: ToastOptions) => void;
    info: (message: string, options?: ToastOptions) => void;
  };
}>();
```

### Icon Implementation

```tsx
// Custom icon component
import { icons } from '@/components/icons/mtg-icons';

<MtgIcon name="planeswalker-spark" className="w-6 h-6 text-accent" />
```

---

## Success Criteria

- [ ] All 5 themes visually distinct and polished
- [ ] Every user action has appropriate feedback
- [ ] New users complete onboarding without confusion
- [ ] Keyboard-only navigation works throughout
- [ ] Mobile experience feels native
- [ ] Page load feels instant (skeletons)
- [ ] Animations enhance without distracting
