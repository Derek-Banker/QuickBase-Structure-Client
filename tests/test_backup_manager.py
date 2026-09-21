from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest

import quickbase_structure_client.tools.backup_manager as backup_manager_module
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


def test_backup_manager_skips_disabled_backups(tmp_path: Path) -> None:
    disabled_client = FakeBackupClient(tmp_path, auto_backup=False)

    assert BackupManager(cast(Any, disabled_client)).trigger_pre_backup("app1") is None
    assert disabled_client.solutions.exported_solution_ids == []


def test_schema_backup_writes_pre_and_post_qbl_files(tmp_path: Path) -> None:
    client = FakeBackupClient(tmp_path)
    manager = BackupManager(cast(Any, client))

    state = manager.trigger_pre_backup("app1")

    assert state is not None
    pre_file = Path(state["pre_file"])
    assert pre_file.read_text(encoding="utf-8") == "qbl: content"
    assert pre_file.name == f"app1_pre_{state['backup_id']}.qbl"
    assert state["backup_id"].startswith(f"{state['timestamp']}_")
    assert len(state["backup_id"].removeprefix(f"{state['timestamp']}_")) == 16

    manager.trigger_post_backup(state)

    post_file = tmp_path / f"app1_post_{state['backup_id']}.qbl"
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
            "target_name": f"Backup_Pre_app1_{state['backup_id']}",
            "exclude_files": True,
            "keep_data": False,
        },
        {
            "target_name": f"Backup_Post_app1_{state['backup_id']}",
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


def test_same_second_backups_preserve_both_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Mock()
    clock.now.return_value = datetime(2026, 9, 21, 12, 34, 56, tzinfo=timezone.utc)
    monkeypatch.setattr(backup_manager_module, "datetime", clock)
    suffixes = iter(["0123456789abcdef", "fedcba9876543210"])
    monkeypatch.setattr(backup_manager_module.secrets, "token_hex", lambda size: next(suffixes))
    client = FakeBackupClient(tmp_path, solutions=FakeSolutions(content="first state"))
    manager = BackupManager(cast(Any, client))

    first = manager.trigger_pre_backup("app1")
    client.solutions.content = "second state"
    second = manager.trigger_pre_backup("app1")

    assert first is not None and second is not None
    assert first["timestamp"] == second["timestamp"] == "20260921_123456"
    assert first["backup_id"] != second["backup_id"]
    assert Path(first["pre_file"]).read_text(encoding="utf-8") == "first state"
    assert Path(second["pre_file"]).read_text(encoding="utf-8") == "second state"
    assert len(list(tmp_path.glob("*.qbl"))) == 2


def test_forced_suffix_collision_does_not_overwrite_pre_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Mock()
    clock.now.return_value = datetime(2026, 9, 21, 12, 34, 56, tzinfo=timezone.utc)
    monkeypatch.setattr(backup_manager_module, "datetime", clock)
    monkeypatch.setattr(backup_manager_module.secrets, "token_hex", lambda size: "a" * 16)
    client = FakeBackupClient(tmp_path, solutions=FakeSolutions(content="original state"))
    manager = BackupManager(cast(Any, client))
    state = manager.trigger_pre_backup("app1")
    assert state is not None
    client.solutions.content = "replacement state"

    with pytest.raises(QuickbaseBackupError) as captured:
        manager.trigger_pre_backup("app1")

    assert isinstance(captured.value.__cause__, FileExistsError)
    assert Path(state["pre_file"]).read_text(encoding="utf-8") == "original state"
    assert len(list(tmp_path.glob("*.qbl"))) == 1


def test_post_backup_does_not_overwrite_existing_snapshot(tmp_path: Path) -> None:
    client = FakeBackupClient(tmp_path)
    manager = BackupManager(cast(Any, client))
    state = manager.trigger_pre_backup("app1")
    assert state is not None
    manager.trigger_post_backup(state)
    client.solutions.content = "replacement state"

    with pytest.raises(QuickbaseBackupError) as captured:
        manager.trigger_post_backup(state)

    assert isinstance(captured.value.__cause__, FileExistsError)
    post_file = tmp_path / f"app1_post_{state['backup_id']}.qbl"
    assert post_file.read_text(encoding="utf-8") == "qbl: content"


@pytest.mark.parametrize(
    "app_id",
    ["", " ", "../outside", "..\\outside", "C:\\outside", "/outside", "app/1", None, 3],
)
def test_backup_rejects_invalid_dbids_before_effects(tmp_path: Path, app_id: Any) -> None:
    backup_dir = tmp_path / "backups"
    client = FakeBackupClient(backup_dir, backup_fallback_to_clone=True)
    manager = BackupManager(cast(Any, client))

    with pytest.raises(QuickbaseValidationError):
        manager.trigger_pre_backup(app_id)

    assert client.solutions.exported_solution_ids == []
    assert client.requested_app_ids == []
    assert not backup_dir.exists()


def test_backup_rejects_resolved_path_outside_backup_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup_dir = tmp_path / "backups"
    outside = tmp_path / "outside.qbl"
    client = FakeBackupClient(backup_dir)
    manager = BackupManager(cast(Any, client))
    original_resolve = Path.resolve

    def resolve(path: Path, strict: bool = False) -> Path:
        if path.suffix == ".qbl":
            return outside
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve)

    with pytest.raises(QuickbaseBackupError) as captured:
        manager.trigger_pre_backup("app1")

    assert isinstance(captured.value.__cause__, QuickbaseValidationError)
    assert not outside.exists()
    assert not backup_dir.exists()


@pytest.mark.parametrize("solution_id", ["", " ", False, 3])
def test_backup_rejects_invalid_solution_override_before_effects(
    tmp_path: Path, solution_id: Any
) -> None:
    backup_dir = tmp_path / "backups"
    client = FakeBackupClient(backup_dir, backup_fallback_to_clone=True)
    manager = BackupManager(cast(Any, client))

    with pytest.raises(QuickbaseValidationError):
        manager.trigger_pre_backup("app1", solution_id=solution_id)

    assert client.solutions.exported_solution_ids == []
    assert client.requested_app_ids == []
    assert not backup_dir.exists()


@pytest.mark.parametrize("override", [None, "target-solution"])
def test_post_backup_uses_solution_target_captured_before_mutation(
    tmp_path: Path, override: str | None
) -> None:
    client = FakeBackupClient(tmp_path, backup_solution_id="configured-solution")
    manager = BackupManager(cast(Any, client))

    state = manager.trigger_pre_backup("app1", solution_id=override)
    assert state is not None
    client.backup_solution_id = "different-solution"
    manager.trigger_post_backup(state)

    expected_solution = override or "configured-solution"
    assert state["solution_id"] == expected_solution
    assert client.solutions.exported_solution_ids == [expected_solution, expected_solution]


def test_solution_override_avoids_clone_fallback_when_global_target_is_missing(
    tmp_path: Path,
) -> None:
    client = FakeBackupClient(tmp_path, backup_solution_id=None, backup_fallback_to_clone=True)
    manager = BackupManager(cast(Any, client))

    state = manager.trigger_pre_backup("app1", solution_id="target-solution")
    assert state is not None
    manager.trigger_post_backup(state)

    assert state["fell_back_to_clone"] is False
    assert client.solutions.exported_solution_ids == ["target-solution", "target-solution"]
    assert client.requested_app_ids == []


def test_post_backup_rejects_invalid_state_app_id_before_effects(tmp_path: Path) -> None:
    client = FakeBackupClient(tmp_path / "backups")
    manager = BackupManager(cast(Any, client))
    state = {
        "app_id": "../outside",
        "backup_id": "20260921_123456_0123456789abcdef",
        "solution_id": "solution1",
        "backup_method": "schema",
        "fell_back_to_clone": False,
    }

    with pytest.raises(QuickbaseValidationError):
        manager.trigger_post_backup(state)

    assert client.solutions.exported_solution_ids == []
    assert client.requested_app_ids == []
    assert not Path(client.backup_dir).exists()
