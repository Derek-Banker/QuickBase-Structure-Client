from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict

from quickbase_structure_client.exceptions import QuickbaseValidationError, format_error_message

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient

logger = logging.getLogger(__name__)


class StructureRelationship:
    """Ref-like wrapper representing a Quickbase table-to-table relationship."""

    def __init__(
        self,
        api_client: QuickBaseStructureClient,
        child_table_id: str,
        relationship_id: int | str | None = None,
        *,
        app_id: str | None = None,
    ):
        self.api_client = api_client
        self._child_table_id = child_table_id
        self._relationship_id = relationship_id
        self._app_id = app_id

    @property
    def child_table_id(self) -> str:
        return self._child_table_id

    @property
    def id(self) -> int | str | None:
        return self._relationship_id

    @property
    def app_id(self) -> str | None:
        return self._app_id

    def _require_id(self, operation: str) -> int | str:
        if self._relationship_id is None:
            raise QuickbaseValidationError(
                format_error_message(
                    "This operation requires a resolved relationship ID.",
                    operation=operation,
                    child_table_id=self._child_table_id,
                )
            )
        return self._relationship_id

    def _backup_app_id(self, operation: str) -> str | None:
        if self.api_client.auto_backup and not self._app_id:
            raise QuickbaseValidationError(
                format_error_message(
                    "Mutating relationship operations require app_id when auto_backup is enabled.",
                    operation=operation,
                    child_table_id=self._child_table_id,
                    relationship_id=self._relationship_id,
                )
            )
        return self._app_id

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a relationship via POST /v1/tables/{childTableId}/relationship."""
        response = self.api_client.request(
            method="POST",
            endpoint=f"/tables/{self._child_table_id}/relationship",
            payload=payload,
            app_id_for_backup=self._backup_app_id("StructureRelationship.create"),
        )
        data = response.json()
        self._relationship_id = data.get("id", self._relationship_id)
        return data

    def update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update a relationship via POST /v1/tables/{childTableId}/relationship/{id}."""
        relationship_id = self._require_id("StructureRelationship.update")
        response = self.api_client.request(
            method="POST",
            endpoint=f"/tables/{self._child_table_id}/relationship/{relationship_id}",
            payload=payload,
            app_id_for_backup=self._backup_app_id("StructureRelationship.update"),
        )
        return response.json()

    def delete(self) -> Dict[str, Any]:
        """Delete a relationship via DELETE /v1/tables/{childTableId}/relationship/{id}."""
        relationship_id = self._require_id("StructureRelationship.delete")
        response = self.api_client.request(
            method="DELETE",
            endpoint=f"/tables/{self._child_table_id}/relationship/{relationship_id}",
            app_id_for_backup=self._backup_app_id("StructureRelationship.delete"),
        )
        self._relationship_id = None
        return response.json()
