from __future__ import annotations

from typing import Any, cast

import pytest

from quickbase_structure_client.app import StructureApp
from quickbase_structure_client.exceptions import QuickbaseValidationError
from quickbase_structure_client.field import StructureField
from quickbase_structure_client.relationship import StructureRelationship
from quickbase_structure_client.table import StructureTable
from quickbase_structure_client.trustees import TrusteesManager

from .conftest import FakeResponse, RecordingClient


def test_app_copy_uses_nested_copy_properties() -> None:
    client = RecordingClient([FakeResponse({"id": "copied-app"})])
    app = StructureApp(cast(Any, client), id="app1")

    copied = app.copy(
        "Backup",
        description="Backup app",
        exclude_files=True,
        keep_data=False,
        users_and_roles=False,
        assign_user_token=True,
    )

    assert copied.id == "copied-app"
    assert client.calls[0] == {
        "method": "POST",
        "endpoint": "/apps/app1/copy",
        "payload": {
            "name": "Backup",
            "description": "Backup app",
            "properties": {
                "excludeFiles": True,
                "keepData": False,
                "usersAndRoles": False,
                "assignUserToken": True,
            },
        },
        "app_id_for_backup": "app1",
    }


def test_app_delete_requires_confirmation_name() -> None:
    client = RecordingClient()
    app = StructureApp(cast(Any, client), id="app1")

    with pytest.raises(QuickbaseValidationError, match="requires the application name"):
        app.delete()

    app.delete(confirm_name="Orders")

    assert client.calls[0] == {
        "method": "DELETE",
        "endpoint": "/apps/app1",
        "payload": {"name": "Orders"},
        "app_id_for_backup": "app1",
    }


def test_app_create_table_uses_record_name_properties() -> None:
    client = RecordingClient([FakeResponse({"id": "table1"})])
    app = StructureApp(cast(Any, client), id="app1")

    table = app.create_table(
        "Order",
        plural_name="Orders",
        single_record_name="Order",
        description="Customer orders",
    )

    assert table.id == "table1"
    assert client.calls[0]["method"] == "POST"
    assert client.calls[0]["endpoint"] == "/tables?appId=app1"
    assert client.calls[0]["payload"] == {
        "name": "Order",
        "pluralRecordName": "Orders",
        "singleRecordName": "Order",
        "description": "Customer orders",
    }


def test_table_update_field_and_relationship_use_structural_post_methods() -> None:
    client = RecordingClient(
        [
            FakeResponse({"id": "table1", "name": "Invoices"}),
            FakeResponse({"id": 7}),
            FakeResponse({"id": 3}),
        ]
    )
    table = StructureTable(cast(Any, client), id="table1", app_id="app1")

    table.update(name="Invoices", plural_name="Invoices", single_record_name="Invoice")
    table.update_field(7, {"label": "Total", "properties": {"formula": "[Subtotal]"}})
    table.update_relationship(3, {"summaryFields": [{"summaryFid": 10}]})

    assert client.calls[0]["method"] == "POST"
    assert client.calls[0]["endpoint"] == "/tables/table1?appId=app1"
    assert client.calls[0]["payload"]["pluralRecordName"] == "Invoices"
    assert client.calls[1]["method"] == "POST"
    assert client.calls[1]["endpoint"] == "/fields/7?tableId=table1"
    assert client.calls[2]["method"] == "POST"
    assert client.calls[2]["endpoint"] == "/tables/table1/relationship/3"


def test_structure_field_requires_app_id_for_mutation_when_auto_backup_enabled() -> None:
    client = RecordingClient([FakeResponse({"id": 7, "label": "Total"})])
    client.auto_backup = True
    field = StructureField(cast(Any, client), table_id="table1", field_id=7)

    with pytest.raises(QuickbaseValidationError, match="require app_id"):
        field.update({"label": "Total"})

    field = StructureField(cast(Any, client), table_id="table1", field_id=7, app_id="app1")
    field.update({"label": "Total"})

    assert client.calls[0]["app_id_for_backup"] == "app1"


def test_relationship_wrapper_updates_and_deletes() -> None:
    client = RecordingClient([FakeResponse({"id": 2}), FakeResponse({"deleted": [2]})])
    relationship = StructureRelationship(
        cast(Any, client),
        child_table_id="child",
        relationship_id=2,
        app_id="app1",
    )

    relationship.update({"lookupFieldIds": [6, 7]})
    relationship.delete()

    assert client.calls[0]["method"] == "POST"
    assert client.calls[0]["endpoint"] == "/tables/child/relationship/2"
    assert client.calls[1]["method"] == "DELETE"
    assert client.calls[1]["endpoint"] == "/tables/child/relationship/2"


def test_trustees_manager_uses_apps_path_and_list_payloads() -> None:
    client = RecordingClient([FakeResponse({"ok": True})])
    manager = TrusteesManager(cast(Any, client))
    trustees = [{"id": "user@example.com", "type": "user", "roleId": 12}]

    manager.add_trustees("app1", trustees)
    manager.update_trustees("app1", trustees)
    manager.remove_trustees("app1", [{"id": "user@example.com", "type": "user"}])

    assert client.calls[0] == {
        "method": "POST",
        "endpoint": "/apps/app1/trustees",
        "payload": trustees,
        "app_id_for_backup": "app1",
    }
    assert client.calls[1]["method"] == "PUT"
    assert client.calls[1]["endpoint"] == "/apps/app1/trustees"
    assert client.calls[2]["method"] == "DELETE"
    assert client.calls[2]["payload"] == [{"id": "user@example.com", "type": "user"}]
