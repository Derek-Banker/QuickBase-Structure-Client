"""Public package interface for the Quickbase Structure Client."""

from __future__ import annotations

from .app import StructureApp
from .exceptions import (
    QuickbaseAuthError,
    QuickbaseBackupError,
    QuickbaseConfigurationError,
    QuickbaseError,
    QuickbaseHTTPError,
    QuickbaseNotFoundError,
    QuickbasePayloadError,
    QuickbasePermissionError,
    QuickbaseRateLimitError,
    QuickbaseSchemaError,
    QuickbaseTransportError,
    QuickbaseValidationError,
)
from .field import StructureField
from .quickbase_api import (
    Auth,
    QuickBaseStructureClient,
    RequestConfig,
    normalize_realm_hostname,
    normalize_user_token,
)
from .relationship import StructureRelationship
from .schema_exporter import SchemaExporter
from .solutions import SolutionsManager
from .table import StructureTable
from .trustees import TrusteesManager

__version__ = "0.1.5"

__all__ = [
    "__version__",
    "Auth",
    "QuickBaseStructureClient",
    "RequestConfig",
    "normalize_realm_hostname",
    "normalize_user_token",
    "StructureApp",
    "StructureTable",
    "StructureField",
    "StructureRelationship",
    "TrusteesManager",
    "SchemaExporter",
    "SolutionsManager",
    "QuickbaseError",
    "QuickbaseValidationError",
    "QuickbaseConfigurationError",
    "QuickbaseTransportError",
    "QuickbaseHTTPError",
    "QuickbaseAuthError",
    "QuickbasePermissionError",
    "QuickbaseRateLimitError",
    "QuickbaseSchemaError",
    "QuickbaseNotFoundError",
    "QuickbaseBackupError",
    "QuickbasePayloadError",
]
