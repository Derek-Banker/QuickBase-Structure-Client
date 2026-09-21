from __future__ import annotations

import sys
from typing import Any, cast

import pytest

from quickbase_structure_client.exceptions import QuickbaseValidationError
from quickbase_structure_client.field import StructureField
from quickbase_structure_client.table import StructureTable

from .conftest import FakeResponse, RecordingClient

FIELD_OPERATIONS = (
    "read", "usage", "update", "delete", "xml_update", "table_update", "table_delete", "key"
)


def _field_operation(table: StructureTable, operation: str, field_id: Any) -> None:
    field = table.field(field_id)
    if operation == "read":
        field.get_details()
    elif operation == "usage":
        field.get_usage()
    elif operation == "update":
        field.update({"label": "Changed"})
    elif operation == "delete":
        field.delete()
    elif operation == "xml_update":
        field.update_xml({"label": "Changed"})
    elif operation == "table_update":
        table.update_field(field_id, {"label": "Changed"})
    elif operation == "table_delete":
        table.delete_fields([6, field_id, 8])
    else:
        table.set_key_field(field_id)


@pytest.mark.parametrize("operation", FIELD_OPERATIONS)
@pytest.mark.parametrize("field_id", [7, "7", "007"])
def test_field_operations_normalize_valid_ids(operation: str, field_id: int | str) -> None:
    client = RecordingClient([FakeResponse(text="<qdbapi><errcode>0</errcode></qdbapi>")])
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")

    _field_operation(table, operation, field_id)

    expected: dict[str, Any] = {
        "method": "POST",
        "endpoint": "/fields/7?tableId=table1",
        "payload": {"label": "Changed"},
        "app_id_for_backup": "app1",
    }
    if operation in ("read", "usage"):
        endpoint = "/fields/7?tableId=table1"
        if operation == "usage":
            endpoint = "/fields/usage/7?tableId=table1"
        expected = {"method": "GET", "endpoint": endpoint}
    elif operation in ("delete", "table_delete"):
        expected.update(
            method="DELETE",
            endpoint="/fields?tableId=table1",
            payload={"fieldIds": [6, 7, 8] if operation == "table_delete" else [7]},
        )
    elif operation in ("xml_update", "key"):
        expected.update(
            endpoint="/db/table1",
            payload={"fid": "7", "label": "Changed"} if operation == "xml_update" else {"fid": "7"},
            xml_action="API_SetFieldProperties" if operation == "xml_update" else "API_SetKeyField",
            app_token=None,
        )
    assert client.calls == [expected]


@pytest.mark.parametrize("operation", FIELD_OPERATIONS)
@pytest.mark.parametrize(
    "field_id", [None, True, False, 0, -1, 7.0, 7.5, "", "0", "-1", "+7", " 7", "7/8", "٧"]
)
def test_field_operations_reject_invalid_ids_before_request(operation: str, field_id: Any) -> None:
    client = RecordingClient()
    client.auto_backup = True
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")

    with pytest.raises(QuickbaseValidationError):
        _field_operation(table, operation, field_id)

    assert client.calls == []


@pytest.mark.parametrize("field_ids", ["78", (7, 8), None, 7])
def test_batch_field_deletion_requires_a_list(field_ids: Any) -> None:
    client = RecordingClient()
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")

    with pytest.raises(QuickbaseValidationError, match="list"):
        table.delete_fields(field_ids)

    assert client.calls == []


def test_batch_field_deletion_retains_empty_list_behavior() -> None:
    client = RecordingClient()
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")

    table.delete_fields([])

    assert client.calls == [
        {
            "method": "DELETE",
            "endpoint": "/fields?tableId=table1",
            "payload": {"fieldIds": []},
            "app_id_for_backup": "app1",
        }
    ]


@pytest.mark.parametrize("via_table", [True, False])
@pytest.mark.parametrize("via_options", [True, False])
@pytest.mark.parametrize("parameter", ["label", "fieldType"])
@pytest.mark.parametrize("value", [None, False, 7, "", " \t"])
def test_field_creation_validates_final_label_and_type(
    via_table: bool, via_options: bool, parameter: str, value: Any
) -> None:
    client = RecordingClient()
    client.auto_backup = True
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")
    arguments: dict[str, Any] = {"label": "Total", "field_type": "numeric"}
    if via_options:
        arguments["options"] = {parameter: value}
    else:
        arguments["label" if parameter == "label" else "field_type"] = value

    with pytest.raises(QuickbaseValidationError, match=parameter):
        if via_table:
            table.create_field(**arguments)
        else:
            table.field(7).create(**arguments)

    assert client.calls == []


@pytest.mark.parametrize("via_table", [True, False])
def test_field_creation_accepts_unknown_types_and_valid_final_overrides(via_table: bool) -> None:
    client = RecordingClient([FakeResponse({"id": 7, "label": "Final label"})])
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")
    options = {"label": "Final label", "fieldType": "future-field-type"}

    if via_table:
        table.create_field("", "", options=options)
    else:
        table.field(7).create("", "", options=options)

    assert client.calls == [
        {
            "method": "POST",
            "endpoint": "/fields?tableId=table1",
            "payload": options,
            "app_id_for_backup": "app1",
        }
    ]


@pytest.mark.parametrize("operation", ["create", "read", "usage", "update", "delete", "xml_update"])
def test_bound_field_operations_reject_invalid_table_ids(operation: str) -> None:
    client = RecordingClient()
    table = StructureTable(cast(Any, client), id="table1?other=value", app_id="app1")

    with pytest.raises(QuickbaseValidationError, match="table_id"):
        if operation == "create":
            table.field(7).create("Total", "numeric")
        else:
            _field_operation(table, operation, 7)

    assert client.calls == []


@pytest.mark.parametrize("operation", ["create", "update", "delete", "xml_update"])
def test_bound_field_mutations_reject_invalid_app_ids(operation: str) -> None:
    client = RecordingClient()
    table = StructureTable(cast(Any, client), id="table1", app_id="app1/other")

    with pytest.raises(QuickbaseValidationError, match="app_id"):
        if operation == "create":
            table.field(7).create("Total", "numeric")
        else:
            _field_operation(table, operation, 7)

    assert client.calls == []


@pytest.mark.parametrize(
    ("method", "arguments"),
    [
        ("get_details", ()),
        ("update", ("Renamed",)),
        ("delete", ()),
        ("set_key_field", (7,)),
        ("create_field", ("Total", "numeric")),
        ("list_fields", ()),
        ("get_fields_usage", ()),
        ("update_field", (7, {"label": "Changed"})),
        ("delete_fields", ([7],)),
        ("update_field_xml", (7, {"label": "Changed"})),
        ("list_relationships", ()),
        ("create_relationship", ({"parentTableId": "parent"},)),
        ("update_relationship", (7, {})),
        ("delete_relationship", (7,)),
    ],
)
def test_table_operations_reject_invalid_table_ids(method: str, arguments: tuple[Any, ...]) -> None:
    client = RecordingClient()
    table = StructureTable(cast(Any, client), id="table1/other", app_id="app1")

    with pytest.raises(QuickbaseValidationError, match="table_id"):
        getattr(table, method)(*arguments)

    assert client.calls == []


def test_xml_scalar_conversion_errors_use_package_exception_before_request() -> None:
    get_limit = getattr(sys, "get_int_max_str_digits", None)
    set_limit = getattr(sys, "set_int_max_str_digits", None)
    if get_limit is None or set_limit is None:
        pytest.skip("Python has no integer string conversion limit.")
    client = RecordingClient()
    field = StructureField(cast(Any, client), table_id="table1", field_id=7)
    old_limit = get_limit()
    try:
        set_limit(640)
        with pytest.raises(QuickbaseValidationError, match="too large") as captured:
            field.update_xml({"width": 10**1000})
    finally:
        set_limit(old_limit)

    assert isinstance(captured.value.__cause__, ValueError)
    assert client.calls == []
