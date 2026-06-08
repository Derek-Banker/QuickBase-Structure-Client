from __future__ import annotations

from typing import Any, cast

import pytest

from quickbase_structure_client.exceptions import QuickbaseSchemaError
from quickbase_structure_client.schema_exporter import SchemaExporter
from quickbase_structure_client.solutions import SolutionsManager

from .conftest import FakeResponse, RecordingClient


def test_solutions_export_passes_qbl_version_header() -> None:
    client = RecordingClient([FakeResponse(text="qbl: content")])
    manager = SolutionsManager(cast(Any, client))

    content = manager.export_solution("solution1", qbl_version="0.9")

    assert content == "qbl: content"
    assert client.calls[0] == {
        "method": "GET",
        "endpoint": "/solutions/solution1",
        "headers": {"QBL-Version": "0.9"},
    }


def test_solutions_create_and_export_to_record_payloads() -> None:
    client = RecordingClient([FakeResponse({"id": "solution1"}), FakeResponse({"recordId": 4})])
    manager = SolutionsManager(cast(Any, client))
    qbl = "Version: 0.2\nResources: {}\n"

    created = manager.create_solution(qbl, errors_as_success=True)
    exported = manager.export_solution_to_record(
        "solution1",
        "table1",
        12,
        record_id=4,
        qbl_version="0.9",
    )

    assert created == {"id": "solution1"}
    assert exported == {"recordId": 4}
    assert client.calls[0] == {
        "method": "POST",
        "endpoint": "/solutions",
        "payload": qbl,
        "headers": {
            "Content-Type": "application/x-yaml",
            "X-QBL-Errors-As-Success": "true",
        },
    }
    assert client.calls[1] == {
        "method": "GET",
        "endpoint": "/solutions/solution1/torecord?tableId=table1&fieldId=12&recordId=4",
        "headers": {"QBL-Version": "0.9"},
    }


def test_schema_exporter_compiles_json_and_escapes_markdown() -> None:
    schema = {
        "app_id": "app1",
        "name": "Operations",
        "description": "Ops schema",
        "tables": [
            {
                "id": "table1",
                "name": "Orders",
                "plural_name": "Orders",
                "description": "Order records",
                "fields": [
                    {
                        "id": 7,
                        "label": "Total | Net",
                        "type": "formula-numeric",
                        "formula": "If([A] | [B], 1, 0)",
                        "unique": False,
                        "required": True,
                    }
                ],
                "relationships": [
                    {
                        "parent_table_name": "Customers",
                        "parent_table_id": "customers",
                        "reference_field_id": 12,
                        "reference_field_label": "Customer",
                    }
                ],
            }
        ],
    }

    exporter = SchemaExporter(api_client=cast(Any, None))
    json_export = exporter.to_json(schema)
    markdown = exporter.to_markdown(schema)

    assert '"app_id": "app1"' in json_export
    assert "Total \\| Net" in markdown
    assert "If([A] \\| [B], 1, 0)" in markdown
    assert "Links to parent table **Customers**" in markdown


def test_schema_exporter_raises_instead_of_returning_partial_schema() -> None:
    class FailingTable:
        def list_fields(self) -> list[dict[str, Any]]:
            raise RuntimeError("field lookup failed")

    class FakeApp:
        def get_details(self) -> dict[str, Any]:
            return {"name": "Operations"}

        def list_tables(self) -> list[dict[str, Any]]:
            return [{"id": "table1", "name": "Orders"}]

        def table(self, id: str) -> FailingTable:
            return FailingTable()

    class FakeClient:
        def app(self, id: str) -> FakeApp:
            return FakeApp()

    exporter = SchemaExporter(cast(Any, FakeClient()))

    with pytest.raises(QuickbaseSchemaError, match="Failed to fetch fields"):
        exporter.compile_schema("app1")
