from __future__ import annotations

from unittest.mock import Mock

import pytest

from . import test_live_structure as live


@pytest.mark.parametrize("gate", [None, "0", "true"])
def test_live_tests_do_not_load_credentials_without_explicit_gate(
    monkeypatch: pytest.MonkeyPatch, gate: str | None
) -> None:
    monkeypatch.delenv("QUICKBASE_RUN_INTEGRATION_TESTS", raising=False)
    if gate is not None:
        monkeypatch.setenv("QUICKBASE_RUN_INTEGRATION_TESTS", gate)
    load_credentials = Mock()
    create_client = Mock()
    monkeypatch.setattr(live, "load_dotenv", load_credentials)
    monkeypatch.setattr(live, "QuickBaseStructureClient", create_client)

    with pytest.raises(pytest.skip.Exception):
        live._live_client()

    load_credentials.assert_not_called()
    create_client.assert_not_called()


@pytest.mark.parametrize("missing", ["QUICKBASE_TEST_APP_ID", "QUICKBASE_TEST_REALM_HOSTNAME"])
def test_live_tests_require_targets_before_loading_credentials(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.setenv("QUICKBASE_RUN_INTEGRATION_TESTS", "1")
    monkeypatch.setenv("QUICKBASE_TEST_APP_ID", "app1")
    monkeypatch.setenv("QUICKBASE_TEST_REALM_HOSTNAME", "test.quickbase.com")
    monkeypatch.delenv(missing)
    load_credentials = Mock()
    create_client = Mock()
    monkeypatch.setattr(live, "load_dotenv", load_credentials)
    monkeypatch.setattr(live, "QuickBaseStructureClient", create_client)

    with pytest.raises(pytest.fail.Exception, match="explicitly"):
        live._live_client()

    load_credentials.assert_not_called()
    create_client.assert_not_called()


def test_live_tests_reject_credential_realm_mismatch_before_creating_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUICKBASE_RUN_INTEGRATION_TESTS", "1")
    monkeypatch.setenv("QUICKBASE_TEST_APP_ID", "app1")
    monkeypatch.setenv("QUICKBASE_TEST_REALM_HOSTNAME", "test.quickbase.com")
    monkeypatch.setenv("QUICKBASE_REALM_HOSTNAME", "different.quickbase.com")
    monkeypatch.setenv("QUICKBASE_USER_TOKEN", "test-token")
    monkeypatch.setattr(live, "load_dotenv", Mock())
    create_client = Mock()
    monkeypatch.setattr(live, "QuickBaseStructureClient", create_client)

    with pytest.raises(pytest.fail.Exception, match="does not match"):
        live._live_client()

    create_client.assert_not_called()
