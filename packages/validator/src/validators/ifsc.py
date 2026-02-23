"""IFSC Code Validator - Format: AAAA0BBBBBB"""

import re
from .result import ValidationResult


class IFSCValidator:
    PATTERN = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")

    def validate(self, raw_input: str) -> ValidationResult:
        if not raw_input or not raw_input.strip():
            return ValidationResult(valid=False, error_code="IFSC_EMPTY",
                                    message={"en": "IFSC code is required."})
        cleaned = raw_input.upper().replace(" ", "").replace("-", "")
        if len(cleaned) != 11:
            return ValidationResult(valid=False, error_code="IFSC_LENGTH",
                                    message={"en": f"IFSC must be 11 characters, got {len(cleaned)}."})
        if not self.PATTERN.match(cleaned):
            return ValidationResult(valid=False, error_code="IFSC_FORMAT",
                                    message={"en": "IFSC format: 4 letters + 0 + 6 alphanumeric. Example: SBIN0001234",
                                             "hi": "IFSC का प्रारूप: 4 अक्षर + 0 + 6 अंक। जैसे: SBIN0001234"})
        return ValidationResult(valid=True, normalized=cleaned)
