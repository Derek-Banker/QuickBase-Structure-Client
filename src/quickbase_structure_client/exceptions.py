"""Exception types and error-formatting helpers for the package."""

from __future__ import annotations

from typing import Any


def _format_detail(value: Any) -> str:
    """Format a contextual error value for display.

    Args:
        value: Value to include in an error message.

    Returns:
        A readable representation of the value.
    """
    if isinstance(value, BaseException):
        return f"{type(value).__name__}: {value}"
    return repr(value)


def format_error_message(
    summary: str,
    *,
    operation: str | None = None,
    endpoint: str | None = None,
    object_ref: str | None = None,
    **context: Any,
) -> str:
    """Build an error message with structured operation context.

    Args:
        summary: Human-readable description of the failure.
        operation: Operation that failed.
        endpoint: Quickbase API endpoint involved in the failure.
        object_ref: Identifier or name of the affected object.
        **context: Additional named values to append to the message.

    Returns:
        The summary followed by any supplied context values.
    """
    details: list[str] = []

    if operation:
        details.append(f"operation={operation}")
    if endpoint:
        details.append(f"endpoint={endpoint}")
    if object_ref:
        details.append(f"object={object_ref}")

    for key, value in context.items():
        if value is None:
            continue
        details.append(f"{key}={_format_detail(value)}")

    if not details:
        return summary
    return f"{summary} [{', '.join(details)}]"


class QuickbaseError(Exception):
    """Base exception for package-level Quickbase failures."""


class QuickbaseValidationError(QuickbaseError, ValueError):
    """Raised when caller input is invalid for the requested operation."""


class QuickbaseConfigurationError(QuickbaseValidationError):
    """Raised when local package configuration or paths are invalid."""


class QuickbaseTransportError(QuickbaseError):
    """Raised for network or transport failures before a valid HTTP response exists."""


class QuickbaseHTTPError(QuickbaseError):
    """Raised when Quickbase returns an unsuccessful HTTP response."""


class QuickbaseAuthError(QuickbaseHTTPError, PermissionError):
    """Raised for authentication or authorization failures."""


class QuickbaseRateLimitError(QuickbaseHTTPError):
    """Raised when Quickbase responds with a rate-limit failure."""


class QuickbaseSchemaError(QuickbaseError):
    """Raised for schema lookup or parsing failures."""


class QuickbaseNotFoundError(QuickbaseError, LookupError):
    """Raised when a requested Quickbase object is missing."""


class QuickbasePayloadError(QuickbaseValidationError):
    """Raised when request or response payload content is invalid."""


class QuickbaseBackupError(QuickbaseError):
    """Raised when a pre-change or post-change backup fails."""


__all__ = [
    "QuickbaseAuthError",
    "QuickbaseConfigurationError",
    "QuickbaseError",
    "QuickbaseHTTPError",
    "QuickbaseNotFoundError",
    "QuickbasePayloadError",
    "QuickbaseRateLimitError",
    "QuickbaseSchemaError",
    "QuickbaseTransportError",
    "QuickbaseValidationError",
    "QuickbaseBackupError",
    "format_error_message",
]
