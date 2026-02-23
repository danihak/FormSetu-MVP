"""Validation result returned by all validators."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationResult:
    """
    Result of a validation operation.

    Attributes:
        valid: Whether the input passed validation.
        normalized: The cleaned/normalized version of the input (if valid).
        error_code: Machine-readable error code (if invalid).
        message: Human-readable error messages keyed by language code.
        partial: Partial data extracted before validation failed.
        suggestions: Possible corrections (e.g., "did you mean SBIN0001234?").
    """
    valid: bool
    normalized: Optional[str] = None
    error_code: Optional[str] = None
    message: dict = field(default_factory=dict)
    partial: Optional[str] = None
    suggestions: list = field(default_factory=list)

    def __bool__(self):
        return self.valid
