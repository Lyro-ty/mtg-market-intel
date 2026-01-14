# Discord Bot Design

**Date:** 2025-12-31
**Status:** Approved
**Author:** Claude + User

## Overview

Discord bot for Dualcaster Deals that provides MTG price lookups, want list management, portfolio tracking, and price alert notifications. Users link their Discord accounts via OAuth, then interact with the platform through Discord commands.

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Account linking | Discord OAuth | Verifies user owns the Discord account |
| Command style | Both `!prefix` and `/slash` | Slash for discoverability, prefix for speed |
| Alert delivery | 5-minute polling loop | Simple, reliable, price alerts aren't time-critical |
| Privacy | `private` flag on commands | Flexibility without forcing DMs |
| Service architecture | Separate Python service | Independent scaling, clean separation |

---

## Discord OAuth Flow

### User Journey

1. User visits web app → Settings → "Link Discord"
2. Redirected to Discord OAuth authorize URL
   - Scopes: `identify` (user id, username, avatar)
   - Redirect: `/api/auth/discord/callback`
3. User approves on Discord
4. Callback exchanges code for access token
5. Backend fetches Discord user info and stores link
6. User can now use bot commands and receive DM alerts

### Database Changes

```sql
ALTER TABLE users ADD COLUMN discord_id VARCHAR(20) UNIQUE;
ALTER TABLE users ADD COLUMN discord_username VARCHAR(50);
ALTER TABLE users ADD COLUMN discord_alerts_enabled BOOLEAN DEFAULT TRUE;
```

### Backend Endpoints

```python
GET  /api/auth/discord/authorize
# Returns Discord OAuth URL with state token

GET  /api/auth/discord/callback?code={code}&state={state}
# Exchanges code, links account, redirects to settings

DELETE /api/auth/discord/unlink
# Removes Discord link from account
```

---

## Bot Architecture

### Directory Structure

```
discord-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Bot entry point, loads cogs
│   ├── config.py            # Settings from environment
│   ├── api_client.py        # HTTP client for backend API
│   ├── embeds.py            # Rich embed builders
│   ├── cogs/
│   │   ├── __init__.py
│   │   ├── general.py       # !help, !ping, !link, !status
│   │   ├── price.py         # !price, !history, !spread, !buylist
│   │   ├── market.py        # !movers, !meta, !staples
│   │   ├── portfolio.py     # !portfolio, !mygainers
│   │   ├── wantlist.py      # !want add/list/remove
│   │   ├── alerts.py        # !alerts, !alert, !mute + delivery loop
│   │   ├── discovery.py     # !find, !profile
│   │   └── slash.py         # Slash command variants
│   └── utils/
│       ├── __init__.py
│       ├── cards.py         # Card disambiguation logic
│       └── permissions.py   # Auth check decorators
├── Dockerfile
├── requirements.txt
└── .env.example
```

### Docker Compose Addition

```yaml
discord-bot:
  build: ./discord-bot
  restart: unless-stopped
  environment:
    - DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
    - BOT_SERVICE_TOKEN=${BOT_SERVICE_TOKEN}
    - API_URL=http://backend:8000/api
  depends_on:
    - backend
```

### API Client

```python
class APIClient:
    """HTTP client for backend API calls."""

    def __init__(self):
        self.base_url = config.API_URL
        self.headers = {"X-Bot-Token": config.BOT_SERVICE_TOKEN}

    async def get_user(self, discord_id: str) -> Optional[dict]:
        """Get user by Discord ID, None if not linked."""

    async def search_cards(self, query: str) -> dict:
        """Fuzzy search cards, returns results + suggestions."""

    async def get_card_price(self, card_id: int) -> dict:
        """Get all price data for a card in one call."""

    async def get_price_history(self, card_id: int, days: int = 30) -> list:
        """Get price history for chart/summary."""

    async def get_portfolio(self, discord_id: str) -> dict:
        """Get portfolio summary for user."""

    async def get_want_list(self, discord_id: str) -> list:
        """Get user's want list."""

    async def add_to_want_list(self, discord_id: str, card_id: int, target_price: float) -> dict:
        """Add card to want list."""

    async def remove_from_want_list(self, discord_id: str, card_id: int) -> bool:
        """Remove card from want list."""

    async def get_pending_alerts(self, since: datetime) -> list:
        """Get alerts that fired since timestamp."""

    async def mark_alert_delivered(self, alert_id: int) -> bool:
        """Mark alert as delivered via Discord."""
```

---

## Commands

### General (No Auth Required)

| Command | Description | Example |
|---------|-------------|---------|
| `!help [command]` | List commands or get help for specific command | `!help price` |
| `!ping` | Bot health check, shows latency | `!ping` |
| `!link` | Instructions to link Discord account | `!link` |
| `!status` | Shows if linked, account info | `!status` |

### Price & Market (No Auth Required)

| Command | Description | Example |
|---------|-------------|---------|
| `!price <card> [set] [foil]` | Current price with 7d change | `!price lightning bolt [2X2]` |
| `!price <card> cheapest` | Cheapest printing | `!price ragavan cheapest` |
| `!history <card>` | 30-day price trend | `!history sheoldred` |
| `!spread <card>` | Buy vs sell spread | `!spread mana crypt` |
| `!buylist <card>` | Card Kingdom buylist prices | `!buylist force of will` |
| `!movers` | Top gainers/losers today | `!movers` |
| `!meta <format>` | Top decks and staple prices | `!meta modern` |
| `!staples <commander>` | EDHREC staples with prices | `!staples atraxa` |

### Portfolio (Auth Required)

| Command | Description | Example |
|---------|-------------|---------|
| `!portfolio [private]` | Collection value summary | `!portfolio private` |
| `!mygainers [private]` | Top movers in your collection | `!mygainers` |

### Want List (Auth Required)

| Command | Description | Example |
|---------|-------------|---------|
| `!want add <card> [price]` | Add to want list | `!want add lightning bolt 1.50` |
| `!want list [private]` | Show want list | `!want list` |
| `!want remove <card>` | Remove from want list | `!want remove lightning bolt` |
| `!alerts [private]` | List active price alerts | `!alerts` |
| `!alert <card> <price>` | Quick-set price alert | `!alert ragavan 50` |
| `!mute` / `!unmute` | Toggle Discord DM alerts | `!mute` |

### Discovery (Auth Required)

| Command | Description | Example |
|---------|-------------|---------|
| `!find <card>` | Find users with card for trade | `!find mana crypt` |
| `!profile` | Link to your public profile | `!profile` |

---

## Command Output Examples

### Price Command (Rich Embed)

```python
# !price lightning bolt [2X2]
embed = discord.Embed(
    title="Lightning Bolt",
    url="https://dualcasterdeals.com/cards/12345",
    color=0xED1C24,  # Red for red card
)
embed.set_thumbnail(url="https://cards.scryfall.io/normal/front/...")
embed.add_field(name="Set", value="Double Masters 2022 (2X2)", inline=True)
embed.add_field(name="Price", value="$2.15", inline=True)
embed.add_field(name="7d Change", value="+5.2% 📈", inline=True)
embed.add_field(name="Buylist (CK)", value="$1.80", inline=True)
embed.add_field(name="Meta Share", value="12.3% Modern", inline=True)
embed.set_footer(text="Dualcaster Deals", icon_url=LOGO_URL)
```

### Card Disambiguation

```
!price lightning bolt

⚡ Multiple printings found for "Lightning Bolt":

1. **Double Masters 2022** (2X2) — $2.15
2. **Strixhaven Mystical Archive** (STA) — $4.50
3. **Masters 25** (A25) — $2.80
4. **4th Edition** (4ED) — $2.40

Reply with a number, or use: `!price lightning bolt [2X2]`
Use `!price lightning bolt cheapest` for lowest price ($2.15)
```

### Portfolio Command

```
📊 **Your Portfolio**

**Total Value:** $4,523.50
**Today:** +$127.30 (+2.9%) 📈
**7 Days:** +$342.15 (+8.2%) 📈

**Cards:** 847
**Top Card:** Mana Crypt ($180.00)

[View Full Portfolio →](https://dualcasterdeals.com/portfolio)
```

### Want List

```
📝 **Your Want List** (5 cards)

1. ⏳ **Lightning Bolt** — Target: $1.50 (Current: $2.15)
2. ✅ **Counterspell** — Target: $1.00 (Current: $0.89) — *HIT!*
3. ⏳ **Force of Will** — Target: $80.00 (Current: $95.00)
4. ⏳ **Ragavan** — Target: $50.00 (Current: $68.00)
5. ⏳ **Sheoldred** — Target: $60.00 (Current: $72.00)

[Manage Want List →](https://dualcasterdeals.com/want-list)
```

### Find Traders

```
🔍 **3 users have Lightning Bolt for trade:**

• **@CardCollector** — 4 copies
• **@MTGTrader** — 2 copies
• **@SpellSlinger** — 1 copy

[View on Dualcaster Deals →](https://dualcasterdeals.com/cards/12345/traders)
```

### Error Messages

```
# Not linked
❌ **Account not linked**
Visit dualcasterdeals.com/settings to connect your Discord account.

# Card not found with suggestion
❌ **Card not found:** "Lightening Bolt"
Did you mean **Lightning Bolt**? Try: `!price lightning bolt`

# API unavailable
⚠️ **Service temporarily unavailable**
Please try again in a few minutes.

# Command on cooldown
⏳ **Slow down!** Try again in 3 seconds.
```

---

## Alert Delivery System

### Polling Loop

```python
class AlertsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_check = datetime.now(timezone.utc)
        self.check_alerts.start()

    @tasks.loop(minutes=5)
    async def check_alerts(self):
        """Poll for pending alerts and deliver via DM."""
        alerts = await api.get_pending_alerts(since=self.last_check)
        self.last_check = datetime.now(timezone.utc)

        for alert in alerts:
            await self.deliver_alert(alert)

    async def deliver_alert(self, alert: dict):
        """Attempt to DM user about triggered alert."""
        try:
            user = await self.bot.fetch_user(int(alert["discord_id"]))
            embed = build_alert_embed(alert)
            await user.send(embed=embed)
            await api.mark_alert_delivered(alert["id"])
        except discord.Forbidden:
            # User has DMs disabled
            await api.mark_alert_failed(alert["id"], "DMs disabled")
        except discord.NotFound:
            # User not found
            await api.mark_alert_failed(alert["id"], "User not found")
```

### Alert Queue Table

```sql
CREATE TABLE discord_alert_queue (
    id SERIAL PRIMARY KEY,
    notification_id INTEGER REFERENCES notifications(id) ON DELETE CASCADE,
    discord_id VARCHAR(20) NOT NULL,

    -- Delivery tracking
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    last_attempt_at TIMESTAMPTZ,
    next_attempt_at TIMESTAMPTZ,

    -- Status
    delivered_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    error_message TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_alert_queue_pending ON discord_alert_queue (next_attempt_at)
    WHERE delivered_at IS NULL AND failed_at IS NULL;
CREATE INDEX ix_alert_queue_discord ON discord_alert_queue (discord_id);
```

### Retry Logic

```python
RETRY_DELAYS = [0, 300, 900]  # Immediate, 5min, 15min

async def queue_alert(notification_id: int, discord_id: str):
    """Add alert to delivery queue."""
    await db.execute(
        insert(discord_alert_queue).values(
            notification_id=notification_id,
            discord_id=discord_id,
            next_attempt_at=datetime.now(timezone.utc),
        )
    )

async def handle_delivery_failure(queue_id: int, error: str):
    """Handle failed delivery with retry logic."""
    queue_item = await db.get(queue_id)

    if queue_item.attempts >= queue_item.max_attempts:
        # Give up
        queue_item.failed_at = datetime.now(timezone.utc)
        queue_item.error_message = error
    else:
        # Schedule retry
        delay = RETRY_DELAYS[min(queue_item.attempts, len(RETRY_DELAYS) - 1)]
        queue_item.attempts += 1
        queue_item.last_attempt_at = datetime.now(timezone.utc)
        queue_item.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        queue_item.error_message = error
```

---

## Backend API Additions

### Bot-Specific Endpoints

All endpoints require `X-Bot-Token` header authentication.

```python
# backend/app/api/routes/bot.py

router = APIRouter(prefix="/bot", tags=["Bot"])

@router.get("/user/{discord_id}")
async def get_user_by_discord(discord_id: str) -> UserResponse:
    """Get user profile by Discord ID. Returns 404 if not linked."""

@router.get("/user/{discord_id}/portfolio")
async def get_user_portfolio(discord_id: str) -> PortfolioSummary:
    """Get portfolio summary for Discord user."""

@router.get("/user/{discord_id}/want-list")
async def get_user_want_list(discord_id: str) -> list[WantListItemResponse]:
    """Get want list for Discord user."""

@router.post("/user/{discord_id}/want-list")
async def add_to_want_list(
    discord_id: str,
    body: WantListCreate
) -> WantListItemResponse:
    """Add card to want list."""

@router.delete("/user/{discord_id}/want-list/{card_id}")
async def remove_from_want_list(discord_id: str, card_id: int):
    """Remove card from want list."""

@router.get("/user/{discord_id}/alerts")
async def get_user_alerts(discord_id: str) -> list[AlertResponse]:
    """Get active alerts for user."""

@router.post("/user/{discord_id}/alerts")
async def create_alert(
    discord_id: str,
    body: AlertCreate
) -> AlertResponse:
    """Create price alert."""

@router.patch("/user/{discord_id}/preferences")
async def update_preferences(
    discord_id: str,
    body: PreferencesUpdate
) -> PreferencesResponse:
    """Update user preferences (mute/unmute alerts)."""

@router.get("/cards/search")
async def search_cards(q: str, limit: int = 10) -> CardSearchResponse:
    """Fuzzy search cards with suggestions."""

@router.get("/card-price/{card_id}")
async def get_card_price(card_id: int) -> CardPriceResponse:
    """Get all price data for a card in one call."""

@router.get("/card/{card_id}/history")
async def get_price_history(
    card_id: int,
    days: int = 30
) -> list[PricePoint]:
    """Get price history."""

@router.get("/movers")
async def get_movers(limit: int = 5) -> MoversResponse:
    """Get top gainers and losers."""

@router.get("/find-traders/{card_id}")
async def find_traders(card_id: int, limit: int = 10) -> list[TraderInfo]:
    """Find users with card marked for trade."""

@router.get("/pending-alerts")
async def get_pending_alerts(since: datetime) -> list[PendingAlert]:
    """Get alerts that fired since timestamp."""

@router.post("/alerts/{alert_id}/delivered")
async def mark_alert_delivered(alert_id: int):
    """Mark alert as delivered via Discord."""

@router.post("/alerts/{alert_id}/failed")
async def mark_alert_failed(alert_id: int, error: str):
    """Mark alert delivery as failed."""
```

### Bot Authentication Middleware

```python
from fastapi import Request, HTTPException, Depends

async def verify_bot_token(request: Request):
    """Verify bot service token."""
    token = request.headers.get("X-Bot-Token")
    if not token or token != settings.BOT_SERVICE_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing bot token"
        )

# Apply to all bot routes
router = APIRouter(
    prefix="/bot",
    dependencies=[Depends(verify_bot_token)]
)
```

---

## Slash Commands

### Registration

```python
from discord import app_commands

class SlashCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="price", description="Get card price")
    @app_commands.describe(
        card="Card name to look up",
        set_code="Optional set code (e.g., 2X2)",
        foil="Get foil price"
    )
    async def price(
        self,
        interaction: discord.Interaction,
        card: str,
        set_code: Optional[str] = None,
        foil: bool = False
    ):
        await interaction.response.defer()
        # ... same logic as !price

    @price.autocomplete("card")
    async def card_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete card names as user types."""
        if len(current) < 2:
            return []

        results = await api.search_cards(current, limit=25)
        return [
            app_commands.Choice(name=card["name"][:100], value=card["name"])
            for card in results["cards"]
        ]
```

---

## Rate Limiting

```python
from discord.ext.commands import cooldown, BucketType

class PriceCog(commands.Cog):
    @commands.command()
    @cooldown(1, 5, BucketType.user)  # 1 use per 5 seconds per user
    async def price(self, ctx, *, query: str):
        ...

    @commands.command()
    @cooldown(1, 30, BucketType.user)  # More expensive command
    async def portfolio(self, ctx):
        ...

    @price.error
    async def price_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Slow down! Try again in {error.retry_after:.0f}s")
```

---

## Environment Variables

```bash
# .env.example for discord-bot/

# Discord
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_APPLICATION_ID=your_app_id_here

# Backend API
API_URL=http://backend:8000/api
BOT_SERVICE_TOKEN=your_service_token_here

# Bot config
COMMAND_PREFIX=!
EMBED_COLOR=0x7C3AED  # Purple theme
```

---

## Implementation Tasks

### Phase 1: Core Infrastructure
1. Create `discord-bot/` directory structure
2. Set up Discord OAuth endpoints in backend
3. Add `discord_id`, `discord_username`, `discord_alerts_enabled` to users table
4. Implement bot authentication middleware
5. Create API client class

### Phase 2: Basic Commands
6. Implement `!help`, `!ping`, `!link`, `!status`
7. Implement `!price` with disambiguation
8. Implement `!movers`
9. Add rich embeds with Scryfall images
10. Add rate limiting

### Phase 3: User Features
11. Implement `!portfolio`, `!mygainers`
12. Implement `!want add/list/remove`
13. Implement `!alerts`, `!alert`
14. Add `private` flag support

### Phase 4: Market & Discovery
15. Implement `!spread`, `!buylist`, `!history`
16. Implement `!meta`, `!staples`
17. Implement `!find`, `!profile`

### Phase 5: Alerts & Polish
18. Create alert queue table and delivery loop
19. Implement retry logic
20. Implement `!mute`/`!unmute`
21. Add slash commands with autocomplete
22. Add fuzzy search with "did you mean?"

### Phase 6: Deployment
23. Create Dockerfile
24. Add to docker-compose.yml
25. Document bot setup in README
26. Register slash commands with Discord

---

## Security Considerations

1. **Bot token** — Never log, rotate if compromised
2. **Service token** — Separate from user JWTs, limited scope
3. **Rate limiting** — Per-user cooldowns prevent abuse
4. **Input validation** — Sanitize all card name inputs
5. **DM permissions** — Gracefully handle users who disable DMs
6. **OAuth state** — CSRF protection on OAuth flow

---

## Success Criteria

- Users can link Discord accounts via OAuth
- `!price` returns accurate data with card image
- Card disambiguation works for multi-printing cards
- Want list syncs between web and Discord
- Price alerts deliver via DM within 5 minutes
- Slash commands work with autocomplete
- Bot handles errors gracefully with helpful messages
