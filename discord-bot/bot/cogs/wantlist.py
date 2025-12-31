"""Want list commands cog - want list viewing."""
import discord
from discord import app_commands
from discord.ext import commands
import structlog

from ..embeds import build_wantlist_embed, build_error_embed, build_info_embed

logger = structlog.get_logger(__name__)


class WantlistCog(commands.Cog):
    """Want list commands."""

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

    @app_commands.command(name="wantlist", description="View your want list")
    @app_commands.describe(limit="Number of items to show (default 10)")
    async def wantlist_command(
        self, interaction: discord.Interaction, limit: int = 10
    ):
        """Show user's want list."""
        await interaction.response.defer()

        limit = min(max(limit, 1), 25)

        try:
            user = await self._get_linked_user(interaction)
            if not user:
                return

            wantlist = await self.bot.api.get_wantlist(user.user_id, limit=limit)

            if not wantlist or wantlist.total_items == 0:
                embed = build_info_embed(
                    "Empty Want List",
                    "Your want list is empty!\n\n"
                    "Add cards to your want list on Dualcaster Deals to track prices."
                )
                await interaction.followup.send(embed=embed)
                return

            display_name = user.display_name or user.username
            embed = build_wantlist_embed(wantlist, display_name)
            await interaction.followup.send(embed=embed)

            logger.info(
                "Wantlist lookup",
                user=str(interaction.user),
                linked_user=user.username,
                total_items=wantlist.total_items,
            )

        except Exception as e:
            logger.error("Wantlist lookup failed", error=str(e))
            embed = build_error_embed(
                "Lookup Failed",
                "Failed to fetch your want list. Please try again later."
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="wants", description="Alias for /wantlist")
    @app_commands.describe(limit="Number of items to show (default 10)")
    async def wants_command(
        self, interaction: discord.Interaction, limit: int = 10
    ):
        """Alias for wantlist command."""
        await self.wantlist_command.callback(self, interaction, limit)

    @app_commands.command(name="watchlist", description="Alias for /wantlist")
    @app_commands.describe(limit="Number of items to show (default 10)")
    async def watchlist_command(
        self, interaction: discord.Interaction, limit: int = 10
    ):
        """Alias for wantlist command."""
        await self.wantlist_command.callback(self, interaction, limit)


async def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    await bot.add_cog(WantlistCog(bot))
    logger.info("WantlistCog loaded")
