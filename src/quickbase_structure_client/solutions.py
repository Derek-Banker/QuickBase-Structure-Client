"""Quickbase Solutions API operations and QBL export helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict
from urllib.parse import quote

from quickbase_structure_client._validation import validate_dbid
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
        if not isinstance(solution_id, str) or not solution_id.strip():
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
            endpoint=f"/solutions/{quote(solution_id, safe='')}",
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

    def update_solution(
        self,
        solution_id: str,
        qbl: str,
        *,
        app_ids_for_backup: list[str] | None = None,
        errors_as_success: bool = False,
    ) -> Dict[str, Any]:
        """Update an existing solution with a complete QBL document.

        Preserve the full exported solution and its logical IDs. Quickbase can
        delete tables and fields omitted from the document, including their data.
        Quickbase validates the QBL. This method does not merge partial documents
        or determine which applications the document affects.
        Schema backups export this target solution, regardless of the client's
        default backup solution. Backups do not preserve records or attachments.

        Args:
            solution_id: Non-empty Quickbase solution ID.
            qbl: Non-empty, complete QBL document for the target solution.
            app_ids_for_backup: IDs of every affected application. Required when
                automatic backups are enabled. Duplicate IDs are removed before
                the request. All pre-change backups run before the update, and
                post-change backups run after a successful request.
            errors_as_success: Whether Quickbase returns QBL processing errors
                as successful HTTP responses. Inspect the result for these errors.

        Returns:
            The solution update response returned by Quickbase.

        Raises:
            QuickbaseValidationError: If an argument is invalid or automatic
                backups are enabled without application IDs.
            QuickbaseError: If the Quickbase request or automatic backup fails.
        """
        operation = "SolutionsManager.update_solution"
        if not isinstance(solution_id, str) or not solution_id.strip():
            raise QuickbaseValidationError(
                format_error_message(
                    "A non-empty solution_id is required to update a solution.",
                    operation=operation,
                )
            )
        if not isinstance(qbl, str) or not qbl.strip():
            raise QuickbaseValidationError(
                format_error_message(
                    "A non-empty QBL document is required to update a solution.",
                    operation=operation,
                )
            )
        if not isinstance(errors_as_success, bool):
            raise QuickbaseValidationError(
                format_error_message(
                    "errors_as_success must be a boolean.",
                    operation=operation,
                )
            )
        backup_args: Dict[str, Any] = {}
        if app_ids_for_backup is not None:
            if not isinstance(app_ids_for_backup, list) or any(
                not isinstance(app_id, str) or not app_id.strip()
                for app_id in app_ids_for_backup
            ):
                raise QuickbaseValidationError(
                    format_error_message(
                        "app_ids_for_backup must be a list of non-empty application IDs.",
                        operation=operation,
                    )
                )
            backup_args["app_ids_for_backup"] = list(
                dict.fromkeys(validate_dbid(app_id) for app_id in app_ids_for_backup)
            )
        if self.api_client.auto_backup and not app_ids_for_backup:
            raise QuickbaseValidationError(
                format_error_message(
                    "Solution updates require app_ids_for_backup when auto_backup is enabled.",
                    operation=operation,
                )
            )

        headers = {"Content-Type": "application/x-yaml"}
        if errors_as_success:
            headers["X-QBL-Errors-As-Success"] = "true"
        response = self.api_client.request(
            method="PUT",
            endpoint=f"/solutions/{quote(solution_id, safe='')}",
            payload=qbl,
            headers=headers,
            solution_id_for_backup=solution_id,
            **backup_args,
        )
        return response.json()

    def preview_solution_changes(
        self,
        solution_id: str,
        qbl: str,
        *,
        errors_as_success: bool = False,
    ) -> Dict[str, Any]:
        """Preview the changes a QBL document would make to a solution.

        This operation does not apply the QBL or create automatic backups.
        Review the returned changes, especially removals, before updating.
        A preview does not lock the solution against subsequent changes.

        Args:
            solution_id: Non-empty Quickbase solution ID or alias.
            qbl: Non-empty, complete QBL document to preview.
            errors_as_success: Whether QBL processing errors are returned in a
                successful HTTP response. Inspect the result for those errors.

        Returns:
            The proposed changes and metadata returned by Quickbase.

        Raises:
            QuickbaseValidationError: If an argument is invalid.
            QuickbaseError: If the Quickbase request fails.
        """
        operation = "SolutionsManager.preview_solution_changes"
        if not isinstance(solution_id, str) or not solution_id.strip():
            raise QuickbaseValidationError(
                format_error_message("A non-empty solution_id is required.", operation=operation)
            )
        if not isinstance(qbl, str) or not qbl.strip():
            raise QuickbaseValidationError(
                format_error_message("A non-empty QBL document is required.", operation=operation)
            )
        if not isinstance(errors_as_success, bool):
            raise QuickbaseValidationError(
                format_error_message("errors_as_success must be a boolean.", operation=operation)
            )
        headers = {"Content-Type": "application/x-yaml"}
        if errors_as_success:
            headers["X-QBL-Errors-As-Success"] = "true"
        response = self.api_client.request(
            method="PUT",
            endpoint=f"/solutions/{quote(solution_id, safe='')}/changeset",
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
