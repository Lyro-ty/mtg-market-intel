"""Portfolio commands cog - collection viewing."""
import discord
from discord import app_commands
from discord.ext import commands
import structlog

from ..embeds import build_portfolio_embed, build_error_embed, build_info_embed

logger = structlog.get_logger(__name__)


class PortfolioCog(commands.Cog):
    """Portfolio and collection commands."""

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

    @app_commands.command(name="portfolio", description="View your portfolio summary")
    async def portfolio_command(self, interaction: discord.Interaction):
        """Show user's portfolio summary."""
        await interaction.response.defer()

        try:
            user = await self._get_linked_user(interaction)
            if not user:
                return

            portfolio = await self.bot.api.get_portfolio(user.user_id)

            if not portfolio:
                embed = build_info_embed(
                    "Empty Portfolio",
                    "Your portfolio is empty!\n\n"
                    "Add cards to your collection on Dualcaster Deals to track their value."
                )
                await interaction.followup.send(embed=embed)
                return

            display_name = user.display_name or user.username
            embed = build_portfolio_embed(portfolio, display_name)
            await interaction.followup.send(embed=embed)

            logger.info(
                "Portfolio lookup",
                user=str(interaction.user),
                linked_user=user.username,
                total_value=str(portfolio.total_value),
            )

        except Exception as e:
            logger.error("Portfolio lookup failed", error=str(e))
            embed = build_error_embed(
                "Lookup Failed",
                "Failed to fetch your portfolio. Please try again later."
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="collection", description="Alias for /portfolio")
    async def collection_command(self, interaction: discord.Interaction):
        """Alias for portfolio command."""
        await self.portfolio_command.callback(self, interaction)

    @app_commands.command(name="value", description="Quick check of your portfolio value")
    async def value_command(self, interaction: discord.Interaction):
        """Quick portfolio value check."""
        await interaction.response.defer(ephemeral=True)

        try:
            user = await self._get_linked_user(interaction)
            if not user:
                return

            portfolio = await self.bot.api.get_portfolio(user.user_id)

            if not portfolio:
                await interaction.followup.send(
                    "Your portfolio is empty.", ephemeral=True
                )
                return

            # Quick summary message
            value_msg = f"**Total Value:** ${portfolio.total_value:,.2f}"
            if portfolio.change_24h is not None:
                change_emoji = "" if portfolio.change_24h >= 0 else ""
                value_msg += f"\n**24h Change:** {change_emoji} ${portfolio.change_24h:,.2f}"
                if portfolio.change_24h_pct is not None:
                    value_msg += f" ({portfolio.change_24h_pct:+.1f}%)"

            value_msg += f"\n**Cards:** {portfolio.total_cards:,} ({portfolio.unique_cards:,} unique)"

            await interaction.followup.send(value_msg, ephemeral=True)

        except Exception as e:
            logger.error("Value lookup failed", error=str(e))
            await interaction.followup.send(
                "Failed to fetch portfolio value.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    await bot.add_cog(PortfolioCog(bot))
    logger.info("PortfolioCog loaded")
