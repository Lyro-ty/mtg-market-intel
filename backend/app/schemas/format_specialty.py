"""
Format specialty schemas for API request/response validation.

Users can indicate which MTG formats they specialize in
(e.g., Commander, Modern, Standard) for discovery purposes.
"""
from typing import Literal

from pydantic import BaseModel, Field


# Allowed MTG formats for format specialties
ALLOWED_FORMATS = [
    "Standard",
    "Pioneer",
    "Modern",
    "Legacy",
    "Vintage",
    "Pauper",
    "Commander",
    "cEDH",
    "Oathbreaker",
    "Brawl",
    "Historic",
    "Explorer",
    "Alchemy",
    "Premodern",
    "Old School",
    "Penny Dreadful",
    "Limited",
    "Draft",
    "Sealed",
    "Cube",
]

FormatType = Literal[
    "Standard",
    "Pioneer",
    "Modern",
    "Legacy",
    "Vintage",
    "Pauper",
    "Commander",
    "cEDH",
    "Oathbreaker",
    "Brawl",
    "Historic",
    "Explorer",
    "Alchemy",
    "Premodern",
    "Old School",
    "Penny Dreadful",
    "Limited",
    "Draft",
    "Sealed",
    "Cube",
]


class AddFormatRequest(BaseModel):
    """Schema for adding a format specialty."""

    format: FormatType = Field(..., description="The MTG format to add as a specialty")


class ReplaceFormatsRequest(BaseModel):
    """Schema for replacing all format specialties."""

    formats: list[FormatType] = Field(
        ...,
        max_length=10,
        description="List of MTG formats to set as specialties (max 10)",
    )


class FormatSpecialtiesResponse(BaseModel):
    """Response schema for format specialties."""

    formats: list[str] = Field(..., description="List of format specialties")
    count: int = Field(..., description="Number of format specialties")
