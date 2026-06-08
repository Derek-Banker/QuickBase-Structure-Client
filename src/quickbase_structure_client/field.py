"""Quickbase field structure operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict

from quickbase_structure_client.exceptions import QuickbaseValidationError, format_error_message
from quickbase_structure_client.table import normalize_field_payload

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient

logger = logging.getLogger(__name__)


class StructureField:
    """Reference-like wrapper for a Quickbase field.

    Attributes:
        api_client: Client used to execute Quickbase API requests.
    """

    def __init__(
        self,
        api_client: QuickBaseStructureClient,
        table_id: str,
        field_id: int | str | None = None,
        *,
        app_id: str | None = None,
        label: str | None = None,
    ) -> None:
        """Initialize a field reference.

        Args:
            api_client: Client used to execute API requests.
            table_id: ID of the table containing the field.
            field_id: Quickbase field ID, if already known.
            app_id: Parent application ID, when known.
            label: Field label, when known.
        """
        self.api_client = api_client
        self._table_id = table_id
        self._field_id = field_id
        self._app_id = app_id
        self._label = label

    @property
    def table_id(self) -> str:
        """Return the ID of the table containing the field."""
        return self._table_id

    @property
    def id(self) -> int | str | None:
        """Return the resolved Quickbase field ID."""
        return self._field_id

    @property
    def app_id(self) -> str | None:
        """Return the known parent application ID."""
        return self._app_id

    @property
    def label(self) -> str | None:
        """Return the known field label."""
        return self._label

    def _require_id(self, operation: str) -> int | str:
        """Return the field ID or raise a validation error.

        Args:
            operation: Name of the operation requiring a field ID.

        Returns:
            The resolved field ID.

        Raises:
            QuickbaseValidationError: If this reference has no field ID.
        """
        if self._field_id is None:
            raise QuickbaseValidationError(
                format_error_message(
                    "This operation requires a resolved field ID.",
                    operation=operation,
                    table_id=self._table_id,
                    field_label=self._label,
                )
            )
        return self._field_id

    def _backup_app_id(self, operation: str) -> str | None:
        """Return the application ID required by automatic backups.

        Args:
            operation: Name of the pending mutating operation.

        Returns:
            The parent application ID, or ``None`` when backup is disabled.

        Raises:
            QuickbaseValidationError: If automatic backup is enabled and the
                parent application ID is unknown.
        """
        if self.api_client.auto_backup and not self._app_id:
            raise QuickbaseValidationError(
                format_error_message(
                    "Mutating field operations require app_id when auto_backup is enabled.",
                    operation=operation,
                    table_id=self._table_id,
                    field_id=self._field_id,
                )
            )
        return self._app_id

    def create(
        self,
        label: str,
        field_type: str,
        properties: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Create the field and update this reference.

        Args:
            label: Field label.
            field_type: Quickbase field type.
            properties: Additional Quickbase field properties. ``description``
                is accepted as an alias for ``fieldHelp``.

        Returns:
            The created field payload returned by Quickbase.

        Raises:
            QuickbaseValidationError: If automatic backup is enabled and the
                parent application ID is unknown.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        payload: Dict[str, Any] = {
            "label": label,
            "fieldType": field_type,
        }
        if properties:
            payload.update(normalize_field_payload(properties))

        response = self.api_client.request(
            method="POST",
            endpoint=f"/fields?tableId={self._table_id}",
            payload=payload,
            app_id_for_backup=self._backup_app_id("StructureField.create"),
        )
        data = response.json()
        self._field_id = data.get("id", self._field_id)
        self._label = data.get("label", label)
        return data

    def get_details(self, include_field_perms: bool = False) -> Dict[str, Any]:
        """Retrieve the field's properties.

        Args:
            include_field_perms: Whether to include field-level permissions.

        Returns:
            The field properties returned by Quickbase.

        Raises:
            QuickbaseValidationError: If this reference has no field ID.
            QuickbaseError: If the Quickbase request fails.
        """
        field_id = self._require_id("StructureField.get_details")
        endpoint = f"/fields/{field_id}?tableId={self._table_id}"
        if include_field_perms:
            endpoint += "&includeFieldPerms=true"

        response = self.api_client.request(method="GET", endpoint=endpoint)
        data = response.json()
        if "label" in data and not self._label:
            self._label = data["label"]
        return data

    def update(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Update field properties.

        Args:
            properties: Field properties to update. ``description`` is
                accepted as an alias for ``fieldHelp``.

        Returns:
            The updated field payload returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the field ID is unavailable, or if
                automatic backup requires an unknown application ID.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        field_id = self._require_id("StructureField.update")
        response = self.api_client.request(
            method="POST",
            endpoint=f"/fields/{field_id}?tableId={self._table_id}",
            payload=normalize_field_payload(properties),
            app_id_for_backup=self._backup_app_id("StructureField.update"),
        )
        data = response.json()
        if "label" in data:
            self._label = data["label"]
        return data

    def delete(self) -> Dict[str, Any]:
        """Delete the field and clear its ID from this reference.

        Returns:
            The deletion response returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the field ID is unavailable, or if
                automatic backup requires an unknown application ID.
            ValueError: If the field ID cannot be converted to an integer.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        field_id = self._require_id("StructureField.delete")
        response = self.api_client.request(
            method="DELETE",
            endpoint=f"/fields?tableId={self._table_id}",
            payload={"fieldIds": [int(field_id)]},
            app_id_for_backup=self._backup_app_id("StructureField.delete"),
        )
        self._field_id = None
        return response.json()
