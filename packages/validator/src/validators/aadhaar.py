"""
Aadhaar Number Validator
========================
Validates 12-digit Aadhaar numbers issued by UIDAI.
Uses Verhoeff checksum algorithm (last digit is check digit).
"""

import re
from .result import ValidationResult


class AadhaarValidator:
    """
    Validates Indian Aadhaar numbers.

    Rules:
    - Exactly 12 digits
    - First digit cannot be 0 or 1 (UIDAI doesn't issue these)
    - Last digit is Verhoeff checksum
    - Common test numbers (e.g., all same digits) are rejected
    """

    # Verhoeff algorithm tables
    VERHOEFF_D = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
        [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
        [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
        [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
        [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
        [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
    ]

    VERHOEFF_P = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
        [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
        [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
        [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
        [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
    ]

    VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]

    # Known test/dummy Aadhaar patterns
    BLOCKED_PATTERNS = {
        "000000000000", "111111111111", "222222222222",
        "333333333333", "444444444444", "555555555555",
        "666666666666", "777777777777", "888888888888",
        "999999999999", "123456789012",
    }

    def _verhoeff_checksum(self, number: str) -> bool:
        """Verify Verhoeff checksum. Returns True if valid."""
        c = 0
        for i, digit in enumerate(reversed(number)):
            c = self.VERHOEFF_D[c][self.VERHOEFF_P[i % 8][int(digit)]]
        return c == 0

    def _extract_digits(self, raw: str) -> str:
        """Extract only digits from input. Handles spaces, dashes, dots."""
        return re.sub(r"[^0-9]", "", raw)

    def validate(self, raw_input: str) -> ValidationResult:
        """
        Validate an Aadhaar number.

        Accepts formats: "2345 6789 0123", "234567890123", "2345-6789-0123"

        Returns:
            ValidationResult with normalized 12-digit string if valid.
        """
        if not raw_input or not raw_input.strip():
            return ValidationResult(
                valid=False,
                error_code="AADHAAR_EMPTY",
                message={
                    "en": "Aadhaar number is required.",
                    "hi": "आधार संख्या आवश्यक है।",
                },
            )

        digits = self._extract_digits(raw_input)

        if len(digits) < 12:
            return ValidationResult(
                valid=False,
                error_code="AADHAAR_TOO_SHORT",
                message={
                    "en": f"Aadhaar must be 12 digits. You gave {len(digits)} digits.",
                    "hi": f"आधार 12 अंकों का होना चाहिए। आपने {len(digits)} अंक दिए।",
                },
                partial=digits,
            )

        if len(digits) > 12:
            return ValidationResult(
                valid=False,
                error_code="AADHAAR_TOO_LONG",
                message={
                    "en": f"Aadhaar must be 12 digits. You gave {len(digits)} digits.",
                    "hi": f"आधार 12 अंकों का होना चाहिए। आपने {len(digits)} अंक दिए।",
                },
                partial=digits[:12],
            )

        if digits[0] in ("0", "1"):
            return ValidationResult(
                valid=False,
                error_code="AADHAAR_INVALID_START",
                message={
                    "en": "Aadhaar numbers cannot start with 0 or 1.",
                    "hi": "आधार नंबर 0 या 1 से शुरू नहीं हो सकता।",
                },
            )

        if digits in self.BLOCKED_PATTERNS:
            return ValidationResult(
                valid=False,
                error_code="AADHAAR_BLOCKED_PATTERN",
                message={
                    "en": "This does not appear to be a valid Aadhaar number.",
                    "hi": "यह एक मान्य आधार संख्या नहीं लगती।",
                },
            )

        if not self._verhoeff_checksum(digits):
            return ValidationResult(
                valid=False,
                error_code="AADHAAR_CHECKSUM_FAIL",
                message={
                    "en": "Aadhaar number checksum is incorrect. Please check and try again.",
                    "hi": "आधार नंबर की जांच में त्रुटि। कृपया दोबारा जांच करें।",
                },
            )

        # Format as XXXX XXXX XXXX for display
        f"{digits[:4]} {digits[4:8]} {digits[8:12]}"

        return ValidationResult(valid=True, normalized=digits)
