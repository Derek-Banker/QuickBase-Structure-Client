from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any, cast

import pytest

from quickbase_structure_client.exceptions import (
    QuickbaseBackupError,
    QuickbaseValidationError,
)
from quickbase_structure_client.tools.backup_manager import BackupManager


class FakeSolutions:
    def __init__(self, content: str = "qbl: content", error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.exported_solution_ids: list[str] = []

    def export_solution(self, solution_id: str) -> str:
        self.exported_solution_ids.append(solution_id)
        if self.error is not None:
            raise self.error
        return self.content


class FakeApp:
    def __init__(self) -> None:
        self.copy_calls: list[dict[str, Any]] = []

    def copy(self, target_name: str, **kwargs: Any) -> Any:
        self.copy_calls.append({"target_name": target_name, **kwargs})
        return type("CopiedApp", (), {"id": "backup-app"})()


class FakeBackupClient:
    def __init__(
        self,
        backup_dir: Path,
        *,
        auto_backup: bool = True,
        backup_method: str = "schema",
        backup_solution_id: str | None = "solution1",
        backup_fallback_to_clone: bool = False,
        solutions: FakeSolutions | None = None,
    ) -> None:
        self.auto_backup = auto_backup
        self.backup_method = backup_method
        self.backup_solution_id = backup_solution_id
        self.backup_dir = str(backup_dir)
        self.backup_fallback_to_clone = backup_fallback_to_clone
        self.solutions = solutions or FakeSolutions()
        self.source_app = FakeApp()
        self.requested_app_ids: list[str] = []

    def suppress_auto_backup(self) -> Any:
        return nullcontext()

    def app(self, *, id: str) -> FakeApp:
        self.requested_app_ids.append(id)
        return self.source_app


def test_backup_manager_skips_disabled_or_unidentified_backups(tmp_path: Path) -> None:
    disabled_client = FakeBackupClient(tmp_path, auto_backup=False)
    enabled_client = FakeBackupClient(tmp_path)

    assert BackupManager(cast(Any, disabled_client)).trigger_pre_backup("app1") is None
    assert BackupManager(cast(Any, enabled_client)).trigger_pre_backup("") is None


def test_schema_backup_writes_pre_and_post_qbl_files(tmp_path: Path) -> None:
    client = FakeBackupClient(tmp_path)
    manager = BackupManager(cast(Any, client))

    state = manager.trigger_pre_backup("app1")

    assert state is not None
    pre_file = Path(state["pre_file"])
    assert pre_file.read_text(encoding="utf-8") == "qbl: content"
    assert pre_file.name == f"app1_pre_{state['timestamp']}.qbl"

    manager.trigger_post_backup(state)

    post_file = tmp_path / f"app1_post_{state['timestamp']}.qbl"
    assert post_file.read_text(encoding="utf-8") == "qbl: content"
    assert client.solutions.exported_solution_ids == ["solution1", "solution1"]


def test_missing_schema_solution_can_fall_back_to_pre_and_post_clones(
    tmp_path: Path,
) -> None:
    client = FakeBackupClient(
        tmp_path,
        backup_solution_id=None,
        backup_fallback_to_clone=True,
    )
    manager = BackupManager(cast(Any, client))

    state = manager.trigger_pre_backup("app1")

    assert state is not None
    assert state["fell_back_to_clone"] is True
    assert state["pre_clone_id"] == "backup-app"

    manager.trigger_post_backup(state)

    assert client.requested_app_ids == ["app1", "app1"]
    assert client.source_app.copy_calls == [
        {
            "target_name": f"Backup_Pre_app1_{state['timestamp']}",
            "exclude_files": True,
            "keep_data": False,
        },
        {
            "target_name": f"Backup_Post_app1_{state['timestamp']}",
            "exclude_files": True,
            "keep_data": False,
        },
    ]


def test_schema_backup_requires_solution_without_clone_fallback(tmp_path: Path) -> None:
    client = FakeBackupClient(tmp_path, backup_solution_id=None)

    with pytest.raises(QuickbaseValidationError, match="backup_solution_id is required"):
        BackupManager(cast(Any, client)).trigger_pre_backup("app1")


def test_schema_export_failure_is_wrapped_as_backup_error(tmp_path: Path) -> None:
    client = FakeBackupClient(
        tmp_path,
        solutions=FakeSolutions(error=RuntimeError("export failed")),
    )

    with pytest.raises(QuickbaseBackupError, match="Pre-change QBL backup failed"):
        BackupManager(cast(Any, client)).trigger_pre_backup("app1")
