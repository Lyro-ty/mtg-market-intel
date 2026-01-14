---
name: mtg-intel:discord-bot
description: Use when creating or modifying Discord bot commands, cogs, or alert functionality
---

# Discord Bot Development Skill for Dualcaster Deals

Follow these patterns when developing Discord bot features.

## File Structure

```
discord-bot/
├── main.py                    # Bot entry point
├── config.py                  # Environment configuration
├── bot/
│   ├── __init__.py
│   ├── cogs/                  # Command modules
│   │   ├── __init__.py
│   │   ├── general.py         # /help, /link, /status
│   │   ├── price.py           # /price <card>
│   │   ├── {feature}.py       # Your new cog
│   │   └── ...
│   ├── embeds.py              # Embed builders
│   └── api_client.py          # Backend API client
└── requirements.txt
```

## Cog Pattern

```python
# discord-bot/bot/cogs/{feature}.py
import discord
from discord import app_commands
from discord.ext import commands
from structlog import get_logger

from bot.embeds import build_card_embed, build_error_embed

logger = get_logger()


class {Feature}Cog(commands.Cog):
    """Cog for {feature} commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Access API client via self.bot.api

    @app_commands.command(name="{command}", description="Description of command")
    @app_commands.describe(
        param1="Description of param1",
        param2="Description of param2"
    )
    async def {command}_command(
        self,
        interaction: discord.Interaction,
        param1: str,
        param2: int = 10  # Optional with default
    ):
        """Handle /{command} command."""
        # Defer response for long operations
        await interaction.response.defer()

        try:
            # Call backend API
            data = await self.bot.api.get_{feature}(param1, limit=param2)

            if not data:
                embed = build_error_embed(
                    title="Not Found",
                    description=f"No {feature} found for '{param1}'"
                )
                await interaction.followup.send(embed=embed)
                return

            # Build response embed
            embed = self._build_{feature}_embed(data)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error("{command}_failed", error=str(e))
            embed = build_error_embed(
                title="Error",
                description=f"Failed to get {feature}: {str(e)}"
            )
            await interaction.followup.send(embed=embed)

    def _build_{feature}_embed(self, data: dict) -> discord.Embed:
        """Build embed for {feature} response."""
        embed = discord.Embed(
            title=data["name"],
            description=data.get("description", ""),
            color=discord.Color.gold()  # MTG gold theme
        )

        # Add fields
        embed.add_field(
            name="Field 1",
            value=str(data.get("field1", "N/A")),
            inline=True
        )

        # Add footer
        embed.set_footer(text="Dualcaster Deals")

        return embed


async def setup(bot: commands.Bot):
    """Register cog with bot."""
    await bot.add_cog({Feature}Cog(bot))
```

## Register Cog

Add to `discord-bot/main.py` in `setup_hook`:

```python
async def setup_hook(self):
    # Load cogs
    await self.load_extension("bot.cogs.general")
    await self.load_extension("bot.cogs.price")
    await self.load_extension("bot.cogs.{feature}")  # Add this

    # Sync commands
    await self.tree.sync()
```

## API Client Pattern

```python
# discord-bot/bot/api_client.py
import aiohttp
from config import settings


class APIClient:
    def __init__(self):
        self.base_url = settings.BACKEND_API_URL
        self.api_key = settings.DISCORD_BOT_API_KEY
        self._session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"X-API-Key": self.api_key}
            )
        return self._session

    async def get_{feature}(self, query: str, limit: int = 10) -> list[dict]:
        """Fetch {feature} from backend."""
        session = await self._get_session()
        async with session.get(
            f"{self.base_url}/api/{feature}/",
            params={"q": query, "limit": limit}
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            return []

    async def close(self):
        if self._session:
            await self._session.close()
```

## Embed Builder Pattern

```python
# discord-bot/bot/embeds.py
import discord


def build_card_embed(card: dict) -> discord.Embed:
    """Build embed for a card."""
    embed = discord.Embed(
        title=card["name"],
        description=card.get("oracle_text", ""),
        color=discord.Color.gold()
    )

    # Add price field
    if card.get("current_price"):
        embed.add_field(
            name="Price",
            value=f"${card['current_price']:.2f}",
            inline=True
        )

    # Add image
    if card.get("image_url"):
        embed.set_thumbnail(url=card["image_url"])

    return embed


def build_error_embed(title: str, description: str) -> discord.Embed:
    """Build error embed."""
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.red()
    )


def build_success_embed(title: str, description: str) -> discord.Embed:
    """Build success embed."""
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green()
    )
```

## Slash Command Options

### Choice Parameters
```python
@app_commands.command(name="format")
@app_commands.describe(format="MTG format to filter by")
@app_commands.choices(format=[
    app_commands.Choice(name="Standard", value="standard"),
    app_commands.Choice(name="Modern", value="modern"),
    app_commands.Choice(name="Pioneer", value="pioneer"),
    app_commands.Choice(name="Legacy", value="legacy"),
])
async def format_command(
    self,
    interaction: discord.Interaction,
    format: app_commands.Choice[str]
):
    selected_format = format.value  # "standard", "modern", etc.
```

### Autocomplete
```python
async def card_autocomplete(
    self,
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete for card names."""
    if len(current) < 2:
        return []

    cards = await self.bot.api.search_cards(current, limit=25)
    return [
        app_commands.Choice(name=card["name"][:100], value=card["name"][:100])
        for card in cards
    ]

@app_commands.command(name="price")
@app_commands.autocomplete(card=card_autocomplete)
async def price_command(self, interaction: discord.Interaction, card: str):
    ...
```

## Checklist

Before committing:
- [ ] Cog file created with proper class structure
- [ ] `setup()` function defined for cog loading
- [ ] Cog registered in main.py setup_hook
- [ ] API client methods added if needed
- [ ] Embed builders created for responses
- [ ] Error handling with user-friendly messages
- [ ] Logging added for debugging
- [ ] Test locally with Discord Developer Portal

## Testing

```bash
# Start bot locally
cd discord-bot
python main.py

# Sync commands (if needed)
python sync_commands.py

# Check logs
docker compose logs discord-bot
```

## Environment Variables

Required in `.env`:
```bash
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_BOT_API_KEY=your_internal_api_key
DISCORD_GUILD_ID=optional_for_dev_guild
BACKEND_API_URL=http://backend:8000
```

## Alert Delivery

The bot polls for pending alerts every 30 seconds:

```python
@tasks.loop(seconds=30)
async def poll_alerts(self):
    """Poll backend for pending price alerts."""
    try:
        alerts = await self.api.get_pending_alerts(limit=50)

        for alert in alerts:
            user = await self.fetch_user(int(alert["discord_id"]))
            if user:
                embed = build_alert_embed(alert)
                await user.send(embed=embed)
                await self.api.mark_alert_delivered(alert["id"])

    except Exception as e:
        logger.error("alert_polling_failed", error=str(e))
```

## Common Issues

1. **Commands not appearing**: Run sync_commands.py
2. **Rate limiting**: Use defer() for long operations
3. **Missing permissions**: Check bot has proper intents enabled
4. **DM failures**: User may have DMs disabled - handle gracefully
