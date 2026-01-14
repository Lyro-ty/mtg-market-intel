"""Development and monitoring commands cog."""
import discord
from discord import app_commands
from discord.ext import commands
import structlog
from datetime import datetime

from ..embeds import build_info_embed, build_success_embed, build_error_embed

logger = structlog.get_logger(__name__)


class DevCog(commands.Cog):
    """Development commands for monitoring system status."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="status", description="Check Dualcaster Deals system status")
    async def status_command(self, interaction: discord.Interaction):
        """Display system health status."""
        await interaction.response.defer()

        try:
            health = await self.bot.api.get_health()

            # Build status embed
            embed = discord.Embed(
                title="System Status",
                description="Current health of Dualcaster Deals services",
                color=discord.Color.green() if health.get("status") == "healthy" else discord.Color.orange()
            )

            # Overall status
            status_emoji = "" if health.get("status") == "healthy" else ""
            embed.add_field(
                name="Overall Status",
                value=f"{status_emoji} {health.get('status', 'unknown').upper()}",
                inline=False
            )

            # Service checks
            services = health.get("services", {})
            for service, status in services.items():
                emoji = "" if status == "ok" else ""
                embed.add_field(
                    name=service.replace("_", " ").title(),
                    value=f"{emoji} {status}",
                    inline=True
                )

            # Data freshness
            if "last_price_update" in health:
                embed.add_field(
                    name="Last Price Update",
                    value=health["last_price_update"],
                    inline=True
                )

            embed.set_footer(text=f"Checked at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error("status_command_failed", error=str(e))
            embed = build_error_embed(
                "Status Check Failed",
                f"Could not retrieve system status: {str(e)}"
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping_command(self, interaction: discord.Interaction):
        """Display bot latency."""
        latency = round(self.bot.latency * 1000)

        if latency < 100:
            color = discord.Color.green()
            status = "Excellent"
        elif latency < 200:
            color = discord.Color.yellow()
            status = "Good"
        else:
            color = discord.Color.red()
            status = "High latency"

        embed = discord.Embed(
            title="Pong!",
            description=f"**Latency:** {latency}ms\n**Status:** {status}",
            color=color
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stats", description="Show bot statistics")
    async def stats_command(self, interaction: discord.Interaction):
        """Display bot statistics."""
        await interaction.response.defer()

        try:
            # Get bot stats
            guild_count = len(self.bot.guilds)
            user_count = sum(g.member_count or 0 for g in self.bot.guilds)

            # Get system stats from API
            stats = await self.bot.api.get_stats()

            embed = discord.Embed(
                title="Bot Statistics",
                color=discord.Color.gold()
            )

            # Bot stats
            embed.add_field(
                name="Bot",
                value=f"**Servers:** {guild_count}\n**Users:** {user_count}",
                inline=True
            )

            # Database stats
            if stats:
                embed.add_field(
                    name="Database",
                    value=f"**Cards:** {stats.get('cards', 'N/A'):,}\n"
                          f"**Prices:** {stats.get('prices', 'N/A'):,}\n"
                          f"**Users:** {stats.get('users', 'N/A'):,}",
                    inline=True
                )

                embed.add_field(
                    name="Analytics",
                    value=f"**Signals:** {stats.get('signals', 'N/A'):,}\n"
                          f"**Recommendations:** {stats.get('recommendations', 'N/A'):,}",
                    inline=True
                )

            embed.set_footer(text="Dualcaster Deals")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error("stats_command_failed", error=str(e))
            embed = build_error_embed(
                "Stats Failed",
                f"Could not retrieve statistics: {str(e)}"
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="uptime", description="Show bot uptime")
    async def uptime_command(self, interaction: discord.Interaction):
        """Display bot uptime."""
        if hasattr(self.bot, 'start_time'):
            uptime = datetime.utcnow() - self.bot.start_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            uptime_str = ""
            if days > 0:
                uptime_str += f"{days}d "
            uptime_str += f"{hours}h {minutes}m {seconds}s"

            embed = discord.Embed(
                title="Bot Uptime",
                description=f"**Uptime:** {uptime_str}\n**Started:** {self.bot.start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="Bot Uptime",
                description="Uptime tracking not available",
                color=discord.Color.gray()
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Register cog with bot."""
    await bot.add_cog(DevCog(bot))
