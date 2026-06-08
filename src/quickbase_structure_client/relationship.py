"""Quickbase table relationship structure operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict

from quickbase_structure_client.exceptions import QuickbaseValidationError, format_error_message

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient

logger = logging.getLogger(__name__)


class StructureRelationship:
    """Reference-like wrapper for a Quickbase table relationship.

    Attributes:
        api_client: Client used to execute Quickbase API requests.
    """

    def __init__(
        self,
        api_client: QuickBaseStructureClient,
        child_table_id: str,
        relationship_id: int | str | None = None,
        *,
        app_id: str | None = None,
    ) -> None:
        """Initialize a relationship reference.

        Args:
            api_client: Client used to execute API requests.
            child_table_id: ID of the relationship's child table.
            relationship_id: Quickbase relationship ID, if already known.
            app_id: Parent application ID, when known.
        """
        self.api_client = api_client
        self._child_table_id = child_table_id
        self._relationship_id = relationship_id
        self._app_id = app_id

    @property
    def child_table_id(self) -> str:
        """Return the ID of the relationship's child table."""
        return self._child_table_id

    @property
    def id(self) -> int | str | None:
        """Return the resolved Quickbase relationship ID."""
        return self._relationship_id

    @property
    def app_id(self) -> str | None:
        """Return the known parent application ID."""
        return self._app_id

    def _require_id(self, operation: str) -> int | str:
        """Return the relationship ID or raise a validation error.

        Args:
            operation: Name of the operation requiring a relationship ID.

        Returns:
            The resolved relationship ID.

        Raises:
            QuickbaseValidationError: If this reference has no relationship ID.
        """
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
                    "Mutating relationship operations require app_id when auto_backup is enabled.",
                    operation=operation,
                    child_table_id=self._child_table_id,
                    relationship_id=self._relationship_id,
                )
            )
        return self._app_id

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create the relationship and update this reference.

        Args:
            payload: Relationship definition accepted by Quickbase.

        Returns:
            The created relationship payload returned by Quickbase.

        Raises:
            QuickbaseValidationError: If automatic backup is enabled and the
                parent application ID is unknown.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
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
        """Update the relationship.

        Args:
            payload: Relationship properties to update.

        Returns:
            The updated relationship payload returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the relationship ID is unavailable,
                or if automatic backup requires an unknown application ID.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        relationship_id = self._require_id("StructureRelationship.update")
        response = self.api_client.request(
            method="POST",
            endpoint=f"/tables/{self._child_table_id}/relationship/{relationship_id}",
            payload=payload,
            app_id_for_backup=self._backup_app_id("StructureRelationship.update"),
        )
        return response.json()

    def delete(self) -> Dict[str, Any]:
        """Delete the relationship and clear its ID from this reference.

        Returns:
            The deletion response returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the relationship ID is unavailable,
                or if automatic backup requires an unknown application ID.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        relationship_id = self._require_id("StructureRelationship.delete")
        response = self.api_client.request(
            method="DELETE",
            endpoint=f"/tables/{self._child_table_id}/relationship/{relationship_id}",
            app_id_for_backup=self._backup_app_id("StructureRelationship.delete"),
        )
        self._relationship_id = None
        return response.json()
