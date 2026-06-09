from __future__ import annotations

from pathlib import Path
from typing import Any

from examples import export_schema


def test_export_schema_main_exports_requested_table(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    calls: dict[str, Any] = {}

    class FakeExporter:
        def compile_schema(
            self,
            app_id: str,
            *,
            table_id: str | None = None,
        ) -> dict[str, Any]:
            calls["compile"] = (app_id, table_id)
            return {"app_id": app_id, "tables": []}

        def to_json(self, schema: dict[str, Any], filepath: Path) -> str:
            calls["json_path"] = filepath
            return "{}"

        def to_markdown(self, schema: dict[str, Any], filepath: Path) -> str:
            calls["markdown_path"] = filepath
            return "# Schema"

    class FakeClient:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.exporter = FakeExporter()

    monkeypatch.setattr(export_schema, "QuickBaseStructureClient", FakeClient)

    result = export_schema.main(
        [
            "--app-id",
            "app1",
            "--table-id",
            "table1",
            "--realm-hostname",
            "example.quickbase.com",
            "--user-token",
            "token",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert calls == {
        "compile": ("app1", "table1"),
        "json_path": tmp_path / "app1_table1_schema.json",
        "markdown_path": tmp_path / "app1_table1_schema.md",
    }
