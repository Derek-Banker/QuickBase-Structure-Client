from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from examples import pto_tracking_demo as demo


def test_load_env_file_parses_simple_dotenv(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
        # comment
        QUICKBASE_REALM_HOSTNAME="demo.quickbase.com"
        export QUICKBASE_DEMO_EXECUTE=true
        QUICKBASE_DEMO_APP_NAME='PTO Test'
        MALFORMED
        """,
        encoding="utf-8",
    )

    values = demo.load_env_file(env_file)

    assert values["QUICKBASE_REALM_HOSTNAME"] == "demo.quickbase.com"
    assert values["QUICKBASE_DEMO_EXECUTE"] == "true"
    assert values["QUICKBASE_DEMO_APP_NAME"] == "PTO Test"
    assert "MALFORMED" not in values


def test_build_config_defaults_to_dry_run_without_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUICKBASE_REALM_HOSTNAME", raising=False)
    monkeypatch.delenv("QUICKBASE_USER_TOKEN", raising=False)

    config = demo.build_config(tmp_path / "missing.env")

    assert config.execute is False
    assert config.realm_hostname == "example.quickbase.com"
    assert config.user_token == "<qb-user-token>"
    assert config.app_name == "PTO Tracking Demo"
    assert config.assign_token is True


def test_build_config_rejects_placeholder_credentials_for_execute(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
        QUICKBASE_REALM_HOSTNAME=example.quickbase.com
        QUICKBASE_USER_TOKEN=replace-with-qb-user-token
        QUICKBASE_DEMO_EXECUTE=true
        """,
        encoding="utf-8",
    )

    with pytest.raises(demo.DemoConfigurationError, match="Real QUICKBASE"):
        demo.build_config(env_file)


def test_demo_plan_includes_optional_relationship_and_trustee(tmp_path: Path) -> None:
    config = demo.DemoConfig(
        realm_hostname="demo.quickbase.com",
        user_token="token",
        app_name="PTO Demo",
        execute=False,
        assign_token=True,
        auto_backup=False,
        backup_method="schema",
        backup_solution_id=None,
        backup_dir=tmp_path / "backups",
        backup_fallback_to_clone=True,
        export_dir=tmp_path / "exports",
        create_relationship=True,
        trustee_email="admin@example.com",
        trustee_role_id=12,
    )

    plan = demo.demo_plan(config)

    assert "Create relationship: Users -> PTO Events" in plan
    assert "Add trustee admin@example.com with role id 12" in plan


def test_quickbase_resource_url_normalizes_realm() -> None:
    assert (
        demo.quickbase_resource_url("https://co2monitoring.quickbase.com/", "bv4n4bifc")
        == "https://co2monitoring.quickbase.com/db/bv4n4bifc"
    )
    assert demo.quickbase_resource_url("co2monitoring.quickbase.com", None) is None


def test_main_dry_run_does_not_require_live_credentials(tmp_path: Path, capsys) -> None:
    exit_code = demo.main(["--env-file", str(tmp_path / "missing.env")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "PTO tracking demo mode: DRY RUN" in captured.out
    assert "Dry run only" in captured.out


class FakeTable:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name
        self.fields: list[tuple[str, str, dict[str, Any]]] = []
        self.relationships: list[dict[str, Any]] = []

    def create_field(
        self,
        label: str,
        field_type: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.fields.append((label, field_type, properties or {}))
        return {"id": len(self.fields) + 5, "label": label, "fieldType": field_type}

    def create_relationship(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.relationships.append(payload)
        return {"id": 1}


class FakeApp:
    def __init__(self, id: str):
        self.id = id
        self.tables: list[FakeTable] = []
        self.trustees: list[dict[str, Any]] = []

    def create_table(
        self,
        name: str,
        plural_name: str | None = None,
        single_record_name: str | None = None,
        description: str | None = None,
    ) -> FakeTable:
        table = FakeTable(f"table{len(self.tables) + 1}", name)
        self.tables.append(table)
        return table

    def add_trustees(self, trustees: list[dict[str, Any]]) -> dict[str, Any]:
        self.trustees.extend(trustees)
        return {"ok": True}


class FakeExporter:
    def compile_schema(self, app_id: str) -> dict[str, Any]:
        return {"app_id": app_id, "name": "PTO Demo", "tables": []}

    def to_json(self, schema: dict[str, Any], filepath: Path) -> str:
        filepath.write_text('{"app_id": "app1"}', encoding="utf-8")
        return filepath.read_text(encoding="utf-8")

    def to_markdown(self, schema: dict[str, Any], filepath: Path) -> str:
        filepath.write_text("# PTO Demo", encoding="utf-8")
        return filepath.read_text(encoding="utf-8")


class FakeClient:
    created: list["FakeClient"] = []

    def __init__(self, *args: Any, **kwargs: Any):
        self.app = FakeApp("app1")
        self.exporter = FakeExporter()
        self.kwargs = kwargs
        self.create_app_calls: list[dict[str, Any]] = []
        FakeClient.created.append(self)

    def create_app(
        self,
        name: str,
        description: str | None = None,
        *,
        assign_token: bool = False,
    ) -> FakeApp:
        self.create_app_calls.append(
            {
                "name": name,
                "description": description,
                "assign_token": assign_token,
            }
        )
        return self.app


def test_run_demo_creates_pto_structure_with_fake_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeClient.created.clear()
    monkeypatch.setattr(demo, "QuickBaseStructureClient", FakeClient)
    config = demo.DemoConfig(
        realm_hostname="demo.quickbase.com",
        user_token="token",
        app_name="PTO Demo",
        execute=True,
        assign_token=True,
        auto_backup=False,
        backup_method="schema",
        backup_solution_id=None,
        backup_dir=tmp_path / "backups",
        backup_fallback_to_clone=True,
        export_dir=tmp_path / "exports",
        create_relationship=True,
        trustee_email="admin@example.com",
        trustee_role_id=12,
    )

    result = demo.run_demo(config)

    fake_client = FakeClient.created[0]
    assert result.app_id == "app1"
    assert fake_client.create_app_calls[0]["assign_token"] is True
    assert result.app_url == "https://demo.quickbase.com/db/app1"
    assert result.users_table_url == "https://demo.quickbase.com/db/table1"
    assert result.events_table_url == "https://demo.quickbase.com/db/table2"
    assert [table.name for table in fake_client.app.tables] == ["User", "PTO Event"]
    assert len(fake_client.app.tables[0].fields) == 5
    assert len(fake_client.app.tables[1].fields) == 7
    assert fake_client.app.tables[1].relationships[0]["parentTableId"] == "table1"
    assert fake_client.app.trustees[0]["id"] == "admin@example.com"
    assert (tmp_path / "exports" / "pto_tracking_schema.json").exists()
