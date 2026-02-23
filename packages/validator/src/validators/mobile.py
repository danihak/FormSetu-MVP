"""Indian Mobile Number Validator - 10 digits, starts with 6/7/8/9"""

import re
from .result import ValidationResult


class MobileValidator:
    def validate(self, raw_input: str) -> ValidationResult:
        if not raw_input or not raw_input.strip():
            return ValidationResult(valid=False, error_code="MOBILE_EMPTY",
                                    message={"en": "Mobile number is required."})
        digits = re.sub(r"[^0-9]", "", raw_input)
        # Handle +91 prefix
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        if len(digits) != 10:
            return ValidationResult(valid=False, error_code="MOBILE_LENGTH",
                                    message={"en": f"Mobile number must be 10 digits, got {len(digits)}.",
                                             "hi": f"मोबाइल नंबर 10 अंकों का होना चाहिए, आपने {len(digits)} दिए।"})
        if digits[0] not in "6789":
            return ValidationResult(valid=False, error_code="MOBILE_PREFIX",
                                    message={"en": "Indian mobile numbers start with 6, 7, 8, or 9.",
                                             "hi": "भारतीय मोबाइल नंबर 6, 7, 8 या 9 से शुरू होते हैं।"})
        return ValidationResult(valid=True, normalized=digits)
