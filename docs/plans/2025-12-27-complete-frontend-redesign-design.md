# Complete Frontend Redesign - Dualcaster Deals

**Date:** 2025-12-27
**Status:** Draft - Pending Approval
**Scope:** Full site redesign including new pages, visual overhaul, security, and features

---

## Executive Summary

Transform Dualcaster Deals from a rough prototype into a polished, secure, MTG-themed platform serving three user types: shop owners, collectors, and market newcomers.

**Key Deliverables:**
- 14-page architecture (5 new pages)
- "Ornate Saga" visual identity with custom icons
- Comprehensive security hardening
- Collection management features
- Price alerts and notification system
- Platform imports (Moxfield, Archidekt, Deckbox)
- TCGPlayer affiliate integration

---

## Target Users

### Shop Owners
- Bulk import/export (existing)
- Margin tracking (future enhancement)
- Price label printing (future)
- Account type: "Business"

### Collectors
- Set completion tracking
- Want list with price targets
- Collection milestones
- Visual binder view
- Account type: "Collector"

### Market Newcomers
- Educational content explaining "why" behind recommendations
- Risk warnings before purchases
- Simplified UI with guidance
- Optional onboarding wizard

---

## Page Architecture

### Public Pages (4)
| Page | Route | Purpose |
|------|-------|---------|
| Landing | `/` | Hero, value prop, CTAs, preview data |
| Login | `/login` | Email + Google OAuth |
| Register | `/register` | Email + Google OAuth |
| Market | `/market` | Global trends, top movers, tournament meta |
| Tournaments | `/tournaments` | TopDeck.gg data with required attribution |

### Protected Pages (9)
| Page | Route | Purpose |
|------|-------|---------|
| Dashboard | `/dashboard` | Personalized home (varies by account type) |
| Insights | `/insights` | Actionable alerts, opportunities, education |
| Cards | `/cards` | Search with filters, semantic autocomplete |
| Card Detail | `/cards/[id]` | Stats, charts, similar cards, market context |
| Inventory | `/inventory` | Your cards list, quick actions |
| Collection | `/collection` | Set progress, binder view, stats |
| Want List | `/want-list` | Price targets, priorities, TCGPlayer links |
| Recommendations | `/recommendations` | Enhanced Buy/Sell/Hold with explanations |
| Settings | `/settings` | Account, notifications, security, theme |

### Navigation Structure

**Logged In:**
```
Dashboard | Market | Cards | Inventory | Collection | Want List | Recommendations | Insights | [Avatar Menu]
```

**Logged Out:**
```
Market | Cards | Tournaments | Login | Get Started
```

---

## Visual Identity: "Ornate Saga" Style

### Logo
- File: `Gemini_Generated_Image_2kb1r62kb1r62kb1.png`
- Two robed wizards performing ritual
- Purple and green magical energy
- Runic circle with "M" symbol
- Tagline: "FINANCE & CARD COLLECTING"

### Color System

**Base (Dark Theme):**
```css
--background: #0C0C10;
--surface: #14141A;
--elevated: #1C1C24;
--border: #2A2A35;
```

**Magical Accents (from logo):**
```css
--magic-purple: #8B5CF6;
--magic-green: #22C55E;
--magic-gold: #D4AF37;
```

**Mana Themes (user-selectable, accent-only):**
- White: #F8F6D8 (cream)
- Blue: #0E68AB (ocean)
- Black: #8B5CF6 (violet)
- Red: #DC2626 (crimson)
- Green: #16A34A (emerald)

### Typography

**Headlines:** Cinzel or Playfair Display (elegant serif)
**Body:** Inter (clean sans-serif, already in use)
**Accent:** Cinzel Decorative for special headers

### Decorative Elements

**Borders & Frames:**
- Gold/bronze inner borders on cards
- Ornate corner flourishes (SVG)
- Thin separator lines with gradient
- Rune patterns in subtle backgrounds

**Textures:**
- Subtle parchment texture on card backgrounds
- Stone/marble effects on page backgrounds
- Noise/grain for aged feel
- Vignette around edges

**Animations:**
- Gentle shimmer on important elements
- Page transitions as "chapter turns"
- Magical energy pulse on data updates
- Respect `prefers-reduced-motion`

### Custom Icon Set

Source from game-icons.net, Iconify, or custom SVGs:

| Purpose | Icon Concept |
|---------|-------------|
| Home/Dashboard | Planeswalker spark |
| Search | Scrying orb with eye |
| Inventory | Ornate treasure chest |
| Collection | Stacked tomes with gem clasp |
| Want List | Glowing star/wishbone |
| Settings | Arcane gear with runes |
| Alerts | Cracked crystal bell |
| Buy | Hand receiving card |
| Sell | Hand offering card |
| Hold | Shield with hourglass |
| Price Up | Flame arrow ascending |
| Price Down | Ice arrow descending |
| Import | Portal swirl inward |
| Export | Portal swirl outward |
| Filter | Alchemist's sieve |
| Refresh | Cyclical runes |

---

## Page Designs

### Landing Page (`/`)

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Logo]                              [Market] [Cards] [Login] [CTA] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│            Make Smarter MTG Market Decisions                         │
│                                                                      │
│     Accurate pricing data. Real-time alerts.                         │
│     Know exactly when to buy, sell, or hold.                         │
│                                                                      │
│     [Search any card...                              ] [Search]      │
│                                                                      │
│     90,000+ cards tracked  |  Live prices  |  Tournament meta        │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                        WHO IT'S FOR                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  Collectors  │  │ Shop Owners  │  │   Everyone   │               │
│  │  Set tracking │  │ Margin track │  │ Price alerts │               │
│  │  Want lists   │  │ Bulk ops     │  │ AI insights  │               │
│  │  Milestones   │  │ Price labels │  │ Market data  │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
├─────────────────────────────────────────────────────────────────────┤
│                      LIVE MARKET DATA                                │
│  ┌─────────────────────────┐  ┌─────────────────────────┐           │
│  │  Top Gainers Today      │  │  Market Index Chart     │           │
│  │  [Card] +45%            │  │  [Chart showing trend]  │           │
│  │  [Card] +32%            │  │                         │           │
│  │  [Card] +28%            │  │                         │           │
│  └─────────────────────────┘  └─────────────────────────┘           │
├─────────────────────────────────────────────────────────────────────┤
│                      [Get Started Free - No Credit Card]             │
└─────────────────────────────────────────────────────────────────────┘
```

### Market Page (`/market`) - NEW

Global market intelligence (public):
- Market index chart (all cards)
- Top gainers/losers (24h, 7d, 30d)
- Format health indicators (Modern, Pioneer, Standard, etc.)
- Tournament meta snapshot (recent winning archetypes)
- Hot cards section (trending across platform)

### Insights Page (`/insights`) - NEW

Personalized actionable intelligence:

**Portfolio Alerts:**
- "Sell Lightning Bolt - up 40% in 7 days"
- "Price dropping fast: Ragavan, Nimble Pilferer"
- "Card you own in winning deck: Consider selling into hype"

**Market Opportunities:**
- "Underpriced: [Card] at $X vs market average $Y"
- "Reserved List deals under $50"
- "Cards likely to spike (tournament this weekend)"

**Educational:**
- "Why your Sheoldred spiked: Won Pioneer GP"
- "Meta shift: Boros Energy rising, prepare for [cards]"
- "This week in MTG: New bans, spoiler impact"

### Collection Page (`/collection`) - NEW

Three views (tabs):

**Set Progress View:**
- List of all sets with % completion
- Expand to see missing cards
- Filter: Owned / Missing / All
- Sort: Newest / Oldest / Completion %

**Binder View:**
- Visual grid organized like physical binder
- Show card images in set order
- Empty slots for missing cards
- Click to add missing to want list

**Stats Dashboard:**
- Total collection value
- Rarest cards owned (by price, rarity)
- Cards by color/type breakdown
- Historical value growth chart
- Collection milestones achieved

### Want List Page (`/want-list`) - NEW

**Card List:**
- Card name, set, condition, target price
- Current market price vs target
- Priority tag (Need Now / Nice to Have)
- "Buy on TCGPlayer" affiliate link

**Features:**
- Price alerts when card drops below target
- Sort by: Priority, Price Gap, Recently Added
- Group by: Set, Format, Color
- One-click "Add to Inventory" when purchased

**TCGPlayer Integration:**
- Affiliate links to TCGPlayer product pages
- Price comparison across marketplaces

### Card Detail Enhancements (`/cards/[id]`)

Add to existing page:

**Similar Cards Section:**
- Cards with similar mechanics
- Budget alternatives
- Cards that combo well

**Price Context:**
- "This price is HIGH/FAIR/LOW vs 30-day average"
- Comparison across conditions
- Best marketplace to buy from

**Market News (if available):**
- "This card spiked because: [reason]"
- Link to tournament results if applicable
- Recent price movements explained

### Recommendations Page Enhancements

**Better Explanations:**
```
Instead of: BUY - 75% confidence

Show:
BUY Signal (75% confidence)
"Ragavan has dropped 30% from its peak and tournament play
is increasing. Historical patterns suggest a rebound within
2 weeks. Consider buying if you need it for Modern."
```

**Visual Confidence:**
- Confidence meter (bar or gauge)
- Risk indicator (Low/Medium/High volatility)
- Supporting data points shown

**Actionable Buttons:**
- "Add to Want List"
- "Mark as Acted On"
- "Dismiss" (with optional reason)

### Settings Page Rebuild

**Sections:**

1. **Account**
   - Profile info (name, email, avatar)
   - Account type (Collector / Shop Owner)
   - Change password
   - Delete account
   - Data export (GDPR)

2. **Appearance**
   - Mana theme picker (5 orbs)
   - (Future: Light/Dark mode toggle)

3. **Notifications** (NEW)
   - Email notifications on/off
   - Push notifications on/off
   - Alert types: Price targets, recommendations, portfolio alerts

4. **Trading Preferences**
   - ROI threshold
   - Confidence threshold
   - Recommendation horizon
   - Price history days

5. **Marketplaces**
   - Enable/disable data sources
   - API status indicators

6. **Security** (NEW)
   - Connected accounts (Google)
   - Active sessions (logout all devices)
   - Activity log (recent logins)

7. **Help**
   - Restart onboarding tour
   - Contact support
   - Keyboard shortcuts

---

## Security Enhancements

### Authentication

**Google OAuth:**
- Primary recommended login method
- Handles 2FA via Google
- Reduce password management burden

**Password Security:**
- Minimum 12 characters
- Require complexity (upper, lower, number)
- Check against breached password databases
- Rate limit login attempts (5 per minute)

**Sessions:**
- JWT with short expiry (1 hour)
- Refresh tokens (7 days)
- Session management page
- "Logout all devices" option

### Input Validation

- Sanitize all user inputs server-side
- XSS prevention on rendered content
- CSRF tokens on all forms
- Validate file uploads (imports)
- Rate limit API endpoints

### Data Protection

- Encrypt sensitive fields (API keys if any)
- Audit all API endpoints for authorization
- Ensure inventory data is user-scoped
- Secure password reset flow

---

## New Features

### Price Alerts System

**Backend:**
- `PriceAlert` model: user_id, card_id, target_price, direction (below/above), active
- Task to check alerts on price updates
- Notification dispatch (email, push)

**Frontend:**
- "Set Price Alert" button on card detail
- Alerts list in Settings > Notifications
- Want list auto-creates alerts for target prices

### Platform Imports

**Supported Platforms:**
- Moxfield (CSV export)
- Archidekt (CSV export)
- Deckbox (CSV export)
- TCGPlayer collection (CSV)

**Import Flow:**
1. Select platform
2. Upload file
3. Preview matched cards (show unmatched for manual fix)
4. Confirm import
5. Toast: "Imported X cards, Y unmatched"

### Mobile Card Scanning (Future Phase)

- Use phone camera to scan card
- Send image to Scryfall image recognition API
- Return matched card
- One-tap add to inventory

### Portfolio History

**Track:**
- All inventory additions with date and acquisition price
- All removals/sales with date and sale price
- Realized gains/losses

**Display:**
- Timeline of transactions
- Total realized P&L
- Filter by date range
- Export for tax reporting

### Saved Searches

- Save filter combinations with a name
- Quick access from search dropdown
- Examples: "Standard staples under $5", "Reserved List missing"

### Notification System

**Channels:**
- Email (via SendGrid or similar)
- Browser push notifications
- In-app notification center

**Event Types:**
- Price alert triggered
- Recommendation generated
- Collection milestone reached
- Import completed

---

## Backend Alignment

This design aligns with `docs/plans/2025-12-27-inventory-pricing-search-design.md`:

| Backend Feature | Frontend Usage |
|-----------------|----------------|
| Scryfall bulk pricing | Market index, card prices |
| TCGPlayer condition pricing | Card detail condition prices |
| TopDeck.gg tournaments | Tournaments page, meta insights |
| Semantic search | Card search autocomplete |
| Fixed top gainers/losers | Market page, dashboard |
| Fixed value index | Portfolio chart uses acquisition cost base |

**New API Endpoints Needed:**

```
# Alerts
POST   /api/v1/alerts              # Create price alert
GET    /api/v1/alerts              # List user alerts
DELETE /api/v1/alerts/{id}         # Delete alert

# Want List
GET    /api/v1/want-list           # Get user want list
POST   /api/v1/want-list           # Add card to want list
PUT    /api/v1/want-list/{id}      # Update (target price, priority)
DELETE /api/v1/want-list/{id}      # Remove from want list

# Collection
GET    /api/v1/collection/sets     # Set completion data
GET    /api/v1/collection/stats    # Collection statistics
GET    /api/v1/collection/missing/{set_code}  # Missing cards in set

# Portfolio History
GET    /api/v1/portfolio/history   # Transaction log
GET    /api/v1/portfolio/summary   # Realized P&L summary

# Imports
POST   /api/v1/imports/preview     # Parse file, return preview
POST   /api/v1/imports/confirm     # Confirm and execute import

# Saved Searches
GET    /api/v1/saved-searches
POST   /api/v1/saved-searches
DELETE /api/v1/saved-searches/{id}

# Notifications
GET    /api/v1/notifications       # Notification center
PUT    /api/v1/notifications/{id}/read
PUT    /api/v1/settings/notifications  # Notification preferences
```

---

## Implementation Phases

### Phase 1: Foundation (Security + Auth)
**Priority:** Critical
**Effort:** Medium

- [ ] Google OAuth integration (backend + frontend)
- [ ] Password strength requirements
- [ ] Rate limiting on login/API
- [ ] Session management page in settings
- [ ] Input sanitization audit
- [ ] CSRF token implementation

### Phase 2: Visual Overhaul
**Priority:** High
**Effort:** Large

- [ ] Integrate logo into header/favicon
- [ ] Implement Cinzel typography
- [ ] Create ornate CSS system (borders, backgrounds, textures)
- [ ] Source/create custom icon set
- [ ] Update all components to new style
- [ ] Add decorative flourishes
- [ ] Animation system with reduced-motion support

### Phase 3: Landing + Market
**Priority:** High
**Effort:** Medium

- [ ] Complete landing page redesign
- [ ] Create Market page
- [ ] Public data preview (no login required)
- [ ] SEO optimization for landing

### Phase 4: Collection Features
**Priority:** High
**Effort:** Large

- [ ] Collection page (3 views)
- [ ] Want List page
- [ ] Price alerts system (backend + frontend)
- [ ] Set completion tracking API
- [ ] TCGPlayer affiliate link integration

### Phase 5: Enhanced Pages
**Priority:** Medium
**Effort:** Large

- [ ] Insights page
- [ ] Recommendations page overhaul
- [ ] Card detail enhancements (similar, context, news)
- [ ] Settings page rebuild
- [ ] Notification system (backend + frontend)

### Phase 6: Advanced Features
**Priority:** Lower
**Effort:** Large

- [ ] Platform imports (Moxfield, Archidekt, Deckbox)
- [ ] Portfolio history tracking
- [ ] Saved searches
- [ ] Mobile card scanning
- [ ] Trade finder (future)

---

## Files to Modify/Create

### Frontend - New Pages
```
frontend/src/app/
├── market/page.tsx           # NEW
├── insights/page.tsx         # NEW
├── collection/page.tsx       # NEW
├── want-list/page.tsx        # NEW
├── tournaments/page.tsx      # NEW
├── page.tsx                  # Redesign landing
├── settings/page.tsx         # Major rebuild
├── recommendations/page.tsx  # Enhance
└── cards/[id]/page.tsx       # Enhance
```

### Frontend - Components
```
frontend/src/components/
├── icons/                    # Custom icon set
├── ui/
│   ├── OrnateCard.tsx        # Decorative card wrapper
│   ├── PageHeader.tsx        # Ornate page headers
│   └── Flourish.tsx          # Decorative elements
├── landing/
│   ├── Hero.tsx
│   ├── Features.tsx
│   └── LiveData.tsx
├── collection/
│   ├── SetProgress.tsx
│   ├── BinderView.tsx
│   └── CollectionStats.tsx
└── want-list/
    ├── WantListItem.tsx
    └── PriceAlert.tsx
```

### Frontend - Styles
```
frontend/src/styles/
├── globals.css               # Update with ornate system
├── ornate.css                # Decorative CSS classes
└── fonts.css                 # Cinzel font imports
```

### Backend - New Models
```
backend/app/models/
├── price_alert.py            # NEW
├── want_list_item.py         # NEW
├── notification.py           # NEW
├── portfolio_transaction.py  # NEW
└── saved_search.py           # NEW
```

### Backend - New Routes
```
backend/app/api/routes/
├── alerts.py                 # NEW
├── want_list.py              # NEW
├── collection.py             # NEW
├── portfolio.py              # NEW
├── notifications.py          # NEW
├── saved_searches.py         # NEW
└── imports.py                # NEW
```

---

## Success Criteria

- [ ] Landing page clearly communicates value proposition
- [ ] New users understand what platform does within 10 seconds
- [ ] Visual style feels "premium" and "MTG-themed"
- [ ] Collectors can track set completion and want lists
- [ ] Price alerts notify users when targets are hit
- [ ] Recommendations explain "why" in plain English
- [ ] Google OAuth works for signup/login
- [ ] All forms are protected against XSS/CSRF
- [ ] Platform imports work for Moxfield, Archidekt, Deckbox
- [ ] TCGPlayer affiliate links generate revenue

---

## Open Questions

1. **Notifications delivery:** SendGrid for email? Which push service?
2. **Card scanning:** Which Scryfall API endpoint for image recognition?
3. **Trade finder:** Scope for future phase - full matching or simple sharing?
4. **Print labels:** What format? PDF? Thermal printer support?

---

## Related Documents

- `docs/plans/2025-12-25-frontend-redesign-design.md` - Previous frontend work (mana themes)
- `docs/plans/2025-12-27-inventory-pricing-search-design.md` - Backend pricing/search refactor
- `docs/plans/2025-12-24-charting-architecture-overhaul-design.md` - TimescaleDB migration
