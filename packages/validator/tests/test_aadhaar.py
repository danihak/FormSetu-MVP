"""
Tests for Aadhaar validator.
Run: pytest packages/validator/tests/test_aadhaar.py -v
"""

import pytest
import sys
sys.path.insert(0, "packages/validator/src")

from validators.aadhaar import AadhaarValidator


@pytest.fixture
def validator():
    return AadhaarValidator()


class TestAadhaarFormat:
    """Test basic format validation."""

    def test_valid_12_digits(self, validator):
        # Using a number that passes Verhoeff (computed)
        result = validator.validate("499118665246")
        assert result.valid is True
        assert result.normalized == "499118665246"

    def test_valid_with_spaces(self, validator):
        result = validator.validate("4991 1866 5246")
        assert result.valid is True
        assert result.normalized == "499118665246"

    def test_valid_with_dashes(self, validator):
        result = validator.validate("4991-1866-5246")
        assert result.valid is True

    def test_too_short(self, validator):
        result = validator.validate("1234 5678")
        assert result.valid is False
        assert result.error_code == "AADHAAR_TOO_SHORT"
        assert result.partial == "12345678"

    def test_too_long(self, validator):
        result = validator.validate("1234567890123")
        assert result.valid is False
        assert result.error_code == "AADHAAR_TOO_LONG"

    def test_empty_input(self, validator):
        result = validator.validate("")
        assert result.valid is False
        assert result.error_code == "AADHAAR_EMPTY"

    def test_whitespace_only(self, validator):
        result = validator.validate("   ")
        assert result.valid is False
        assert result.error_code == "AADHAAR_EMPTY"


class TestAadhaarStartDigit:
    """Aadhaar cannot start with 0 or 1."""

    def test_starts_with_zero(self, validator):
        result = validator.validate("012345678901")
        assert result.valid is False
        assert result.error_code == "AADHAAR_INVALID_START"

    def test_starts_with_one(self, validator):
        result = validator.validate("112345678901")
        assert result.valid is False
        assert result.error_code == "AADHAAR_INVALID_START"

    def test_starts_with_two(self, validator):
        # Starts with 2 is allowed (checksum may or may not pass)
        result = validator.validate("234567890123")
        # Should not fail on start digit
        assert result.error_code != "AADHAAR_INVALID_START"


class TestAadhaarVerhoeff:
    """Test Verhoeff checksum validation."""

    def test_checksum_pass(self, validator):
        # Known valid Verhoeff number
        assert validator._verhoeff_checksum("499118665246") is True

    def test_checksum_fail_single_digit_change(self, validator):
        # Change last digit — should fail Verhoeff
        result = validator.validate("499118665247")
        assert result.valid is False
        assert result.error_code == "AADHAAR_CHECKSUM_FAIL"

    def test_checksum_fail_transposition(self, validator):
        # Swap two adjacent digits — Verhoeff detects this
        result = validator.validate("499118665264")
        assert result.valid is False


class TestAadhaarBlockedPatterns:
    """Reject obviously fake numbers."""

    def test_all_same_digits(self, validator):
        result = validator.validate("222222222222")
        assert result.valid is False
        assert result.error_code == "AADHAAR_BLOCKED_PATTERN"

    def test_sequential(self, validator):
        result = validator.validate("123456789012")
        assert result.valid is False
        # Starts with 1, so caught by INVALID_START before BLOCKED_PATTERN
        assert result.error_code == "AADHAAR_INVALID_START"


class TestAadhaarErrorMessages:
    """Ensure error messages are bilingual."""

    def test_error_has_english(self, validator):
        result = validator.validate("123")
        assert "en" in result.message

    def test_error_has_hindi(self, validator):
        result = validator.validate("123")
        assert "hi" in result.message


class TestValidationResultBool:
    """ValidationResult should be usable as boolean."""

    def test_valid_is_truthy(self, validator):
        result = validator.validate("499118665246")
        assert result  # Should be truthy

    def test_invalid_is_falsy(self, validator):
        result = validator.validate("123")
        assert not result  # Should be falsy
