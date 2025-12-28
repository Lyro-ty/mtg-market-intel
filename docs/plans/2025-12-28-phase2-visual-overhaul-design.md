# Phase 2: Visual Overhaul - Design Document

**Date:** 2025-12-28
**Status:** Approved
**Scope:** Full UI rebuild with shadcn/ui + "Ornate Saga" MTG theme

---

## Executive Summary

Complete visual overhaul of Dualcaster Deals using shadcn/ui as the component foundation, with an "Ornate Saga" decorative layer that brings MTG-themed premium aesthetics: gold borders, custom fantasy icons, Cinzel typography, and dynamic mana color themes.

---

## Section 1: Foundation & Architecture

### Approach
Full shadcn migration with "Ornate Saga" theme layer on top.

### Directory Structure
```
frontend/
├── components/
│   ├── ui/              # shadcn components (owned, customizable)
│   ├── ornate/          # MTG decorative layer
│   ├── icons/           # Custom MTG icons from game-icons.net
│   ├── layout/          # App shell (sidebar, header)
│   ├── features/        # Page-specific components
│   ├── auth/            # Auth forms
│   └── charts/          # Chart components
├── contexts/            # React contexts
├── hooks/               # Custom hooks
├── lib/                 # Utilities
├── styles/              # Additional CSS
└── config/              # Theme, navigation, site config
```

### Navigation Pattern
Hybrid navigation: collapsible sidebar (shadcn sidebar-07) + slim top header for logo, search, and user menu.

```
┌─────────────────────────────────────────────────────┐
│ [Logo]     [🔍 Search cards...]        [🔔] [Avatar]│
├────────┬────────────────────────────────────────────┤
│ Sidebar│         Main Content Area                  │
│ (icons │                                            │
│  when  │                                            │
│ collapsed)                                          │
└────────┴────────────────────────────────────────────┘
```

---

## Section 2: Typography & Color System

### Typography Stack

| Use Case | Font | Weight |
|----------|------|--------|
| Page titles | Cinzel Decorative | 700 |
| Section headers | Cinzel | 600 |
| Card titles | Cinzel | 500 |
| Body text | Inter | 400 |
| UI elements | Inter | 500-600 |
| Numbers/prices | Inter Tabular | 600 |

### Tailwind Config
```ts
fontFamily: {
  display: ['Cinzel Decorative', 'serif'],
  heading: ['Cinzel', 'serif'],
  sans: ['Inter', 'sans-serif'],
}
```

### Base Color System (Dark Theme Only)
```css
:root {
  /* Base */
  --background: 12 12 16;        /* #0C0C10 */
  --surface: 20 20 26;           /* #14141A */
  --elevated: 28 28 36;          /* #1C1C24 */
  --border: 42 42 53;            /* #2A2A35 */

  /* Text */
  --foreground: 245 245 245;
  --muted-foreground: 163 163 163;

  /* Magic accents (from logo) */
  --magic-purple: 139 92 246;    /* #8B5CF6 */
  --magic-green: 34 197 94;      /* #22C55E */
  --magic-gold: 212 175 55;      /* #D4AF37 */

  /* Semantic */
  --success: 34 197 94;
  --danger: 239 68 68;
  --warning: 251 191 36;
  --info: 59 130 246;
}
```

### Mana Themes (User-Selectable)
```ts
export const MANA_THEMES = {
  white: { accent: '248 246 216', glow: '255 254 245', muted: '201 198 165', name: 'Plains' },
  blue:  { accent: '14 104 171',  glow: '30 144 255',  muted: '10 74 122',   name: 'Island' },
  black: { accent: '139 92 246',  glow: '167 139 250', muted: '109 40 217',  name: 'Swamp' },
  red:   { accent: '220 38 38',   glow: '239 68 68',   muted: '153 27 27',   name: 'Mountain' },
  green: { accent: '22 163 74',   glow: '34 197 94',   muted: '21 128 61',   name: 'Forest' },
} as const;
```

### Exotic Accent Colors
```css
:root {
  /* Ethereal/Mystical */
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

  /* Arcane gradient */
  --arcane-start: 139 92 246;
  --arcane-end: 34 197 94;

  /* Foil shimmer */
  --foil-1: 255 0 128;
  --foil-2: 0 255 255;
  --foil-3: 255 255 0;
}
```

---

## Section 3: Ornate Decorative System

### Card Frame System
- Outer border: subtle `--border` color
- Inner accent border: 3px inset, color based on rarity
- Corner flourishes: gold SVG accents for rare/mythic cards

### Rarity Border Colors
| Rarity | Border Color |
|--------|--------------|
| Common | `--border` |
| Uncommon | `--silver` at 40% |
| Rare | `--gold` at 50% |
| Mythic | `--mythic-orange` at 50% |

### Background Textures
- `.texture-noise` - Subtle grain overlay (3% opacity)
- `.texture-parchment` - Radial gradient for special sections
- `.vignette` - Inset shadow for page edges

### Decorative Elements
- `<OrnateDivider />` - Gradient line with diamond/mana symbol
- `<Flourish />` - Corner SVG accents
- `<PageHeader />` - Title with gradient underline

### Glow Effects
```css
.glow-accent { box-shadow: 0 0 20px rgb(var(--accent) / 0.15); }
.glow-magic { box-shadow: 0 0 10px rgb(var(--magic-purple) / 0.3), 0 0 20px rgb(var(--magic-green) / 0.2); }
.glow-gold { box-shadow: 0 0 15px rgb(var(--magic-gold) / 0.3); }
```

### Foil Shimmer Animation
```css
.foil-shimmer {
  background: linear-gradient(125deg, var(--foil-1), var(--foil-2), var(--foil-3), var(--foil-2), var(--foil-1));
  background-size: 400% 400%;
  animation: shimmer 8s ease infinite;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
```

---

## Section 4: Component Migration

### Current → shadcn Replacements
| Current | shadcn Replacement |
|---------|-------------------|
| ui/Button.tsx | @shadcn/button |
| ui/Card.tsx | @shadcn/card |
| ui/Input.tsx | @shadcn/input + field |
| ui/Badge.tsx | @shadcn/badge |
| ui/Skeleton.tsx | @shadcn/skeleton |
| ui/Toast.tsx | @shadcn/sonner |
| ui/Sidebar.tsx | @shadcn/sidebar |

### New shadcn Components
**Core UI:** button, card, input, label, badge, skeleton, sonner, dialog, dropdown-menu, select, tabs, table, tooltip, avatar, separator, scroll-area

**Navigation:** sidebar, navigation-menu, breadcrumb, command, sheet

**Forms:** form, field, checkbox, switch, radio-group, textarea

**Data Display:** chart, progress, alert, alert-dialog, hover-card, popover

**Blocks:** dashboard-01, sidebar-07, login-01/04, chart-line-dots

---

## Section 5: Custom Icons

### Source
game-icons.net (CC BY 3.0 - attribution required)

### Icon Set
| Purpose | Icon | game-icons.net search |
|---------|------|----------------------|
| Dashboard | Planeswalker spark | spark, flame |
| Search | Scrying orb | crystal-ball |
| Inventory | Treasure chest | chest |
| Collection | Stacked tomes | spell-book |
| Want List | Glowing star | star |
| Settings | Arcane gear | gear, rune |
| Alerts | Crystal bell | bell |
| Buy | Hand receiving | receive |
| Sell | Hand offering | sell, give |
| Hold | Shield hourglass | shield |
| Price Up | Flame arrow | arrow-up, flame |
| Price Down | Ice arrow | arrow-down |
| Import | Portal inward | portal |
| Export | Portal outward | portal |
| Filter | Alchemist sieve | funnel |
| Refresh | Cyclical runes | cycle |

### Implementation
- SVGs with `fill="currentColor"` for theme sync
- Wrapped in React components
- Automatically inherit mana accent color

---

## Section 6: Page Architecture

### Route Groups
```
app/(public)/     # No sidebar - landing, auth, public pages
app/(protected)/  # With sidebar - authenticated app
```

### Public Pages
| Route | Purpose |
|-------|---------|
| `/` | Landing page |
| `/login` | Login form |
| `/register` | Registration form |
| `/market` | Public market data |
| `/tournaments` | TopDeck.gg data |
| `/about` | About us |
| `/contact` | Support email & form |
| `/help` | FAQ & guides |
| `/privacy` | Privacy policy |
| `/terms` | Terms of service |
| `/attributions` | Credits & licenses |
| `/changelog` | Version history |

### Protected Pages
| Route | Purpose |
|-------|---------|
| `/dashboard` | Personalized home |
| `/cards` | Card search |
| `/cards/[id]` | Card detail |
| `/inventory` | User's cards |
| `/collection` | Set completion tracking |
| `/want-list` | Price targets |
| `/insights` | Actionable alerts |
| `/recommendations` | Buy/sell/hold signals |
| `/settings` | Account & preferences |

### New Pages Detail

**Collection** (`/collection`)
- Set Progress tab: completion % per set
- Binder View tab: visual grid
- Stats tab: value charts, milestones

**Want List** (`/want-list`)
- Target price tracking
- Priority tags
- TCGPlayer affiliate links
- Price alerts

**Insights** (`/insights`)
- Portfolio alerts (your cards)
- Market opportunities
- Educational content

**Market** (`/market`) - Public
- Market index chart
- Top gainers/losers
- Format health
- Trending cards

---

## Section 7: Implementation Phases

### Phase 2a: Foundation Setup (5 tasks)
1. Initialize shadcn in frontend/
2. Configure tailwind with custom theme
3. Set up fonts (Cinzel, Inter)
4. Configure color system in globals.css
5. Add core utilities (cn, theme config)

### Phase 2b: Layout Shell (5 tasks)
6. Install sidebar component + sidebar-07 block
7. Create site-header component
8. Create app-shell layout wrapper
9. Add mobile sheet drawer
10. Migrate navigation items with icons

### Phase 2c: Ornate Layer (5 tasks)
11. Create ornate-card component
12. Create flourish, divider components
13. Add texture CSS classes
14. Create page-header component
15. Download & integrate game-icons

### Phase 2d: Page Rebuilds (12 tasks)
16. Landing page
17. Login page
18. Register page
19. Dashboard
20. Cards search
21. Card detail
22. Inventory
23. Collection (new)
24. Want List (new)
25. Insights (new)
26. Market (new)
27. Settings

### Phase 2e: Support & Error Pages (5 tasks)
28. About page
29. Contact page
30. Help/FAQ page
31. Legal pages (privacy, terms, attributions)
32. Error pages (404, 500, loading)

### Phase 2f: Polish & QA (3 tasks)
33. Animation & transition polish
34. Mobile responsive pass
35. Accessibility audit

**Total: ~35 tasks**

---

## Success Criteria

- [ ] All pages use consistent shadcn components
- [ ] Mana theme switching works across entire app
- [ ] Ornate styling feels premium and MTG-themed
- [ ] Custom icons render in all theme colors
- [ ] Mobile responsive with drawer navigation
- [ ] All support/legal pages complete
- [ ] Attribution for game-icons, TopDeck, Scryfall, WotC
- [ ] Lighthouse accessibility score > 90

---

## Attribution Requirements

```
Dualcaster Deals is unofficial Fan Content permitted under the
Fan Content Policy. Not approved/endorsed by Wizards. Portions
of the materials used are property of Wizards of the Coast.
©Wizards of the Coast LLC.

Card data provided by Scryfall.
Tournament data provided by TopDeck.gg.
Icons from game-icons.net under CC BY 3.0.
```

---

## Related Documents

- `docs/plans/2025-12-27-complete-frontend-redesign-design.md` - Master design
- `docs/plans/2025-12-27-phase1-security-auth.md` - Phase 1 (completed)
- `docs/plans/2025-12-25-frontend-redesign-design.md` - Original mana themes
