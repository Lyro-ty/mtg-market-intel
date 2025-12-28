"""
Vectorization integration for ingestion pipeline.

Note: The vectorize_listing and vectorize_listings_batch functions are DEPRECATED.
The Listing model has been replaced by PriceSnapshot, which uses a composite primary key
and is stored in a TimescaleDB hypertable. Individual listings are no longer vectorized;
only cards are vectorized via vectorize_card and vectorize_card_by_attrs.
"""
import warnings
from typing import Any, TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, CardFeatureVector
from app.services.vectorization.service import VectorizationService

if TYPE_CHECKING:
    # Only import for type hints - avoid triggering deprecation warning at import time
    from app.models.listing import Listing
    from app.models.feature_vector import ListingFeatureVector

logger = structlog.get_logger()


async def vectorize_card(
    db: AsyncSession,
    card: Card,
    vectorizer: VectorizationService,
) -> CardFeatureVector | None:
    """
    Vectorize a card and store the feature vector.
    
    Args:
        db: Database session.
        card: Card to vectorize.
        vectorizer: Vectorization service instance.
        
    Returns:
        CardFeatureVector if successful, None otherwise.
    """
    try:
        # Store card_id to avoid lazy loading issues
        card_id = card.id
        
        # Prepare card data
        card_data = {
            "name": card.name,
            "type_line": card.type_line,
            "oracle_text": card.oracle_text,
            "rarity": card.rarity,
            "cmc": card.cmc,
            "colors": card.colors,
            "mana_cost": card.mana_cost,
        }
        
        # Vectorize
        feature_vector = vectorizer.vectorize_card(card_data)
        
        # Check if vector already exists
        existing_query = select(CardFeatureVector).where(CardFeatureVector.card_id == card_id)
        result = await db.execute(existing_query)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing vector
            existing.set_vector(feature_vector)
            existing.model_version = vectorizer.embedding_model_name
            return existing
        else:
            # Create new vector
            card_vector = CardFeatureVector(
                card_id=card_id,
                model_version=vectorizer.embedding_model_name,
            )
            card_vector.set_vector(feature_vector)
            db.add(card_vector)
            return card_vector
            
    except Exception as e:
        # Try to get card_id safely for logging
        card_id = getattr(card, 'id', None)
        logger.warning("Failed to vectorize card", card_id=card_id, error=str(e))
        return None


async def vectorize_card_by_attrs(
    db: AsyncSession,
    card_id: int,
    card_attrs: dict[str, Any],
    vectorizer: VectorizationService,
) -> CardFeatureVector | None:
    """
    Vectorize a card by attributes (avoids lazy loading issues).
    
    Args:
        db: Database session.
        card_id: Card ID.
        card_attrs: Dictionary with card attributes (name, type_line, oracle_text, etc.).
        vectorizer: Vectorization service instance.
        
    Returns:
        CardFeatureVector if successful, None otherwise.
    """
    try:
        # Vectorize
        feature_vector = vectorizer.vectorize_card(card_attrs)
        
        # Check if vector already exists
        existing_query = select(CardFeatureVector).where(CardFeatureVector.card_id == card_id)
        result = await db.execute(existing_query)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing vector
            existing.set_vector(feature_vector)
            existing.model_version = vectorizer.embedding_model_name
            return existing
        else:
            # Create new vector
            card_vector = CardFeatureVector(
                card_id=card_id,
                model_version=vectorizer.embedding_model_name,
            )
            card_vector.set_vector(feature_vector)
            db.add(card_vector)
            return card_vector
            
    except Exception as e:
        logger.warning("Failed to vectorize card by attributes", card_id=card_id, error=str(e))
        return None


async def vectorize_listing(
    db: AsyncSession,
    listing: "Listing",
    card_vector: CardFeatureVector | None,
    vectorizer: VectorizationService,
) -> "ListingFeatureVector | None":
    """
    DEPRECATED: Vectorize a listing and store the feature vector.

    This function is deprecated because the Listing model has been replaced by
    PriceSnapshot, which uses a composite primary key and TimescaleDB hypertable.
    Individual listings/price snapshots are no longer vectorized.

    Use vectorize_card() or vectorize_card_by_attrs() for card-level vectorization.

    Args:
        db: Database session.
        listing: Listing to vectorize.
        card_vector: Pre-computed card feature vector (optional).
        vectorizer: Vectorization service instance.

    Returns:
        ListingFeatureVector if successful, None otherwise.
    """
    warnings.warn(
        "vectorize_listing is deprecated. Listings are no longer vectorized; "
        "use vectorize_card() for card-level vectors instead.",
        DeprecationWarning,
        stacklevel=2
    )

    # Import deprecated models
    from app.models.listing import Listing as ListingModel
    from app.models.feature_vector import ListingFeatureVector

    try:
        # Get card vector if not provided
        if card_vector is None:
            card_vector_query = select(CardFeatureVector).where(
                CardFeatureVector.card_id == listing.card_id
            )
            result = await db.execute(card_vector_query)
            card_vector = result.scalar_one_or_none()
        
        # Prepare listing data
        listing_data = {
            "price": float(listing.price),
            "quantity": listing.quantity,
            "condition": listing.condition,
            "language": listing.language,
            "is_foil": listing.is_foil,
            "seller_rating": float(listing.seller_rating) if listing.seller_rating else None,
            "marketplace_id": listing.marketplace_id,
        }
        
        # Get card vector array if available
        card_vector_array = None
        if card_vector:
            try:
                card_vector_array = card_vector.get_vector()
            except Exception as e:
                logger.debug("Failed to get card vector", listing_id=listing.id, error=str(e))
        
        # Vectorize
        feature_vector = vectorizer.vectorize_listing(listing_data, card_vector_array)
        
        # Check if vector already exists
        existing_query = select(ListingFeatureVector).where(
            ListingFeatureVector.listing_id == listing.id
        )
        result = await db.execute(existing_query)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing vector
            existing.set_vector(feature_vector)
            existing.model_version = vectorizer.embedding_model_name
            return existing
        else:
            # Create new vector
            listing_vector = ListingFeatureVector(
                listing_id=listing.id,
                model_version=vectorizer.embedding_model_name,
            )
            listing_vector.set_vector(feature_vector)
            db.add(listing_vector)
            return listing_vector
            
    except Exception as e:
        logger.warning("Failed to vectorize listing", listing_id=listing.id, error=str(e))
        return None


async def vectorize_listings_batch(
    db: AsyncSession,
    listings: "list[Listing]",
    vectorizer: VectorizationService,
    batch_size: int = 50,
) -> int:
    """
    DEPRECATED: Vectorize a batch of listings efficiently.

    This function is deprecated because the Listing model has been replaced by
    PriceSnapshot, which uses a composite primary key and TimescaleDB hypertable.
    Individual listings/price snapshots are no longer vectorized.

    Use vectorize_card() or vectorize_card_by_attrs() for card-level vectorization.

    Args:
        db: Database session.
        listings: List of listings to vectorize.
        vectorizer: Vectorization service instance.
        batch_size: Number of listings to process at once.

    Returns:
        Number of listings successfully vectorized.
    """
    warnings.warn(
        "vectorize_listings_batch is deprecated. Listings are no longer vectorized; "
        "use vectorize_card() for card-level vectors instead.",
        DeprecationWarning,
        stacklevel=2
    )

    if not listings:
        return 0
    
    # Get card IDs
    card_ids = {listing.card_id for listing in listings}
    
    # Fetch card vectors in batch
    card_vectors_query = select(CardFeatureVector).where(
        CardFeatureVector.card_id.in_(card_ids)
    )
    result = await db.execute(card_vectors_query)
    card_vectors = {cv.card_id: cv for cv in result.scalars().all()}
    
    vectorized_count = 0
    
    # Process in batches
    for i in range(0, len(listings), batch_size):
        batch = listings[i:i + batch_size]
        
        for listing in batch:
            card_vector = card_vectors.get(listing.card_id)
            vector = await vectorize_listing(db, listing, card_vector, vectorizer)
            if vector:
                vectorized_count += 1
        
        # Flush after each batch
        await db.flush()
    
    return vectorized_count

