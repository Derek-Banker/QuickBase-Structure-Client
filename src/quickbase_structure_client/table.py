from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from quickbase_structure_client.exceptions import QuickbaseValidationError, format_error_message

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient

logger = logging.getLogger(__name__)


class StructureTable:
    """Ref-like wrapper representing a Quickbase table structure."""

    def __init__(
        self,
        api_client: QuickBaseStructureClient,
        id: str,
        app_id: str | None = None,
        name: str | None = None,
    ):
        self.api_client = api_client
        self._id = id
        self._app_id = app_id
        self._name = name

    @property
    def id(self) -> str:
        return self._id

    @property
    def app_id(self) -> str | None:
        return self._app_id

    @property
    def name(self) -> str | None:
        return self._name

    def _require_app_id(self, operation: str) -> str:
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
        """Retrieve table properties via GET /v1/tables/{tableId}?appId={appId}."""
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
        """Update table properties via POST /v1/tables/{tableId}?appId={appId}."""
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
        """Delete this table via DELETE /v1/tables/{tableId}?appId={appId}."""
        app_id = self._require_app_id("StructureTable.delete")
        self.api_client.request(
            method="DELETE",
            endpoint=f"/tables/{self._id}?appId={app_id}",
            app_id_for_backup=app_id,
        )

    # FIELD MANAGEMENT
    def field(self, id: int | str, label: str | None = None):
        """Return a StructureField wrapper referencing a field in this table."""
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
        """Create a field via POST /v1/fields?tableId={tableId}."""
        app_id = self._require_app_id("StructureTable.create_field")
        payload: Dict[str, Any] = {
            "label": label,
            "fieldType": field_type,
        }
        if properties:
            payload.update(properties)

        response = self.api_client.request(
            method="POST",
            endpoint=f"/fields?tableId={self._id}",
            payload=payload,
            app_id_for_backup=app_id,
        )
        return response.json()

    def list_fields(self, include_field_perms: bool = False) -> List[Dict[str, Any]]:
        """List fields in this table via GET /v1/fields?tableId={tableId}."""
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
        """Update field properties, including formulas, via POST /v1/fields/{fieldId}."""
        app_id = self._require_app_id("StructureTable.update_field")
        response = self.api_client.request(
            method="POST",
            endpoint=f"/fields/{field_id}?tableId={self._id}",
            payload=properties,
            app_id_for_backup=app_id,
        )
        return response.json()

    def delete_fields(self, field_ids: List[int | str]) -> List[int]:
        """Delete field(s) via DELETE /v1/fields?tableId={tableId} with list of field IDs."""
        app_id = self._require_app_id("StructureTable.delete_fields")
        payload = [int(fid) for fid in field_ids]
        response = self.api_client.request(
            method="DELETE",
            endpoint=f"/fields?tableId={self._id}",
            payload=payload,
            app_id_for_backup=app_id,
        )
        return response.json()

    # RELATIONSHIP MANAGEMENT
    def relationship(self, id: int | str):
        """Return a StructureRelationship wrapper referencing a relationship on this child table."""
        from quickbase_structure_client.relationship import StructureRelationship

        return StructureRelationship(
            api_client=self.api_client,
            child_table_id=self._id,
            relationship_id=id,
            app_id=self._app_id,
        )

    def list_relationships(self, skip: int | None = None) -> List[Dict[str, Any]]:
        """List relationships for this table via GET /v1/tables/{tableId}/relationships."""
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
        """Create relationship with parent table via POST /v1/tables/{childTableId}/relationship."""
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
        """Update relationship via POST /v1/tables/{childTableId}/relationship/{relationshipId}."""
        app_id = self._require_app_id("StructureTable.update_relationship")
        response = self.api_client.request(
            method="POST",
            endpoint=f"/tables/{self._id}/relationship/{relationship_id}",
            payload=payload,
            app_id_for_backup=app_id,
        )
        return response.json()

    def delete_relationship(self, relationship_id: int | str) -> Dict[str, Any]:
        """Delete relationship via DELETE /v1/tables/{childTableId}/relationship/{id}."""
        app_id = self._require_app_id("StructureTable.delete_relationship")
        response = self.api_client.request(
            method="DELETE",
            endpoint=f"/tables/{self._id}/relationship/{relationship_id}",
            app_id_for_backup=app_id,
        )
        return response.json()
