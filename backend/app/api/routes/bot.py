"""
Bot API routes for Discord bot integration.

These endpoints are authenticated via X-Bot-Token header and are used
by the Discord bot to fetch user data and deliver alerts.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import BotAuth, get_db
from app.api.utils.validation import validate_id_list
from app.models.user import User
from app.models.inventory import InventoryItem
from app.models.want_list import WantListItem
from app.models.card import Card
from app.models.discord_alert import DiscordAlertQueue
from app.schemas.bot import (
    BotUserResponse,
    PortfolioSummary,
    PortfolioCard,
    WantListSummary,
    WantListItemBrief,
    UserTradeList,
    TradeItem,
    TraderMatch,
    PendingAlert,
    AlertDeliveryConfirm,
)

router = APIRouter(prefix="/bot", tags=["bot"])
logger = structlog.get_logger(__name__)


@router.get("/users/by-discord/{discord_id}", response_model=BotUserResponse)
async def get_user_by_discord_id(
    discord_id: str,
    _: BotAuth,
    db: AsyncSession = Depends(get_db),
):
    """
    Look up a user by their Discord ID.

    Used by the bot to identify users when they run commands.
    """
    result = await db.execute(
        select(User).where(User.discord_id == discord_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return BotUserResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        discord_alerts_enabled=user.discord_alerts_enabled,
    )


@router.get("/users/{user_id}/portfolio", response_model=PortfolioSummary)
async def get_user_portfolio(
    user_id: int,
    _: BotAuth,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a user's portfolio summary for bot display.

    Returns total value, card count, and top 5 cards by value.
    """
    # Verify user exists
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get inventory items with cards
    result = await db.execute(
        select(InventoryItem)
        .where(InventoryItem.user_id == user_id)
        .options(selectinload(InventoryItem.card))
    )
    items = result.scalars().all()

    if not items:
        return PortfolioSummary(
            total_value=Decimal("0"),
            total_cards=0,
            unique_cards=0,
            top_cards=[],
        )

    # Calculate totals
    total_value = Decimal("0")
    total_cards = 0
    unique_cards = len(items)
    card_values = []

    for item in items:
        card = item.card
        if card and card.price_usd:
            item_value = card.price_usd * item.quantity
            total_value += item_value
            total_cards += item.quantity
            card_values.append((item, card, item_value))

    # Sort by value and get top 5
    card_values.sort(key=lambda x: x[2], reverse=True)
    top_cards = []
    for item, card, value in card_values[:5]:
        top_cards.append(PortfolioCard(
            card_id=card.id,
            name=card.name,
            set_code=card.set_code or "",
            quantity=item.quantity,
            current_price=card.price_usd or Decimal("0"),
            total_value=value,
        ))

    return PortfolioSummary(
        total_value=total_value,
        total_cards=total_cards,
        unique_cards=unique_cards,
        top_cards=top_cards,
    )


@router.get("/users/{user_id}/wantlist", response_model=WantListSummary)
async def get_user_wantlist(
    user_id: int,
    _: BotAuth,
    limit: int = Query(default=10, le=25),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a user's want list summary for bot display.
    """
    # Verify user exists
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get want list items with cards
    result = await db.execute(
        select(WantListItem)
        .where(WantListItem.user_id == user_id)
        .options(selectinload(WantListItem.card))
        .limit(limit)
    )
    items = result.scalars().all()

    # Count totals
    count_result = await db.execute(
        select(func.count(WantListItem.id))
        .where(WantListItem.user_id == user_id)
    )
    total_items = count_result.scalar() or 0

    alerts_with_target = 0
    alerts_triggered = 0
    item_briefs = []

    for item in items:
        card = item.card
        current_price = card.price_usd if card else None
        target_price = item.target_price if hasattr(item, 'target_price') else None

        # Check if alert triggered
        triggered = False
        if target_price and current_price and current_price <= target_price:
            triggered = True
            alerts_triggered += 1

        if target_price:
            alerts_with_target += 1

        item_briefs.append(WantListItemBrief(
            card_id=item.card_id,
            name=card.name if card else "Unknown",
            set_code=card.set_code if card else "",
            target_price=target_price,
            current_price=current_price,
            alert_triggered=triggered,
        ))

    return WantListSummary(
        total_items=total_items,
        items_with_alerts=alerts_with_target,
        alerts_triggered=alerts_triggered,
        items=item_briefs,
    )


@router.get("/users/{user_id}/trades", response_model=UserTradeList)
async def get_user_trades(
    user_id: int,
    _: BotAuth,
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a user's cards available for trade.
    """
    # Verify user exists
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get items marked for trade
    result = await db.execute(
        select(InventoryItem)
        .where(
            InventoryItem.user_id == user_id,
            InventoryItem.for_trade == True,  # noqa: E712
        )
        .options(selectinload(InventoryItem.card))
        .limit(limit)
    )
    items = result.scalars().all()

    trade_items = []
    for item in items:
        card = item.card
        if card:
            trade_items.append(TradeItem(
                card_id=card.id,
                name=card.name,
                set_code=card.set_code or "",
                quantity=item.quantity,
                condition=item.condition or "NM",
                is_foil=item.is_foil or False,
                current_price=card.price_usd,
            ))

    return UserTradeList(
        user_id=user.id,
        username=user.username,
        discord_username=user.discord_username,
        total_for_trade=len(trade_items),
        items=trade_items,
    )


@router.get("/discovery/matches/{user_id}", response_model=list[TraderMatch])
async def find_trade_matches(
    user_id: int,
    _: BotAuth,
    limit: int = Query(default=10, le=25),
    db: AsyncSession = Depends(get_db),
):
    """
    Find potential trade matches for a user.

    Returns users who have cards the user wants AND want cards the user has.
    """
    # Get user's want list card IDs
    want_result = await db.execute(
        select(WantListItem.card_id)
        .where(WantListItem.user_id == user_id)
    )
    wanted_card_ids = set(want_result.scalars().all())

    if not wanted_card_ids:
        return []

    # Get user's trade list card IDs
    trade_result = await db.execute(
        select(InventoryItem.card_id)
        .where(
            InventoryItem.user_id == user_id,
            InventoryItem.for_trade == True,  # noqa: E712
        )
    )
    trading_card_ids = set(trade_result.scalars().all())

    # Find users who have cards we want (and are trading them)
    potential_matches_result = await db.execute(
        select(InventoryItem.user_id, InventoryItem.card_id)
        .where(
            InventoryItem.card_id.in_(wanted_card_ids),
            InventoryItem.for_trade == True,  # noqa: E712
            InventoryItem.user_id != user_id,
        )
    )
    users_with_our_wants = {}
    for other_user_id, card_id in potential_matches_result.all():
        if other_user_id not in users_with_our_wants:
            users_with_our_wants[other_user_id] = set()
        users_with_our_wants[other_user_id].add(card_id)

    if not users_with_our_wants:
        return []

    # For each potential match, check if they want any of our trade cards
    matches = []
    for other_user_id, their_cards in users_with_our_wants.items():
        # Check their want list against our trade list
        their_wants_result = await db.execute(
            select(WantListItem.card_id)
            .where(
                WantListItem.user_id == other_user_id,
                WantListItem.card_id.in_(trading_card_ids),
            )
        )
        their_wants = set(their_wants_result.scalars().all())

        if their_wants:
            # Mutual match found!
            matches.append({
                "user_id": other_user_id,
                "has_cards": their_cards,
                "wants_cards": their_wants,
                "score": len(their_cards) + len(their_wants),
            })

    # Sort by match score and limit
    matches.sort(key=lambda x: x["score"], reverse=True)
    matches = matches[:limit]

    # Fetch user details and card names
    result_matches = []
    for match in matches:
        user_result = await db.execute(
            select(User).where(User.id == match["user_id"])
        )
        other_user = user_result.scalar_one_or_none()
        if not other_user:
            continue

        # Get card names
        has_cards_result = await db.execute(
            select(Card.name).where(Card.id.in_(match["has_cards"]))
        )
        has_card_names = list(has_cards_result.scalars().all())

        wants_cards_result = await db.execute(
            select(Card.name).where(Card.id.in_(match["wants_cards"]))
        )
        wants_card_names = list(wants_cards_result.scalars().all())

        result_matches.append(TraderMatch(
            user_id=other_user.id,
            username=other_user.username,
            discord_id=other_user.discord_id,
            discord_username=other_user.discord_username,
            has_cards=has_card_names,
            wants_cards=wants_card_names,
            match_score=match["score"],
        ))

    return result_matches


# =============================================================================
# Alert Queue Endpoints
# =============================================================================

@router.get("/alerts/pending", response_model=List[PendingAlert])
async def get_pending_alerts(
    _: BotAuth,
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get pending Discord alerts for delivery.

    Returns undelivered alerts ordered by creation time.
    The bot should call this periodically to fetch new alerts.
    """
    result = await db.execute(
        select(DiscordAlertQueue)
        .where(DiscordAlertQueue.delivered == False)  # noqa: E712
        .options(selectinload(DiscordAlertQueue.user))
        .options(selectinload(DiscordAlertQueue.card))
        .order_by(DiscordAlertQueue.created_at.asc())
        .limit(limit)
    )
    alerts = result.scalars().all()

    pending = []
    for alert in alerts:
        # Only include alerts for users with Discord linked
        if not alert.user or not alert.user.discord_id:
            continue

        # Skip if user has disabled Discord alerts
        if not alert.user.discord_alerts_enabled:
            continue

        pending.append(PendingAlert(
            alert_id=alert.id,
            user_id=alert.user_id,
            discord_id=alert.user.discord_id,
            alert_type=alert.alert_type,
            title=alert.title,
            message=alert.message,
            card_id=alert.card_id,
            card_name=alert.card.name if alert.card else None,
            current_price=alert.card.price_usd if alert.card else None,
            created_at=alert.created_at,
        ))

    logger.info("Fetched pending alerts", count=len(pending))
    return pending


@router.post("/alerts/delivered")
async def mark_alerts_delivered(
    payload: AlertDeliveryConfirm,
    _: BotAuth,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark alerts as successfully delivered.

    Called by the bot after sending alerts to Discord.
    """
    if not payload.alert_ids:
        return {"marked": 0}

    # Validate ID list size to prevent DoS via large payloads
    validate_id_list(payload.alert_ids, "alert_ids")

    now = datetime.now(timezone.utc)

    # Update all specified alerts
    result = await db.execute(
        select(DiscordAlertQueue)
        .where(DiscordAlertQueue.id.in_(payload.alert_ids))
    )
    alerts = result.scalars().all()

    marked_count = 0
    for alert in alerts:
        if not alert.delivered:
            alert.delivered = True
            alert.delivered_at = now
            marked_count += 1

    await db.commit()

    logger.info("Marked alerts as delivered", count=marked_count, alert_ids=payload.alert_ids)
    return {"marked": marked_count}


@router.post("/alerts/{alert_id}/failed")
async def mark_alert_failed(
    alert_id: int,
    error: str = Query(None),
    _: BotAuth = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark an alert as failed to deliver.

    Increments the attempt counter and stores the error message.
    """
    alert = await db.get(DiscordAlertQueue, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.delivery_attempts += 1
    alert.last_attempt_at = datetime.now(timezone.utc)
    alert.error_message = error

    await db.commit()

    logger.warning(
        "Alert delivery failed",
        alert_id=alert_id,
        attempts=alert.delivery_attempts,
        error=error,
    )
    return {"alert_id": alert_id, "attempts": alert.delivery_attempts}
