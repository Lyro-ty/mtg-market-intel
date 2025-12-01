"""
Vectorization integration for ingestion pipeline.
"""
import json
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, Listing, CardFeatureVector, ListingFeatureVector
from app.services.vectorization.service import VectorizationService

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
        existing_query = select(CardFeatureVector).where(CardFeatureVector.card_id == card.id)
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
                card_id=card.id,
                model_version=vectorizer.embedding_model_name,
            )
            card_vector.set_vector(feature_vector)
            db.add(card_vector)
            return card_vector
            
    except Exception as e:
        logger.warning("Failed to vectorize card", card_id=card.id, error=str(e))
        return None


async def vectorize_listing(
    db: AsyncSession,
    listing: Listing,
    card_vector: CardFeatureVector | None,
    vectorizer: VectorizationService,
) -> ListingFeatureVector | None:
    """
    Vectorize a listing and store the feature vector.
    
    Args:
        db: Database session.
        listing: Listing to vectorize.
        card_vector: Pre-computed card feature vector (optional).
        vectorizer: Vectorization service instance.
        
    Returns:
        ListingFeatureVector if successful, None otherwise.
    """
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
    listings: list[Listing],
    vectorizer: VectorizationService,
    batch_size: int = 50,
) -> int:
    """
    Vectorize a batch of listings efficiently.
    
    Args:
        db: Database session.
        listings: List of listings to vectorize.
        vectorizer: Vectorization service instance.
        batch_size: Number of listings to process at once.
        
    Returns:
        Number of listings successfully vectorized.
    """
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

