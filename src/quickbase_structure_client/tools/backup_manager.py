"""Automatic backup orchestration for structural Quickbase changes."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Literal

from quickbase_structure_client._validation import validate_dbid
from quickbase_structure_client.exceptions import (
    QuickbaseBackupError,
    QuickbaseValidationError,
    format_error_message,
)

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient

logger = logging.getLogger(__name__)


class BackupManager:
    """Create pre-change and post-change backups for structural mutations.

    Attributes:
        api_client: Client whose backup configuration and API access are used.
    """

    def __init__(self, api_client: QuickBaseStructureClient) -> None:
        """Initialize the backup manager.

        Args:
            api_client: Configured Quickbase structure client.
        """
        self.api_client = api_client

    def _write_schema_backup(
        self,
        app_id: str,
        stage: Literal["pre", "post"],
        backup_id: str,
        qbl_content: str,
    ) -> Path:
        """Write a new QBL snapshot within the resolved backup directory.

        Args:
            app_id: Validated application ID used in the filename.
            stage: Whether the snapshot precedes or follows the mutation.
            backup_id: Timestamp and random suffix shared by a backup pair.
            qbl_content: Complete solution export to write as UTF-8.

        Returns:
            The absolute path to the new snapshot.

        Raises:
            QuickbaseValidationError: If the resolved path escapes the backup
                directory.
            OSError: If the file already exists or the write fails.
        """
        backup_dir = Path(self.api_client.backup_dir).resolve()
        filepath = (backup_dir / f"{app_id}_{stage}_{backup_id}.qbl").resolve()
        if not filepath.is_relative_to(backup_dir):
            raise QuickbaseValidationError(
                "The resolved snapshot path must remain within the backup directory."
            )
        backup_dir.mkdir(parents=True, exist_ok=True)
        with filepath.open("x", encoding="utf-8") as snapshot:
            snapshot.write(qbl_content)
        return filepath

    def trigger_pre_backup(
        self, app_id: str, *, solution_id: str | None = None
    ) -> Dict[str, Any] | None:
        """Create a snapshot before a mutating operation.

        Depending on client configuration, the snapshot is a QBL schema export,
        an application clone, or a clone fallback after schema export failure.

        Args:
            app_id: Application ID to back up.
            solution_id: Optional solution ID for this backup pair. Overrides
                the configured solution ID for schema exports.

        Returns:
            Backup state to pass to :meth:`trigger_post_backup`, or ``None``
            when automatic backup is disabled. The state preserves the plain
            UTC ``timestamp``, the unique ``backup_id``, and the ``solution_id``.

        Raises:
            QuickbaseValidationError: If an ID is invalid, or schema backup
                requires a solution ID and clone fallback is disabled.
            QuickbaseBackupError: If the configured backup cannot be created.
        """
        app_id = validate_dbid(app_id, argument_name="app_id")
        if solution_id is not None and (
            not isinstance(solution_id, str) or not solution_id.strip()
        ):
            raise QuickbaseValidationError(
                "solution_id must be a non-empty string when supplied for a backup."
            )
        if not self.api_client.auto_backup:
            return None

        resolved_solution_id = (
            solution_id if solution_id is not None else self.api_client.backup_solution_id
        )
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_id = f"{timestamp}_{secrets.token_hex(8)}"
        state: Dict[str, Any] = {
            "app_id": app_id,
            "timestamp": timestamp,
            "backup_id": backup_id,
            "solution_id": resolved_solution_id,
            "backup_method": self.api_client.backup_method,
            "fell_back_to_clone": False,
        }

        if self.api_client.backup_method == "schema":
            if not resolved_solution_id:
                if self.api_client.backup_fallback_to_clone:
                    logger.warning(
                        "auto_backup=True and backup_method='schema', but "
                        "backup_solution_id is not set. "
                        "Falling back to App Cloning."
                    )
                    state["fell_back_to_clone"] = True
                else:
                    raise QuickbaseValidationError(
                        format_error_message(
                            (
                                "backup_solution_id is required when backup_method='schema' "
                                "and fallback_to_clone is False."
                            ),
                            operation="BackupManager.trigger_pre_backup",
                            app_id=app_id,
                        )
                    )
            else:
                try:
                    logger.info("Executing pre-change QBL schema export for app %s...", app_id)
                    qbl_content = self.api_client.solutions.export_solution(
                        resolved_solution_id
                    )
                    filepath = self._write_schema_backup(app_id, "pre", backup_id, qbl_content)
                    state["pre_file"] = str(filepath)
                    logger.info("Pre-change QBL schema export saved to %s", filepath)
                except Exception as exc:
                    if self.api_client.backup_fallback_to_clone:
                        logger.warning(
                            "QBL schema export failed. Falling back to App Cloning. Error: %s",
                            exc,
                        )
                        state["fell_back_to_clone"] = True
                    else:
                        raise QuickbaseBackupError(
                            f"Pre-change QBL backup failed for solution {resolved_solution_id}."
                        ) from exc

        if self.api_client.backup_method == "clone" or state["fell_back_to_clone"]:
            try:
                logger.info("Executing pre-change App Cloning for app %s...", app_id)
                with self.api_client.suppress_auto_backup():
                    source_app = self.api_client.app(id=app_id)
                    backup_app = source_app.copy(
                        target_name=f"Backup_Pre_{app_id}_{backup_id}",
                        exclude_files=True,
                        keep_data=False,
                    )
                state["pre_clone_id"] = backup_app.id
                logger.info("Pre-change App Clone successfully created with ID: %s", backup_app.id)
            except Exception as exc:
                raise QuickbaseBackupError(
                    f"Pre-change App Cloning failed for application {app_id}."
                ) from exc

        return state

    def trigger_post_backup(self, state: Dict[str, Any] | None) -> None:
        """Create a snapshot after a successful mutating operation.

        Args:
            state: State returned by :meth:`trigger_pre_backup`. ``None`` is
                accepted and causes no action.

        Raises:
            KeyError: If the supplied backup state is incomplete.
            QuickbaseValidationError: If the application ID in the state is invalid.
            QuickbaseBackupError: If the configured backup cannot be created.
        """
        if not state:
            return

        app_id = validate_dbid(state["app_id"], argument_name="app_id")
        backup_id = state["backup_id"]
        solution_id = state["solution_id"]
        method = state["backup_method"]
        fell_back_to_clone = state["fell_back_to_clone"]

        if method == "schema" and not fell_back_to_clone:
            try:
                logger.info("Executing post-change QBL schema export for app %s...", app_id)
                if solution_id is None:
                    raise QuickbaseValidationError(
                        "The backup state has no solution_id for its schema export."
                    )
                qbl_content = self.api_client.solutions.export_solution(solution_id)
                filepath = self._write_schema_backup(app_id, "post", backup_id, qbl_content)
                logger.info("Post-change QBL schema export saved to %s", filepath)
            except Exception as exc:
                raise QuickbaseBackupError(
                    f"Post-change QBL backup failed for solution {solution_id}."
                ) from exc

        if method == "clone" or fell_back_to_clone:
            try:
                logger.info("Executing post-change App Cloning for app %s...", app_id)
                with self.api_client.suppress_auto_backup():
                    source_app = self.api_client.app(id=app_id)
                    backup_app = source_app.copy(
                        target_name=f"Backup_Post_{app_id}_{backup_id}",
                        exclude_files=True,
                        keep_data=False,
                    )
                logger.info("Post-change App Clone successfully created with ID: %s", backup_app.id)
            except Exception as exc:
                raise QuickbaseBackupError(
                    f"Post-change App Cloning failed for application {app_id}."
                ) from exc
