"""Discovery commands cog - trade matching and discovery features."""
import discord
from discord import app_commands
from discord.ext import commands
import structlog

from ..embeds import build_error_embed, build_info_embed, COLOR_GOLD

logger = structlog.get_logger(__name__)


class DiscoveryCog(commands.Cog):
    """Trade discovery and matching commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_linked_user(self, interaction: discord.Interaction):
        """Get linked user or None with error message."""
        user = await self.bot.api.get_user_by_discord_id(str(interaction.user.id))
        if not user:
            embed = build_info_embed(
                "Account Not Linked",
                "Your Discord account is not linked to Dualcaster Deals.\n\n"
                "Use `/link` to connect your account."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return None
        return user

    @app_commands.command(name="trades", description="View your trade offers")
    async def trades_command(self, interaction: discord.Interaction):
        """Show user's trade offers (for trade list)."""
        await interaction.response.defer()

        try:
            user = await self._get_linked_user(interaction)
            if not user:
                return

            # This would call an API endpoint for trade items
            embed = build_info_embed(
                "Trade List",
                "Your trade list feature is available on the Dualcaster Deals website.\n\n"
                "Mark cards as 'For Trade' in your collection to list them."
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error("Trades lookup failed", error=str(e))
            embed = build_error_embed(
                "Lookup Failed",
                "Failed to fetch your trade list. Please try again later."
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="matches", description="Find potential trade matches")
    async def matches_command(self, interaction: discord.Interaction):
        """Find potential trade matches based on want list and for-trade items."""
        await interaction.response.defer()

        try:
            user = await self._get_linked_user(interaction)
            if not user:
                return

            # Build matches embed
            embed = discord.Embed(
                title="Trade Matching",
                description=(
                    "Trade matching finds users who have cards you want "
                    "and want cards you have for trade.\n\n"
                    "**How it works:**\n"
                    "1. Add cards to your Want List\n"
                    "2. Mark cards as 'For Trade' in your collection\n"
                    "3. We'll find matching traders\n\n"
                    "Visit Dualcaster Deals to explore matches!"
                ),
                color=COLOR_GOLD,
            )

            await interaction.followup.send(embed=embed)

            logger.info(
                "Matches lookup",
                user=str(interaction.user),
                linked_user=user.username,
            )

        except Exception as e:
            logger.error("Matches lookup failed", error=str(e))
            embed = build_error_embed(
                "Lookup Failed",
                "Failed to find trade matches. Please try again later."
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="discover", description="Discover cards based on your collection")
    async def discover_command(self, interaction: discord.Interaction):
        """Discover recommended cards."""
        await interaction.response.defer()

        try:
            user = await self._get_linked_user(interaction)
            if not user:
                return

            embed = discord.Embed(
                title="Card Discovery",
                description=(
                    "Get personalized card recommendations based on:\n\n"
                    "- Your collection theme\n"
                    "- Cards that synergize with your decks\n"
                    "- Market opportunities\n\n"
                    "Visit Dualcaster Deals for AI-powered recommendations!"
                ),
                color=COLOR_GOLD,
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error("Discover lookup failed", error=str(e))
            embed = build_error_embed(
                "Lookup Failed",
                "Failed to get recommendations. Please try again later."
            )
            await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    await bot.add_cog(DiscoveryCog(bot))
    logger.info("DiscoveryCog loaded")
