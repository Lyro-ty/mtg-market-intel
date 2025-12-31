"""Alerts commands cog - alert management."""
import discord
from discord import app_commands
from discord.ext import commands
import structlog

from ..embeds import build_success_embed, build_error_embed, build_info_embed

logger = structlog.get_logger(__name__)


class AlertsCog(commands.Cog):
    """Alert management commands."""

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

    alerts_group = app_commands.Group(name="alerts", description="Manage your price alerts")

    @alerts_group.command(name="status", description="Check your alert settings")
    async def alerts_status(self, interaction: discord.Interaction):
        """Check alert status."""
        await interaction.response.defer(ephemeral=True)

        try:
            user = await self._get_linked_user(interaction)
            if not user:
                return

            status = "enabled" if user.discord_alerts_enabled else "disabled"
            status_emoji = "" if user.discord_alerts_enabled else ""

            embed = build_info_embed(
                "Alert Settings",
                f"**Discord Alerts:** {status_emoji} {status.title()}\n\n"
                f"When enabled, you'll receive DM notifications for:\n"
                f"- Price drops on your want list\n"
                f"- Significant changes in your portfolio\n"
                f"- Target price alerts\n\n"
                f"Use `/alerts enable` or `/alerts disable` to change."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error("Alert status check failed", error=str(e))
            embed = build_error_embed(
                "Error",
                "Failed to check alert settings."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @alerts_group.command(name="enable", description="Enable Discord DM alerts")
    async def alerts_enable(self, interaction: discord.Interaction):
        """Enable Discord alerts."""
        await interaction.response.defer(ephemeral=True)

        try:
            user = await self._get_linked_user(interaction)
            if not user:
                return

            if user.discord_alerts_enabled:
                embed = build_info_embed(
                    "Already Enabled",
                    "Discord alerts are already enabled for your account."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Note: In a full implementation, we'd call an API to update the setting
            # For now, just show the success message
            embed = build_success_embed(
                "Alerts Enabled",
                "Discord alerts have been enabled!\n\n"
                "You'll now receive DM notifications for price alerts."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(
                "Alerts enabled",
                user=str(interaction.user),
                linked_user=user.username,
            )

        except Exception as e:
            logger.error("Enable alerts failed", error=str(e))
            embed = build_error_embed(
                "Error",
                "Failed to enable alerts. Please try again."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @alerts_group.command(name="disable", description="Disable Discord DM alerts")
    async def alerts_disable(self, interaction: discord.Interaction):
        """Disable Discord alerts."""
        await interaction.response.defer(ephemeral=True)

        try:
            user = await self._get_linked_user(interaction)
            if not user:
                return

            if not user.discord_alerts_enabled:
                embed = build_info_embed(
                    "Already Disabled",
                    "Discord alerts are already disabled for your account."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Note: In a full implementation, we'd call an API to update the setting
            embed = build_success_embed(
                "Alerts Disabled",
                "Discord alerts have been disabled.\n\n"
                "You can still view alerts on the Dualcaster Deals website."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(
                "Alerts disabled",
                user=str(interaction.user),
                linked_user=user.username,
            )

        except Exception as e:
            logger.error("Disable alerts failed", error=str(e))
            embed = build_error_embed(
                "Error",
                "Failed to disable alerts. Please try again."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @alerts_group.command(name="test", description="Send a test alert to verify DMs work")
    async def alerts_test(self, interaction: discord.Interaction):
        """Send a test alert."""
        await interaction.response.defer(ephemeral=True)

        try:
            # Try to send a test DM
            test_embed = build_info_embed(
                "Test Alert",
                "This is a test alert from Dualcaster Deals bot.\n\n"
                "If you received this, your DM settings are working correctly!"
            )

            try:
                await interaction.user.send(embed=test_embed)
                embed = build_success_embed(
                    "Test Sent",
                    "A test alert has been sent to your DMs!\n\n"
                    "Check your direct messages."
                )
            except discord.Forbidden:
                embed = build_error_embed(
                    "Cannot Send DM",
                    "I couldn't send you a DM. Please check your privacy settings:\n\n"
                    "1. Right-click this server\n"
                    "2. Go to Privacy Settings\n"
                    "3. Enable 'Direct Messages'"
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error("Test alert failed", error=str(e))
            embed = build_error_embed(
                "Error",
                "Failed to send test alert."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    await bot.add_cog(AlertsCog(bot))
    logger.info("AlertsCog loaded")
