from __future__ import annotations

from typing import Any, cast

import pytest

from quickbase_structure_client.app import StructureApp
from quickbase_structure_client.exceptions import (
    QuickbasePermissionError,
    QuickbaseSchemaError,
    QuickbaseValidationError,
)
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

    with pytest.raises(
        QuickbaseSchemaError,
        match="cause=RuntimeError: field lookup failed",
    ):
        exporter.compile_schema("app1")


def test_schema_exporter_includes_relationship_failure_cause() -> None:
    class FailingTable:
        def list_fields(self) -> list[dict[str, Any]]:
            return []

        def list_relationships(self) -> list[dict[str, Any]]:
            raise RuntimeError("relationship lookup failed")

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

    with pytest.raises(
        QuickbaseSchemaError,
        match="cause=RuntimeError: relationship lookup failed",
    ):
        exporter.compile_schema("app1")


def test_schema_exporter_describes_relationship_permission_failure() -> None:
    permission_error = QuickbasePermissionError(
        "Quickbase denied access.",
        context={"status_code": 403},
    )

    class FailingTable:
        def list_fields(self) -> list[dict[str, Any]]:
            return []

        def list_relationships(self) -> list[dict[str, Any]]:
            raise permission_error

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

    with pytest.raises(
        QuickbaseSchemaError,
        match="Quickbase denied access to relationship metadata",
    ) as exc_info:
        exporter.compile_schema("app1")

    assert exc_info.value.cause is permission_error
    assert exc_info.value.context == {
        "operation": "SchemaExporter.compile_schema",
        "app_id": "app1",
        "table_id": "table1",
        "resource": "relationship metadata",
    }


def test_schema_exporter_compiles_only_requested_table() -> None:
    class SchemaClient(RecordingClient):
        def app(self, id: str) -> StructureApp:
            return StructureApp(cast(Any, self), id=id)

    client = SchemaClient(
        [
            FakeResponse({"name": "Operations", "description": "Ops schema"}),
            FakeResponse(
                {
                    "id": "table1",
                    "name": "Orders",
                    "pluralRecordName": "Orders",
                    "description": "Order records",
                }
            ),
            FakeResponse(
                [
                    {
                        "id": 7,
                        "label": "Total",
                        "fieldType": "currency",
                        "properties": {"required": True},
                    }
                ]
            ),
            FakeResponse(
                {
                    "relationships": [
                        {
                            "id": 3,
                            "parentTableId": "customers",
                            "parentTableName": "Customers",
                            "referenceFieldId": 12,
                            "referenceFieldLabel": "Customer",
                        }
                    ]
                }
            ),
        ]
    )
    exporter = SchemaExporter(cast(Any, client))

    schema = exporter.compile_schema("app1", table_id="table1")

    assert schema == {
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
                        "label": "Total",
                        "type": "currency",
                        "formula": None,
                        "unique": False,
                        "required": True,
                    }
                ],
                "relationships": [
                    {
                        "relationship_id": 3,
                        "parent_table_id": "customers",
                        "parent_table_name": "Customers",
                        "reference_field_id": 12,
                        "reference_field_label": "Customer",
                    }
                ],
            }
        ],
    }
    assert client.calls == [
        {"method": "GET", "endpoint": "/apps/app1"},
        {"method": "GET", "endpoint": "/tables/table1?appId=app1"},
        {"method": "GET", "endpoint": "/fields?tableId=table1"},
        {"method": "GET", "endpoint": "/tables/table1/relationships"},
    ]


def test_schema_exporter_rejects_empty_table_id() -> None:
    exporter = SchemaExporter(api_client=cast(Any, None))

    with pytest.raises(QuickbaseValidationError, match="table_id must be a non-empty string"):
        exporter.compile_schema("app1", table_id=" ")
