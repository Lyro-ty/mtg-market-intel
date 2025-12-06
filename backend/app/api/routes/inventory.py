"""
Inventory management API endpoints.

All inventory endpoints require authentication and filter data by the current user.
"""
import asyncio
import csv
import io
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select, func, and_, or_, case, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models import Card, InventoryItem, InventoryRecommendation, MetricsCardsDaily, PriceSnapshot, Marketplace
from app.api.utils.error_handling import is_database_connection_error
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


def interpolate_missing_points(
    points: List[Dict[str, Any]], 
    start_date: datetime, 
    end_date: datetime, 
    bucket_minutes: int
) -> List[Dict[str, Any]]:
    """
    Fill gaps in time-series data using forward-fill and linear interpolation.
    
    Args:
        points: List of points with 'timestamp' and 'indexValue' keys
        start_date: Start of the time range
        end_date: End of the time range
        bucket_minutes: Size of each bucket in minutes
    
    Returns:
        List of points with gaps filled
    """
    if not points:
        return []
    
    # Convert timestamps to datetime objects for easier manipulation
    point_dict = {}
    for point in points:
        if isinstance(point['timestamp'], str):
            ts = datetime.fromisoformat(point['timestamp'].replace('Z', '+00:00'))
        else:
            ts = point['timestamp']
        point_dict[ts] = point['indexValue']
    
    # Generate all expected bucket timestamps
    bucket_timedelta = timedelta(minutes=bucket_minutes)
    expected_times = []
    current = start_date
    while current <= end_date:
        expected_times.append(current)
        current += bucket_timedelta
    
    # Fill missing points using forward-fill, then linear interpolation
    filled_points = []
    last_value = None
    
    for i, expected_time in enumerate(expected_times):
        if expected_time in point_dict:
            # We have actual data for this bucket
            last_value = point_dict[expected_time]
            filled_points.append({
                'timestamp': expected_time.isoformat(),
                'indexValue': last_value
            })
        elif last_value is not None:
            # Forward-fill: use last known value
            filled_points.append({
                'timestamp': expected_time.isoformat(),
                'indexValue': last_value
            })
        else:
            # No data yet, find next known value for interpolation
            next_value = None
            next_time = None
            for future_time in expected_times[i+1:]:
                if future_time in point_dict:
                    next_value = point_dict[future_time]
                    next_time = future_time
                    break
            
            if next_value is not None and last_value is not None:
                # Linear interpolation between last and next
                time_diff = (next_time - expected_times[i-1]).total_seconds()
                if time_diff > 0:
                    interp_factor = (expected_time - expected_times[i-1]).total_seconds() / time_diff
                    interp_value = last_value + (next_value - last_value) * interp_factor
                    filled_points.append({
                        'timestamp': expected_time.isoformat(),
                        'indexValue': round(interp_value, 2)
                    })
                    last_value = interp_value
            elif next_value is not None:
                # Use next value if no previous value
                filled_points.append({
                    'timestamp': expected_time.isoformat(),
                    'indexValue': next_value
                })
                last_value = next_value
            else:
                # No data available, skip this bucket
                continue
    
    return filled_points


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


async def parse_plaintext_line_enhanced(line: str, db: AsyncSession) -> dict:
    """
    Parse a plaintext line into inventory components with enhanced set code validation.
    
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
        potential_set = set_match.group(1).upper()
        
        # Validate against known sets
        set_query = select(Card.set_code).where(
            Card.set_code.ilike(f"%{potential_set}%")
        ).distinct().limit(5)
        set_result = await db.execute(set_query)
        known_sets = [row[0] for row in set_result.all()]
        
        if known_sets:
            # Use exact match if available, otherwise first match
            if potential_set in known_sets:
                result["set_code"] = potential_set
            else:
                result["set_code"] = known_sets[0]  # Best match
        else:
            # If no match found, still use the extracted code (might be valid but not in DB yet)
            result["set_code"] = potential_set
        
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


def parse_plaintext_line(line: str) -> dict:
    """
    Parse a plaintext line into inventory components (non-async version for backward compatibility).
    
    This is a simplified version that doesn't validate set codes against the database.
    For enhanced validation, use parse_plaintext_line_enhanced().
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
    current_user: CurrentUser,
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
                    user_id=current_user.id,
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
                # Use enhanced parsing with set code validation
                parsed = await parse_plaintext_line_enhanced(line, db)
                
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
                    user_id=current_user.id,
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
    current_user: CurrentUser,
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
    Get the current user's inventory items with filtering and pagination.
    """
    # Build base query - filter by current user
    query = select(InventoryItem, Card).join(Card, InventoryItem.card_id == Card.id).where(
        InventoryItem.user_id == current_user.id
    )
    
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
    
    # Get summary stats for current user only
    stats_query = select(
        func.count(InventoryItem.id).label("total_items"),
        func.sum(InventoryItem.quantity).label("total_quantity"),
        func.sum(InventoryItem.current_value * InventoryItem.quantity).label("total_value"),
        func.sum(InventoryItem.acquisition_price * InventoryItem.quantity).label("total_cost"),
    ).select_from(InventoryItem).where(InventoryItem.user_id == current_user.id)
    
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
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Get comprehensive analytics for the current user's inventory.
    """
    # Basic stats - filtered by current user
    stats_query = select(
        func.count(func.distinct(InventoryItem.card_id)).label("unique_cards"),
        func.sum(InventoryItem.quantity).label("total_quantity"),
        func.sum(InventoryItem.acquisition_price * InventoryItem.quantity).label("total_cost"),
        func.sum(InventoryItem.current_value * InventoryItem.quantity).label("total_value"),
    ).select_from(InventoryItem).where(InventoryItem.user_id == current_user.id)
    
    stats_result = await db.execute(stats_query)
    stats = stats_result.one()
    
    total_cost = float(stats.total_cost or 0)
    total_value = float(stats.total_value or 0)
    total_profit_loss = total_value - total_cost
    profit_loss_pct = (total_profit_loss / total_cost * 100) if total_cost > 0 else None
    
    # Condition breakdown for current user
    condition_query = select(
        InventoryItem.condition,
        func.count(InventoryItem.id).label("count"),
    ).where(InventoryItem.user_id == current_user.id).group_by(InventoryItem.condition)
    
    condition_result = await db.execute(condition_query)
    condition_breakdown = {row.condition: row.count for row in condition_result.all()}
    
    # Top gainers for current user
    gainers_query = select(InventoryItem, Card).join(
        Card, InventoryItem.card_id == Card.id
    ).where(
        and_(
            InventoryItem.user_id == current_user.id,
            InventoryItem.value_change_pct.isnot(None)
        )
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
    
    # Top losers for current user
    losers_query = select(InventoryItem, Card).join(
        Card, InventoryItem.card_id == Card.id
    ).where(
        and_(
            InventoryItem.user_id == current_user.id,
            InventoryItem.value_change_pct.isnot(None)
        )
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
    ).where(
        and_(
            InventoryItem.user_id == current_user.id,
            InventoryItem.current_value.isnot(None)
        )
    )
    
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
    
    # Recommendation counts for current user's inventory items
    rec_query = select(
        func.count(case((InventoryRecommendation.action == "SELL", 1))).label("sell_count"),
        func.count(case((InventoryRecommendation.action == "HOLD", 1))).label("hold_count"),
        func.count(case((InventoryRecommendation.urgency == "CRITICAL", 1))).label("critical_count"),
    ).join(
        InventoryItem, InventoryRecommendation.inventory_item_id == InventoryItem.id
    ).where(
        and_(
            InventoryRecommendation.is_active == True,
            InventoryItem.user_id == current_user.id
        )
    )
    
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
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new inventory item for the current user.
    """
    # Verify card exists
    card = await db.get(Card, item.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    inv_item = InventoryItem(
        user_id=current_user.id,
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


# IMPORTANT: These specific routes must come BEFORE the /{item_id} route
# Otherwise FastAPI will try to match "top-movers" and "market-index" as item_id values

@router.get("/market-index")
async def get_inventory_market_index(
    current_user: CurrentUser,
    range: str = Query("7d", regex="^(7d|30d|90d|1y)$"),
    currency: Optional[str] = Query(None, regex="^(USD|EUR)$"),
    separate_currencies: bool = Query(False),
    is_foil: Optional[str] = Query(None, description="Filter by foil pricing. 'true' uses price_foil, 'false' excludes foil prices, None uses regular prices."),
    db: AsyncSession = Depends(get_db),
):
    # Convert string query parameter to boolean
    is_foil_bool: Optional[bool] = None
    if is_foil is not None:
        is_foil_bool = is_foil.lower() in ('true', '1', 'yes')
    """
    Get market index data for the current user's inventory items.
    
    Calculates a weighted index based on the user's inventory items' price history.
    
    Args:
        range: Time range (7d, 30d, 90d, 1y)
        currency: Filter by currency (USD or EUR). If not specified, aggregates all currencies.
        separate_currencies: If True, returns separate indices for USD and EUR.
    """
    # Determine date range and bucket size
    now = datetime.now(timezone.utc)
    if range == "7d":
        start_date = now - timedelta(days=7)
        bucket_minutes = 30
    elif range == "30d":
        start_date = now - timedelta(days=30)
        bucket_minutes = 60
    elif range == "90d":
        start_date = now - timedelta(days=90)
        bucket_minutes = 240
    else:  # 1y
        start_date = now - timedelta(days=365)
        bucket_minutes = 1440
    
    end_date = now
    
    try:
        # Get user's inventory items with their card IDs
        inventory_query = select(InventoryItem.card_id, InventoryItem.quantity).where(
            InventoryItem.user_id == current_user.id
        )
        inventory_result = await db.execute(inventory_query)
        inventory_items = inventory_result.all()
        
        if not inventory_items:
            # Return empty data if no inventory
            return {
                "range": range,
                "currency": currency or "ALL",
                "points": [],
                "isMockData": False,
            }
        
        # Get unique card IDs and create a quantity map
        card_ids = [item.card_id for item in inventory_items]
        quantity_map = {item.card_id: item.quantity for item in inventory_items}
        
        # Get time-bucketed average prices from price snapshots for inventory cards
        bucket_seconds = bucket_minutes * 60
        bucket_expr = func.to_timestamp(
            func.floor(func.extract('epoch', PriceSnapshot.snapshot_time) / bucket_seconds) * bucket_seconds
        )
        
        # Handle separate currencies mode
        if separate_currencies:
            usd_points = await _get_inventory_currency_index(
                "USD", start_date, bucket_expr, bucket_minutes, card_ids, quantity_map, db, is_foil_bool
            )
            eur_points = await _get_inventory_currency_index(
                "EUR", start_date, bucket_expr, bucket_minutes, card_ids, quantity_map, db, is_foil_bool
            )
            
            # Apply interpolation
            usd_points = interpolate_missing_points(usd_points, start_date, end_date, bucket_minutes)
            eur_points = interpolate_missing_points(eur_points, start_date, end_date, bucket_minutes)
            
            return {
                "range": range,
                "separate_currencies": True,
                "currencies": {
                    "USD": {"currency": "USD", "points": usd_points},
                    "EUR": {"currency": "EUR", "points": eur_points},
                },
                "isMockData": False,
            }
        
        # Determine which price field to use based on foil filter
        if is_foil_bool is True:
            # Use foil prices only
            price_field = PriceSnapshot.price_foil
            price_condition = PriceSnapshot.price_foil.isnot(None)
        elif is_foil_bool is False:
            # Exclude foil prices (only non-foil)
            price_field = PriceSnapshot.price
            price_condition = PriceSnapshot.price_foil.is_(None)
        else:
            # Default: use regular prices
            price_field = PriceSnapshot.price
            price_condition = PriceSnapshot.price.isnot(None)
        
        query = select(
            bucket_expr.label("bucket_time"),
            PriceSnapshot.card_id,
            func.avg(price_field).label("avg_price"),
        ).where(
            and_(
                PriceSnapshot.snapshot_time >= start_date,
                PriceSnapshot.card_id.in_(card_ids),
                price_condition,
                price_field > 0,
            )
        )
        
        # Filter by currency if specified
        if currency:
            query = query.where(PriceSnapshot.currency == currency)
        
        query = query.group_by(
            bucket_expr,
            PriceSnapshot.card_id
        ).order_by(
            bucket_expr
        )
        
        result = await asyncio.wait_for(
            db.execute(query),
            timeout=25
        )
        rows = result.all()
        
        # Group by time bucket and calculate weighted average
        bucket_data = {}
        for row in rows:
            bucket_time = row.bucket_time
            if isinstance(bucket_time, datetime):
                timestamp_str = bucket_time.isoformat()
            else:
                timestamp_str = str(bucket_time)
            
            if timestamp_str not in bucket_data:
                bucket_data[timestamp_str] = {"total_value": 0.0, "total_quantity": 0}
            
            quantity = quantity_map.get(row.card_id, 1)
            value = float(row.avg_price) * quantity
            bucket_data[timestamp_str]["total_value"] += value
            bucket_data[timestamp_str]["total_quantity"] += quantity
        
        # Convert to points and normalize to base 100 using fixed base point
        points = []
        base_date = start_date + timedelta(days=1)
        
        # Calculate base value from first day's data
        if is_foil_bool is True:
            base_price_field = PriceSnapshot.price_foil
            base_condition = PriceSnapshot.price_foil.isnot(None)
        elif is_foil_bool is False:
            base_price_field = PriceSnapshot.price
            base_condition = PriceSnapshot.price_foil.is_(None)
        else:
            base_price_field = PriceSnapshot.price
            base_condition = PriceSnapshot.price.isnot(None)
        # Build CASE statement for quantity mapping
        quantity_case = case(
            *[(PriceSnapshot.card_id == card_id, quantity) for card_id, quantity in quantity_map.items()],
            else_=1
        )
        
        base_query = select(
            func.sum(base_price_field * quantity_case).label("total_value"),
            func.sum(quantity_case).label("total_quantity")
        ).where(
            and_(
                PriceSnapshot.snapshot_time >= start_date,
                PriceSnapshot.snapshot_time < base_date,
                PriceSnapshot.card_id.in_(card_ids),
                base_condition,
                base_price_field > 0,
            )
        )
        if currency:
            base_query = base_query.where(PriceSnapshot.currency == currency)
        
        base_result = await db.execute(base_query)
        base_row = base_result.first()
        base_value = None
        if base_row and base_row.total_quantity and base_row.total_quantity > 0:
            base_value = float(base_row.total_value) / float(base_row.total_quantity)
        
        for timestamp_str in sorted(bucket_data.keys()):
            data = bucket_data[timestamp_str]
            if data["total_quantity"] > 0:
                avg_value = data["total_value"] / data["total_quantity"]
                
                # Use calculated base value or first point as fallback
                if base_value is None:
                    base_value = avg_value
                
                # Normalize to base 100
                index_value = (avg_value / base_value) * 100.0 if base_value > 0 else 100.0
                
                points.append({
                    "timestamp": timestamp_str,
                    "indexValue": round(index_value, 2),
                })
        
        if not points:
            # Log diagnostic info when no data found
            total_snapshots = await db.scalar(
                select(func.count(PriceSnapshot.id))
            ) or 0
            
            recent_snapshots = await db.scalar(
                select(func.count(PriceSnapshot.id)).where(
                    PriceSnapshot.snapshot_time >= start_date,
                    PriceSnapshot.card_id.in_(card_ids) if card_ids else True
                )
            ) or 0
            
            logger.info(
                "No inventory market index data found",
                range=range,
                currency=currency or "ALL",
                is_foil=is_foil_bool,
                inventory_card_count=len(card_ids) if card_ids else 0,
                total_snapshots_in_db=total_snapshots,
                recent_snapshots_in_range=recent_snapshots,
                start_date=start_date.isoformat(),
            )
            
            # Return empty data if no points
            return {
                "range": range,
                "currency": currency or "ALL",
                "points": [],
                "isMockData": False,
            }
        
        # Apply interpolation to fill gaps
        points = interpolate_missing_points(points, start_date, end_date, bucket_minutes)
        
        return {
            "range": range,
            "currency": currency or "ALL",
            "points": points,
            "isMockData": False,
        }
        
    except Exception as e:
        logger.error("Error fetching inventory market index", error=str(e), error_type=type(e).__name__, range=range)
        # Return empty data on error (connection errors handled gracefully)
        if is_database_connection_error(e):
            return {
                "range": range,
                "currency": currency or "ALL",
                "points": [],
                "isMockData": False,
            }
        # For other errors, re-raise to get proper HTTP error response
        raise HTTPException(status_code=500, detail="Failed to fetch inventory market index")


async def _get_inventory_currency_index(
    currency: str,
    start_date: datetime,
    bucket_expr,
    bucket_minutes: int,
    card_ids: List[int],
    quantity_map: Dict[int, int],
    db: AsyncSession,
    is_foil: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """
    Helper function to get inventory index points for a specific currency.
    """
    # Determine which price field to use based on foil filter
    if is_foil is True:
        # Use foil prices only
        price_field = PriceSnapshot.price_foil
        price_condition = PriceSnapshot.price_foil.isnot(None)
    elif is_foil is False:
        # Exclude foil prices (only non-foil)
        price_field = PriceSnapshot.price
        price_condition = PriceSnapshot.price_foil.is_(None)
    else:
        # Default: use regular prices
        price_field = PriceSnapshot.price
        price_condition = PriceSnapshot.price.isnot(None)
    
    query = select(
        bucket_expr.label("bucket_time"),
        PriceSnapshot.card_id,
        func.avg(price_field).label("avg_price"),
    ).where(
        and_(
            PriceSnapshot.snapshot_time >= start_date,
            PriceSnapshot.card_id.in_(card_ids),
            PriceSnapshot.currency == currency,
            price_condition,
            price_field > 0,
        )
    ).group_by(
        bucket_expr,
        PriceSnapshot.card_id
    ).order_by(
        bucket_expr
    )
    
    try:
        result = await asyncio.wait_for(
            db.execute(query),
            timeout=25
        )
        rows = result.all()
    except Exception as e:
        logger.error(f"Error fetching inventory {currency} index", error=str(e))
        return []
    
    # Group by time bucket and calculate weighted average
    bucket_data = {}
    for row in rows:
        bucket_time = row.bucket_time
        if isinstance(bucket_time, datetime):
            timestamp_str = bucket_time.isoformat()
        else:
            timestamp_str = str(bucket_time)
        
        if timestamp_str not in bucket_data:
            bucket_data[timestamp_str] = {"total_value": 0.0, "total_quantity": 0}
        
        quantity = quantity_map.get(row.card_id, 1)
        value = float(row.avg_price) * quantity
        bucket_data[timestamp_str]["total_value"] += value
        bucket_data[timestamp_str]["total_quantity"] += quantity
    
    # Calculate base value from first day
    base_date = start_date + timedelta(days=1)
    if is_foil is True:
        base_price_field = PriceSnapshot.price_foil
        base_condition = PriceSnapshot.price_foil.isnot(None)
    elif is_foil is False:
        base_price_field = PriceSnapshot.price
        base_condition = PriceSnapshot.price_foil.is_(None)
    else:
        base_price_field = PriceSnapshot.price
        base_condition = PriceSnapshot.price.isnot(None)
    # Build CASE statement for quantity mapping
    quantity_case = case(
        *[(PriceSnapshot.card_id == card_id, quantity) for card_id, quantity in quantity_map.items()],
        else_=1
    )
    
    base_query = select(
        func.sum(base_price_field * quantity_case).label("total_value"),
        func.sum(quantity_case).label("total_quantity")
    ).where(
        and_(
            PriceSnapshot.snapshot_time >= start_date,
            PriceSnapshot.snapshot_time < base_date,
            PriceSnapshot.card_id.in_(card_ids),
            PriceSnapshot.currency == currency,
            base_condition,
            base_price_field > 0,
        )
    )
    
    base_result = await db.execute(base_query)
    base_row = base_result.first()
    base_value = None
    if base_row and base_row.total_quantity and base_row.total_quantity > 0:
        base_value = float(base_row.total_value) / float(base_row.total_quantity)
    
    points = []
    for timestamp_str in sorted(bucket_data.keys()):
        data = bucket_data[timestamp_str]
        if data["total_quantity"] > 0:
            avg_value = data["total_value"] / data["total_quantity"]
            
            if base_value is None:
                base_value = avg_value
            
            # Normalize to base 100
            index_value = (avg_value / base_value) * 100.0 if base_value > 0 else 100.0
            
            points.append({
                "timestamp": timestamp_str,
                "indexValue": round(index_value, 2),
            })
    
    return points


@router.get("/top-movers")
async def get_inventory_top_movers(
    current_user: CurrentUser,
    window: str = Query("24h", regex="^(24h|7d)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get top gaining and losing cards from the current user's inventory.
    """
    # Determine time window
    if window == "24h":
        change_field = MetricsCardsDaily.price_change_pct_1d
    else:  # 7d
        change_field = MetricsCardsDaily.price_change_pct_7d
    
    try:
        # Get user's inventory card IDs
        inventory_query = select(InventoryItem.card_id).where(
            InventoryItem.user_id == current_user.id
        )
        inventory_result = await db.execute(inventory_query)
        inventory_card_ids = [row.card_id for row in inventory_result.all()]
        
        if not inventory_card_ids:
            return {
                "window": window,
                "gainers": [],
                "losers": [],
                "isMockData": False,
            }
        
        latest_date = await asyncio.wait_for(
            db.scalar(select(func.max(MetricsCardsDaily.date))),
            timeout=25
        )
        
        if not latest_date:
            return {
                "window": window,
                "gainers": [],
                "losers": [],
                "isMockData": False,
            }
        
        # Get top gainers from inventory
        gainers_query = select(MetricsCardsDaily, Card).join(
            Card, MetricsCardsDaily.card_id == Card.id
        ).where(
            MetricsCardsDaily.date == latest_date,
            MetricsCardsDaily.card_id.in_(inventory_card_ids),
            change_field.isnot(None),
            change_field > 0,
        ).order_by(
            desc(change_field)
        ).limit(10)
        
        gainers_result = await asyncio.wait_for(
            db.execute(gainers_query),
            timeout=25
        )
        gainers_rows = gainers_result.all()
        
        # Get top losers from inventory
        losers_query = select(MetricsCardsDaily, Card).join(
            Card, MetricsCardsDaily.card_id == Card.id
        ).where(
            MetricsCardsDaily.date == latest_date,
            MetricsCardsDaily.card_id.in_(inventory_card_ids),
            change_field.isnot(None),
            change_field < 0,
        ).order_by(
            change_field.asc()
        ).limit(10)
        
        losers_result = await asyncio.wait_for(
            db.execute(losers_query),
            timeout=25
        )
        losers_rows = losers_result.all()
        
    except Exception as e:
        logger.error("Error fetching inventory top movers", error=str(e), error_type=type(e).__name__, window=window)
        # Return empty data on connection errors, raise for other errors
        if is_database_connection_error(e):
            return {
                "window": window,
                "gainers": [],
                "losers": [],
                "isMockData": False,
            }
        raise HTTPException(status_code=500, detail="Failed to fetch inventory top movers")
    
    # Format gainers
    gainers = []
    for metrics, card in gainers_rows:
        volume = metrics.total_listings or 0
        
        if window == "24h":
            change_value = metrics.price_change_pct_1d
        else:
            change_value = metrics.price_change_pct_7d
        
        # Try to determine format from legalities
        format_name = "Standard"
        if card.legalities:
            try:
                legalities = json.loads(card.legalities)
                for fmt, status in legalities.items():
                    if status == "legal":
                        format_name = fmt
                        break
            except (json.JSONDecodeError, TypeError):
                pass
        
        gainers.append({
            "cardName": card.name,
            "setCode": card.set_code,
            "format": format_name,
            "currentPriceUsd": float(metrics.avg_price) if metrics.avg_price else 0.0,
            "changePct": float(change_value) if change_value is not None else 0.0,
            "volume": volume,
        })
    
    # Format losers
    losers = []
    for metrics, card in losers_rows:
        volume = metrics.total_listings or 0
        
        if window == "24h":
            change_value = metrics.price_change_pct_1d
        else:
            change_value = metrics.price_change_pct_7d
        
        format_name = "Standard"
        if card.legalities:
            try:
                legalities = json.loads(card.legalities)
                for fmt, status in legalities.items():
                    if status == "legal":
                        format_name = fmt
                        break
            except (json.JSONDecodeError, TypeError):
                pass
        
        losers.append({
            "cardName": card.name,
            "setCode": card.set_code,
            "format": format_name,
            "currentPriceUsd": float(metrics.avg_price) if metrics.avg_price else 0.0,
            "changePct": float(change_value) if change_value is not None else 0.0,
            "volume": volume,
        })
    
    return {
        "window": window,
        "gainers": gainers,
        "losers": losers,
        "isMockData": False,
    }


@router.get("/{item_id}", response_model=InventoryItemResponse)
async def get_inventory_item(
    item_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific inventory item by ID (must belong to current user).
    """
    query = select(InventoryItem, Card).join(
        Card, InventoryItem.card_id == Card.id
    ).where(
        and_(
            InventoryItem.id == item_id,
            InventoryItem.user_id == current_user.id
        )
    )
    
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
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Update an inventory item (must belong to current user).
    """
    query = select(InventoryItem, Card).join(
        Card, InventoryItem.card_id == Card.id
    ).where(
        and_(
            InventoryItem.id == item_id,
            InventoryItem.user_id == current_user.id
        )
    )
    
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
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an inventory item (must belong to current user).
    """
    query = select(InventoryItem).where(
        and_(
            InventoryItem.id == item_id,
            InventoryItem.user_id == current_user.id
        )
    )
    result = await db.execute(query)
    inv_item = result.scalar_one_or_none()
    
    if not inv_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    await db.delete(inv_item)
    await db.commit()
    
    return {"message": "Item deleted successfully"}


@router.get("/recommendations/list", response_model=InventoryRecommendationListResponse)
async def get_inventory_recommendations(
    current_user: CurrentUser,
    action: Optional[ActionType] = None,
    urgency: Optional[InventoryUrgency] = None,
    min_confidence: Optional[float] = Query(None, ge=0, le=1),
    is_active: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get inventory-specific recommendations for the current user.
    
    These recommendations are more aggressive than market-wide ones,
    with lower thresholds and shorter time horizons.
    """
    # Build base query - filter by current user's inventory items
    query = select(InventoryRecommendation, InventoryItem, Card).join(
        InventoryItem, InventoryRecommendation.inventory_item_id == InventoryItem.id
    ).join(
        Card, InventoryRecommendation.card_id == Card.id
    ).where(InventoryItem.user_id == current_user.id)
    
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
    
    # Get counts by urgency and action for current user
    urgency_query = select(
        func.count(case((InventoryRecommendation.urgency == "CRITICAL", 1))).label("critical"),
        func.count(case((InventoryRecommendation.urgency == "HIGH", 1))).label("high"),
        func.count(case((InventoryRecommendation.urgency == "NORMAL", 1))).label("normal"),
        func.count(case((InventoryRecommendation.urgency == "LOW", 1))).label("low"),
        func.count(case((InventoryRecommendation.action == "SELL", 1))).label("sell"),
        func.count(case((InventoryRecommendation.action == "HOLD", 1))).label("hold"),
    ).join(
        InventoryItem, InventoryRecommendation.inventory_item_id == InventoryItem.id
    ).where(
        and_(
            InventoryRecommendation.is_active == True,
            InventoryItem.user_id == current_user.id
        )
    )
    
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
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh current valuations for all of the current user's inventory items based on latest metrics.
    """
    # Get current user's inventory items
    query = select(InventoryItem).where(InventoryItem.user_id == current_user.id)
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
            item.last_valued_at = datetime.now(timezone.utc)
            
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
    current_user: CurrentUser,
    request: Optional[RunRecommendationsRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate aggressive recommendations for the current user's inventory items.
    
    This uses lower thresholds and shorter time horizons than market recommendations.
    """
    from app.services.agents.inventory_recommendation import InventoryRecommendationAgent
    
    agent = InventoryRecommendationAgent(db)
    item_ids = request.item_ids if request else None
    result = await agent.run_inventory_recommendations(item_ids, user_id=current_user.id)
    
    return result


@router.get("/export")
async def export_inventory(
    current_user: CurrentUser,
    format: str = Query("csv", regex="^(csv|txt)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Export user's inventory to CSV or plain text.
    
    Args:
        format: Export format - 'csv' or 'txt'
    """
    query = select(InventoryItem, Card).join(
        Card, InventoryItem.card_id == Card.id
    ).where(InventoryItem.user_id == current_user.id).order_by(Card.name)
    
    result = await db.execute(query)
    items = result.all()
    
    if format == "csv":
        output = io.StringIO()
        # Use quoting to handle special characters in card names
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([
            "Card Name", "Set", "Quantity", "Condition", "Foil", 
            "Language", "Acquisition Price", "Current Value", "Profit/Loss"
        ])
        for item, card in items:
            writer.writerow([
                card.name, 
                card.set_code, 
                item.quantity, 
                item.condition,
                "Yes" if item.is_foil else "No", 
                item.language or "",
                item.acquisition_price if item.acquisition_price else "",
                item.current_value if item.current_value else "",
                item.profit_loss if item.profit_loss else ""
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=inventory.csv"}
        )
    else:  # txt
        lines = []
        for item, card in items:
            foil_text = " FOIL" if item.is_foil else ""
            lines.append(
                f"{item.quantity}x {card.name} [{card.set_code}]{foil_text} {item.condition}"
            )
        return Response(
            content="\n".join(lines),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=inventory.txt"}
        )
