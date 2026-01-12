"""
Tests verifying the Listing model has been removed and Card uses PriceSnapshot.

This test file documents the migration from the deprecated Listing model
to the PriceSnapshot model for storing price data.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models import Card, PriceSnapshot, Marketplace


@pytest.mark.asyncio
async def test_card_price_snapshots_relationship(db_session, test_card):
    """Card should use price_snapshots, not listings."""
    # Verify relationship exists on the Card class
    assert hasattr(Card, 'price_snapshots'), "Card should have price_snapshots relationship"

    # Verify we can query through relationship using eager loading
    result = await db_session.execute(
        select(Card)
        .options(selectinload(Card.price_snapshots))
        .where(Card.id == test_card.id)
    )
    card = result.scalar_one()

    # Access should not raise - relationship should be accessible
    snapshots = card.price_snapshots
    assert isinstance(snapshots, list), "price_snapshots should return a list"


@pytest.mark.asyncio
async def test_card_has_no_listings_relationship(db_session):
    """Card should NOT have listings relationship after migration."""
    assert not hasattr(Card, 'listings'), "Listing relationship should be removed from Card"


@pytest.mark.asyncio
async def test_marketplace_has_no_listings_relationship(db_session):
    """Marketplace should NOT have listings relationship after migration."""
    assert not hasattr(Marketplace, 'listings'), "Listing relationship should be removed from Marketplace"


@pytest.mark.asyncio
async def test_listing_model_not_importable():
    """Listing model should not be importable after removal."""
    with pytest.raises((ImportError, ModuleNotFoundError)):
        from app.models.listing import Listing  # noqa: F401


@pytest.mark.asyncio
async def test_listing_not_in_models_all():
    """Listing should not be exported from app.models."""
    import app.models
    assert 'Listing' not in app.models.__all__, "Listing should not be in __all__"


@pytest.mark.asyncio
async def test_marketplace_price_snapshots_relationship(db_session):
    """Marketplace should have price_snapshots relationship for price data."""
    assert hasattr(Marketplace, 'price_snapshots'), "Marketplace should have price_snapshots relationship"
