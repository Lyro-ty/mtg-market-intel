#!/usr/bin/env python3
"""Dualcaster Deals Discord Bot - Main Entry Point."""
import asyncio
import sys
from pathlib import Path

import discord
from discord.ext import commands, tasks
import structlog

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent))

from bot.config import config
from bot.api_client import APIClient

logger = structlog.get_logger(__name__)


class DualcasterBot(commands.Bot):
    """Main bot class with API client and alert polling."""

    def __init__(self):
        intents = discord.Intents.default()
        # Note: message_content intent not needed for slash commands only

        super().__init__(
            command_prefix="!",
            intents=intents,
            description="MTG market intelligence and price tracking",
        )

        self.api = APIClient(config.api_base_url, config.api_token)

    async def setup_hook(self):
        """Called when the bot is starting up."""
        # Load cogs
        cogs = [
            "bot.cogs.general",
            "bot.cogs.price",
            "bot.cogs.market",
            "bot.cogs.portfolio",
            "bot.cogs.wantlist",
            "bot.cogs.alerts",
            "bot.cogs.discovery",
            "bot.cogs.dev",
            "bot.cogs.admin",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info("Loaded cog", cog=cog)
            except Exception as e:
                logger.error("Failed to load cog", cog=cog, error=str(e))

        # Sync slash commands
        if config.discord_guild_id:
            guild = discord.Object(id=config.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Synced commands to guild", guild_id=config.discord_guild_id)
        else:
            await self.tree.sync()
            logger.info("Synced global commands")

        # Start alert polling if enabled
        if config.enable_alerts:
            self.poll_alerts.start()
            logger.info("Started alert polling", interval=config.alert_poll_interval)

    async def on_ready(self):
        """Called when the bot is ready."""
        from datetime import datetime
        self.start_time = datetime.utcnow()
        logger.info(
            "Bot is ready",
            user=str(self.user),
            guilds=len(self.guilds),
        )

    async def close(self):
        """Clean up on shutdown."""
        if self.poll_alerts.is_running():
            self.poll_alerts.cancel()
        await self.api.close()
        await super().close()

    @tasks.loop(seconds=30)  # Will be overridden by config
    async def poll_alerts(self):
        """Poll backend for pending alerts and deliver them."""
        try:
            alerts = await self.api.get_pending_alerts(limit=50)
            if not alerts:
                return

            logger.info("Processing alerts", count=len(alerts))
            delivered_ids = []

            for alert in alerts:
                try:
                    # Get the user to DM
                    user = await self.fetch_user(int(alert.discord_id))
                    if not user:
                        await self.api.mark_alert_failed(alert.alert_id, "User not found")
                        continue

                    # Build embed based on alert type
                    embed = self._build_alert_embed(alert)

                    # Send DM
                    await user.send(embed=embed)
                    delivered_ids.append(alert.alert_id)
                    logger.info(
                        "Delivered alert",
                        alert_id=alert.alert_id,
                        user_id=alert.discord_id,
                        alert_type=alert.alert_type,
                    )

                except discord.Forbidden:
                    await self.api.mark_alert_failed(
                        alert.alert_id, "Cannot DM user (DMs disabled)"
                    )
                except discord.NotFound:
                    await self.api.mark_alert_failed(alert.alert_id, "User not found")
                except Exception as e:
                    logger.error(
                        "Failed to deliver alert",
                        alert_id=alert.alert_id,
                        error=str(e),
                    )
                    await self.api.mark_alert_failed(alert.alert_id, str(e))

            # Mark delivered alerts
            if delivered_ids:
                await self.api.mark_alerts_delivered(delivered_ids)
                logger.info("Marked alerts as delivered", count=len(delivered_ids))

        except Exception as e:
            logger.error("Alert polling failed", error=str(e))

    @poll_alerts.before_loop
    async def before_poll_alerts(self):
        """Wait for bot to be ready before polling."""
        await self.wait_until_ready()
        # Update loop interval from config
        self.poll_alerts.change_interval(seconds=config.alert_poll_interval)

    def _build_alert_embed(self, alert) -> discord.Embed:
        """Build a Discord embed for an alert."""
        from bot.embeds import build_alert_embed
        return build_alert_embed(alert)


def main():
    """Run the bot."""
    import logging

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    log = structlog.get_logger("main")
    log.info("Starting Dualcaster Deals Discord Bot")

    if not config:
        log.error("Bot configuration not loaded - check environment variables")
        sys.exit(1)

    log.info("Bot configured", guild_id=config.discord_guild_id, alerts_enabled=config.enable_alerts)

    bot = DualcasterBot()

    try:
        bot.run(config.discord_token, log_handler=None)
    except discord.LoginFailure:
        logger.error("Invalid Discord token")
        sys.exit(1)
    except Exception as e:
        logger.error("Bot crashed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
