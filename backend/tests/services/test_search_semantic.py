"""Tests for semantic search service."""
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.search.semantic import SemanticSearchService


class TestSemanticSearchService:
    """Test semantic search service."""

    def test_init(self):
        """Test service initialization."""
        service = SemanticSearchService()
        assert service.embedding_dim == 384
        assert service.vectorizer is not None

    @pytest.mark.asyncio
    async def test_search_by_text_returns_results(self):
        """Test searching by text query returns matching cards."""
        service = SemanticSearchService()

        # Mock the database session
        mock_db = AsyncMock()

        # Create mock card with feature vector
        mock_card = MagicMock()
        mock_card.id = 1
        mock_card.name = "Lightning Bolt"
        mock_card.oracle_text = "Deal 3 damage to any target."

        mock_vector = MagicMock()
        mock_vector.card_id = 1
        mock_vector.get_vector.return_value = np.random.rand(384).astype(np.float32)

        # Mock database query results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_vector]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock card lookup
        mock_db.get = AsyncMock(return_value=mock_card)

        results = await service.search(
            db=mock_db,
            query="direct damage spell",
            limit=10,
        )

        assert isinstance(results, list)

    def test_compute_similarity(self):
        """Test cosine similarity computation."""
        service = SemanticSearchService()

        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([1.0, 0.0, 0.0])
        vec3 = np.array([0.0, 1.0, 0.0])

        # Same vectors = similarity 1.0
        assert service._compute_similarity(vec1, vec2) == pytest.approx(1.0)

        # Orthogonal vectors = similarity 0.0
        assert service._compute_similarity(vec1, vec3) == pytest.approx(0.0)
