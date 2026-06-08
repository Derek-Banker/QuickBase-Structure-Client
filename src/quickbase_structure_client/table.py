"""Quickbase table, field, and relationship structure operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from quickbase_structure_client.exceptions import QuickbaseValidationError, format_error_message

if TYPE_CHECKING:
    from quickbase_structure_client.field import StructureField
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient
    from quickbase_structure_client.relationship import StructureRelationship

logger = logging.getLogger(__name__)


def normalize_field_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize convenience field properties for the Quickbase API.

    ``description`` is accepted as an alias for Quickbase's ``fieldHelp``
    property when ``fieldHelp`` is not already present.

    Args:
        payload: Field properties supplied by the caller.

    Returns:
        A shallow copy containing Quickbase-compatible property names.
    """
    normalized = dict(payload)
    if "description" in normalized and "fieldHelp" not in normalized:
        normalized["fieldHelp"] = normalized.pop("description")
    return normalized


class StructureTable:
    """Reference-like wrapper for a Quickbase table.

    Attributes:
        api_client: Client used to execute Quickbase API requests.
    """

    def __init__(
        self,
        api_client: QuickBaseStructureClient,
        id: str,
        app_id: str | None = None,
        name: str | None = None,
    ) -> None:
        """Initialize a table reference.

        Args:
            api_client: Client used to execute API requests.
            id: Quickbase table ID.
            app_id: Parent application ID, when known.
            name: Table name, when known.
        """
        self.api_client = api_client
        self._id = id
        self._app_id = app_id
        self._name = name

    @property
    def id(self) -> str:
        """Return the Quickbase table ID."""
        return self._id

    @property
    def app_id(self) -> str | None:
        """Return the known parent application ID."""
        return self._app_id

    @property
    def name(self) -> str | None:
        """Return the known table name."""
        return self._name

    def _require_app_id(self, operation: str) -> str:
        """Return the parent application ID or raise a validation error.

        Args:
            operation: Name of the operation requiring an application ID.

        Returns:
            The resolved parent application ID.

        Raises:
            QuickbaseValidationError: If this reference has no application ID.
        """
        if not self._app_id:
            raise QuickbaseValidationError(
                format_error_message(
                    "This operation requires a resolved parent App ID on the table reference.",
                    operation=operation,
                    table_id=self._id,
                    table_name=self._name,
                )
            )
        return self._app_id

    def get_details(self) -> Dict[str, Any]:
        """Retrieve the table's properties.

        Returns:
            The table properties returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the parent application ID is unknown.
            QuickbaseError: If the Quickbase request fails.
        """
        app_id = self._require_app_id("StructureTable.get_details")
        response = self.api_client.request(
            method="GET",
            endpoint=f"/tables/{self._id}?appId={app_id}",
        )
        data = response.json()
        if "name" in data and not self._name:
            self._name = data["name"]
        return data

    def update(
        self,
        name: str | None = None,
        plural_name: str | None = None,
        single_record_name: str | None = None,
        description: str | None = None,
    ) -> Dict[str, Any]:
        """Update table properties.

        Args:
            name: New table name.
            plural_name: New plural record name.
            single_record_name: New singular record name.
            description: New table description.

        Returns:
            The updated table payload returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the parent application ID is unknown.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id("StructureTable.update")
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if plural_name is not None:
            payload["pluralRecordName"] = plural_name
        if single_record_name is not None:
            payload["singleRecordName"] = single_record_name
        if description is not None:
            payload["description"] = description

        response = self.api_client.request(
            method="POST",
            endpoint=f"/tables/{self._id}?appId={app_id}",
            payload=payload,
            app_id_for_backup=app_id,
        )
        if name is not None:
            self._name = name
        return response.json()

    def delete(self) -> None:
        """Delete the table.

        Raises:
            QuickbaseValidationError: If the parent application ID is unknown.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id("StructureTable.delete")
        self.api_client.request(
            method="DELETE",
            endpoint=f"/tables/{self._id}?appId={app_id}",
            app_id_for_backup=app_id,
        )

    # FIELD MANAGEMENT
    def field(self, id: int | str, label: str | None = None) -> StructureField:
        """Create a reference to a field in the table.

        Args:
            id: Quickbase field ID.
            label: Optional field label.

        Returns:
            A field reference associated with this table.
        """
        from quickbase_structure_client.field import StructureField

        return StructureField(
            api_client=self.api_client,
            table_id=self._id,
            field_id=id,
            app_id=self._app_id,
            label=label,
        )

    def create_field(
        self,
        label: str,
        field_type: str,
        properties: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Create a field in the table.

        Args:
            label: Field label.
            field_type: Quickbase field type.
            properties: Additional Quickbase field properties. ``description``
                is accepted as an alias for ``fieldHelp``.

        Returns:
            The created field payload returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the parent application ID is unknown.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id("StructureTable.create_field")
        payload: Dict[str, Any] = {
            "label": label,
            "fieldType": field_type,
        }
        if properties:
            payload.update(normalize_field_payload(properties))

        response = self.api_client.request(
            method="POST",
            endpoint=f"/fields?tableId={self._id}",
            payload=payload,
            app_id_for_backup=app_id,
        )
        return response.json()

    def list_fields(self, include_field_perms: bool = False) -> List[Dict[str, Any]]:
        """List fields in the table.

        Args:
            include_field_perms: Whether to include field-level permissions.

        Returns:
            Field metadata returned by Quickbase.

        Raises:
            QuickbaseError: If the Quickbase request fails.
        """
        endpoint = f"/fields?tableId={self._id}"
        if include_field_perms:
            endpoint += "&includeFieldPerms=true"
        response = self.api_client.request(
            method="GET",
            endpoint=endpoint,
        )
        return response.json()

    def update_field(
        self,
        field_id: int | str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a field in the table.

        Args:
            field_id: Quickbase field ID.
            properties: Field properties to update. ``description`` is
                accepted as an alias for ``fieldHelp``.

        Returns:
            The updated field payload returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the parent application ID is unknown.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id("StructureTable.update_field")
        response = self.api_client.request(
            method="POST",
            endpoint=f"/fields/{field_id}?tableId={self._id}",
            payload=normalize_field_payload(properties),
            app_id_for_backup=app_id,
        )
        return response.json()

    def delete_fields(self, field_ids: List[int | str]) -> Dict[str, Any]:
        """Delete one or more fields from the table.

        Args:
            field_ids: Quickbase field IDs to delete.

        Returns:
            The deletion response returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the parent application ID is unknown.
            ValueError: If a field ID cannot be converted to an integer.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id("StructureTable.delete_fields")
        payload = {"fieldIds": [int(fid) for fid in field_ids]}
        response = self.api_client.request(
            method="DELETE",
            endpoint=f"/fields?tableId={self._id}",
            payload=payload,
            app_id_for_backup=app_id,
        )
        return response.json()

    # RELATIONSHIP MANAGEMENT
    def relationship(self, id: int | str) -> StructureRelationship:
        """Create a reference to a relationship on this child table.

        Args:
            id: Quickbase relationship ID.

        Returns:
            A relationship reference associated with this child table.
        """
        from quickbase_structure_client.relationship import StructureRelationship

        return StructureRelationship(
            api_client=self.api_client,
            child_table_id=self._id,
            relationship_id=id,
            app_id=self._app_id,
        )

    def list_relationships(self, skip: int | None = None) -> List[Dict[str, Any]]:
        """List relationships for which this table is the child.

        Args:
            skip: Optional number of relationships to skip.

        Returns:
            Relationship metadata returned by Quickbase.

        Raises:
            QuickbaseError: If the Quickbase request fails.
        """
        endpoint = f"/tables/{self._id}/relationships"
        if skip is not None:
            endpoint += f"?skip={skip}"
        response = self.api_client.request(
            method="GET",
            endpoint=endpoint,
        )
        data = response.json()
        if isinstance(data, list):
            return data
        return data.get("relationships", [])

    def create_relationship(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a relationship with a parent table.

        Args:
            payload: Relationship definition accepted by Quickbase.

        Returns:
            The created relationship payload returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the parent application ID is unknown.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id("StructureTable.create_relationship")
        response = self.api_client.request(
            method="POST",
            endpoint=f"/tables/{self._id}/relationship",
            payload=payload,
            app_id_for_backup=app_id,
        )
        return response.json()

    def update_relationship(
        self,
        relationship_id: int | str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a relationship on the table.

        Args:
            relationship_id: Quickbase relationship ID.
            payload: Relationship properties to update.

        Returns:
            The updated relationship payload returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the parent application ID is unknown.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id("StructureTable.update_relationship")
        response = self.api_client.request(
            method="POST",
            endpoint=f"/tables/{self._id}/relationship/{relationship_id}",
            payload=payload,
            app_id_for_backup=app_id,
        )
        return response.json()

    def delete_relationship(self, relationship_id: int | str) -> Dict[str, Any]:
        """Delete a relationship from the table.

        Args:
            relationship_id: Quickbase relationship ID.

        Returns:
            The deletion response returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the parent application ID is unknown.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id("StructureTable.delete_relationship")
        response = self.api_client.request(
            method="DELETE",
            endpoint=f"/tables/{self._id}/relationship/{relationship_id}",
            app_id_for_backup=app_id,
        )
        return response.json()
