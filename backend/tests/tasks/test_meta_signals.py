"""
Tests for meta analysis signal generation.
"""
import pytest
from datetime import date
from unittest.mock import patch, AsyncMock

from app.tasks.meta_signals import (
    META_SPIKE_THRESHOLD,
    META_DROP_THRESHOLD,
    _analyze_format,
    _create_signal,
)


@pytest.mark.asyncio
async def test_meta_spike_threshold():
    """Verify threshold constants are reasonable."""
    assert META_SPIKE_THRESHOLD == 0.20  # 20% increase
    assert META_DROP_THRESHOLD == -0.20  # 20% decrease


@pytest.mark.asyncio
async def test_create_signal(db_session, test_card):
    """Test signal creation."""
    signal = await _create_signal(
        db=db_session,
        card_id=test_card.id,
        signal_type="meta_spike",
        value=0.25,
        confidence=0.75,
        details={
            "format": "Modern",
            "change_pct": 0.25,
        }
    )

    assert signal.card_id == test_card.id
    assert signal.signal_type == "meta_spike"
    assert float(signal.value) == 0.25
    assert float(signal.confidence) == 0.75
    assert signal.date == date.today()


@pytest.mark.asyncio
async def test_create_signal_updates_existing(db_session, test_card):
    """Test that creating a signal twice on same day updates it."""
    # Create first signal
    signal1 = await _create_signal(
        db=db_session,
        card_id=test_card.id,
        signal_type="meta_spike",
        value=0.20,
        confidence=0.70,
        details={"format": "Modern"}
    )
    await db_session.flush()

    # Create second signal with different value
    signal2 = await _create_signal(
        db=db_session,
        card_id=test_card.id,
        signal_type="meta_spike",
        value=0.30,
        confidence=0.80,
        details={"format": "Modern"}
    )
    await db_session.flush()

    # Should be same record, updated
    assert signal1.id == signal2.id
    assert float(signal2.value) == 0.30
    assert float(signal2.confidence) == 0.80
