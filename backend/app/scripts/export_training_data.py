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
    Marketplace,
)

logger = structlog.get_logger()


async def export_training_data(
    output_dir: Path,
    min_listings_per_card: int = 5,
    include_labels: bool = True,
    include_historical_prices: bool = True,
) -> dict[str, Any]:
    """
    Export vectorized training data.
    
    Args:
        output_dir: Directory to save exported data.
        min_listings_per_card: Minimum listings per card to include.
        include_labels: Whether to include price labels for supervised learning.
        include_historical_prices: Whether to include MTGJSON historical price data.
        
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
            
            # Export historical price data from MTGJSON if requested
            historical_prices_data = None
            if include_historical_prices:
                historical_prices_data = await _export_historical_prices(db, output_dir)
            
            # Save feature info
            feature_info = {
                "card_feature_dim": len(card_vectors[0]) if card_vectors else 0,
                "listing_feature_dim": len(listing_vectors[0]) if listing_vectors else 0,
                "total_samples": len(card_vectors),
                "exported_at": datetime.utcnow().isoformat(),
                "includes_historical_prices": include_historical_prices,
            }
            
            if historical_prices_data:
                feature_info["historical_prices"] = {
                    "total_snapshots": historical_prices_data["total_snapshots"],
                    "cards_with_history": historical_prices_data["cards_with_history"],
                }
            
            with open(output_dir / "feature_info.json", "w") as f:
                json.dump(feature_info, f, indent=2)
            
            logger.info(
                "Training data exported",
                output_dir=str(output_dir),
                samples=len(card_vectors),
                card_dim=feature_info["card_feature_dim"],
                listing_dim=feature_info["listing_feature_dim"],
                historical_prices=historical_prices_data["total_snapshots"] if historical_prices_data else 0,
            )
            
            return {
                "samples": len(card_vectors),
                "card_feature_dim": feature_info["card_feature_dim"],
                "listing_feature_dim": feature_info["listing_feature_dim"],
                "output_dir": str(output_dir),
                "historical_prices": historical_prices_data,
            }
            
    finally:
        await engine.dispose()


async def _export_historical_prices(
    db: AsyncSession,
    output_dir: Path,
) -> dict[str, Any]:
    """
    Export historical price data from MTGJSON for training.
    
    This provides price trend data that can be used for time-series models
    or as additional features for price prediction.
    
    Args:
        db: Database session.
        output_dir: Directory to save exported data.
        
    Returns:
        Export statistics.
    """
    # Get MTGJSON marketplace
    mtgjson_query = select(Marketplace).where(Marketplace.slug == "mtgjson")
    result = await db.execute(mtgjson_query)
    mtgjson_marketplace = result.scalar_one_or_none()
    
    if not mtgjson_marketplace:
        logger.warning("MTGJSON marketplace not found - skipping historical price export")
        return {"total_snapshots": 0, "cards_with_history": 0}
    
    # Get all price snapshots from MTGJSON
    snapshots_query = (
        select(PriceSnapshot, Card)
        .join(Card, PriceSnapshot.card_id == Card.id)
        .where(PriceSnapshot.marketplace_id == mtgjson_marketplace.id)
        .order_by(Card.id, PriceSnapshot.snapshot_time)
    )
    result = await db.execute(snapshots_query)
    snapshots = result.all()
    
    if not snapshots:
        logger.info("No MTGJSON historical price data found")
        return {"total_snapshots": 0, "cards_with_history": 0}
    
    # Organize by card
    price_history = {}
    for snapshot, card in snapshots:
        if card.id not in price_history:
            price_history[card.id] = {
                "card_id": card.id,
                "card_name": card.name,
                "set_code": card.set_code,
                "prices": [],
            }
        
        price_history[card.id]["prices"].append({
            "snapshot_time": snapshot.snapshot_time.isoformat(),
            "price": float(snapshot.price),
            "currency": snapshot.currency,
            "price_foil": float(snapshot.price_foil) if snapshot.price_foil else None,
        })
    
    # Save as JSON
    history_file = output_dir / "historical_prices.json"
    with open(history_file, "w") as f:
        json.dump(list(price_history.values()), f, indent=2, default=str)
    
    # Also create a time-series format (card_id -> list of prices over time)
    time_series_data = {}
    for card_id, data in price_history.items():
        time_series_data[card_id] = {
            "timestamps": [p["snapshot_time"] for p in data["prices"]],
            "prices": [p["price"] for p in data["prices"]],
            "prices_foil": [p["price_foil"] for p in data["prices"] if p["price_foil"] is not None],
        }
    
    time_series_file = output_dir / "historical_prices_timeseries.json"
    with open(time_series_file, "w") as f:
        json.dump(time_series_data, f, indent=2, default=str)
    
    logger.info(
        "Historical price data exported",
        total_snapshots=len(snapshots),
        cards_with_history=len(price_history),
    )
    
    return {
        "total_snapshots": len(snapshots),
        "cards_with_history": len(price_history),
        "files": [
            str(history_file),
            str(time_series_file),
        ],
    }


if __name__ == "__main__":
    import sys
    
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/training")
    min_listings = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    result = asyncio.run(export_training_data(output_path, min_listings))
    print(json.dumps(result, indent=2))

