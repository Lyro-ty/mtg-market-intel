# Hero Messaging Redesign

**Date:** 2025-12-31
**Status:** Approved
**Author:** Claude + User

## Overview

Reposition Dualcaster Deals from a pure price-tracking tool to "Bloomberg Terminal + LinkedIn for MTG" — a market intelligence platform that connects players, collectors, and local game stores without becoming a marketplace.

### Core Positioning

| Concept | Description |
|---------|-------------|
| Bloomberg Terminal | Real-time market intelligence, price tracking, analytics |
| LinkedIn | Network of collectors and shops, trust/reputation, connections |
| Not a Marketplace | Facilitate discovery and connections, never handle transactions |

### Target Audiences

1. **Players/Collectors** — Find deals, track collections, connect with others
2. **Local Game Stores (LGS)** — Get visibility, find inventory, connect with customers
3. **Player-to-Player** — Peer trading and selling between collectors

### Business Model

- **Free for players** — Attracts the network
- **Premium for LGS** — Monetizes via visibility, leads, and tools
- **Zero transaction liability** — Connections only, deals happen off-platform

### Core Values

- **Transparency & Honesty** — Real numbers, no inflated metrics
- **Equalizing the playing field** — Give everyone access to pro-level market intelligence
- **Community-first** — Building connections, not just providing tools

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Headline approach | "Your Edge in the Market" | Empowerment angle, appeals to casual and serious traders |
| Subhead approach | Community + intelligence blend | Balances Bloomberg (data) with LinkedIn (network) |
| Fantasy flavor | Full flavor on landing page | Resonates with MTG players, differentiates from generic fintech |
| Fantasy flavor in-app | None — use clear terminology | Usability over theme inside the product |
| Trust indicators | Live real counts | Transparency builds trust, even with small numbers |
| Trademark safety | Avoid "Planeswalker" | WotC trademark — use "Seekers" instead |

---

## Hero Content Specification

### Badge
```
⚔️ Real-Time Market Intelligence
```

### Headline
```
Your Edge in the Market
Scry Further. Connect Deeper. Deal Smarter.
```

### Subhead
```
Market intelligence meets community. Find collectors and trading posts
who have what you seek — and seek what you hold.
```

### Feature Pills
| Pill | Icon | Description |
|------|------|-------------|
| Market Scrying | TrendingUp (green) | Real-time price intelligence |
| Trade Conjuring | Sparkles (gold) | Automatic trade matching |
| Trading Posts | MapPin (accent) | Local shop discovery |
| Trusted Network | Shield (accent) | Reputation and trust system |

### Call-to-Action Buttons

| Button | Style | Link |
|--------|-------|------|
| Enter the Bazaar | Primary (gradient) | /register |
| Begin Your Quest | Secondary (outline) | /cards or /market |

### Trust Indicators (Live Counts)

Display real, dynamically-updated counts:

| Metric | Label | Source |
|--------|-------|--------|
| User count | `{n} Seekers` | `SELECT COUNT(*) FROM users` |
| LGS count | `{n} Trading Posts` | `SELECT COUNT(*) FROM users WHERE is_shop = true` (or similar) |
| Card count | `90K+ Cards in the Vault` | Static or from cards table |
| Price | `Free to Join` | Static |

**Important:** Show real numbers even if small. Authenticity > impressive-looking fake stats.

---

## Terminology Guide

### Landing Page (Fantasy Flavor)

| Concept | Fantasy Term |
|---------|--------------|
| Users/Collectors | Seekers |
| LGS/Shops | Trading Posts |
| Card Database | The Vault |
| Browsing/Searching | Scrying |
| Finding matches | Conjuring |
| Main marketplace view | The Bazaar |
| Getting started | Begin Your Quest |

### In-App (Clear Terminology)

| Concept | In-App Term |
|---------|-------------|
| Users/Collectors | Collectors (or just Users) |
| LGS/Shops | Shops |
| Card Database | Cards |
| Collection | Collection / Portfolio |
| Want List | Want List |
| Price Alerts | Price Alerts |

---

## Trademark Considerations

**Avoid using these WotC trademarks:**
- Planeswalker
- Mana symbols (visual)
- Magic: The Gathering (except in factual references)

**Safe fantasy terms:**
- Seekers, Wanderers, Mages, Traders
- Scry, Conjure, Summon (generic fantasy verbs)
- Vault, Bazaar, Trading Post (generic nouns)

Source: [Wizards of the Coast Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy)

---

## Implementation Tasks

1. Update `HeroContent.tsx` with new headline, subhead, and CTAs
2. Update feature pills with new labels and appropriate icons
3. Create API endpoint for live user/shop counts
4. Update trust indicators to fetch and display live counts
5. Update badge text
6. Test responsive behavior on mobile

---

## Future Considerations

- A/B test headline variations once traffic allows
- Consider animated "scrying" effect on search bar
- LGS onboarding flow with "Claim Your Trading Post" messaging
- Referral program: "Summon a Seeker"
