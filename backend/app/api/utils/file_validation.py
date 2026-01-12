"""
File content validation utilities.

Validates file contents beyond just extension/content-type,
including magic byte detection and content analysis.
"""
import csv
import io
from typing import Tuple

import structlog

logger = structlog.get_logger()

# Magic bytes for common file types we want to REJECT
DANGEROUS_MAGIC_BYTES = {
    b"MZ": "Windows executable",
    b"\x7fELF": "Linux executable",
    b"PK\x03\x04": "ZIP archive (could contain executables)",
    b"\x00\x00\x01\x00": "ICO file",
    b"GIF87a": "GIF image",
    b"GIF89a": "GIF image",
    b"\xff\xd8\xff": "JPEG image",
    b"\x89PNG": "PNG image",
    b"%PDF": "PDF document",
    b"Rar!": "RAR archive",
    b"\x1f\x8b": "GZIP archive",
}


def detect_dangerous_content(content: bytes) -> Tuple[bool, str]:
    """
    Check if content appears to be a dangerous file type.

    Args:
        content: Raw file bytes

    Returns:
        Tuple of (is_dangerous, reason)
    """
    for magic, file_type in DANGEROUS_MAGIC_BYTES.items():
        if content.startswith(magic):
            return True, f"File appears to be {file_type}"
    return False, ""


def validate_csv_structure(content: str, max_columns: int = 50) -> Tuple[bool, str]:
    """
    Validate that content is actually valid CSV.

    Args:
        content: Decoded file content
        max_columns: Maximum allowed columns

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        reader = csv.reader(io.StringIO(content))

        # Check header row
        header = next(reader, None)
        if not header:
            return False, "CSV file is empty"

        if len(header) > max_columns:
            return False, f"Too many columns ({len(header)} > {max_columns})"

        # Validate a few rows
        row_count = 0
        for row in reader:
            row_count += 1
            if row_count > 10:
                break  # Only validate first 10 rows

            if len(row) != len(header):
                logger.warning(
                    "CSV row column mismatch",
                    expected=len(header),
                    actual=len(row),
                    row=row_count,
                )

        return True, ""

    except csv.Error as e:
        return False, f"Invalid CSV format: {e}"


def validate_import_file(content: bytes) -> Tuple[bool, str]:
    """
    Full validation for import files.

    Checks:
    1. Not a dangerous file type (magic bytes)
    2. Valid UTF-8 encoding
    3. Valid CSV structure

    Args:
        content: Raw file bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check magic bytes
    is_dangerous, reason = detect_dangerous_content(content)
    if is_dangerous:
        logger.warning("Rejected dangerous file upload", reason=reason)
        return False, reason

    # Validate UTF-8
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError as e:
        return False, f"File is not valid UTF-8: {e}"

    # Validate CSV structure
    is_valid, error = validate_csv_structure(decoded)
    if not is_valid:
        return False, error

    return True, ""
