"""Quickbase table, field, and relationship structure operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from quickbase_structure_client._validation import (
    validate_dbid,
    validate_field_definition,
    validate_field_id,
)
from quickbase_structure_client._xml import parse_xml_response, validate_xml_id
from quickbase_structure_client.exceptions import QuickbaseValidationError, format_error_message

if TYPE_CHECKING:
    from quickbase_structure_client.field import StructureField
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient
    from quickbase_structure_client.relationship import StructureRelationship

logger = logging.getLogger(__name__)


def normalize_field_payload(
    options: Dict[str, Any] | None = None,
    *,
    properties: Dict[str, Any] | None = None,
    required: bool = False,
) -> Dict[str, Any]:
    """Normalize convenience field properties for the Quickbase API.

    ``description`` is accepted as an alias for Quickbase's ``fieldHelp``
    property. An explicit ``fieldHelp`` value takes precedence.

    Args:
        options: Top-level field options supplied by the caller.
        properties: Legacy alias for ``options``.
        required: Whether the caller must supply either argument.

    Returns:
        A shallow copy containing Quickbase-compatible property names.

    Raises:
        QuickbaseValidationError: If both arguments are supplied, a required
            argument is missing, or the options have an invalid dictionary shape.
    """
    if options is not None and properties is not None:
        raise QuickbaseValidationError(
            format_error_message(
                "Specify options or properties, not both.",
                operation="normalize_field_payload",
            )
        )
    payload = options if options is not None else properties
    if payload is None:
        if required:
            raise QuickbaseValidationError(
                format_error_message(
                    "Field options are required.",
                    operation="normalize_field_payload",
                )
            )
        return {}
    if not isinstance(payload, dict):
        raise QuickbaseValidationError(
            format_error_message(
                "Field options must be a dictionary.",
                operation="normalize_field_payload",
            )
        )
    if "properties" in payload and not isinstance(payload["properties"], dict):
        raise QuickbaseValidationError(
            format_error_message(
                "The nested properties option must be a dictionary.",
                operation="normalize_field_payload",
            )
        )
    normalized = dict(payload)
    if "description" in normalized:
        description = normalized.pop("description")
        normalized.setdefault("fieldHelp", description)
    return normalized


class StructureTable:
    """Reference-like wrapper for a Quickbase table.

    HTTP operations require a non-empty ASCII alphanumeric table ID. Operations
    with an application context validate the application ID before the request.

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

    def _require_table_id(self) -> str:
        """Return the validated table ID before an HTTP operation."""
        return validate_dbid(self._id, argument_name="table_id")

    def _require_app_id(self, operation: str) -> str:
        """Return the parent application ID or raise a validation error.

        Args:
            operation: Name of the operation requiring an application ID.

        Returns:
            The resolved parent application ID.

        Raises:
            QuickbaseValidationError: If the application ID is missing or invalid.
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
        return validate_dbid(self._app_id)

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
            endpoint=f"/tables/{self._require_table_id()}?appId={app_id}",
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
            endpoint=f"/tables/{self._require_table_id()}?appId={app_id}",
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
            endpoint=f"/tables/{self._require_table_id()}?appId={app_id}",
            app_id_for_backup=app_id,
        )

    def set_key_field(self, field_id: int | str, *, app_token: str | None = None) -> Dict[str, str]:
        """Set the table's key field through the Quickbase XML API.

        Args:
            field_id: Positive ID of the field to use as the table key.
            app_token: Application token, if the application requires one.

        Returns:
            The successful XML response as a dictionary of text values.

        Raises:
            QuickbaseValidationError: If the field ID is invalid or the parent
                application ID is unknown.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id("StructureTable.set_key_field")
        normalized_id = validate_xml_id(field_id)
        response = self.api_client.request(
            method="POST",
            endpoint=f"/db/{self._require_table_id()}",
            payload={"fid": normalized_id},
            xml_action="API_SetKeyField",
            app_token=app_token,
            app_id_for_backup=app_id,
        )
        return parse_xml_response(response.text)

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
        options: Dict[str, Any] | None = None,
        *,
        properties: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Create a field in the table.

        Args:
            label: Non-empty field label.
            field_type: Non-empty Quickbase field type name.
            options: Additional top-level Quickbase field options. Put
                type-specific settings in a nested ``properties`` dictionary.
                ``description`` is an alias for ``fieldHelp``.
            properties: Legacy keyword alias for ``options``. Do not supply both.

        Returns:
            The created field payload returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the parent application ID is unknown
                or the field options are invalid.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id("StructureTable.create_field")
        payload: Dict[str, Any] = {
            "label": label,
            "fieldType": field_type,
        }
        payload.update(normalize_field_payload(options, properties=properties))
        validate_field_definition(payload)

        response = self.api_client.request(
            method="POST",
            endpoint=f"/fields?tableId={self._require_table_id()}",
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
        endpoint = f"/fields?tableId={self._require_table_id()}"
        if include_field_perms:
            endpoint += "&includeFieldPerms=true"
        response = self.api_client.request(
            method="GET",
            endpoint=endpoint,
        )
        return response.json()

    def get_fields_usage(
        self,
        skip: int | None = None,
        top: int | None = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve a page of field usage details for the table.

        Args:
            skip: Number of fields to skip. Must be a non-negative integer.
            top: Maximum number of fields to return. Must be a positive integer.

        Returns:
            The list of field usage details returned by Quickbase.

        Raises:
            QuickbaseValidationError: If a pagination value is invalid.
            QuickbaseError: If the Quickbase request fails.
        """
        endpoint = f"/fields/usage?tableId={self._require_table_id()}"
        for parameter, value, minimum in (("skip", skip, 0), ("top", top, 1)):
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise QuickbaseValidationError(
                    format_error_message(
                        f"{parameter} must be an integer greater than or equal to {minimum}.",
                        operation="StructureTable.get_fields_usage",
                        table_id=self._id,
                        table_name=self._name,
                    )
                )
            endpoint += f"&{parameter}={value}"
        response = self.api_client.request(method="GET", endpoint=endpoint)
        return response.json()

    def update_field(
        self,
        field_id: int | str,
        options: Dict[str, Any] | None = None,
        *,
        properties: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Update a field in the table.

        Args:
            field_id: Positive Quickbase field ID or numeric string.
            options: Top-level field options to update. Put type-specific
                settings in a nested ``properties`` dictionary. ``description``
                is an alias for ``fieldHelp``.
            properties: Legacy keyword alias for ``options``. Do not supply both.

        Returns:
            The updated field payload returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the parent application ID is unknown,
                the field ID is invalid, or the field options are missing or invalid.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id("StructureTable.update_field")
        normalized_id = validate_field_id(field_id)
        response = self.api_client.request(
            method="POST",
            endpoint=f"/fields/{normalized_id}?tableId={self._require_table_id()}",
            payload=normalize_field_payload(options, properties=properties, required=True),
            app_id_for_backup=app_id,
        )
        return response.json()

    def update_field_xml(
        self,
        field_id: int | str,
        options: Dict[str, Any],
        *,
        app_token: str | None = None,
    ) -> Dict[str, str]:
        """Update field settings through the Quickbase XML API.

        Args:
            field_id: Positive ID of the field to update.
            options: Field settings with the documented XML tag names.
            app_token: Application token, if the application requires one.

        Returns:
            The successful XML response as a dictionary of text values.

        Raises:
            QuickbaseValidationError: If the field ID or options are invalid,
                or the parent application ID is unknown.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        self._require_app_id("StructureTable.update_field_xml")
        return self.field(field_id).update_xml(options, app_token=app_token)

    def delete_fields(self, field_ids: List[int | str]) -> Dict[str, Any]:
        """Delete one or more fields from the table.

        Args:
            field_ids: List of positive field IDs or numeric strings to delete.

        Returns:
            The deletion response returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the parent application ID is unknown,
                the IDs are not a list, or any field ID is invalid.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id("StructureTable.delete_fields")
        if not isinstance(field_ids, list):
            raise QuickbaseValidationError(
                format_error_message(
                    "field_ids must be a list of positive field IDs.",
                    operation="StructureTable.delete_fields",
                    table_id=self._id,
                )
            )
        payload = {"fieldIds": [validate_field_id(fid) for fid in field_ids]}
        response = self.api_client.request(
            method="DELETE",
            endpoint=f"/fields?tableId={self._require_table_id()}",
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
        endpoint = f"/tables/{self._require_table_id()}/relationships"
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
            endpoint=f"/tables/{self._require_table_id()}/relationship",
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
            endpoint=f"/tables/{self._require_table_id()}/relationship/{relationship_id}",
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
            endpoint=f"/tables/{self._require_table_id()}/relationship/{relationship_id}",
            app_id_for_backup=app_id,
        )
        return response.json()
