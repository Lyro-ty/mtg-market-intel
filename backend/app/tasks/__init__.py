"""
Celery tasks for background job processing.

Includes:
- Ingestion tasks: Scraping marketplace data
- Analytics tasks: Computing metrics and signals
- Recommendation tasks: Generating trading recommendations
- Want list check: Monitoring target prices for alerts
- Sets sync: Syncing MTG sets from Scryfall
- Collection stats: Updating user collection metrics
"""
from app.tasks.celery_app import celery_app
from app.tasks.collection_stats import update_collection_stats, update_user_collection_stats
from app.tasks.sets_sync import sync_mtg_sets
from app.tasks.want_list_check import check_want_list_prices

__all__ = [
    "celery_app",
    "check_want_list_prices",
    "sync_mtg_sets",
    "update_collection_stats",
    "update_user_collection_stats",
]

