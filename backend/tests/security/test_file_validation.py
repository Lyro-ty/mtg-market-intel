"""Tests for file content validation utilities."""
import pytest

from app.api.utils.file_validation import (
    detect_dangerous_content,
    validate_csv_structure,
    validate_import_file,
)


class TestDangerousContentDetection:
    """Tests for magic byte detection of dangerous files."""

    def test_detects_windows_executable(self):
        """Windows PE executables should be detected."""
        content = b"MZ\x90\x00\x03\x00\x00\x00"  # PE header start
        is_dangerous, reason = detect_dangerous_content(content)
        assert is_dangerous
        assert "executable" in reason.lower()

    def test_detects_linux_executable(self):
        """Linux ELF executables should be detected."""
        content = b"\x7fELF\x02\x01\x01\x00"  # ELF header
        is_dangerous, reason = detect_dangerous_content(content)
        assert is_dangerous
        assert "executable" in reason.lower()

    def test_detects_zip_archive(self):
        """ZIP archives should be detected (could contain executables)."""
        content = b"PK\x03\x04\x14\x00\x00\x00"  # ZIP header
        is_dangerous, reason = detect_dangerous_content(content)
        assert is_dangerous
        assert "ZIP" in reason

    def test_detects_pdf(self):
        """PDF documents should be detected."""
        content = b"%PDF-1.4 some pdf content"
        is_dangerous, reason = detect_dangerous_content(content)
        assert is_dangerous
        assert "PDF" in reason

    def test_detects_png_image(self):
        """PNG images should be detected."""
        content = b"\x89PNG\r\n\x1a\n\x00\x00\x00"
        is_dangerous, reason = detect_dangerous_content(content)
        assert is_dangerous
        assert "PNG" in reason

    def test_detects_jpeg_image(self):
        """JPEG images should be detected."""
        content = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        is_dangerous, reason = detect_dangerous_content(content)
        assert is_dangerous
        assert "JPEG" in reason

    def test_detects_gif_image(self):
        """GIF images should be detected."""
        content = b"GIF89a\x00\x00\x00"
        is_dangerous, reason = detect_dangerous_content(content)
        assert is_dangerous
        assert "GIF" in reason

    def test_detects_rar_archive(self):
        """RAR archives should be detected."""
        content = b"Rar!\x1a\x07\x00"
        is_dangerous, reason = detect_dangerous_content(content)
        assert is_dangerous
        assert "RAR" in reason

    def test_detects_gzip_archive(self):
        """GZIP archives should be detected."""
        content = b"\x1f\x8b\x08\x00\x00\x00"
        is_dangerous, reason = detect_dangerous_content(content)
        assert is_dangerous
        assert "GZIP" in reason

    def test_allows_csv_content(self):
        """Valid CSV content should not be flagged as dangerous."""
        content = b"name,quantity,price\nLightning Bolt,4,2.50"
        is_dangerous, _ = detect_dangerous_content(content)
        assert not is_dangerous

    def test_allows_plain_text(self):
        """Plain text should not be flagged as dangerous."""
        content = b"Just some plain text content"
        is_dangerous, _ = detect_dangerous_content(content)
        assert not is_dangerous

    def test_allows_csv_with_bom(self):
        """CSV with UTF-8 BOM should not be flagged as dangerous."""
        # UTF-8 BOM followed by CSV content
        content = b"\xef\xbb\xbfname,quantity\nBolt,4"
        is_dangerous, _ = detect_dangerous_content(content)
        assert not is_dangerous


class TestCsvValidation:
    """Tests for CSV structure validation."""

    def test_valid_csv(self):
        """Valid CSV should pass validation."""
        content = "name,quantity,price\nLightning Bolt,4,2.50\nCounterspell,2,1.00"
        is_valid, error = validate_csv_structure(content)
        assert is_valid
        assert error == ""

    def test_empty_csv_rejected(self):
        """Empty CSV should be rejected."""
        content = ""
        is_valid, error = validate_csv_structure(content)
        assert not is_valid
        assert "empty" in error.lower()

    def test_too_many_columns_rejected(self):
        """CSV with too many columns should be rejected."""
        content = ",".join([f"col{i}" for i in range(100)])
        is_valid, error = validate_csv_structure(content, max_columns=50)
        assert not is_valid
        assert "columns" in error.lower()

    def test_custom_max_columns(self):
        """Custom max_columns limit should be respected."""
        # 5 columns should be rejected when limit is 3
        content = "a,b,c,d,e\n1,2,3,4,5"
        is_valid, error = validate_csv_structure(content, max_columns=3)
        assert not is_valid
        assert "columns" in error.lower()

    def test_single_column_csv(self):
        """Single column CSV should be valid."""
        content = "name\nLightning Bolt\nCounterspell"
        is_valid, error = validate_csv_structure(content)
        assert is_valid

    def test_csv_with_quotes(self):
        """CSV with quoted fields should be valid."""
        content = 'name,description\n"Lightning Bolt","Deals 3 damage"'
        is_valid, error = validate_csv_structure(content)
        assert is_valid

    def test_csv_with_newlines_in_quotes(self):
        """CSV with newlines inside quoted fields should be valid."""
        content = 'name,description\n"Lightning Bolt","Line 1\nLine 2"'
        is_valid, error = validate_csv_structure(content)
        assert is_valid

    def test_whitespace_only_csv(self):
        """Whitespace-only content is technically valid CSV (one cell with whitespace)."""
        # CSV parser treats "   \n\n   " as valid - one cell containing "   "
        # This is correct behavior - semantic validation happens elsewhere
        content = "   \n\n   "
        is_valid, error = validate_csv_structure(content)
        # Whitespace is valid CSV, just has one column with whitespace
        assert is_valid


class TestFullValidation:
    """Tests for full import file validation."""

    def test_valid_csv_file(self):
        """Valid CSV file should pass all validation."""
        content = b"name,quantity\nBolt,4"
        is_valid, error = validate_import_file(content)
        assert is_valid
        assert error == ""

    def test_executable_rejected(self):
        """Executable disguised as CSV should be rejected."""
        content = b"MZ\x90\x00" + b"name,qty\ntest,1"
        is_valid, error = validate_import_file(content)
        assert not is_valid
        assert "executable" in error.lower()

    def test_invalid_utf8_rejected(self):
        """File with invalid UTF-8 should be rejected."""
        content = b"\xff\xfe name,qty"  # Invalid UTF-8
        is_valid, error = validate_import_file(content)
        assert not is_valid
        assert "UTF-8" in error

    def test_pdf_disguised_as_csv_rejected(self):
        """PDF file disguised with .csv extension should be rejected."""
        content = b"%PDF-1.4\nname,qty\ntest,1"
        is_valid, error = validate_import_file(content)
        assert not is_valid
        assert "PDF" in error

    def test_zip_disguised_as_csv_rejected(self):
        """ZIP file should be rejected."""
        content = b"PK\x03\x04 some,csv,data"
        is_valid, error = validate_import_file(content)
        assert not is_valid
        assert "ZIP" in error

    def test_empty_file_rejected(self):
        """Empty file should be rejected."""
        content = b""
        is_valid, error = validate_import_file(content)
        assert not is_valid
        assert "empty" in error.lower()

    def test_valid_utf8_with_special_chars(self):
        """Valid UTF-8 with special characters should pass."""
        content = "name,quantity\nBolt,4\nAether Vial,2".encode("utf-8")
        is_valid, error = validate_import_file(content)
        assert is_valid

    def test_csv_with_unicode(self):
        """CSV with unicode characters should pass."""
        content = "name,quantity\nAEther Vial,2\nJuzam Djinn,1".encode("utf-8")
        is_valid, error = validate_import_file(content)
        assert is_valid

    def test_real_world_moxfield_format(self):
        """Real-world Moxfield export format should pass."""
        content = b"""Name,Quantity,Collector Number,Set,Set Name,Foil
"Lightning Bolt",4,"245","2xm","Double Masters",false
"Counterspell",2,"031","mh2","Modern Horizons 2",true"""
        is_valid, error = validate_import_file(content)
        assert is_valid

    def test_real_world_tcgplayer_format(self):
        """Real-world TCGPlayer export format should pass."""
        content = b"""Quantity,Name,Simple Name,Set,Card Number,Printing,Rarity,Condition,Language
4,Lightning Bolt,Lightning Bolt,Double Masters,245,Normal,Rare,Near Mint,English"""
        is_valid, error = validate_import_file(content)
        assert is_valid
