"""General commands cog - account linking and help."""
import discord
from discord import app_commands
from discord.ext import commands
import structlog

from ..embeds import build_help_embed, build_success_embed, build_error_embed, build_info_embed
from ..config import config

logger = structlog.get_logger(__name__)


class GeneralCog(commands.Cog):
    """General bot commands for account management and help."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show bot help and available commands")
    async def help_command(self, interaction: discord.Interaction):
        """Display help information."""
        embed = build_help_embed()
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="link", description="Link your Discord account to Dualcaster Deals")
    async def link_command(self, interaction: discord.Interaction):
        """Start the account linking process."""
        # Check if already linked
        user = await self.bot.api.get_user_by_discord_id(str(interaction.user.id))

        if user:
            embed = build_info_embed(
                "Already Linked",
                f"Your Discord account is already linked to **{user.username}**.\n\n"
                f"Use `/unlink` to disconnect your account."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Generate linking URL
        # In production, this would be a proper OAuth flow URL
        link_url = f"{config.api_base_url.replace('backend:8000', 'localhost:3000')}/settings/integrations"

        embed = build_info_embed(
            "Link Your Account",
            f"To link your Discord account:\n\n"
            f"1. Go to [Account Settings]({link_url})\n"
            f"2. Click 'Connect Discord'\n"
            f"3. Authorize the connection\n\n"
            f"Your Discord ID: `{interaction.user.id}`"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="unlink", description="Unlink your Discord account from Dualcaster Deals")
    async def unlink_command(self, interaction: discord.Interaction):
        """Unlink Discord account."""
        user = await self.bot.api.get_user_by_discord_id(str(interaction.user.id))

        if not user:
            embed = build_error_embed(
                "Not Linked",
                "Your Discord account is not linked to any Dualcaster Deals account."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Direct user to unlink via the website
        unlink_url = f"{config.api_base_url.replace('backend:8000', 'localhost:3000')}/settings/integrations"

        embed = build_info_embed(
            "Unlink Your Account",
            f"To unlink your Discord account:\n\n"
            f"1. Go to [Account Settings]({unlink_url})\n"
            f"2. Click 'Disconnect' next to Discord\n\n"
            f"Currently linked to: **{user.username}**"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="status", description="Check your account status and bot connection")
    async def status_command(self, interaction: discord.Interaction):
        """Check account and bot status."""
        user = await self.bot.api.get_user_by_discord_id(str(interaction.user.id))

        if user:
            alerts_status = "Enabled" if user.discord_alerts_enabled else "Disabled"
            embed = build_success_embed(
                "Account Status",
                f"**Linked Account:** {user.username}\n"
                f"**Discord Alerts:** {alerts_status}\n\n"
                f"Use `/portfolio` to view your collection.\n"
                f"Use `/alerts enable/disable` to toggle notifications."
            )
        else:
            embed = build_info_embed(
                "Account Status",
                f"Your Discord account is not linked.\n\n"
                f"Use `/link` to connect your Dualcaster Deals account."
            )

        # Add bot info
        embed.add_field(
            name="Bot Info",
            value=f"Latency: {round(self.bot.latency * 1000)}ms\n"
                  f"Guilds: {len(self.bot.guilds)}",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping_command(self, interaction: discord.Interaction):
        """Simple ping command."""
        latency = round(self.bot.latency * 1000)
        embed = build_info_embed("Pong!", f"Latency: {latency}ms")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    await bot.add_cog(GeneralCog(bot))
    logger.info("GeneralCog loaded")
