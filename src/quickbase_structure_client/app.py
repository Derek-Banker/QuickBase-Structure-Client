from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from quickbase_structure_client.exceptions import QuickbaseValidationError, format_error_message

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient
    from quickbase_structure_client.table import StructureTable

logger = logging.getLogger(__name__)


class StructureApp:
    """Ref-like wrapper representing a Quickbase application structure."""

    def __init__(
        self,
        api_client: QuickBaseStructureClient,
        id: str | None = None,
        name: str | None = None,
    ):
        self.api_client = api_client
        self._id = id
        self._name = name

    @property
    def id(self) -> str | None:
        return self._id

    @property
    def name(self) -> str | None:
        return self._name

    def _require_id(self, operation: str) -> str:
        if not self._id:
            raise QuickbaseValidationError(
                format_error_message(
                    "This operation requires a resolved application ID.",
                    operation=operation,
                    app_name=self._name,
                )
            )
        return self._id

    def get_details(self) -> Dict[str, Any]:
        """Retrieve application properties via GET /v1/apps/{appId}."""
        app_id = self._require_id("StructureApp.get_details")
        response = self.api_client.request(
            method="GET",
            endpoint=f"/apps/{app_id}",
        )
        data = response.json()
        if "name" in data and not self._name:
            self._name = data["name"]
        return data

    def create(
        self,
        name: str,
        description: str | None = None,
        *,
        assign_token: bool = False,
    ) -> StructureApp:
        """Create a new application via POST /v1/apps."""
        payload: Dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        if assign_token:
            payload["assignToken"] = True

        response = self.api_client.request(
            method="POST",
            endpoint="/apps",
            payload=payload,
        )
        data = response.json()
        self._id = data.get("id")
        self._name = name
        return self

    def update(
        self,
        name: str | None = None,
        description: str | None = None,
        variables: List[Dict[str, Any]] | None = None,
        properties: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Update application properties via POST /v1/apps/{appId}."""
        app_id = self._require_id("StructureApp.update")
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if variables is not None:
            payload["variables"] = variables
        if properties:
            payload.update(properties)

        response = self.api_client.request(
            method="POST",
            endpoint=f"/apps/{app_id}",
            payload=payload,
            app_id_for_backup=app_id,
        )
        if name is not None:
            self._name = name
        return response.json()

    def copy(
        self,
        target_name: str,
        description: str | None = None,
        exclude_files: bool = True,
        keep_data: bool = False,
        users_and_roles: bool = True,
        assign_user_token: bool = False,
    ) -> StructureApp:
        """Copy/Clone the application via POST /v1/apps/{appId}/copy."""
        app_id = self._require_id("StructureApp.copy")
        payload: Dict[str, Any] = {
            "name": target_name,
            "properties": {
                "excludeFiles": exclude_files,
                "keepData": keep_data,
                "usersAndRoles": users_and_roles,
                "assignUserToken": assign_user_token,
            },
        }
        if description is not None:
            payload["description"] = description

        response = self.api_client.request(
            method="POST",
            endpoint=f"/apps/{app_id}/copy",
            payload=payload,
            app_id_for_backup=app_id,
        )
        data = response.json()
        return StructureApp(
            api_client=self.api_client,
            id=data.get("id"),
            name=target_name,
        )

    def delete(self, confirm_name: str | None = None) -> None:
        """Delete the application via DELETE /v1/apps/{appId}."""
        app_id = self._require_id("StructureApp.delete")
        app_name = confirm_name or self._name
        if not app_name:
            raise QuickbaseValidationError(
                format_error_message(
                    "Application deletion requires the application name for confirmation.",
                    operation="StructureApp.delete",
                    app_id=app_id,
                )
            )
        self.api_client.request(
            method="DELETE",
            endpoint=f"/apps/{app_id}",
            payload={"name": app_name},
            app_id_for_backup=app_id,
        )
        self._id = None

    def create_table(
        self,
        name: str,
        plural_name: str | None = None,
        single_record_name: str | None = None,
        description: str | None = None,
    ) -> StructureTable:
        """Create a new table in this app via POST /v1/tables."""
        app_id = self._require_id("StructureApp.create_table")
        from quickbase_structure_client.table import StructureTable

        payload: Dict[str, Any] = {
            "name": name,
        }
        if plural_name is not None:
            payload["pluralRecordName"] = plural_name
        if single_record_name is not None:
            payload["singleRecordName"] = single_record_name
        if description:
            payload["description"] = description

        response = self.api_client.request(
            method="POST",
            endpoint=f"/tables?appId={app_id}",
            payload=payload,
            app_id_for_backup=app_id,
        )
        data = response.json()
        return StructureTable(
            api_client=self.api_client,
            id=data.get("id"),
            app_id=app_id,
            name=name,
        )

    def list_tables(self) -> List[Dict[str, Any]]:
        """List all tables in this app via GET /v1/tables?appId={appId}."""
        app_id = self._require_id("StructureApp.list_tables")
        response = self.api_client.request(
            method="GET",
            endpoint=f"/tables?appId={app_id}",
        )
        return response.json()

    def table(self, id: str, name: str | None = None) -> StructureTable:
        """Return a StructureTable wrapper referencing a table in this app."""
        from quickbase_structure_client.table import StructureTable
        return StructureTable(
            api_client=self.api_client,
            id=id,
            app_id=self._id,
            name=name,
        )

    # TRUSTEE MANAGEMENT
    def get_trustees(self) -> Dict[str, Any]:
        """Get trustees for the application via GET /v1/apps/{appId}/trustees."""
        app_id = self._require_id("StructureApp.get_trustees")
        from quickbase_structure_client.trustees import TrusteesManager

        return TrusteesManager(self.api_client).get_trustees(app_id)

    def add_trustees(self, trustees: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add trustees to the application via POST /v1/apps/{appId}/trustees."""
        app_id = self._require_id("StructureApp.add_trustees")
        from quickbase_structure_client.trustees import TrusteesManager

        return TrusteesManager(self.api_client).add_trustees(app_id, trustees)

    def update_trustees(self, trustees: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update trustees of the application via POST /v1/apps/{appId}/trustees."""
        app_id = self._require_id("StructureApp.update_trustees")
        from quickbase_structure_client.trustees import TrusteesManager

        return TrusteesManager(self.api_client).update_trustees(app_id, trustees)

    def remove_trustees(self, trustees: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Remove trustees from the application via DELETE /v1/apps/{appId}/trustees."""
        app_id = self._require_id("StructureApp.remove_trustees")
        from quickbase_structure_client.trustees import TrusteesManager

        return TrusteesManager(self.api_client).remove_trustees(app_id, trustees)

    # ROLE MANAGEMENT
    def get_roles(self) -> Dict[str, Any]:
        """Get application roles via GET /v1/apps/{appId}/roles."""
        app_id = self._require_id("StructureApp.get_roles")
        response = self.api_client.request(
            method="GET",
            endpoint=f"/apps/{app_id}/roles",
        )
        return response.json()
