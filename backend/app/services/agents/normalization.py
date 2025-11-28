"""
Normalization service for mapping marketplace data to canonical card identities.
"""
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, Marketplace
from app.services.ingestion import ScryfallAdapter, CardListing, CardPrice

logger = structlog.get_logger()


class NormalizationService:
    """
    Service for normalizing marketplace data to canonical card identities.
    
    Uses Scryfall as the canonical source for card data and handles:
    - Mapping marketplace-specific identifiers to Scryfall IDs
    - Creating/updating card records from Scryfall data
    - Handling card variants (art, printings, etc.)
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize the normalization service.
        
        Args:
            db: Database session.
        """
        self.db = db
        self.scryfall = ScryfallAdapter()
    
    async def get_or_create_card(
        self,
        name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> Card | None:
        """
        Get or create a card record from Scryfall data.
        
        Args:
            name: Card name.
            set_code: Set code.
            collector_number: Collector number.
            scryfall_id: Scryfall ID if known.
            
        Returns:
            Card object or None if not found.
        """
        # Try to find existing card by Scryfall ID
        if scryfall_id:
            query = select(Card).where(Card.scryfall_id == scryfall_id)
            result = await self.db.execute(query)
            card = result.scalar_one_or_none()
            if card:
                return card
        
        # Try to find by set and collector number
        if set_code and collector_number:
            query = select(Card).where(
                Card.set_code == set_code.upper(),
                Card.collector_number == collector_number,
            )
            result = await self.db.execute(query)
            card = result.scalar_one_or_none()
            if card:
                return card
        
        # Fetch from Scryfall and create
        try:
            scryfall_data = await self.scryfall.fetch_card_by_id(scryfall_id) if scryfall_id else None
            
            if not scryfall_data:
                # Search by name and set
                results = await self.scryfall.search_cards(f'!"{name}" set:{set_code}', limit=1)
                if results:
                    scryfall_data = results[0]
            
            if not scryfall_data:
                logger.warning("Card not found on Scryfall", name=name, set_code=set_code)
                return None
            
            card = await self.create_card_from_scryfall(scryfall_data)
            return card
            
        except Exception as e:
            logger.error("Failed to fetch card from Scryfall", name=name, error=str(e))
            return None
    
    async def create_card_from_scryfall(self, scryfall_data: dict) -> Card:
        """
        Create a card record from Scryfall data.
        
        Args:
            scryfall_data: Normalized Scryfall card data.
            
        Returns:
            Created Card object.
        """
        # Check if already exists
        query = select(Card).where(Card.scryfall_id == scryfall_data["scryfall_id"])
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing card
            for key, value in scryfall_data.items():
                if key not in ("prices",) and hasattr(existing, key):
                    setattr(existing, key, value)
            await self.db.flush()
            return existing
        
        # Create new card
        card = Card(
            scryfall_id=scryfall_data["scryfall_id"],
            oracle_id=scryfall_data.get("oracle_id"),
            name=scryfall_data["name"],
            set_code=scryfall_data["set_code"],
            set_name=scryfall_data.get("set_name"),
            collector_number=scryfall_data["collector_number"],
            rarity=scryfall_data.get("rarity"),
            mana_cost=scryfall_data.get("mana_cost"),
            cmc=scryfall_data.get("cmc"),
            type_line=scryfall_data.get("type_line"),
            oracle_text=scryfall_data.get("oracle_text"),
            colors=scryfall_data.get("colors"),
            color_identity=scryfall_data.get("color_identity"),
            power=scryfall_data.get("power"),
            toughness=scryfall_data.get("toughness"),
            legalities=scryfall_data.get("legalities"),
            image_url=scryfall_data.get("image_url"),
            image_url_small=scryfall_data.get("image_url_small"),
            image_url_large=scryfall_data.get("image_url_large"),
        )
        
        self.db.add(card)
        await self.db.flush()
        return card
    
    async def normalize_listing(
        self,
        listing: CardListing,
        marketplace: Marketplace,
    ) -> dict:
        """
        Normalize a marketplace listing to canonical format.
        
        Args:
            listing: Raw marketplace listing.
            marketplace: Marketplace the listing is from.
            
        Returns:
            Normalized listing data dict.
        """
        # Find or create the card
        card = await self.get_or_create_card(
            name=listing.card_name,
            set_code=listing.set_code,
            collector_number=listing.collector_number,
            scryfall_id=listing.scryfall_id,
        )
        
        if not card:
            raise ValueError(f"Could not normalize card: {listing.card_name}")
        
        return {
            "card_id": card.id,
            "marketplace_id": marketplace.id,
            "condition": listing.condition,
            "language": listing.language,
            "is_foil": listing.is_foil,
            "price": listing.price,
            "currency": listing.currency,
            "quantity": listing.quantity,
            "seller_name": listing.seller_name,
            "seller_rating": listing.seller_rating,
            "external_id": listing.external_id,
            "listing_url": listing.listing_url,
        }
    
    async def normalize_price(
        self,
        price_data: CardPrice,
        marketplace: Marketplace,
    ) -> dict:
        """
        Normalize marketplace price data.
        
        Args:
            price_data: Raw price data.
            marketplace: Marketplace the price is from.
            
        Returns:
            Normalized price data dict.
        """
        card = await self.get_or_create_card(
            name=price_data.card_name,
            set_code=price_data.set_code,
            collector_number=price_data.collector_number,
            scryfall_id=price_data.scryfall_id,
        )
        
        if not card:
            raise ValueError(f"Could not normalize card: {price_data.card_name}")
        
        return {
            "card_id": card.id,
            "marketplace_id": marketplace.id,
            "snapshot_time": price_data.snapshot_time,
            "price": price_data.price,
            "currency": price_data.currency,
            "price_foil": price_data.price_foil,
            "min_price": price_data.price_low,
            "max_price": price_data.price_high,
            "avg_price": price_data.price_mid,
            "median_price": price_data.price_market,
            "num_listings": price_data.num_listings,
            "total_quantity": price_data.total_quantity,
        }
    
    async def get_or_create_marketplace(
        self,
        name: str,
        slug: str,
        base_url: str,
        **kwargs,
    ) -> Marketplace:
        """
        Get or create a marketplace record.
        
        Args:
            name: Marketplace display name.
            slug: Unique identifier.
            base_url: Base URL.
            **kwargs: Additional marketplace attributes.
            
        Returns:
            Marketplace object.
        """
        query = select(Marketplace).where(Marketplace.slug == slug)
        result = await self.db.execute(query)
        marketplace = result.scalar_one_or_none()
        
        if marketplace:
            return marketplace
        
        marketplace = Marketplace(
            name=name,
            slug=slug,
            base_url=base_url,
            **kwargs,
        )
        self.db.add(marketplace)
        await self.db.flush()
        
        return marketplace
    
    async def sync_cards_from_set(
        self,
        set_code: str,
        limit: int | None = None,
    ) -> int:
        """
        Sync all cards from a set using Scryfall.
        
        Args:
            set_code: Set code to sync.
            limit: Maximum number of cards to sync.
            
        Returns:
            Number of cards synced.
        """
        try:
            cards_data = await self.scryfall.fetch_set_cards(set_code)
            
            if limit:
                cards_data = cards_data[:limit]
            
            count = 0
            for card_data in cards_data:
                await self.create_card_from_scryfall(card_data)
                count += 1
            
            await self.db.commit()
            logger.info("Synced cards from set", set_code=set_code, count=count)
            return count
            
        except Exception as e:
            logger.error("Failed to sync set", set_code=set_code, error=str(e))
            raise
    
    async def close(self) -> None:
        """Clean up resources."""
        await self.scryfall.close()

