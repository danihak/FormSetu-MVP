"""
Validator Registry
==================
Central registry for all field validators. Allows plugging in custom validators.
"""

from .result import ValidationResult


class ValidatorRegistry:
    """
    Registry of field type validators.
    
    Usage:
        registry = ValidatorRegistry()
        registry.register("aadhaar", AadhaarValidator())
        result = registry.validate("aadhaar", "1234 5678 9012")
    """

    def __init__(self):
        self._validators = {}

    def register(self, field_type: str, validator):
        """Register a validator for a field type."""
        if not hasattr(validator, "validate"):
            raise ValueError(f"Validator for '{field_type}' must have a validate() method")
        self._validators[field_type] = validator

    def validate(self, field_type: str, value: str, **kwargs) -> ValidationResult:
        """
        Validate a value using the registered validator for the given field type.
        
        Raises KeyError if no validator is registered for the field type.
        """
        if field_type not in self._validators:
            raise KeyError(
                f"No validator registered for field type '{field_type}'. "
                f"Available: {list(self._validators.keys())}"
            )
        return self._validators[field_type].validate(value, **kwargs) if kwargs else self._validators[field_type].validate(value)

    def list_types(self) -> list[str]:
        """List all registered field types."""
        return list(self._validators.keys())

    def has(self, field_type: str) -> bool:
        """Check if a validator is registered for a field type."""
        return field_type in self._validators
