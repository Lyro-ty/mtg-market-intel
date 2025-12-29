"""Import service for collection imports from external platforms."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.import_job import ImportJob, ImportPlatform, ImportStatus
from app.models.inventory import InventoryItem, InventoryCondition
from app.services.imports.parser import ImportParser, ParsedCard


class ImportService:
    """Service for handling collection imports."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_import_job(
        self,
        user_id: int,
        filename: str,
        content: str,
        platform: ImportPlatform,
    ) -> ImportJob:
        """Create a new import job and store the raw content."""
        job = ImportJob(
            user_id=user_id,
            filename=filename,
            file_size=len(content.encode("utf-8")),
            platform=platform,
            status=ImportStatus.PENDING,
            raw_content=content,
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def generate_preview(self, job_id: int, user_id: int) -> ImportJob:
        """Parse the import file and generate a preview."""
        job = await self._get_job(job_id, user_id)
        if not job:
            raise ValueError("Import job not found")

        if job.status != ImportStatus.PENDING:
            raise ValueError(f"Cannot preview job in status {job.status}")

        job.status = ImportStatus.PREVIEWING
        await self.db.commit()

        try:
            # Parse the CSV content
            parsed_cards = ImportParser.parse(job.raw_content, job.platform)
            job.total_rows = len(parsed_cards)

            # Match cards to database
            matched, unmatched = await self._match_cards(parsed_cards)

            job.matched_cards = len(matched)
            job.unmatched_cards = len(unmatched)

            # Store preview data (first 100 cards for display)
            preview_items = []
            for card in (matched + unmatched)[:100]:
                preview_items.append({
                    "row_number": card.row_number,
                    "card_name": card.card_name,
                    "set_code": card.set_code,
                    "set_name": card.set_name,
                    "collector_number": card.collector_number,
                    "quantity": card.quantity,
                    "condition": card.condition,
                    "is_foil": card.is_foil,
                    "language": card.language,
                    "acquisition_price": card.acquisition_price,
                    "matched_card_id": card.matched_card_id,
                    "match_confidence": card.match_confidence,
                    "match_error": card.match_error,
                })

            job.preview_data = {
                "items": preview_items,
                "total": len(parsed_cards),
                "matched": len(matched),
                "unmatched": len(unmatched),
            }
            job.status = ImportStatus.PREVIEW_READY

        except Exception as e:
            job.status = ImportStatus.FAILED
            job.error_message = str(e)

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def confirm_import(
        self,
        job_id: int,
        user_id: int,
        skip_unmatched: bool = True,
    ) -> ImportJob:
        """Execute the import, creating inventory items."""
        job = await self._get_job(job_id, user_id)
        if not job:
            raise ValueError("Import job not found")

        if job.status != ImportStatus.PREVIEW_READY:
            raise ValueError(f"Cannot import job in status {job.status}")

        job.status = ImportStatus.IMPORTING
        job.started_at = datetime.now(timezone.utc)
        await self.db.commit()

        try:
            # Re-parse to get all cards (preview may have been truncated)
            parsed_cards = ImportParser.parse(job.raw_content, job.platform)
            matched, unmatched = await self._match_cards(parsed_cards)

            imported = 0
            skipped = 0
            errors = []

            # Import matched cards
            for card in matched:
                try:
                    await self._create_inventory_item(user_id, card)
                    imported += 1
                except Exception as e:
                    errors.append({
                        "row": card.row_number,
                        "card_name": card.card_name,
                        "error": str(e),
                    })

            # Handle unmatched
            if skip_unmatched:
                skipped = len(unmatched)
            else:
                for card in unmatched:
                    errors.append({
                        "row": card.row_number,
                        "card_name": card.card_name,
                        "error": card.match_error or "Card not found in database",
                    })

            job.imported_count = imported
            job.skipped_count = skipped
            job.error_count = len(errors)
            job.errors_detail = errors if errors else None
            job.status = ImportStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)

            # Clear raw content to save space
            job.raw_content = None

        except Exception as e:
            job.status = ImportStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def cancel_import(self, job_id: int, user_id: int) -> ImportJob:
        """Cancel a pending or preview-ready import."""
        job = await self._get_job(job_id, user_id)
        if not job:
            raise ValueError("Import job not found")

        if job.status not in (ImportStatus.PENDING, ImportStatus.PREVIEW_READY):
            raise ValueError(f"Cannot cancel job in status {job.status}")

        job.status = ImportStatus.CANCELLED
        job.raw_content = None  # Clear content
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_user_imports(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ImportJob], int]:
        """Get user's import jobs with pagination."""
        # Get total count
        count_query = select(func.count()).select_from(ImportJob).where(
            ImportJob.user_id == user_id
        )
        total = await self.db.scalar(count_query)

        # Get items
        query = (
            select(ImportJob)
            .where(ImportJob.user_id == user_id)
            .order_by(ImportJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        jobs = list(result.scalars().all())

        return jobs, total or 0

    async def _get_job(self, job_id: int, user_id: int) -> Optional[ImportJob]:
        """Get an import job by ID, ensuring it belongs to the user."""
        query = select(ImportJob).where(
            ImportJob.id == job_id,
            ImportJob.user_id == user_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _match_cards(
        self, parsed_cards: list[ParsedCard]
    ) -> tuple[list[ParsedCard], list[ParsedCard]]:
        """Match parsed cards to database cards."""
        matched = []
        unmatched = []

        for card in parsed_cards:
            db_card = await self._find_matching_card(card)
            if db_card:
                card.matched_card_id = db_card.id
                card.match_confidence = 1.0 if card.set_code and card.collector_number else 0.8
                matched.append(card)
            else:
                card.match_error = "No matching card found in database"
                unmatched.append(card)

        return matched, unmatched

    async def _find_matching_card(self, parsed: ParsedCard) -> Optional[Card]:
        """Find a matching card in the database."""
        # Try exact match first (set_code + collector_number)
        if parsed.set_code and parsed.collector_number:
            query = select(Card).where(
                func.upper(Card.set_code) == parsed.set_code.upper(),
                Card.collector_number == parsed.collector_number,
            )
            result = await self.db.execute(query)
            card = result.scalar_one_or_none()
            if card:
                return card

        # Try set_code + name match
        if parsed.set_code:
            query = select(Card).where(
                func.upper(Card.set_code) == parsed.set_code.upper(),
                func.lower(Card.name) == parsed.card_name.lower(),
            )
            result = await self.db.execute(query)
            card = result.scalar_one_or_none()
            if card:
                return card

        # Try name-only match (return most recent printing)
        query = (
            select(Card)
            .where(func.lower(Card.name) == parsed.card_name.lower())
            .order_by(Card.released_at.desc().nullslast())
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _create_inventory_item(
        self, user_id: int, parsed: ParsedCard
    ) -> InventoryItem:
        """Create an inventory item from a parsed card."""
        # Map condition string to enum
        try:
            condition = InventoryCondition(parsed.condition)
        except ValueError:
            condition = InventoryCondition.NEAR_MINT

        item = InventoryItem(
            user_id=user_id,
            card_id=parsed.matched_card_id,
            quantity=parsed.quantity,
            condition=condition,
            is_foil=parsed.is_foil,
            language=parsed.language,
            acquisition_price=parsed.acquisition_price,
            notes=parsed.notes,
        )
        self.db.add(item)
        await self.db.flush()  # Get ID without committing
        return item
