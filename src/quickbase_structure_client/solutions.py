"""Quickbase Solutions API operations and QBL export helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from quickbase_structure_client.exceptions import QuickbaseValidationError, format_error_message

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient

logger = logging.getLogger(__name__)


class SolutionsManager:
    """Manage Quickbase Solutions and QBL documents.

    Attributes:
        api_client: Client used to execute Quickbase API requests.
    """

    def __init__(self, api_client: QuickBaseStructureClient) -> None:
        """Initialize the solutions manager.

        Args:
            api_client: Client used to execute API requests.
        """
        self.api_client = api_client

    def export_solution(self, solution_id: str, qbl_version: str | None = None) -> str:
        """Export a solution's schema as QBL text.

        Args:
            solution_id: Quickbase solution ID.
            qbl_version: Optional QBL version to request.

        Returns:
            The solution schema as QBL text.

        Raises:
            QuickbaseValidationError: If ``solution_id`` is empty.
            QuickbaseError: If the Quickbase request fails.
        """
        if not solution_id:
            raise QuickbaseValidationError(
                format_error_message(
                    "solution_id is required to export a solution.",
                    operation="SolutionsManager.export_solution",
                )
            )

        headers: Dict[str, str] = {}
        if qbl_version:
            headers["QBL-Version"] = qbl_version

        # Solutions endpoints typically return QBL text (often yaml format)
        response = self.api_client.request(
            method="GET",
            endpoint=f"/solutions/{solution_id}",
            headers=headers or None,
        )
        return response.text

    def create_solution(
        self,
        qbl: str,
        *,
        errors_as_success: bool = False,
    ) -> Dict[str, Any]:
        """Create a Quickbase solution from a QBL document.

        Args:
            qbl: Non-empty QBL document.
            errors_as_success: Whether QBL processing errors should be returned
                as successful HTTP responses.

        Returns:
            The solution creation response returned by Quickbase.

        Raises:
            QuickbaseValidationError: If ``qbl`` is not a non-empty string.
            QuickbaseError: If the Quickbase request fails.
        """
        if not isinstance(qbl, str) or not qbl.strip():
            raise QuickbaseValidationError(
                format_error_message(
                    "A non-empty QBL document is required to create a solution.",
                    operation="SolutionsManager.create_solution",
                )
            )

        headers = {"Content-Type": "application/x-yaml"}
        if errors_as_success:
            headers["X-QBL-Errors-As-Success"] = "true"

        response = self.api_client.request(
            method="POST",
            endpoint="/solutions",
            payload=qbl,
            headers=headers,
        )
        return response.json()

    def export_solution_to_record(
        self,
        solution_id: str,
        table_id: str,
        field_id: int | str,
        record_id: int | str | None = None,
        qbl_version: str | None = None,
    ) -> Dict[str, Any]:
        """Export a solution's QBL schema to a file attachment field.

        Args:
            solution_id: Quickbase solution ID.
            table_id: Destination table ID.
            field_id: Destination file attachment field ID.
            record_id: Existing destination record ID. Quickbase creates a
                record when this value is omitted.
            qbl_version: Optional QBL version to request.

        Returns:
            The export response returned by Quickbase.

        Raises:
            QuickbaseValidationError: If the solution, table, or field ID is
                missing.
            QuickbaseError: If the Quickbase request fails.
        """
        if not solution_id or not table_id or not field_id:
            raise QuickbaseValidationError(
                format_error_message(
                    "solution_id, table_id, and field_id are required.",
                    operation="SolutionsManager.export_solution_to_record",
                    solution_id=solution_id,
                    table_id=table_id,
                    field_id=field_id,
                )
            )

        endpoint = f"/solutions/{solution_id}/torecord?tableId={table_id}&fieldId={field_id}"
        if record_id is not None:
            endpoint += f"&recordId={record_id}"
        headers: Dict[str, str] = {}
        if qbl_version:
            headers["QBL-Version"] = qbl_version

        response = self.api_client.request(
            method="GET",
            endpoint=endpoint,
            headers=headers or None,
        )
        return response.json()

    def export_solution_to_file(
        self,
        solution_id: str,
        filepath: str | Path,
        qbl_version: str | None = None,
    ) -> Path:
        """Download a solution's QBL schema to a local file.

        Args:
            solution_id: Quickbase solution ID.
            filepath: Destination file path.
            qbl_version: Optional QBL version to request.

        Returns:
            The path of the written QBL file.

        Raises:
            QuickbaseValidationError: If ``solution_id`` is empty.
            QuickbaseError: If the Quickbase request fails.
            OSError: If the destination directory or file cannot be written.
        """
        qbl_content = self.export_solution(solution_id, qbl_version=qbl_version)
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(qbl_content, encoding="utf-8")
        return path
