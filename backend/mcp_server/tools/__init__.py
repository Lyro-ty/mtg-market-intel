"""MCP Server tools - all available tool functions."""

# Card tools
from mcp_server.tools.cards import (
    get_card_by_id,
    get_card_by_name,
    get_card_by_scryfall_id,
    search_cards,
    get_random_cards,
)

# Price tools
from mcp_server.tools.prices import (
    get_current_price,
    get_price_history,
    get_top_movers,
    get_market_overview,
    get_market_index,
)

# Schema tools
from mcp_server.tools.schema import (
    list_tables,
    describe_table,
    get_model_schema,
    get_api_endpoints,
    describe_endpoint,
)

# Database tools
from mcp_server.tools.database import (
    run_query,
    count_records,
    get_sample_records,
    write_run_migration,
)

# Health tools
from mcp_server.tools.health import (
    check_db_connection,
    check_redis_connection,
    check_containers,
    get_data_freshness,
    get_environment,
    get_migration_status,
)

# Log tools
from mcp_server.tools.logs import (
    get_container_logs,
    get_recent_errors,
)

# Task tools
from mcp_server.tools.tasks import (
    list_celery_tasks,
    get_task_history,
    trigger_price_collection,
    trigger_analytics,
    trigger_recommendations,
    trigger_scryfall_import,
)

# Cache tools
from mcp_server.tools.cache import (
    list_cache_keys,
    get_cache_value,
    get_cache_stats,
    write_clear_cache,
    write_invalidate_cache_key,
)

# Inventory tools
from mcp_server.tools.inventory import (
    list_inventory,
    get_inventory_item,
    get_portfolio_value,
    write_add_inventory_item,
    write_remove_inventory_item,
    write_update_inventory_item,
)

# Recommendations tools
from mcp_server.tools.recommendations import (
    get_recommendations,
    get_signals,
)

# Documentation tools
from mcp_server.tools.docs import (
    get_design_docs,
    read_design_doc,
    get_claude_md,
)

# Implementation validation tools
from mcp_server.tools.implementation import (
    get_implementation_status,
    list_missing_tests,
    get_schema_differences,
    analyze_dead_letter_queue,
    get_signal_coverage,
    get_empty_tables,
)

__all__ = [
    # Cards
    "get_card_by_id",
    "get_card_by_name",
    "get_card_by_scryfall_id",
    "search_cards",
    "get_random_cards",
    # Prices
    "get_current_price",
    "get_price_history",
    "get_top_movers",
    "get_market_overview",
    "get_market_index",
    # Schema
    "list_tables",
    "describe_table",
    "get_model_schema",
    "get_api_endpoints",
    "describe_endpoint",
    # Database
    "run_query",
    "count_records",
    "get_sample_records",
    "write_run_migration",
    # Health
    "check_db_connection",
    "check_redis_connection",
    "check_containers",
    "get_data_freshness",
    "get_environment",
    "get_migration_status",
    # Logs
    "get_container_logs",
    "get_recent_errors",
    # Tasks
    "list_celery_tasks",
    "get_task_history",
    "trigger_price_collection",
    "trigger_analytics",
    "trigger_recommendations",
    "trigger_scryfall_import",
    # Cache
    "list_cache_keys",
    "get_cache_value",
    "get_cache_stats",
    "write_clear_cache",
    "write_invalidate_cache_key",
    # Inventory
    "list_inventory",
    "get_inventory_item",
    "get_portfolio_value",
    "write_add_inventory_item",
    "write_remove_inventory_item",
    "write_update_inventory_item",
    # Recommendations
    "get_recommendations",
    "get_signals",
    # Docs
    "get_design_docs",
    "read_design_doc",
    "get_claude_md",
    # Implementation validation
    "get_implementation_status",
    "list_missing_tests",
    "get_schema_differences",
    "analyze_dead_letter_queue",
    "get_signal_coverage",
    "get_empty_tables",
]
