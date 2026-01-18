"""
Trade proposal service for managing user-to-user trades.

Handles:
- Creating and updating trade proposals
- Counter-proposals
- Completion confirmation
- Integration with reputation system
"""
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from app.models.trade import (
    TradeProposal,
    TradeProposalItem,
    TradeStatus,
    TradeSide,
)
from app.models.card import Card
from app.models.metrics import MetricsCardsDaily
from app.services.reputation import ReputationService

logger = get_logger()


class TradeService:
    """Service for managing trade proposals."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_proposal(
        self,
        proposer_id: int,
        recipient_id: int,
        proposer_items: list[dict],
        recipient_items: list[dict],
        message: str | None = None,
        expires_days: int = 7,
    ) -> TradeProposal:
        """
        Create a new trade proposal.

        Args:
            proposer_id: ID of user making the proposal
            recipient_id: ID of user receiving the proposal
            proposer_items: Items offered by proposer [{card_id, quantity, condition}]
            recipient_items: Items requested from recipient [{card_id, quantity, condition}]
            message: Optional message
            expires_days: Days until proposal expires

        Returns:
            The created proposal
        """
        if proposer_id == recipient_id:
            raise ValueError("Cannot create a trade with yourself")

        proposal = TradeProposal(
            proposer_id=proposer_id,
            recipient_id=recipient_id,
            status=TradeStatus.PENDING,
            message=message,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=expires_days),
        )
        self.db.add(proposal)
        await self.db.flush()

        # Add items
        await self._add_items(proposal.id, proposer_items, TradeSide.PROPOSER)
        await self._add_items(proposal.id, recipient_items, TradeSide.RECIPIENT)

        logger.info(
            "trade_proposal_created",
            proposal_id=proposal.id,
            proposer_id=proposer_id,
            recipient_id=recipient_id,
        )

        return proposal

    async def _add_items(
        self,
        proposal_id: int,
        items: list[dict],
        side: TradeSide,
    ) -> None:
        """Add items to a proposal."""
        for item_data in items:
            card_id = item_data["card_id"]

            # Get latest price from metrics
            price = await self._get_latest_price(card_id)

            item = TradeProposalItem(
                proposal_id=proposal_id,
                side=side,
                card_id=card_id,
                quantity=item_data.get("quantity", 1),
                condition=item_data.get("condition"),
                price_at_proposal=price,
            )
            self.db.add(item)

    async def _get_latest_price(self, card_id: int) -> float | None:
        """Get the latest average price for a card from daily metrics."""
        query = (
            select(MetricsCardsDaily.avg_price)
            .where(MetricsCardsDaily.card_id == card_id)
            .order_by(MetricsCardsDaily.date.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        price = result.scalar_one_or_none()
        return float(price) if price is not None else None

    async def get_proposal(self, proposal_id: int) -> TradeProposal | None:
        """Get a proposal by ID with all related data."""
        query = (
            select(TradeProposal)
            .options(selectinload(TradeProposal.items).selectinload(TradeProposalItem.card))
            .where(TradeProposal.id == proposal_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_proposals(
        self,
        user_id: int,
        status: TradeStatus | None = None,
        direction: str = "all",  # "sent", "received", "all"
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[TradeProposal], int]:
        """
        Get proposals for a user.

        Args:
            user_id: User ID
            status: Filter by status
            direction: "sent", "received", or "all"
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (proposals, total_count)
        """
        # Build base condition
        if direction == "sent":
            condition = TradeProposal.proposer_id == user_id
        elif direction == "received":
            condition = TradeProposal.recipient_id == user_id
        else:
            condition = or_(
                TradeProposal.proposer_id == user_id,
                TradeProposal.recipient_id == user_id,
            )

        # Add status filter
        if status:
            condition = and_(condition, TradeProposal.status == status)

        # Count
        count_query = select(func.count()).where(condition).select_from(TradeProposal)
        result = await self.db.execute(count_query)
        total = result.scalar() or 0

        # Get proposals
        query = (
            select(TradeProposal)
            .options(selectinload(TradeProposal.items).selectinload(TradeProposalItem.card))
            .where(condition)
            .order_by(TradeProposal.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        proposals = list(result.scalars().all())

        return proposals, total

    async def accept_proposal(
        self,
        proposal_id: int,
        user_id: int,
    ) -> TradeProposal:
        """Accept a trade proposal."""
        proposal = await self.get_proposal(proposal_id)

        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.recipient_id != user_id:
            raise ValueError("Only the recipient can accept a proposal")

        if proposal.status != TradeStatus.PENDING:
            raise ValueError(f"Cannot accept a {proposal.status} proposal")

        if proposal.is_expired:
            proposal.status = TradeStatus.EXPIRED
            raise ValueError("Proposal has expired")

        proposal.status = TradeStatus.ACCEPTED
        proposal.updated_at = datetime.utcnow()

        logger.info(
            "trade_proposal_accepted",
            proposal_id=proposal_id,
            recipient_id=user_id,
        )

        return proposal

    async def decline_proposal(
        self,
        proposal_id: int,
        user_id: int,
    ) -> TradeProposal:
        """Decline a trade proposal."""
        proposal = await self.get_proposal(proposal_id)

        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.recipient_id != user_id:
            raise ValueError("Only the recipient can decline a proposal")

        if proposal.status != TradeStatus.PENDING:
            raise ValueError(f"Cannot decline a {proposal.status} proposal")

        proposal.status = TradeStatus.DECLINED
        proposal.updated_at = datetime.utcnow()

        logger.info(
            "trade_proposal_declined",
            proposal_id=proposal_id,
            recipient_id=user_id,
        )

        return proposal

    async def cancel_proposal(
        self,
        proposal_id: int,
        user_id: int,
    ) -> TradeProposal:
        """Cancel a trade proposal (by proposer)."""
        proposal = await self.get_proposal(proposal_id)

        if not proposal:
            raise ValueError("Proposal not found")

        if proposal.proposer_id != user_id:
            raise ValueError("Only the proposer can cancel a proposal")

        if proposal.status not in (TradeStatus.PENDING, TradeStatus.COUNTERED):
            raise ValueError(f"Cannot cancel a {proposal.status} proposal")

        proposal.status = TradeStatus.CANCELLED
        proposal.updated_at = datetime.utcnow()

        logger.info(
            "trade_proposal_cancelled",
            proposal_id=proposal_id,
            proposer_id=user_id,
        )

        return proposal

    async def counter_proposal(
        self,
        original_proposal_id: int,
        user_id: int,
        proposer_items: list[dict],
        recipient_items: list[dict],
        message: str | None = None,
    ) -> TradeProposal:
        """
        Create a counter-proposal.

        This creates a new proposal with the roles swapped
        and links to the original.
        """
        original = await self.get_proposal(original_proposal_id)

        if not original:
            raise ValueError("Original proposal not found")

        if original.recipient_id != user_id:
            raise ValueError("Only the recipient can counter a proposal")

        if original.status != TradeStatus.PENDING:
            raise ValueError(f"Cannot counter a {original.status} proposal")

        # Mark original as countered
        original.status = TradeStatus.COUNTERED
        original.updated_at = datetime.utcnow()

        # Create counter proposal (roles swapped)
        counter = await self.create_proposal(
            proposer_id=original.recipient_id,
            recipient_id=original.proposer_id,
            proposer_items=proposer_items,
            recipient_items=recipient_items,
            message=message,
        )
        counter.parent_proposal_id = original_proposal_id

        logger.info(
            "trade_counter_proposal_created",
            original_id=original_proposal_id,
            counter_id=counter.id,
        )

        return counter

    async def confirm_completion(
        self,
        proposal_id: int,
        user_id: int,
    ) -> TradeProposal:
        """
        Confirm trade completion (by one party).

        Both parties must confirm for the trade to be marked complete.
        """
        proposal = await self.get_proposal(proposal_id)

        if not proposal:
            raise ValueError("Proposal not found")

        if user_id not in (proposal.proposer_id, proposal.recipient_id):
            raise ValueError("You are not part of this trade")

        if proposal.status != TradeStatus.ACCEPTED:
            raise ValueError(f"Cannot confirm a {proposal.status} proposal")

        now = datetime.utcnow()

        if user_id == proposal.proposer_id:
            proposal.proposer_confirmed_at = now
        else:
            proposal.recipient_confirmed_at = now

        # Check if both confirmed
        if proposal.proposer_confirmed_at and proposal.recipient_confirmed_at:
            proposal.status = TradeStatus.COMPLETED
            proposal.completed_at = now

            logger.info(
                "trade_completed",
                proposal_id=proposal_id,
            )

        proposal.updated_at = now
        return proposal

    async def expire_old_proposals(self) -> int:
        """Mark expired proposals as expired. Returns count of updated proposals."""
        query = (
            select(TradeProposal)
            .where(
                TradeProposal.status == TradeStatus.PENDING,
                TradeProposal.expires_at < datetime.utcnow(),
            )
        )
        result = await self.db.execute(query)
        proposals = list(result.scalars().all())

        for proposal in proposals:
            proposal.status = TradeStatus.EXPIRED
            proposal.updated_at = datetime.utcnow()

        return len(proposals)

    async def get_statistics(self, user_id: int) -> dict[str, Any]:
        """Get trade statistics for a user."""
        # Count by status
        sent_query = select(
            TradeProposal.status,
            func.count().label("count")
        ).where(
            TradeProposal.proposer_id == user_id
        ).group_by(TradeProposal.status)
        result = await self.db.execute(sent_query)
        sent_counts = {row.status: row.count for row in result.all()}

        received_query = select(
            TradeProposal.status,
            func.count().label("count")
        ).where(
            TradeProposal.recipient_id == user_id
        ).group_by(TradeProposal.status)
        result = await self.db.execute(received_query)
        received_counts = {row.status: row.count for row in result.all()}

        # Completed trades
        completed_query = select(func.count()).where(
            TradeProposal.status == TradeStatus.COMPLETED,
            or_(
                TradeProposal.proposer_id == user_id,
                TradeProposal.recipient_id == user_id,
            )
        )
        result = await self.db.execute(completed_query)
        completed = result.scalar() or 0

        return {
            "sent": sent_counts,
            "received": received_counts,
            "completed_total": completed,
        }
