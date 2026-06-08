"""Automatic backup orchestration for structural Quickbase changes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

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

    def trigger_pre_backup(self, app_id: str) -> Dict[str, Any] | None:
        """Create a snapshot before a mutating operation.

        Depending on client configuration, the snapshot is a QBL schema export,
        an application clone, or a clone fallback after schema export failure.

        Args:
            app_id: Application ID to back up.

        Returns:
            Backup state to pass to :meth:`trigger_post_backup`, or ``None``
            when automatic backup is disabled or ``app_id`` is empty.

        Raises:
            QuickbaseValidationError: If schema backup requires a solution ID
                and clone fallback is disabled.
            QuickbaseBackupError: If the configured backup cannot be created.
        """
        if not self.api_client.auto_backup:
            return None

        if not app_id:
            logger.warning(
                "Auto-backup is enabled, but no app_id was provided to trigger_pre_backup."
            )
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        state: Dict[str, Any] = {
            "app_id": app_id,
            "timestamp": timestamp,
            "backup_method": self.api_client.backup_method,
            "fell_back_to_clone": False,
        }

        if self.api_client.backup_method == "schema":
            if not self.api_client.backup_solution_id:
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
                    solution_id = self.api_client.backup_solution_id
                    if solution_id is None:
                        raise QuickbaseValidationError(
                            "backup_solution_id unexpectedly missing after validation."
                        )
                    qbl_content = self.api_client.solutions.export_solution(
                        solution_id
                    )
                    backup_dir = Path(self.api_client.backup_dir)
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    filepath = backup_dir / f"{app_id}_pre_{timestamp}.qbl"
                    filepath.write_text(qbl_content, encoding="utf-8")
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
                        solution_id = self.api_client.backup_solution_id
                        raise QuickbaseBackupError(
                            f"Pre-change QBL backup failed for solution {solution_id}."
                        ) from exc

        if self.api_client.backup_method == "clone" or state["fell_back_to_clone"]:
            try:
                logger.info("Executing pre-change App Cloning for app %s...", app_id)
                with self.api_client.suppress_auto_backup():
                    source_app = self.api_client.app(id=app_id)
                    backup_app = source_app.copy(
                        target_name=f"Backup_Pre_{app_id}_{timestamp}",
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
            QuickbaseBackupError: If the configured backup cannot be created.
        """
        if not state:
            return

        app_id = state["app_id"]
        timestamp = state["timestamp"]
        method = state["backup_method"]
        fell_back_to_clone = state["fell_back_to_clone"]

        if method == "schema" and not fell_back_to_clone:
            try:
                logger.info("Executing post-change QBL schema export for app %s...", app_id)
                solution_id = self.api_client.backup_solution_id
                if solution_id is None:
                    raise QuickbaseValidationError(
                        "backup_solution_id unexpectedly missing after validation."
                    )
                qbl_content = self.api_client.solutions.export_solution(solution_id)
                backup_dir = Path(self.api_client.backup_dir)
                backup_dir.mkdir(parents=True, exist_ok=True)
                filepath = backup_dir / f"{app_id}_post_{timestamp}.qbl"
                filepath.write_text(qbl_content, encoding="utf-8")
                logger.info("Post-change QBL schema export saved to %s", filepath)
            except Exception as exc:
                solution_id = self.api_client.backup_solution_id
                raise QuickbaseBackupError(
                    f"Post-change QBL backup failed for solution {solution_id}."
                ) from exc

        if method == "clone" or fell_back_to_clone:
            try:
                logger.info("Executing post-change App Cloning for app %s...", app_id)
                with self.api_client.suppress_auto_backup():
                    source_app = self.api_client.app(id=app_id)
                    backup_app = source_app.copy(
                        target_name=f"Backup_Post_{app_id}_{timestamp}",
                        exclude_files=True,
                        keep_data=False,
                    )
                logger.info("Post-change App Clone successfully created with ID: %s", backup_app.id)
            except Exception as exc:
                raise QuickbaseBackupError(
                    f"Post-change App Cloning failed for application {app_id}."
                ) from exc
