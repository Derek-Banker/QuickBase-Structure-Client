from __future__ import annotations

from typing import Any, cast

import pytest

from quickbase_structure_client.exceptions import QuickbaseValidationError
from quickbase_structure_client.field import StructureField
from quickbase_structure_client.table import StructureTable

from .conftest import FakeResponse, RecordingClient


def _call_field_helper(
    table: StructureTable, operation: str, *args: Any, **kwargs: Any
) -> dict[str, Any]:
    if operation == "table_create":
        return table.create_field("Total", "numeric", *args, **kwargs)
    if operation == "table_update":
        return table.update_field(7, *args, **kwargs)
    if operation == "create":
        return table.field(7).create("Total", "numeric", *args, **kwargs)
    return table.field(7).update(*args, **kwargs)


@pytest.mark.parametrize("operation", ["table_create", "table_update", "create", "update"])
def test_field_help_takes_precedence_without_sending_description(operation: str) -> None:
    client = RecordingClient([FakeResponse({"id": 7})])
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")
    properties = {"description": "Alias text", "fieldHelp": "Explicit help"}

    _call_field_helper(table, operation, properties)

    expected_payload = {"fieldHelp": "Explicit help"}
    if operation.endswith("create"):
        expected_payload.update({"label": "Total", "fieldType": "numeric"})
    expected_endpoint = "/fields?tableId=table1"
    if operation.endswith("update"):
        expected_endpoint = "/fields/7?tableId=table1"
    assert client.calls == [
        {
            "method": "POST",
            "endpoint": expected_endpoint,
            "payload": expected_payload,
            "app_id_for_backup": "app1",
        }
    ]
    assert properties == {"description": "Alias text", "fieldHelp": "Explicit help"}


@pytest.mark.parametrize("operation", ["table_create", "table_update", "create", "update"])
@pytest.mark.parametrize("argument", ["options", "properties", "positional"])
def test_field_options_preserve_api_nesting_and_legacy_arguments(
    operation: str, argument: str
) -> None:
    client = RecordingClient([FakeResponse({"id": 7})])
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")
    options = {
        "fieldHelp": "Final amount",
        "properties": {"formula": "[Subtotal]", "decimalPlaces": 2},
        "futureOption": "preserved",
    }

    if argument == "positional":
        _call_field_helper(table, operation, options)
    else:
        _call_field_helper(table, operation, **{argument: options})

    expected = dict(options)
    if operation.endswith("create"):
        expected.update({"label": "Total", "fieldType": "numeric"})
    endpoint = "/fields?tableId=table1"
    if operation.endswith("update"):
        endpoint = "/fields/7?tableId=table1"
    assert client.calls == [
        {
            "method": "POST",
            "endpoint": endpoint,
            "payload": expected,
            "app_id_for_backup": "app1",
        }
    ]
    assert "label" not in options


@pytest.mark.parametrize("operation", ["table_create", "table_update", "create", "update"])
def test_field_helpers_reject_both_options_and_legacy_properties(operation: str) -> None:
    client = RecordingClient()
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")

    with pytest.raises(QuickbaseValidationError, match="not both"):
        _call_field_helper(table, operation, options={}, properties={})

    assert client.calls == []


@pytest.mark.parametrize("operation", ["table_create", "table_update", "create", "update"])
@pytest.mark.parametrize("options", [[], "invalid", {"properties": []}, {"properties": None}])
def test_field_helpers_reject_invalid_option_shapes(operation: str, options: Any) -> None:
    client = RecordingClient()
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")

    with pytest.raises(QuickbaseValidationError, match="dictionary"):
        _call_field_helper(table, operation, options=options)

    assert client.calls == []


@pytest.mark.parametrize("operation", ["table_update", "update"])
def test_field_updates_require_options_but_accept_an_empty_dictionary(operation: str) -> None:
    client = RecordingClient()
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")

    with pytest.raises(QuickbaseValidationError, match="required"):
        _call_field_helper(table, operation)

    assert client.calls == []
    _call_field_helper(table, operation, options={})
    assert client.calls[0]["payload"] == {}


@pytest.mark.parametrize(
    ("skip", "top", "suffix"),
    [(None, None, ""), (0, None, "&skip=0"), (None, 20, "&top=20"), (10, 5, "&skip=10&top=5")],
)
def test_get_fields_usage_returns_usage_list_without_backup(
    skip: int | None, top: int | None, suffix: str
) -> None:
    response = [{"field": {"id": 7}, "usage": {"reports": [{"id": 1}]}}]
    client = RecordingClient([FakeResponse(response)])
    client.auto_backup = True
    table = StructureTable(cast(Any, client), id="table1")

    assert table.get_fields_usage(skip=skip, top=top) == response
    assert client.calls == [{"method": "GET", "endpoint": f"/fields/usage?tableId=table1{suffix}"}]


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("skip", -1),
        ("skip", True),
        ("skip", "1"),
        ("skip", 1.5),
        ("top", 0),
        ("top", -1),
        ("top", False),
        ("top", "5"),
        ("top", 2.5),
    ],
)
def test_get_fields_usage_rejects_invalid_pagination(parameter: str, value: Any) -> None:
    client = RecordingClient()
    table = StructureTable(cast(Any, client), id="table1")

    with pytest.raises(QuickbaseValidationError, match=parameter):
        table.get_fields_usage(**{parameter: value})

    assert client.calls == []


@pytest.mark.parametrize("field_id", [7, "7"])
def test_set_key_field_uses_xml_action_and_backup_context(field_id: int | str) -> None:
    client = RecordingClient(
        [FakeResponse(text="<qdbapi><errcode>0</errcode><errtext>No error</errtext></qdbapi>")]
    )
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")

    assert table.set_key_field(field_id, app_token="app-token") == {
        "errcode": "0",
        "errtext": "No error",
    }
    assert client.calls == [
        {
            "method": "POST",
            "endpoint": "/db/table1",
            "payload": {"fid": "7"},
            "xml_action": "API_SetKeyField",
            "app_token": "app-token",
            "app_id_for_backup": "app1",
        }
    ]


@pytest.mark.parametrize("via_table", [True, False])
def test_update_field_xml_preserves_settings_and_backup_context(via_table: bool) -> None:
    client = RecordingClient([FakeResponse(text="<qdbapi><errcode>0</errcode></qdbapi>")])
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")
    options = {"doesdatacopy": "0", "allowHTML": "1"}

    if via_table:
        result = table.update_field_xml(7, options, app_token="app-token")
    else:
        result = table.field("7").update_xml(options, app_token="app-token")

    assert result == {"errcode": "0"}
    assert client.calls == [
        {
            "method": "POST",
            "endpoint": "/db/table1",
            "payload": {"fid": "7", "doesdatacopy": "0", "allowHTML": "1"},
            "xml_action": "API_SetFieldProperties",
            "app_token": "app-token",
            "app_id_for_backup": "app1",
        }
    ]
    assert options == {"doesdatacopy": "0", "allowHTML": "1"}


@pytest.mark.parametrize("operation", ["set_key", "table_update", "field_update"])
def test_xml_mutations_require_app_context_for_backup(operation: str) -> None:
    client = RecordingClient()
    client.auto_backup = True
    table = StructureTable(cast(Any, client), id="table1")

    with pytest.raises(QuickbaseValidationError, match="[Aa]pp"):
        if operation == "set_key":
            table.set_key_field(7)
        elif operation == "table_update":
            table.update_field_xml(7, {"doesdatacopy": False})
        else:
            table.field(7).update_xml({"doesdatacopy": False})

    assert client.calls == []


@pytest.mark.parametrize("operation", ["set_key", "table_update", "field_update"])
@pytest.mark.parametrize("field_id", [True, 0, -1, "", "x", "1/2"])
def test_xml_mutations_reject_invalid_field_ids(operation: str, field_id: Any) -> None:
    client = RecordingClient()
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")

    with pytest.raises(QuickbaseValidationError):
        if operation == "set_key":
            table.set_key_field(field_id)
        elif operation == "table_update":
            table.update_field_xml(field_id, {"doesdatacopy": False})
        else:
            table.field(field_id).update_xml({"doesdatacopy": False})

    assert client.calls == []


def test_bound_field_xml_update_without_backup_accepts_missing_app_context() -> None:
    client = RecordingClient([FakeResponse(text="<qdbapi><errcode>0</errcode></qdbapi>")])
    field = StructureField(cast(Any, client), table_id="table1", field_id=7)

    field.update_xml({"doesdatacopy": "0"})

    assert client.calls[0]["app_id_for_backup"] is None


@pytest.mark.parametrize("via_table", [True, False])
@pytest.mark.parametrize(
    "options", [{}, {"fid": 8}, {"usertoken": "not-a-token"}, {"choices": "A"}]
)
def test_xml_field_updates_reject_invalid_options_before_request(
    via_table: bool, options: dict[str, Any]
) -> None:
    client = RecordingClient()
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")

    with pytest.raises(QuickbaseValidationError):
        if via_table:
            table.update_field_xml(7, options)
        else:
            table.field(7).update_xml(options)

    assert client.calls == []


def test_bound_field_xml_update_uses_returned_field_name() -> None:
    client = RecordingClient(
        [FakeResponse(text="<qdbapi><errcode>0</errcode><fname>Final total</fname></qdbapi>")]
    )
    field = StructureField(cast(Any, client), table_id="table1", field_id=7, label="Old total")

    field.update_xml({"label": "Final total"})

    assert field.label == "Final total"


@pytest.mark.parametrize("field_id", [7, "7", "007"])
def test_field_get_usage_requires_no_app_context_or_backup(field_id: int | str) -> None:
    response = [{"field": {"id": 7}, "usage": {"reports": {"count": 1}}}]
    client = RecordingClient([FakeResponse(response)])
    client.auto_backup = True
    field = StructureField(cast(Any, client), table_id="table1", field_id=field_id)

    assert field.get_usage() == response
    assert client.calls == [{"method": "GET", "endpoint": "/fields/usage/7?tableId=table1"}]


@pytest.mark.parametrize("field_id", [None, True, False, 0, -1, 1.5, "", "0", "-1", "x", "1/2"])
def test_field_get_usage_rejects_invalid_id(field_id: Any) -> None:
    client = RecordingClient()
    field = StructureField(cast(Any, client), table_id="table1", field_id=field_id)

    with pytest.raises(QuickbaseValidationError):
        field.get_usage()

    assert client.calls == []
