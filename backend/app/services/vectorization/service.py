"""
Feature vectorization service.

Converts raw card and listing data into normalized feature vectors
ready for machine learning models.
"""
import json
from typing import Any

import numpy as np
import structlog
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger()


class VectorizationService:
    """
    Service for vectorizing card and listing data for ML training.
    
    Features:
    - Text embeddings for card names, descriptions, type lines
    - Normalized numerical features (price, quantity, ratings)
    - One-hot encoded categorical features (condition, language, rarity)
    - Combined feature vectors ready for training
    """
    
    def __init__(self, embedding_model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the vectorization service.
        
        Args:
            embedding_model_name: Name of the sentence transformer model to use.
                Default is a lightweight, fast model suitable for production.
        """
        self.embedding_model_name = embedding_model_name
        self._embedding_model: SentenceTransformer | None = None
        
        # Feature dimensions
        self.text_embedding_dim = 384  # all-MiniLM-L6-v2 produces 384-dim vectors
        self.condition_dim = 5  # NM, LP, MP, HP, DMG
        self.language_dim = 10  # Common languages
        self.rarity_dim = 5  # common, uncommon, rare, mythic, special
        self.marketplace_dim = 5  # TCGPlayer, Card Kingdom, Cardmarket, etc.
        
        # Numerical feature normalization stats (will be computed from data)
        self.price_mean = 0.0
        self.price_std = 1.0
        self.quantity_mean = 0.0
        self.quantity_std = 1.0
        self.rating_mean = 0.0
        self.rating_std = 1.0
    
    def _get_embedding_model(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._embedding_model is None:
            logger.info("Loading embedding model", model=self.embedding_model_name)
            self._embedding_model = SentenceTransformer(self.embedding_model_name)
        return self._embedding_model
    
    def vectorize_card(self, card_data: dict[str, Any]) -> np.ndarray:
        """
        Vectorize card data into a feature vector.
        
        Args:
            card_data: Dictionary containing card fields:
                - name: str
                - type_line: str | None
                - oracle_text: str | None
                - rarity: str | None
                - cmc: float | None
                - colors: list[str] | None
                - mana_cost: str | None
                
        Returns:
            Combined feature vector as numpy array.
        """
        model = self._get_embedding_model()
        
        # 1. Text embeddings
        # Combine card name, type line, and oracle text for embedding
        text_parts = []
        if card_data.get("name"):
            text_parts.append(card_data["name"])
        if card_data.get("type_line"):
            text_parts.append(card_data["type_line"])
        if card_data.get("oracle_text"):
            text_parts.append(card_data["oracle_text"])
        
        text = " ".join(text_parts) if text_parts else ""
        text_embedding = model.encode(text, normalize_embeddings=True)
        
        # 2. Rarity one-hot encoding
        rarity = card_data.get("rarity", "").lower()
        rarity_vector = np.zeros(self.rarity_dim)
        rarity_map = {
            "common": 0,
            "uncommon": 1,
            "rare": 2,
            "mythic": 3,
            "special": 4,
        }
        if rarity in rarity_map:
            rarity_vector[rarity_map[rarity]] = 1.0
        
        # 3. Numerical features (normalized)
        cmc = card_data.get("cmc") or 0.0
        cmc_normalized = min(cmc / 10.0, 1.0)  # Normalize to 0-1 (assuming max CMC ~10)
        
        # Color features (one-hot for 5 colors)
        colors = card_data.get("colors") or []
        if isinstance(colors, str):
            try:
                colors = json.loads(colors)
            except (json.JSONDecodeError, TypeError):
                colors = []
        color_vector = np.zeros(5)  # W, U, B, R, G
        color_map = {"W": 0, "U": 1, "B": 2, "R": 3, "G": 4}
        for color in colors:
            if color in color_map:
                color_vector[color_map[color]] = 1.0
        
        # Combine all features
        feature_vector = np.concatenate([
            text_embedding,  # 384 dims
            rarity_vector,   # 5 dims
            [cmc_normalized],  # 1 dim
            color_vector,    # 5 dims
        ])
        
        return feature_vector
    
    def vectorize_listing(self, listing_data: dict[str, Any], card_vector: np.ndarray | None = None) -> np.ndarray:
        """
        Vectorize listing data into a feature vector.
        
        Args:
            listing_data: Dictionary containing listing fields:
                - price: float
                - quantity: int
                - condition: str | None
                - language: str | None
                - is_foil: bool
                - seller_rating: float | None
                - marketplace_id: int
            card_vector: Optional pre-computed card feature vector.
                If None, will create a minimal card vector.
                
        Returns:
            Combined feature vector as numpy array.
        """
        # 1. Normalized numerical features
        price = listing_data.get("price", 0.0)
        quantity = listing_data.get("quantity", 1)
        seller_rating = listing_data.get("seller_rating") or 0.0
        
        # Normalize price (log scale for better distribution)
        price_normalized = np.log1p(price) / 10.0  # log(1+price) / 10, caps around 1.0
        price_normalized = min(price_normalized, 1.0)
        
        # Normalize quantity (assuming max ~100)
        quantity_normalized = min(quantity / 100.0, 1.0)
        
        # Normalize rating (assuming 0-5 scale)
        rating_normalized = seller_rating / 5.0 if seller_rating else 0.0
        
        # 2. Condition one-hot encoding
        condition = (listing_data.get("condition") or "NM").upper()
        condition_vector = np.zeros(self.condition_dim)
        condition_map = {
            "NM": 0, "NEAR MINT": 0,
            "LP": 1, "LIGHTLY PLAYED": 1,
            "MP": 2, "MODERATELY PLAYED": 2,
            "HP": 3, "HEAVILY PLAYED": 3,
            "DMG": 4, "DAMAGED": 4,
        }
        if condition in condition_map:
            condition_vector[condition_map[condition]] = 1.0
        
        # 3. Language one-hot encoding
        language = listing_data.get("language", "English")
        language_vector = np.zeros(self.language_dim)
        language_map = {
            "English": 0, "Japanese": 1, "German": 2, "French": 3, "Italian": 4,
            "Spanish": 5, "Portuguese": 6, "Korean": 7, "Chinese Simplified": 8, "Russian": 9,
        }
        if language in language_map:
            language_vector[language_map[language]] = 1.0
        
        # 4. Foil flag
        is_foil = 1.0 if listing_data.get("is_foil", False) else 0.0
        
        # 5. Marketplace one-hot encoding
        marketplace_id = listing_data.get("marketplace_id", 0)
        marketplace_vector = np.zeros(self.marketplace_dim)
        # Map marketplace IDs to indices (this should match your marketplace IDs)
        # For now, use modulo to fit into vector
        if marketplace_id > 0:
            idx = min(marketplace_id % self.marketplace_dim, self.marketplace_dim - 1)
            marketplace_vector[idx] = 1.0
        
        # 6. Card vector (if provided, otherwise use zeros)
        if card_vector is None:
            card_vector = np.zeros(self.text_embedding_dim + self.rarity_dim + 1 + 5)  # Default size
        
        # Combine all features
        listing_features = np.concatenate([
            [price_normalized],      # 1 dim
            [quantity_normalized],   # 1 dim
            [rating_normalized],      # 1 dim
            condition_vector,        # 5 dims
            language_vector,         # 10 dims
            [is_foil],              # 1 dim
            marketplace_vector,      # 5 dims
        ])
        
        # Combine card and listing features
        feature_vector = np.concatenate([
            card_vector,      # ~395 dims (card features)
            listing_features,  # 24 dims (listing features)
        ])
        
        return feature_vector
    
    def vectorize_listing_batch(
        self,
        listings: list[dict[str, Any]],
        card_vector: np.ndarray | None = None,
    ) -> np.ndarray:
        """
        Vectorize a batch of listings efficiently.
        
        Args:
            listings: List of listing dictionaries.
            card_vector: Optional pre-computed card feature vector.
            
        Returns:
            Array of shape (n_listings, feature_dim).
        """
        vectors = [self.vectorize_listing(listing, card_vector) for listing in listings]
        return np.array(vectors)
    
    def get_feature_dim(self) -> int:
        """Get the total feature dimension."""
        return (
            self.text_embedding_dim +  # Text embedding
            self.rarity_dim +          # Rarity
            1 +                        # CMC
            5 +                        # Colors
            1 +                        # Price
            1 +                        # Quantity
            1 +                        # Rating
            self.condition_dim +       # Condition
            self.language_dim +        # Language
            1 +                        # Foil
            self.marketplace_dim      # Marketplace
        )
    
    def close(self):
        """Clean up resources."""
        if self._embedding_model is not None:
            # SentenceTransformer doesn't need explicit cleanup, but we can clear the reference
            self._embedding_model = None

