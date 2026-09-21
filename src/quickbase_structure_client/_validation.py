"""Shared validation for Quickbase resource identifiers and field definitions."""

from __future__ import annotations

import re
from typing import Any, Dict

from quickbase_structure_client.exceptions import QuickbaseValidationError, format_error_message


def validate_dbid(value: str, *, argument_name: str = "app_id") -> str:
    """Require a non-empty ASCII alphanumeric application or table ID.

    The validation rejects paths and URL fragments before requests or backups.
    Quickbase determines whether the identifier names an existing resource.
    """
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9]+", value) is None:
        raise QuickbaseValidationError(
            format_error_message(
                f"{argument_name} must be a non-empty ASCII alphanumeric Quickbase ID.",
                operation="validate_dbid",
            )
        )
    return value


def validate_field_id(value: int | str) -> int:
    """Return a positive field ID without truncating numbers or accepting booleans.

    Args:
        value: Positive integer or string containing ASCII decimal digits.

    Returns:
        The field ID as an integer.

    Raises:
        QuickbaseValidationError: If the ID is invalid or too large to serialize.
    """
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise QuickbaseValidationError("Field ID must be a positive integer or numeric string.")
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value) is None:
        raise QuickbaseValidationError("Field ID must contain only ASCII decimal digits.")
    try:
        field_id = int(value)
        str(field_id)
    except ValueError as exc:
        raise QuickbaseValidationError("Field ID is too large to serialize.") from exc
    if field_id <= 0:
        raise QuickbaseValidationError("Field ID must be greater than zero.")
    return field_id


def validate_field_definition(payload: Dict[str, Any]) -> None:
    """Require a label and field type in the final field creation payload.

    Unknown non-empty type names pass through for Quickbase to validate.
    """
    for name in ("label", "fieldType"):
        value = payload.get(name)
        if not isinstance(value, str) or not value.strip():
            raise QuickbaseValidationError(
                format_error_message(
                    f"{name} must be a non-empty string.",
                    operation="validate_field_definition",
                )
            )
