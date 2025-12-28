"""MTG Set model for tracking Magic: The Gathering sets."""
from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MTGSet(Base):
    """Magic: The Gathering set for collection completion tracking."""

    __tablename__ = "mtg_sets"

    code: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        index=True,
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    released_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    set_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    card_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    icon_svg_uri: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    scryfall_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        unique=True,
        nullable=True
    )
    parent_set_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_digital: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_foil_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<MTGSet code={self.code} name={self.name}>"
