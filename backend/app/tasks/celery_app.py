"""
Celery application configuration.

Simplified pricing-focused task schedule:
- Bulk price refresh: Every 12 hours (Scryfall bulk data)
- Inventory price refresh: Every 4 hours (Scryfall API)
- Condition price refresh: Every 6 hours (TCGPlayer API or multipliers)
- Search embeddings refresh: Daily at 3 AM
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
        "app.tasks.ingestion_v2",  # Optimized parallel ingestion
        "app.tasks.analytics",
        "app.tasks.recommendations",
        "app.tasks.pricing",
        "app.tasks.tournaments",
        "app.tasks.search",
        "app.tasks.want_list_check",
        "app.tasks.collection_stats",
        "app.tasks.sets_sync",
        "app.tasks.ban_detection",
        "app.tasks.meta_signals",
        "app.tasks.supply_signals",
        "app.tasks.arbitrage_signals",
        "app.tasks.news_collection",
        "app.tasks.buylist_collection",
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

    # Simplified beat schedule for pricing-focused tasks
    beat_schedule={
        # Parallel price collection: Dispatch parallel adapter tasks every 5 minutes
        # Uses optimized bulk operations and Redis caching
        "ingestion-parallel-collection": {
            "task": "app.tasks.ingestion_v2.dispatch_price_collection",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
            "args": [500],  # batch_size
        },

        # Bulk price refresh: Download Scryfall bulk data every 12 hours
        # Provides comprehensive price coverage for all cards
        "pricing-bulk-refresh": {
            "task": "app.tasks.pricing.bulk_refresh",
            "schedule": crontab(hour="*/12"),  # Every 12 hours
        },

        # Inventory price refresh: Update prices for inventory cards every 4 hours
        # Uses Scryfall API for cards in user collections
        "pricing-inventory-refresh": {
            "task": "app.tasks.pricing.inventory_refresh",
            "schedule": crontab(hour="*/4"),  # Every 4 hours
        },

        # Condition price refresh: Get condition-specific prices every 6 hours
        # Uses TCGPlayer API for high-value cards, multipliers for cheaper ones
        "pricing-condition-refresh": {
            "task": "app.tasks.pricing.condition_refresh",
            "schedule": crontab(hour="*/6"),  # Every 6 hours
        },

        # Search embeddings refresh: Update card embeddings daily at 3 AM
        # Ensures similarity search remains accurate
        "search-refresh-embeddings": {
            "task": "app.tasks.search.refresh_embeddings",
            "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
        },

        # Tournament data ingestion: Daily at 4 AM
        # Fetches recent tournament results and updates meta statistics
        "tournaments-ingest-recent": {
            "task": "app.tasks.tournaments.ingest_recent",
            "schedule": crontab(hour=4, minute=0),  # Daily at 4 AM
        },

        # Want list price check: Every 15 minutes
        # Checks want list items and creates notifications when target prices are hit
        "want-list-price-check": {
            "task": "check_want_list_prices",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
        },

        # Collection stats update: Every hour
        # Updates stats for users with stale collection data
        "collection-stats-update": {
            "task": "update_collection_stats",
            "schedule": crontab(minute=30),  # Every hour at :30
        },

        # MTG sets sync: Daily at 2 AM
        # Syncs set metadata from Scryfall for collection completion tracking
        "sets-sync": {
            "task": "sync_mtg_sets",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
        },

        # Recommendation generation: Every 6 hours
        # Generates buy/sell/hold recommendations based on signals and metrics
        "generate-recommendations": {
            "task": "app.tasks.recommendations.generate_recommendations",
            "schedule": crontab(hour="*/6", minute=0),  # Every 6 hours at :00
        },

        # Recommendation outcome evaluation: Every hour at :30
        # Evaluates expired recommendations against actual price data
        "evaluate-recommendation-outcomes": {
            "task": "app.tasks.recommendations.evaluate_outcomes",
            "schedule": crontab(minute=30),  # Every hour at :30
        },

        # Meta signals generation: Every 6 hours
        # Generates META_SPIKE and META_DROP signals from tournament data
        "meta-signals-generation": {
            "task": "generate_meta_signals",
            "schedule": crontab(hour="*/6", minute=15),  # Every 6 hours at :15
        },

        # Supply signals generation: Every 6 hours
        # Generates SUPPLY_LOW and SUPPLY_VELOCITY signals from marketplace data
        "supply-signals-generation": {
            "task": "generate_supply_signals",
            "schedule": crontab(hour="*/6", minute=20),  # Every 6 hours at :20
        },

        # Arbitrage signals generation: Every 4 hours
        # Compares prices across marketplaces to find arbitrage opportunities
        "arbitrage-signals-generation": {
            "task": "generate_arbitrage_signals",
            "schedule": crontab(hour="*/4", minute=25),  # Every 4 hours at :25
        },

        # Price prediction signals: Every 12 hours
        # Technical analysis for momentum, breakouts, and trend reversals
        "prediction-signals-generation": {
            "task": "generate_prediction_signals",
            "schedule": crontab(hour="*/12", minute=35),  # Every 12 hours at :35
        },

        # News collection: Every 6 hours
        # Fetches MTG news from RSS feeds and extracts card mentions
        "news-collection": {
            "task": "collect_news",
            "schedule": crontab(hour="*/6", minute=45),  # Every 6 hours at :45
        },

        # Buylist collection: Daily at 6 AM
        # Collects buylist prices from Card Kingdom for inventory cards and high-value cards
        "buylist-collection": {
            "task": "app.tasks.buylist_collection.collect_buylist_prices",
            "schedule": crontab(hour=6, minute=0),  # Daily at 6 AM
        },
    },

    # Task routing
    task_routes={
        "app.tasks.data_seeding.*": {"queue": "ingestion"},
        "app.tasks.ingestion.*": {"queue": "ingestion"},
        "app.tasks.ingestion_v2.*": {"queue": "ingestion"},
        "app.tasks.analytics.*": {"queue": "analytics"},
        "app.tasks.recommendations.*": {"queue": "recommendations"},
        "app.tasks.pricing.*": {"queue": "ingestion"},
        "app.tasks.search.*": {"queue": "ingestion"},
        "app.tasks.tournaments.*": {"queue": "ingestion"},
        "check_want_list_prices": {"queue": "analytics"},
        "update_collection_stats": {"queue": "analytics"},
        "update_user_collection_stats": {"queue": "analytics"},
        "sync_mtg_sets": {"queue": "ingestion"},
        "detect_ban_changes": {"queue": "analytics"},
        "generate_meta_signals": {"queue": "analytics"},
        "generate_supply_signals": {"queue": "analytics"},
        "generate_arbitrage_signals": {"queue": "analytics"},
        "generate_prediction_signals": {"queue": "analytics"},
        "collect_news": {"queue": "ingestion"},
        "app.tasks.buylist_collection.*": {"queue": "ingestion"},
    },

    # Default queue
    task_default_queue="default",
)


# Autodiscover tasks
celery_app.autodiscover_tasks(["app.tasks"])
