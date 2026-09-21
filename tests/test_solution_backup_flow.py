from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, call

import pytest
import requests

from quickbase_structure_client.quickbase_api import Auth, QuickBaseStructureClient, RequestConfig

from .conftest import FakeResponse


@pytest.mark.parametrize("configured_solution", [None, "different-solution"])
def test_solution_update_exports_target_before_and_after_mutation(
    configured_solution: str | None, tmp_path: Path
) -> None:
    session = Mock(spec=requests.Session)
    session.headers = {}
    session.request.side_effect = [
        FakeResponse(text="Before QBL"),
        FakeResponse({"solutionId": "target"}),
        FakeResponse(text="After QBL"),
    ]
    api = QuickBaseStructureClient(
        Auth("example.quickbase.com", "test-token"),
        session=cast(requests.Session, session),
        request_config=RequestConfig(retry_count=0),
        auto_backup=True,
        backup_method="schema",
        backup_solution_id=configured_solution,
        backup_dir=str(tmp_path),
        backup_fallback_to_clone=False,
    )
    qbl = "Version: 0.12\nResources: {}\n"

    result = api.solutions.update_solution("target/alias", qbl, app_ids_for_backup=["app1"])

    assert result == {"solutionId": "target"}
    target_url = f"{api.base_url}/solutions/target%2Falias"
    assert [(c.args[0], c.args[1]) for c in session.request.call_args_list] == [
        ("GET", target_url), ("PUT", target_url), ("GET", target_url)
    ]
    assert session.request.call_args_list[1].kwargs["data"] == qbl
    pre, = tmp_path.glob("app1_pre_*.qbl")
    post, = tmp_path.glob("app1_post_*.qbl")
    assert pre.read_text(encoding="utf-8") == "Before QBL"
    assert post.read_text(encoding="utf-8") == "After QBL"
    assert pre.name.removeprefix("app1_pre_") == post.name.removeprefix("app1_post_")
    assert api.backup_solution_id == configured_solution


def test_solution_update_passes_target_to_every_application_backup() -> None:
    session = Mock(spec=requests.Session)
    session.headers = {}
    session.request.return_value = FakeResponse({"solutionId": "target"})
    api = QuickBaseStructureClient(
        Auth("example.quickbase.com", "test-token"), session=cast(requests.Session, session)
    )
    backup = Mock()
    backup.trigger_pre_backup.side_effect = [{"app_id": "app1"}, {"app_id": "app2"}]
    api.backup_manager = cast(Any, backup)

    api.solutions.update_solution("target", "QBL", app_ids_for_backup=["app1", "app2"])

    assert backup.trigger_pre_backup.call_args_list == [
        call("app1", solution_id="target"), call("app2", solution_id="target")
    ]
    assert backup.trigger_post_backup.call_args_list == [
        call({"app_id": "app1"}), call({"app_id": "app2"})
    ]


def test_solution_preview_sends_only_the_preview_request_with_backups_enabled() -> None:
    result = {"id": "changeset1", "changes": []}
    session = Mock(spec=requests.Session)
    session.headers = {}
    session.request.return_value = FakeResponse(result)
    api = QuickBaseStructureClient(
        Auth("example.quickbase.com", "test-token"),
        session=cast(requests.Session, session),
        auto_backup=True,
    )
    backup = Mock()
    api.backup_manager = cast(Any, backup)
    qbl = "Version: 0.12\nResources: {}\n"

    assert api.solutions.preview_solution_changes("target", qbl) == result

    session.request.assert_called_once_with(
        "PUT",
        f"{api.base_url}/solutions/target/changeset",
        headers={"Content-Type": "application/x-yaml"},
        timeout=api.request_config.timeout,
        data=qbl,
    )
    backup.trigger_pre_backup.assert_not_called()
    backup.trigger_post_backup.assert_not_called()
