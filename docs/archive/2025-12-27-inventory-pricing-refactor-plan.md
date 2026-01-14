# Inventory, Pricing & Search Refactor Implementation Plan

**Status:** ✅ Implemented (2025-12-28)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the pricing ingestion system to provide reliable, fresh pricing with condition support, fix inventory valuations, add semantic search, and integrate tournament data from TopDeck.gg.

**Architecture:** Layered pricing (Scryfall bulk every 12h + API every 4h + TCGPlayer conditions every 6h), direct price comparison for top movers, acquisition-cost-based value index, unified semantic search across all pages, tournament data with attribution.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Celery, TimescaleDB, PostgreSQL, Next.js, TanStack Query, sentence-transformers (MiniLM-L6-v2)

**Design Document:** `docs/plans/2025-12-27-inventory-pricing-search-design.md`

---

## Phase 1: Core Pricing

### Task 1.1: Database Migration - Add Card Fields

**Files:**
- Create: `backend/alembic/versions/20251227_001_add_card_semantic_fields.py`
- Reference: `backend/app/models/card.py`

**Step 1: Create migration file**

```python
"""Add semantic search fields to cards table

Revision ID: 20251227_001
Revises: <previous_revision>
Create Date: 2025-12-27
"""
from alembic import op
import sqlalchemy as sa

revision = '20251227_001'
down_revision = None  # Set to latest revision
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('cards', sa.Column('keywords', sa.Text(), nullable=True))
    op.add_column('cards', sa.Column('flavor_text', sa.Text(), nullable=True))
    op.add_column('cards', sa.Column('edhrec_rank', sa.Integer(), nullable=True))
    op.add_column('cards', sa.Column('reserved_list', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('cards', sa.Column('meta_score', sa.Float(), nullable=True))

def downgrade() -> None:
    op.drop_column('cards', 'meta_score')
    op.drop_column('cards', 'reserved_list')
    op.drop_column('cards', 'edhrec_rank')
    op.drop_column('cards', 'flavor_text')
    op.drop_column('cards', 'keywords')
```

**Step 2: Update Card model**

In `backend/app/models/card.py`, add after line 60 (after `legalities`):

```python
    # Semantic search fields
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    flavor_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    edhrec_rank: Mapped[Optional[int]] = mapped_column(nullable=True)
    reserved_list: Mapped[bool] = mapped_column(default=False, nullable=False)
    meta_score: Mapped[Optional[float]] = mapped_column(nullable=True)
```

**Step 3: Run migration**

```bash
docker compose exec backend alembic upgrade head
```

Expected: Migration applies successfully

**Step 4: Verify columns exist**

```bash
docker compose exec db psql -U postgres -d mtg_market -c "\d cards" | grep -E "(keywords|flavor_text|edhrec_rank|reserved_list|meta_score)"
```

Expected: All 5 columns listed

**Step 5: Commit**

```bash
git add backend/alembic/versions/20251227_001_add_card_semantic_fields.py backend/app/models/card.py
git commit -m "feat: add semantic search fields to cards table"
```

---

### Task 1.2: Database Migration - Add Price Source Tracking

**Files:**
- Create: `backend/alembic/versions/20251227_002_add_price_source.py`
- Modify: `backend/app/models/price_snapshot.py`

**Step 1: Create migration file**

```python
"""Add source column to price_snapshots

Revision ID: 20251227_002
Revises: 20251227_001
Create Date: 2025-12-27
"""
from alembic import op
import sqlalchemy as sa

revision = '20251227_002'
down_revision = '20251227_001'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('price_snapshots', sa.Column(
        'source',
        sa.String(20),
        server_default='bulk',
        nullable=False
    ))
    op.create_index('ix_price_snapshots_source', 'price_snapshots', ['source'])

def downgrade() -> None:
    op.drop_index('ix_price_snapshots_source')
    op.drop_column('price_snapshots', 'source')
```

**Step 2: Update PriceSnapshot model**

In `backend/app/models/price_snapshot.py`, add the source field:

```python
    # Source tracking: 'bulk', 'api', 'tcgplayer', 'calculated'
    source: Mapped[str] = mapped_column(String(20), default='bulk', nullable=False)
```

**Step 3: Run migration**

```bash
docker compose exec backend alembic upgrade head
```

**Step 4: Commit**

```bash
git add backend/alembic/versions/20251227_002_add_price_source.py backend/app/models/price_snapshot.py
git commit -m "feat: add source tracking to price_snapshots"
```

---

### Task 1.3: Create Pricing Service - Bulk Import

**Files:**
- Create: `backend/app/services/pricing/__init__.py`
- Create: `backend/app/services/pricing/bulk_import.py`
- Create: `backend/tests/services/test_bulk_import.py`

**Step 1: Create pricing service directory**

```bash
mkdir -p backend/app/services/pricing
```

**Step 2: Create __init__.py**

```python
"""Pricing services for MTG Market Intel."""
from .bulk_import import BulkPriceImporter
from .valuation import InventoryValuator

__all__ = ["BulkPriceImporter", "InventoryValuator"]
```

**Step 3: Write failing test for BulkPriceImporter**

Create `backend/tests/services/test_bulk_import.py`:

```python
"""Tests for bulk price import service."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import json

from app.services.pricing.bulk_import import BulkPriceImporter


class TestBulkPriceImporter:
    """Test bulk price import from Scryfall."""

    @pytest.fixture
    def importer(self):
        return BulkPriceImporter()

    def test_parse_scryfall_prices_extracts_all_fields(self, importer):
        """Should extract USD, EUR, foil prices from Scryfall card data."""
        card_data = {
            "id": "abc-123",
            "oracle_id": "def-456",
            "name": "Lightning Bolt",
            "set": "lea",
            "collector_number": "161",
            "prices": {
                "usd": "450.00",
                "usd_foil": None,
                "eur": "400.00",
                "eur_foil": None,
                "tix": "0.50"
            },
            "keywords": ["Instant"],
            "flavor_text": "The spark ignites...",
            "edhrec_rank": 5,
            "reserved": True
        }

        prices = importer.parse_scryfall_prices(card_data)

        assert prices["usd"] == 450.00
        assert prices["usd_foil"] is None
        assert prices["eur"] == 400.00
        assert prices["keywords"] == ["Instant"]
        assert prices["flavor_text"] == "The spark ignites..."
        assert prices["edhrec_rank"] == 5
        assert prices["reserved"] is True

    def test_parse_scryfall_prices_handles_missing_prices(self, importer):
        """Should handle cards with no price data gracefully."""
        card_data = {
            "id": "abc-123",
            "name": "Test Card",
            "set": "tst",
            "collector_number": "1",
            "prices": {}
        }

        prices = importer.parse_scryfall_prices(card_data)

        assert prices["usd"] is None
        assert prices["eur"] is None

    @pytest.mark.asyncio
    async def test_get_bulk_data_url_returns_default_cards(self, importer):
        """Should fetch and return the default_cards bulk data URL."""
        mock_response = {
            "data": [
                {"type": "oracle_cards", "download_uri": "https://example.com/oracle"},
                {"type": "default_cards", "download_uri": "https://example.com/default"},
                {"type": "all_cards", "download_uri": "https://example.com/all"},
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=MagicMock(json=lambda: mock_response, status_code=200)
            )
            url = await importer.get_bulk_data_url()

        assert url == "https://example.com/default"
```

**Step 4: Run test to verify it fails**

```bash
docker compose exec backend pytest tests/services/test_bulk_import.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.pricing.bulk_import'"

**Step 5: Implement BulkPriceImporter**

Create `backend/app/services/pricing/bulk_import.py`:

```python
"""Bulk price import service using Scryfall bulk data."""
import asyncio
import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import httpx
import ijson
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.card import Card
from app.models.price_snapshot import PriceSnapshot
from app.models.marketplace import Marketplace

logger = logging.getLogger(__name__)

SCRYFALL_BULK_API = "https://api.scryfall.com/bulk-data"
SCRYFALL_USER_AGENT = "DualcasterDeals/1.0"


class BulkPriceImporter:
    """Import prices from Scryfall bulk data files."""

    def __init__(self):
        self.headers = {
            "User-Agent": SCRYFALL_USER_AGENT,
            "Accept": "application/json"
        }

    def parse_scryfall_prices(self, card_data: dict[str, Any]) -> dict[str, Any]:
        """Extract price and semantic fields from Scryfall card data."""
        prices = card_data.get("prices", {})

        def parse_price(val: Optional[str]) -> Optional[float]:
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        return {
            "scryfall_id": card_data.get("id"),
            "oracle_id": card_data.get("oracle_id"),
            "name": card_data.get("name"),
            "set_code": card_data.get("set"),
            "collector_number": card_data.get("collector_number"),
            # Prices
            "usd": parse_price(prices.get("usd")),
            "usd_foil": parse_price(prices.get("usd_foil")),
            "usd_etched": parse_price(prices.get("usd_etched")),
            "eur": parse_price(prices.get("eur")),
            "eur_foil": parse_price(prices.get("eur_foil")),
            "tix": parse_price(prices.get("tix")),
            # Semantic fields
            "keywords": card_data.get("keywords", []),
            "flavor_text": card_data.get("flavor_text"),
            "edhrec_rank": card_data.get("edhrec_rank"),
            "reserved": card_data.get("reserved", False),
        }

    async def get_bulk_data_url(self, data_type: str = "default_cards") -> str:
        """Fetch the current bulk data download URL from Scryfall."""
        async with httpx.AsyncClient(headers=self.headers) as client:
            response = await client.get(SCRYFALL_BULK_API)
            response.raise_for_status()
            data = response.json()

        for item in data.get("data", []):
            if item.get("type") == data_type:
                return item["download_uri"]

        raise ValueError(f"Bulk data type '{data_type}' not found")

    async def download_bulk_file(self, url: str, dest_path: Path) -> None:
        """Download bulk data file with streaming."""
        async with httpx.AsyncClient(headers=self.headers, timeout=600.0) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

    async def stream_cards(self, file_path: Path) -> AsyncIterator[dict[str, Any]]:
        """Stream parse cards from bulk JSON file."""
        loop = asyncio.get_event_loop()

        def parse_sync():
            with open(file_path, "rb") as f:
                parser = ijson.items(f, "item")
                for card in parser:
                    yield card

        for card in await loop.run_in_executor(None, lambda: list(parse_sync())):
            yield card

    async def import_prices(
        self,
        db: AsyncSession,
        progress_callback: Optional[callable] = None
    ) -> dict[str, int]:
        """
        Download and import all prices from Scryfall bulk data.

        Returns dict with counts: cards_updated, snapshots_created, errors
        """
        stats = {"cards_updated": 0, "snapshots_created": 0, "errors": 0}

        # Get bulk data URL
        url = await self.get_bulk_data_url()
        logger.info(f"Downloading bulk data from {url}")

        # Download to temp file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            await self.download_bulk_file(url, tmp_path)
            logger.info(f"Downloaded to {tmp_path}")

            # Get marketplace IDs
            tcgplayer = await self._get_or_create_marketplace(db, "tcgplayer", "TCGPlayer")
            cardmarket = await self._get_or_create_marketplace(db, "cardmarket", "Cardmarket")

            now = datetime.now(timezone.utc)
            batch_size = 500
            batch = []

            async for card_data in self.stream_cards(tmp_path):
                try:
                    parsed = self.parse_scryfall_prices(card_data)

                    # Update card semantic fields
                    await self._update_card_fields(db, parsed)
                    stats["cards_updated"] += 1

                    # Create price snapshots
                    snapshots = self._create_snapshots(parsed, now, tcgplayer.id, cardmarket.id)
                    batch.extend(snapshots)

                    if len(batch) >= batch_size:
                        await self._insert_snapshots(db, batch)
                        stats["snapshots_created"] += len(batch)
                        batch = []

                        if progress_callback:
                            progress_callback(stats)

                except Exception as e:
                    logger.warning(f"Error processing card: {e}")
                    stats["errors"] += 1

            # Insert remaining batch
            if batch:
                await self._insert_snapshots(db, batch)
                stats["snapshots_created"] += len(batch)

            await db.commit()

        finally:
            tmp_path.unlink(missing_ok=True)

        return stats

    async def _get_or_create_marketplace(
        self, db: AsyncSession, slug: str, name: str
    ) -> Marketplace:
        """Get or create a marketplace by slug."""
        result = await db.execute(
            select(Marketplace).where(Marketplace.slug == slug)
        )
        marketplace = result.scalar_one_or_none()

        if not marketplace:
            marketplace = Marketplace(slug=slug, name=name)
            db.add(marketplace)
            await db.flush()

        return marketplace

    async def _update_card_fields(self, db: AsyncSession, parsed: dict) -> None:
        """Update card with semantic fields from Scryfall."""
        if not parsed.get("scryfall_id"):
            return

        await db.execute(
            update(Card)
            .where(Card.scryfall_id == parsed["scryfall_id"])
            .values(
                keywords=json.dumps(parsed.get("keywords", [])),
                flavor_text=parsed.get("flavor_text"),
                edhrec_rank=parsed.get("edhrec_rank"),
                reserved_list=parsed.get("reserved", False),
            )
        )

    def _create_snapshots(
        self,
        parsed: dict,
        timestamp: datetime,
        tcgplayer_id: int,
        cardmarket_id: int
    ) -> list[dict]:
        """Create snapshot dicts for insertion."""
        snapshots = []
        scryfall_id = parsed.get("scryfall_id")

        if not scryfall_id:
            return snapshots

        # USD (TCGPlayer) - Non-foil
        if parsed.get("usd"):
            snapshots.append({
                "scryfall_id": scryfall_id,
                "marketplace_id": tcgplayer_id,
                "time": timestamp,
                "price": parsed["usd"],
                "currency": "USD",
                "condition": "NEAR_MINT",
                "is_foil": False,
                "source": "bulk",
            })

        # USD Foil (TCGPlayer)
        if parsed.get("usd_foil"):
            snapshots.append({
                "scryfall_id": scryfall_id,
                "marketplace_id": tcgplayer_id,
                "time": timestamp,
                "price": parsed["usd_foil"],
                "currency": "USD",
                "condition": "NEAR_MINT",
                "is_foil": True,
                "source": "bulk",
            })

        # EUR (Cardmarket) - Non-foil
        if parsed.get("eur"):
            snapshots.append({
                "scryfall_id": scryfall_id,
                "marketplace_id": cardmarket_id,
                "time": timestamp,
                "price": parsed["eur"],
                "currency": "EUR",
                "condition": "NEAR_MINT",
                "is_foil": False,
                "source": "bulk",
            })

        # EUR Foil (Cardmarket)
        if parsed.get("eur_foil"):
            snapshots.append({
                "scryfall_id": scryfall_id,
                "marketplace_id": cardmarket_id,
                "time": timestamp,
                "price": parsed["eur_foil"],
                "currency": "EUR",
                "condition": "NEAR_MINT",
                "is_foil": True,
                "source": "bulk",
            })

        return snapshots

    async def _insert_snapshots(self, db: AsyncSession, snapshots: list[dict]) -> None:
        """Bulk insert snapshots, joining on card_id."""
        if not snapshots:
            return

        # Get card IDs for scryfall_ids
        scryfall_ids = list(set(s["scryfall_id"] for s in snapshots))
        result = await db.execute(
            select(Card.id, Card.scryfall_id).where(Card.scryfall_id.in_(scryfall_ids))
        )
        id_map = {row.scryfall_id: row.id for row in result}

        # Build insert values
        values = []
        for s in snapshots:
            card_id = id_map.get(s["scryfall_id"])
            if card_id:
                values.append({
                    "card_id": card_id,
                    "marketplace_id": s["marketplace_id"],
                    "time": s["time"],
                    "price": s["price"],
                    "currency": s["currency"],
                    "condition": s["condition"],
                    "is_foil": s["is_foil"],
                    "source": s["source"],
                    "language": "ENGLISH",
                })

        if values:
            stmt = insert(PriceSnapshot).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["time", "card_id", "marketplace_id", "condition", "is_foil", "language"],
                set_={
                    "price": stmt.excluded.price,
                    "source": stmt.excluded.source,
                }
            )
            await db.execute(stmt)
```

**Step 6: Run tests**

```bash
docker compose exec backend pytest tests/services/test_bulk_import.py -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add backend/app/services/pricing/ backend/tests/services/test_bulk_import.py
git commit -m "feat: add bulk price import service"
```

---

### Task 1.4: Create Pricing Service - Valuation

**Files:**
- Create: `backend/app/services/pricing/valuation.py`
- Create: `backend/tests/services/test_valuation.py`

**Step 1: Write failing test**

Create `backend/tests/services/test_valuation.py`:

```python
"""Tests for inventory valuation service."""
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from app.services.pricing.valuation import InventoryValuator, ConditionMultiplier


class TestConditionMultiplier:
    """Test condition-based price adjustments."""

    def test_near_mint_is_100_percent(self):
        assert ConditionMultiplier.get("NEAR_MINT") == 1.0

    def test_lightly_played_is_87_percent(self):
        assert ConditionMultiplier.get("LIGHTLY_PLAYED") == 0.87

    def test_moderately_played_is_72_percent(self):
        assert ConditionMultiplier.get("MODERATELY_PLAYED") == 0.72

    def test_heavily_played_is_55_percent(self):
        assert ConditionMultiplier.get("HEAVILY_PLAYED") == 0.55

    def test_damaged_is_35_percent(self):
        assert ConditionMultiplier.get("DAMAGED") == 0.35

    def test_unknown_condition_defaults_to_100_percent(self):
        assert ConditionMultiplier.get("UNKNOWN") == 1.0


class TestInventoryValuator:
    """Test inventory valuation calculations."""

    @pytest.fixture
    def valuator(self):
        return InventoryValuator()

    def test_calculate_item_value_applies_condition_multiplier(self, valuator):
        """LP card at $10 NM should value at $8.70."""
        result = valuator.calculate_item_value(
            base_price=10.00,
            condition="LIGHTLY_PLAYED",
            quantity=1,
            is_foil=False
        )
        assert result == pytest.approx(8.70, rel=0.01)

    def test_calculate_item_value_multiplies_by_quantity(self, valuator):
        """4 copies of $10 NM card = $40."""
        result = valuator.calculate_item_value(
            base_price=10.00,
            condition="NEAR_MINT",
            quantity=4,
            is_foil=False
        )
        assert result == pytest.approx(40.00, rel=0.01)

    def test_calculate_profit_loss(self, valuator):
        """Bought at $5, now worth $8 = $3 profit."""
        result = valuator.calculate_profit_loss(
            current_value=8.00,
            acquisition_price=5.00,
            quantity=1
        )
        assert result["profit_loss"] == pytest.approx(3.00, rel=0.01)
        assert result["profit_loss_pct"] == pytest.approx(60.0, rel=0.01)

    def test_calculate_profit_loss_handles_loss(self, valuator):
        """Bought at $10, now worth $6 = -$4 loss."""
        result = valuator.calculate_profit_loss(
            current_value=6.00,
            acquisition_price=10.00,
            quantity=1
        )
        assert result["profit_loss"] == pytest.approx(-4.00, rel=0.01)
        assert result["profit_loss_pct"] == pytest.approx(-40.0, rel=0.01)

    def test_calculate_portfolio_index(self, valuator):
        """Index = (current_value / acquisition_cost) * 100."""
        result = valuator.calculate_portfolio_index(
            total_current_value=650.00,
            total_acquisition_cost=500.00
        )
        assert result == pytest.approx(130.0, rel=0.01)

    def test_calculate_portfolio_index_handles_zero_cost(self, valuator):
        """Zero acquisition cost should return 100 (neutral)."""
        result = valuator.calculate_portfolio_index(
            total_current_value=100.00,
            total_acquisition_cost=0.00
        )
        assert result == 100.0
```

**Step 2: Run test to verify it fails**

```bash
docker compose exec backend pytest tests/services/test_valuation.py -v
```

Expected: FAIL

**Step 3: Implement valuation service**

Create `backend/app/services/pricing/valuation.py`:

```python
"""Inventory valuation service."""
from typing import Optional


class ConditionMultiplier:
    """TCGPlayer-standard condition price multipliers."""

    MULTIPLIERS = {
        "MINT": 1.0,
        "NEAR_MINT": 1.0,
        "LIGHTLY_PLAYED": 0.87,
        "MODERATELY_PLAYED": 0.72,
        "HEAVILY_PLAYED": 0.55,
        "DAMAGED": 0.35,
    }

    @classmethod
    def get(cls, condition: str) -> float:
        """Get multiplier for condition, defaulting to 1.0."""
        return cls.MULTIPLIERS.get(condition.upper(), 1.0)


class InventoryValuator:
    """Calculate inventory item and portfolio valuations."""

    def calculate_item_value(
        self,
        base_price: float,
        condition: str,
        quantity: int,
        is_foil: bool = False,
    ) -> float:
        """
        Calculate the current value of an inventory item.

        Args:
            base_price: NM price (foil or non-foil as appropriate)
            condition: Card condition (NEAR_MINT, LIGHTLY_PLAYED, etc.)
            quantity: Number of copies
            is_foil: Whether this is a foil (base_price should already be foil price)

        Returns:
            Total current value for this item
        """
        multiplier = ConditionMultiplier.get(condition)
        per_card_value = base_price * multiplier
        return per_card_value * quantity

    def calculate_profit_loss(
        self,
        current_value: float,
        acquisition_price: float,
        quantity: int,
    ) -> dict:
        """
        Calculate profit/loss for an inventory item.

        Returns:
            Dict with profit_loss (absolute) and profit_loss_pct
        """
        if acquisition_price <= 0:
            return {"profit_loss": 0.0, "profit_loss_pct": 0.0}

        total_acquisition = acquisition_price * quantity
        profit_loss = current_value - total_acquisition
        profit_loss_pct = (profit_loss / total_acquisition) * 100

        return {
            "profit_loss": profit_loss,
            "profit_loss_pct": profit_loss_pct,
        }

    def calculate_portfolio_index(
        self,
        total_current_value: float,
        total_acquisition_cost: float,
    ) -> float:
        """
        Calculate portfolio value index.

        Index = (current_value / acquisition_cost) * 100

        Returns:
            Index value where 100 = break even, >100 = profit, <100 = loss
        """
        if total_acquisition_cost <= 0:
            return 100.0

        return (total_current_value / total_acquisition_cost) * 100
```

**Step 4: Update __init__.py**

Ensure `backend/app/services/pricing/__init__.py` exports ConditionMultiplier:

```python
"""Pricing services for MTG Market Intel."""
from .bulk_import import BulkPriceImporter
from .valuation import InventoryValuator, ConditionMultiplier

__all__ = ["BulkPriceImporter", "InventoryValuator", "ConditionMultiplier"]
```

**Step 5: Run tests**

```bash
docker compose exec backend pytest tests/services/test_valuation.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/services/pricing/valuation.py backend/tests/services/test_valuation.py backend/app/services/pricing/__init__.py
git commit -m "feat: add inventory valuation service with condition multipliers"
```

---

### Task 1.5: Create Pricing Service - Condition Pricing

**Files:**
- Create: `backend/app/services/pricing/condition_pricing.py`
- Create: `backend/tests/services/test_condition_pricing.py`

**Step 1: Write failing test**

Create `backend/tests/services/test_condition_pricing.py`:

```python
"""Tests for condition pricing service."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.pricing.condition_pricing import ConditionPricer


class TestConditionPricer:
    """Test condition-based pricing from TCGPlayer or multipliers."""

    @pytest.fixture
    def pricer(self):
        return ConditionPricer(tcgplayer_api_key="test-key")

    def test_should_use_tcgplayer_for_expensive_cards(self, pricer):
        """Cards over $5 should use TCGPlayer API."""
        assert pricer.should_use_tcgplayer(nm_price=10.00) is True
        assert pricer.should_use_tcgplayer(nm_price=5.01) is True

    def test_should_use_multiplier_for_cheap_cards(self, pricer):
        """Cards $5 or under should use multipliers."""
        assert pricer.should_use_tcgplayer(nm_price=5.00) is False
        assert pricer.should_use_tcgplayer(nm_price=1.00) is False

    def test_calculate_condition_prices_with_multipliers(self, pricer):
        """Should calculate all condition prices from NM base."""
        prices = pricer.calculate_condition_prices_from_multipliers(nm_price=10.00)

        assert prices["NEAR_MINT"] == 10.00
        assert prices["LIGHTLY_PLAYED"] == pytest.approx(8.70, rel=0.01)
        assert prices["MODERATELY_PLAYED"] == pytest.approx(7.20, rel=0.01)
        assert prices["HEAVILY_PLAYED"] == pytest.approx(5.50, rel=0.01)
        assert prices["DAMAGED"] == pytest.approx(3.50, rel=0.01)

    @pytest.mark.asyncio
    async def test_get_tcgplayer_prices_returns_condition_map(self, pricer):
        """Should fetch and parse TCGPlayer condition prices."""
        mock_response = {
            "results": [
                {"subTypeName": "Near Mint", "marketPrice": 12.50},
                {"subTypeName": "Lightly Played", "marketPrice": 10.80},
                {"subTypeName": "Moderately Played", "marketPrice": 9.00},
            ]
        }

        with patch.object(pricer, "_fetch_tcgplayer_prices", return_value=mock_response):
            prices = await pricer.get_tcgplayer_prices(tcgplayer_product_id=12345)

        assert prices["NEAR_MINT"] == 12.50
        assert prices["LIGHTLY_PLAYED"] == 10.80
        assert prices["MODERATELY_PLAYED"] == 9.00
```

**Step 2: Run test to verify it fails**

```bash
docker compose exec backend pytest tests/services/test_condition_pricing.py -v
```

Expected: FAIL

**Step 3: Implement condition pricing service**

Create `backend/app/services/pricing/condition_pricing.py`:

```python
"""Condition-based pricing service using TCGPlayer or multipliers."""
import logging
from typing import Optional

import httpx

from app.services.pricing.valuation import ConditionMultiplier

logger = logging.getLogger(__name__)

TCGPLAYER_API_URL = "https://api.tcgplayer.com/v1.39.0"
PRICE_THRESHOLD = 5.00  # Use TCGPlayer for cards above this price


class ConditionPricer:
    """Get condition-specific prices from TCGPlayer or calculate from multipliers."""

    # Map TCGPlayer condition names to our enum values
    CONDITION_MAP = {
        "Near Mint": "NEAR_MINT",
        "Lightly Played": "LIGHTLY_PLAYED",
        "Moderately Played": "MODERATELY_PLAYED",
        "Heavily Played": "HEAVILY_PLAYED",
        "Damaged": "DAMAGED",
    }

    def __init__(self, tcgplayer_api_key: Optional[str] = None):
        self.api_key = tcgplayer_api_key
        self._access_token: Optional[str] = None

    def should_use_tcgplayer(self, nm_price: float) -> bool:
        """Determine if TCGPlayer API should be used based on card value."""
        return nm_price > PRICE_THRESHOLD and self.api_key is not None

    def calculate_condition_prices_from_multipliers(
        self, nm_price: float
    ) -> dict[str, float]:
        """Calculate prices for all conditions using standard multipliers."""
        return {
            condition: nm_price * multiplier
            for condition, multiplier in ConditionMultiplier.MULTIPLIERS.items()
        }

    async def get_tcgplayer_prices(
        self, tcgplayer_product_id: int
    ) -> dict[str, float]:
        """Fetch condition prices from TCGPlayer API."""
        response = await self._fetch_tcgplayer_prices(tcgplayer_product_id)

        prices = {}
        for result in response.get("results", []):
            condition_name = result.get("subTypeName")
            market_price = result.get("marketPrice")

            if condition_name in self.CONDITION_MAP and market_price:
                our_condition = self.CONDITION_MAP[condition_name]
                prices[our_condition] = float(market_price)

        return prices

    async def _fetch_tcgplayer_prices(self, product_id: int) -> dict:
        """Make API call to TCGPlayer for pricing data."""
        if not self.api_key:
            raise ValueError("TCGPlayer API key not configured")

        # Ensure we have valid access token
        if not self._access_token:
            await self._authenticate()

        url = f"{TCGPLAYER_API_URL}/pricing/product/{product_id}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def _authenticate(self) -> None:
        """Authenticate with TCGPlayer OAuth2."""
        if not self.api_key:
            raise ValueError("TCGPlayer API key not configured")

        # TCGPlayer uses client_id:client_secret format
        parts = self.api_key.split(":")
        if len(parts) != 2:
            raise ValueError("TCGPlayer API key should be in format 'client_id:client_secret'")

        client_id, client_secret = parts

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tcgplayer.com/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data["access_token"]

    async def get_prices_for_card(
        self,
        nm_price: float,
        tcgplayer_product_id: Optional[int] = None,
        is_foil: bool = False,
    ) -> dict[str, float]:
        """
        Get condition prices for a card.

        Uses TCGPlayer for expensive cards, multipliers for cheap ones.
        """
        if self.should_use_tcgplayer(nm_price) and tcgplayer_product_id:
            try:
                return await self.get_tcgplayer_prices(tcgplayer_product_id)
            except Exception as e:
                logger.warning(f"TCGPlayer fetch failed, using multipliers: {e}")

        # Fallback to multipliers
        return self.calculate_condition_prices_from_multipliers(nm_price)
```

**Step 4: Update __init__.py**

```python
"""Pricing services for MTG Market Intel."""
from .bulk_import import BulkPriceImporter
from .valuation import InventoryValuator, ConditionMultiplier
from .condition_pricing import ConditionPricer

__all__ = [
    "BulkPriceImporter",
    "InventoryValuator",
    "ConditionMultiplier",
    "ConditionPricer",
]
```

**Step 5: Run tests**

```bash
docker compose exec backend pytest tests/services/test_condition_pricing.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/services/pricing/condition_pricing.py backend/tests/services/test_condition_pricing.py backend/app/services/pricing/__init__.py
git commit -m "feat: add condition pricing service with TCGPlayer integration"
```

---

### Task 1.6: Create Celery Pricing Tasks

**Files:**
- Create: `backend/app/tasks/pricing.py`
- Modify: `backend/app/tasks/celery_app.py`

**Step 1: Create pricing tasks**

Create `backend/app/tasks/pricing.py`:

```python
"""Celery tasks for price data collection and refresh."""
import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import select, func

from app.db.session import async_session_maker
from app.models.card import Card
from app.models.inventory import InventoryItem
from app.models.price_snapshot import PriceSnapshot
from app.services.pricing.bulk_import import BulkPriceImporter
from app.services.pricing.valuation import InventoryValuator
from app.services.pricing.condition_pricing import ConditionPricer
from app.core.config import settings

logger = logging.getLogger(__name__)


@shared_task(name="app.tasks.pricing.bulk_refresh")
def bulk_refresh():
    """
    Download Scryfall bulk data and update all card prices.

    Runs every 12 hours or on startup if data is stale.
    """
    import asyncio
    asyncio.run(_bulk_refresh_async())


async def _bulk_refresh_async():
    """Async implementation of bulk refresh."""
    logger.info("Starting bulk price refresh from Scryfall")

    importer = BulkPriceImporter()

    async with async_session_maker() as db:
        try:
            stats = await importer.import_prices(
                db,
                progress_callback=lambda s: logger.info(f"Progress: {s}")
            )
            logger.info(f"Bulk refresh complete: {stats}")

            # Trigger inventory valuation update
            await _update_all_inventory_valuations(db)

        except Exception as e:
            logger.error(f"Bulk refresh failed: {e}")
            raise


@shared_task(name="app.tasks.pricing.inventory_refresh")
def inventory_refresh():
    """
    Refresh prices for cards in user inventories using Scryfall API.

    Runs every 4 hours. Only updates cards that are in at least one inventory.
    """
    import asyncio
    asyncio.run(_inventory_refresh_async())


async def _inventory_refresh_async():
    """Async implementation of inventory refresh."""
    logger.info("Starting inventory price refresh")

    async with async_session_maker() as db:
        # Get unique card IDs from all inventories
        result = await db.execute(
            select(InventoryItem.card_id).distinct()
        )
        card_ids = [row[0] for row in result.fetchall()]

        if not card_ids:
            logger.info("No inventory cards to refresh")
            return

        logger.info(f"Refreshing prices for {len(card_ids)} inventory cards")

        # Get scryfall_ids for these cards
        result = await db.execute(
            select(Card.id, Card.scryfall_id).where(Card.id.in_(card_ids))
        )
        cards = result.fetchall()

        # Fetch fresh prices from Scryfall API
        import httpx

        async with httpx.AsyncClient() as client:
            for card_id, scryfall_id in cards:
                try:
                    await _refresh_single_card(db, client, card_id, scryfall_id)
                    # Respect rate limit: 100ms between requests
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.warning(f"Failed to refresh card {scryfall_id}: {e}")

        await db.commit()

        # Update inventory valuations
        await _update_all_inventory_valuations(db)

    logger.info("Inventory price refresh complete")


async def _refresh_single_card(db, client, card_id: int, scryfall_id: str):
    """Fetch fresh price for a single card from Scryfall API."""
    url = f"https://api.scryfall.com/cards/{scryfall_id}"
    headers = {"User-Agent": "DualcasterDeals/1.0"}

    response = await client.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    prices = data.get("prices", {})
    now = datetime.now(timezone.utc)

    # Create snapshots for available prices
    from app.services.pricing.bulk_import import BulkPriceImporter
    importer = BulkPriceImporter()
    parsed = importer.parse_scryfall_prices(data)

    # Insert price snapshots with source='api'
    # (Implementation similar to bulk_import but with source='api')


@shared_task(name="app.tasks.pricing.condition_refresh")
def condition_refresh():
    """
    Refresh condition-specific prices for high-value inventory cards.

    Runs every 6 hours. Uses TCGPlayer for cards >$5, multipliers for others.
    """
    import asyncio
    asyncio.run(_condition_refresh_async())


async def _condition_refresh_async():
    """Async implementation of condition refresh."""
    logger.info("Starting condition price refresh")

    pricer = ConditionPricer(tcgplayer_api_key=settings.TCGPLAYER_API_KEY)
    valuator = InventoryValuator()

    async with async_session_maker() as db:
        # Get inventory items with their current NM prices
        # (Implementation fetches TCGPlayer prices for expensive cards,
        # applies multipliers for cheap cards, and stores condition snapshots)
        pass

    logger.info("Condition price refresh complete")


async def _update_all_inventory_valuations(db):
    """Update current_value for all inventory items based on latest prices."""
    logger.info("Updating inventory valuations")

    valuator = InventoryValuator()

    # Get all inventory items with their latest prices
    result = await db.execute(
        select(InventoryItem)
    )
    items = result.scalars().all()

    for item in items:
        # Get latest price for this card/foil combination
        price_result = await db.execute(
            select(PriceSnapshot.price)
            .where(PriceSnapshot.card_id == item.card_id)
            .where(PriceSnapshot.is_foil == item.is_foil)
            .where(PriceSnapshot.currency == "USD")
            .order_by(PriceSnapshot.time.desc())
            .limit(1)
        )
        latest_price = price_result.scalar_one_or_none()

        if latest_price:
            # Calculate value with condition multiplier
            new_value = valuator.calculate_item_value(
                base_price=float(latest_price),
                condition=item.condition.value if hasattr(item.condition, 'value') else str(item.condition),
                quantity=1,  # per-card value
                is_foil=item.is_foil
            )

            old_value = item.current_value
            item.current_value = new_value
            item.last_valued_at = datetime.now(timezone.utc)

            # Calculate value change percentage
            if old_value and old_value > 0:
                item.value_change_pct = ((new_value - old_value) / old_value) * 100

    await db.commit()
    logger.info(f"Updated valuations for {len(items)} inventory items")
```

**Step 2: Update Celery beat schedule**

In `backend/app/tasks/celery_app.py`, replace the schedule with:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    # Pricing tasks
    "pricing-bulk-refresh": {
        "task": "app.tasks.pricing.bulk_refresh",
        "schedule": crontab(hour="*/12"),  # Every 12 hours
    },
    "pricing-inventory-refresh": {
        "task": "app.tasks.pricing.inventory_refresh",
        "schedule": crontab(hour="*/4"),  # Every 4 hours
    },
    "pricing-condition-refresh": {
        "task": "app.tasks.pricing.condition_refresh",
        "schedule": crontab(hour="*/6"),  # Every 6 hours
    },

    # Search tasks
    "search-refresh-embeddings": {
        "task": "app.tasks.search.refresh_embeddings",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
    },

    # Tournament tasks (Phase 2)
    # "tournaments-ingest": {
    #     "task": "app.tasks.tournaments.ingest_recent",
    #     "schedule": crontab(hour="*/6"),
    # },
}
```

**Step 3: Commit**

```bash
git add backend/app/tasks/pricing.py backend/app/tasks/celery_app.py
git commit -m "feat: add Celery pricing tasks with simplified schedule"
```

---

### Task 1.7: Fix Inventory Top Movers Endpoint

**Files:**
- Modify: `backend/app/api/routes/inventory.py`
- Create: `backend/tests/api/test_inventory_top_movers.py`

**Step 1: Write failing test**

Create `backend/tests/api/test_inventory_top_movers.py`:

```python
"""Tests for inventory top movers endpoint."""
import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient

from app.models.card import Card
from app.models.inventory import InventoryItem
from app.models.price_snapshot import PriceSnapshot
from app.models.marketplace import Marketplace


@pytest.mark.asyncio
class TestTopMovers:
    """Test GET /inventory/top-movers endpoint."""

    async def test_returns_gainers_and_losers(
        self, client: AsyncClient, db_session, auth_headers
    ):
        """Should return cards with biggest price changes."""
        # Create test data
        marketplace = Marketplace(slug="tcgplayer", name="TCGPlayer")
        db_session.add(marketplace)

        card1 = Card(
            scryfall_id="card-1",
            name="Gainer Card",
            set_code="TST",
            collector_number="1"
        )
        card2 = Card(
            scryfall_id="card-2",
            name="Loser Card",
            set_code="TST",
            collector_number="2"
        )
        db_session.add_all([card1, card2])
        await db_session.flush()

        # Add to inventory
        inv1 = InventoryItem(
            user_id=1, card_id=card1.id, quantity=1,
            condition="NEAR_MINT", is_foil=False
        )
        inv2 = InventoryItem(
            user_id=1, card_id=card2.id, quantity=1,
            condition="NEAR_MINT", is_foil=False
        )
        db_session.add_all([inv1, inv2])

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        # Card 1: $10 -> $15 (50% gain)
        db_session.add(PriceSnapshot(
            card_id=card1.id, marketplace_id=marketplace.id,
            time=yesterday, price=10.00, currency="USD",
            condition="NEAR_MINT", is_foil=False, source="bulk"
        ))
        db_session.add(PriceSnapshot(
            card_id=card1.id, marketplace_id=marketplace.id,
            time=now, price=15.00, currency="USD",
            condition="NEAR_MINT", is_foil=False, source="bulk"
        ))

        # Card 2: $20 -> $12 (40% loss)
        db_session.add(PriceSnapshot(
            card_id=card2.id, marketplace_id=marketplace.id,
            time=yesterday, price=20.00, currency="USD",
            condition="NEAR_MINT", is_foil=False, source="bulk"
        ))
        db_session.add(PriceSnapshot(
            card_id=card2.id, marketplace_id=marketplace.id,
            time=now, price=12.00, currency="USD",
            condition="NEAR_MINT", is_foil=False, source="bulk"
        ))

        await db_session.commit()

        response = await client.get(
            "/api/v1/inventory/top-movers?window=24h",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["gainers"]) >= 1
        assert len(data["losers"]) >= 1
        assert data["gainers"][0]["card_name"] == "Gainer Card"
        assert data["losers"][0]["card_name"] == "Loser Card"
        assert data["gainers"][0]["change_pct"] == pytest.approx(50.0, rel=0.1)
        assert data["losers"][0]["change_pct"] == pytest.approx(-40.0, rel=0.1)
```

**Step 2: Implement fixed top-movers endpoint**

Replace the existing top-movers logic in `backend/app/api/routes/inventory.py` with direct price comparison:

```python
@router.get("/top-movers")
async def get_top_movers(
    window: str = Query("24h", regex="^(24h|7d)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get top gaining and losing cards in user's inventory.

    Uses direct price_snapshot comparison instead of stale metrics.
    """
    # Determine time window
    now = datetime.now(timezone.utc)
    if window == "24h":
        past_time = now - timedelta(hours=24)
    else:
        past_time = now - timedelta(days=7)

    # Get user's inventory card IDs
    inv_result = await db.execute(
        select(InventoryItem.card_id, InventoryItem.is_foil)
        .where(InventoryItem.user_id == current_user.id)
        .distinct()
    )
    inventory_cards = inv_result.fetchall()

    if not inventory_cards:
        return {"gainers": [], "losers": [], "data_freshness_hours": 0}

    card_ids = [row[0] for row in inventory_cards]

    # Subquery for latest price per card
    latest_subq = (
        select(
            PriceSnapshot.card_id,
            func.max(PriceSnapshot.time).label("latest_time")
        )
        .where(PriceSnapshot.card_id.in_(card_ids))
        .where(PriceSnapshot.currency == "USD")
        .group_by(PriceSnapshot.card_id)
        .subquery()
    )

    # Get current prices
    current_result = await db.execute(
        select(PriceSnapshot.card_id, PriceSnapshot.price, PriceSnapshot.time)
        .join(latest_subq, and_(
            PriceSnapshot.card_id == latest_subq.c.card_id,
            PriceSnapshot.time == latest_subq.c.latest_time
        ))
    )
    current_prices = {row.card_id: (float(row.price), row.time) for row in current_result}

    # Subquery for past price per card
    past_subq = (
        select(
            PriceSnapshot.card_id,
            func.max(PriceSnapshot.time).label("past_time")
        )
        .where(PriceSnapshot.card_id.in_(card_ids))
        .where(PriceSnapshot.currency == "USD")
        .where(PriceSnapshot.time <= past_time)
        .group_by(PriceSnapshot.card_id)
        .subquery()
    )

    # Get past prices
    past_result = await db.execute(
        select(PriceSnapshot.card_id, PriceSnapshot.price)
        .join(past_subq, and_(
            PriceSnapshot.card_id == past_subq.c.card_id,
            PriceSnapshot.time == past_subq.c.past_time
        ))
    )
    past_prices = {row.card_id: float(row.price) for row in past_result}

    # Calculate changes
    changes = []
    for card_id in card_ids:
        if card_id in current_prices and card_id in past_prices:
            current_price, current_time = current_prices[card_id]
            past_price = past_prices[card_id]

            if past_price > 0:
                change_pct = ((current_price - past_price) / past_price) * 100
                changes.append({
                    "card_id": card_id,
                    "old_price": past_price,
                    "new_price": current_price,
                    "change_pct": change_pct,
                })

    # Get card names
    card_result = await db.execute(
        select(Card.id, Card.name, Card.set_code, Card.image_url)
        .where(Card.id.in_(card_ids))
    )
    card_info = {row.id: row for row in card_result}

    # Enrich with card info
    for change in changes:
        card = card_info.get(change["card_id"])
        if card:
            change["card_name"] = card.name
            change["set_code"] = card.set_code
            change["image_url"] = card.image_url

    # Sort and split
    gainers = sorted(
        [c for c in changes if c["change_pct"] > 0],
        key=lambda x: x["change_pct"],
        reverse=True
    )[:5]

    losers = sorted(
        [c for c in changes if c["change_pct"] < 0],
        key=lambda x: x["change_pct"]
    )[:5]

    # Calculate data freshness
    if current_prices:
        latest_time = max(t for _, t in current_prices.values())
        freshness_hours = (now - latest_time).total_seconds() / 3600
    else:
        freshness_hours = 999

    return {
        "gainers": gainers,
        "losers": losers,
        "data_freshness_hours": round(freshness_hours, 1)
    }
```

**Step 3: Run tests**

```bash
docker compose exec backend pytest tests/api/test_inventory_top_movers.py -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/api/routes/inventory.py backend/tests/api/test_inventory_top_movers.py
git commit -m "fix: inventory top-movers uses direct price comparison"
```

---

### Task 1.8: Fix Inventory Summary and Index

**Files:**
- Modify: `backend/app/api/routes/inventory.py`

**Step 1: Update summary endpoint to use acquisition-based index**

In `backend/app/api/routes/inventory.py`, update the summary calculation:

```python
@router.get("/summary")
async def get_inventory_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get portfolio summary with acquisition-cost-based index.

    Index = (current_value / acquisition_cost) * 100
    - 100 = break even
    - >100 = profit
    - <100 = loss
    """
    from app.services.pricing.valuation import InventoryValuator

    valuator = InventoryValuator()

    # Get all inventory items
    result = await db.execute(
        select(InventoryItem)
        .where(InventoryItem.user_id == current_user.id)
    )
    items = result.scalars().all()

    if not items:
        return {
            "total_items": 0,
            "total_quantity": 0,
            "total_value": 0.0,
            "total_acquisition_cost": 0.0,
            "profit_loss": 0.0,
            "profit_loss_pct": 0.0,
            "index_value": 100.0,
            "last_valued_at": None,
        }

    total_quantity = sum(item.quantity for item in items)
    total_value = sum(
        (item.current_value or 0) * item.quantity
        for item in items
    )
    total_acquisition = sum(
        (item.acquisition_price or 0) * item.quantity
        for item in items
    )

    profit_loss = total_value - total_acquisition
    profit_loss_pct = (
        (profit_loss / total_acquisition * 100)
        if total_acquisition > 0 else 0.0
    )

    index_value = valuator.calculate_portfolio_index(
        total_current_value=total_value,
        total_acquisition_cost=total_acquisition
    )

    # Find most recent valuation time
    valued_times = [
        item.last_valued_at for item in items
        if item.last_valued_at
    ]
    last_valued = max(valued_times) if valued_times else None

    return {
        "total_items": len(items),
        "total_quantity": total_quantity,
        "total_value": round(total_value, 2),
        "total_acquisition_cost": round(total_acquisition, 2),
        "profit_loss": round(profit_loss, 2),
        "profit_loss_pct": round(profit_loss_pct, 1),
        "index_value": round(index_value, 1),
        "last_valued_at": last_valued.isoformat() if last_valued else None,
    }
```

**Step 2: Commit**

```bash
git add backend/app/api/routes/inventory.py
git commit -m "fix: inventory summary uses acquisition-cost-based index"
```

---

## Phase 2: Tournament Integration

### Task 2.1: Create Tournament Models

**Files:**
- Create: `backend/app/models/tournament.py`
- Create: `backend/alembic/versions/20251227_003_create_tournament_tables.py`

**Step 1: Create tournament models**

Create `backend/app/models/tournament.py`:

```python
"""Tournament data models for TopDeck.gg integration."""
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card


class Tournament(Base):
    """Tournament event from TopDeck.gg."""

    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    topdeck_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    player_count: Mapped[int] = mapped_column(Integer, nullable=False)
    swiss_rounds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    top_cut_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Location
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    venue: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Attribution
    topdeck_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Relationships
    standings: Mapped[list["TournamentStanding"]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan"
    )


class TournamentStanding(Base):
    """Player standing in a tournament."""

    __tablename__ = "tournament_standings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    player_name: Mapped[str] = mapped_column(String(100), nullable=False)
    player_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    tournament: Mapped["Tournament"] = relationship(back_populates="standings")
    decklist: Mapped[Optional["Decklist"]] = relationship(
        back_populates="standing", uselist=False
    )


class Decklist(Base):
    """Decklist submitted by a player."""

    __tablename__ = "decklists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    standing_id: Mapped[int] = mapped_column(
        ForeignKey("tournament_standings.id", ondelete="CASCADE"),
        nullable=False, unique=True
    )
    archetype_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    standing: Mapped["TournamentStanding"] = relationship(back_populates="decklist")
    cards: Mapped[list["DecklistCard"]] = relationship(
        back_populates="decklist", cascade="all, delete-orphan"
    )


class DecklistCard(Base):
    """Card entry in a decklist."""

    __tablename__ = "decklist_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    decklist_id: Mapped[int] = mapped_column(
        ForeignKey("decklists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(20), default="mainboard")  # mainboard, sideboard, commander

    # Relationships
    decklist: Mapped["Decklist"] = relationship(back_populates="cards")
    card: Mapped["Card"] = relationship()


class CardMetaStats(Base):
    """Aggregated tournament statistics for a card."""

    __tablename__ = "card_meta_stats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    format: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # 7d, 30d, 90d

    deck_inclusion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_copies: Mapped[float] = mapped_column(Float, default=0.0)
    top8_rate: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

**Step 2: Create migration**

Create `backend/alembic/versions/20251227_003_create_tournament_tables.py`:

```python
"""Create tournament tables

Revision ID: 20251227_003
Revises: 20251227_002
Create Date: 2025-12-27
"""
from alembic import op
import sqlalchemy as sa

revision = '20251227_003'
down_revision = '20251227_002'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'tournaments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('topdeck_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('format', sa.String(50), nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('player_count', sa.Integer(), nullable=False),
        sa.Column('swiss_rounds', sa.Integer(), nullable=True),
        sa.Column('top_cut_size', sa.Integer(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('venue', sa.String(255), nullable=True),
        sa.Column('topdeck_url', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tournaments_topdeck_id', 'tournaments', ['topdeck_id'], unique=True)
    op.create_index('ix_tournaments_format', 'tournaments', ['format'])
    op.create_index('ix_tournaments_date', 'tournaments', ['date'])

    op.create_table(
        'tournament_standings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('player_name', sa.String(100), nullable=False),
        sa.Column('player_id', sa.String(50), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('wins', sa.Integer(), default=0),
        sa.Column('losses', sa.Integer(), default=0),
        sa.Column('draws', sa.Integer(), default=0),
        sa.Column('win_rate', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tournament_standings_tournament_id', 'tournament_standings', ['tournament_id'])

    op.create_table(
        'decklists',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('standing_id', sa.Integer(), nullable=False),
        sa.Column('archetype_name', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['standing_id'], ['tournament_standings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('standing_id')
    )

    op.create_table(
        'decklist_cards',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('decklist_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('section', sa.String(20), default='mainboard'),
        sa.ForeignKeyConstraint(['decklist_id'], ['decklists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decklist_cards_decklist_id', 'decklist_cards', ['decklist_id'])
    op.create_index('ix_decklist_cards_card_id', 'decklist_cards', ['card_id'])

    op.create_table(
        'card_meta_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('format', sa.String(50), nullable=False),
        sa.Column('period', sa.String(10), nullable=False),
        sa.Column('deck_inclusion_rate', sa.Float(), default=0.0),
        sa.Column('avg_copies', sa.Float(), default=0.0),
        sa.Column('top8_rate', sa.Float(), default=0.0),
        sa.Column('win_rate_delta', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_card_meta_stats_card_id', 'card_meta_stats', ['card_id'])
    op.create_index('ix_card_meta_stats_format', 'card_meta_stats', ['format'])

def downgrade() -> None:
    op.drop_table('card_meta_stats')
    op.drop_table('decklist_cards')
    op.drop_table('decklists')
    op.drop_table('tournament_standings')
    op.drop_table('tournaments')
```

**Step 3: Run migration and commit**

```bash
docker compose exec backend alembic upgrade head
git add backend/app/models/tournament.py backend/alembic/versions/20251227_003_create_tournament_tables.py
git commit -m "feat: add tournament data models"
```

---

### Task 2.2-2.5: TopDeck Client, Ingestion, API, Frontend

(Detailed steps follow same pattern as Task 1.3-1.7)

---

## Phase 3: Semantic Search

### Task 3.1-3.4: Search Services, Endpoints, Frontend

(Detailed steps follow same pattern)

---

## Phase 4: Cleanup

### Task 4.1: Remove Deprecated Code

**Files to delete:**
- `backend/app/services/ingestion/adapters/manapool.py`
- `backend/app/services/ingestion/adapters/mtgjson.py`
- `backend/app/tasks/data_seeding.py`

**Files to simplify:**
- Remove MetricsCardsDaily usage from inventory routes
- Remove overlapping task schedules from celery_app.py

---

## Verification Checklist

After each phase, verify:

- [ ] All tests pass: `make test`
- [ ] Linting passes: `make lint`
- [ ] Docker builds: `make up-build`
- [ ] Manual smoke test of affected endpoints

---

## Notes for Implementer

1. **Run migrations carefully** - Check current revision before applying
2. **Test with real data** - The bulk import downloads ~500MB, takes 5-10 minutes
3. **Rate limits matter** - Scryfall: 10 req/s, TCGPlayer: 100/min, TopDeck: 200/min
4. **Commit frequently** - After each passing test
5. **Check CLAUDE.md** - For project-specific commands and conventions
