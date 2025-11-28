"""
Settings API endpoints.
"""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import AppSettings
from app.models.settings import DEFAULT_SETTINGS
from app.schemas.settings import SettingsResponse, SettingsUpdate

router = APIRouter()


async def _get_setting_value(db: AsyncSession, key: str) -> Any:
    """Get a setting value, returning default if not found."""
    query = select(AppSettings).where(AppSettings.key == key)
    result = await db.execute(query)
    setting = result.scalar_one_or_none()
    
    if setting:
        return _parse_setting_value(setting.value, setting.value_type)
    
    # Return default if exists
    if key in DEFAULT_SETTINGS:
        default = DEFAULT_SETTINGS[key]
        return _parse_setting_value(default["value"], default["value_type"])
    
    return None


def _parse_setting_value(value: str, value_type: str) -> Any:
    """Parse a setting value based on its type."""
    if value_type == "json":
        return json.loads(value)
    elif value_type == "float":
        return float(value)
    elif value_type == "integer":
        return int(value)
    elif value_type == "boolean":
        return value.lower() == "true"
    return value


async def _set_setting_value(
    db: AsyncSession,
    key: str,
    value: Any,
    value_type: str,
    description: str | None = None,
) -> None:
    """Set a setting value."""
    # Convert value to string
    if value_type == "json":
        str_value = json.dumps(value)
    elif value_type == "boolean":
        str_value = "true" if value else "false"
    else:
        str_value = str(value)
    
    query = select(AppSettings).where(AppSettings.key == key)
    result = await db.execute(query)
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.value = str_value
        setting.value_type = value_type
        if description:
            setting.description = description
    else:
        setting = AppSettings(
            key=key,
            value=str_value,
            value_type=value_type,
            description=description or DEFAULT_SETTINGS.get(key, {}).get("description"),
        )
        db.add(setting)


@router.get("", response_model=SettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
):
    """
    Get all application settings.
    """
    # Get all settings from database
    query = select(AppSettings)
    result = await db.execute(query)
    db_settings = result.scalars().all()
    
    # Build settings dict, starting with defaults
    settings = {}
    for key, default in DEFAULT_SETTINGS.items():
        settings[key] = _parse_setting_value(default["value"], default["value_type"])
    
    # Override with database values
    for setting in db_settings:
        settings[setting.key] = _parse_setting_value(setting.value, setting.value_type)
    
    return SettingsResponse(
        settings=settings,
        enabled_marketplaces=settings.get("enabled_marketplaces", []),
        min_roi_threshold=settings.get("min_roi_threshold", 0.10),
        min_confidence_threshold=settings.get("min_confidence_threshold", 0.60),
        recommendation_horizon_days=settings.get("recommendation_horizon_days", 7),
        price_history_days=settings.get("price_history_days", 90),
        scraping_enabled=settings.get("scraping_enabled", True),
        analytics_enabled=settings.get("analytics_enabled", True),
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    updates: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update application settings.
    
    Only provided fields will be updated.
    """
    # Process each field that was provided
    if updates.enabled_marketplaces is not None:
        await _set_setting_value(
            db, "enabled_marketplaces", updates.enabled_marketplaces, "json"
        )
    
    if updates.min_roi_threshold is not None:
        await _set_setting_value(
            db, "min_roi_threshold", updates.min_roi_threshold, "float"
        )
    
    if updates.min_confidence_threshold is not None:
        await _set_setting_value(
            db, "min_confidence_threshold", updates.min_confidence_threshold, "float"
        )
    
    if updates.recommendation_horizon_days is not None:
        await _set_setting_value(
            db, "recommendation_horizon_days", updates.recommendation_horizon_days, "integer"
        )
    
    if updates.price_history_days is not None:
        await _set_setting_value(
            db, "price_history_days", updates.price_history_days, "integer"
        )
    
    if updates.scraping_enabled is not None:
        await _set_setting_value(
            db, "scraping_enabled", updates.scraping_enabled, "boolean"
        )
    
    if updates.analytics_enabled is not None:
        await _set_setting_value(
            db, "analytics_enabled", updates.analytics_enabled, "boolean"
        )
    
    await db.commit()
    
    # Return updated settings
    return await get_settings(db)


@router.get("/{key}")
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific setting by key.
    """
    value = await _get_setting_value(db, key)
    
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting not found: {key}")
    
    return {"key": key, "value": value}

