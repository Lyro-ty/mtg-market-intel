"""Price commands cog - card price lookups."""
import discord
from discord import app_commands
from discord.ext import commands
import structlog

from ..embeds import build_card_embed, build_card_list_embed, build_error_embed

logger = structlog.get_logger(__name__)


class PriceCog(commands.Cog):
    """Card price lookup commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="price", description="Look up card prices")
    @app_commands.describe(card="Card name to search for")
    async def price_command(self, interaction: discord.Interaction, card: str):
        """Look up prices for a card."""
        await interaction.response.defer()

        try:
            cards = await self.bot.api.search_cards(card, limit=5)

            if not cards:
                embed = build_error_embed(
                    "Card Not Found",
                    f"No cards found matching '{card}'.\n\n"
                    f"Try a more specific search or check your spelling."
                )
                await interaction.followup.send(embed=embed)
                return

            if len(cards) == 1:
                # Single result - show detailed view
                embed = build_card_embed(cards[0])
            else:
                # Multiple results - show list
                embed = build_card_list_embed(cards, card)

            await interaction.followup.send(embed=embed)

            logger.info(
                "Price lookup",
                user=str(interaction.user),
                query=card,
                results=len(cards),
            )

        except Exception as e:
            logger.error("Price lookup failed", query=card, error=str(e))
            embed = build_error_embed(
                "Lookup Failed",
                "Failed to fetch card prices. Please try again later."
            )
            await interaction.followup.send(embed=embed)

    @price_command.autocomplete("card")
    async def price_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for card names."""
        if len(current) < 2:
            return []

        try:
            cards = await self.bot.api.search_cards(current, limit=10)
            return [
                app_commands.Choice(
                    name=f"{c.name} [{c.set_code.upper()}]"[:100],
                    value=c.name[:100],
                )
                for c in cards
            ]
        except Exception as e:
            logger.error("Autocomplete failed", query=current, error=str(e))
            return []

    @app_commands.command(name="p", description="Quick price lookup (alias for /price)")
    @app_commands.describe(card="Card name to search for")
    async def price_alias(self, interaction: discord.Interaction, card: str):
        """Alias for /price command."""
        await self.price_command.callback(self, interaction, card)

    @price_alias.autocomplete("card")
    async def p_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for the alias command."""
        return await self.price_autocomplete(interaction, current)


async def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    await bot.add_cog(PriceCog(bot))
    logger.info("PriceCog loaded")
