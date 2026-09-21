# Development

This guide covers local setup, repository structure, validation, and contribution constraints.
Read the root [AGENTS.md](../AGENTS.md) before changing code.

## Setup

The package supports Python 3.10 and later. Use the repository virtual environment when it
exists:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

The development extras install pytest, coverage, Ruff, mypy, request type stubs, and dotenv
support used by local workflows. Install `build` separately when creating distributions:

```powershell
.\.venv\Scripts\python.exe -m pip install build
```

## Repository Layout

| Path | Responsibility |
|---|---|
| `src/quickbase_structure_client/quickbase_api.py` | Authentication, requests, retries, logging, error mapping |
| `src/quickbase_structure_client/app.py` | Application, table, trustee, and role entry points |
| `src/quickbase_structure_client/table.py` | Table, field, and relationship operations |
| `src/quickbase_structure_client/field.py` | Bound field operations |
| `src/quickbase_structure_client/relationship.py` | Bound relationship operations |
| `src/quickbase_structure_client/trustees.py` | Trustee validation and requests |
| `src/quickbase_structure_client/solutions.py` | Solutions and QBL operations |
| `src/quickbase_structure_client/schema_exporter.py` | Schema compilation and rendering |
| `src/quickbase_structure_client/tools/backup_manager.py` | Pre-change and post-change backups |
| `src/quickbase_structure_client/exceptions.py` | Package exception hierarchy |
| `tests/` | Mock-based unit tests and gated live tests |
| `examples/` | Schema export and PTO demo commands |
| `docs/` | Long-form user and developer documentation |

The public package surface is defined in
`src/quickbase_structure_client/__init__.py`.

## Validation

Run the narrowest relevant test while iterating. Before considering a change complete, match
CI:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -m "not integration"
.\.venv\Scripts\python.exe -m ruff check src tests examples
.\.venv\Scripts\python.exe -m mypy src tests examples
.\.venv\Scripts\python.exe -m pytest tests `
  --cov=quickbase_structure_client `
  --cov-report=term-missing `
  -m "not integration"
```

If the Windows environment cannot use pytest's default temporary directory, append:

```powershell
--basetemp build/pytest-temp
```

Branch coverage must remain at or above 70 percent.

## Test Isolation

Normal tests must not contact Quickbase. Use:

- `RecordingClient` and `FakeResponse` from `tests/conftest.py` for wrapper composition.
- Monkeypatched `requests.Session` methods for request behavior.
- Monkeypatched sleep and randomness for deterministic retry tests.
- `tmp_path` for generated files.

Integration tests require the `integration` marker and an explicit environment-variable gate.
Normal CI sets `QUICKBASE_RUN_INTEGRATION_TESTS=0`.

For resource wrapper changes, assert the HTTP method, endpoint, payload, headers, and
`app_id_for_backup`.

### Live Field and Table Tests

[`tests/test_live_structure.py`](../tests/test_live_structure.py) covers REST table and field
operations, XML field properties, and XML key-field changes. It creates,
changes, and deletes its own uniquely named test table. It also changes and restores that
table's key field. The test disables automatic backups and clone fallback. This test file
does not cover Solutions or QBL operations.

Use a disposable application that you have permission to change. Put its realm and token in
the Git-ignored `.env` file, using `QUICKBASE_REALM_HOSTNAME` and `QUICKBASE_USER_TOKEN`.
Use a token that can access only the test application.
If the application requires an app token, set `QUICKBASE_APP_TOKEN` in `.env` for the XML calls.

Set all three variables in the PowerShell session before the test. Replace the sample realm
and application ID with your approved targets.

```powershell
$env:QUICKBASE_RUN_INTEGRATION_TESTS = "1"
$env:QUICKBASE_TEST_REALM_HOSTNAME = "your-realm.quickbase.com"
$env:QUICKBASE_TEST_APP_ID = "b12345678"
try {
    .\.venv\Scripts\python.exe -m pytest tests/test_live_structure.py -m integration -q
}
finally {
    Remove-Item Env:QUICKBASE_RUN_INTEGRATION_TESTS
}
```

The test requires these variables before it reads `.env`. The credential realm must match
the explicit test realm. OS environment variables override values from `.env`.

Cleanup runs even if a test phase fails. If cleanup fails, the error includes the test table
ID for manual cleanup. An interrupted process can also leave its test table behind.

## Implementation Constraints

- Preserve the synchronous `requests` API unless a task explicitly changes the contract.
- Keep HTTP transport in `QuickBaseStructureClient.request(...)`.
- Pass mapping and list payloads as JSON.
- Pass QBL strings as raw data.
- Preserve parent IDs on app, table, field, and relationship wrappers.
- Supply `app_id_for_backup` for structural mutations with application context.
- Validate caller input before issuing requests.
- Raise package exceptions instead of leaking raw `requests` exceptions.
- Keep request logs and hooks free of credentials and raw sensitive payloads.
- Do not add dependencies or abstractions without a concrete requirement.

Quickbase payload assumptions must be verified against tests or authoritative Quickbase API
documentation.

## Documentation

Update documentation in the same change as user-visible behavior:

- Keep the root README concise.
- Put detailed guides in `docs/`.
- Add or remove pages in `docs/index.md`.
- Update examples when the recommended workflow changes.
- Record notable changes under `Unreleased` in `CHANGELOG.md`.

Use Google-style docstrings for public Python APIs and keep them synchronized with behavior.

## Release Build

Build source and wheel distributions:

```powershell
.\.venv\Scripts\python.exe -m build --sdist --wheel
```

Do not edit generated files under `build/`, `dist/`, or `*.egg-info/`.

When changing a release version, keep these values synchronized:

- `pyproject.toml`
- `quickbase_api.DEFAULT_USER_AGENT`
- `quickbase_structure_client.__version__`

Publishing is handled by the GitHub release workflow and PyPI trusted publishing.
