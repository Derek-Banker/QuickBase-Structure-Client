from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from quickbase_structure_client.exceptions import QuickbaseValidationError, format_error_message

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient

logger = logging.getLogger(__name__)


class TrusteesManager:
    """Manager for Quickbase app trustees, roles, users, and groups."""

    def __init__(self, api_client: QuickBaseStructureClient):
        self.api_client = api_client

    @staticmethod
    def _require_app_id(app_id: str, operation: str) -> str:
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
        """Get trustees for the application via GET /v1/app/{appId}/trustees."""
        app_id = self._require_app_id(app_id, "TrusteesManager.get_trustees")
        response = self.api_client.request(
            method="GET",
            endpoint=f"/app/{app_id}/trustees",
        )
        return response.json()

    def add_trustees(self, app_id: str, trustees: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add trustees via POST /v1/app/{appId}/trustees."""
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
        """Update trustees via PATCH /v1/app/{appId}/trustees."""
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
        """Remove trustees via DELETE /v1/app/{appId}/trustees."""
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
