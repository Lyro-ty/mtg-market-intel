"""Admin commands cog - restricted to bot owner/admins."""
import discord
from discord import app_commands
from discord.ext import commands
import structlog

from ..embeds import build_success_embed, build_error_embed, build_info_embed
from ..config import config

logger = structlog.get_logger(__name__)


def is_admin():
    """Check if user is a bot admin."""
    async def predicate(interaction: discord.Interaction) -> bool:
        # Check if user is bot owner
        app_info = await interaction.client.application_info()
        if interaction.user.id == app_info.owner.id:
            return True

        # Check if user has admin role in a guild
        if interaction.guild:
            member = interaction.guild.get_member(interaction.user.id)
            if member and member.guild_permissions.administrator:
                return True

        return False

    return app_commands.check(predicate)


class AdminCog(commands.Cog):
    """Admin commands for system operations."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="trigger-task", description="[Admin] Trigger a background task")
    @app_commands.describe(task="The task to trigger")
    @app_commands.choices(task=[
        app_commands.Choice(name="Price Collection", value="prices"),
        app_commands.Choice(name="Analytics", value="analytics"),
        app_commands.Choice(name="Recommendations", value="recommendations"),
        app_commands.Choice(name="Scryfall Import", value="scryfall"),
    ])
    @is_admin()
    async def trigger_task_command(
        self,
        interaction: discord.Interaction,
        task: app_commands.Choice[str]
    ):
        """Trigger a background task manually."""
        await interaction.response.defer(ephemeral=True)

        try:
            result = await self.bot.api.trigger_task(task.value)

            if result.get("success"):
                embed = build_success_embed(
                    "Task Triggered",
                    f"Successfully triggered **{task.name}**.\n\n"
                    f"Task ID: `{result.get('task_id', 'N/A')}`"
                )
            else:
                embed = build_error_embed(
                    "Task Failed",
                    f"Failed to trigger {task.name}: {result.get('error', 'Unknown error')}"
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error("trigger_task_failed", task=task.value, error=str(e))
            embed = build_error_embed(
                "Task Failed",
                f"Error triggering task: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @trigger_task_command.error
    async def trigger_task_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle trigger-task permission errors."""
        if isinstance(error, app_commands.CheckFailure):
            embed = build_error_embed(
                "Permission Denied",
                "You don't have permission to use this command."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clear-cache", description="[Admin] Clear Redis cache")
    @app_commands.describe(pattern="Cache key pattern to clear (default: all)")
    @is_admin()
    async def clear_cache_command(
        self,
        interaction: discord.Interaction,
        pattern: str = "*"
    ):
        """Clear Redis cache keys matching pattern."""
        await interaction.response.defer(ephemeral=True)

        try:
            result = await self.bot.api.clear_cache(pattern)

            if result.get("success"):
                embed = build_success_embed(
                    "Cache Cleared",
                    f"Cleared **{result.get('count', 0)}** cache keys matching `{pattern}`"
                )
            else:
                embed = build_error_embed(
                    "Clear Failed",
                    f"Failed to clear cache: {result.get('error', 'Unknown error')}"
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error("clear_cache_failed", pattern=pattern, error=str(e))
            embed = build_error_embed(
                "Clear Failed",
                f"Error clearing cache: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @clear_cache_command.error
    async def clear_cache_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle clear-cache permission errors."""
        if isinstance(error, app_commands.CheckFailure):
            embed = build_error_embed(
                "Permission Denied",
                "You don't have permission to use this command."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="sync-commands", description="[Admin] Sync slash commands with Discord")
    @is_admin()
    async def sync_commands_command(self, interaction: discord.Interaction):
        """Sync bot slash commands with Discord."""
        await interaction.response.defer(ephemeral=True)

        try:
            # Sync commands
            if interaction.guild:
                # Sync to current guild for faster updates
                synced = await self.bot.tree.sync(guild=interaction.guild)
                embed = build_success_embed(
                    "Commands Synced",
                    f"Synced **{len(synced)}** commands to this server."
                )
            else:
                # Global sync
                synced = await self.bot.tree.sync()
                embed = build_success_embed(
                    "Commands Synced",
                    f"Synced **{len(synced)}** commands globally.\n"
                    f"Note: Global sync may take up to an hour to propagate."
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error("sync_commands_failed", error=str(e))
            embed = build_error_embed(
                "Sync Failed",
                f"Error syncing commands: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @sync_commands_command.error
    async def sync_commands_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle sync-commands permission errors."""
        if isinstance(error, app_commands.CheckFailure):
            embed = build_error_embed(
                "Permission Denied",
                "You don't have permission to use this command."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="announce", description="[Admin] Send an announcement to all linked users")
    @app_commands.describe(
        title="Announcement title",
        message="Announcement message"
    )
    @is_admin()
    async def announce_command(
        self,
        interaction: discord.Interaction,
        title: str,
        message: str
    ):
        """Send announcement to all linked Discord users."""
        await interaction.response.defer(ephemeral=True)

        # This would typically queue announcements to be sent
        embed = build_info_embed(
            "Announcement Queued",
            f"**Title:** {title}\n\n{message}\n\n"
            f"*Note: Announcement delivery not yet implemented.*"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @announce_command.error
    async def announce_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle announce permission errors."""
        if isinstance(error, app_commands.CheckFailure):
            embed = build_error_embed(
                "Permission Denied",
                "You don't have permission to use this command."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Register cog with bot."""
    await bot.add_cog(AdminCog(bot))
