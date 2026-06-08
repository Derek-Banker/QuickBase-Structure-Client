"""Quickbase application trustee management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from quickbase_structure_client.exceptions import QuickbaseValidationError, format_error_message

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient

logger = logging.getLogger(__name__)


class TrusteesManager:
    """Manage trustees assigned to Quickbase applications.

    Attributes:
        api_client: Client used to execute Quickbase API requests.
    """

    def __init__(self, api_client: QuickBaseStructureClient) -> None:
        """Initialize the trustee manager.

        Args:
            api_client: Client used to execute API requests.
        """
        self.api_client = api_client

    @staticmethod
    def _require_app_id(app_id: str, operation: str) -> str:
        """Validate and return an application ID.

        Args:
            app_id: Quickbase application ID.
            operation: Name of the trustee operation being performed.

        Returns:
            The validated application ID.

        Raises:
            QuickbaseValidationError: If ``app_id`` is empty.
        """
        if not app_id:
            raise QuickbaseValidationError(
                format_error_message(
                    "app_id is required for trustee operations.",
                    operation=operation,
                )
            )
        return app_id

    @staticmethod
    def _validate_trustees(
        trustees: List[Dict[str, Any]],
        operation: str,
        *,
        required_keys: frozenset[str],
    ) -> List[Dict[str, Any]]:
        """Validate trustee payload shape and required keys.

        Args:
            trustees: Trustee payloads to validate.
            operation: Name of the trustee operation being performed.
            required_keys: Keys required in every trustee payload.

        Returns:
            The validated trustee payload list.

        Raises:
            QuickbaseValidationError: If the list is empty, contains a
                non-dictionary item, or omits required keys.
        """
        if not isinstance(trustees, list) or not trustees:
            raise QuickbaseValidationError(
                format_error_message(
                    "trustees must be a non-empty list of trustee payloads.",
                    operation=operation,
                    trustees=trustees,
                )
            )

        invalid = [trustee for trustee in trustees if not isinstance(trustee, dict)]
        if invalid:
            raise QuickbaseValidationError(
                format_error_message(
                    "Each trustee payload must be a dictionary.",
                    operation=operation,
                    invalid=invalid,
                )
            )

        missing_keys = [
            {
                "index": index,
                "missing": sorted(required_keys.difference(trustee)),
            }
            for index, trustee in enumerate(trustees)
            if required_keys.difference(trustee)
        ]
        if missing_keys:
            raise QuickbaseValidationError(
                format_error_message(
                    "Each trustee payload is missing required fields.",
                    operation=operation,
                    missing=missing_keys,
                )
            )
        return trustees

    def get_trustees(self, app_id: str) -> Dict[str, Any]:
        """Retrieve trustees assigned to an application.

        Args:
            app_id: Quickbase application ID.

        Returns:
            Trustee information returned by Quickbase.

        Raises:
            QuickbaseValidationError: If ``app_id`` is empty.
            QuickbaseError: If the Quickbase request fails.
        """
        app_id = self._require_app_id(app_id, "TrusteesManager.get_trustees")
        response = self.api_client.request(
            method="GET",
            endpoint=f"/app/{app_id}/trustees",
        )
        return response.json()

    def add_trustees(self, app_id: str, trustees: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add trustees to an application.

        Args:
            app_id: Quickbase application ID.
            trustees: Trustee payloads containing ``id``, ``type``, and
                ``roleId`` values.

        Returns:
            The trustee update response returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the application ID or trustee
                payloads are invalid.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id(app_id, "TrusteesManager.add_trustees")
        payload = self._validate_trustees(
            trustees,
            "TrusteesManager.add_trustees",
            required_keys=frozenset({"id", "type", "roleId"}),
        )
        response = self.api_client.request(
            method="POST",
            endpoint=f"/app/{app_id}/trustees",
            payload=payload,
            app_id_for_backup=app_id,
        )
        return response.json()

    def update_trustees(self, app_id: str, trustees: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update trustee role assignments for an application.

        Args:
            app_id: Quickbase application ID.
            trustees: Trustee payloads containing ``id``, ``type``,
                ``roleId``, and ``oldRoleId`` values.

        Returns:
            The trustee update response returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the application ID or trustee
                payloads are invalid.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id(app_id, "TrusteesManager.update_trustees")
        payload = self._validate_trustees(
            trustees,
            "TrusteesManager.update_trustees",
            required_keys=frozenset({"id", "type", "roleId", "oldRoleId"}),
        )
        response = self.api_client.request(
            method="PATCH",
            endpoint=f"/app/{app_id}/trustees",
            payload=payload,
            app_id_for_backup=app_id,
        )
        return response.json()

    def remove_trustees(self, app_id: str, trustees: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Remove trustees from an application.

        Args:
            app_id: Quickbase application ID.
            trustees: Trustee payloads containing ``id``, ``type``, and
                ``roleId`` values.

        Returns:
            The trustee removal response returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the application ID or trustee
                payloads are invalid.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        app_id = self._require_app_id(app_id, "TrusteesManager.remove_trustees")
        payload = self._validate_trustees(
            trustees,
            "TrusteesManager.remove_trustees",
            required_keys=frozenset({"id", "type", "roleId"}),
        )
        response = self.api_client.request(
            method="DELETE",
            endpoint=f"/app/{app_id}/trustees",
            payload=payload,
            app_id_for_backup=app_id,
        )
        return response.json()
