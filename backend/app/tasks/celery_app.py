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
        # Scrape marketplace data every 30 minutes
        "scrape-marketplaces": {
            "task": "app.tasks.ingestion.scrape_all_marketplaces",
            "schedule": crontab(minute=f"*/{settings.scrape_interval_minutes}"),
            "options": {"queue": "ingestion"},
        },
        
        # Scrape INVENTORY cards every 15 minutes (higher priority)
        "scrape-inventory": {
            "task": "app.tasks.ingestion.scrape_inventory_cards",
            "schedule": crontab(minute="*/15"),
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
    },
    
    # Task routing
    task_routes={
        "app.tasks.ingestion.*": {"queue": "ingestion"},
        "app.tasks.analytics.*": {"queue": "analytics"},
        "app.tasks.recommendations.*": {"queue": "recommendations"},
    },
    
    # Default queue
    task_default_queue="default",
)


# Autodiscover tasks
celery_app.autodiscover_tasks(["app.tasks"])

