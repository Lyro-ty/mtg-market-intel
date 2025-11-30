"""
Inventory management API endpoints.
"""
import csv
import io
import re
import uuid
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Card, InventoryItem, InventoryRecommendation, MetricsCardsDaily
from pydantic import BaseModel
from app.schemas.inventory import (
    InventoryImportRequest,
    InventoryImportResponse,
    ImportedItem,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryListResponse,
    InventoryAnalytics,
    InventoryRecommendationResponse,
    InventoryRecommendationListResponse,
    InventoryCondition,
    InventoryUrgency,
    ActionType,
)


class RunRecommendationsRequest(BaseModel):
    item_ids: Optional[list[int]] = None

router = APIRouter()
logger = structlog.get_logger()


# Condition mappings for parsing
CONDITION_ALIASES = {
    "m": InventoryCondition.MINT,
    "mint": InventoryCondition.MINT,
    "nm": InventoryCondition.NEAR_MINT,
    "near mint": InventoryCondition.NEAR_MINT,
    "near-mint": InventoryCondition.NEAR_MINT,
    "lp": InventoryCondition.LIGHTLY_PLAYED,
    "light play": InventoryCondition.LIGHTLY_PLAYED,
    "lightly played": InventoryCondition.LIGHTLY_PLAYED,
    "mp": InventoryCondition.MODERATELY_PLAYED,
    "moderate play": InventoryCondition.MODERATELY_PLAYED,
    "moderately played": InventoryCondition.MODERATELY_PLAYED,
    "hp": InventoryCondition.HEAVILY_PLAYED,
    "heavy play": InventoryCondition.HEAVILY_PLAYED,
    "heavily played": InventoryCondition.HEAVILY_PLAYED,
    "d": InventoryCondition.DAMAGED,
    "dmg": InventoryCondition.DAMAGED,
    "damaged": InventoryCondition.DAMAGED,
}


def parse_condition(text: str) -> InventoryCondition:
    """Parse condition from text."""
    normalized = text.lower().strip()
    return CONDITION_ALIASES.get(normalized, InventoryCondition.NEAR_MINT)


def parse_plaintext_line(line: str) -> dict:
    """
    Parse a plaintext line into inventory components.
    
    Supports formats like:
    - "4x Lightning Bolt"
    - "2 Black Lotus [FOIL]"
    - "1x Tarmogoyf (MMA) NM"
    - "Force of Will - Alliances - LP"
    """
    result = {
        "quantity": 1,
        "card_name": "",
        "set_code": None,
        "condition": InventoryCondition.NEAR_MINT,
        "is_foil": False,
    }
    
    # Check for foil
    if re.search(r'\[foil\]|\(foil\)|foil', line, re.IGNORECASE):
        result["is_foil"] = True
        line = re.sub(r'\[foil\]|\(foil\)|foil', '', line, flags=re.IGNORECASE)
    
    # Parse quantity at start: "4x", "4 x", or just "4 "
    qty_match = re.match(r'^(\d+)\s*[xX]?\s*', line)
    if qty_match:
        result["quantity"] = int(qty_match.group(1))
        line = line[qty_match.end():]
    
    # Check for condition at end
    for alias, cond in CONDITION_ALIASES.items():
        if line.lower().rstrip().endswith(alias):
            result["condition"] = cond
            line = line[:-(len(alias))].rstrip(' -')
            break
    
    # Check for set code in parentheses: (MMA) or [MMA]
    set_match = re.search(r'[\(\[]([A-Z0-9]{2,6})[\)\]]', line, re.IGNORECASE)
    if set_match:
        result["set_code"] = set_match.group(1).upper()
        line = line[:set_match.start()] + line[set_match.end():]
    
    # Check for set name after dash: "Card Name - Set Name"
    if " - " in line and not result["set_code"]:
        parts = line.split(" - ")
        result["card_name"] = parts[0].strip()
        # The rest might be set name or other info - just use the card name
    else:
        result["card_name"] = line.strip()
    
    # Clean up card name
    result["card_name"] = re.sub(r'\s+', ' ', result["card_name"]).strip()
    
    return result


async def find_card(db: AsyncSession, name: str, set_code: Optional[str] = None) -> Optional[Card]:
    """Find a card by name and optional set code."""
    query = select(Card).where(
        func.lower(Card.name) == func.lower(name)
    )
    
    if set_code:
        query = query.where(func.lower(Card.set_code) == func.lower(set_code))
    
    result = await db.execute(query.limit(1))
    return result.scalar_one_or_none()


@router.post("/import", response_model=InventoryImportResponse)
async def import_inventory(
    request: InventoryImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Import inventory from CSV or plaintext.
    
    CSV format expects columns: card_name, set_code (optional), quantity, condition, is_foil, acquisition_price
    
    Plaintext format supports common formats like:
    - "4x Lightning Bolt"
    - "2 Black Lotus [FOIL]"
    - "Force of Will (ALL) NM"
    """
    batch_id = str(uuid.uuid4())
    items: list[ImportedItem] = []
    lines = request.content.strip().split("\n")
    
    # Detect format
    format_type = request.format
    if format_type == "auto":
        # Check if first line looks like CSV (has commas and common headers)
        first_line = lines[0].lower() if lines else ""
        if "," in first_line and any(h in first_line for h in ["name", "card", "quantity", "qty"]):
            format_type = "csv"
        elif "," in first_line and len(first_line.split(",")) >= 2:
            format_type = "csv"
        else:
            format_type = "plaintext"
    
    if format_type == "csv":
        # Parse CSV
        reader = csv.DictReader(io.StringIO(request.content)) if request.has_header else None
        
        if not request.has_header:
            # Assume format: name, set_code, quantity, condition, foil, price
            reader = csv.reader(io.StringIO(request.content))
        
        for line_num, row in enumerate(reader or [], start=1 if not request.has_header else 2):
            raw_line = ",".join(row.values()) if isinstance(row, dict) else ",".join(row)
            
            try:
                if isinstance(row, dict):
                    # Header-based CSV
                    card_name = row.get("card_name") or row.get("name") or row.get("card") or ""
                    set_code = row.get("set_code") or row.get("set") or row.get("expansion")
                    quantity = int(row.get("quantity") or row.get("qty") or 1)
                    condition_str = row.get("condition") or row.get("cond") or "NM"
                    is_foil = str(row.get("foil") or row.get("is_foil") or "").lower() in ("true", "1", "yes", "foil")
                    price_str = row.get("price") or row.get("acquisition_price") or ""
                    acquisition_price = float(price_str) if price_str else None
                else:
                    # Positional CSV
                    card_name = row[0] if len(row) > 0 else ""
                    set_code = row[1] if len(row) > 1 else None
                    quantity = int(row[2]) if len(row) > 2 and row[2] else 1
                    condition_str = row[3] if len(row) > 3 else "NM"
                    is_foil = str(row[4]).lower() in ("true", "1", "yes", "foil") if len(row) > 4 else False
                    acquisition_price = float(row[5]) if len(row) > 5 and row[5] else None
                
                if not card_name.strip():
                    items.append(ImportedItem(
                        line_number=line_num,
                        raw_line=raw_line,
                        success=False,
                        error="Missing card name"
                    ))
                    continue
                
                # Find card
                card = await find_card(db, card_name.strip(), set_code)
                if not card:
                    items.append(ImportedItem(
                        line_number=line_num,
                        raw_line=raw_line,
                        success=False,
                        error=f"Card not found: {card_name}"
                    ))
                    continue
                
                # Create inventory item
                inv_item = InventoryItem(
                    card_id=card.id,
                    quantity=quantity,
                    condition=parse_condition(condition_str).value,
                    is_foil=is_foil,
                    acquisition_price=acquisition_price,
                    acquisition_source=request.default_acquisition_source,
                    import_batch_id=batch_id,
                    import_raw_line=raw_line,
                )
                db.add(inv_item)
                await db.flush()
                
                items.append(ImportedItem(
                    line_number=line_num,
                    raw_line=raw_line,
                    success=True,
                    inventory_item_id=inv_item.id,
                    card_id=card.id,
                    card_name=card.name,
                ))
                
            except Exception as e:
                items.append(ImportedItem(
                    line_number=line_num,
                    raw_line=raw_line,
                    success=False,
                    error=str(e)
                ))
    else:
        # Parse plaintext
        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            try:
                parsed = parse_plaintext_line(line)
                
                if not parsed["card_name"]:
                    items.append(ImportedItem(
                        line_number=line_num,
                        raw_line=line,
                        success=False,
                        error="Could not parse card name"
                    ))
                    continue
                
                # Find card
                card = await find_card(db, parsed["card_name"], parsed["set_code"])
                if not card:
                    items.append(ImportedItem(
                        line_number=line_num,
                        raw_line=line,
                        success=False,
                        error=f"Card not found: {parsed['card_name']}"
                    ))
                    continue
                
                # Create inventory item
                inv_item = InventoryItem(
                    card_id=card.id,
                    quantity=parsed["quantity"],
                    condition=parsed["condition"].value,
                    is_foil=parsed["is_foil"],
                    acquisition_source=request.default_acquisition_source,
                    import_batch_id=batch_id,
                    import_raw_line=line,
                )
                db.add(inv_item)
                await db.flush()
                
                items.append(ImportedItem(
                    line_number=line_num,
                    raw_line=line,
                    success=True,
                    inventory_item_id=inv_item.id,
                    card_id=card.id,
                    card_name=card.name,
                ))
                
            except Exception as e:
                items.append(ImportedItem(
                    line_number=line_num,
                    raw_line=line,
                    success=False,
                    error=str(e)
                ))
    
    await db.commit()
    
    successful = sum(1 for i in items if i.success)
    failed = sum(1 for i in items if not i.success)
    
    logger.info(
        "Inventory import completed",
        batch_id=batch_id,
        total=len(items),
        successful=successful,
        failed=failed,
    )
    
    return InventoryImportResponse(
        batch_id=batch_id,
        total_lines=len(items),
        successful_imports=successful,
        failed_imports=failed,
        items=items,
    )


@router.get("", response_model=InventoryListResponse)
async def get_inventory(
    search: Optional[str] = None,
    set_code: Optional[str] = None,
    condition: Optional[InventoryCondition] = None,
    is_foil: Optional[bool] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    sort_by: str = Query("created_at", regex="^(created_at|current_value|value_change_pct|card_name|quantity)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get inventory items with filtering and pagination.
    """
    # Build base query
    query = select(InventoryItem, Card).join(Card, InventoryItem.card_id == Card.id)
    
    # Apply filters
    if search:
        query = query.where(Card.name.ilike(f"%{search}%"))
    
    if set_code:
        query = query.where(Card.set_code == set_code.upper())
    
    if condition:
        query = query.where(InventoryItem.condition == condition.value)
    
    if is_foil is not None:
        query = query.where(InventoryItem.is_foil == is_foil)
    
    if min_value is not None:
        query = query.where(InventoryItem.current_value >= min_value)
    
    if max_value is not None:
        query = query.where(InventoryItem.current_value <= max_value)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # Get summary stats
    stats_query = select(
        func.count(InventoryItem.id).label("total_items"),
        func.sum(InventoryItem.quantity).label("total_quantity"),
        func.sum(InventoryItem.current_value * InventoryItem.quantity).label("total_value"),
        func.sum(InventoryItem.acquisition_price * InventoryItem.quantity).label("total_cost"),
    ).select_from(InventoryItem)
    
    stats_result = await db.execute(stats_query)
    stats = stats_result.one()
    
    total_items = stats.total_items or 0
    total_quantity = stats.total_quantity or 0
    total_value = float(stats.total_value or 0)
    total_cost = float(stats.total_cost or 0)
    total_profit_loss = total_value - total_cost
    total_profit_loss_pct = (total_profit_loss / total_cost * 100) if total_cost > 0 else None
    
    # Apply sorting
    sort_column = {
        "created_at": InventoryItem.created_at,
        "current_value": InventoryItem.current_value,
        "value_change_pct": InventoryItem.value_change_pct,
        "card_name": Card.name,
        "quantity": InventoryItem.quantity,
    }.get(sort_by, InventoryItem.created_at)
    
    if sort_order == "desc":
        query = query.order_by(sort_column.desc().nulls_last())
    else:
        query = query.order_by(sort_column.asc().nulls_last())
    
    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    rows = result.all()
    
    items = [
        InventoryItemResponse(
            id=inv_item.id,
            card_id=inv_item.card_id,
            card_name=card.name,
            card_set=card.set_code,
            card_image_url=card.image_url_small,
            quantity=inv_item.quantity,
            condition=InventoryCondition(inv_item.condition),
            is_foil=inv_item.is_foil,
            language=inv_item.language,
            acquisition_price=float(inv_item.acquisition_price) if inv_item.acquisition_price else None,
            acquisition_currency=inv_item.acquisition_currency,
            acquisition_date=inv_item.acquisition_date,
            acquisition_source=inv_item.acquisition_source,
            current_value=float(inv_item.current_value) if inv_item.current_value else None,
            value_change_pct=float(inv_item.value_change_pct) if inv_item.value_change_pct else None,
            last_valued_at=inv_item.last_valued_at,
            profit_loss=inv_item.profit_loss,
            profit_loss_pct=inv_item.profit_loss_pct,
            import_batch_id=inv_item.import_batch_id,
            notes=inv_item.notes,
            created_at=inv_item.created_at,
            updated_at=inv_item.updated_at,
        )
        for inv_item, card in rows
    ]
    
    return InventoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
        total_items=total_items,
        total_quantity=total_quantity,
        total_value=total_value,
        total_acquisition_cost=total_cost,
        total_profit_loss=total_profit_loss,
        total_profit_loss_pct=total_profit_loss_pct,
    )


@router.get("/analytics", response_model=InventoryAnalytics)
async def get_inventory_analytics(
    db: AsyncSession = Depends(get_db),
):
    """
    Get comprehensive inventory analytics.
    """
    # Basic stats
    stats_query = select(
        func.count(func.distinct(InventoryItem.card_id)).label("unique_cards"),
        func.sum(InventoryItem.quantity).label("total_quantity"),
        func.sum(InventoryItem.acquisition_price * InventoryItem.quantity).label("total_cost"),
        func.sum(InventoryItem.current_value * InventoryItem.quantity).label("total_value"),
    ).select_from(InventoryItem)
    
    stats_result = await db.execute(stats_query)
    stats = stats_result.one()
    
    total_cost = float(stats.total_cost or 0)
    total_value = float(stats.total_value or 0)
    total_profit_loss = total_value - total_cost
    profit_loss_pct = (total_profit_loss / total_cost * 100) if total_cost > 0 else None
    
    # Condition breakdown
    condition_query = select(
        InventoryItem.condition,
        func.count(InventoryItem.id).label("count"),
    ).group_by(InventoryItem.condition)
    
    condition_result = await db.execute(condition_query)
    condition_breakdown = {row.condition: row.count for row in condition_result.all()}
    
    # Top gainers
    gainers_query = select(InventoryItem, Card).join(
        Card, InventoryItem.card_id == Card.id
    ).where(
        InventoryItem.value_change_pct.isnot(None)
    ).order_by(
        InventoryItem.value_change_pct.desc()
    ).limit(5)
    
    gainers_result = await db.execute(gainers_query)
    top_gainers = [
        InventoryItemResponse(
            id=inv.id,
            card_id=inv.card_id,
            card_name=card.name,
            card_set=card.set_code,
            card_image_url=card.image_url_small,
            quantity=inv.quantity,
            condition=InventoryCondition(inv.condition),
            is_foil=inv.is_foil,
            language=inv.language,
            acquisition_price=float(inv.acquisition_price) if inv.acquisition_price else None,
            acquisition_currency=inv.acquisition_currency,
            current_value=float(inv.current_value) if inv.current_value else None,
            value_change_pct=float(inv.value_change_pct) if inv.value_change_pct else None,
            profit_loss=inv.profit_loss,
            profit_loss_pct=inv.profit_loss_pct,
            created_at=inv.created_at,
            updated_at=inv.updated_at,
        )
        for inv, card in gainers_result.all()
    ]
    
    # Top losers
    losers_query = select(InventoryItem, Card).join(
        Card, InventoryItem.card_id == Card.id
    ).where(
        InventoryItem.value_change_pct.isnot(None)
    ).order_by(
        InventoryItem.value_change_pct.asc()
    ).limit(5)
    
    losers_result = await db.execute(losers_query)
    top_losers = [
        InventoryItemResponse(
            id=inv.id,
            card_id=inv.card_id,
            card_name=card.name,
            card_set=card.set_code,
            card_image_url=card.image_url_small,
            quantity=inv.quantity,
            condition=InventoryCondition(inv.condition),
            is_foil=inv.is_foil,
            language=inv.language,
            acquisition_price=float(inv.acquisition_price) if inv.acquisition_price else None,
            acquisition_currency=inv.acquisition_currency,
            current_value=float(inv.current_value) if inv.current_value else None,
            value_change_pct=float(inv.value_change_pct) if inv.value_change_pct else None,
            profit_loss=inv.profit_loss,
            profit_loss_pct=inv.profit_loss_pct,
            created_at=inv.created_at,
            updated_at=inv.updated_at,
        )
        for inv, card in losers_result.all()
    ]
    
    # Value distribution
    value_ranges = {
        "$0-$5": 0,
        "$5-$20": 0,
        "$20-$50": 0,
        "$50-$100": 0,
        "$100+": 0,
    }
    
    dist_query = select(
        InventoryItem.current_value,
        InventoryItem.quantity,
    ).where(InventoryItem.current_value.isnot(None))
    
    dist_result = await db.execute(dist_query)
    for row in dist_result.all():
        value = float(row.current_value)
        qty = row.quantity
        if value < 5:
            value_ranges["$0-$5"] += qty
        elif value < 20:
            value_ranges["$5-$20"] += qty
        elif value < 50:
            value_ranges["$20-$50"] += qty
        elif value < 100:
            value_ranges["$50-$100"] += qty
        else:
            value_ranges["$100+"] += qty
    
    # Recommendation counts
    rec_query = select(
        func.count(case((InventoryRecommendation.action == "SELL", 1))).label("sell_count"),
        func.count(case((InventoryRecommendation.action == "HOLD", 1))).label("hold_count"),
        func.count(case((InventoryRecommendation.urgency == "CRITICAL", 1))).label("critical_count"),
    ).where(InventoryRecommendation.is_active == True)
    
    rec_result = await db.execute(rec_query)
    rec_stats = rec_result.one()
    
    return InventoryAnalytics(
        total_unique_cards=stats.unique_cards or 0,
        total_quantity=stats.total_quantity or 0,
        total_acquisition_cost=total_cost,
        total_current_value=total_value,
        total_profit_loss=total_profit_loss,
        profit_loss_pct=profit_loss_pct,
        condition_breakdown=condition_breakdown,
        top_gainers=top_gainers,
        top_losers=top_losers,
        value_distribution=value_ranges,
        sell_recommendations=rec_stats.sell_count or 0,
        hold_recommendations=rec_stats.hold_count or 0,
        critical_alerts=rec_stats.critical_count or 0,
    )


@router.post("", response_model=InventoryItemResponse)
async def create_inventory_item(
    item: InventoryItemCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new inventory item.
    """
    # Verify card exists
    card = await db.get(Card, item.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    inv_item = InventoryItem(
        card_id=item.card_id,
        quantity=item.quantity,
        condition=item.condition.value,
        is_foil=item.is_foil,
        language=item.language,
        acquisition_price=item.acquisition_price,
        acquisition_currency=item.acquisition_currency,
        acquisition_date=item.acquisition_date,
        acquisition_source=item.acquisition_source,
        notes=item.notes,
    )
    db.add(inv_item)
    await db.commit()
    await db.refresh(inv_item)
    
    return InventoryItemResponse(
        id=inv_item.id,
        card_id=inv_item.card_id,
        card_name=card.name,
        card_set=card.set_code,
        card_image_url=card.image_url_small,
        quantity=inv_item.quantity,
        condition=InventoryCondition(inv_item.condition),
        is_foil=inv_item.is_foil,
        language=inv_item.language,
        acquisition_price=float(inv_item.acquisition_price) if inv_item.acquisition_price else None,
        acquisition_currency=inv_item.acquisition_currency,
        acquisition_date=inv_item.acquisition_date,
        acquisition_source=inv_item.acquisition_source,
        current_value=float(inv_item.current_value) if inv_item.current_value else None,
        value_change_pct=float(inv_item.value_change_pct) if inv_item.value_change_pct else None,
        last_valued_at=inv_item.last_valued_at,
        profit_loss=inv_item.profit_loss,
        profit_loss_pct=inv_item.profit_loss_pct,
        notes=inv_item.notes,
        created_at=inv_item.created_at,
        updated_at=inv_item.updated_at,
    )


@router.get("/{item_id}", response_model=InventoryItemResponse)
async def get_inventory_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific inventory item by ID.
    """
    query = select(InventoryItem, Card).join(
        Card, InventoryItem.card_id == Card.id
    ).where(InventoryItem.id == item_id)
    
    result = await db.execute(query)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    inv_item, card = row
    
    return InventoryItemResponse(
        id=inv_item.id,
        card_id=inv_item.card_id,
        card_name=card.name,
        card_set=card.set_code,
        card_image_url=card.image_url_small,
        quantity=inv_item.quantity,
        condition=InventoryCondition(inv_item.condition),
        is_foil=inv_item.is_foil,
        language=inv_item.language,
        acquisition_price=float(inv_item.acquisition_price) if inv_item.acquisition_price else None,
        acquisition_currency=inv_item.acquisition_currency,
        acquisition_date=inv_item.acquisition_date,
        acquisition_source=inv_item.acquisition_source,
        current_value=float(inv_item.current_value) if inv_item.current_value else None,
        value_change_pct=float(inv_item.value_change_pct) if inv_item.value_change_pct else None,
        last_valued_at=inv_item.last_valued_at,
        profit_loss=inv_item.profit_loss,
        profit_loss_pct=inv_item.profit_loss_pct,
        import_batch_id=inv_item.import_batch_id,
        notes=inv_item.notes,
        created_at=inv_item.created_at,
        updated_at=inv_item.updated_at,
    )


@router.patch("/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    item_id: int,
    updates: InventoryItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update an inventory item.
    """
    query = select(InventoryItem, Card).join(
        Card, InventoryItem.card_id == Card.id
    ).where(InventoryItem.id == item_id)
    
    result = await db.execute(query)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    inv_item, card = row
    
    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "condition" and value is not None:
            setattr(inv_item, field, value.value)
        else:
            setattr(inv_item, field, value)
    
    await db.commit()
    await db.refresh(inv_item)
    
    return InventoryItemResponse(
        id=inv_item.id,
        card_id=inv_item.card_id,
        card_name=card.name,
        card_set=card.set_code,
        card_image_url=card.image_url_small,
        quantity=inv_item.quantity,
        condition=InventoryCondition(inv_item.condition),
        is_foil=inv_item.is_foil,
        language=inv_item.language,
        acquisition_price=float(inv_item.acquisition_price) if inv_item.acquisition_price else None,
        acquisition_currency=inv_item.acquisition_currency,
        acquisition_date=inv_item.acquisition_date,
        acquisition_source=inv_item.acquisition_source,
        current_value=float(inv_item.current_value) if inv_item.current_value else None,
        value_change_pct=float(inv_item.value_change_pct) if inv_item.value_change_pct else None,
        last_valued_at=inv_item.last_valued_at,
        profit_loss=inv_item.profit_loss,
        profit_loss_pct=inv_item.profit_loss_pct,
        import_batch_id=inv_item.import_batch_id,
        notes=inv_item.notes,
        created_at=inv_item.created_at,
        updated_at=inv_item.updated_at,
    )


@router.delete("/{item_id}")
async def delete_inventory_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an inventory item.
    """
    inv_item = await db.get(InventoryItem, item_id)
    if not inv_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    await db.delete(inv_item)
    await db.commit()
    
    return {"message": "Item deleted successfully"}


@router.get("/recommendations/list", response_model=InventoryRecommendationListResponse)
async def get_inventory_recommendations(
    action: Optional[ActionType] = None,
    urgency: Optional[InventoryUrgency] = None,
    min_confidence: Optional[float] = Query(None, ge=0, le=1),
    is_active: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get inventory-specific recommendations.
    
    These recommendations are more aggressive than market-wide ones,
    with lower thresholds and shorter time horizons.
    """
    # Build base query
    query = select(InventoryRecommendation, InventoryItem, Card).join(
        InventoryItem, InventoryRecommendation.inventory_item_id == InventoryItem.id
    ).join(
        Card, InventoryRecommendation.card_id == Card.id
    )
    
    # Apply filters
    if is_active:
        query = query.where(InventoryRecommendation.is_active == True)
    
    if action:
        query = query.where(InventoryRecommendation.action == action.value)
    
    if urgency:
        query = query.where(InventoryRecommendation.urgency == urgency.value)
    
    if min_confidence is not None:
        query = query.where(InventoryRecommendation.confidence >= min_confidence)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # Get counts by urgency and action
    urgency_query = select(
        func.count(case((InventoryRecommendation.urgency == "CRITICAL", 1))).label("critical"),
        func.count(case((InventoryRecommendation.urgency == "HIGH", 1))).label("high"),
        func.count(case((InventoryRecommendation.urgency == "NORMAL", 1))).label("normal"),
        func.count(case((InventoryRecommendation.urgency == "LOW", 1))).label("low"),
        func.count(case((InventoryRecommendation.action == "SELL", 1))).label("sell"),
        func.count(case((InventoryRecommendation.action == "HOLD", 1))).label("hold"),
    ).where(InventoryRecommendation.is_active == True)
    
    counts_result = await db.execute(urgency_query)
    counts = counts_result.one()
    
    # Apply pagination and ordering (by urgency priority, then confidence)
    urgency_order = case(
        (InventoryRecommendation.urgency == "CRITICAL", 1),
        (InventoryRecommendation.urgency == "HIGH", 2),
        (InventoryRecommendation.urgency == "NORMAL", 3),
        (InventoryRecommendation.urgency == "LOW", 4),
        else_=5
    )
    
    query = query.order_by(
        urgency_order,
        InventoryRecommendation.confidence.desc(),
        InventoryRecommendation.created_at.desc(),
    ).offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    rows = result.all()
    
    recommendations = [
        InventoryRecommendationResponse(
            id=rec.id,
            inventory_item_id=rec.inventory_item_id,
            card_id=rec.card_id,
            card_name=card.name,
            card_set=card.set_code,
            card_image_url=card.image_url_small,
            action=ActionType(rec.action),
            urgency=InventoryUrgency(rec.urgency),
            confidence=float(rec.confidence),
            horizon_days=rec.horizon_days,
            current_price=float(rec.current_price) if rec.current_price else None,
            target_price=float(rec.target_price) if rec.target_price else None,
            potential_profit_pct=float(rec.potential_profit_pct) if rec.potential_profit_pct else None,
            acquisition_price=float(inv_item.acquisition_price) if inv_item.acquisition_price else None,
            roi_from_acquisition=float(rec.roi_from_acquisition) if rec.roi_from_acquisition else None,
            rationale=rec.rationale,
            suggested_marketplace=rec.suggested_marketplace,
            suggested_listing_price=float(rec.suggested_listing_price) if rec.suggested_listing_price else None,
            valid_until=rec.valid_until,
            is_active=rec.is_active,
            created_at=rec.created_at,
        )
        for rec, inv_item, card in rows
    ]
    
    return InventoryRecommendationListResponse(
        recommendations=recommendations,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
        critical_count=counts.critical or 0,
        high_count=counts.high or 0,
        normal_count=counts.normal or 0,
        low_count=counts.low or 0,
        sell_count=counts.sell or 0,
        hold_count=counts.hold or 0,
    )


@router.post("/scrape-prices")
async def scrape_inventory_prices():
    """
    Trigger immediate price scraping for all inventory cards.
    
    This runs a targeted scrape that only fetches prices for cards
    in your inventory, making it faster than a full marketplace scrape.
    """
    from app.tasks.ingestion import scrape_inventory_cards
    
    task = scrape_inventory_cards.delay()
    
    return {
        "message": "Inventory price scrape started",
        "task_id": str(task.id),
    }


@router.post("/refresh-valuations")
async def refresh_inventory_valuations(
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh current valuations for all inventory items based on latest metrics.
    """
    # Get all inventory items
    query = select(InventoryItem)
    result = await db.execute(query)
    items = result.scalars().all()
    
    updated_count = 0
    
    for item in items:
        # Get latest metrics for the card
        metrics_query = select(MetricsCardsDaily).where(
            MetricsCardsDaily.card_id == item.card_id
        ).order_by(MetricsCardsDaily.date.desc()).limit(1)
        
        metrics_result = await db.execute(metrics_query)
        metrics = metrics_result.scalar_one_or_none()
        
        if metrics and metrics.avg_price:
            old_value = item.current_value
            item.current_value = float(metrics.avg_price)
            item.last_valued_at = datetime.utcnow()
            
            # Calculate value change percentage
            if old_value:
                item.value_change_pct = ((float(item.current_value) - float(old_value)) / float(old_value)) * 100
            
            updated_count += 1
    
    await db.commit()
    
    return {
        "message": f"Updated valuations for {updated_count} items",
        "updated_count": updated_count,
    }


@router.post("/run-recommendations")
async def run_inventory_recommendations(
    request: Optional[RunRecommendationsRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate aggressive recommendations for inventory items.
    
    This uses lower thresholds and shorter time horizons than market recommendations.
    """
    from app.services.agents.inventory_recommendation import InventoryRecommendationAgent
    
    agent = InventoryRecommendationAgent(db)
    item_ids = request.item_ids if request else None
    result = await agent.run_inventory_recommendations(item_ids)
    
    return result
