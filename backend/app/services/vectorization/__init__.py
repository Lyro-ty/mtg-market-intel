"""
Feature vectorization service for ML training.

Converts raw card and listing data into normalized feature vectors
ready for machine learning models.
"""
from app.services.vectorization.service import VectorizationService

__all__ = ["VectorizationService"]

