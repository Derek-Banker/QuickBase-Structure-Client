from __future__ import annotations

import logging
import traceback
from typing import Any, Literal, cast
from unittest.mock import Mock
from xml.etree import ElementTree
from xml.sax.saxutils import escape

import pytest
import requests

from quickbase_structure_client.exceptions import (
    QuickbaseAuthError,
    QuickbaseBackupError,
    QuickbaseError,
    QuickbaseHTTPError,
    QuickbaseNotFoundError,
    QuickbasePayloadError,
    QuickbasePermissionError,
    QuickbaseValidationError,
)
from quickbase_structure_client.quickbase_api import Auth, QuickBaseStructureClient, RequestConfig

from .conftest import FakeResponse


def _client(
    response: FakeResponse,
    *,
    user_token: str = "test-user-token",
    realm: str = "example.quickbase.com",
    request_config: RequestConfig | None = None,
) -> tuple[QuickBaseStructureClient, Mock, Mock]:
    """Create a client whose network and backup operations are isolated mocks."""
    session = Mock(spec=requests.Session)
    session.headers = {}
    session.request.return_value = response
    api = QuickBaseStructureClient(
        Auth(realm, user_token),
        session=cast(requests.Session, session),
        request_config=request_config or RequestConfig(retry_count=0),
        auto_backup=True,
    )
    backup = Mock()
    backup.trigger_pre_backup.side_effect = lambda app_id, **kwargs: f"state:{app_id}"
    api.backup_manager = cast(Any, backup)
    return api, session, backup


def _xml_success(action: str = "API_SetFieldProperties") -> FakeResponse:
    return FakeResponse(
        text=f"<qdbapi><action>{action}</action><errcode>0</errcode><fid>7</fid></qdbapi>"
    )


def test_xml_field_wrapper_sends_escaped_utf8_to_realm_with_backups() -> None:
    api, session, backup = _client(_xml_success(), user_token="test-user<&>token")
    options = {
        "label": "Café <&> costs",
        "doesdatacopy": False,
        "choices": ["Été & automne", "<winter>"],
        "decimal_places": "",
    }

    result = api.table("table1", app_id="app1").field(7).update_xml(
        options, app_token="test-app<&>token"
    )

    assert result == {"action": "API_SetFieldProperties", "errcode": "0", "fid": "7"}
    session.request.assert_called_once()
    assert session.request.call_args.args == ("POST", "https://example.quickbase.com/db/table1")
    arguments = session.request.call_args.kwargs
    assert arguments["headers"] == {
        "Content-Type": "application/xml",
        "QUICKBASE-ACTION": "API_SetFieldProperties",
        "X_QUICKBASE_RETURN_HTTP_ERROR": "true",
    }
    assert arguments["allow_redirects"] is False
    assert arguments["timeout"] == api.request_config.timeout
    assert "json" not in arguments
    assert isinstance(arguments["data"], bytes)
    assert b"Caf\xc3\xa9" in arguments["data"]
    assert b"&lt;&amp;&gt;" in arguments["data"]
    root = ElementTree.fromstring(arguments["data"])
    assert root.findtext("usertoken") == "test-user<&>token"
    assert root.findtext("apptoken") == "test-app<&>token"
    assert root.findtext("fid") == "7"
    assert root.findtext("label") == options["label"]
    assert root.findtext("doesdatacopy") == "0"
    assert root.findtext("decimal_places") == ""
    assert [choice.text for choice in root.findall("choices/choice")] == options["choices"]
    backup.trigger_pre_backup.assert_called_once_with("app1")
    backup.trigger_post_backup.assert_called_once_with("state:app1")


def test_xml_key_wrapper_omits_optional_app_token() -> None:
    api, session, _ = _client(_xml_success("API_SetKeyField"))

    result = api.table("table1", app_id="app1").set_key_field("007")

    assert result["errcode"] == "0"
    root = ElementTree.fromstring(session.request.call_args.kwargs["data"])
    assert root.findtext("fid") == "7"
    assert root.find("apptoken") is None
    assert session.request.call_args.kwargs["headers"]["QUICKBASE-ACTION"] == "API_SetKeyField"


@pytest.mark.parametrize("status_code", [200, 400])
@pytest.mark.parametrize(
    ("code", "error_type"),
    [
        (20, QuickbaseAuthError),
        (22, QuickbaseAuthError),
        (24, QuickbaseAuthError),
        (3, QuickbasePermissionError),
        (30, QuickbaseNotFoundError),
        (31, QuickbaseNotFoundError),
        (32, QuickbaseNotFoundError),
        (2, QuickbaseHTTPError),
    ],
)
def test_xml_error_maps_package_exception_without_post_backup(
    code: int, error_type: type[QuickbaseError], status_code: int
) -> None:
    response = FakeResponse(
        status_code=status_code,
        text=f"<qdbapi><errcode>{code}</errcode><errtext>Remote details</errtext></qdbapi>",
    )
    api, session, backup = _client(response)

    with pytest.raises(error_type) as captured:
        api.table("table1", app_id="app1").set_key_field(7)

    assert type(captured.value) is error_type
    assert captured.value.context["xml_error_code"] == code
    assert "Remote details" not in str(captured.value)
    session.request.assert_called_once()
    backup.trigger_pre_backup.assert_called_once_with("app1")
    backup.trigger_post_backup.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        "<qdbapi>",
        "<qdbapi/>",
        "<different><errcode>0</errcode></different>",
        "<qdbapi><errcode>0</errcode><errcode>3</errcode></qdbapi>",
        "<qdbapi><errcode>unknown</errcode></qdbapi>",
        "<qdbapi><errcode>" + "9" * 5000 + "</errcode></qdbapi>",
        '<!DOCTYPE qdbapi [<!ENTITY data "secret">]><qdbapi><errcode>0</errcode></qdbapi>',
    ],
    ids=["malformed", "missing-code", "wrong-root", "duplicate", "nonnumeric", "large", "entity"],
)
def test_xml_invalid_response_stops_before_post_backup(body: str) -> None:
    api, session, backup = _client(FakeResponse(text=body))

    with pytest.raises(QuickbasePayloadError):
        api.table("table1", app_id="app1").set_key_field(7)

    session.request.assert_called_once()
    backup.trigger_post_backup.assert_not_called()


def test_xml_wrong_response_action_stops_before_post_backup() -> None:
    api, _, backup = _client(_xml_success("API_SetFieldProperties"))

    with pytest.raises(QuickbaseHTTPError, match="unexpected action"):
        api.table("table1", app_id="app1").set_key_field(7)

    backup.trigger_post_backup.assert_not_called()


def test_xml_redirect_is_not_followed_or_treated_as_success() -> None:
    api, session, backup = _client(
        FakeResponse(status_code=302, headers={"Location": "https://different.example/db/table1"})
    )

    with pytest.raises(QuickbaseHTTPError, match="redirects"):
        api.table("table1", app_id="app1").set_key_field(7)

    session.request.assert_called_once()
    assert session.request.call_args.kwargs["allow_redirects"] is False
    backup.trigger_post_backup.assert_not_called()


def test_xml_malformed_http_error_uses_status_without_response_body() -> None:
    private_response = "A gateway returned a private error instead of XML."
    api, session, backup = _client(FakeResponse(status_code=400, text=private_response))

    with pytest.raises(QuickbaseHTTPError) as captured:
        api.table("table1", app_id="app1").set_key_field(7)

    assert type(captured.value) is QuickbaseHTTPError
    assert captured.value.context["status_code"] == 400
    assert captured.value.context["response_body"] is None
    assert "xml_error_code" not in captured.value.context
    assert private_response not in str(captured.value)
    session.request.assert_called_once()
    backup.trigger_post_backup.assert_not_called()


def test_xml_retryable_http_status_retries_before_mapping_xml_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []
    monkeypatch.setattr("quickbase_structure_client.quickbase_api.time.sleep", delays.append)
    success = _xml_success("API_SetKeyField")
    api, session, backup = _client(
        success,
        request_config=RequestConfig(retry_count=1, backoff_factor=0.25, jitter=0.0),
    )
    session.request.side_effect = [
        FakeResponse(status_code=503, text="<qdbapi><errcode>3</errcode></qdbapi>"),
        success,
    ]

    result = api.table("table1", app_id="app1").set_key_field(7)

    assert result["errcode"] == "0"
    assert session.request.call_count == 2
    assert delays == [0.25]
    backup.trigger_pre_backup.assert_called_once_with("app1")
    backup.trigger_post_backup.assert_called_once_with("state:app1")


@pytest.mark.parametrize("status_code", [200, 400])
def test_xml_errors_and_logs_do_not_expose_tokens_or_response_contents(
    status_code: int, caplog: pytest.LogCaptureFixture
) -> None:
    user_token, app_token = "secret-user<&>token", "secret-app<&>token"
    private_value = "private field label"
    events: list[dict[str, Any]] = []
    body = (
        "<qdbapi><errcode>24</errcode><errtext>"
        f"{escape(user_token)} {escape(app_token)} {private_value}"
        "</errtext></qdbapi>"
    )
    api, _, backup = _client(
        FakeResponse(status_code=status_code, text=body),
        user_token=user_token,
        request_config=RequestConfig(
            retry_count=0, request_log_hook=events.append, response_log_hook=events.append
        ),
    )

    with caplog.at_level(logging.DEBUG), pytest.raises(QuickbaseHTTPError) as captured:
        api.table("table1", app_id="app1").field(7).update_xml(
            {"label": private_value}, app_token=app_token
        )

    visible = repr(events) + caplog.text + repr(captured.value.context)
    visible += "".join(traceback.format_exception(captured.value))
    for secret in (user_token, app_token, escape(user_token), escape(app_token), private_value):
        assert secret not in visible
    assert len(events) == 2
    assert events[0]["headers"]["Authorization"] == "<redacted>"
    assert events[0]["payload_summary"]["type"] == "str"
    backup.trigger_post_backup.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        {"method": "GET"},
        {"endpoint": "/db/table1?redirect=elsewhere"},
        {"payload": "<qdbapi/>"},
        {"xml_action": "API_DeleteDatabase"},
        {"payload": {"fid": 7, "usertoken": "replacement"}},
        {"payload": {"fid": 7, "label": "unexpected for key changes"}},
        {"payload": {"fid": 0}},
        {"payload": {"fid": 7}, "app_token": " "},
        {"xml_action": None, "app_token": "unexpected for REST"},
        {
            "xml_action": "API_SetFieldProperties",
            "payload": {"fid": 7, "label": "invalid\x00character"},
        },
    ],
)
def test_xml_invalid_arguments_fail_before_backups_and_network(overrides: dict[str, Any]) -> None:
    api, session, backup = _client(_xml_success())
    arguments: dict[str, Any] = {
        "method": "POST",
        "endpoint": "/db/table1",
        "payload": {"fid": 7},
        "xml_action": "API_SetKeyField",
        "app_id_for_backup": "app1",
    }
    arguments.update(overrides)

    with pytest.raises(QuickbaseValidationError):
        api.request(**arguments)

    session.request.assert_not_called()
    backup.trigger_pre_backup.assert_not_called()
    backup.trigger_post_backup.assert_not_called()


def test_xml_invalid_realm_fails_before_backups_and_network() -> None:
    api, session, backup = _client(_xml_success(), realm="example.quickbase.com/other")

    with pytest.raises(QuickbaseValidationError, match="realm hostname"):
        api.table("table1", app_id="app1").set_key_field(7)

    session.request.assert_not_called()
    backup.trigger_pre_backup.assert_not_called()


def test_multi_app_request_backs_up_all_apps_before_and_after_one_request() -> None:
    response = FakeResponse({"solutionId": "solution1"})
    api, session, backup = _client(response)
    events: list[str] = []

    def pre_backup(app_id: str) -> str:
        events.append(f"pre:{app_id}")
        return app_id

    def send_request(*args: Any, **kwargs: Any) -> FakeResponse:
        events.append("request")
        return response

    backup.trigger_pre_backup.side_effect = pre_backup
    backup.trigger_post_backup.side_effect = lambda state: events.append(f"post:{state}")
    session.request.side_effect = send_request
    qbl = "Version: 0.12\nResources: {}\n"
    app_ids = ["app1", "app2", "app1"]

    result = api.request(
        method="PUT", endpoint="/solutions/solution1", payload=qbl, app_ids_for_backup=app_ids
    )

    assert result is response
    assert events == ["pre:app1", "pre:app2", "request", "post:app1", "post:app2"]
    assert app_ids == ["app1", "app2", "app1"]
    assert session.request.call_args.kwargs["data"] == qbl
    assert "json" not in session.request.call_args.kwargs
    assert "allow_redirects" not in session.request.call_args.kwargs


def test_multi_app_failed_request_does_not_run_post_backups() -> None:
    api, session, backup = _client(FakeResponse(status_code=400, text="Invalid QBL"))

    with pytest.raises(QuickbaseHTTPError):
        api.solutions.update_solution("solution1", "QBL", app_ids_for_backup=["app1", "app2"])

    assert [call.args[0] for call in backup.trigger_pre_backup.call_args_list] == ["app1", "app2"]
    session.request.assert_called_once()
    backup.trigger_post_backup.assert_not_called()


def test_multi_app_pre_backup_failure_prevents_mutation() -> None:
    api, session, backup = _client(FakeResponse())
    backup.trigger_pre_backup.side_effect = ["state:app1", QuickbaseBackupError("backup failed")]

    with pytest.raises(QuickbaseBackupError, match="backup failed"):
        api.solutions.update_solution("solution1", "QBL", app_ids_for_backup=["app1", "app2"])

    session.request.assert_not_called()
    backup.trigger_post_backup.assert_not_called()


def test_multi_app_post_backup_failure_does_not_skip_remaining_apps() -> None:
    api, session, backup = _client(FakeResponse({"solutionId": "solution1"}))
    failure = QuickbaseBackupError("First application post-backup failed.")
    backup.trigger_pre_backup.side_effect = lambda app_id, **kwargs: {"app_id": app_id}
    backup.trigger_post_backup.side_effect = [failure, None]

    with pytest.raises(QuickbaseBackupError) as captured:
        api.solutions.update_solution("solution1", "QBL", app_ids_for_backup=["app1", "app2"])

    session.request.assert_called_once()
    assert [call.args[0] for call in backup.trigger_post_backup.call_args_list] == [
        {"app_id": "app1"},
        {"app_id": "app2"},
    ]
    assert captured.value.context["failed_app_ids"] == ["app1"]
    assert captured.value.cause is failure
    assert captured.value.__cause__ is failure


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_multi_app_read_only_or_suppressed_request_skips_backups(
    method: Literal["GET", "PUT"],
) -> None:
    api, session, backup = _client(FakeResponse())

    if method == "GET":
        api.request(method=method, endpoint="/apps", app_ids_for_backup=["app1", "app2"])
    else:
        with api.suppress_auto_backup():
            api.request(
                method=method,
                endpoint="/solutions/solution1",
                payload="QBL",
                app_ids_for_backup=["app1", "app2"],
            )

    session.request.assert_called_once()
    backup.trigger_pre_backup.assert_not_called()
    backup.trigger_post_backup.assert_not_called()


@pytest.mark.parametrize(
    "backup_arguments",
    [
        {"app_ids_for_backup": "app1"},
        {"app_ids_for_backup": [""]},
        {"app_ids_for_backup": [" "]},
        {"app_ids_for_backup": [1]},
        {"app_ids_for_backup": ["app1"], "app_id_for_backup": "app2"},
        {"app_ids_for_backup": ["app1", "../app2"]},
        {"app_id_for_backup": "../app1"},
        {"app_id_for_backup": "app1?query=yes"},
        {"app_id_for_backup": 42},
        {"app_id_for_backup": "app1", "solution_id_for_backup": " "},
        {"app_id_for_backup": "app1", "solution_id_for_backup": 42},
    ],
)
def test_multi_app_invalid_backup_arguments_fail_before_side_effects(
    backup_arguments: dict[str, Any],
) -> None:
    api, session, backup = _client(FakeResponse())

    with pytest.raises(QuickbaseValidationError):
        api.request(method="PUT", endpoint="/solutions/solution1", **backup_arguments)

    session.request.assert_not_called()
    backup.trigger_pre_backup.assert_not_called()
