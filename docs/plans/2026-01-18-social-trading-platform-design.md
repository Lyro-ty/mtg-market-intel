# Social Trading Platform Design

**Date:** 2026-01-18
**Status:** Draft
**Author:** Claude + User

## Overview

A profile-centric social trading platform that transforms user identity into trading card-inspired profiles. The system gamifies engagement through achievements that unlock cosmetic rewards and improve discovery visibility, while providing robust tools for trading, messaging, user discovery, and community moderation.

### Design Principles

1. **Profile card is the anchor** - Appears everywhere, creates visual consistency
2. **Gamification drives quality** - Better traders surface higher in discovery
3. **Privacy by default** - Users control visibility, can opt out of directory
4. **Trust through transparency** - Reputation, reviews, verification badges visible
5. **Moderation scales** - Self-service handles most issues, admin focuses on serious cases
6. **No payment/shipping** - Platform facilitates connection, users handle logistics externally

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Profile visual style | MTG-inspired, not replica | Avoid trademark issues while maintaining theme |
| Achievement permanence | Permanent once earned | Encourages users without fear of losing progress |
| Frame tier basis | Current highest qualifier | Frames reflect active status, badges are permanent |
| Trade chat model | Hybrid (trade threads + DMs) | Organized negotiations + general social connection |
| Moderation approach | Tiered (self-service → community → automated → admin) | Scales efficiently, admin focuses on serious cases |
| Notifications | In-app only (v1) | Can add browser push/email later |
| Payment/shipping | External | Reduces liability, users handle logistics |

---

## Section 1: Trading Card Profile System

### Profile Card Anatomy

Every user has a "profile card" - a card-inspired visual component that appears throughout the platform. It draws from fantasy card game aesthetics (ornate borders, aged parchment textures, metallic accents, mystical flourishes) without replicating MTG exactly.

#### Front Side

| Element | Description |
|---------|-------------|
| **Header** | Display name, username, card type badge (Collector/Trader/Brewer/Investor) |
| **Portrait** | User avatar with signature card as subtle background watermark |
| **Tagline** | User's custom motto (max 50 chars) |
| **Stats row** | Trades completed, reputation (stars), success rate, response time |
| **Badge row** | Top 4-6 achievement icons + overflow indicator |
| **Frame** | Tier-based border (Bronze → Legendary) with tier-appropriate effects |
| **Quick actions** | Message, Trade, Endorse, Connect buttons |

#### Back Side (flip on click/tap)

| Element | Description |
|---------|-------------|
| **Extended stats** | Full trade history summary, portfolio value tier, member since |
| **Endorsements** | Counts for each type (trustworthy, fair trader, etc.) |
| **Recent activity** | Last 3 trades or reviews |
| **Mutual connections** | "You both know @username" |
| **Verification badges** | Discord, email, ID verified status |

### Frame Tiers

| Tier | Visual Effect | Unlock Criteria (any one) |
|------|---------------|---------------------------|
| **Bronze** | Clean matte border, no animation | Default for all users |
| **Silver** | Subtle metallic sheen on hover | 10+ trades OR Established reputation OR $1K portfolio |
| **Gold** | Warm glow effect, gentle parallax tilt | 50+ trades OR Trusted reputation OR $10K portfolio |
| **Platinum** | Animated gradient border, pronounced parallax | 100+ trades OR Elite reputation OR significant contribution |
| **Legendary** | Particle effects (floating motes), holographic shimmer | Special achievements or combination of high-tier accomplishments |

### Visual Effects

- **Hover/parallax** - Cards tilt slightly with parallax depth (like holographic cards catching light)
- **Foil/shimmer** - Platinum and Legendary frames have subtle animated gradients
- **Reduced motion** - Respect `prefers-reduced-motion` setting, disable animations

### Profile Card Variants

| Variant | Use Case |
|---------|----------|
| **Full** | Profile page, trade detail header |
| **Standard** | Directory grid, discovery matches |
| **Compact** | Lists, autocomplete, mentions, conversation headers |
| **Skeleton** | Loading state with shimmer placeholder |

### Personalization Features

| Feature | Details |
|---------|---------|
| **Tagline** | 50 chars max, profanity filtered, reportable |
| **Signature card** | User picks one MTG card as their identity (persists even if not in collection) |
| **Card type** | Self-selected: Collector, Trader, Brewer, Investor. Changeable once per 30 days |
| **Format specialties** | Multi-select: Commander, Modern, Legacy, Vintage, Pioneer, Standard, Pauper, cEDH, Limited |

### Shareability

- **Export as PNG** - Generate styled image of profile card for social media
- **Card URL** - `dualcaster.deals/card/{hashid}` - shareable public link
- **Export includes** - Small "Report abuse" watermark URL for safety

### Trust & Social Proof

| Element | Display |
|---------|---------|
| **Verification badges** | Email verified, Discord linked, ID verified (optional) |
| **Response time** | "Usually responds within 2 hours" |
| **Trade success rate** | "98% of trades completed successfully" |
| **Mutual connections** | "3 traders you know have traded with this user" |

### Edge Cases

| Scenario | Resolution |
|----------|------------|
| Banned user's profile card | Greyed out, "Account Suspended" overlay, no quick actions |
| Signature card no longer in collection | Still displays (sentimental, not inventory proof) |
| Offensive tagline | Auto-filter profanity + reportable, mods can force-clear |
| Card type changes | Users can change once per 30 days (prevent gaming) |
| New user with no data | "New Trader" default state, bronze frame, placeholder stats |

### Where Profile Cards Appear

- User directory and search results
- Trade proposals (see who you're trading with)
- Messages (conversation header)
- Discovery matches
- Leaderboards
- Reviews and endorsements

---

## Section 2: Achievement System

### Achievement Categories

Each category has its own progression track. Highest tier across all categories determines frame eligibility, but all achievements contribute to discovery priority.

#### 1. Trade Milestones

| Achievement | Requirement | Icon Concept | Discovery Points |
|-------------|-------------|--------------|------------------|
| First Deal | Complete 1 trade | Handshake | 5 |
| Regular Trader | 10 trades | Balanced scales | 15 |
| Seasoned Dealer | 50 trades | Merchant's pouch | 30 |
| Trade Master | 100 trades | Golden contract | 50 |
| Market Legend | 500 trades | Crown with coins | 100 |

#### 2. Reputation Tiers

| Achievement | Requirement | Icon Concept | Discovery Points |
|-------------|-------------|--------------|------------------|
| Newcomer | < 5 reviews | Seedling | 10 |
| Established | 5+ reviews, 4.0+ avg | Growing tree | 30 |
| Trusted | 20+ reviews, 4.5+ avg | Sturdy oak | 60 |
| Elite | 50+ reviews, 4.7+ avg | Ancient tree with runes | 100 |

#### 3. Portfolio Value

| Achievement | Requirement | Icon Concept | Discovery Points |
|-------------|-------------|--------------|------------------|
| Starter Collection | $100+ tracked | Single gem | 5 |
| Growing Hoard | $1,000+ | Small chest | 10 |
| Serious Collector | $10,000+ | Treasure pile | 20 |
| Dragon's Hoard | $50,000+ | Vault door | 35 |
| Legendary Vault | $100,000+ | Overflowing treasury | 50 |

#### 4. Community Contribution

| Achievement | Requirement | Icon Concept | Discovery Points |
|-------------|-------------|--------------|------------------|
| Friendly | 5 endorsements given | Open hand | 10 |
| Helpful | 20 reviews written | Quill pen | 20 |
| Community Pillar | 50+ endorsements given | Stone pillar | 40 |
| Veteran | 1 year member | Calendar with star | 25 |
| Founder | Early adopter (first 1000 users) | Special emblem | 50 |

#### 5. Special Achievements

| Achievement | Requirement | Icon Concept | Discovery Points |
|-------------|-------------|--------------|------------------|
| Negotiator | 10 counter-offers accepted | Chess piece | 25 |
| Set Completionist | Complete any full set | Completed book | 30 |
| Big Deal | Single trade over $500 value | Diamond | 20 |
| Whale Trade | Single trade over $2,000 value | Leviathan | 40 |
| Perfect Record | 50+ trades, 100% success rate | Pristine shield | 50 |
| Speed Dealer | 10 trades completed within 24h of proposal | Lightning bolt | 15 |
| Matchmaker | 5 mutual discovery matches converted to trades | Linked rings | 20 |

#### Hidden Achievements (Secret)

| Achievement | Requirement | Icon Concept |
|-------------|-------------|--------------|
| Night Owl | Complete a trade between 2-4 AM | Moon |
| Palindrome | Complete trade #1221, #1331, etc. | Mirror |
| Century | Be a member for 100 days | Roman numerals |

### Achievement Permanence

- **Badges are permanent** - Once earned, always displayed
- **Frame tier is dynamic** - Reflects current highest active qualifier
- Example: If portfolio drops from $10K to $5K, you keep "Serious Collector" badge but may drop from Gold frame if that was your only Gold qualifier

### Achievement Display

```
┌─ Achievement: Regular Trader ────────────┐
│ 🏅                                       │
│ Complete 10 trades                       │
│                                          │
│ Progress: ████████░░ 8/10               │
│                                          │
│ Unlocks: Silver frame eligibility        │
│ Rarity: 34% of traders                   │
└──────────────────────────────────────────┘
```

### Discovery Priority Calculation

```
Base score: 100

+ Trade milestones: 5-100 points per tier
+ Reputation tier: 10-100 points
+ Portfolio tier: 5-50 points
+ Community badges: 10-50 points each
+ Special achievements: 15-50 points each
+ Verification bonuses: +20 (email), +30 (Discord), +50 (ID)
- Penalty: Unresolved reports (-50 each)
```

Higher scores surface first in directory, discovery matches, and search results. Users never see the raw number.

### Achievement Timing

- **User-triggered** (trades, reviews): Real-time unlock
- **Passive** (portfolio value): Hourly batch calculation
- **Time-based** (veteran): Daily check

---

## Section 3: Trade Chat & Messaging

### Hybrid Messaging Architecture

Two distinct conversation types, unified in one inbox.

#### General DMs

- Standard conversations between connected users
- No special context, just chat
- Persist indefinitely
- Requires accepted connection to start

#### Trade Threads

- Auto-created when a trade proposal is sent
- Does NOT require existing connection (trade proposal acts as introduction)
- Thread header shows live trade status and card summary
- Archived (read-only) when trade completes, cancels, or expires
- Both parties can still reference archived threads

### Inbox UI

```
┌─────────────────────────────────────────────────────┐
│  Messages                          [New Message ▼] │
├─────────────────┬───────────────────────────────────┤
│ Conversations   │  @CardShark - Trade #1847        │
│                 │  ┌─────────────────────────────┐  │
│ 🔄 @CardShark   │  │ TRADE PROPOSAL · PENDING    │  │
│    Trade #1847  │  │ You offer: 2 cards ($45)    │  │
│    "What about.."│  │ They offer: 1 card ($50)   │  │
│                 │  │ [View Full] [Counter]       │  │
│ 💬 @MtgCollector│  └─────────────────────────────┘  │
│    "Thanks for..│                                   │
│                 │  CardShark: Would you consider    │
│ 🔄 @VintageMage │  adding $5 to balance it out?    │
│    Trade #1832  │                                   │
│    ✓ Completed  │  You: What about if I swap the   │
│                 │  Llanowar for a different elf?   │
│                 │                                   │
│                 │  [Type a message...]    [Send]   │
└─────────────────┴───────────────────────────────────┘
```

### Conversation Indicators

| Indicator | Meaning |
|-----------|---------|
| 🔄 | Trade thread (with trade number) |
| 💬 | General DM |
| Status badges | Pending, Accepted, Completed, Expired |
| Unread dot | New messages |
| Last message preview | Truncated recent message + timestamp |

### Trade Thread Features

| Feature | Description |
|---------|-------------|
| **Pinned trade widget** | Always visible at top, shows current proposal state |
| **Inline trade actions** | Accept, decline, counter directly from chat |
| **Card references** | Mention a card → shows mini preview (image, price) |
| **Status updates** | System messages when status changes |
| **Expiration warning** | Banner when trade is within 24h of expiring |

### Photo Sharing

- Available in trade threads only (abuse prevention)
- Up to 4 images per message, max 5MB each
- Lightbox view for inspection
- Auto-purged 30 days after trade closes (unless disputed)
- Common use: card condition verification

### Card Sharing in Chat

```
┌─────────────────────────────────────────┐
│ @You shared a card:                     │
│ ┌─────────────────────────────────────┐ │
│ │ [Card Image]  Sheoldred, the        │ │
│ │               Apocalypse            │ │
│ │               DMU · Mythic          │ │
│ │               Your price: $48       │ │
│ │               [Add to Trade]        │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### Real-Time Features

| Feature | Description |
|---------|-------------|
| Typing indicators | "@CardShark is typing..." |
| Presence status | Online (green), Away (yellow), Offline (grey) |
| Read receipts | ✓ sent, ✓✓ delivered, blue ✓✓ read |
| Message reactions | Quick emoji reactions (👍 ✅ 🤔) |

### Message Management

| Action | Rules |
|--------|-------|
| Delete own message | Within 5-minute window only |
| Deleted display | Shows "Message deleted" placeholder |
| System messages | Cannot be deleted |
| Message search | Search within conversations |
| Link previews | Scryfall/TCGPlayer links show card preview |

### Multiple Simultaneous Trades

- Same two users can have multiple open trade proposals
- Each trade gets unique thread: "Trade #1847", "Trade #1852"
- Listed separately in conversation list

### Connection Flow for Trades

1. Sending trade proposal to non-connection auto-sends connection request
2. If they accept trade → connection also accepted
3. If they decline → can still choose to connect or not
4. Enables cold-outreach trading while building social graph

### Blocking Behavior

- Block mid-trade → trade auto-cancels immediately
- System message: "Trade cancelled - user no longer available"
- Neither party penalized in success rate
- Blocked user cannot see profile, send trades, or message

### Thread Retention

| Thread Type | Retention |
|-------------|-----------|
| Active threads | Indefinite |
| Archived threads | Visible 1 year, then auto-hidden |
| Disputed trades | Retained until resolved + 1 year |

### Notification Batching

- 5 messages in 30 seconds = 1 notification "5 new messages from @User"

---

## Section 4: User Search & Directory

### Directory Home (`/traders`)

A browsable hub for discovering other users. Default view shows a grid of profile cards.

```
┌────────────────────────────────────────────────────────────┐
│  Trader Directory                                          │
│                                                            │
│  [🔍 Search users...                    ] [Filters ▼]     │
│                                                            │
│  Sort by: [Most Active ▼]  View: [Grid] [List]            │
│                                                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │ Profile  │ │ Profile  │ │ Profile  │ │ Profile  │     │
│  │  Card    │ │  Card    │ │  Card    │ │  Card    │     │
│  │@CardShark│ │@MTGWhale │ │@VintageM │ │@SetCollec│     │
│  │ ⭐⭐⭐⭐⭐ │ │ ⭐⭐⭐⭐⭐ │ │ ⭐⭐⭐⭐   │ │ ⭐⭐⭐⭐⭐ │     │
│  │ 142 trdz │ │ 89 trades│ │ 234 trdz │ │ 56 trades│     │
│  │ [Gold]   │ │[Platinum]│ │ [Gold]   │ │ [Silver] │     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │
│                                                            │
│  [Load More...]                                            │
└────────────────────────────────────────────────────────────┘
```

### Search

- Instant search by username or display name
- Results ranked by discovery score
- Fuzzy matching for typos (trigram index)
- URL persistence: `/traders?q=cardshark`

### Sort Options

| Option | Description |
|--------|-------------|
| Most Active | Recent trades |
| Highest Reputation | By star rating |
| Most Trades | Total completed |
| Newest Members | Recently joined |
| Best Match | Users with cards you want (logged in only) |

### Filters Panel

```
┌─ Filters ─────────────────────┐
│                               │
│ Location                      │
│ [Any region          ▼]      │
│ ☐ Near me (within 50 mi)     │
│                               │
│ Shipping                      │
│ ☐ Local meetup OK            │
│ ☐ Domestic shipping          │
│ ☐ International shipping     │
│                               │
│ Format                        │
│ ☐ Commander  ☐ Modern        │
│ ☐ Legacy  ☐ Pioneer          │
│ ☐ Vintage  ☐ Standard        │
│ ☐ Pauper  ☐ cEDH            │
│                               │
│ Reputation Tier               │
│ ☐ Elite  ☐ Trusted           │
│ ☐ Established  ☐ New         │
│                               │
│ Frame Tier                    │
│ ☐ Legendary  ☐ Platinum      │
│ ☐ Gold  ☐ Silver  ☐ Bronze   │
│                               │
│ Card Type                     │
│ ☐ Collector  ☐ Trader        │
│ ☐ Brewer  ☐ Investor         │
│                               │
│ Status                        │
│ ☐ Online now                 │
│ ☐ Open to trades             │
│ ☐ Has cards I want           │
│ ☐ Wants cards I have         │
│                               │
│ Verification                  │
│ ☐ Email verified             │
│ ☐ Discord linked             │
│ ☐ ID verified                │
│                               │
│ User Type                     │
│ ○ All  ○ Traders  ○ Stores   │
│                               │
│ [Apply Filters] [Clear]       │
└───────────────────────────────┘
```

### Privacy Toggle

In user settings (`/settings/privacy`):

| Setting | Default | Effect when off |
|---------|---------|-----------------|
| Appear in trader directory | On | Not shown in directory browse |
| Appear in search results | On | Not found via search |
| Show online status | On | Always shows as offline |
| Show portfolio value tier | On | Tier hidden on profile |

Users who opt out can still:
- Be found via direct profile URL
- Receive trade proposals from discovery matches
- Appear in "mutual connections" sections

### Quick Trade Preview

On hover/tap:
```
┌─────────────────────────┐
│ You want: 3 cards ($45) │
│ They want: 2 cards ($30)│
│ [See Matches]           │
└─────────────────────────┘
```

### List View Alternative

Compact rows for power users:
```
@CardShark     ⭐4.9  142 trades  Gold    Online   [View] [Trade]
@MTGWhale      ⭐5.0   89 trades  Plat    Away     [View] [Trade]
```

### Location & Shipping

| Field | Details |
|-------|---------|
| City, Country | Optional, user-entered |
| Shipping preference | Local meetup, Domestic only, International OK |
| Distance display | "~25 miles away" (when location shared) |
| Near me sort | Requires location sharing |

### Saved/Favorite Traders

- Bookmark icon on any profile card
- "Favorites" tab in directory
- Optional notification: "A favorite trader listed new cards"
- Bulk actions: Message All, Remove from Favorites

### Private Notes

- "Add note" on any user profile (only you see it)
- Yellow banner when viewing their profile
- Shows in trade thread header
- Searchable: find users by your notes

### Recently Interacted

- "Recent" tab in directory
- Last 20 users viewed, messaged, or traded with
- Timestamp: "Viewed 2 hours ago", "Traded 3 days ago"

### Suggested Connections

Algorithm considers:
- Mutual connections (friends of friends)
- Overlapping want lists
- Same format specialties
- Similar collection value tier

Displayed on directory home and profile sidebar.

### Pagination & Results

- Infinite scroll with "Load More"
- 24 results per load (divisible by 2, 3, 4 for grid)
- URL persistence: `/traders?tier=gold&format=commander&sort=reputation`

### Empty States

```
┌────────────────────────────────────────────────────┐
│                                                    │
│         🔍                                         │
│                                                    │
│   No traders match "vintage lotus"                │
│   with your current filters                        │
│                                                    │
│   Suggestions:                                     │
│   • Try different keywords                         │
│   • Remove some filters                            │
│   • Check spelling                                 │
│                                                    │
│   [Clear All Filters]                              │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## Section 5: Moderation System

### Three-Layer Approach

#### Layer 1: Self-Service (User Controls)

| Action | Effect |
|--------|--------|
| **Block user** | Cannot view profile, message, send trades, see in directory |
| **Unblock** | Via Settings → Blocked Users |
| **Mute conversation** | Stop notifications without blocking |

- Blocks are silent (blocked user sees "User not found")
- Active trades with blocked user auto-cancel

#### Layer 2: Community Reporting

**Reportable items:**
- User profiles (scam, impersonation)
- Individual messages (harassment, threats)
- Trade behavior (didn't ship, item not as described)

**Report Flow:**
```
┌─ Report User ────────────────────────────┐
│                                          │
│ Why are you reporting @BadActor?         │
│                                          │
│ ○ Spam or fake account                   │
│ ○ Harassment or abusive messages         │
│ ○ Scam or fraud attempt                  │
│ ○ Item not as described                  │
│ ○ Failed to complete trade               │
│ ○ Impersonation                          │
│ ○ Other                                  │
│                                          │
│ Additional details:                      │
│ ┌──────────────────────────────────────┐ │
│ │                                      │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ ☐ Block this user after reporting       │
│                                          │
│ [Cancel]                    [Submit]     │
└──────────────────────────────────────────┘
```

#### Layer 3: Automated Flags

| Trigger | Flag Level | Auto-Action |
|---------|------------|-------------|
| New user (<7 days), 10+ trade requests | Medium | None |
| 3+ reports from different users in 7 days | High | None |
| 5+ reports in 7 days | Critical | Auto-restrict |
| Sudden reputation drop (5→3 in a week) | Medium | None |
| Multiple cancelled trades in short period | Medium | None |
| Account created, immediately sends proposals | Low | None |
| Message contains known scam phrases | High | Message blocked |
| Failed trade with high-value items | High | None |
| Same device as banned user | Critical | Auto-restrict |

### Admin Dashboard (`/admin/moderation`)

```
┌─────────────────────────────────────────────────────────────┐
│  Moderation Queue                              [Settings ⚙]│
├─────────────────────────────────────────────────────────────┤
│  Filter: [All ▼]  [High Priority First ▼]    12 pending   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🔴 HIGH - @ShadyTrader                      2 hours ago  │
│     Auto-flag: 4 reports in 3 days                         │
│     Reports: Scam (2), Failed trade (1), Harassment (1)    │
│     [Review] [Quick: Warn ⚡] [Quick: Suspend ⚡]           │
│                                                             │
│  🟡 MEDIUM - @NewUser123                     5 hours ago  │
│     Auto-flag: New account, 15 trade requests sent         │
│     [Review] [Dismiss]                                      │
│                                                             │
│  🟢 LOW - @Collector99                       1 day ago    │
│     User report: Item not as described                     │
│     [Review] [Dismiss]                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Review Detail View

Shows:
- Full user profile and stats
- All reports against them with context
- Recent message threads (reported messages highlighted)
- Trade history and outcomes
- Previous moderation actions
- Similar past cases

### Moderator Actions

| Action | Effect |
|--------|--------|
| Dismiss | Close report, no action |
| Warn | Send warning message, flag on record |
| Restrict | Limit actions for X days |
| Suspend | Temporary ban (7/14/30 days) |
| Ban | Permanent removal |
| Escalate | Flag for other moderator |

### Graduated Punishment Guidance

| User History | Suggested Action |
|--------------|------------------|
| Clean record | Warn |
| 1 prior warning | Restrict (7 days) |
| Prior restriction | Suspend (14 days) |
| Prior suspension | Suspend (30 days) or Ban |
| Multiple suspensions | Ban |

Override requires written reason (logged).

### Appeals Process

- Suspended/banned users see "Appeal this decision" button
- Appeal form: Explain why action was wrong + upload evidence
- One appeal per moderation action
- Options: Uphold, Reduce, Overturn
- User notified of outcome

### Trade Dispute Mediation

Separate flow for trade-related issues:

```
┌─ Trade Dispute #1847 ──────────────────────────────────────┐
│                                                            │
│ Parties: @Buyer vs @Seller                                │
│ Trade value: $127.50                                       │
│ Status: Awaiting evidence                                  │
│                                                            │
│ Complaint: Item not as described                          │
│ "Cards arrived with water damage, listed as NM"           │
│                                                            │
│ ┌─ Evidence ────────────────────────────────────────────┐ │
│ │ @Buyer uploaded: 3 photos of damaged cards           │ │
│ │ @Seller uploaded: 1 photo of pre-ship condition      │ │
│ └───────────────────────────────────────────────────────┘ │
│                                                            │
│ Resolution:                                                │
│ ○ Side with buyer (seller gets negative review)           │
│ ○ Side with seller (buyer gets warning)                   │
│ ○ Mutual cancellation (no fault)                          │
│ ○ Inconclusive (no action)                                │
│                                                            │
│ [Request More Evidence] [Resolve Dispute]                 │
└────────────────────────────────────────────────────────────┘
```

### Evidence Preservation

Report filing triggers automatic snapshot:
- Full trade thread content (including deleted messages)
- Trade proposal details and history
- Photos exchanged (exempt from 30-day purge)
- Both users' profiles at time of report

Retained 1 year or until dispute resolved.

### Ban Evasion Detection

- Device fingerprint + IP pattern matching (hashed, privacy-conscious)
- New account flags:
  - Same device as banned user
  - Same IP range + similar username
  - Immediate contact with banned user's trade partners
- Alert: "⚠️ Possible alt of banned user @X - 78% confidence"
- Not auto-banned, queued for review

### Report Outcome Notifications

**To reporter:**
- "Thanks for your report. We've taken action." (violation found)
- "We reviewed your report and didn't find a violation." (dismissed)

**To reported user (if action taken):**
- "Your account has received a warning for [reason]"
- Link to appeal if eligible

### False Report Handling

- Track per-user: reports filed vs. reports with action
- Thresholds:
  - 5+ dismissed reports, <20% action rate → Flag for review
  - Pattern of targeting same user → Warning for harassment
  - Obvious bad faith → Reporting privileges suspended 30 days

### Moderator Internal Notes

- Separate from user-visible profile
- Only moderators see
- Timestamped, attributed to author
- Persists across all reports/reviews
- Searchable by keywords

### Additional Admin Features

| Feature | Purpose |
|---------|---------|
| Bulk actions | Handle spam waves efficiently |
| Moderator activity log | Track actions per mod |
| Conflict detection | Auto-escalate if mod is reported user |
| Response time targets | High: 24h, Medium: 72h, Low: 1 week |

### Legal Compliance

- DMCA takedown process
- Law enforcement request handling
- Data preservation hold capability

---

## Section 6: Real-Time Notifications

### WebSocket Architecture

Persistent connection when user is on site enables instant updates without polling.

### Notification Types & Triggers

#### Trade Activity
| Event | Notification |
|-------|--------------|
| New proposal received | "📦 @CardShark wants to trade with you" |
| Counter-offer received | "🔄 @CardShark sent a counter-offer" |
| Trade accepted | "✅ @CardShark accepted your trade!" |
| Trade declined | "@CardShark declined your trade" |
| Confirmation needed | "⏳ Confirm trade #1847 to complete" |
| Trade completed | "🎉 Trade #1847 completed!" |
| Expiring soon (24h) | "⚠️ Trade #1847 expires in 24 hours" |

#### Messages
| Event | Notification |
|-------|--------------|
| New message | "💬 @CardShark: Can you do $40?" |
| New photo shared | "📷 @CardShark shared a photo" |
| Multiple messages | "💬 5 new messages from @CardShark" |

#### Social
| Event | Notification |
|-------|--------------|
| Connection request | "👋 @NewTrader wants to connect" |
| Connection accepted | "@NewTrader accepted your connection" |
| Endorsement received | "🏅 @CardShark endorsed you as trustworthy" |
| New review | "⭐ @CardShark left you a 5-star review" |
| Connection milestone | "🤝 You now have 25 connections!" |

#### Discovery
| Event | Notification |
|-------|--------------|
| Hot match | "🔥 @Collector has 3 cards you want!" |
| Mutual match | "🎯 Mutual match with @Trader!" |
| Favorite listed cards | "📣 @FaveTrader listed new tradeable cards" |

#### Achievements
| Event | Notification |
|-------|--------------|
| Achievement unlocked | "🏆 Achievement unlocked: Trade Master!" |
| Frame upgrade | "✨ You've earned a Gold frame!" |
| Trading streak | "🔥 5-week trading streak!" |
| Leaderboard position | "📊 You're now #15 on the leaderboard" |

#### Price & Market
| Event | Notification |
|-------|--------------|
| Want list price drop | "💰 Sheoldred dropped 15% - now $45" |
| Portfolio change | "📈 Your collection is up 10% this week" |
| Card spiking | "🚀 Ragavan is up 25% today" |

#### Security & Account
| Event | Notification |
|-------|--------------|
| New device login | "🔐 New login from Chrome on Windows" |
| Password changed | "Your password was changed" |
| Email changed | "Your email was updated" |

#### Moderation
| Event | Notification |
|-------|--------------|
| Warning received | "⚠️ You've received a warning" |
| Restriction applied | "Your account has been restricted" |
| Appeal resolved | "Your appeal has been reviewed" |
| Dispute update | "Your dispute has a status update" |
| Report resolved | "Your report has been reviewed" |

### In-App Notification Center

```
┌─ Notifications ─────────────────────────────────┐
│                                                 │
│ [All] [Trades] [Messages] [Social] [System]    │
│                                                 │
│ 🔵 📦 @CardShark wants to trade      2 min ago │
│      [View Trade]                              │
│                                                 │
│ 🔵 💬 @MTGWhale: "Deal!"             15 min ago│
│      [View Message]                            │
│                                                 │
│    ✅ Trade #1832 completed          2 hrs ago │
│      [View Trade]                              │
│                                                 │
│    🏆 Achievement: Regular Trader    1 day ago │
│      [View Achievements]                       │
│                                                 │
│ [Mark All Read]         [Notification Settings]│
└─────────────────────────────────────────────────┘
```

### Toast Notifications

Real-time popups:
```
┌────────────────────────────────────────┐
│ 📦 New Trade Proposal                  │
│ @CardShark wants to trade with you    │
│                                        │
│ [View]                    [Dismiss]   │
└────────────────────────────────────────┘
```

- Top-right, auto-dismisses after 5 seconds
- Stack up to 3, older collapse
- Don't show for own actions

### Live Badge Updates

Without page refresh:
- Notification bell count
- Message inbox unread count
- Trade status badges
- Online status indicators

### Notification Preferences

```
┌─ Notification Preferences ───────────────────────┐
│                                                  │
│ Trade Activity           [On ▼]                 │
│ Messages                 [On ▼]                 │
│ Social                   [On ▼]                 │
│ Discovery & Matching     [Daily Digest ▼]       │
│ Price & Market Alerts    [Daily Digest ▼]       │
│ Achievements & Milestones [On ▼]                │
│ Security Alerts          [Always On - Required] │
│ Disputes & Reports       [On ▼]                 │
│ Listing Reminders        [Weekly ▼]             │
│                                                  │
│ Quiet Hours                                      │
│ ☐ Enable quiet hours                            │
│ From [10:00 PM ▼] to [8:00 AM ▼]               │
│ (Notifications batched, no toasts)              │
│                                                  │
│ [Save Preferences]                               │
└──────────────────────────────────────────────────┘
```

Options: On, Daily Digest, Off

Security alerts always on, cannot be disabled.

### Quiet Hours

- Notifications batched, no toasts during quiet period
- Security alerts bypass quiet hours
- User's local timezone

### Rate Limiting

- Max 50 notifications per hour per user
- Discovery notifications capped at 5 per day

### Retention

- Active notifications: 90 days
- Archived: Accessible via "View Older"

### Offline Handling

- WebSocket reconnects automatically
- Missed notifications fetched on reconnect
- Deduplication prevents duplicates

---

## Section 7: Onboarding Flow

### First-Time User Experience

**Step 1: Welcome**
```
┌────────────────────────────────────────────────────┐
│  Welcome to Dualcaster Deals! 🎴                  │
│                                                    │
│  Let's set up your trader profile.                │
│  This takes about 2 minutes.                       │
│                                                    │
│  [Get Started]                                     │
└────────────────────────────────────────────────────┘
```

**Step 2: Basic Info**
```
┌────────────────────────────────────────────────────┐
│  What should we call you?                          │
│                                                    │
│  Display Name: [_______________]                   │
│                                                    │
│  Tagline (optional):                               │
│  [_______________] 50 chars                        │
│  e.g., "Commander enthusiast, fair trades"        │
│                                                    │
│  [Continue]                                        │
└────────────────────────────────────────────────────┘
```

**Step 3: Trader Type**
```
┌────────────────────────────────────────────────────┐
│  What kind of trader are you?                      │
│                                                    │
│  ○ Collector - Building collections                │
│  ○ Trader - Active buying/selling                  │
│  ○ Brewer - Deckbuilding focused                   │
│  ○ Investor - Value-focused                        │
│                                                    │
│  (You can change this later)                       │
│                                                    │
│  [Continue]                                        │
└────────────────────────────────────────────────────┘
```

**Step 4: Formats (Optional)**
```
┌────────────────────────────────────────────────────┐
│  What formats do you play? (Select all)            │
│                                                    │
│  ☐ Commander    ☐ Modern     ☐ Legacy              │
│  ☐ Pioneer      ☐ Standard   ☐ Vintage             │
│  ☐ Pauper       ☐ cEDH       ☐ Limited             │
│                                                    │
│  [Continue]  [Skip]                                │
└────────────────────────────────────────────────────┘
```

**Step 5: Complete**
```
┌────────────────────────────────────────────────────┐
│  You're all set! 🎉                                │
│                                                    │
│  ┌──────────┐                                      │
│  │ Your     │  Your Bronze frame is ready.        │
│  │ Profile  │  Unlock better frames by trading    │
│  │ Card     │  and building reputation.           │
│  │ Preview  │                                      │
│  └──────────┘                                      │
│                                                    │
│  Next steps:                                       │
│  • Add cards to your inventory                     │
│  • Browse traders who have cards you want          │
│                                                    │
│  [Go to Dashboard]                                 │
└────────────────────────────────────────────────────┘
```

### Post-Onboarding Nudges

| Day | Nudge |
|-----|-------|
| 1 | "Welcome! Complete your profile to get discovered" |
| 2 | "Add cards to your tradeable inventory" |
| 3 | "Check out traders who have cards you want" |
| 7 | "You haven't made your first trade yet - need help?" |

---

## Database Schema

### New Models

```sql
-- Achievement definitions
CREATE TABLE achievement_definitions (
    id SERIAL PRIMARY KEY,
    key VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,  -- trade, reputation, portfolio, community, special
    icon VARCHAR(100),
    threshold JSONB,  -- {"trades": 10} or {"reviews": 5, "avg_rating": 4.0}
    discovery_points INTEGER DEFAULT 0,
    frame_tier_unlock VARCHAR(20),  -- bronze, silver, gold, platinum, legendary
    rarity_percent DECIMAL(5,2),
    is_hidden BOOLEAN DEFAULT FALSE,
    is_seasonal BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- User achievements
CREATE TABLE user_achievements (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    achievement_id INTEGER REFERENCES achievement_definitions(id),
    unlocked_at TIMESTAMP DEFAULT NOW(),
    progress JSONB,  -- {"current": 7, "target": 10}
    UNIQUE(user_id, achievement_id)
);

-- User frames
CREATE TABLE user_frames (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    frame_tier VARCHAR(20) NOT NULL,
    unlocked_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, frame_tier)
);

-- Trade threads
CREATE TABLE trade_threads (
    id SERIAL PRIMARY KEY,
    trade_proposal_id INTEGER REFERENCES trade_proposals(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    archived_at TIMESTAMP,
    last_message_at TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    UNIQUE(trade_proposal_id)
);

-- Trade thread messages
CREATE TABLE trade_thread_messages (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER REFERENCES trade_threads(id) ON DELETE CASCADE,
    sender_id INTEGER REFERENCES users(id),
    content TEXT,
    has_attachments BOOLEAN DEFAULT FALSE,
    reactions JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP,
    reported_at TIMESTAMP
);

-- Trade thread attachments
CREATE TABLE trade_thread_attachments (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES trade_thread_messages(id) ON DELETE CASCADE,
    file_url VARCHAR(500) NOT NULL,
    file_type VARCHAR(50),
    file_size INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    purge_after TIMESTAMP
);

-- User favorites
CREATE TABLE user_favorites (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    favorited_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    notify_on_listings BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, favorited_user_id)
);

-- User notes (private)
CREATE TABLE user_notes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    target_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, target_user_id)
);

-- Moderation actions
CREATE TABLE moderation_actions (
    id SERIAL PRIMARY KEY,
    moderator_id INTEGER REFERENCES users(id),
    target_user_id INTEGER REFERENCES users(id),
    action_type VARCHAR(50) NOT NULL,  -- warn, restrict, suspend, ban, dismiss
    reason TEXT,
    duration_days INTEGER,
    related_report_id INTEGER,
    related_dispute_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Moderation notes (internal)
CREATE TABLE moderation_notes (
    id SERIAL PRIMARY KEY,
    moderator_id INTEGER REFERENCES users(id),
    target_user_id INTEGER REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Appeals
CREATE TABLE appeals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    moderation_action_id INTEGER REFERENCES moderation_actions(id),
    appeal_text TEXT NOT NULL,
    evidence_urls TEXT[],
    status VARCHAR(20) DEFAULT 'pending',  -- pending, upheld, reduced, overturned
    reviewed_by INTEGER REFERENCES users(id),
    resolution_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

-- Trade disputes
CREATE TABLE trade_disputes (
    id SERIAL PRIMARY KEY,
    trade_proposal_id INTEGER REFERENCES trade_proposals(id),
    filed_by INTEGER REFERENCES users(id),
    dispute_type VARCHAR(50) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'open',  -- open, evidence_requested, resolved
    assigned_moderator_id INTEGER REFERENCES users(id),
    resolution VARCHAR(50),  -- buyer_wins, seller_wins, mutual_cancel, inconclusive
    resolution_notes TEXT,
    evidence_snapshot JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

-- Notification preferences
CREATE TABLE notification_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    preferences JSONB DEFAULT '{}',
    quiet_hours_enabled BOOLEAN DEFAULT FALSE,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC'
);

-- User format specialties
CREATE TABLE user_format_specialties (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    format VARCHAR(50) NOT NULL,
    UNIQUE(user_id, format)
);

-- Profile views (partitioned, auto-purge)
CREATE TABLE profile_views (
    id SERIAL PRIMARY KEY,
    viewer_id INTEGER REFERENCES users(id),  -- null for anonymous
    viewed_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_profile_views_viewed_user ON profile_views(viewed_user_id, created_at DESC);
```

### Extend Existing Models

```sql
-- Add to users table
ALTER TABLE users ADD COLUMN tagline VARCHAR(50);
ALTER TABLE users ADD COLUMN signature_card_id INTEGER REFERENCES cards(id);
ALTER TABLE users ADD COLUMN card_type VARCHAR(20);  -- collector, trader, brewer, investor
ALTER TABLE users ADD COLUMN card_type_changed_at TIMESTAMP;
ALTER TABLE users ADD COLUMN city VARCHAR(100);
ALTER TABLE users ADD COLUMN country VARCHAR(100);
ALTER TABLE users ADD COLUMN shipping_preference VARCHAR(20);  -- local, domestic, international
ALTER TABLE users ADD COLUMN active_frame_tier VARCHAR(20) DEFAULT 'bronze';
ALTER TABLE users ADD COLUMN discovery_score INTEGER DEFAULT 100;
ALTER TABLE users ADD COLUMN show_in_directory BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN show_in_search BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN show_online_status BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN show_portfolio_tier BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN onboarding_completed_at TIMESTAMP;
ALTER TABLE users ADD COLUMN last_active_at TIMESTAMP;

-- Add to messages table
ALTER TABLE messages ADD COLUMN trade_thread_id INTEGER REFERENCES trade_threads(id);
ALTER TABLE messages ADD COLUMN has_attachments BOOLEAN DEFAULT FALSE;
ALTER TABLE messages ADD COLUMN reactions JSONB DEFAULT '{}';
ALTER TABLE messages ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE messages ADD COLUMN reported_at TIMESTAMP;

-- Add to user_reports table
ALTER TABLE user_reports ADD COLUMN report_type VARCHAR(50);
ALTER TABLE user_reports ADD COLUMN evidence_snapshot JSONB;
ALTER TABLE user_reports ADD COLUMN resolution VARCHAR(50);
ALTER TABLE user_reports ADD COLUMN resolved_by INTEGER REFERENCES users(id);
ALTER TABLE user_reports ADD COLUMN resolved_at TIMESTAMP;
ALTER TABLE user_reports ADD COLUMN resolution_notes TEXT;
```

### Indexes

```sql
-- Directory search
CREATE INDEX idx_users_discovery_score ON users(discovery_score DESC) WHERE show_in_directory = TRUE;
CREATE INDEX idx_users_search_trgm ON users USING gin(username gin_trgm_ops, display_name gin_trgm_ops);
CREATE INDEX idx_users_location ON users(country, city) WHERE show_in_directory = TRUE;

-- Achievements
CREATE INDEX idx_user_achievements_user ON user_achievements(user_id);
CREATE INDEX idx_achievement_defs_category ON achievement_definitions(category);

-- Trade threads
CREATE INDEX idx_trade_threads_proposal ON trade_threads(trade_proposal_id);
CREATE INDEX idx_trade_thread_messages_thread ON trade_thread_messages(thread_id, created_at DESC);

-- Moderation
CREATE INDEX idx_moderation_actions_target ON moderation_actions(target_user_id, created_at DESC);
CREATE INDEX idx_user_reports_status ON user_reports(status, created_at DESC);
CREATE INDEX idx_trade_disputes_status ON trade_disputes(status, created_at DESC);

-- Notifications
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, read_at) WHERE read_at IS NULL;
```

---

## API Endpoints

### Achievements & Frames

```
GET  /achievements                    - All definitions + user progress
GET  /achievements/users/{id}         - User's unlocked achievements
GET  /frames                          - Available frames for current user
POST /frames/active                   - Set active frame {frame_tier}
```

### Directory & Search

```
GET  /directory                       - Paginated, filtered user list
     ?page=1&limit=24&sort=reputation&tier=gold&format=commander
     &shipping=domestic&online=true&has_my_wants=true
GET  /directory/search?q=cardshark    - Search by name
GET  /directory/suggested             - Suggested connections
GET  /directory/recent                - Recently interacted users
```

### Favorites & Notes

```
GET    /favorites                     - List favorites
POST   /favorites/{user_id}           - Add {notify_on_listings: bool}
DELETE /favorites/{user_id}           - Remove
GET    /notes                         - All my notes
GET    /notes/{user_id}               - Note for specific user
PUT    /notes/{user_id}               - Create/update {content}
DELETE /notes/{user_id}               - Remove
```

### Trade Threads

```
GET  /trades/{id}/thread              - Get thread with messages
POST /trades/{id}/thread/messages     - Send {content, card_id?}
POST /trades/{id}/thread/attachments  - Upload photo (multipart)
POST /trades/{id}/thread/messages/{msg_id}/react - {emoji}
DELETE /trades/{id}/thread/messages/{msg_id} - Delete (5 min window)
POST /trades/{id}/thread/messages/{msg_id}/report - Report message
```

### Moderation (Admin)

```
GET  /admin/moderation/queue          - Queue with filters
GET  /admin/moderation/cases/{id}     - Case detail with context
POST /admin/moderation/cases/{id}/action - {action, reason, duration?}
GET  /admin/moderation/appeals        - Appeals queue
POST /admin/moderation/appeals/{id}/resolve - {resolution, notes}
GET  /admin/moderation/disputes       - Trade disputes
POST /admin/moderation/disputes/{id}/resolve - {resolution, notes}
GET  /admin/moderation/users/{id}/history - Full mod history
POST /admin/moderation/users/{id}/notes - Add internal note
GET  /admin/moderation/stats          - Dashboard stats
```

### Disputes & Reports (User)

```
POST /disputes                        - File {trade_id, type, description}
GET  /disputes                        - My disputes
GET  /disputes/{id}                   - Dispute detail
POST /disputes/{id}/evidence          - Add evidence (multipart)
GET  /reports/mine                    - My submitted reports
GET  /reports/mine/{id}               - Report status
```

### Notifications

```
GET   /notifications                  - Paginated, filterable
POST  /notifications/{id}/read        - Mark read
POST  /notifications/read-all         - Mark all read
POST  /notifications/read-category    - Mark category read {category}
GET   /notifications/preferences      - Get prefs
PATCH /notifications/preferences      - Update prefs
GET   /notifications/unread-counts    - Counts by category
WS    /ws/notifications               - Real-time connection
```

### Profile Extensions

```
GET   /profile/me                     - Full profile with new fields
PATCH /profile/me                     - Update profile
POST  /profile/me/card-type           - Change card type (30-day cooldown)
GET   /profile/{id}/card              - Profile card data (public)
GET   /profile/{id}/card/preview      - Quick trade preview data
POST  /profile/me/export-card         - Generate shareable PNG
GET   /profile/me/views               - Who viewed my profile
```

### Onboarding

```
GET  /onboarding/status               - Completion state
POST /onboarding/complete             - Mark complete
POST /onboarding/skip                 - Skip
```

---

## Frontend Pages

### New Pages

| Route | Purpose |
|-------|---------|
| `/traders` | User directory |
| `/traders/favorites` | Favorited users |
| `/achievements` | Achievement showcase |
| `/settings/notifications` | Notification preferences |
| `/settings/privacy` | Privacy controls |
| `/settings/blocked` | Blocked users list |
| `/disputes` | My disputes |
| `/disputes/{id}` | Dispute detail |
| `/admin/moderation` | Moderation dashboard |
| `/admin/moderation/disputes` | Trade disputes |
| `/admin/moderation/appeals` | Appeals queue |

### Updated Pages

| Route | Changes |
|-------|---------|
| `/trades/{id}` | Add trade thread chat panel |
| `/messages` | Support trade thread conversations |
| `/profile/me` | Add new profile fields, frame selection |
| `/u/{hashid}` | Display full profile card with effects |

---

## Cross-Cutting Concerns

### Performance

| Concern | Solution |
|---------|----------|
| Profile cards loaded constantly | Redis cache, 5-min TTL, invalidate on update |
| Achievement calculations | Real-time for user-triggered, hourly batch for passive |
| Discovery score | Recalculate on achievement unlock, cache in user record |
| WebSocket connections | Redis pub/sub for horizontal scaling |
| Directory search | PostgreSQL full-text + trigram index |

### Security

| Concern | Solution |
|---------|----------|
| Photo uploads | Max 5MB, image types only, virus scan, strip EXIF |
| XSS in user content | Sanitize input, escape on render, CSP headers |
| Rate limiting | 10 proposals/hr, 100 messages/hr, 5 reports/day |
| Blocked user privacy | Show "User not found" not "You're blocked" |

### Data Retention

| Data Type | Retention |
|-----------|-----------|
| Messages (active) | Indefinite |
| Messages (archived) | 1 year visible, then hidden |
| Trade photos | 30 days (unless disputed) |
| Notifications | 90 days active, then archived |
| Moderation logs | 3 years |
| Deleted user data | Anonymized, not purged |

### Accessibility

| Element | Requirement |
|---------|-------------|
| Frame tiers | Don't rely on color alone (patterns/textures) |
| Frame effects | Respect prefers-reduced-motion |
| Achievement icons | Meaningful alt text |
| Toast notifications | ARIA live regions |
| Color contrast | WCAG AA minimum (4.5:1) |

### Mobile Adaptations

| Feature | Mobile |
|---------|--------|
| Profile cards | Stack vertically, full width |
| Directory grid | 2 columns tablet, 1 phone |
| Trade thread widget | Collapsible header |
| Filters | Bottom sheet |
| Quick actions | Bottom action bar |
| Card flip | Tap with hint |

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| User deletes account mid-trade | Active trades cancelled, others notified |
| User banned mid-trade | Trades auto-cancel, no penalty to other party |
| Simultaneous trade acceptance | Database transaction ensures one succeeds |
| Signature card removed from Scryfall | Graceful fallback, prompt to pick new |
| Quiet hours + security alert | Security alerts bypass quiet hours |
| Trade expires while typing | Show "Trade expired" banner, archive thread |
| User reports themselves | System rejects self-reports |
| Moderator is reported user | Auto-escalate, flag conflict |
| Timezone for expirations | User's local timezone |

---

## Implementation Order (Suggested)

1. **Database migrations** - New tables and columns
2. **Profile card system** - Core component, frames, tiers
3. **Achievement system** - Definitions, tracking, unlocks
4. **Trade threads** - Messaging integration
5. **User directory** - Search, filters, favorites
6. **Moderation system** - Reports, admin dashboard
7. **Real-time notifications** - WebSocket infrastructure
8. **Onboarding flow** - New user experience
9. **Polish** - Mobile, accessibility, performance

---

## Future Considerations

- Browser push notifications
- Email digests
- More achievement categories (seasonal, events)
- Additional frame customization (patterns within tiers)
- Internationalization (i18n)
- Store-specific features (verified store badges)
