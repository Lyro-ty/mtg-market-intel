"""
Feature vector model for storing pre-computed ML feature vectors.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import numpy as np
from sqlalchemy import DateTime, ForeignKey, Index, Integer, LargeBinary, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.listing import Listing


class CardFeatureVector(Base):
    """
    Stores pre-computed feature vectors for cards.
    
    These vectors are ready for ML training and include:
    - Text embeddings (card name, type, description)
    - Normalized numerical features (CMC, colors)
    - One-hot encoded categorical features (rarity)
    """
    
    __tablename__ = "card_feature_vectors"
    __mapper_args__ = {
        "exclude_properties": ["id"]
    }
    
    # Primary key (overrides base id)
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    
    # Feature vector (stored as numpy array serialized to bytes)
    # Using LargeBinary for efficient storage
    feature_vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    
    # Feature dimensions (for validation)
    feature_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Metadata
    model_version: Mapped[str] = mapped_column(String, default="all-MiniLM-L6-v2", nullable=False)
    
    # Timestamps (explicitly define since we're not using base id)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    card: Mapped["Card"] = relationship("Card", overlaps="feature_vector")
    
    # Indexes
    __table_args__ = (
        Index("ix_card_feature_vectors_card_id", "card_id"),
    )
    
    def get_vector(self) -> np.ndarray:
        """Deserialize the feature vector from bytes."""
        return np.frombuffer(self.feature_vector, dtype=np.float32)
    
    def set_vector(self, vector: np.ndarray):
        """Serialize the feature vector to bytes."""
        self.feature_vector = vector.astype(np.float32).tobytes()
        self.feature_dim = len(vector)
    
    def __repr__(self) -> str:
        return f"<CardFeatureVector card_id={self.card_id} dim={self.feature_dim}>"


class ListingFeatureVector(Base):
    """
    Stores pre-computed feature vectors for listings.
    
    These vectors combine card features with listing-specific features:
    - Card features (from CardFeatureVector)
    - Listing features (price, condition, quantity, seller info)
    """
    
    __tablename__ = "listing_feature_vectors"
    __mapper_args__ = {
        "exclude_properties": ["id"]
    }
    
    # Primary key (overrides base id)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    
    # Feature vector (stored as numpy array serialized to bytes)
    feature_vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    
    # Feature dimensions (for validation)
    feature_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Metadata
    model_version: Mapped[str] = mapped_column(String, default="all-MiniLM-L6-v2", nullable=False)
    
    # Timestamps (explicitly define since we're not using base id)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    listing: Mapped["Listing"] = relationship("Listing", overlaps="feature_vector")
    
    # Indexes
    __table_args__ = (
        Index("ix_listing_feature_vectors_listing_id", "listing_id"),
        Index("ix_listing_feature_vectors_card_id", "listing_id"),  # For batch queries
    )
    
    def get_vector(self) -> np.ndarray:
        """Deserialize the feature vector from bytes."""
        return np.frombuffer(self.feature_vector, dtype=np.float32)
    
    def set_vector(self, vector: np.ndarray):
        """Serialize the feature vector to bytes."""
        self.feature_vector = vector.astype(np.float32).tobytes()
        self.feature_dim = len(vector)
    
    def __repr__(self) -> str:
        return f"<ListingFeatureVector listing_id={self.listing_id} dim={self.feature_dim}>"

