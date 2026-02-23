"""Indian PIN Code Validator - 6 digits, first digit 1-9"""

import re
from .result import ValidationResult


class PINCodeValidator:
    # First digit → region mapping
    REGION_MAP = {
        "1": "Delhi, Haryana, Punjab, HP, J&K, Chandigarh",
        "2": "UP, Uttarakhand",
        "3": "Rajasthan, Gujarat, Daman & Diu, Dadra & Nagar Haveli",
        "4": "Maharashtra, Goa, MP, Chhattisgarh",
        "5": "AP, Telangana, Karnataka",
        "6": "Tamil Nadu, Kerala, Puducherry, Lakshadweep",
        "7": "West Bengal, Odisha, Arunachal, Nagaland, Manipur, Mizoram, Tripura, Meghalaya, AN Islands, Assam, Sikkim",
        "8": "Bihar, Jharkhand",
        "9": "Army Post Office (APO/FPO)",
    }

    def validate(self, raw_input: str, **kwargs) -> ValidationResult:
        if not raw_input or not raw_input.strip():
            return ValidationResult(valid=False, error_code="PIN_EMPTY",
                                    message={"en": "PIN code is required."})
        digits = re.sub(r"[^0-9]", "", raw_input)
        if len(digits) != 6:
            return ValidationResult(valid=False, error_code="PIN_LENGTH",
                                    message={"en": f"PIN code must be 6 digits, got {len(digits)}.",
                                             "hi": f"पिन कोड 6 अंकों का होना चाहिए।"})
        if digits[0] == "0":
            return ValidationResult(valid=False, error_code="PIN_INVALID_START",
                                    message={"en": "PIN code cannot start with 0."})
        return ValidationResult(valid=True, normalized=digits)
