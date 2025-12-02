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
    CardFeatureVector,
    PriceSnapshot,
    Marketplace,
)

logger = structlog.get_logger()


async def export_training_data(
    output_dir: Path,
    min_snapshots_per_card: int = 5,
    include_labels: bool = True,
    include_historical_prices: bool = True,
) -> dict[str, Any]:
    """
    Export vectorized training data from Scryfall and MTGJSON price snapshots.
    
    Args:
        output_dir: Directory to save exported data.
        min_snapshots_per_card: Minimum price snapshots per card to include.
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
            
            # Collect training data from price snapshots
            card_vectors = []
            snapshot_vectors = []
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
                
                # Get price snapshots for this card (from Scryfall and MTGJSON)
                snapshots_query = select(PriceSnapshot).where(
                    PriceSnapshot.card_id == card.id,
                    PriceSnapshot.price > 0
                ).order_by(PriceSnapshot.snapshot_time.desc())
                snapshots_result = await db.execute(snapshots_query)
                card_snapshots = snapshots_result.scalars().all()
                
                if len(card_snapshots) < min_snapshots_per_card:
                    continue
                
                # Use price snapshots as training examples
                # For each snapshot, combine card vector with snapshot metadata
                for snapshot in card_snapshots:
                    # Get marketplace info
                    marketplace_query = select(Marketplace).where(Marketplace.id == snapshot.marketplace_id)
                    marketplace_result = await db.execute(marketplace_query)
                    marketplace = marketplace_result.scalar_one_or_none()
                    
                    # Create snapshot feature vector by combining card vector with snapshot features
                    # Features: card vector + timestamp features + marketplace features
                    snapshot_features = np.concatenate([
                        card_vec,
                        np.array([
                            snapshot.snapshot_time.timestamp() if snapshot.snapshot_time else 0,
                            float(snapshot.price) if snapshot.price else 0,
                            float(snapshot.price_foil) if snapshot.price_foil else 0,
                            float(snapshot.min_price) if snapshot.min_price else 0,
                            float(snapshot.max_price) if snapshot.max_price else 0,
                            float(snapshot.avg_price) if snapshot.avg_price else 0,
                            float(snapshot.median_price) if snapshot.median_price else 0,
                            int(snapshot.num_listings) if snapshot.num_listings else 0,
                            int(snapshot.total_quantity) if snapshot.total_quantity else 0,
                            snapshot.marketplace_id or 0,
                        ])
                    ])
                    
                    card_vectors.append(card_vec)
                    snapshot_vectors.append(snapshot_features)
                    
                    if include_labels:
                        # Use future price as label (if available)
                        # For now, use current price as label
                        labels.append(float(snapshot.price) if snapshot.price else 0.0)
                    
                    metadata.append({
                        "card_id": card.id,
                        "card_name": card.name,
                        "set_code": card.set_code,
                        "snapshot_id": snapshot.id,
                        "price": float(snapshot.price) if snapshot.price else 0.0,
                        "price_foil": float(snapshot.price_foil) if snapshot.price_foil else None,
                        "marketplace_id": snapshot.marketplace_id,
                        "marketplace_slug": marketplace.slug if marketplace else None,
                        "snapshot_time": snapshot.snapshot_time.isoformat() if snapshot.snapshot_time else None,
                        "currency": snapshot.currency,
                    })
            
            # Convert to numpy arrays
            card_vectors_array = np.array(card_vectors)
            snapshot_vectors_array = np.array(snapshot_vectors) if snapshot_vectors else None
            labels_array = np.array(labels) if labels else None
            
            # Save data
            np.save(output_dir / "card_vectors.npy", card_vectors_array)
            if snapshot_vectors_array is not None:
                np.save(output_dir / "snapshot_vectors.npy", snapshot_vectors_array)
            
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
                "snapshot_feature_dim": len(snapshot_vectors[0]) if snapshot_vectors else 0,
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
                snapshot_dim=feature_info["snapshot_feature_dim"],
                historical_prices=historical_prices_data["total_snapshots"] if historical_prices_data else 0,
            )
            
            return {
                "samples": len(card_vectors),
                "card_feature_dim": feature_info["card_feature_dim"],
                "snapshot_feature_dim": feature_info["snapshot_feature_dim"],
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

