"""
Semantic search service using vector embeddings.

Enables natural language search like "blue card draw" or "flying creatures".
Uses sentence-transformers for query embedding and cosine similarity for matching.
"""
from typing import Optional
import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, CardFeatureVector
from app.services.vectorization.service import VectorizationService

logger = structlog.get_logger()


class SemanticSearchService:
    """
    Service for semantic card search using vector embeddings.

    Uses pre-computed card embeddings from card_feature_vectors table
    and computes query embedding on-the-fly for similarity matching.
    """

    def __init__(self):
        """Initialize the semantic search service."""
        self.vectorizer = VectorizationService()
        self.embedding_dim = 384  # all-MiniLM-L6-v2 dimension

    def _compute_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score between -1 and 1
        """
        # Normalize vectors
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    async def search(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 20,
        offset: int = 0,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """
        Search for cards using semantic similarity.

        Args:
            db: Database session
            query: Natural language search query
            limit: Maximum results to return
            offset: Number of results to skip
            filters: Optional attribute filters (colors, format, type, etc.)

        Returns:
            List of card dicts with similarity scores
        """
        # Get query embedding
        query_embedding = self._get_query_embedding(query)

        # Get all card vectors (in production, use approximate nearest neighbors)
        vectors_query = select(CardFeatureVector)
        result = await db.execute(vectors_query)
        all_vectors = result.scalars().all()

        if not all_vectors:
            return []

        # Compute similarities
        similarities = []
        for card_vector in all_vectors:
            vec = card_vector.get_vector()
            # Only compare the text embedding portion (first 384 dims)
            text_vec = vec[:self.embedding_dim]
            similarity = self._compute_similarity(query_embedding, text_vec)
            similarities.append((card_vector.card_id, similarity))

        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Apply offset and limit
        top_results = similarities[offset:offset + limit]

        # Fetch card details
        results = []
        for card_id, score in top_results:
            card = await db.get(Card, card_id)
            if card:
                results.append({
                    "card_id": card.id,
                    "name": card.name,
                    "set_code": card.set_code,
                    "oracle_text": card.oracle_text,
                    "type_line": card.type_line,
                    "image_url": card.image_url,
                    "similarity_score": score,
                })

        return results

    def _get_query_embedding(self, query: str) -> np.ndarray:
        """
        Get embedding vector for a search query.

        Args:
            query: Natural language search query

        Returns:
            384-dimensional embedding vector
        """
        model = self.vectorizer._get_embedding_model()
        embedding = model.encode(query, normalize_embeddings=True)
        return embedding
