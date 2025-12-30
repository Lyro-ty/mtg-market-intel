"""
Feature vector model for storing pre-computed ML feature vectors.

Used for card similarity search and ML-based recommendations.
"""
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import DateTime, ForeignKey, Index, Integer, LargeBinary, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db.base import Base


# Create a base class without id for feature vectors
# Use the same registry as Base so relationships work
class FeatureVectorBase(DeclarativeBase):
    """Base class for feature vector models that don't use the standard id column."""

    # Share the same registry as Base
    registry = Base.registry

    # Only include created_at and updated_at, not id
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


if TYPE_CHECKING:
    from app.models.card import Card


class CardFeatureVector(FeatureVectorBase):
    """
    Stores pre-computed feature vectors for cards.

    These vectors are ready for ML training and include:
    - Text embeddings (card name, type, description)
    - Normalized numerical features (CMC, colors)
    - One-hot encoded categorical features (rarity)

    Used for:
    - Card similarity search
    - Content-based recommendations
    - Clustering similar cards
    """

    __tablename__ = "card_feature_vectors"

    # Primary key
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
    model_version: Mapped[str] = mapped_column(
        String, default="all-MiniLM-L6-v2", nullable=False
    )

    # Relationships
    card: Mapped["Card"] = relationship("Card", overlaps="feature_vector")

    # card_id is primary key, no additional index needed

    def get_vector(self) -> np.ndarray:
        """Deserialize the feature vector from bytes."""
        return np.frombuffer(self.feature_vector, dtype=np.float32)

    def set_vector(self, vector: np.ndarray) -> None:
        """Serialize the feature vector to bytes."""
        self.feature_vector = vector.astype(np.float32).tobytes()
        self.feature_dim = len(vector)

    def __repr__(self) -> str:
        return f"<CardFeatureVector card_id={self.card_id} dim={self.feature_dim}>"

