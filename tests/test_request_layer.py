from __future__ import annotations

from unittest.mock import Mock

import pytest
import requests

import quickbase_structure_client.quickbase_api as quickbase_api_module
from quickbase_structure_client import __version__
from quickbase_structure_client.exceptions import (
    QuickbaseAuthError,
    QuickbaseConfigurationError,
    QuickbasePermissionError,
    QuickbaseTransportError,
)
from quickbase_structure_client.quickbase_api import (
    Auth,
    QuickBaseStructureClient,
    RequestConfig,
    normalize_realm_hostname,
    normalize_user_token,
)

from .conftest import FakeResponse


def test_public_version_matches_default_user_agent() -> None:
    assert __version__ == "0.1.5"
    assert quickbase_api_module.DEFAULT_USER_AGENT["Version"] == __version__


def test_auth_normalizes_realm_hostname_and_user_token_prefix() -> None:
    auth = Auth(
        "https://example.quickbase.com/",
        "  QB-USER-TOKEN abc123  ",
    )

    assert auth.realm == "example.quickbase.com"
    assert auth.user_token == "abc123"
    assert auth.headers["QB-Realm-Hostname"] == "example.quickbase.com"
    assert auth.headers["Authorization"] == "QB-USER-TOKEN abc123"


def test_auth_normalization_helpers_are_available() -> None:
    assert normalize_realm_hostname("http://example.quickbase.com/") == "example.quickbase.com"
    assert normalize_user_token("qb-user-token token-value") == "token-value"


@pytest.mark.parametrize(
    ("realm", "user_token", "message"),
    [
        ("", "real-token", "realm hostname"),
        ("example.quickbase.com", "QB-USER-TOKEN", "user token"),
    ],
)
def test_auth_rejects_empty_normalized_credentials(
    realm: str,
    user_token: str,
    message: str,
) -> None:
    with pytest.raises(QuickbaseConfigurationError, match=message):
        Auth(realm, user_token)


def test_request_retries_retryable_status_and_passes_extra_headers(monkeypatch) -> None:
    delays: list[float] = []
    monkeypatch.setattr(quickbase_api_module.time, "sleep", delays.append)

    api = QuickBaseStructureClient(
        Auth("example.quickbase.com", "token"),
        request_config=RequestConfig(retry_count=1, backoff_factor=0.5, jitter=0.0),
        auto_backup=False,
    )
    request_mock = Mock(
        side_effect=[
            FakeResponse(status_code=503, text="unavailable"),
            FakeResponse(status_code=200, text="ok"),
        ]
    )
    monkeypatch.setattr(api.session, "request", request_mock)

    response = api.request(
        method="GET",
        endpoint="/solutions/abc",
        headers={"QBL-Version": "0.9"},
    )

    assert response.status_code == 200
    assert request_mock.call_count == 2
    assert delays == [0.5]
    assert request_mock.call_args.kwargs["headers"] == {"QBL-Version": "0.9"}


def test_request_uses_retry_after_for_rate_limit(monkeypatch) -> None:
    delays: list[float] = []
    monkeypatch.setattr(quickbase_api_module.time, "sleep", delays.append)

    api = QuickBaseStructureClient(
        Auth("example.quickbase.com", "token"),
        request_config=RequestConfig(retry_count=1, backoff_factor=0.5, jitter=0.0),
        auto_backup=False,
    )
    request_mock = Mock(
        side_effect=[
            FakeResponse(status_code=429, text="rate limited", headers={"Retry-After": "4"}),
            FakeResponse(status_code=200),
        ]
    )
    monkeypatch.setattr(api.session, "request", request_mock)

    api.request(method="GET", endpoint="/apps/app1")

    assert delays == [4.0]


def test_request_retries_connection_errors_then_raises_transport_error(monkeypatch) -> None:
    delays: list[float] = []
    monkeypatch.setattr(quickbase_api_module.time, "sleep", delays.append)

    api = QuickBaseStructureClient(
        Auth("example.quickbase.com", "token"),
        request_config=RequestConfig(retry_count=1, backoff_factor=0.25, jitter=0.0),
        auto_backup=False,
    )
    monkeypatch.setattr(
        api.session,
        "request",
        Mock(side_effect=requests.ConnectionError("socket closed")),
    )

    with pytest.raises(QuickbaseTransportError, match="transport/connection"):
        api.request(method="GET", endpoint="/apps/app1")

    assert delays == [0.25]


def test_request_logging_hooks_redact_auth_and_summarize_payload(monkeypatch) -> None:
    request_events: list[dict] = []
    response_events: list[dict] = []
    api = QuickBaseStructureClient(
        Auth("example.quickbase.com", "secret-token"),
        request_config=RequestConfig(
            retry_count=0,
            jitter=0.0,
            request_log_hook=request_events.append,
            response_log_hook=response_events.append,
        ),
        auto_backup=False,
    )
    monkeypatch.setattr(api.session, "request", Mock(return_value=FakeResponse()))

    api.request(
        method="POST",
        endpoint="/app/app1/trustees",
        payload=[{"id": "user@example.com", "type": "user"}],
    )

    assert request_events[0]["headers"]["Authorization"] == "<redacted>"
    assert request_events[0]["payload_summary"] == {"type": "list", "item_count": 1}
    assert "secret-token" not in repr(request_events[0])
    assert response_events[0]["will_retry"] is False


def test_request_sends_string_payload_as_raw_data(monkeypatch) -> None:
    request_events: list[dict] = []
    api = QuickBaseStructureClient(
        Auth("example.quickbase.com", "token"),
        request_config=RequestConfig(
            retry_count=0,
            request_log_hook=request_events.append,
        ),
        auto_backup=False,
    )
    request_mock = Mock(return_value=FakeResponse({"id": "solution1"}))
    monkeypatch.setattr(api.session, "request", request_mock)
    qbl = "Version: 0.2\nResources: {}\n"

    api.request(
        method="POST",
        endpoint="/solutions",
        payload=qbl,
        headers={"Content-Type": "application/x-yaml"},
    )

    assert request_mock.call_args.kwargs["data"] == qbl
    assert "json" not in request_mock.call_args.kwargs
    assert request_events[0]["payload_summary"] == {
        "type": "str",
        "character_count": len(qbl),
    }


def test_http_error_redacts_user_token_from_response_body(monkeypatch) -> None:
    user_token = "sensitive-user-token"
    api = QuickBaseStructureClient(
        Auth("example.quickbase.com", user_token),
        request_config=RequestConfig(retry_count=0, jitter=0.0),
        auto_backup=False,
    )
    monkeypatch.setattr(
        api.session,
        "request",
        Mock(
            return_value=FakeResponse(
                status_code=401,
                text=f"Quickbase rejected {user_token}.",
            )
        ),
    )

    with pytest.raises(QuickbaseAuthError) as exc_info:
        api.request(method="GET", endpoint="/apps/app1")

    assert "rejected authentication" in str(exc_info.value)
    assert exc_info.value.context["status_code"] == 401
    assert user_token not in str(exc_info.value)
    assert "<redacted>" in str(exc_info.value)


def test_http_403_raises_permission_error_with_context(monkeypatch) -> None:
    api = QuickBaseStructureClient(
        Auth("example.quickbase.com", "token"),
        request_config=RequestConfig(retry_count=0, jitter=0.0),
        auto_backup=False,
    )
    monkeypatch.setattr(
        api.session,
        "request",
        Mock(
            return_value=FakeResponse(
                status_code=403,
                text='{"message":"Insufficient permissions"}',
            )
        ),
    )

    with pytest.raises(QuickbasePermissionError) as exc_info:
        api.request(method="GET", endpoint="/tables/table1/relationships")

    assert isinstance(exc_info.value, QuickbaseAuthError)
    assert "denied access" in str(exc_info.value)
    assert isinstance(exc_info.value.cause, requests.HTTPError)
    assert exc_info.value.context == {
        "operation": "QuickBaseStructureClient.request",
        "endpoint": "/tables/table1/relationships",
        "method": "GET",
        "status_code": 403,
        "attempts": 1,
        "retry_count": 0,
        "retry_after": None,
        "response_body": '{"message":"Insufficient permissions"}',
    }


def test_clone_backup_is_suppressed_during_backup_operations(monkeypatch) -> None:
    api = QuickBaseStructureClient(
        Auth("example.quickbase.com", "token"),
        request_config=RequestConfig(retry_count=0, jitter=0.0),
        auto_backup=True,
        backup_method="clone",
    )
    request_mock = Mock(
        side_effect=[
            FakeResponse({"id": "pre-clone"}),
            FakeResponse({"id": "created-table"}),
            FakeResponse({"id": "post-clone"}),
        ]
    )
    monkeypatch.setattr(api.session, "request", request_mock)

    response = api.request(
        method="POST",
        endpoint="/tables?appId=app1",
        payload={"name": "Orders"},
        app_id_for_backup="app1",
    )

    assert response.json() == {"id": "created-table"}
    urls = [call.args[1] for call in request_mock.call_args_list]
    assert urls == [
        "https://api.quickbase.com/v1/apps/app1/copy",
        "https://api.quickbase.com/v1/tables?appId=app1",
        "https://api.quickbase.com/v1/apps/app1/copy",
    ]
