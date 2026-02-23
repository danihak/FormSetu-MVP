"""PAN Card Validator - Format: AAAAA9999A"""

import re
from .result import ValidationResult


class PANValidator:
    """
    Validates Indian PAN (Permanent Account Number).

    Format: 5 uppercase letters + 4 digits + 1 uppercase letter
    4th character indicates entity type:
      P = Individual, C = Company, H = HUF, F = Firm, etc.
    """

    PATTERN = re.compile(r"^[A-Z]{3}[ABCFGHLJPTK][A-Z][0-9]{4}[A-Z]$")

    ENTITY_TYPES = {
        "A": "Association of Persons",
        "B": "Body of Individuals",
        "C": "Company",
        "F": "Firm/LLP",
        "G": "Government",
        "H": "HUF",
        "L": "Local Authority",
        "J": "Artificial Juridical Person",
        "P": "Individual/Person",
        "T": "Trust",
        "K": "Krishi (not yet used)",
    }

    def validate(self, raw_input: str) -> ValidationResult:
        if not raw_input or not raw_input.strip():
            return ValidationResult(
                valid=False, error_code="PAN_EMPTY",
                message={"en": "PAN number is required.", "hi": "पैन नंबर आवश्यक है।"}
            )

        cleaned = raw_input.upper().replace(" ", "").replace("-", "")

        if len(cleaned) != 10:
            return ValidationResult(
                valid=False, error_code="PAN_LENGTH",
                message={"en": f"PAN must be exactly 10 characters, got {len(cleaned)}."}
            )

        if not self.PATTERN.match(cleaned):
            return ValidationResult(
                valid=False, error_code="PAN_FORMAT",
                message={
                    "en": "PAN format is invalid. It should be like ABCDE1234F.",
                    "hi": "पैन का प्रारूप गलत है। यह ABCDE1234F जैसा होना चाहिए।"
                }
            )

        return ValidationResult(valid=True, normalized=cleaned)
