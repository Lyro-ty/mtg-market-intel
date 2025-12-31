#!/usr/bin/env python3
"""Script to manually sync Discord slash commands.

This can be run separately from the bot to force-sync commands,
useful when commands have changed or for debugging.

Usage:
    python sync_commands.py [--global]

    --global: Sync globally instead of to a specific guild
              (takes up to 1 hour for Discord to propagate)
"""
import asyncio
import sys

import discord
from discord.ext import commands

from bot.config import config


async def sync_commands(global_sync: bool = False):
    """Sync slash commands to Discord."""
    if not config:
        print("ERROR: Bot configuration not loaded - check environment variables")
        sys.exit(1)

    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user}")

        # Load all cogs to register commands
        cogs = [
            "bot.cogs.general",
            "bot.cogs.price",
            "bot.cogs.market",
            "bot.cogs.portfolio",
            "bot.cogs.wantlist",
            "bot.cogs.alerts",
            "bot.cogs.discovery",
        ]

        for cog in cogs:
            try:
                await bot.load_extension(cog)
                print(f"Loaded {cog}")
            except Exception as e:
                print(f"Failed to load {cog}: {e}")

        # Sync commands
        if global_sync:
            print("Syncing commands globally (may take up to 1 hour)...")
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} global commands")
        else:
            if config.discord_guild_id:
                guild = discord.Object(id=config.discord_guild_id)
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                print(f"Synced {len(synced)} commands to guild {config.discord_guild_id}")
            else:
                print("No DISCORD_GUILD_ID set - syncing globally...")
                synced = await bot.tree.sync()
                print(f"Synced {len(synced)} global commands")

        # Print synced commands
        print("\nRegistered commands:")
        for cmd in synced:
            print(f"  /{cmd.name}: {cmd.description}")

        await bot.close()

    await bot.start(config.discord_token)


def main():
    global_sync = "--global" in sys.argv

    print("Discord Slash Command Sync Tool")
    print("=" * 40)

    try:
        asyncio.run(sync_commands(global_sync))
    except discord.LoginFailure:
        print("ERROR: Invalid Discord token")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted")
        sys.exit(0)


if __name__ == "__main__":
    main()
