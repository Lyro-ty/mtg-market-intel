"""
Script to add Mock marketplace for testing listings functionality.

The Mock adapter is the only adapter that currently returns individual listings.
This script adds it to the database so you can test the listings feature.
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select

from app.db.session import async_session_maker
from app.models import Marketplace

async def add_mock_marketplace():
    """Add Mock marketplace to database if it doesn't exist."""
    async with async_session_maker() as db:
        # Check if mock marketplace exists
        query = select(Marketplace).where(Marketplace.slug == "mock")
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"Mock marketplace already exists: {existing.name} (ID: {existing.id})")
            if not existing.is_enabled:
                existing.is_enabled = True
                await db.commit()
                print("Enabled Mock marketplace")
            return existing
        
        # Create new mock marketplace
        mock_marketplace = Marketplace(
            name="Mock Market",
            slug="mock",
            base_url="https://mock-marketplace.example.com",
            api_url=None,
            is_enabled=True,
            supports_api=False,
            default_currency="USD",
            rate_limit_seconds=0.1,  # Fast for testing
        )
        db.add(mock_marketplace)
        await db.commit()
        
        print(f"Created Mock marketplace: {mock_marketplace.name} (ID: {mock_marketplace.id})")
        print("Mock marketplace is enabled and ready to use!")
        print("\nTo get listings:")
        print("1. Make sure you have cards in the database")
        print("2. The scrape task will automatically use the Mock adapter")
        print("3. Listings will be generated for each card scraped")
        
        return mock_marketplace

if __name__ == "__main__":
    asyncio.run(add_mock_marketplace())



