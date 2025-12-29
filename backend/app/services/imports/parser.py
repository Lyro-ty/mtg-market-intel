"""CSV parsers for different collection platforms."""
import csv
import io
from dataclasses import dataclass, field
from typing import Optional

from app.models.import_job import ImportPlatform
from app.models.inventory import InventoryCondition


@dataclass
class ParsedCard:
    """Represents a parsed card from an import file."""
    row_number: int
    card_name: str
    set_code: Optional[str] = None
    set_name: Optional[str] = None
    collector_number: Optional[str] = None
    quantity: int = 1
    condition: str = InventoryCondition.NEAR_MINT.value
    is_foil: bool = False
    language: str = "English"
    acquisition_price: Optional[float] = None
    notes: Optional[str] = None

    # Matching results (filled during card matching)
    matched_card_id: Optional[int] = None
    match_confidence: float = 0.0
    match_error: Optional[str] = None
    raw_line: str = ""


class ImportParser:
    """Parser for collection import CSV files."""

    # Condition mappings from various formats to our enum
    CONDITION_MAP = {
        # Near Mint variations
        "nm": InventoryCondition.NEAR_MINT.value,
        "near mint": InventoryCondition.NEAR_MINT.value,
        "nearmint": InventoryCondition.NEAR_MINT.value,
        "near_mint": InventoryCondition.NEAR_MINT.value,
        "m": InventoryCondition.MINT.value,
        "mint": InventoryCondition.MINT.value,
        # Lightly Played
        "lp": InventoryCondition.LIGHTLY_PLAYED.value,
        "lightly played": InventoryCondition.LIGHTLY_PLAYED.value,
        "lightlyplayed": InventoryCondition.LIGHTLY_PLAYED.value,
        "lightly_played": InventoryCondition.LIGHTLY_PLAYED.value,
        "sp": InventoryCondition.LIGHTLY_PLAYED.value,  # "Slightly Played"
        "excellent": InventoryCondition.LIGHTLY_PLAYED.value,
        "ex": InventoryCondition.LIGHTLY_PLAYED.value,
        # Moderately Played
        "mp": InventoryCondition.MODERATELY_PLAYED.value,
        "moderately played": InventoryCondition.MODERATELY_PLAYED.value,
        "moderatelyplayed": InventoryCondition.MODERATELY_PLAYED.value,
        "moderately_played": InventoryCondition.MODERATELY_PLAYED.value,
        "played": InventoryCondition.MODERATELY_PLAYED.value,
        "good": InventoryCondition.MODERATELY_PLAYED.value,
        "gd": InventoryCondition.MODERATELY_PLAYED.value,
        # Heavily Played
        "hp": InventoryCondition.HEAVILY_PLAYED.value,
        "heavily played": InventoryCondition.HEAVILY_PLAYED.value,
        "heavilyplayed": InventoryCondition.HEAVILY_PLAYED.value,
        "heavily_played": InventoryCondition.HEAVILY_PLAYED.value,
        "poor": InventoryCondition.HEAVILY_PLAYED.value,
        # Damaged
        "dmg": InventoryCondition.DAMAGED.value,
        "damaged": InventoryCondition.DAMAGED.value,
        "d": InventoryCondition.DAMAGED.value,
    }

    @classmethod
    def parse(cls, content: str, platform: ImportPlatform) -> list[ParsedCard]:
        """Parse CSV content based on platform format."""
        if platform == ImportPlatform.MOXFIELD:
            return cls._parse_moxfield(content)
        elif platform == ImportPlatform.ARCHIDEKT:
            return cls._parse_archidekt(content)
        elif platform == ImportPlatform.DECKBOX:
            return cls._parse_deckbox(content)
        elif platform == ImportPlatform.TCGPLAYER:
            return cls._parse_tcgplayer(content)
        else:
            return cls._parse_generic(content)

    @classmethod
    def _normalize_condition(cls, condition: Optional[str]) -> str:
        """Convert condition string to our enum value."""
        if not condition:
            return InventoryCondition.NEAR_MINT.value
        normalized = condition.lower().strip()
        return cls.CONDITION_MAP.get(normalized, InventoryCondition.NEAR_MINT.value)

    @classmethod
    def _parse_foil(cls, foil_value: Optional[str]) -> bool:
        """Parse foil indicator from various formats."""
        if not foil_value:
            return False
        val = foil_value.lower().strip()
        return val in ("true", "yes", "1", "foil", "y", "x")

    @classmethod
    def _parse_quantity(cls, qty_value: Optional[str]) -> int:
        """Parse quantity, defaulting to 1."""
        if not qty_value:
            return 1
        try:
            return max(1, int(qty_value.strip()))
        except ValueError:
            return 1

    @classmethod
    def _parse_price(cls, price_value: Optional[str]) -> Optional[float]:
        """Parse price value, removing currency symbols."""
        if not price_value:
            return None
        try:
            # Remove common currency symbols and whitespace
            cleaned = price_value.strip().replace("$", "").replace("€", "").replace("£", "").strip()
            if not cleaned:
                return None
            return float(cleaned)
        except ValueError:
            return None

    @classmethod
    def _parse_moxfield(cls, content: str) -> list[ParsedCard]:
        """
        Parse Moxfield CSV export format.

        Expected columns: Count, Name, Edition, Collector Number, Foil, Condition, Language
        """
        cards = []
        reader = csv.DictReader(io.StringIO(content))

        for row_num, row in enumerate(reader, start=2):  # Start at 2 to account for header
            raw_line = ",".join(str(v) for v in row.values())

            card_name = row.get("Name", "").strip()
            if not card_name:
                continue

            cards.append(ParsedCard(
                row_number=row_num,
                card_name=card_name,
                set_code=row.get("Edition", "").strip().upper() or None,
                collector_number=row.get("Collector Number", "").strip() or None,
                quantity=cls._parse_quantity(row.get("Count")),
                condition=cls._normalize_condition(row.get("Condition")),
                is_foil=cls._parse_foil(row.get("Foil")),
                language=row.get("Language", "English").strip() or "English",
                raw_line=raw_line,
            ))

        return cards

    @classmethod
    def _parse_archidekt(cls, content: str) -> list[ParsedCard]:
        """
        Parse Archidekt CSV export format.

        Expected columns: Quantity, Name, Set, Collector Number, Foil, Condition
        """
        cards = []
        reader = csv.DictReader(io.StringIO(content))

        for row_num, row in enumerate(reader, start=2):
            raw_line = ",".join(str(v) for v in row.values())

            card_name = row.get("Name", "").strip()
            if not card_name:
                continue

            cards.append(ParsedCard(
                row_number=row_num,
                card_name=card_name,
                set_code=row.get("Set", "").strip().upper() or None,
                collector_number=row.get("Collector Number", "").strip() or None,
                quantity=cls._parse_quantity(row.get("Quantity")),
                condition=cls._normalize_condition(row.get("Condition")),
                is_foil=cls._parse_foil(row.get("Foil")),
                raw_line=raw_line,
            ))

        return cards

    @classmethod
    def _parse_deckbox(cls, content: str) -> list[ParsedCard]:
        """
        Parse Deckbox CSV export format.

        Expected columns: Count, Tradelist Count, Name, Edition, Card Number, Condition, Language, Foil, Signed, Artist Proof, Altered Art, Misprint, Promo, Textless, My Price
        """
        cards = []
        reader = csv.DictReader(io.StringIO(content))

        for row_num, row in enumerate(reader, start=2):
            raw_line = ",".join(str(v) for v in row.values())

            card_name = row.get("Name", "").strip()
            if not card_name:
                continue

            # Deckbox uses "Count" for owned quantity
            quantity = cls._parse_quantity(row.get("Count"))
            if quantity == 0:
                continue

            cards.append(ParsedCard(
                row_number=row_num,
                card_name=card_name,
                set_name=row.get("Edition", "").strip() or None,
                collector_number=row.get("Card Number", "").strip() or None,
                quantity=quantity,
                condition=cls._normalize_condition(row.get("Condition")),
                is_foil=cls._parse_foil(row.get("Foil")),
                language=row.get("Language", "English").strip() or "English",
                acquisition_price=cls._parse_price(row.get("My Price")),
                raw_line=raw_line,
            ))

        return cards

    @classmethod
    def _parse_tcgplayer(cls, content: str) -> list[ParsedCard]:
        """
        Parse TCGPlayer collection export format.

        Expected columns: Quantity, Name, Simple Name, Set, Card Number, Set Code, Printing, Condition, Language, Rarity, Product ID, SKU, Price, Price Each
        """
        cards = []
        reader = csv.DictReader(io.StringIO(content))

        for row_num, row in enumerate(reader, start=2):
            raw_line = ",".join(str(v) for v in row.values())

            card_name = row.get("Name", row.get("Simple Name", "")).strip()
            if not card_name:
                continue

            # Check if foil from Printing column
            printing = row.get("Printing", "").lower()
            is_foil = "foil" in printing

            cards.append(ParsedCard(
                row_number=row_num,
                card_name=card_name,
                set_code=row.get("Set Code", "").strip().upper() or None,
                set_name=row.get("Set", "").strip() or None,
                collector_number=row.get("Card Number", "").strip() or None,
                quantity=cls._parse_quantity(row.get("Quantity")),
                condition=cls._normalize_condition(row.get("Condition")),
                is_foil=is_foil,
                language=row.get("Language", "English").strip() or "English",
                acquisition_price=cls._parse_price(row.get("Price Each")),
                raw_line=raw_line,
            ))

        return cards

    @classmethod
    def _parse_generic(cls, content: str) -> list[ParsedCard]:
        """
        Parse generic CSV with flexible column detection.

        Attempts to detect columns by common header names.
        """
        cards = []
        reader = csv.DictReader(io.StringIO(content))

        if not reader.fieldnames:
            return cards

        # Map common column names to our fields
        headers = {h.lower().strip(): h for h in reader.fieldnames}

        def find_column(*names: str) -> Optional[str]:
            for name in names:
                if name in headers:
                    return headers[name]
            return None

        name_col = find_column("name", "card name", "cardname", "card")
        qty_col = find_column("quantity", "qty", "count", "amount")
        set_col = find_column("set", "edition", "set code", "set_code", "expansion")
        num_col = find_column("collector number", "card number", "number", "num", "#")
        cond_col = find_column("condition", "cond")
        foil_col = find_column("foil", "finish", "printing")
        lang_col = find_column("language", "lang")
        price_col = find_column("price", "purchase price", "cost", "my price")

        if not name_col:
            # Try first column as name
            name_col = reader.fieldnames[0]

        for row_num, row in enumerate(reader, start=2):
            raw_line = ",".join(str(v) for v in row.values())

            card_name = row.get(name_col, "").strip() if name_col else ""
            if not card_name:
                continue

            cards.append(ParsedCard(
                row_number=row_num,
                card_name=card_name,
                set_code=row.get(set_col, "").strip().upper() if set_col else None,
                collector_number=row.get(num_col, "").strip() if num_col else None,
                quantity=cls._parse_quantity(row.get(qty_col)) if qty_col else 1,
                condition=cls._normalize_condition(row.get(cond_col)) if cond_col else InventoryCondition.NEAR_MINT.value,
                is_foil=cls._parse_foil(row.get(foil_col)) if foil_col else False,
                language=row.get(lang_col, "English").strip() if lang_col else "English",
                acquisition_price=cls._parse_price(row.get(price_col)) if price_col else None,
                raw_line=raw_line,
            ))

        return cards
