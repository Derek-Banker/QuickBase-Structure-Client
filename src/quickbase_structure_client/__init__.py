from __future__ import annotations

from .quickbase_api import Auth, QuickBaseStructureClient, RequestConfig
from .app import StructureApp
from .field import StructureField
from .relationship import StructureRelationship
from .table import StructureTable
from .trustees import TrusteesManager
from .exceptions import (
    QuickbaseAuthError,
    QuickbaseConfigurationError,
    QuickbaseError,
    QuickbaseHTTPError,
    QuickbaseNotFoundError,
    QuickbaseRateLimitError,
    QuickbaseSchemaError,
    QuickbaseTransportError,
    QuickbaseValidationError,
    QuickbaseBackupError,
    QuickbasePayloadError,
)
from .schema_exporter import SchemaExporter
from .solutions import SolutionsManager

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Auth",
    "QuickBaseStructureClient",
    "RequestConfig",
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
    "QuickbaseRateLimitError",
    "QuickbaseSchemaError",
    "QuickbaseNotFoundError",
    "QuickbaseBackupError",
    "QuickbasePayloadError",
]
