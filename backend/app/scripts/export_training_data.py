"""
Export vectorized training data for ML models.

This script exports pre-vectorized feature vectors and labels
ready for immediate use in training pipelines.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models import (
    Card,
    Listing,
    CardFeatureVector,
    ListingFeatureVector,
    PriceSnapshot,
)

logger = structlog.get_logger()


async def export_training_data(
    output_dir: Path,
    min_listings_per_card: int = 5,
    include_labels: bool = True,
) -> dict[str, Any]:
    """
    Export vectorized training data.
    
    Args:
        output_dir: Directory to save exported data.
        min_listings_per_card: Minimum listings per card to include.
        include_labels: Whether to include price labels for supervised learning.
        
    Returns:
        Export statistics.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create database session
    engine = create_async_engine(
        settings.database_url_computed,
        echo=False,
        pool_pre_ping=True,
    )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with session_maker() as db:
            # Get all cards with feature vectors
            cards_query = select(Card).join(CardFeatureVector).distinct()
            result = await db.execute(cards_query)
            cards = result.scalars().all()
            
            logger.info("Found cards with vectors", count=len(cards))
            
            # Collect training data
            card_vectors = []
            listing_vectors = []
            labels = []
            metadata = []
            
            for card in cards:
                # Get card vector
                card_vector_query = select(CardFeatureVector).where(
                    CardFeatureVector.card_id == card.id
                )
                card_vector_result = await db.execute(card_vector_query)
                card_vector_obj = card_vector_result.scalar_one_or_none()
                
                if not card_vector_obj:
                    continue
                
                card_vec = card_vector_obj.get_vector()
                
                # Get listings for this card
                listings_query = select(Listing).where(Listing.card_id == card.id)
                listings_result = await db.execute(listings_query)
                card_listings = listings_result.scalars().all()
                
                if len(card_listings) < min_listings_per_card:
                    continue
                
                # Get listing vectors
                listing_ids = [listing.id for listing in card_listings]
                listing_vectors_query = select(ListingFeatureVector).where(
                    ListingFeatureVector.listing_id.in_(listing_ids)
                )
                listing_vectors_result = await db.execute(listing_vectors_query)
                listing_vector_objs = {lv.listing_id: lv for lv in listing_vectors_result.scalars().all()}
                
                # Collect data for each listing
                for listing in card_listings:
                    listing_vector_obj = listing_vector_objs.get(listing.id)
                    if not listing_vector_obj:
                        continue
                    
                    listing_vec = listing_vector_obj.get_vector()
                    
                    card_vectors.append(card_vec)
                    listing_vectors.append(listing_vec)
                    
                    if include_labels:
                        labels.append(float(listing.price))
                    
                    metadata.append({
                        "card_id": card.id,
                        "card_name": card.name,
                        "set_code": card.set_code,
                        "listing_id": listing.id,
                        "price": float(listing.price),
                        "condition": listing.condition,
                        "is_foil": listing.is_foil,
                        "marketplace_id": listing.marketplace_id,
                    })
            
            # Convert to numpy arrays
            card_vectors_array = np.array(card_vectors)
            listing_vectors_array = np.array(listing_vectors)
            labels_array = np.array(labels) if labels else None
            
            # Save data
            np.save(output_dir / "card_vectors.npy", card_vectors_array)
            np.save(output_dir / "listing_vectors.npy", listing_vectors_array)
            
            if labels_array is not None:
                np.save(output_dir / "labels.npy", labels_array)
            
            # Save metadata
            with open(output_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2, default=str)
            
            # Save feature info
            feature_info = {
                "card_feature_dim": len(card_vectors[0]) if card_vectors else 0,
                "listing_feature_dim": len(listing_vectors[0]) if listing_vectors else 0,
                "total_samples": len(card_vectors),
                "exported_at": datetime.utcnow().isoformat(),
            }
            
            with open(output_dir / "feature_info.json", "w") as f:
                json.dump(feature_info, f, indent=2)
            
            logger.info(
                "Training data exported",
                output_dir=str(output_dir),
                samples=len(card_vectors),
                card_dim=feature_info["card_feature_dim"],
                listing_dim=feature_info["listing_feature_dim"],
            )
            
            return {
                "samples": len(card_vectors),
                "card_feature_dim": feature_info["card_feature_dim"],
                "listing_feature_dim": feature_info["listing_feature_dim"],
                "output_dir": str(output_dir),
            }
            
    finally:
        await engine.dispose()


if __name__ == "__main__":
    import sys
    
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/training")
    min_listings = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    result = asyncio.run(export_training_data(output_path, min_listings))
    print(json.dumps(result, indent=2))

