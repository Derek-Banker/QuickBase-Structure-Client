from __future__ import annotations

from typing import Any, cast

import pytest

from quickbase_structure_client.exceptions import QuickbaseValidationError
from quickbase_structure_client.solutions import SolutionsManager

from .conftest import FakeResponse, RecordingClient


def test_update_solution_sends_raw_qbl_and_all_backup_app_ids() -> None:
    result = {"solutionId": "solution1", "warnings": []}
    client = RecordingClient([FakeResponse(result)])
    client.auto_backup = True
    manager = SolutionsManager(cast(Any, client))
    qbl = "Version: 0.12\nResources:\n  $App_Orders: {}\n"
    app_ids = ["app1", "app2", "app1"]

    updated = manager.update_solution(
        "solution1",
        qbl,
        app_ids_for_backup=app_ids,
        errors_as_success=True,
    )

    assert updated == result
    assert app_ids == ["app1", "app2", "app1"]
    assert client.calls == [
        {
            "method": "PUT",
            "endpoint": "/solutions/solution1",
            "payload": qbl,
            "headers": {
                "Content-Type": "application/x-yaml",
                "X-QBL-Errors-As-Success": "true",
            },
            "app_ids_for_backup": ["app1", "app2"],
            "solution_id_for_backup": "solution1",
        }
    ]


def test_update_solution_encodes_id_and_omits_unspecified_backup_ids() -> None:
    client = RecordingClient([FakeResponse({"solutionId": "solution1"})])
    manager = SolutionsManager(cast(Any, client))
    qbl = "Version: 0.12\nResources: {}\n"

    manager.update_solution("solution/1?query=yes#part", qbl)

    assert client.calls == [
        {
            "method": "PUT",
            "endpoint": "/solutions/solution%2F1%3Fquery%3Dyes%23part",
            "payload": qbl,
            "headers": {"Content-Type": "application/x-yaml"},
            "solution_id_for_backup": "solution/1?query=yes#part",
        }
    ]


def test_update_solution_accepts_empty_backup_ids_when_backups_are_disabled() -> None:
    client = RecordingClient()
    manager = SolutionsManager(cast(Any, client))

    manager.update_solution("solution1", "Version: 0.12\n", app_ids_for_backup=[])

    assert client.calls[0]["app_ids_for_backup"] == []


@pytest.mark.parametrize("solution_id", ["", " \t", None, 42])
def test_update_solution_rejects_invalid_solution_id(solution_id: Any) -> None:
    client = RecordingClient()
    manager = SolutionsManager(cast(Any, client))

    with pytest.raises(QuickbaseValidationError, match="non-empty solution_id"):
        manager.update_solution(solution_id, "Version: 0.12\n")

    assert client.calls == []


@pytest.mark.parametrize("app_id", ["../app1", "app/1", "app?query=1", "app#1", "app 1"])
def test_update_solution_rejects_unsafe_backup_app_ids(app_id: str) -> None:
    client = RecordingClient()
    manager = SolutionsManager(cast(Any, client))

    with pytest.raises(QuickbaseValidationError, match="alphanumeric Quickbase ID"):
        manager.update_solution("solution1", "QBL", app_ids_for_backup=["app1", app_id])

    assert client.calls == []


@pytest.mark.parametrize("errors_as_success", [False, True])
def test_preview_solution_returns_changes_without_backup_context(errors_as_success: bool) -> None:
    result = {
        "id": "changeset1",
        "changes": [{"logicalType": "Table", "logicalId": "$Table_Orders", "action": "Remove"}],
    }
    client = RecordingClient([FakeResponse(result)])
    client.auto_backup = True
    manager = SolutionsManager(cast(Any, client))
    qbl = "Version: 0.12\nResources: {}\n"

    preview = manager.preview_solution_changes(
        "solution/1?query=yes#part", qbl, errors_as_success=errors_as_success
    )

    headers = {"Content-Type": "application/x-yaml"}
    if errors_as_success:
        headers["X-QBL-Errors-As-Success"] = "true"
    assert preview == result
    assert client.calls == [
        {
            "method": "PUT",
            "endpoint": "/solutions/solution%2F1%3Fquery%3Dyes%23part/changeset",
            "payload": qbl,
            "headers": headers,
        }
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"solution_id": ""},
        {"solution_id": " \t"},
        {"solution_id": None},
        {"solution_id": 42},
        {"qbl": ""},
        {"qbl": " \n"},
        {"qbl": {}},
        {"qbl": b"QBL"},
        {"errors_as_success": None},
        {"errors_as_success": 1},
        {"errors_as_success": "true"},
    ],
)
def test_preview_solution_rejects_invalid_arguments(overrides: dict[str, Any]) -> None:
    client = RecordingClient()
    manager = SolutionsManager(cast(Any, client))
    arguments: dict[str, Any] = {"solution_id": "solution1", "qbl": "QBL"}
    arguments.update(overrides)

    with pytest.raises(QuickbaseValidationError):
        manager.preview_solution_changes(**arguments)

    assert client.calls == []


def test_export_solution_encodes_the_same_target_as_update_and_preview() -> None:
    client = RecordingClient([FakeResponse(text="QBL")])
    manager = SolutionsManager(cast(Any, client))

    assert manager.export_solution("solution/1?query=yes#part") == "QBL"

    assert client.calls == [
        {
            "method": "GET",
            "endpoint": "/solutions/solution%2F1%3Fquery%3Dyes%23part",
            "headers": None,
        }
    ]


@pytest.mark.parametrize("qbl", ["", " \n", None, {}, b"Version: 0.12"])
def test_update_solution_rejects_invalid_qbl(qbl: Any) -> None:
    client = RecordingClient()
    manager = SolutionsManager(cast(Any, client))

    with pytest.raises(QuickbaseValidationError, match="non-empty QBL"):
        manager.update_solution("solution1", qbl)

    assert client.calls == []


@pytest.mark.parametrize("errors_as_success", [None, 1, "true"])
def test_update_solution_rejects_invalid_error_option(errors_as_success: Any) -> None:
    client = RecordingClient()
    manager = SolutionsManager(cast(Any, client))

    with pytest.raises(QuickbaseValidationError, match="errors_as_success must be a boolean"):
        manager.update_solution("solution1", "Version: 0.12\n", errors_as_success=errors_as_success)

    assert client.calls == []


@pytest.mark.parametrize("app_ids", ["app1", ("app1",), [""], ["  "], [None], [1]])
def test_update_solution_rejects_invalid_backup_ids(app_ids: Any) -> None:
    client = RecordingClient()
    manager = SolutionsManager(cast(Any, client))

    with pytest.raises(QuickbaseValidationError, match="list of non-empty application IDs"):
        manager.update_solution("solution1", "Version: 0.12\n", app_ids_for_backup=app_ids)

    assert client.calls == []


@pytest.mark.parametrize("app_ids", [None, []])
def test_update_solution_requires_app_ids_when_auto_backup_enabled(
    app_ids: list[str] | None,
) -> None:
    client = RecordingClient()
    client.auto_backup = True
    manager = SolutionsManager(cast(Any, client))

    with pytest.raises(QuickbaseValidationError, match="require app_ids_for_backup"):
        manager.update_solution("solution1", "Version: 0.12\n", app_ids_for_backup=app_ids)

    assert client.calls == []
