from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from quickbase_structure_client.exceptions import QuickbaseValidationError, format_error_message

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient

logger = logging.getLogger(__name__)


class SolutionsManager:
    """Manager for the Quickbase Solutions (ALM / QBL) API endpoints."""

    def __init__(self, api_client: QuickBaseStructureClient):
        self.api_client = api_client

    def export_solution(self, solution_id: str, qbl_version: str | None = None) -> str:
        """
        Export a solution's schema as QBL text.
        GET /v1/solutions/{solutionId}
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
        """
        Create a Quickbase solution from a QBL document.
        POST /v1/solutions
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
        """
        Export a solution's QBL schema directly into a file attachment field of a table.
        GET /v1/solutions/{solutionId}/torecord?tableId={tableId}&fieldId={fieldId}
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
        """Helper to download a solution's QBL schema and save it to a local file."""
        qbl_content = self.export_solution(solution_id, qbl_version=qbl_version)
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(qbl_content, encoding="utf-8")
        return path
