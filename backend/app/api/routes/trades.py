"""
Trade proposal API routes.

Endpoints:
- GET /trades - List user's trade proposals
- POST /trades - Create a new trade proposal
- GET /trades/{id} - Get trade proposal details
- POST /trades/{id}/accept - Accept a proposal
- POST /trades/{id}/decline - Decline a proposal
- POST /trades/{id}/cancel - Cancel a proposal
- POST /trades/{id}/counter - Create counter-proposal
- POST /trades/{id}/confirm - Confirm completion
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.models.trade import TradeStatus, TradeSide
from app.services.trades import TradeService

router = APIRouter()


# Schemas
class TradeItemRequest(BaseModel):
    """Item in a trade proposal."""
    card_id: int
    quantity: int = Field(1, ge=1)
    condition: str | None = None


class CreateTradeRequest(BaseModel):
    """Request to create a trade proposal."""
    recipient_id: int = Field(..., description="ID of user to trade with")
    proposer_items: list[TradeItemRequest] = Field(..., description="Items you're offering")
    recipient_items: list[TradeItemRequest] = Field(..., description="Items you want")
    message: str | None = Field(None, max_length=1000)


class CounterTradeRequest(BaseModel):
    """Request to create a counter-proposal."""
    proposer_items: list[TradeItemRequest] = Field(..., description="Items you're offering")
    recipient_items: list[TradeItemRequest] = Field(..., description="Items you want")
    message: str | None = Field(None, max_length=1000)


class TradeItemResponse(BaseModel):
    """Item in a trade proposal response."""
    id: int
    side: str
    card_id: int
    card_name: str
    quantity: int
    condition: str | None = None
    price_at_proposal: float | None = None


class UserBrief(BaseModel):
    """Brief user info."""
    id: int
    username: str
    display_name: str | None = None


class TradeProposalResponse(BaseModel):
    """Trade proposal response."""
    id: int
    proposer: UserBrief
    recipient: UserBrief
    status: str
    message: str | None = None
    proposer_items: list[TradeItemResponse]
    recipient_items: list[TradeItemResponse]
    parent_proposal_id: int | None = None
    created_at: str
    updated_at: str
    expires_at: str
    proposer_confirmed: bool
    recipient_confirmed: bool
    completed_at: str | None = None


class TradeListResponse(BaseModel):
    """List of trade proposals."""
    proposals: list[TradeProposalResponse]
    total: int


# Helper to build response
def _build_proposal_response(proposal) -> TradeProposalResponse:
    return TradeProposalResponse(
        id=proposal.id,
        proposer=UserBrief(
            id=proposal.proposer.id,
            username=proposal.proposer.username,
            display_name=proposal.proposer.display_name,
        ),
        recipient=UserBrief(
            id=proposal.recipient.id,
            username=proposal.recipient.username,
            display_name=proposal.recipient.display_name,
        ),
        status=proposal.status.value if hasattr(proposal.status, 'value') else str(proposal.status),
        message=proposal.message,
        proposer_items=[
            TradeItemResponse(
                id=item.id,
                side=item.side.value if hasattr(item.side, 'value') else str(item.side),
                card_id=item.card_id,
                card_name=item.card.name if item.card else "Unknown",
                quantity=item.quantity,
                condition=item.condition,
                price_at_proposal=float(item.price_at_proposal) if item.price_at_proposal else None,
            )
            for item in proposal.items if item.side == TradeSide.PROPOSER
        ],
        recipient_items=[
            TradeItemResponse(
                id=item.id,
                side=item.side.value if hasattr(item.side, 'value') else str(item.side),
                card_id=item.card_id,
                card_name=item.card.name if item.card else "Unknown",
                quantity=item.quantity,
                condition=item.condition,
                price_at_proposal=float(item.price_at_proposal) if item.price_at_proposal else None,
            )
            for item in proposal.items if item.side == TradeSide.RECIPIENT
        ],
        parent_proposal_id=proposal.parent_proposal_id,
        created_at=proposal.created_at.isoformat(),
        updated_at=proposal.updated_at.isoformat(),
        expires_at=proposal.expires_at.isoformat(),
        proposer_confirmed=proposal.proposer_confirmed_at is not None,
        recipient_confirmed=proposal.recipient_confirmed_at is not None,
        completed_at=proposal.completed_at.isoformat() if proposal.completed_at else None,
    )


# Routes
@router.get("", response_model=TradeListResponse)
async def list_trades(
    status: str | None = Query(None, description="Filter by status"),
    direction: str = Query("all", regex="^(sent|received|all)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List trade proposals for the current user."""
    service = TradeService(db)

    status_enum = None
    if status:
        try:
            status_enum = TradeStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    proposals, total = await service.get_user_proposals(
        user_id=current_user.id,
        status=status_enum,
        direction=direction,
        limit=limit,
        offset=offset,
    )

    return TradeListResponse(
        proposals=[_build_proposal_response(p) for p in proposals],
        total=total,
    )


@router.post("", response_model=TradeProposalResponse)
async def create_trade(
    request: CreateTradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new trade proposal."""
    service = TradeService(db)

    try:
        proposal = await service.create_proposal(
            proposer_id=current_user.id,
            recipient_id=request.recipient_id,
            proposer_items=[i.model_dump() for i in request.proposer_items],
            recipient_items=[i.model_dump() for i in request.recipient_items],
            message=request.message,
        )
        await db.commit()

        # Reload to get relationships
        proposal = await service.get_proposal(proposal.id)
        return _build_proposal_response(proposal)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{proposal_id}", response_model=TradeProposalResponse)
async def get_trade(
    proposal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a trade proposal by ID."""
    service = TradeService(db)
    proposal = await service.get_proposal(proposal_id)

    if not proposal:
        raise HTTPException(status_code=404, detail="Trade proposal not found")

    # Only participants can view
    if current_user.id not in (proposal.proposer_id, proposal.recipient_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this trade")

    return _build_proposal_response(proposal)


@router.post("/{proposal_id}/accept", response_model=TradeProposalResponse)
async def accept_trade(
    proposal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept a trade proposal."""
    service = TradeService(db)

    try:
        proposal = await service.accept_proposal(proposal_id, current_user.id)
        await db.commit()
        proposal = await service.get_proposal(proposal_id)
        return _build_proposal_response(proposal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{proposal_id}/decline", response_model=TradeProposalResponse)
async def decline_trade(
    proposal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Decline a trade proposal."""
    service = TradeService(db)

    try:
        proposal = await service.decline_proposal(proposal_id, current_user.id)
        await db.commit()
        proposal = await service.get_proposal(proposal_id)
        return _build_proposal_response(proposal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{proposal_id}/cancel", response_model=TradeProposalResponse)
async def cancel_trade(
    proposal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a trade proposal (proposer only)."""
    service = TradeService(db)

    try:
        proposal = await service.cancel_proposal(proposal_id, current_user.id)
        await db.commit()
        proposal = await service.get_proposal(proposal_id)
        return _build_proposal_response(proposal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{proposal_id}/counter", response_model=TradeProposalResponse)
async def counter_trade(
    proposal_id: int,
    request: CounterTradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a counter-proposal."""
    service = TradeService(db)

    try:
        proposal = await service.counter_proposal(
            original_proposal_id=proposal_id,
            user_id=current_user.id,
            proposer_items=[i.model_dump() for i in request.proposer_items],
            recipient_items=[i.model_dump() for i in request.recipient_items],
            message=request.message,
        )
        await db.commit()

        proposal = await service.get_proposal(proposal.id)
        return _build_proposal_response(proposal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{proposal_id}/confirm", response_model=TradeProposalResponse)
async def confirm_trade(
    proposal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm trade completion."""
    service = TradeService(db)

    try:
        proposal = await service.confirm_completion(proposal_id, current_user.id)
        await db.commit()
        proposal = await service.get_proposal(proposal_id)
        return _build_proposal_response(proposal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stats/me")
async def get_my_trade_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get trade statistics for current user."""
    service = TradeService(db)
    return await service.get_statistics(current_user.id)
