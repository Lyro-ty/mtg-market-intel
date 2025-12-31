"""Market commands cog - gainers, losers, and market overview."""
import discord
from discord import app_commands
from discord.ext import commands
import structlog

from ..embeds import build_movers_embed, build_error_embed

logger = structlog.get_logger(__name__)


class MarketCog(commands.Cog):
    """Market overview and top movers commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="gainers", description="Show top gaining cards in the last 24 hours")
    @app_commands.describe(count="Number of cards to show (default 5, max 10)")
    async def gainers_command(
        self, interaction: discord.Interaction, count: int = 5
    ):
        """Show top gaining cards."""
        await interaction.response.defer()

        count = min(max(count, 1), 10)  # Clamp between 1 and 10

        try:
            movers = await self.bot.api.get_top_movers(direction="up", limit=count)
            embed = build_movers_embed(movers, "up")
            await interaction.followup.send(embed=embed)

            logger.info(
                "Gainers lookup",
                user=str(interaction.user),
                count=len(movers),
            )

        except Exception as e:
            logger.error("Gainers lookup failed", error=str(e))
            embed = build_error_embed(
                "Lookup Failed",
                "Failed to fetch top gainers. Please try again later."
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="losers", description="Show top losing cards in the last 24 hours")
    @app_commands.describe(count="Number of cards to show (default 5, max 10)")
    async def losers_command(
        self, interaction: discord.Interaction, count: int = 5
    ):
        """Show top losing cards."""
        await interaction.response.defer()

        count = min(max(count, 1), 10)

        try:
            movers = await self.bot.api.get_top_movers(direction="down", limit=count)
            embed = build_movers_embed(movers, "down")
            await interaction.followup.send(embed=embed)

            logger.info(
                "Losers lookup",
                user=str(interaction.user),
                count=len(movers),
            )

        except Exception as e:
            logger.error("Losers lookup failed", error=str(e))
            embed = build_error_embed(
                "Lookup Failed",
                "Failed to fetch top losers. Please try again later."
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="movers", description="Show top market movers")
    @app_commands.describe(
        direction="Show gainers or losers",
        count="Number of cards to show (default 5, max 10)",
    )
    @app_commands.choices(direction=[
        app_commands.Choice(name="Gainers", value="up"),
        app_commands.Choice(name="Losers", value="down"),
    ])
    async def movers_command(
        self,
        interaction: discord.Interaction,
        direction: str = "up",
        count: int = 5,
    ):
        """Combined movers command with direction choice."""
        await interaction.response.defer()

        count = min(max(count, 1), 10)

        try:
            movers = await self.bot.api.get_top_movers(direction=direction, limit=count)
            embed = build_movers_embed(movers, direction)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error("Movers lookup failed", direction=direction, error=str(e))
            embed = build_error_embed(
                "Lookup Failed",
                "Failed to fetch market movers. Please try again later."
            )
            await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    await bot.add_cog(MarketCog(bot))
    logger.info("MarketCog loaded")
