"""
FormSetu Validator Library
==========================
Standalone validators for Indian government data formats.
Usable independently of the FormSetu engine.

    pip install formsetu-validator

    from formsetu_validator import validate
    result = validate("aadhaar", "2345 6789 0123")
"""

from .result import ValidationResult
from .validators.aadhaar import AadhaarValidator
from .validators.pan import PANValidator
from .validators.ifsc import IFSCValidator
from .validators.mobile import MobileValidator
from .validators.pincode import PINCodeValidator
from .registry import ValidatorRegistry

# Global registry
_registry = ValidatorRegistry()
_registry.register("aadhaar", AadhaarValidator())
_registry.register("pan", PANValidator())
_registry.register("ifsc", IFSCValidator())
_registry.register("mobile", MobileValidator())
_registry.register("pincode", PINCodeValidator())


def validate(field_type: str, value: str, **kwargs) -> ValidationResult:
    """
    Validate a value against an Indian data format.

    Args:
        field_type: One of "aadhaar", "pan", "ifsc", "mobile", "pincode"
        value: The raw input string
        **kwargs: Additional context (e.g., state for pincode cross-validation)

    Returns:
        ValidationResult with valid, normalized, error_code, message fields
    """
    return _registry.validate(field_type, value, **kwargs)


__all__ = [
    "validate",
    "ValidationResult",
    "AadhaarValidator",
    "PANValidator",
    "IFSCValidator",
    "MobileValidator",
    "PINCodeValidator",
    "ValidatorRegistry",
]
