# Semantic Search Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add semantic search enabling users to find cards by meaning (e.g., "blue card draw", "flying creatures under 3 mana") instead of just exact text matches.

**Architecture:** Use existing sentence-transformers embeddings stored in `card_feature_vectors` table. Build a search service that combines vector similarity with attribute filters. Frontend gets autocomplete dropdown and filters.

**Tech Stack:** Python/FastAPI, sentence-transformers (all-MiniLM-L6-v2), numpy for cosine similarity, React/TypeScript frontend

---

## Task 1: Create Search Service - Semantic Search

**Files:**
- Create: `backend/app/services/search/__init__.py`
- Create: `backend/app/services/search/semantic.py`
- Test: `backend/tests/services/test_search_semantic.py`

**Step 1: Write the failing test**

```python
# backend/tests/services/test_search_semantic.py
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
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/services/test_search_semantic.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.search'"

**Step 3: Write minimal implementation**

```python
# backend/app/services/search/__init__.py
"""Search services for semantic and text-based card search."""
from app.services.search.semantic import SemanticSearchService

__all__ = ["SemanticSearchService"]
```

```python
# backend/app/services/search/semantic.py
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
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/services/test_search_semantic.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/search/ backend/tests/services/test_search_semantic.py
git commit -m "feat: add semantic search service with vector similarity"
```

---

## Task 2: Add Search Filters

**Files:**
- Create: `backend/app/services/search/filters.py`
- Test: `backend/tests/services/test_search_filters.py`

**Step 1: Write the failing test**

```python
# backend/tests/services/test_search_filters.py
"""Tests for search filters."""
import pytest
from unittest.mock import MagicMock

from app.services.search.filters import apply_card_filters, build_filter_query


class TestSearchFilters:
    """Test search filter functions."""

    def test_filter_by_colors(self):
        """Test filtering cards by color."""
        cards = [
            {"id": 1, "name": "Lightning Bolt", "colors": '["R"]'},
            {"id": 2, "name": "Counterspell", "colors": '["U"]'},
            {"id": 3, "name": "Giant Growth", "colors": '["G"]'},
        ]

        filtered = apply_card_filters(cards, colors=["R"])
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Lightning Bolt"

    def test_filter_by_type(self):
        """Test filtering cards by type."""
        cards = [
            {"id": 1, "name": "Lightning Bolt", "type_line": "Instant"},
            {"id": 2, "name": "Llanowar Elves", "type_line": "Creature - Elf Druid"},
            {"id": 3, "name": "Wrath of God", "type_line": "Sorcery"},
        ]

        filtered = apply_card_filters(cards, card_type="Creature")
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Llanowar Elves"

    def test_filter_by_cmc_range(self):
        """Test filtering cards by CMC range."""
        cards = [
            {"id": 1, "name": "Lightning Bolt", "cmc": 1},
            {"id": 2, "name": "Counterspell", "cmc": 2},
            {"id": 3, "name": "Wrath of God", "cmc": 4},
        ]

        filtered = apply_card_filters(cards, cmc_min=1, cmc_max=2)
        assert len(filtered) == 2

    def test_filter_by_format_legality(self):
        """Test filtering cards by format legality."""
        cards = [
            {"id": 1, "name": "Lightning Bolt", "legalities": '{"modern": "legal", "standard": "not_legal"}'},
            {"id": 2, "name": "Oko", "legalities": '{"modern": "banned", "standard": "banned"}'},
        ]

        filtered = apply_card_filters(cards, format_legal="modern")
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Lightning Bolt"
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/services/test_search_filters.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# backend/app/services/search/filters.py
"""
Search filters for card attributes.

Provides functions to filter search results by colors, type, CMC, format, etc.
"""
import json
from typing import Optional


def apply_card_filters(
    cards: list[dict],
    colors: Optional[list[str]] = None,
    card_type: Optional[str] = None,
    cmc_min: Optional[float] = None,
    cmc_max: Optional[float] = None,
    format_legal: Optional[str] = None,
    rarity: Optional[str] = None,
    keywords: Optional[list[str]] = None,
) -> list[dict]:
    """
    Apply filters to a list of card dicts.

    Args:
        cards: List of card dictionaries
        colors: Filter by colors (e.g., ["R", "U"] for red or blue)
        card_type: Filter by type line (e.g., "Creature", "Instant")
        cmc_min: Minimum converted mana cost
        cmc_max: Maximum converted mana cost
        format_legal: Filter by format legality (e.g., "modern", "standard")
        rarity: Filter by rarity (e.g., "rare", "mythic")
        keywords: Filter by keywords (e.g., ["Flying", "Haste"])

    Returns:
        Filtered list of cards
    """
    result = cards

    if colors:
        result = _filter_by_colors(result, colors)

    if card_type:
        result = _filter_by_type(result, card_type)

    if cmc_min is not None or cmc_max is not None:
        result = _filter_by_cmc(result, cmc_min, cmc_max)

    if format_legal:
        result = _filter_by_format(result, format_legal)

    if rarity:
        result = _filter_by_rarity(result, rarity)

    if keywords:
        result = _filter_by_keywords(result, keywords)

    return result


def _filter_by_colors(cards: list[dict], colors: list[str]) -> list[dict]:
    """Filter cards that contain any of the specified colors."""
    filtered = []
    for card in cards:
        card_colors = card.get("colors", "[]")
        if isinstance(card_colors, str):
            try:
                card_colors = json.loads(card_colors)
            except json.JSONDecodeError:
                card_colors = []

        # Check if card has any of the requested colors
        if any(c in card_colors for c in colors):
            filtered.append(card)

    return filtered


def _filter_by_type(cards: list[dict], card_type: str) -> list[dict]:
    """Filter cards by type line (case-insensitive contains)."""
    card_type_lower = card_type.lower()
    return [
        card for card in cards
        if card.get("type_line") and card_type_lower in card["type_line"].lower()
    ]


def _filter_by_cmc(
    cards: list[dict],
    cmc_min: Optional[float],
    cmc_max: Optional[float],
) -> list[dict]:
    """Filter cards by CMC range."""
    filtered = []
    for card in cards:
        cmc = card.get("cmc")
        if cmc is None:
            continue

        if cmc_min is not None and cmc < cmc_min:
            continue
        if cmc_max is not None and cmc > cmc_max:
            continue

        filtered.append(card)

    return filtered


def _filter_by_format(cards: list[dict], format_legal: str) -> list[dict]:
    """Filter cards that are legal in the specified format."""
    format_lower = format_legal.lower()
    filtered = []

    for card in cards:
        legalities = card.get("legalities", "{}")
        if isinstance(legalities, str):
            try:
                legalities = json.loads(legalities)
            except json.JSONDecodeError:
                legalities = {}

        if legalities.get(format_lower) == "legal":
            filtered.append(card)

    return filtered


def _filter_by_rarity(cards: list[dict], rarity: str) -> list[dict]:
    """Filter cards by rarity."""
    rarity_lower = rarity.lower()
    return [
        card for card in cards
        if card.get("rarity", "").lower() == rarity_lower
    ]


def _filter_by_keywords(cards: list[dict], keywords: list[str]) -> list[dict]:
    """Filter cards that have any of the specified keywords."""
    keywords_lower = [k.lower() for k in keywords]
    filtered = []

    for card in cards:
        card_keywords = card.get("keywords", "[]")
        if isinstance(card_keywords, str):
            try:
                card_keywords = json.loads(card_keywords)
            except json.JSONDecodeError:
                card_keywords = []

        card_keywords_lower = [k.lower() for k in card_keywords]
        if any(k in card_keywords_lower for k in keywords_lower):
            filtered.append(card)

    return filtered


def build_filter_query(base_query, filters: dict):
    """
    Build SQLAlchemy query with filters applied.

    Args:
        base_query: Base SQLAlchemy select query
        filters: Dict of filter parameters

    Returns:
        Modified query with filters applied
    """
    from sqlalchemy import and_, or_
    from app.models import Card

    if filters.get("colors"):
        # Colors stored as JSON string, need to check contains
        color_conditions = []
        for color in filters["colors"]:
            color_conditions.append(Card.colors.contains(f'"{color}"'))
        base_query = base_query.where(or_(*color_conditions))

    if filters.get("card_type"):
        base_query = base_query.where(
            Card.type_line.ilike(f"%{filters['card_type']}%")
        )

    if filters.get("cmc_min") is not None:
        base_query = base_query.where(Card.cmc >= filters["cmc_min"])

    if filters.get("cmc_max") is not None:
        base_query = base_query.where(Card.cmc <= filters["cmc_max"])

    if filters.get("rarity"):
        base_query = base_query.where(Card.rarity == filters["rarity"].lower())

    return base_query
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/services/test_search_filters.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/search/filters.py backend/tests/services/test_search_filters.py
git commit -m "feat: add search filter functions for colors, type, cmc, format"
```

---

## Task 3: Add Autocomplete Service

**Files:**
- Create: `backend/app/services/search/autocomplete.py`
- Test: `backend/tests/services/test_search_autocomplete.py`

**Step 1: Write the failing test**

```python
# backend/tests/services/test_search_autocomplete.py
"""Tests for autocomplete service."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.search.autocomplete import AutocompleteService


class TestAutocompleteService:
    """Test autocomplete service."""

    @pytest.mark.asyncio
    async def test_autocomplete_returns_matches(self):
        """Test autocomplete returns matching card names."""
        service = AutocompleteService()

        mock_db = AsyncMock()
        mock_result = MagicMock()

        # Mock cards returned from DB
        mock_cards = [
            MagicMock(id=1, name="Lightning Bolt", set_code="LEA", image_url_small="/img1.jpg"),
            MagicMock(id=2, name="Lightning Helix", set_code="RAV", image_url_small="/img2.jpg"),
        ]
        mock_result.scalars.return_value.all.return_value = mock_cards
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await service.get_suggestions(mock_db, "light", limit=5)

        assert len(results) == 2
        assert results[0]["name"] == "Lightning Bolt"
        assert results[1]["name"] == "Lightning Helix"

    @pytest.mark.asyncio
    async def test_autocomplete_empty_query(self):
        """Test autocomplete with empty query returns empty list."""
        service = AutocompleteService()
        mock_db = AsyncMock()

        results = await service.get_suggestions(mock_db, "", limit=5)

        assert results == []

    @pytest.mark.asyncio
    async def test_autocomplete_respects_limit(self):
        """Test autocomplete respects the limit parameter."""
        service = AutocompleteService()

        mock_db = AsyncMock()
        mock_result = MagicMock()

        # Return 10 cards
        mock_cards = [MagicMock(id=i, name=f"Card {i}", set_code="TST", image_url_small=None) for i in range(10)]
        mock_result.scalars.return_value.all.return_value = mock_cards[:5]  # DB returns limited
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await service.get_suggestions(mock_db, "card", limit=5)

        assert len(results) <= 5
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/services/test_search_autocomplete.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# backend/app/services/search/autocomplete.py
"""
Fast autocomplete service for card names.

Uses prefix matching on card names for instant suggestions.
"""
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card

logger = structlog.get_logger()


class AutocompleteService:
    """
    Service for fast card name autocomplete.

    Uses database prefix matching for instant suggestions.
    """

    async def get_suggestions(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        """
        Get autocomplete suggestions for a search query.

        Args:
            db: Database session
            query: Partial card name to search for
            limit: Maximum suggestions to return (default 5)

        Returns:
            List of suggestion dicts with id, name, set_code, image_url
        """
        if not query or len(query) < 1:
            return []

        # Use ILIKE for case-insensitive prefix matching
        search_query = select(Card).where(
            Card.name.ilike(f"{query}%")
        ).order_by(Card.name).limit(limit)

        result = await db.execute(search_query)
        cards = result.scalars().all()

        return [
            {
                "id": card.id,
                "name": card.name,
                "set_code": card.set_code,
                "image_url": card.image_url_small or card.image_url,
            }
            for card in cards
        ]
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/services/test_search_autocomplete.py -v`
Expected: PASS

**Step 5: Update __init__.py and commit**

```python
# backend/app/services/search/__init__.py
"""Search services for semantic and text-based card search."""
from app.services.search.semantic import SemanticSearchService
from app.services.search.autocomplete import AutocompleteService
from app.services.search.filters import apply_card_filters, build_filter_query

__all__ = [
    "SemanticSearchService",
    "AutocompleteService",
    "apply_card_filters",
    "build_filter_query",
]
```

```bash
git add backend/app/services/search/
git commit -m "feat: add autocomplete service for fast card name suggestions"
```

---

## Task 4: Create Search API Endpoints

**Files:**
- Create: `backend/app/api/routes/search.py`
- Create: `backend/app/schemas/search.py`
- Modify: `backend/app/api/__init__.py`
- Test: `backend/tests/api/test_search.py`

**Step 1: Write the failing test**

```python
# backend/tests/api/test_search.py
"""Tests for search API endpoints."""
import pytest
from unittest.mock import AsyncMock, patch


class TestSearchAPI:
    """Test search API endpoints."""

    @pytest.mark.asyncio
    async def test_search_endpoint(self, client):
        """Test main search endpoint."""
        response = client.get("/api/search?q=lightning")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_autocomplete_endpoint(self, client):
        """Test autocomplete endpoint."""
        response = client.get("/api/search/autocomplete?q=light")

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data

    @pytest.mark.asyncio
    async def test_similar_cards_endpoint(self, client, db_session):
        """Test similar cards endpoint."""
        # Create a test card first
        from app.models import Card
        card = Card(
            scryfall_id="test-similar-123",
            name="Test Card",
            set_code="TST",
            collector_number="1",
        )
        db_session.add(card)
        await db_session.commit()

        response = client.get(f"/api/cards/{card.id}/similar")

        assert response.status_code == 200
        data = response.json()
        assert "similar_cards" in data
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/api/test_search.py -v`
Expected: FAIL with 404 (endpoints don't exist)

**Step 3: Write implementation**

```python
# backend/app/schemas/search.py
"""Search API schemas."""
from typing import Optional
from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    """Filters for search queries."""
    colors: Optional[list[str]] = Field(None, description="Filter by colors (W, U, B, R, G)")
    card_type: Optional[str] = Field(None, description="Filter by card type")
    cmc_min: Optional[float] = Field(None, description="Minimum CMC")
    cmc_max: Optional[float] = Field(None, description="Maximum CMC")
    format_legal: Optional[str] = Field(None, description="Format legality (modern, standard, etc.)")
    rarity: Optional[str] = Field(None, description="Card rarity")
    keywords: Optional[list[str]] = Field(None, description="Card keywords (Flying, Haste, etc.)")


class SearchResult(BaseModel):
    """Single search result."""
    card_id: int
    name: str
    set_code: str
    oracle_text: Optional[str] = None
    type_line: Optional[str] = None
    image_url: Optional[str] = None
    similarity_score: Optional[float] = None


class SearchResponse(BaseModel):
    """Search response with results and metadata."""
    results: list[SearchResult]
    total: int
    page: int
    page_size: int
    has_more: bool
    query: str
    search_type: str = "semantic"  # "semantic" or "text"


class AutocompleteSuggestion(BaseModel):
    """Single autocomplete suggestion."""
    id: int
    name: str
    set_code: str
    image_url: Optional[str] = None


class AutocompleteResponse(BaseModel):
    """Autocomplete response."""
    suggestions: list[AutocompleteSuggestion]
    query: str


class SimilarCardsResponse(BaseModel):
    """Similar cards response."""
    card_id: int
    card_name: str
    similar_cards: list[SearchResult]
```

```python
# backend/app/api/routes/search.py
"""
Search API endpoints.

Provides semantic search, autocomplete, and similar cards functionality.
"""
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Card
from app.schemas.search import (
    SearchResponse,
    SearchResult,
    AutocompleteResponse,
    AutocompleteSuggestion,
    SimilarCardsResponse,
)
from app.services.search import (
    SemanticSearchService,
    AutocompleteService,
    apply_card_filters,
)

router = APIRouter()
logger = structlog.get_logger(__name__)

# Service instances (lazy initialization)
_semantic_service: Optional[SemanticSearchService] = None
_autocomplete_service: Optional[AutocompleteService] = None


def get_semantic_service() -> SemanticSearchService:
    """Get or create semantic search service."""
    global _semantic_service
    if _semantic_service is None:
        _semantic_service = SemanticSearchService()
    return _semantic_service


def get_autocomplete_service() -> AutocompleteService:
    """Get or create autocomplete service."""
    global _autocomplete_service
    if _autocomplete_service is None:
        _autocomplete_service = AutocompleteService()
    return _autocomplete_service


@router.get("", response_model=SearchResponse)
async def search_cards(
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    colors: Optional[str] = Query(None, description="Comma-separated colors (W,U,B,R,G)"),
    card_type: Optional[str] = Query(None, description="Card type filter"),
    cmc_min: Optional[float] = Query(None, description="Minimum CMC"),
    cmc_max: Optional[float] = Query(None, description="Maximum CMC"),
    format_legal: Optional[str] = Query(None, description="Format legality"),
    rarity: Optional[str] = Query(None, description="Rarity filter"),
    mode: str = Query("semantic", description="Search mode: 'semantic' or 'text'"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for cards using semantic similarity or text matching.

    Semantic mode uses AI embeddings to find cards by meaning.
    Text mode uses traditional ILIKE matching on card name.
    """
    offset = (page - 1) * page_size

    # Parse color filter
    color_list = colors.split(",") if colors else None

    filters = {
        "colors": color_list,
        "card_type": card_type,
        "cmc_min": cmc_min,
        "cmc_max": cmc_max,
        "format_legal": format_legal,
        "rarity": rarity,
    }

    if mode == "semantic":
        service = get_semantic_service()
        # Get more results than needed for filtering
        raw_results = await service.search(
            db=db,
            query=q,
            limit=page_size * 3,  # Get extra for filtering
            offset=0,
        )

        # Apply filters
        filtered = apply_card_filters(raw_results, **{k: v for k, v in filters.items() if v})

        # Apply pagination to filtered results
        paginated = filtered[offset:offset + page_size]
        total = len(filtered)

        results = [
            SearchResult(
                card_id=r["card_id"],
                name=r["name"],
                set_code=r["set_code"],
                oracle_text=r.get("oracle_text"),
                type_line=r.get("type_line"),
                image_url=r.get("image_url"),
                similarity_score=r.get("similarity_score"),
            )
            for r in paginated
        ]
    else:
        # Text search fallback
        from sqlalchemy import select, func
        from app.services.search.filters import build_filter_query

        query = select(Card).where(Card.name.ilike(f"%{q}%"))
        query = build_filter_query(query, filters)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query) or 0

        # Apply pagination
        query = query.order_by(Card.name).offset(offset).limit(page_size)
        result = await db.execute(query)
        cards = result.scalars().all()

        results = [
            SearchResult(
                card_id=c.id,
                name=c.name,
                set_code=c.set_code,
                oracle_text=c.oracle_text,
                type_line=c.type_line,
                image_url=c.image_url,
            )
            for c in cards
        ]

    return SearchResponse(
        results=results,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
        query=q,
        search_type=mode,
    )


@router.get("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(
    q: str = Query(..., min_length=1, description="Partial card name"),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """
    Get autocomplete suggestions for card names.

    Returns up to `limit` cards whose names start with the query.
    """
    service = get_autocomplete_service()
    suggestions = await service.get_suggestions(db, q, limit)

    return AutocompleteResponse(
        suggestions=[
            AutocompleteSuggestion(
                id=s["id"],
                name=s["name"],
                set_code=s["set_code"],
                image_url=s.get("image_url"),
            )
            for s in suggestions
        ],
        query=q,
    )


@router.get("/cards/{card_id}/similar", response_model=SimilarCardsResponse)
async def get_similar_cards(
    card_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Get cards similar to a specific card.

    Uses semantic similarity based on card text and attributes.
    """
    # Get the target card
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Search using the card's text as query
    search_text = f"{card.name} {card.type_line or ''} {card.oracle_text or ''}"

    service = get_semantic_service()
    results = await service.search(
        db=db,
        query=search_text,
        limit=limit + 1,  # Get one extra to filter out the source card
    )

    # Filter out the source card
    similar = [r for r in results if r["card_id"] != card_id][:limit]

    return SimilarCardsResponse(
        card_id=card_id,
        card_name=card.name,
        similar_cards=[
            SearchResult(
                card_id=r["card_id"],
                name=r["name"],
                set_code=r["set_code"],
                oracle_text=r.get("oracle_text"),
                type_line=r.get("type_line"),
                image_url=r.get("image_url"),
                similarity_score=r.get("similarity_score"),
            )
            for r in similar
        ],
    )
```

**Step 4: Register router**

Add to `backend/app/api/__init__.py`:

```python
from app.api.routes import search

api_router.include_router(search.router, prefix="/search", tags=["search"])
```

**Step 5: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/api/test_search.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/api/routes/search.py backend/app/schemas/search.py backend/app/api/__init__.py backend/tests/api/test_search.py
git commit -m "feat: add search API endpoints with semantic search and autocomplete"
```

---

## Task 5: Create Embedding Refresh Task

**Files:**
- Create: `backend/app/tasks/search.py`
- Modify: `backend/app/tasks/celery_app.py`
- Test: `backend/tests/tasks/test_search.py`

**Step 1: Write the failing test**

```python
# backend/tests/tasks/test_search.py
"""Tests for search tasks."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSearchTasks:
    """Test search-related Celery tasks."""

    def test_refresh_embeddings_task_registered(self):
        """Verify refresh_embeddings task is registered."""
        from app.tasks.search import refresh_embeddings

        assert refresh_embeddings.name == "app.tasks.search.refresh_embeddings"
        assert callable(refresh_embeddings)

    @patch("app.tasks.search.create_task_session_maker")
    def test_refresh_embeddings_runs(self, mock_session_maker):
        """Test refresh_embeddings task can be called."""
        from app.tasks.search import refresh_embeddings

        # Setup mock
        mock_session = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        async_session_maker = MagicMock()
        async_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        async_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_session_maker.return_value = (async_session_maker, mock_engine)

        # Mock query results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Should not raise
        result = refresh_embeddings()
        assert "completed_at" in result or "cards_processed" in result
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/tasks/test_search.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write implementation**

```python
# backend/app/tasks/search.py
"""
Search-related Celery tasks.

Handles embedding refresh and search index maintenance.
"""
import asyncio
from datetime import datetime, timezone

import structlog
from celery import shared_task
from sqlalchemy import select

from app.db.session import create_task_session_maker
from app.models import Card, CardFeatureVector
from app.services.vectorization.service import VectorizationService
from app.services.vectorization.ingestion import vectorize_card_by_attrs

logger = structlog.get_logger()


@shared_task(name="app.tasks.search.refresh_embeddings")
def refresh_embeddings(batch_size: int = 100, force: bool = False):
    """
    Refresh card embeddings for semantic search.

    Processes cards that:
    - Have no embedding yet, or
    - Were updated since last embedding (if force=False)

    Args:
        batch_size: Number of cards to process per batch
        force: If True, re-embed all cards regardless of status

    Returns:
        Dict with processing statistics
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_refresh_embeddings_async(batch_size, force))
    finally:
        loop.close()


async def _refresh_embeddings_async(batch_size: int, force: bool) -> dict:
    """Async implementation of embedding refresh."""
    session_maker, engine = create_task_session_maker()
    vectorizer = VectorizationService()

    stats = {
        "cards_processed": 0,
        "embeddings_created": 0,
        "embeddings_updated": 0,
        "errors": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with session_maker() as db:
            if force:
                # Get all cards
                query = select(Card)
            else:
                # Get cards without embeddings
                subquery = select(CardFeatureVector.card_id)
                query = select(Card).where(Card.id.notin_(subquery))

            result = await db.execute(query)
            cards = result.scalars().all()

            logger.info(
                "Starting embedding refresh",
                total_cards=len(cards),
                force=force,
            )

            for card in cards:
                try:
                    # Prepare card attributes
                    card_attrs = {
                        "name": card.name,
                        "type_line": card.type_line,
                        "oracle_text": card.oracle_text,
                        "rarity": card.rarity,
                        "cmc": card.cmc,
                        "colors": card.colors,
                        "mana_cost": card.mana_cost,
                    }

                    # Check if embedding exists
                    existing_query = select(CardFeatureVector).where(
                        CardFeatureVector.card_id == card.id
                    )
                    existing_result = await db.execute(existing_query)
                    existing = existing_result.scalar_one_or_none()

                    # Create or update embedding
                    vector_obj = await vectorize_card_by_attrs(
                        db, card.id, card_attrs, vectorizer
                    )

                    if vector_obj:
                        if existing:
                            stats["embeddings_updated"] += 1
                        else:
                            stats["embeddings_created"] += 1

                    stats["cards_processed"] += 1

                    # Commit in batches
                    if stats["cards_processed"] % batch_size == 0:
                        await db.commit()
                        logger.info(
                            "Embedding batch committed",
                            processed=stats["cards_processed"],
                        )

                except Exception as e:
                    stats["errors"] += 1
                    logger.warning(
                        "Failed to embed card",
                        card_id=card.id,
                        error=str(e),
                    )

            # Final commit
            await db.commit()

    except Exception as e:
        logger.error("Embedding refresh failed", error=str(e))
        stats["error_message"] = str(e)

    finally:
        await engine.dispose()
        vectorizer.close()

    stats["completed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Embedding refresh completed",
        **stats,
    )

    return stats
```

**Step 4: Enable the task in celery_app.py**

Uncomment the search task in `backend/app/tasks/celery_app.py`:

```python
# Search embeddings refresh: Update card embeddings daily at 3 AM
# Ensures similarity search remains accurate
"search-refresh-embeddings": {
    "task": "app.tasks.search.refresh_embeddings",
    "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
},
```

And add to include list:
```python
include=[
    "app.tasks.data_seeding",
    "app.tasks.ingestion",
    "app.tasks.analytics",
    "app.tasks.recommendations",
    "app.tasks.pricing",
    "app.tasks.tournaments",
    "app.tasks.search",  # Add this
],
```

**Step 5: Run test to verify it passes**

Run: `docker compose exec backend pytest tests/tasks/test_search.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/tasks/search.py backend/app/tasks/celery_app.py backend/tests/tasks/test_search.py
git commit -m "feat: add embedding refresh task for semantic search"
```

---

## Task 6: Frontend SearchAutocomplete Component

**Files:**
- Create: `frontend/src/components/search/SearchAutocomplete.tsx`
- Create: `frontend/src/components/search/index.ts`
- Test manually in browser

**Step 1: Create the component**

```typescript
// frontend/src/components/search/SearchAutocomplete.tsx
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import Image from "next/image";

interface Suggestion {
  id: number;
  name: string;
  set_code: string;
  image_url: string | null;
}

interface SearchAutocompleteProps {
  placeholder?: string;
  onSelect?: (card: Suggestion) => void;
  className?: string;
}

export function SearchAutocomplete({
  placeholder = "Search cards...",
  onSelect,
  className = "",
}: SearchAutocompleteProps) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);

  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Debounced fetch
  const fetchSuggestions = useCallback(async (searchQuery: string) => {
    if (searchQuery.length < 2) {
      setSuggestions([]);
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(
        `/api/search/autocomplete?q=${encodeURIComponent(searchQuery)}&limit=5`
      );
      if (response.ok) {
        const data = await response.json();
        setSuggestions(data.suggestions);
        setIsOpen(true);
      }
    } catch (error) {
      console.error("Autocomplete error:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Debounce effect
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchSuggestions(query);
    }, 150);

    return () => clearTimeout(timer);
  }, [query, fetchSuggestions]);

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) return;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case "Enter":
        e.preventDefault();
        if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
          handleSelect(suggestions[selectedIndex]);
        } else if (query.length >= 2) {
          // Submit search
          router.push(`/cards?q=${encodeURIComponent(query)}`);
          setIsOpen(false);
        }
        break;
      case "Escape":
        setIsOpen(false);
        setSelectedIndex(-1);
        break;
    }
  };

  const handleSelect = (suggestion: Suggestion) => {
    if (onSelect) {
      onSelect(suggestion);
    } else {
      router.push(`/cards/${suggestion.id}`);
    }
    setQuery("");
    setIsOpen(false);
    setSelectedIndex(-1);
  };

  const clearQuery = () => {
    setQuery("");
    setSuggestions([]);
    setIsOpen(false);
    inputRef.current?.focus();
  };

  return (
    <div className={`relative ${className}`}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setIsOpen(true)}
          placeholder={placeholder}
          className="w-full pl-10 pr-10 py-2 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-ring"
          aria-label="Search cards"
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          role="combobox"
        />
        {query && (
          <button
            onClick={clearQuery}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Dropdown */}
      {isOpen && suggestions.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-lg shadow-lg overflow-hidden"
          role="listbox"
        >
          {suggestions.map((suggestion, index) => (
            <button
              key={suggestion.id}
              onClick={() => handleSelect(suggestion)}
              onMouseEnter={() => setSelectedIndex(index)}
              className={`w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-accent transition-colors ${
                index === selectedIndex ? "bg-accent" : ""
              }`}
              role="option"
              aria-selected={index === selectedIndex}
            >
              {suggestion.image_url ? (
                <Image
                  src={suggestion.image_url}
                  alt=""
                  width={32}
                  height={45}
                  className="rounded object-cover"
                />
              ) : (
                <div className="w-8 h-11 bg-muted rounded" />
              )}
              <div>
                <div className="font-medium">{suggestion.name}</div>
                <div className="text-sm text-muted-foreground">
                  {suggestion.set_code}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Loading indicator */}
      {isLoading && (
        <div className="absolute right-10 top-1/2 -translate-y-1/2">
          <div className="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      )}
    </div>
  );
}
```

```typescript
// frontend/src/components/search/index.ts
export { SearchAutocomplete } from "./SearchAutocomplete";
```

**Step 2: Test manually**

Run: `npm run dev` in frontend directory
Navigate to: http://localhost:3000
Test: Type "lightning" in search box and verify suggestions appear

**Step 3: Commit**

```bash
git add frontend/src/components/search/
git commit -m "feat: add SearchAutocomplete component with keyboard navigation"
```

---

## Task 7: Update Cards Page with Semantic Search

**Files:**
- Modify: `frontend/src/app/cards/page.tsx`

**Step 1: Add semantic search toggle and filters**

Update the cards page to use the new search API with semantic mode option. The key changes are:

1. Replace the ILIKE search with API call to `/api/search`
2. Add mode toggle (semantic vs text)
3. Add filter controls for colors, type, CMC

**Step 2: Test manually**

Navigate to `/cards` and test:
- Semantic search with "blue card draw"
- Filter by colors
- Filter by type
- Verify pagination works

**Step 3: Commit**

```bash
git add frontend/src/app/cards/page.tsx
git commit -m "feat: integrate semantic search into cards page"
```

---

## Task 8: Add Similar Cards to Card Detail Page

**Files:**
- Modify: `frontend/src/app/cards/[id]/page.tsx`

**Step 1: Add similar cards section**

Add a "Similar Cards" section at the bottom of the card detail page that fetches from `/api/cards/{id}/similar`.

**Step 2: Test manually**

Navigate to a card detail page and verify:
- Similar cards section appears
- Cards shown are semantically similar
- Clicking a similar card navigates to its page

**Step 3: Commit**

```bash
git add frontend/src/app/cards/\[id\]/page.tsx
git commit -m "feat: add similar cards section to card detail page"
```

---

## Summary

| Task | Component | Description |
|------|-----------|-------------|
| 1 | SemanticSearchService | Core vector similarity search |
| 2 | Search Filters | Color, type, CMC, format filtering |
| 3 | AutocompleteService | Fast prefix matching |
| 4 | Search API | `/api/search`, `/api/search/autocomplete`, `/api/cards/{id}/similar` |
| 5 | Embedding Task | Daily refresh of card embeddings |
| 6 | SearchAutocomplete | Frontend autocomplete dropdown |
| 7 | Cards Page | Semantic search integration |
| 8 | Card Detail | Similar cards section |

**After all tasks:**
- Run full test suite: `make test`
- Verify search works: Navigate to `/cards` and search
- Use `superpowers:finishing-a-development-branch` to complete
