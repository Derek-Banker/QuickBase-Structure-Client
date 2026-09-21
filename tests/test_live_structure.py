"""Opt-in live tests that remove their temporary table after each run."""

from __future__ import annotations

import os
from pathlib import Path
from secrets import token_hex

import pytest
from dotenv import load_dotenv

from quickbase_structure_client import (
    Auth,
    QuickbaseError,
    QuickBaseStructureClient,
    RequestConfig,
    StructureTable,
    normalize_realm_hostname,
)

pytestmark = pytest.mark.integration


def _failure_details(exc: QuickbaseError) -> str:
    """Return the error type and numeric codes without response data or secrets."""
    details = type(exc).__name__
    for name in ("status_code", "xml_error_code"):
        value = exc.context.get(name)
        if type(value) is int:
            details += f", {name}={value}"
    return details


def _live_client() -> tuple[QuickBaseStructureClient, str]:
    """Require explicit targets before loading credentials from the local file."""
    __tracebackhide__ = True
    if os.environ.get("QUICKBASE_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set QUICKBASE_RUN_INTEGRATION_TESTS=1 to enable live tests.")

    app_id = os.environ.get("QUICKBASE_TEST_APP_ID", "")
    expected_realm = os.environ.get("QUICKBASE_TEST_REALM_HOSTNAME", "")
    if not app_id or not expected_realm:
        pytest.fail(
            "Set QUICKBASE_TEST_APP_ID and QUICKBASE_TEST_REALM_HOSTNAME explicitly.",
            pytrace=False,
        )

    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    try:
        auth = Auth(
            realm=os.environ.get("QUICKBASE_REALM_HOSTNAME", ""),
            user_token=os.environ.get("QUICKBASE_USER_TOKEN", ""),
        )
    except QuickbaseError as exc:
        pytest.fail(
            f"Live authentication configuration failed: {type(exc).__name__}.",
            pytrace=False,
        )

    if auth.realm != normalize_realm_hostname(expected_realm):
        pytest.fail("The credential realm does not match the explicit test realm.", pytrace=False)

    return (
        QuickBaseStructureClient(
            auth,
            auto_backup=False,
            backup_fallback_to_clone=False,
            request_config=RequestConfig(timeout=(10, 30), retry_count=0),
        ),
        app_id,
    )


def test_live_table_and_field_lifecycle() -> None:
    """Verify REST and XML field operations within one temporary table."""
    __tracebackhide__ = True
    client, app_id = _live_client()
    app = client.app(app_id)
    table: StructureTable | None = None
    stage = "create table"
    table_name = f"Structure client integration {token_hex(8)}"

    try:
        table = app.create_table(
            table_name,
            plural_name="Test entries",
            single_record_name="Test entry",
            description="Temporary integration test table.",
        )
        assert table.id, "Quickbase must return the created table ID."
        original_key_id = int(table.get_details()["keyFieldId"])

        stage = "update table properties"
        table.update(
            name=f"{table_name} updated",
            plural_name="Checked entries",
            single_record_name="Checked entry",
            description="Updated integration test description.",
        )
        details = table.get_details()
        assert details["name"] == f"{table_name} updated"
        assert details["pluralRecordName"] == "Checked entries"
        assert details["singleRecordName"] == "Checked entry"
        assert details["description"] == "Updated integration test description."

        stage = "create field with REST options"
        created_field = table.create_field(
            "Test text",
            "text",
            options={
                "description": "Help from the description alias.",
                "properties": {"defaultValue": "Initial default"},
            },
        )
        field = table.field(created_field["id"])
        details = field.get_details()
        assert details["fieldHelp"] == "Help from the description alias."
        assert details["properties"]["defaultValue"] == "Initial default"

        stage = "update field with the legacy properties keyword"
        field.update(
            properties={
                "label": "Updated text",
                "description": "This alias must not override fieldHelp.",
                "fieldHelp": "Explicit field help.",
                "properties": {"defaultValue": "Updated default"},
            }
        )
        details = field.get_details()
        assert details["label"] == "Updated text"
        assert details["fieldHelp"] == "Explicit field help."
        assert details["properties"]["defaultValue"] == "Updated default"

        stage = "read paged and individual field usage"
        first_page = table.get_fields_usage(skip=0, top=1)
        second_page = table.get_fields_usage(skip=1, top=1)
        assert len(first_page) == len(second_page) == 1
        assert first_page[0]["field"]["id"] != second_page[0]["field"]["id"]
        usage = field.get_usage()
        assert len(usage) == 1
        assert usage[0]["field"]["id"] == created_field["id"]
        assert "usage" in usage[0]

        stage = "update XML label and copy behavior"
        result = field.update_xml(
            {"label": "XML text & notes", "doesdatacopy": False},
            app_token=os.environ.get("QUICKBASE_APP_TOKEN") or None,
        )
        assert result["errcode"] == "0"
        assert field.get_details()["label"] == "XML text & notes"
        result = table.update_field_xml(
            created_field["id"],
            {"doesdatacopy": True},
            app_token=os.environ.get("QUICKBASE_APP_TOKEN") or None,
        )
        assert result["errcode"] == "0"

        stage = "update XML rich-text HTML behavior"
        rich_text = table.create_field("Test rich text", "rich-text")
        rich_field = table.field(rich_text["id"])
        for allow_html in (False, True):
            result = rich_field.update_xml(
                {"allowHTML": allow_html},
                app_token=os.environ.get("QUICKBASE_APP_TOKEN") or None,
            )
            assert result["errcode"] == "0"
        assert rich_field.get_details()["fieldType"] == "rich-text"

        stage = "change and restore the table key"
        key_field = table.create_field("Test key", "text")
        table.update_field(key_field["id"], options={"unique": True, "required": True})
        key_details = table.field(key_field["id"]).get_details()
        assert key_details["unique"] is True and key_details["required"] is True
        try:
            result = table.set_key_field(
                key_field["id"], app_token=os.environ.get("QUICKBASE_APP_TOKEN") or None
            )
            assert result["errcode"] == "0"
            assert table.get_details()["keyFieldId"] == key_field["id"]
        finally:
            table.set_key_field(
                original_key_id, app_token=os.environ.get("QUICKBASE_APP_TOKEN") or None
            )
        assert table.get_details()["keyFieldId"] == original_key_id

        stage = "delete fields"
        field.delete()
        table.delete_fields([key_field["id"], rich_text["id"]])
        remaining_ids = {item["id"] for item in table.list_fields()}
        assert created_field["id"] not in remaining_ids
        assert key_field["id"] not in remaining_ids
        assert rich_text["id"] not in remaining_ids
    except QuickbaseError as exc:
        raise pytest.fail.Exception(
            f"Live phase '{stage}' failed: {_failure_details(exc)}.", pytrace=False
        ) from None
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        raise pytest.fail.Exception(
            f"Live phase '{stage}' failed: {type(exc).__name__}.", pytrace=False
        ) from None
    finally:
        try:
            if table is not None:
                try:
                    table.delete()
                    assert table.id not in {item["id"] for item in app.list_tables()}
                except QuickbaseError as exc:
                    raise pytest.fail.Exception(
                        f"Live cleanup failed for table {table.id}: {_failure_details(exc)}.",
                        pytrace=False,
                    ) from None
        finally:
            client.session.close()
