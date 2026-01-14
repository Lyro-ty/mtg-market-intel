# Revised Platform Vision: Intelligence-First Approach

**Date:** 2025-12-30
**Status:** Approved revision of unified platform spec
**Core Principle:** We are Bloomberg Terminal + LinkedIn for MTG, NOT a marketplace

---

## Vision Statement

**Dualcaster Deals** is the premier MTG market intelligence platform that:
1. **Tracks** prices across all major marketplaces
2. **Analyzes** market trends, meta shifts, and opportunities
3. **Connects** buyers, sellers, and LGS for discovery (not transactions)

We facilitate the **introduction**, not the **transaction**.

---

## What We Removed (Marketplace Complexity)

| Removed Feature | Reason |
|-----------------|--------|
| Stripe/Escrow | Regulatory liability, not our core value |
| have_list_items table | Use `available_for_trade` flag on inventory |
| asking_price field | Makes us a marketplace |
| trade_proposals workflow | Can't verify trades we don't process |
| trade_proposal_items | Unnecessary complexity |
| Trade-based reputation | Unverifiable without handling transactions |
| LGS as sellers | Competes with TCGPlayer |

---

## Intelligence Gap Analysis

### Current Data Assets

| Data | Status | Quality |
|------|--------|---------|
| Card catalog | 98,579 cards | Excellent |
| Price snapshots | 4 marketplaces | Good |
| Signals | 898,287 | Good |
| Recommendations | 2,329 | Good |
| Tournaments | 0 rows | **EMPTY** |
| News articles | 0 rows | **EMPTY** |

### Critical Intelligence Gaps

#### 1. Tournament/Meta Data (HIGH PRIORITY)
**Current state:** Tables exist, zero data
**Why it matters:** Meta defines demand. Winning decks = price spikes.

**What we need:**
- Tournament results by format (Modern, Pioneer, Standard, Legacy, Commander)
- Deck archetypes and card usage frequency
- Meta share percentages
- New deck emergence signals

**Data sources:**
- TopDeck.gg API (client exists, not collecting)
- MTGGoldfish (scraping)
- EDHREC API (Commander popularity)
- MTGTop8 (legacy data)

**Implementation:** Add Celery task `collect_tournament_data` running every 4 hours

#### 2. Buylist Prices (HIGH PRIORITY)
**Current state:** Not tracked at all
**Why it matters:** Buylist = floor price, spread = opportunity

**What we need:**
- Card Kingdom buylist prices
- TCGPlayer buylist (if available)
- ChannelFireball buylist
- Buylist-to-retail spread analysis

**Implementation:**
- Add `buylist_price` field to price_snapshots OR separate `buylist_snapshots` table
- Add Card Kingdom adapter

#### 3. Supply/Inventory Signals (PARTIALLY IMPLEMENTED)
**Current state:** Schema has `num_listings`, `total_quantity` but unclear if populated
**Why it matters:** Low supply + stable price = imminent spike

**What we need:**
- Seller count per card on TCGPlayer
- Total available quantity
- Velocity (how fast are copies selling?)
- "Drying up" alerts when supply drops 50%+

**Implementation:** Ensure adapters populate supply fields, add supply-based signals

#### 4. Reprint Risk Analysis (NOT IMPLEMENTED)
**Current state:** No tracking
**Why it matters:** Non-reserved cards have reprint risk affecting long-term value

**What we need:**
- Last reprint date per card
- Reprint frequency history
- Reprint risk score (0-100)
- Reserved List flag (already have!)

**Data source:** Scryfall has reprint data
**Implementation:** Add fields to cards table, calculate risk score in analytics

#### 5. Format Legality History (NOT IMPLEMENTED)
**Current state:** Current legality only, no history
**Why it matters:** Bans/unbans cause 50%+ price swings

**What we need:**
- Legality change history
- "Ban watch" signals (cards being discussed)
- Unban speculation tracking

**Implementation:** Store legality snapshots, track changes over time

#### 6. Cross-Market Arbitrage (DATA EXISTS, NO ANALYSIS)
**Current state:** We have prices from 4 marketplaces
**Why it matters:** Price differences = profit opportunity

**What we need:**
- Real-time spread between marketplaces
- After-fees arbitrage calculation
- Arbitrage window alerts

**Implementation:** New signal type in analytics task

#### 7. Content Creator Signals (NOT IMPLEMENTED)
**Current state:** No tracking
**Why it matters:** YouTuber features card = price spike within hours

**What we need:**
- MTG YouTube channel monitoring
- Reddit r/mtgfinance mentions
- Twitter/X MTG influencer tracking

**Implementation:** Lower priority, but high alpha potential

---

## Revised Phase Plans

### Phase 0: Foundation + Intelligence Infrastructure (12 tasks)

**Goal:** Establish public identity, notifications, and fix empty data tables

#### Database Changes
```sql
-- Add to users table
ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500);
ALTER TABLE users ADD COLUMN bio TEXT;
ALTER TABLE users ADD COLUMN location VARCHAR(100);
ALTER TABLE users ADD COLUMN discord_id VARCHAR(20);
ALTER TABLE users ADD COLUMN last_active_at TIMESTAMPTZ;

-- Add to inventory_items (replaces separate have_list)
ALTER TABLE inventory_items ADD COLUMN available_for_trade BOOLEAN DEFAULT FALSE;

-- Notification preferences (simpler than separate table)
-- Already have: email_alerts, price_drop_threshold, digest_frequency on users
```

#### Tasks

**Task 0.1: Hashids Setup**
- Install hashids library
- Create `app/core/hashids.py` with encode/decode functions
- Salt with SECRET_KEY

**Task 0.2: Public Card Endpoints**
- `GET /cards/:hashid` - Public card page (no auth)
- `GET /cards/:hashid/prices` - Price history (no auth)
- Update frontend card pages to use hashids

**Task 0.3: User Profile Fields Migration**
- Add avatar_url, bio, location, discord_id, last_active_at to users
- Create API endpoints for profile updates
- Frontend settings page

**Task 0.4: Available-for-Trade Flag**
- Add `available_for_trade` boolean to inventory_items
- Add filter to inventory API: `?available_for_trade=true`
- Frontend toggle on inventory items

**Task 0.5: Notification System Activation**
- Notifications table exists, needs triggers
- Create NotificationService with send methods
- Hook into price alerts, want list matches
- Frontend notification dropdown

**Task 0.6: Discord OAuth**
- Implement Discord OAuth flow
- Store discord_id on user profile
- Link/unlink Discord account

**Task 0.7: Tournament Data Collection (FIX EMPTY TABLE)**
- TopDeck.gg client exists, wire it to Celery
- Add `collect_tournament_data` task (every 4 hours)
- Populate tournaments and tournament_standings tables
- Parse deck lists into card usage stats

**Task 0.8: Meta Analysis Signals**
- New signal types: META_SPIKE, META_DROP, NEW_ARCHETYPE
- Calculate meta share per card by format
- "Card X is in 15% of Modern decks" insights

**Task 0.9: News Collection (FIX EMPTY TABLE)**
- Implement RSS/scraper for MTG news sources
- MTGGoldfish articles
- WotC announcements
- r/mtgfinance hot posts

**Task 0.10: Reprint Risk Fields**
- Add to cards: first_printed_at, reprint_count, last_reprinted_at
- Calculate reprint_risk_score (0-100)
- Signal for high-value cards with high reprint risk

**Task 0.11: Supply Signal Enhancement**
- Verify num_listings and total_quantity are being populated
- Add SUPPLY_LOW signal type (< 20 listings on TCGPlayer)
- Add SUPPLY_VELOCITY signal (selling faster than restocking)

**Task 0.12: Cross-Market Arbitrage Signals**
- Compare prices across marketplaces
- Calculate after-fees spread
- New signal type: ARBITRAGE_OPPORTUNITY
- "Buy on CardMarket at $X, sell on TCGPlayer at $Y, profit $Z"

---

### Phase 1: Enhanced Intelligence + Discovery (14 tasks)

**Goal:** Best-in-class market intelligence, basic user discovery

#### Tasks

**Task 1.1: Buylist Price Tracking**
- New adapter: CardKingdomBuylistAdapter
- Either add buylist fields to price_snapshots OR new table
- Track buylist-to-retail spread

**Task 1.2: Spread Analysis Dashboard**
- Frontend page showing buylist vs retail spreads
- "Best cards to sell to buylists right now"
- "Highest spread cards" (buylist opportunity)

**Task 1.3: Format Legality History**
- New table: legality_changes (card_id, format, old_status, new_status, changed_at)
- Track bans/unbans historically
- Signal: LEGALITY_CHANGE

**Task 1.4: Price Alert Enhancements**
- "Alert when price drops X% in Y hours"
- "Alert when card enters top 10 gainers"
- "Alert when supply drops below Z"

**Task 1.5: Want List Intelligence Integration**
- Show market intelligence on want list items
- "This card is spiking, buy now?"
- "This card is in 20% of Modern decks"
- "Reprint risk: HIGH"

**Task 1.6: Discovery - Users Who Have What I Want**
- Query: Find users with `available_for_trade=true` items matching my want list
- Consider location (same city = local trade)
- Basic matching score

**Task 1.7: Discovery - Users Who Want What I Have**
- Inverse of above
- "3 users near you want your Ragavan"

**Task 1.8: Public User Profiles**
- `GET /u/:hashid` - Public profile page
- Show: display_name, location (city only), bio
- Show: "X cards available for trade"
- Show: Want list (if public)

**Task 1.9: Discord Bot - Price Lookups**
- Separate Python service: discord-bot/
- Command: `!price <card name>`
- Returns: Current price, 7d change, meta info

**Task 1.10: Discord Bot - Want List Management**
- Command: `!want add <card>`
- Command: `!want list`
- Command: `!want remove <card>`

**Task 1.11: Discord Bot - Alert Notifications**
- DM users when price alerts trigger
- "Lightning Bolt dropped 15%!"

**Task 1.12: EDHREC Integration**
- Fetch EDHREC rank and popularity data
- "Most popular commanders this week"
- "Staples for X commander"

**Task 1.13: Price Prediction Signals**
- ML-lite: "Based on meta share increase, expect price rise"
- Historical pattern matching
- Confidence scores on predictions

**Task 1.14: Portfolio Intelligence Dashboard**
- "Your portfolio value: $X (+Y% this week)"
- "Top gainers in your collection"
- "Cards at risk (high reprint risk, falling meta share)"
- "Recommended sells from your inventory"

---

### Phase 2: Connections (10 tasks)

**Goal:** Enable users to connect and communicate, without being a marketplace

#### Database Changes
```sql
-- Simple connection/messaging
CREATE TABLE connection_requests (
    id SERIAL PRIMARY KEY,
    requester_id INTEGER REFERENCES users(id),
    recipient_id INTEGER REFERENCES users(id),
    card_ids INTEGER[],  -- Cards they might discuss
    message TEXT,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, accepted, declined
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER REFERENCES users(id),
    recipient_id INTEGER REFERENCES users(id),
    content TEXT,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Community endorsements (not trade-based)
CREATE TABLE user_endorsements (
    id SERIAL PRIMARY KEY,
    endorser_id INTEGER REFERENCES users(id),
    endorsed_id INTEGER REFERENCES users(id),
    endorsement_type VARCHAR(20),  -- 'trustworthy', 'knowledgeable', 'responsive'
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(endorser_id, endorsed_id)
);
```

#### Tasks

**Task 2.1: Connection Request Flow**
- "I'd like to connect about these cards"
- Simple accept/decline
- No negotiation, just introduction

**Task 2.2: Basic Messaging**
- Simple DM system after connection accepted
- No real-time needed initially (polling OK)
- Mark as read functionality

**Task 2.3: Messaging UI**
- Inbox with conversation threads
- Unread count badge
- Basic message composition

**Task 2.4: User Endorsements**
- "Endorse this user as trustworthy"
- Public endorsement count on profiles
- No numeric scores, just counts

**Task 2.5: Block/Report Users**
- Block users from messaging you
- Report inappropriate behavior
- Admin moderation queue

**Task 2.6: Location-Based Discovery**
- "Users near me" with trade-available cards
- City/region based, not exact location
- Privacy: users opt-in to show location

**Task 2.7: Notification Integration**
- Notify on new connection requests
- Notify on new messages
- Email digest option

**Task 2.8: Discord Integration for Connections**
- "You have a new connection request" DM
- Link to web to respond

**Task 2.9: Public Want Lists**
- Option to make want list public
- Shows on public profile
- Helps with discovery

**Task 2.10: Connection Suggestions**
- "Based on your want list, connect with these users"
- Weekly email: "5 users have cards you want"

---

### Phase 3: LGS Intelligence + Premium (10 tasks)

**Goal:** Provide value to LGS as intelligence consumers, monetize platform

#### Database Changes
```sql
CREATE TABLE lgs_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) UNIQUE,
    store_name VARCHAR(200) NOT NULL,
    address TEXT,
    website VARCHAR(500),
    phone VARCHAR(20),
    hours JSONB,  -- {"monday": "10-8", ...}
    services TEXT[],  -- ['singles', 'tournaments', 'buylist']
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Premium subscriptions
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    tier VARCHAR(20),  -- 'free', 'premium', 'lgs'
    stripe_subscription_id VARCHAR(100),
    started_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Note: Stripe is now ONLY for subscriptions, not escrow/transactions.

#### Tasks

**Task 3.1: LGS Registration Flow**
- Store name, address, website
- Manual verification (admin approves)
- LGS badge on profile

**Task 3.2: LGS Demand Dashboard**
- "Most wanted cards in your area"
- Aggregate want list data by location
- "10 users near you want Ragavan"

**Task 3.3: LGS Buylist Intelligence**
- "Optimal buylist prices based on demand"
- "Cards users are selling (available_for_trade)"
- Market price context for buylist setting

**Task 3.4: LGS Event Promotion**
- Create/promote events
- Show on user dashboards if nearby
- "Upcoming events at LGS near you"

**Task 3.5: Premium Tier - More Alerts**
- Free: 5 price alerts
- Premium: Unlimited alerts
- Premium: SMS alerts option

**Task 3.6: Premium Tier - Advanced Analytics**
- Historical data beyond 30 days
- Export to CSV/Excel
- API access for power users

**Task 3.7: Premium Tier - Portfolio Reports**
- Weekly email: portfolio summary
- Monthly: detailed analytics PDF
- Tax helper: acquisition cost tracking

**Task 3.8: Affiliate Link Integration**
- When showing prices, link to TCGPlayer with affiliate tag
- Track clicks and conversions
- Revenue without being a marketplace

**Task 3.9: LGS Subscription Tier**
- Monthly fee for LGS features
- Stripe subscription (not escrow!)
- Demand data, event promotion, verified badge

**Task 3.10: API for Partners**
- Rate-limited public API
- Premium tier: higher limits
- Documentation and developer portal

---

## Implementation Priority

### Immediate (Week 1-2)
1. **Task 0.7: Tournament Data Collection** - Fix the empty table!
2. **Task 0.1-0.2: Hashids + Public Cards** - Enable sharing
3. **Task 0.5: Notifications** - Table exists, just needs triggers

### Short-term (Week 3-4)
4. **Task 0.8-0.9: Meta Analysis + News** - Fill intelligence gaps
5. **Task 0.3-0.4: Profiles + Trade Flag** - User identity
6. **Task 0.11-0.12: Supply + Arbitrage Signals** - More alpha

### Medium-term (Week 5-8)
7. **Phase 1 Intelligence Tasks** - Buylist, legality, predictions
8. **Phase 1 Discovery Tasks** - User matching
9. **Phase 1 Discord Bot** - Distribution channel

### Long-term (Week 9-12)
10. **Phase 2 Connections** - Messaging, endorsements
11. **Phase 3 LGS + Premium** - Monetization

---

## Revenue Model (Non-Marketplace)

| Stream | Description | Phase |
|--------|-------------|-------|
| Affiliate Links | TCGPlayer/CardMarket links with tracking | 3 |
| Premium Subscription | $5/mo: more alerts, advanced analytics | 3 |
| LGS Subscription | $20/mo: demand data, event promotion | 3 |
| API Access | Usage-based for developers | 3 |

**Key principle:** We make money when users buy **elsewhere**, not from us.

---

## Success Metrics

| Metric | Target | How |
|--------|--------|-----|
| Tournament data | 1000+ events | Fix Task 0.7 |
| News articles | 100+ per month | Fix Task 0.9 |
| Active signals | 1M+ | Already close |
| Users discovering each other | 100+ connections/month | Phase 2 |
| LGS signups | 50+ stores | Phase 3 |
| Premium conversions | 5% of active users | Phase 3 |

---

## Summary

**Before:** 98 tasks across 4 phases with marketplace complexity
**After:** 46 tasks across 4 phases focused on intelligence + connections

| Phase | Tasks | Focus |
|-------|-------|-------|
| 0 | 12 | Foundation + Fix Empty Intelligence Tables |
| 1 | 14 | Enhanced Intelligence + Basic Discovery |
| 2 | 10 | Connections + Messaging |
| 3 | 10 | LGS Intelligence + Premium |

The platform is now clearly positioned as **intelligence-first** with **connection facilitation** rather than transaction processing.
