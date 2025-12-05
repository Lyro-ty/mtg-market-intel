"""
Celery application configuration.
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "mtg_market_intel",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.data_seeding",
        "app.tasks.ingestion",
        "app.tasks.analytics",
        "app.tasks.recommendations",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # Comprehensive data seeding: Current + Historical (30d/90d/6m/1y)
        # Runs on startup (via main.py) and every 6 hours to refresh historical data
        "seed-comprehensive-data": {
            "task": "app.tasks.data_seeding.seed_comprehensive_price_data",
            "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
            "options": {"queue": "ingestion"},
        },
        
        # Aggressively collect current price data every 5 minutes (data older than 24h is stale)
        "collect-price-data": {
            "task": "app.tasks.ingestion.collect_price_data",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
            "options": {"queue": "ingestion"},
        },
        
        # Collect INVENTORY card prices every 2 minutes (highest priority)
        "collect-inventory-prices": {
            "task": "app.tasks.ingestion.collect_inventory_prices",
            "schedule": crontab(minute="*/2"),  # Every 2 minutes
            "options": {"queue": "ingestion"},
        },
        
        # Import MTGJSON historical prices daily at 3 AM (backup/refresh)
        "import-mtgjson-historical": {
            "task": "app.tasks.ingestion.import_mtgjson_historical_prices",
            "schedule": crontab(minute=0, hour=3),
            "options": {"queue": "ingestion"},
        },
        
        # Run analytics hourly
        "run-analytics": {
            "task": "app.tasks.analytics.run_analytics",
            "schedule": crontab(minute=0, hour=f"*/{settings.analytics_interval_hours}"),
            "options": {"queue": "analytics"},
        },
        
        # Generate recommendations every 6 hours
        "generate-recommendations": {
            "task": "app.tasks.recommendations.generate_recommendations",
            "schedule": crontab(minute=0, hour=f"*/{settings.recommendations_interval_hours}"),
            "options": {"queue": "recommendations"},
        },
        
        # Daily card data sync at 2 AM
        "sync-card-data": {
            "task": "app.tasks.ingestion.sync_card_catalog",
            "schedule": crontab(minute=0, hour=2),
            "options": {"queue": "ingestion"},
        },
        
        # Bulk vectorize all cards every evening at 11 PM
        # This ensures all cards have pre-computed embeddings for faster recommendations
        "bulk-vectorize-cards": {
            "task": "app.tasks.ingestion.bulk_vectorize_cards",
            "schedule": crontab(minute=0, hour=23),  # 11 PM UTC
            "options": {"queue": "ingestion"},
        },
        
        # Download Scryfall bulk data daily at 2 AM
        # This provides comprehensive historical price coverage
        "download-scryfall-bulk": {
            "task": "app.tasks.data_seeding.download_scryfall_bulk_data_task",
            "schedule": crontab(minute=0, hour=2),  # 2 AM UTC
            "options": {"queue": "ingestion"},
        },
    },
    
    # Task routing
    task_routes={
        "app.tasks.data_seeding.*": {"queue": "ingestion"},
        "app.tasks.ingestion.*": {"queue": "ingestion"},
        "app.tasks.analytics.*": {"queue": "analytics"},
        "app.tasks.recommendations.*": {"queue": "recommendations"},
    },
    
    # Default queue
    task_default_queue="default",
)


# Autodiscover tasks
celery_app.autodiscover_tasks(["app.tasks"])

