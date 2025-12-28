"""
Celery tasks for background job processing.

Includes:
- Ingestion tasks: Scraping marketplace data
- Analytics tasks: Computing metrics and signals
- Recommendation tasks: Generating trading recommendations
- Want list check: Monitoring target prices for alerts
"""
from app.tasks.celery_app import celery_app
from app.tasks.want_list_check import check_want_list_prices

__all__ = ["celery_app", "check_want_list_prices"]

