"""
Trade Quote API routes.

Allows users to:
- Create trade-in quotes with cards they want to sell
- Get offer previews from nearby stores
- Submit quotes to stores for review
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.card import Card
from app.models.trading_post import (
    TradingPost,
    TradeQuote,
    TradeQuoteItem,
    TradeQuoteSubmission,
)
from app.models.user import User
from app.schemas.trading_post import (
    QuoteCreate,
    QuoteUpdate,
    QuoteResponse,
    QuoteListResponse,
    QuoteItemCreate,
    QuoteItemUpdate,
    QuoteItemResponse,
    QuoteBulkImport,
    QuoteBulkImportResult,
    QuoteOffersPreview,
    StoreOffer,
    QuoteSubmit,
    SubmissionResponse,
    SubmissionListResponse,
    TradingPostPublic,
)

router = APIRouter(prefix="/quotes", tags=["Quotes"])


# ============ Quote CRUD ============

@router.post("", response_model=QuoteResponse, status_code=201)
async def create_quote(
    data: QuoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new trade-in quote draft.

    Users can create quotes to estimate trade-in value before
    submitting to local stores.
    """
    quote = TradeQuote(
        user_id=current_user.id,
        name=data.name,
        status="draft",
    )

    db.add(quote)
    await db.commit()
    await db.refresh(quote)

    return _quote_to_response(quote, [])


@router.get("/my", response_model=QuoteListResponse)
async def get_my_quotes(
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's trade quotes."""
    query = select(TradeQuote).where(TradeQuote.user_id == current_user.id)
    count_query = select(func.count(TradeQuote.id)).where(
        TradeQuote.user_id == current_user.id
    )

    if status:
        query = query.where(TradeQuote.status == status)
        count_query = count_query.where(TradeQuote.status == status)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    query = (
        query
        .options(selectinload(TradeQuote.items).selectinload(TradeQuoteItem.card))
        .order_by(TradeQuote.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    quotes = result.scalars().all()

    return QuoteListResponse(
        items=[_quote_to_response(q, q.items) for q in quotes],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific quote with all items."""
    result = await db.execute(
        select(TradeQuote)
        .where(TradeQuote.id == quote_id, TradeQuote.user_id == current_user.id)
        .options(selectinload(TradeQuote.items).selectinload(TradeQuoteItem.card))
    )
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    return _quote_to_response(quote, quote.items)


@router.put("/{quote_id}", response_model=QuoteResponse)
async def update_quote(
    quote_id: int,
    data: QuoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update quote name or status."""
    result = await db.execute(
        select(TradeQuote)
        .where(TradeQuote.id == quote_id, TradeQuote.user_id == current_user.id)
        .options(selectinload(TradeQuote.items).selectinload(TradeQuoteItem.card))
    )
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote.status == "submitted":
        raise HTTPException(
            status_code=400,
            detail="Cannot modify a submitted quote"
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value:
            value = value.value
        setattr(quote, field, value)

    quote.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(quote)

    return _quote_to_response(quote, quote.items)


@router.delete("/{quote_id}", status_code=204)
async def delete_quote(
    quote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a quote (only drafts can be deleted)."""
    result = await db.execute(
        select(TradeQuote)
        .where(TradeQuote.id == quote_id, TradeQuote.user_id == current_user.id)
    )
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote.status == "submitted":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a submitted quote"
        )

    await db.delete(quote)
    await db.commit()


# ============ Quote Items ============

@router.post("/{quote_id}/items", response_model=QuoteItemResponse, status_code=201)
async def add_quote_item(
    quote_id: int,
    data: QuoteItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a card to a quote."""
    # Get quote
    result = await db.execute(
        select(TradeQuote)
        .where(TradeQuote.id == quote_id, TradeQuote.user_id == current_user.id)
    )
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Can only add items to draft quotes"
        )

    # Get card with current price
    card_result = await db.execute(
        select(Card).where(Card.id == data.card_id)
    )
    card = card_result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check if card already in quote
    existing_result = await db.execute(
        select(TradeQuoteItem).where(
            TradeQuoteItem.quote_id == quote_id,
            TradeQuoteItem.card_id == data.card_id,
            TradeQuoteItem.condition == data.condition,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        # Update quantity instead of creating duplicate
        existing.quantity += data.quantity
        existing.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing)
        return _item_to_response(existing, card)

    # Get market price (use tcg_market or tcg_low)
    market_price = card.tcg_market or card.tcg_low or Decimal("0")

    item = TradeQuoteItem(
        quote_id=quote_id,
        card_id=data.card_id,
        quantity=data.quantity,
        condition=data.condition,
        market_price=market_price,
    )

    db.add(item)

    # Update quote total
    await _update_quote_total(db, quote)

    await db.commit()
    await db.refresh(item)

    return _item_to_response(item, card)


@router.put("/{quote_id}/items/{item_id}", response_model=QuoteItemResponse)
async def update_quote_item(
    quote_id: int,
    item_id: int,
    data: QuoteItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a quote item's quantity or condition."""
    # Verify quote ownership
    quote_result = await db.execute(
        select(TradeQuote)
        .where(TradeQuote.id == quote_id, TradeQuote.user_id == current_user.id)
    )
    quote = quote_result.scalar_one_or_none()

    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Can only modify draft quotes"
        )

    # Get item
    result = await db.execute(
        select(TradeQuoteItem)
        .where(TradeQuoteItem.id == item_id, TradeQuoteItem.quote_id == quote_id)
        .options(selectinload(TradeQuoteItem.card))
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    item.updated_at = datetime.now(timezone.utc)

    # Update quote total
    await _update_quote_total(db, quote)

    await db.commit()
    await db.refresh(item)

    return _item_to_response(item, item.card)


@router.delete("/{quote_id}/items/{item_id}", status_code=204)
async def delete_quote_item(
    quote_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a card from a quote."""
    # Verify quote ownership
    quote_result = await db.execute(
        select(TradeQuote)
        .where(TradeQuote.id == quote_id, TradeQuote.user_id == current_user.id)
    )
    quote = quote_result.scalar_one_or_none()

    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Can only modify draft quotes"
        )

    # Get item
    result = await db.execute(
        select(TradeQuoteItem)
        .where(TradeQuoteItem.id == item_id, TradeQuoteItem.quote_id == quote_id)
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(item)

    # Update quote total
    await _update_quote_total(db, quote)

    await db.commit()


@router.post("/{quote_id}/import", response_model=QuoteBulkImportResult)
async def bulk_import_cards(
    quote_id: int,
    data: QuoteBulkImport,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk import cards to a quote.

    Matches cards by name (and optionally set code).
    Returns count of imported and failed items.
    """
    # Verify quote ownership
    quote_result = await db.execute(
        select(TradeQuote)
        .where(TradeQuote.id == quote_id, TradeQuote.user_id == current_user.id)
    )
    quote = quote_result.scalar_one_or_none()

    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Can only import to draft quotes"
        )

    imported = 0
    failed = 0
    errors = []

    for import_item in data.items:
        # Find card by name
        card_query = select(Card).where(
            func.lower(Card.name) == func.lower(import_item.card_name)
        )

        if import_item.set_code:
            card_query = card_query.where(
                func.lower(Card.set_code) == func.lower(import_item.set_code)
            )

        # Order by price to get the most relevant printing
        card_query = card_query.order_by(Card.tcg_market.desc().nullslast()).limit(1)

        card_result = await db.execute(card_query)
        card = card_result.scalar_one_or_none()

        if not card:
            failed += 1
            errors.append(f"Card not found: {import_item.card_name}")
            continue

        # Check for existing item
        existing_result = await db.execute(
            select(TradeQuoteItem).where(
                TradeQuoteItem.quote_id == quote_id,
                TradeQuoteItem.card_id == card.id,
                TradeQuoteItem.condition == import_item.condition,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.quantity += import_item.quantity
            existing.updated_at = datetime.now(timezone.utc)
        else:
            market_price = card.tcg_market or card.tcg_low or Decimal("0")
            item = TradeQuoteItem(
                quote_id=quote_id,
                card_id=card.id,
                quantity=import_item.quantity,
                condition=import_item.condition,
                market_price=market_price,
            )
            db.add(item)

        imported += 1

    # Update quote total
    await _update_quote_total(db, quote)

    await db.commit()

    return QuoteBulkImportResult(
        imported=imported,
        failed=failed,
        errors=errors[:10],  # Limit errors returned
    )


# ============ Offer Preview & Submission ============

@router.get("/{quote_id}/offers", response_model=QuoteOffersPreview)
async def get_quote_offers(
    quote_id: int,
    city: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Preview offers from nearby Trading Posts.

    Shows what each store would pay based on their buylist margin.
    """
    # Get quote with items
    result = await db.execute(
        select(TradeQuote)
        .where(TradeQuote.id == quote_id, TradeQuote.user_id == current_user.id)
        .options(selectinload(TradeQuote.items))
    )
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if not quote.items:
        raise HTTPException(
            status_code=400,
            detail="Quote has no items"
        )

    # Calculate total market value
    total_value = sum(
        (item.market_price or Decimal("0")) * item.quantity
        for item in quote.items
    )

    # Find nearby verified trading posts
    store_query = (
        select(TradingPost)
        .where(TradingPost.email_verified_at.isnot(None))
    )

    if city:
        store_query = store_query.where(TradingPost.city.ilike(f"%{city}%"))

    if state:
        store_query = store_query.where(TradingPost.state == state)

    store_query = store_query.order_by(
        TradingPost.buylist_margin.desc()  # Best offers first
    ).limit(limit)

    store_result = await db.execute(store_query)
    stores = store_result.scalars().all()

    # Calculate offer from each store
    offers = []
    for store in stores:
        offer_amount = total_value * store.buylist_margin
        offers.append(StoreOffer(
            trading_post_id=store.id,
            store_name=store.store_name,
            city=store.city,
            state=store.state,
            is_verified=store.verified_at is not None,
            buylist_margin=store.buylist_margin,
            offer_amount=offer_amount,
        ))

    return QuoteOffersPreview(
        quote_id=quote_id,
        total_market_value=total_value,
        offers=offers,
    )


@router.post("/{quote_id}/submit", response_model=list[SubmissionResponse])
async def submit_quote(
    quote_id: int,
    data: QuoteSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a quote to selected Trading Posts.

    Creates submission records for each store, calculating
    offer based on their buylist margin.
    """
    # Get quote with items
    result = await db.execute(
        select(TradeQuote)
        .where(TradeQuote.id == quote_id, TradeQuote.user_id == current_user.id)
        .options(selectinload(TradeQuote.items))
    )
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    if quote.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Quote has already been submitted"
        )

    if not quote.items:
        raise HTTPException(
            status_code=400,
            detail="Cannot submit empty quote"
        )

    # Calculate total market value
    total_value = sum(
        (item.market_price or Decimal("0")) * item.quantity
        for item in quote.items
    )

    # Get selected trading posts
    store_result = await db.execute(
        select(TradingPost)
        .where(
            TradingPost.id.in_(data.trading_post_ids),
            TradingPost.email_verified_at.isnot(None),
        )
    )
    stores = store_result.scalars().all()

    if not stores:
        raise HTTPException(
            status_code=400,
            detail="No valid Trading Posts selected"
        )

    # Create submissions
    submissions = []
    for store in stores:
        offer_amount = total_value * store.buylist_margin

        submission = TradeQuoteSubmission(
            quote_id=quote_id,
            trading_post_id=store.id,
            status="pending",
            offer_amount=offer_amount,
            user_message=data.message,
        )
        db.add(submission)
        submissions.append((submission, store))

    # Update quote status
    quote.status = "submitted"
    quote.updated_at = datetime.now(timezone.utc)

    await db.commit()

    # Refresh and return
    responses = []
    for submission, store in submissions:
        await db.refresh(submission)
        responses.append(_submission_to_response(submission, store, quote))

    return responses


# ============ User Submission Management ============

@router.get("/submissions/my", response_model=SubmissionListResponse)
async def get_my_submissions(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the user's quote submissions with status."""
    query = (
        select(TradeQuoteSubmission)
        .join(TradeQuote)
        .where(TradeQuote.user_id == current_user.id)
        .options(
            selectinload(TradeQuoteSubmission.trading_post),
            selectinload(TradeQuoteSubmission.quote).selectinload(TradeQuote.items),
        )
    )

    if status:
        query = query.where(TradeQuoteSubmission.status == status)

    query = query.order_by(TradeQuoteSubmission.submitted_at.desc())

    result = await db.execute(query)
    submissions = result.scalars().all()

    return SubmissionListResponse(
        items=[
            _submission_to_response(s, s.trading_post, s.quote)
            for s in submissions
        ],
        total=len(submissions),
    )


@router.post("/submissions/{submission_id}/accept-counter")
async def accept_counter_offer(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept a store's counter-offer."""
    result = await db.execute(
        select(TradeQuoteSubmission)
        .join(TradeQuote)
        .where(
            TradeQuoteSubmission.id == submission_id,
            TradeQuote.user_id == current_user.id,
        )
        .options(selectinload(TradeQuoteSubmission.trading_post))
    )
    submission = result.scalar_one_or_none()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission.status != "countered":
        raise HTTPException(
            status_code=400,
            detail="Can only accept counter-offers"
        )

    submission.status = "user_accepted"
    submission.responded_at = datetime.now(timezone.utc)

    await db.commit()

    return {"status": "accepted", "message": "Counter-offer accepted"}


@router.post("/submissions/{submission_id}/decline-counter")
async def decline_counter_offer(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Decline a store's counter-offer."""
    result = await db.execute(
        select(TradeQuoteSubmission)
        .join(TradeQuote)
        .where(
            TradeQuoteSubmission.id == submission_id,
            TradeQuote.user_id == current_user.id,
        )
    )
    submission = result.scalar_one_or_none()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission.status != "countered":
        raise HTTPException(
            status_code=400,
            detail="Can only decline counter-offers"
        )

    submission.status = "user_declined"
    submission.responded_at = datetime.now(timezone.utc)

    await db.commit()

    return {"status": "declined", "message": "Counter-offer declined"}


# ============ Helper Functions ============

async def _update_quote_total(db: AsyncSession, quote: TradeQuote) -> None:
    """Recalculate quote total from items."""
    result = await db.execute(
        select(
            func.sum(TradeQuoteItem.market_price * TradeQuoteItem.quantity)
        ).where(TradeQuoteItem.quote_id == quote.id)
    )
    total = result.scalar() or Decimal("0")
    quote.total_market_value = total
    quote.updated_at = datetime.now(timezone.utc)


def _quote_to_response(quote: TradeQuote, items: list) -> QuoteResponse:
    """Convert TradeQuote model to response schema."""
    return QuoteResponse(
        id=quote.id,
        user_id=quote.user_id,
        name=quote.name,
        status=quote.status,
        total_market_value=quote.total_market_value,
        item_count=len(items),
        items=[_item_to_response(i, i.card) for i in items] if items else [],
        created_at=quote.created_at,
        updated_at=quote.updated_at,
    )


def _item_to_response(item: TradeQuoteItem, card: Card) -> QuoteItemResponse:
    """Convert TradeQuoteItem to response schema."""
    line_total = None
    if item.market_price:
        line_total = item.market_price * item.quantity

    return QuoteItemResponse(
        id=item.id,
        card_id=item.card_id,
        card_name=card.name if card else "Unknown",
        set_code=card.set_code if card else None,
        quantity=item.quantity,
        condition=item.condition,
        market_price=item.market_price,
        line_total=line_total,
    )


def _submission_to_response(
    submission: TradeQuoteSubmission,
    trading_post: Optional[TradingPost],
    quote: Optional[TradeQuote],
) -> SubmissionResponse:
    """Convert TradeQuoteSubmission to response schema."""
    tp_public = None
    if trading_post:
        tp_public = TradingPostPublic(
            id=trading_post.id,
            store_name=trading_post.store_name,
            description=trading_post.description,
            city=trading_post.city,
            state=trading_post.state,
            country=trading_post.country,
            website=trading_post.website,
            hours=trading_post.hours,
            services=trading_post.services,
            logo_url=trading_post.logo_url,
            is_verified=trading_post.verified_at is not None,
        )

    return SubmissionResponse(
        id=submission.id,
        quote_id=submission.quote_id,
        trading_post_id=submission.trading_post_id,
        status=submission.status,
        offer_amount=submission.offer_amount,
        counter_amount=submission.counter_amount,
        store_message=submission.store_message,
        user_message=submission.user_message,
        submitted_at=submission.submitted_at,
        responded_at=submission.responded_at,
        trading_post=tp_public,
        quote_name=quote.name if quote else None,
        quote_item_count=len(quote.items) if quote and quote.items else None,
        quote_total_value=quote.total_market_value if quote else None,
    )
