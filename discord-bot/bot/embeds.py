"""Discord embed builders for various response types."""
from decimal import Decimal
from typing import Optional

import discord

from .api_client import (
    CardPrice,
    Portfolio,
    PortfolioCard,
    WantList,
    WantListItem,
    MarketMover,
    PendingAlert,
)

# Color constants (MTG mana colors)
COLOR_WHITE = 0xF8F6D8
COLOR_BLUE = 0x0E68AB
COLOR_BLACK = 0x150B00
COLOR_RED = 0xD3202A
COLOR_GREEN = 0x00733E
COLOR_GOLD = 0xFFD700  # Multi-color / default
COLOR_SUCCESS = 0x2ECC71
COLOR_ERROR = 0xE74C3C
COLOR_WARNING = 0xF39C12
COLOR_INFO = 0x3498DB


def format_price(price: Optional[Decimal]) -> str:
    """Format a price for display."""
    if price is None:
        return "N/A"
    return f"${price:,.2f}"


def format_change(change_pct: Optional[float]) -> str:
    """Format a percentage change with emoji."""
    if change_pct is None:
        return ""
    emoji = "" if change_pct >= 0 else ""
    return f"{emoji} {change_pct:+.1f}%"


def build_card_embed(card: CardPrice) -> discord.Embed:
    """Build an embed for a card price lookup."""
    embed = discord.Embed(
        title=card.name,
        url=card.scryfall_uri,
        color=COLOR_GOLD,
    )

    # Set thumbnail if image available
    if card.image_uri:
        embed.set_thumbnail(url=card.image_uri)

    # Set info
    embed.add_field(name="Set", value=f"{card.set_name} ({card.set_code.upper()})", inline=True)

    # Prices
    price_text = format_price(card.price_usd)
    if card.price_usd_foil:
        price_text += f"\nFoil: {format_price(card.price_usd_foil)}"
    embed.add_field(name="Price", value=price_text, inline=True)

    # 24h change
    if card.change_24h_pct is not None:
        embed.add_field(name="24h Change", value=format_change(card.change_24h_pct), inline=True)

    embed.set_footer(text="Data from Dualcaster Deals")

    return embed


def build_card_list_embed(cards: list[CardPrice], query: str) -> discord.Embed:
    """Build an embed for a list of card search results."""
    embed = discord.Embed(
        title=f"Search Results: {query}",
        color=COLOR_INFO,
    )

    if not cards:
        embed.description = "No cards found matching your search."
        return embed

    for card in cards[:10]:  # Limit to 10 results
        price_info = format_price(card.price_usd)
        if card.change_24h_pct is not None:
            price_info += f" ({format_change(card.change_24h_pct)})"

        embed.add_field(
            name=f"{card.name} [{card.set_code.upper()}]",
            value=price_info,
            inline=True,
        )

    if len(cards) > 10:
        embed.set_footer(text=f"Showing 10 of {len(cards)} results")

    return embed


def build_portfolio_embed(portfolio: Portfolio, username: str) -> discord.Embed:
    """Build an embed for a portfolio summary."""
    embed = discord.Embed(
        title=f"{username}'s Portfolio",
        color=COLOR_SUCCESS,
    )

    # Overview
    embed.add_field(
        name="Total Value",
        value=format_price(portfolio.total_value),
        inline=True,
    )
    embed.add_field(
        name="Cards",
        value=f"{portfolio.total_cards:,} ({portfolio.unique_cards:,} unique)",
        inline=True,
    )

    if portfolio.change_24h is not None:
        change_text = format_price(portfolio.change_24h)
        if portfolio.change_24h_pct is not None:
            change_text += f" ({format_change(portfolio.change_24h_pct)})"
        embed.add_field(name="24h Change", value=change_text, inline=True)

    # Top cards
    if portfolio.top_cards:
        top_cards_text = "\n".join(
            f"**{c.name}** [{c.set_code.upper()}] x{c.quantity} - {format_price(c.total_value)}"
            for c in portfolio.top_cards[:5]
        )
        embed.add_field(name="Top Holdings", value=top_cards_text, inline=False)

    embed.set_footer(text="View full portfolio on Dualcaster Deals")

    return embed


def build_wantlist_embed(wantlist: WantList, username: str) -> discord.Embed:
    """Build an embed for a want list summary."""
    embed = discord.Embed(
        title=f"{username}'s Want List",
        color=COLOR_BLUE,
    )

    # Overview
    embed.add_field(name="Total Items", value=str(wantlist.total_items), inline=True)
    embed.add_field(name="With Alerts", value=str(wantlist.items_with_alerts), inline=True)
    embed.add_field(name="Alerts Triggered", value=str(wantlist.alerts_triggered), inline=True)

    # Items
    if wantlist.items:
        items_text = []
        for item in wantlist.items[:10]:
            line = f"**{item.name}** [{item.set_code.upper()}]"
            if item.current_price:
                line += f" - {format_price(item.current_price)}"
            if item.target_price:
                line += f" (target: {format_price(item.target_price)})"
            if item.alert_triggered:
                line += " :bell:"
            items_text.append(line)

        embed.add_field(name="Items", value="\n".join(items_text), inline=False)

    if wantlist.total_items > 10:
        embed.set_footer(text=f"Showing 10 of {wantlist.total_items} items")

    return embed


def build_movers_embed(movers: list[MarketMover], direction: str) -> discord.Embed:
    """Build an embed for top gainers/losers."""
    title = "Top Gainers" if direction == "up" else "Top Losers"
    color = COLOR_SUCCESS if direction == "up" else COLOR_ERROR
    emoji = "" if direction == "up" else ""

    embed = discord.Embed(
        title=f"{emoji} {title}",
        color=color,
    )

    if not movers:
        embed.description = "No significant movers found."
        return embed

    for i, mover in enumerate(movers[:10], 1):
        value = f"{format_price(mover.price)} ({format_change(mover.change_pct)})"
        embed.add_field(
            name=f"{i}. {mover.name} [{mover.set_code.upper()}]",
            value=value,
            inline=False,
        )

    embed.set_footer(text="24-hour price movement")

    return embed


def build_alert_embed(alert: PendingAlert) -> discord.Embed:
    """Build an embed for a price alert notification."""
    # Choose color based on alert type
    color_map = {
        "price_drop": COLOR_SUCCESS,
        "price_spike": COLOR_WARNING,
        "target_reached": COLOR_GOLD,
        "daily_summary": COLOR_INFO,
    }
    color = color_map.get(alert.alert_type, COLOR_INFO)

    embed = discord.Embed(
        title=alert.title,
        description=alert.message,
        color=color,
        timestamp=alert.created_at,
    )

    if alert.card_name:
        embed.add_field(name="Card", value=alert.card_name, inline=True)

    if alert.current_price:
        embed.add_field(name="Current Price", value=format_price(alert.current_price), inline=True)

    embed.set_footer(text="Dualcaster Deals Alert")

    return embed


def build_error_embed(title: str, message: str) -> discord.Embed:
    """Build an error embed."""
    return discord.Embed(
        title=f"Error: {title}",
        description=message,
        color=COLOR_ERROR,
    )


def build_success_embed(title: str, message: str) -> discord.Embed:
    """Build a success embed."""
    return discord.Embed(
        title=title,
        description=message,
        color=COLOR_SUCCESS,
    )


def build_info_embed(title: str, message: str) -> discord.Embed:
    """Build an info embed."""
    return discord.Embed(
        title=title,
        description=message,
        color=COLOR_INFO,
    )


def build_help_embed() -> discord.Embed:
    """Build the help command embed."""
    embed = discord.Embed(
        title="Dualcaster Deals Bot",
        description="MTG market intelligence at your fingertips!",
        color=COLOR_GOLD,
    )

    embed.add_field(
        name="Price Commands",
        value=(
            "`/price <card>` - Look up card prices\n"
            "`/gainers` - Top gaining cards\n"
            "`/losers` - Top losing cards"
        ),
        inline=False,
    )

    embed.add_field(
        name="Portfolio Commands",
        value=(
            "`/portfolio` - View your portfolio summary\n"
            "`/wantlist` - View your want list"
        ),
        inline=False,
    )

    embed.add_field(
        name="Alert Commands",
        value=(
            "`/alerts` - Manage your price alerts\n"
            "`/alerts enable` - Enable Discord alerts\n"
            "`/alerts disable` - Disable Discord alerts"
        ),
        inline=False,
    )

    embed.add_field(
        name="Account Commands",
        value=(
            "`/link` - Link your Discord account\n"
            "`/unlink` - Unlink your account\n"
            "`/help` - Show this help message"
        ),
        inline=False,
    )

    embed.set_footer(text="Visit dualcasterdeals.com for full features")

    return embed
