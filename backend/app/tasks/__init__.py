"""
Celery tasks for background job processing.

Includes:
- Ingestion tasks: Scraping marketplace data
- Analytics tasks: Computing metrics and signals
- Recommendation tasks: Generating trading recommendations
"""
from app.tasks.celery_app import celery_app

__all__ = ["celery_app"]

