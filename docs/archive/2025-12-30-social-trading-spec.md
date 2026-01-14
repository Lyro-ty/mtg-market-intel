# Dualcaster Deals: Social Trading Platform Specification

## Executive Summary

Transform Dualcaster Deals from a single-player price tracking tool into **the premier social platform for MTG traders**. The core innovation is building the authoritative graph of MTG players, their collections, their wants, and the trust relationships between them.

### Strategic Positioning

| Competitor | Their Moat | Our Opportunity |
|------------|-----------|-----------------|
| TCGPlayer | Transactions, inventory | We don't handle money — we find matches |
| Card Kingdom | Curation, buylist | We aggregate THEIR prices |
| MTGGoldfish | Price history, content | We add social layer on top |
| Moxfield | Deck building, UI/UX | We import from them, focus on trading |
| Discord | Community, chat | We extend INTO Discord, not compete |

**Our Moat: Network effects from the social trading graph. The more users with public collections, the more valuable the platform becomes.**

---

## Core Concepts

### 1. The Social Graph Model

```
User
├── Identity
│   ├── Profile (username, bio, avatar)
│   ├── Connected Accounts (Discord, Moxfield, Twitter)
│   ├── Verification Level (email, Discord, LGS vouched)
│   └── Location (optional, for local trading)
│
├── Collections (existing)
│   ├── Inventory (what they own)
│   ├── Want List (what they want)
│   └── **Have List** (NEW: what they're willing to trade)
│
├── Reputation
│   ├── Trade History (completed trades)
│   ├── Reviews (from trade partners)
│   ├── Vouches (from community members)
│   └── Reputation Score (computed)
│
├── Social Connections
│   ├── Following (users they follow)
│   ├── Followers (users following them)
│   ├── Blocked Users
│   └── Server Memberships (Discord)
│
└── Preferences
    ├── Trade Radius (miles/km)
    ├── Preferred Formats
    ├── Communication Preferences
    └── Notification Settings
```

### 2. Trade Matching Types

**Direct Match (2-way)**
```
User A                     User B
Has: [Ragavan]      ←→     Has: [Force of Will]
Wants: [Force of Will]     Wants: [Ragavan]

Result: Perfect swap opportunity!
```

**One-Way Match**
```
User A                     User B
Wants: [Mana Crypt]  →     Has: [Mana Crypt]
Has: [nothing B wants]     Wants: [stuff A doesn't have]

Result: B might sell for cash, or 3-way trade possible
```

**Triangular Match (3+ way)**
```
User A → User B → User C → User A
Has: X    Has: Y    Has: Z
Wants: Z  Wants: X  Wants: Y

Result: Each person sends one card, receives one card
```

### 3. Trust Without Liability

We facilitate introductions and provide tools, but **never touch money or guarantee transactions**.

| We Provide | We DON'T Provide |
|------------|------------------|
| Match discovery | Payment processing |
| Trade value calculation | Escrow |
| User reputation/reviews | Shipping insurance |
| Messaging platform | Dispute resolution (beyond reviews) |
| Fair trade suggestions | Guarantees |

**Legal positioning: We're a communication platform, not a marketplace.**

---

## Database Schema Extensions

### New Tables

```sql
-- ============================================
-- USER SOCIAL EXTENSIONS
-- ============================================

-- Extend existing users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS trade_radius_miles INTEGER DEFAULT 50;
ALTER TABLE users ADD COLUMN IF NOT EXISTS location_display VARCHAR(255); -- "Denver, CO"
ALTER TABLE users ADD COLUMN IF NOT EXISTS latitude DECIMAL(10, 8);
ALTER TABLE users ADD COLUMN IF NOT EXISTS longitude DECIMAL(11, 8);
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_views INTEGER DEFAULT 0;

-- ============================================
-- CONNECTED ACCOUNTS
-- ============================================

CREATE TABLE connected_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL, -- 'discord', 'moxfield', 'twitter', 'archidekt'
    provider_user_id VARCHAR(255) NOT NULL,
    provider_username VARCHAR(255),
    provider_display_name VARCHAR(255),
    provider_avatar_url TEXT,
    access_token_encrypted TEXT,
    refresh_token_encrypted TEXT,
    token_expires_at TIMESTAMP,
    scopes TEXT[], -- OAuth scopes granted
    metadata JSONB, -- Provider-specific data
    connected_at TIMESTAMP DEFAULT NOW(),
    last_synced_at TIMESTAMP,
    is_primary BOOLEAN DEFAULT false, -- Primary account for this provider
    verified BOOLEAN DEFAULT false,
    
    UNIQUE(provider, provider_user_id),
    UNIQUE(user_id, provider, is_primary) -- Only one primary per provider
);

CREATE INDEX idx_connected_accounts_user ON connected_accounts(user_id);
CREATE INDEX idx_connected_accounts_provider ON connected_accounts(provider, provider_user_id);

-- ============================================
-- HAVE LIST (Tradeable Items)
-- ============================================

CREATE TABLE have_list_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    card_id UUID NOT NULL REFERENCES cards(id),
    inventory_item_id UUID REFERENCES inventory_items(id) ON DELETE SET NULL,
    
    -- Quantity and condition
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    condition VARCHAR(20) DEFAULT 'NM', -- NM, LP, MP, HP, DMG
    is_foil BOOLEAN DEFAULT false,
    is_etched BOOLEAN DEFAULT false,
    language VARCHAR(10) DEFAULT 'EN',
    
    -- Trading preferences for this item
    min_trade_value DECIMAL(10, 2), -- Won't trade unless receiving at least this
    trade_for_wants_only BOOLEAN DEFAULT false, -- Only trade for items on want list
    notes TEXT, -- "Will only trade for other RL cards"
    
    -- Visibility
    is_active BOOLEAN DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, card_id, condition, is_foil, language)
);

CREATE INDEX idx_have_list_user ON have_list_items(user_id) WHERE is_active = true;
CREATE INDEX idx_have_list_card ON have_list_items(card_id) WHERE is_active = true;
CREATE INDEX idx_have_list_value ON have_list_items(min_trade_value);

-- ============================================
-- TRADE MATCHES (Computed/Cached)
-- ============================================

CREATE TABLE trade_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Users involved
    user_a_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_b_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Match classification
    match_type VARCHAR(20) NOT NULL, -- 'direct', 'one_way_a_to_b', 'one_way_b_to_a', 'triangular'
    match_quality_score INTEGER, -- 0-100, higher = better match
    
    -- What each user could get
    user_a_receives JSONB, -- [{card_id, card_name, quantity, value, condition}]
    user_b_receives JSONB,
    
    -- Value calculations
    user_a_value DECIMAL(10, 2),
    user_b_value DECIMAL(10, 2),
    value_difference DECIMAL(10, 2),
    value_difference_pct DECIMAL(5, 2),
    
    -- For triangular matches
    intermediary_users UUID[], -- Other users in the chain
    
    -- Location relevance
    distance_miles DECIMAL(10, 2),
    is_local BOOLEAN DEFAULT false,
    
    -- Cache management
    computed_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '1 hour',
    is_stale BOOLEAN DEFAULT false,
    
    UNIQUE(user_a_id, user_b_id, match_type)
);

CREATE INDEX idx_matches_user_a ON trade_matches(user_a_id) WHERE NOT is_stale;
CREATE INDEX idx_matches_user_b ON trade_matches(user_b_id) WHERE NOT is_stale;
CREATE INDEX idx_matches_quality ON trade_matches(match_quality_score DESC);
CREATE INDEX idx_matches_local ON trade_matches(user_a_id, is_local) WHERE is_local = true;

-- ============================================
-- TRADE PROPOSALS
-- ============================================

CREATE TYPE trade_proposal_status AS ENUM (
    'draft',
    'pending',
    'viewed',
    'accepted',
    'declined',
    'countered',
    'expired',
    'cancelled',
    'completed'
);

CREATE TABLE trade_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Participants
    proposer_id UUID NOT NULL REFERENCES users(id),
    recipient_id UUID NOT NULL REFERENCES users(id),
    
    -- Status tracking
    status trade_proposal_status DEFAULT 'pending',
    
    -- What's being offered
    proposer_offers JSONB NOT NULL, -- [{card_id, card_name, quantity, condition, is_foil, value}]
    proposer_offers_value DECIMAL(10, 2),
    
    -- What's being requested
    proposer_wants JSONB NOT NULL,
    proposer_wants_value DECIMAL(10, 2),
    
    -- Cash adjustments (we don't process, just record intent)
    proposer_adds_cash DECIMAL(10, 2) DEFAULT 0,
    recipient_adds_cash DECIMAL(10, 2) DEFAULT 0,
    
    -- Communication
    message TEXT,
    decline_reason TEXT,
    
    -- For counter-offers
    parent_proposal_id UUID REFERENCES trade_proposals(id),
    counter_count INTEGER DEFAULT 0,
    
    -- Completion method (set when accepted)
    completion_method VARCHAR(50), -- 'mail', 'local_meetup', 'lgs', 'tcgplayer_direct', 'other'
    completion_notes TEXT,
    
    -- Expiration
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '7 days',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    viewed_at TIMESTAMP,
    responded_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    CONSTRAINT different_users CHECK (proposer_id != recipient_id)
);

CREATE INDEX idx_proposals_proposer ON trade_proposals(proposer_id, status);
CREATE INDEX idx_proposals_recipient ON trade_proposals(recipient_id, status);
CREATE INDEX idx_proposals_pending ON trade_proposals(recipient_id) 
    WHERE status IN ('pending', 'viewed');
CREATE INDEX idx_proposals_expires ON trade_proposals(expires_at) 
    WHERE status = 'pending';

-- ============================================
-- COMPLETED TRADES (Historical Record)
-- ============================================

CREATE TABLE completed_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES trade_proposals(id),
    
    -- Participants (denormalized for history)
    user_a_id UUID NOT NULL REFERENCES users(id),
    user_a_username VARCHAR(255),
    user_b_id UUID NOT NULL REFERENCES users(id),
    user_b_username VARCHAR(255),
    
    -- What was traded (snapshot)
    user_a_gave JSONB NOT NULL,
    user_a_gave_value DECIMAL(10, 2),
    user_b_gave JSONB NOT NULL,
    user_b_gave_value DECIMAL(10, 2),
    
    -- Cash involved
    cash_from_a DECIMAL(10, 2) DEFAULT 0,
    cash_from_b DECIMAL(10, 2) DEFAULT 0,
    
    -- Total value of trade
    total_trade_value DECIMAL(10, 2),
    
    -- How it was completed
    completion_method VARCHAR(50),
    
    -- Timestamps
    proposed_at TIMESTAMP,
    completed_at TIMESTAMP DEFAULT NOW(),
    
    -- Both parties confirmed?
    user_a_confirmed BOOLEAN DEFAULT false,
    user_b_confirmed BOOLEAN DEFAULT false,
    
    notes TEXT
);

CREATE INDEX idx_completed_trades_user_a ON completed_trades(user_a_id);
CREATE INDEX idx_completed_trades_user_b ON completed_trades(user_b_id);
CREATE INDEX idx_completed_trades_date ON completed_trades(completed_at DESC);

-- ============================================
-- TRADE REVIEWS
-- ============================================

CREATE TABLE trade_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id UUID NOT NULL REFERENCES completed_trades(id),
    
    -- Who is reviewing whom
    reviewer_id UUID NOT NULL REFERENCES users(id),
    reviewee_id UUID NOT NULL REFERENCES users(id),
    
    -- Ratings (1-5 scale)
    overall_rating INTEGER NOT NULL CHECK (overall_rating BETWEEN 1 AND 5),
    communication_rating INTEGER CHECK (communication_rating BETWEEN 1 AND 5),
    packaging_rating INTEGER CHECK (packaging_rating BETWEEN 1 AND 5), -- For mail trades
    accuracy_rating INTEGER CHECK (accuracy_rating BETWEEN 1 AND 5), -- Cards as described
    speed_rating INTEGER CHECK (speed_rating BETWEEN 1 AND 5),
    
    -- Written review
    comment TEXT,
    
    -- Flags
    is_positive BOOLEAN GENERATED ALWAYS AS (overall_rating >= 4) STORED,
    is_negative BOOLEAN GENERATED ALWAYS AS (overall_rating <= 2) STORED,
    
    -- Moderation
    is_hidden BOOLEAN DEFAULT false,
    hidden_reason TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    
    UNIQUE(trade_id, reviewer_id)
);

CREATE INDEX idx_reviews_reviewee ON trade_reviews(reviewee_id) WHERE NOT is_hidden;
CREATE INDEX idx_reviews_positive ON trade_reviews(reviewee_id) WHERE is_positive AND NOT is_hidden;

-- ============================================
-- USER REPUTATION (Computed Aggregate)
-- ============================================

CREATE TABLE user_reputation (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    
    -- Trade counts
    total_trades INTEGER DEFAULT 0,
    trades_as_proposer INTEGER DEFAULT 0,
    trades_as_recipient INTEGER DEFAULT 0,
    
    -- Value traded
    total_trade_value DECIMAL(12, 2) DEFAULT 0,
    average_trade_value DECIMAL(10, 2) DEFAULT 0,
    largest_trade_value DECIMAL(10, 2) DEFAULT 0,
    
    -- Review aggregates
    total_reviews INTEGER DEFAULT 0,
    average_rating DECIMAL(3, 2),
    communication_avg DECIMAL(3, 2),
    packaging_avg DECIMAL(3, 2),
    accuracy_avg DECIMAL(3, 2),
    speed_avg DECIMAL(3, 2),
    
    positive_reviews INTEGER DEFAULT 0,
    neutral_reviews INTEGER DEFAULT 0,
    negative_reviews INTEGER DEFAULT 0,
    
    -- Computed score (0-1000)
    reputation_score INTEGER DEFAULT 0,
    reputation_tier VARCHAR(20) DEFAULT 'new', -- 'new', 'bronze', 'silver', 'gold', 'platinum', 'diamond'
    
    -- Activity
    member_since TIMESTAMP,
    first_trade_at TIMESTAMP,
    last_trade_at TIMESTAMP,
    
    -- Streaks
    current_positive_streak INTEGER DEFAULT 0,
    longest_positive_streak INTEGER DEFAULT 0,
    
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- USER RELATIONSHIPS
-- ============================================

CREATE TABLE user_follows (
    follower_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followed_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (follower_id, followed_id),
    CONSTRAINT no_self_follow CHECK (follower_id != followed_id)
);

CREATE INDEX idx_follows_follower ON user_follows(follower_id);
CREATE INDEX idx_follows_followed ON user_follows(followed_id);

CREATE TABLE user_blocks (
    blocker_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (blocker_id, blocked_id),
    CONSTRAINT no_self_block CHECK (blocker_id != blocked_id)
);

CREATE INDEX idx_blocks_blocker ON user_blocks(blocker_id);

-- ============================================
-- MESSAGING
-- ============================================

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_a_id UUID NOT NULL REFERENCES users(id),
    user_b_id UUID NOT NULL REFERENCES users(id),
    
    -- Related trade (optional)
    trade_proposal_id UUID REFERENCES trade_proposals(id),
    
    -- Last activity
    last_message_at TIMESTAMP,
    last_message_preview TEXT,
    
    -- Read status
    user_a_last_read_at TIMESTAMP,
    user_b_last_read_at TIMESTAMP,
    
    -- Archive/mute
    user_a_archived BOOLEAN DEFAULT false,
    user_b_archived BOOLEAN DEFAULT false,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_a_id, user_b_id),
    CONSTRAINT ordered_users CHECK (user_a_id < user_b_id) -- Ensures uniqueness regardless of order
);

CREATE INDEX idx_conversations_user_a ON conversations(user_a_id);
CREATE INDEX idx_conversations_user_b ON conversations(user_b_id);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES users(id),
    
    content TEXT NOT NULL,
    
    -- Optional attachments
    attachment_type VARCHAR(20), -- 'image', 'trade_proposal'
    attachment_id UUID,
    
    -- Status
    read_at TIMESTAMP,
    edited_at TIMESTAMP,
    deleted_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at DESC);
CREATE INDEX idx_messages_unread ON messages(conversation_id) WHERE read_at IS NULL;

-- ============================================
-- DISCORD INTEGRATION
-- ============================================

CREATE TABLE discord_guilds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id VARCHAR(255) UNIQUE NOT NULL, -- Discord's snowflake ID
    guild_name VARCHAR(255),
    guild_icon_url TEXT,
    owner_discord_id VARCHAR(255),
    
    -- Link info
    linked_by_user_id UUID REFERENCES users(id),
    linked_at TIMESTAMP DEFAULT NOW(),
    
    -- Settings
    settings JSONB DEFAULT '{}',
    /*
    {
        "notification_channel_id": "...",
        "trade_channel_id": "...",
        "allow_price_lookups": true,
        "allow_trade_matching": true,
        "allow_server_wants": true,
        "require_linked_account": false,
        "mod_role_ids": ["..."]
    }
    */
    
    -- Stats
    member_count INTEGER DEFAULT 0,
    linked_member_count INTEGER DEFAULT 0,
    
    -- Verification
    is_verified BOOLEAN DEFAULT false, -- Verified as legitimate MTG community
    verified_at TIMESTAMP,
    verified_by VARCHAR(255),
    
    -- Activity
    last_activity_at TIMESTAMP,
    command_count INTEGER DEFAULT 0,
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_guilds_guild_id ON discord_guilds(guild_id);

CREATE TABLE discord_guild_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id UUID NOT NULL REFERENCES discord_guilds(id) ON DELETE CASCADE,
    
    -- Discord identity
    discord_user_id VARCHAR(255) NOT NULL,
    discord_username VARCHAR(255),
    discord_display_name VARCHAR(255),
    discord_avatar_url TEXT,
    
    -- Link to Dualcaster account (optional)
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Discord roles (cached)
    role_ids TEXT[],
    is_admin BOOLEAN DEFAULT false,
    is_mod BOOLEAN DEFAULT false,
    
    -- Timestamps
    joined_guild_at TIMESTAMP,
    linked_account_at TIMESTAMP,
    
    UNIQUE(guild_id, discord_user_id)
);

CREATE INDEX idx_guild_members_user ON discord_guild_members(user_id);
CREATE INDEX idx_guild_members_discord ON discord_guild_members(discord_user_id);

-- ============================================
-- NOTIFICATION PREFERENCES
-- ============================================

CREATE TABLE notification_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    
    -- Email notifications
    email_enabled BOOLEAN DEFAULT true,
    email_price_alerts BOOLEAN DEFAULT true,
    email_trade_matches BOOLEAN DEFAULT true,
    email_trade_proposals BOOLEAN DEFAULT true,
    email_messages BOOLEAN DEFAULT true,
    email_weekly_digest BOOLEAN DEFAULT true,
    
    -- Discord notifications
    discord_enabled BOOLEAN DEFAULT true,
    discord_price_alerts BOOLEAN DEFAULT true,
    discord_trade_matches BOOLEAN DEFAULT true,
    discord_trade_proposals BOOLEAN DEFAULT true,
    discord_dm_messages BOOLEAN DEFAULT false, -- Can be noisy
    
    -- Push notifications (future)
    push_enabled BOOLEAN DEFAULT false,
    
    -- Quiet hours
    quiet_hours_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    quiet_hours_timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Frequency limits
    max_emails_per_day INTEGER DEFAULT 10,
    max_discord_per_hour INTEGER DEFAULT 20,
    
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- ACTIVITY FEED (for following feature)
-- ============================================

CREATE TABLE activity_feed_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    event_type VARCHAR(50) NOT NULL,
    /*
    Types:
    - 'added_to_have_list'
    - 'added_to_want_list'
    - 'completed_trade'
    - 'received_review'
    - 'milestone' (100 trades, etc.)
    - 'price_target_hit'
    */
    
    -- Event data
    event_data JSONB NOT NULL,
    /*
    Example for 'added_to_have_list':
    {
        "cards": [{"card_id": "...", "card_name": "Ragavan", "quantity": 1}],
        "total_value": 65.00
    }
    */
    
    -- Visibility
    is_public BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_activity_user ON activity_feed_events(user_id, created_at DESC);
CREATE INDEX idx_activity_public ON activity_feed_events(created_at DESC) WHERE is_public = true;

-- ============================================
-- FUNCTIONS & TRIGGERS
-- ============================================

-- Update reputation when trade completes
CREATE OR REPLACE FUNCTION update_user_reputation()
RETURNS TRIGGER AS $$
BEGIN
    -- Update for user_a
    INSERT INTO user_reputation (user_id, total_trades, total_trade_value, member_since, last_trade_at, updated_at)
    VALUES (NEW.user_a_id, 1, NEW.total_trade_value, NOW(), NOW(), NOW())
    ON CONFLICT (user_id) DO UPDATE SET
        total_trades = user_reputation.total_trades + 1,
        total_trade_value = user_reputation.total_trade_value + NEW.total_trade_value,
        average_trade_value = (user_reputation.total_trade_value + NEW.total_trade_value) / (user_reputation.total_trades + 1),
        largest_trade_value = GREATEST(user_reputation.largest_trade_value, NEW.total_trade_value),
        last_trade_at = NOW(),
        updated_at = NOW();
    
    -- Update for user_b
    INSERT INTO user_reputation (user_id, total_trades, total_trade_value, member_since, last_trade_at, updated_at)
    VALUES (NEW.user_b_id, 1, NEW.total_trade_value, NOW(), NOW(), NOW())
    ON CONFLICT (user_id) DO UPDATE SET
        total_trades = user_reputation.total_trades + 1,
        total_trade_value = user_reputation.total_trade_value + NEW.total_trade_value,
        average_trade_value = (user_reputation.total_trade_value + NEW.total_trade_value) / (user_reputation.total_trades + 1),
        largest_trade_value = GREATEST(user_reputation.largest_trade_value, NEW.total_trade_value),
        last_trade_at = NOW(),
        updated_at = NOW();
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_reputation
AFTER INSERT ON completed_trades
FOR EACH ROW EXECUTE FUNCTION update_user_reputation();

-- Update reputation when review is added
CREATE OR REPLACE FUNCTION update_reputation_from_review()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE user_reputation SET
        total_reviews = total_reviews + 1,
        average_rating = (
            SELECT AVG(overall_rating)::DECIMAL(3,2)
            FROM trade_reviews
            WHERE reviewee_id = NEW.reviewee_id AND NOT is_hidden
        ),
        positive_reviews = (
            SELECT COUNT(*) FROM trade_reviews
            WHERE reviewee_id = NEW.reviewee_id AND is_positive AND NOT is_hidden
        ),
        negative_reviews = (
            SELECT COUNT(*) FROM trade_reviews
            WHERE reviewee_id = NEW.reviewee_id AND is_negative AND NOT is_hidden
        ),
        communication_avg = (
            SELECT AVG(communication_rating)::DECIMAL(3,2)
            FROM trade_reviews
            WHERE reviewee_id = NEW.reviewee_id AND communication_rating IS NOT NULL AND NOT is_hidden
        ),
        updated_at = NOW()
    WHERE user_id = NEW.reviewee_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_reputation_review
AFTER INSERT ON trade_reviews
FOR EACH ROW EXECUTE FUNCTION update_reputation_from_review();

-- Invalidate matches when have/want list changes
CREATE OR REPLACE FUNCTION invalidate_matches()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE trade_matches
    SET is_stale = true
    WHERE user_a_id = COALESCE(NEW.user_id, OLD.user_id)
       OR user_b_id = COALESCE(NEW.user_id, OLD.user_id);
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_invalidate_matches_have
AFTER INSERT OR UPDATE OR DELETE ON have_list_items
FOR EACH ROW EXECUTE FUNCTION invalidate_matches();

CREATE TRIGGER trigger_invalidate_matches_want
AFTER INSERT OR UPDATE OR DELETE ON want_list_items
FOR EACH ROW EXECUTE FUNCTION invalidate_matches();
```

---

## API Endpoints

### Authentication & Profile

```
# Existing
POST   /api/auth/register
POST   /api/auth/login
GET    /api/auth/me

# New - Profile
GET    /api/users/{username}                    # Public profile
PATCH  /api/users/me                            # Update profile
POST   /api/users/me/location                   # Set location
GET    /api/users/{username}/stats              # Trade stats
GET    /api/users/{username}/activity           # Activity feed
```

### Connected Accounts

```
GET    /api/connections                         # List connected accounts
POST   /api/connections/discord/initiate        # Start Discord OAuth
GET    /api/connections/discord/callback        # OAuth callback
POST   /api/connections/moxfield                # Link Moxfield
DELETE /api/connections/{provider}              # Unlink account
```

### Have List

```
GET    /api/have-list                           # My have list
POST   /api/have-list                           # Add item(s)
PATCH  /api/have-list/{id}                      # Update item
DELETE /api/have-list/{id}                      # Remove item
POST   /api/have-list/bulk                      # Bulk add from inventory
GET    /api/users/{username}/have-list          # Public have list
```

### Trade Matching

```
GET    /api/matches                             # My matches
GET    /api/matches/direct                      # Direct (2-way) matches only
GET    /api/matches/local                       # Local matches
GET    /api/matches/with/{username}             # Match details with specific user
POST   /api/matches/refresh                     # Force recalculation
GET    /api/matches/server/{guild_id}           # Matches within Discord server
```

### Trade Proposals

```
GET    /api/trades                              # My trades (all statuses)
GET    /api/trades/incoming                     # Proposals I've received
GET    /api/trades/outgoing                     # Proposals I've sent
POST   /api/trades                              # Create proposal
GET    /api/trades/{id}                         # Proposal details
PATCH  /api/trades/{id}                         # Update (accept/decline/counter)
POST   /api/trades/{id}/complete                # Mark completed
DELETE /api/trades/{id}                         # Cancel/withdraw
```

### Reviews & Reputation

```
GET    /api/users/{username}/reputation         # Reputation summary
GET    /api/users/{username}/reviews            # Reviews received
POST   /api/trades/{trade_id}/review            # Leave review
GET    /api/trades/{trade_id}/reviews           # Reviews for trade
```

### Messaging

```
GET    /api/messages                            # My conversations
GET    /api/messages/{username}                 # Conversation with user
POST   /api/messages/{username}                 # Send message
PATCH  /api/messages/conversations/{id}/read    # Mark conversation read
DELETE /api/messages/{id}                       # Delete message
```

### Social

```
GET    /api/following                           # Who I follow
GET    /api/followers                           # Who follows me
POST   /api/following/{username}                # Follow user
DELETE /api/following/{username}                # Unfollow
GET    /api/feed                                # Activity feed from followed users
POST   /api/blocks/{username}                   # Block user
DELETE /api/blocks/{username}                   # Unblock
```

### Discord Bot Internal API

```
# These endpoints are authenticated via bot token, not user JWT

POST   /api/bot/discord/user/lookup             # Get user by Discord ID
POST   /api/bot/discord/user/link               # Link Discord to account
GET    /api/bot/discord/user/{discord_id}/wants # User's want list
POST   /api/bot/discord/user/{discord_id}/wants # Add to want list
GET    /api/bot/discord/user/{discord_id}/has   # User's have list
POST   /api/bot/discord/user/{discord_id}/has   # Add to have list
GET    /api/bot/discord/user/{discord_id}/matches # User's matches
GET    /api/bot/discord/price/{card_name}       # Price lookup
GET    /api/bot/discord/guild/{guild_id}/stats  # Server stats
GET    /api/bot/discord/guild/{guild_id}/wants  # Aggregate wants
GET    /api/bot/discord/guild/{guild_id}/has    # Aggregate has
GET    /api/bot/discord/guild/{guild_id}/matches # Intra-server matches
POST   /api/bot/discord/guild/{guild_id}/link   # Link guild
PATCH  /api/bot/discord/guild/{guild_id}/settings # Update settings
```

---

## Discord Bot Specification

### Architecture

```
discord-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py                     # Entry point
│   ├── config.py                   # Environment config
│   ├── client.py                   # Discord client setup
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── client.py               # HTTP client to DD API
│   │   └── models.py               # Response models
│   │
│   ├── cogs/
│   │   ├── __init__.py
│   │   ├── account.py              # Link/unlink account
│   │   ├── wants.py                # Want list commands
│   │   ├── haves.py                # Have list commands
│   │   ├── prices.py               # Price lookup
│   │   ├── matches.py              # Trade matching
│   │   ├── trades.py               # Trade proposals
│   │   ├── profile.py              # View profiles
│   │   ├── server.py               # Server admin commands
│   │   └── help.py                 # Custom help
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── embeds.py               # Rich embed builders
│   │   ├── views.py                # Button/select menus
│   │   ├── modals.py               # Modal forms
│   │   └── pagination.py           # Paginated lists
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── price_alerts.py         # Check & send alerts
│   │   ├── match_notifications.py  # New match alerts
│   │   └── sync.py                 # Sync guild data
│   │
│   └── utils/
│       ├── __init__.py
│       ├── cards.py                # Card name parsing
│       ├── formatting.py           # Text formatting
│       └── permissions.py          # Permission checks
│
├── Dockerfile
├── requirements.txt
└── docker-compose.yml
```

### Slash Commands

```
/dd link                            # Link Discord to Dualcaster account
/dd unlink                          # Unlink account
/dd profile [user]                  # View profile (self or other)

/dd want add <card> [quantity]      # Add to want list
/dd want remove <card>              # Remove from want list
/dd want list [user]                # Show want list
/dd want clear                      # Clear want list

/dd have add <card> [quantity] [condition]  # Add to have list
/dd have remove <card>              # Remove from have list
/dd have list [user]                # Show have list
/dd have from-inventory             # Add all inventory to have list

/dd price <card>                    # Get card prices
/dd price history <card>            # Price history graph

/dd match                           # Find my trade matches
/dd match with <user>               # See match with specific user
/dd match server                    # Find matches in this server

/dd trade propose <user>            # Start trade proposal flow
/dd trade list                      # My active trades
/dd trade view <id>                 # View trade details

/dd server setup                    # Initial server setup (admin)
/dd server settings                 # Configure server (admin)
/dd server stats                    # Server trading stats
/dd server wants                    # Aggregate server want list
/dd server has                      # Aggregate server have list
```

### Rich Embeds

```python
# Example: Price Lookup Embed
def build_price_embed(card_data: dict) -> discord.Embed:
    embed = discord.Embed(
        title=card_data["name"],
        url=f"https://dualcasterdeals.com/cards/{card_data['id']}",
        color=get_color_for_rarity(card_data["rarity"])
    )
    
    embed.set_thumbnail(url=card_data["image_url"])
    
    # Price fields
    embed.add_field(
        name="💰 Market Prices",
        value=f"""
        **TCGPlayer:** ${card_data['tcg_market']:.2f}
        **Card Kingdom:** ${card_data['ck_price']:.2f}
        **Cardmarket:** €{card_data['cm_price']:.2f}
        """,
        inline=True
    )
    
    embed.add_field(
        name="📈 Trend",
        value=f"{card_data['trend_emoji']} {card_data['trend_pct']:+.1f}% (7d)",
        inline=True
    )
    
    embed.set_footer(text="Dualcaster Deals • Prices updated hourly")
    
    return embed
```

### Interactive Components

```python
# Trade Proposal View with Buttons
class TradeProposalView(discord.ui.View):
    def __init__(self, proposal_id: str, is_recipient: bool):
        super().__init__(timeout=300)
        self.proposal_id = proposal_id
        
        if is_recipient:
            self.add_item(AcceptButton(proposal_id))
            self.add_item(DeclineButton(proposal_id))
            self.add_item(CounterButton(proposal_id))
        else:
            self.add_item(CancelButton(proposal_id))
        
        self.add_item(ViewOnWebButton(proposal_id))


class AcceptButton(discord.ui.Button):
    def __init__(self, proposal_id: str):
        super().__init__(
            label="Accept Trade",
            style=discord.ButtonStyle.success,
            emoji="✅"
        )
        self.proposal_id = proposal_id
    
    async def callback(self, interaction: discord.Interaction):
        # Call API to accept
        result = await api_client.accept_trade(self.proposal_id)
        if result.success:
            await interaction.response.send_message(
                "🎉 Trade accepted! Check your DMs for next steps.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Error: {result.error}",
                ephemeral=True
            )
```

### Notification System

```python
# Background task for price alerts
@tasks.loop(minutes=15)
async def check_price_alerts():
    """Check for price alerts and send notifications."""
    alerts = await api_client.get_triggered_alerts()
    
    for alert in alerts:
        user = await bot.fetch_user(alert.discord_user_id)
        if user:
            embed = build_price_alert_embed(alert)
            try:
                await user.send(embed=embed)
                await api_client.mark_alert_sent(alert.id)
            except discord.Forbidden:
                # User has DMs disabled
                pass

# Background task for match notifications  
@tasks.loop(minutes=30)
async def check_new_matches():
    """Notify users of new trade matches."""
    matches = await api_client.get_new_matches()
    
    for match in matches:
        user = await bot.fetch_user(match.user_discord_id)
        if user:
            embed = build_match_notification_embed(match)
            try:
                await user.send(embed=embed)
            except discord.Forbidden:
                pass
```

---

## Matching Algorithm

### Core Matching Engine

```python
from typing import List, Optional
from dataclasses import dataclass
from uuid import UUID
import networkx as nx

@dataclass
class MatchCandidate:
    user_id: UUID
    username: str
    cards_they_have_i_want: List[dict]  # [{card_id, name, value, qty}]
    cards_i_have_they_want: List[dict]
    my_value: float  # Value of what I'd receive
    their_value: float  # Value of what they'd receive
    match_quality: int  # 0-100
    distance_miles: Optional[float]

@dataclass  
class TriangularMatch:
    participants: List[UUID]  # [A, B, C] means A→B→C→A
    trades: List[dict]  # What each person gives to next
    total_value: float
    balance_score: float  # How fair is it? 1.0 = perfectly balanced


class MatchingEngine:
    def __init__(self, db_session, price_service):
        self.db = db_session
        self.prices = price_service
    
    async def find_direct_matches(
        self, 
        user_id: UUID,
        min_match_value: float = 1.0,
        max_results: int = 50,
        local_only: bool = False,
        max_distance: Optional[float] = None
    ) -> List[MatchCandidate]:
        """
        Find users where mutual trading is possible.
        
        Algorithm:
        1. Get my want list and have list
        2. Find users whose have list intersects my wants
        3. Filter to those whose wants intersect my haves
        4. Calculate values and rank by match quality
        """
        
        # Get my lists
        my_wants = await self._get_want_list(user_id)
        my_haves = await self._get_have_list(user_id)
        
        if not my_wants or not my_haves:
            return []
        
        my_want_card_ids = {w.card_id for w in my_wants}
        my_have_card_ids = {h.card_id for h in my_haves}
        
        # Find candidates: users who have what I want
        candidates = await self.db.execute("""
            SELECT DISTINCT h.user_id
            FROM have_list_items h
            JOIN users u ON h.user_id = u.id
            WHERE h.card_id = ANY(:want_ids)
              AND h.user_id != :user_id
              AND h.is_active = true
              AND u.is_public = true
        """, {"want_ids": list(my_want_card_ids), "user_id": user_id})
        
        matches = []
        for candidate_id in candidates:
            # Check if they want what I have
            their_wants = await self._get_want_list(candidate_id)
            their_want_ids = {w.card_id for w in their_wants}
            
            overlap = their_want_ids & my_have_card_ids
            if not overlap:
                continue  # One-way only, skip for direct matches
            
            # Calculate match details
            their_haves = await self._get_have_list(candidate_id)
            
            cards_for_me = [
                h for h in their_haves 
                if h.card_id in my_want_card_ids
            ]
            cards_for_them = [
                h for h in my_haves
                if h.card_id in their_want_ids
            ]
            
            my_value = sum(self.prices.get_price(c.card_id) for c in cards_for_me)
            their_value = sum(self.prices.get_price(c.card_id) for c in cards_for_them)
            
            # Calculate match quality
            quality = self._calculate_match_quality(
                my_value, their_value, 
                len(cards_for_me), len(cards_for_them)
            )
            
            if quality < 20:  # Minimum quality threshold
                continue
            
            matches.append(MatchCandidate(
                user_id=candidate_id,
                username=await self._get_username(candidate_id),
                cards_they_have_i_want=cards_for_me,
                cards_i_have_they_want=cards_for_them,
                my_value=my_value,
                their_value=their_value,
                match_quality=quality,
                distance_miles=await self._calculate_distance(user_id, candidate_id)
            ))
        
        # Sort by quality
        matches.sort(key=lambda m: m.match_quality, reverse=True)
        
        return matches[:max_results]
    
    def _calculate_match_quality(
        self, 
        value_a: float, 
        value_b: float,
        count_a: int,
        count_b: int
    ) -> int:
        """
        Calculate match quality score (0-100).
        
        Factors:
        - Value balance (closer = better)
        - Total value (higher = more significant trade)
        - Card count (more cards = more options)
        """
        if value_a == 0 or value_b == 0:
            return 0
        
        # Value balance: 1.0 when equal, lower when imbalanced
        ratio = min(value_a, value_b) / max(value_a, value_b)
        balance_score = ratio * 40  # 0-40 points
        
        # Total value: logarithmic scale, maxes out around $500
        total = value_a + value_b
        value_score = min(30, (total / 500) * 30)  # 0-30 points
        
        # Card variety: more options = easier to balance
        variety_score = min(30, (count_a + count_b) * 3)  # 0-30 points
        
        return int(balance_score + value_score + variety_score)
    
    async def find_triangular_matches(
        self,
        user_id: UUID,
        max_depth: int = 4,
        max_results: int = 10
    ) -> List[TriangularMatch]:
        """
        Find N-way trade cycles using graph algorithms.
        
        This is computationally expensive, so we:
        1. Limit depth (usually 3-4)
        2. Only consider high-value cards
        3. Cache results aggressively
        """
        
        # Build trade graph
        # Nodes: users
        # Edges: A→B if A has something B wants
        
        graph = nx.DiGraph()
        
        # Get all active traders (with public profiles)
        traders = await self._get_active_traders(limit=1000)
        
        for trader in traders:
            graph.add_node(trader.user_id)
        
        # Add edges based on have/want overlaps
        for trader in traders:
            their_wants = await self._get_want_list(trader.user_id)
            want_ids = {w.card_id for w in their_wants}
            
            # Find who has what they want
            providers = await self.db.execute("""
                SELECT DISTINCT user_id, card_id
                FROM have_list_items
                WHERE card_id = ANY(:want_ids)
                  AND user_id != :trader_id
                  AND is_active = true
            """, {"want_ids": list(want_ids), "trader_id": trader.user_id})
            
            for provider_id, card_id in providers:
                # Edge: provider → trader (provider can give to trader)
                if not graph.has_edge(provider_id, trader.user_id):
                    graph.add_edge(provider_id, trader.user_id, cards=[])
                graph[provider_id][trader.user_id]['cards'].append(card_id)
        
        # Find cycles that include our user
        cycles = []
        for cycle in nx.simple_cycles(graph):
            if user_id in cycle and len(cycle) <= max_depth:
                cycles.append(cycle)
        
        # Convert to TriangularMatch objects
        matches = []
        for cycle in cycles[:max_results]:
            match = await self._build_triangular_match(cycle, graph)
            if match:
                matches.append(match)
        
        return sorted(matches, key=lambda m: m.balance_score, reverse=True)
```

---

## Frontend Components Needed

### New Pages

```
/profile/[username]         # Public profile page
/trades                     # Trade management hub
/trades/[id]               # Trade proposal detail
/matches                    # Trade match discovery
/messages                   # Messaging inbox
/settings/connections       # Manage connected accounts
/settings/notifications     # Notification preferences
/settings/privacy          # Privacy settings
```

### Key Components

```typescript
// Profile Components
<PublicProfile />           // User's public page
<ReputationBadge />         // Shows trade rep visually
<TradeHistory />            // List of completed trades
<ReviewsList />             // Reviews received

// Trade Components
<MatchCard />               // Single match preview
<MatchList />               // List of matches
<TradeProposalBuilder />    // Create/counter trade
<TradeDetail />             // Full trade view
<TradeStatusBadge />        // pending/accepted/etc

// Have List Components
<HaveListManager />         // Manage tradeable items
<AddToHaveList />           // Add from inventory
<HaveListItem />            // Single item row

// Social Components
<UserSearch />              // Find users
<FollowButton />            // Follow/unfollow
<ActivityFeed />            // Feed from followed users
<MessageThread />           // Conversation view
<MessageComposer />         // Send message

// Connection Components  
<DiscordConnect />          // Link Discord account
<MoxfieldConnect />         // Link Moxfield
<ConnectionsList />         // Manage connections
```

---

## Implementation Phases

### Phase 1: Social Foundation (2-3 weeks)

**Goal:** Public profiles, have lists, basic matching

**Backend:**
- [ ] Database migrations for new tables
- [ ] User profile endpoints (public view, edit)
- [ ] Have list CRUD endpoints
- [ ] Basic direct matching algorithm
- [ ] Location storage and distance calculation

**Frontend:**
- [ ] Public profile page
- [ ] Have list management UI
- [ ] Basic match discovery page
- [ ] Profile settings expansion

**Deliverable:** Users can make profiles public, add items to trade, see potential matches

---

### Phase 2: Trading Infrastructure (2-3 weeks)

**Goal:** Trade proposals, messaging, reputation foundation

**Backend:**
- [ ] Trade proposal CRUD
- [ ] Messaging system
- [ ] Trade completion flow
- [ ] Review system
- [ ] Reputation calculation

**Frontend:**
- [ ] Trade proposal builder
- [ ] Trade detail view
- [ ] Messaging inbox/thread
- [ ] Review submission
- [ ] Reputation display

**Deliverable:** Users can propose trades, negotiate via messages, complete trades, leave reviews

---

### Phase 3: Discord Integration (2-3 weeks)

**Goal:** Full-featured Discord bot

**Bot Development:**
- [ ] Bot scaffolding and auth
- [ ] Account linking flow
- [ ] Want/have list commands
- [ ] Price lookup commands
- [ ] Match commands
- [ ] Trade proposal flow (via DM)
- [ ] Server setup commands

**Backend:**
- [ ] Bot API endpoints
- [ ] Discord OAuth integration
- [ ] Guild management
- [ ] Notification delivery

**Deliverable:** Discord bot that can manage lists, find matches, facilitate trades

---

### Phase 4: Advanced Features (2-3 weeks)

**Goal:** Network effects and stickiness

**Features:**
- [ ] Triangular matching algorithm
- [ ] Activity feed from followed users
- [ ] Server-level aggregate features
- [ ] Price alert → Discord notifications
- [ ] Match notifications

**Polish:**
- [ ] Performance optimization (caching matches)
- [ ] Mobile responsiveness
- [ ] Onboarding flow
- [ ] Tutorial/help content

**Deliverable:** Full social trading platform with virality mechanisms

---

### Phase 5: Growth & Moats (Ongoing)

**Features:**
- [ ] LGS integration / local meetups
- [ ] Verified trader program
- [ ] API for third parties
- [ ] Mobile app (React Native?)
- [ ] Speculation groups (private communities)

---

## Success Metrics

### User Engagement
- DAU/MAU ratio
- Have list creation rate
- Match click-through rate
- Trade proposal rate
- Trade completion rate

### Network Health
- % of users with public profiles
- Average connections per user
- Cross-server trade rate
- Reputation score distribution

### Growth
- Discord servers using bot
- Organic referral rate
- User retention (30/60/90 day)

---

## Risk Mitigation

### Fraud/Scams
- Clear "we don't guarantee trades" messaging
- Reputation system with review authenticity checks
- Block/report functionality
- Community moderation tools for Discord servers

### Platform Risk
- Discord API changes → abstract bot interactions
- Don't rely solely on Discord → web is primary
- Data portability → users can export everything

### Scaling
- Match computation can be expensive → aggressive caching, background jobs
- Message storage → consider archival strategy
- Image/avatar storage → CDN with size limits

---

## Claude Code Implementation Guide

When implementing with Claude Code, approach in this order:

1. **Database first:** Run migrations, verify schema
2. **API endpoints:** Build and test with curl/Postman
3. **Frontend pages:** One at a time, starting with profile
4. **Discord bot:** Separate service, connects to existing API
5. **Background jobs:** Celery tasks for matching, notifications

For each feature, follow TDD:
1. Write failing test
2. Implement minimum code to pass
3. Refactor
4. Integration test
5. Manual QA

Key files to update:
- `backend/app/models/` - New SQLAlchemy models
- `backend/app/schemas/` - Pydantic schemas
- `backend/app/api/routes/` - New route files
- `backend/app/services/` - Business logic (especially matching)
- `frontend/src/app/` - New pages
- `frontend/src/components/` - New components

---

*This specification is the north star. Implementation details will evolve, but the vision remains: become the social graph for MTG trading.*
