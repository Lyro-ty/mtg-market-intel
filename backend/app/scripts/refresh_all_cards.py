#!/usr/bin/env python3
"""
Script to refresh all cards in the database via the API.

This script:
1. Fetches all card IDs from the database
2. Calls the refresh endpoint for each card
3. Optionally runs in batches with rate limiting

Usage:
    # Refresh all cards (synchronous, waits for each to complete)
    python -m app.scripts.refresh_all_cards
    
    # Refresh with custom settings
    python -m app.scripts.refresh_all_cards --base-url http://localhost:8000 --batch-size 5 --limit 100
    
    # Refresh asynchronously (faster, but doesn't wait for completion)
    python -m app.scripts.refresh_all_cards --async
"""
import asyncio
import sys

# Add parent directory to path for imports (works in Docker)
sys.path.insert(0, "/app")

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.models import Card

logger = structlog.get_logger()


async def get_all_card_ids(db: AsyncSession) -> list[int]:
    """Get all card IDs from the database."""
    query = select(Card.id).order_by(Card.id)
    result = await db.execute(query)
    return [row[0] for row in result.all()]


async def refresh_card(
    client: httpx.AsyncClient,
    card_id: int,
    base_url: str = "http://localhost:8000",
    sync: bool = True,
) -> dict:
    """
    Refresh a single card via the API.
    
    Args:
        client: HTTP client
        card_id: Card ID to refresh
        base_url: API base URL
        sync: Whether to run synchronously (waits for completion)
        
    Returns:
        Response data or error info
    """
    url = f"{base_url}/api/cards/{card_id}/refresh"
    params = {"sync": "true" if sync else "false"}
    
    try:
        response = await client.post(url, params=params, timeout=300.0)  # 5 min timeout for sync
        response.raise_for_status()
        return {"card_id": card_id, "status": "success", "data": response.json()}
    except httpx.HTTPStatusError as e:
        logger.warning(
            "Failed to refresh card",
            card_id=card_id,
            status_code=e.response.status_code,
            error=e.response.text[:200],
        )
        return {"card_id": card_id, "status": "error", "error": str(e)}
    except Exception as e:
        logger.warning("Error refreshing card", card_id=card_id, error=str(e))
        return {"card_id": card_id, "status": "error", "error": str(e)}


async def refresh_all_cards(
    base_url: str = "http://localhost:8000",
    batch_size: int = 10,
    delay_between_batches: float = 1.0,
    sync: bool = True,
    limit: int | None = None,
) -> dict:
    """
    Refresh all cards in the database.
    
    Args:
        base_url: API base URL
        batch_size: Number of cards to refresh concurrently
        delay_between_batches: Seconds to wait between batches
        sync: Whether to run synchronously (waits for each card to complete)
        limit: Optional limit on number of cards to refresh (for testing)
        
    Returns:
        Summary of refresh results
    """
    # Connect to database to get card IDs
    engine = create_async_engine(
        settings.database_url_computed,
        echo=False,
        pool_pre_ping=True,
    )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with session_maker() as db:
            card_ids = await get_all_card_ids(db)
            
            if limit:
                card_ids = card_ids[:limit]
                logger.info("Limited to first N cards", limit=limit, total=len(card_ids))
            
            logger.info("Starting card refresh", total_cards=len(card_ids))
    finally:
        await engine.dispose()
    
    # Refresh cards in batches
    results = {
        "total": len(card_ids),
        "success": 0,
        "errors": 0,
        "results": [],
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        for i in range(0, len(card_ids), batch_size):
            batch = card_ids[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(card_ids) + batch_size - 1) // batch_size
            
            logger.info(
                "Processing batch",
                batch=batch_num,
                total_batches=total_batches,
                batch_size=len(batch),
                cards=f"{i+1}-{min(i+batch_size, len(card_ids))}",
            )
            
            # Refresh cards in this batch concurrently
            tasks = [refresh_card(client, card_id, base_url, sync) for card_id in batch]
            batch_results = await asyncio.gather(*tasks)
            
            # Update summary
            for result in batch_results:
                results["results"].append(result)
                if result["status"] == "success":
                    results["success"] += 1
                else:
                    results["errors"] += 1
            
            # Log batch progress
            logger.info(
                "Batch completed",
                batch=batch_num,
                success=sum(1 for r in batch_results if r["status"] == "success"),
                errors=sum(1 for r in batch_results if r["status"] == "error"),
                total_so_far=len(results["results"]),
            )
            
            # Wait between batches (except for the last one)
            if i + batch_size < len(card_ids):
                await asyncio.sleep(delay_between_batches)
    
    logger.info(
        "Card refresh completed",
        total=results["total"],
        success=results["success"],
        errors=results["errors"],
    )
    
    return results


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Refresh all cards via the API")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of cards to refresh concurrently (default: 10)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to wait between batches (default: 1.0)",
    )
    parser.add_argument(
        "--async",
        dest="sync",
        action="store_false",
        help="Run refreshes asynchronously (don't wait for completion)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of cards to refresh (for testing)",
    )
    
    args = parser.parse_args()
    
    results = await refresh_all_cards(
        base_url=args.base_url,
        batch_size=args.batch_size,
        delay_between_batches=args.delay,
        sync=args.sync,
        limit=args.limit,
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("REFRESH SUMMARY")
    print("=" * 60)
    print(f"Total cards: {results['total']}")
    print(f"Successful: {results['success']}")
    print(f"Errors: {results['errors']}")
    print("=" * 60)
    
    if results["errors"] > 0:
        print("\nFailed cards:")
        for result in results["results"]:
            if result["status"] == "error":
                print(f"  Card ID {result['card_id']}: {result.get('error', 'Unknown error')}")
    
    return 0 if results["errors"] == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

