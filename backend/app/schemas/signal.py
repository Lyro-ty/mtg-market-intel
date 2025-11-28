"""
Signal-related Pydantic schemas.
"""
from datetime import date
from typing import Optional, Any

from pydantic import BaseModel


class SignalResponse(BaseModel):
    """Signal response schema."""
    id: int
    card_id: int
    date: date
    signal_type: str
    value: Optional[float] = None
    confidence: Optional[float] = None
    details: Optional[dict[str, Any]] = None
    llm_insight: Optional[str] = None
    llm_provider: Optional[str] = None
    created_at: Optional[str] = None
    
    class Config:
        from_attributes = True


class SignalListResponse(BaseModel):
    """List of signals for a card."""
    card_id: int
    signals: list[SignalResponse]
    total: int

