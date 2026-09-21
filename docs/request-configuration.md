# Request Configuration

`RequestConfig` controls request timeouts, retries, backoff, and sanitized logging hooks for
`QuickBaseStructureClient`.

## Defaults

```python
from quickbase_structure_client import RequestConfig

config = RequestConfig()
```

The current defaults are:

| Setting | Default | Meaning |
|---|---:|---|
| `timeout` | `(3.0, 25.0)` | Connect and read timeout in seconds |
| `retry_count` | `2` | Retries after the initial request |
| `retryable_status_codes` | `429, 502, 503, 504` | HTTP responses retried automatically |
| `backoff_factor` | `0.5` | Base exponential backoff delay in seconds |
| `jitter` | `0.25` | Maximum random delay added to backoff |
| `respect_retry_after` | `True` | Honor a valid `Retry-After` response header |
| `request_log_hook` | `None` | Optional sanitized request event callback |
| `response_log_hook` | `None` | Optional sanitized response event callback |

`retry_count=2` permits up to three total attempts.

## Customize Requests

```python
from quickbase_structure_client import Auth, QuickBaseStructureClient, RequestConfig

request_config = RequestConfig(
    timeout=(5.0, 60.0),
    retry_count=4,
    backoff_factor=1.0,
    jitter=0.1,
)

client = QuickBaseStructureClient(
    Auth("example.quickbase.com", "user-token"),
    request_config=request_config,
    auto_backup=False,
)
```

`timeout` may be a positive number or a positive `(connect, read)` pair. Invalid timeout,
retry, backoff, jitter, status-code, or hook values raise `QuickbaseConfigurationError` during
configuration.

## Retry Behavior

The request layer retries:

- Responses whose status code is in `retryable_status_codes`.
- `requests.Timeout`.
- `requests.ConnectionError` and other `requests.RequestException` transport failures.

When Quickbase provides a valid `Retry-After` value and `respect_retry_after=True`, that delay
takes precedence over exponential backoff. Otherwise, the delay is:

```text
backoff_factor * (2 ** (failed_attempt - 1)) + random_jitter
```

REST responses with a status code below 400 pass the HTTP success check.
XML responses must also contain a successful `errcode`.
Terminal failures are translated to package exceptions:

| Condition | Exception |
|---|---|
| HTTP 401 | `QuickbaseAuthError` |
| HTTP 403 | `QuickbasePermissionError` |
| HTTP 404 | `QuickbaseNotFoundError` |
| HTTP 429 | `QuickbaseRateLimitError` |
| Other HTTP errors | `QuickbaseHTTPError` |
| Exhausted timeout or connection retries | `QuickbaseTransportError` |

`QuickbasePermissionError` derives from `QuickbaseAuthError`, so existing authentication error
handlers remain compatible. Package exceptions expose a `context` dictionary with structured
details such as the endpoint and status code. Wrapper exceptions may also expose the translated
exception through `cause`.

## Logging Hooks

Use hooks to send request lifecycle events to an application logger or metrics system:

```python
import logging

from quickbase_structure_client import RequestConfig

log = logging.getLogger("quickbase.requests")


def log_request(event: dict[str, object]) -> None:
    log.info("Quickbase request", extra={"quickbase_event": event})


def log_response(event: dict[str, object]) -> None:
    log.info("Quickbase response", extra={"quickbase_event": event})


config = RequestConfig(
    request_log_hook=log_request,
    response_log_hook=log_response,
)
```

Request events include method, endpoint, URL, attempt number, timeout, sanitized headers, and a
structural payload summary. Response events include status, attempt number, sanitized headers,
and retry information.

Sensitive headers such as `Authorization`, cookies, proxy authorization, and API keys are
redacted. Payload values are not included. Dictionaries report keys, lists report item counts,
and QBL strings report only character counts.

Hook failures are logged as warnings and do not interrupt the Quickbase operation.

## Custom Sessions

Supply a `requests.Session` to control adapters, proxies, certificates, or test transport:

```python
import requests

from quickbase_structure_client import Auth, QuickBaseStructureClient

session = requests.Session()
session.verify = "/path/to/corporate-ca.pem"

client = QuickBaseStructureClient(
    Auth("example.quickbase.com", "user-token"),
    session=session,
    auto_backup=False,
)
```

The client adds its authentication headers to the supplied session. Avoid placing credentials
in debug output or custom hooks.

## Direct Requests

Resource wrappers should be preferred because they preserve endpoint, payload, and backup
behavior. The low-level method remains available for endpoints already understood by the
caller:

```python
response = client.request(
    method="GET",
    endpoint="/apps/b12345678",
)
```

Endpoints must begin with `/`. Dictionary and list payloads are sent as JSON. String and byte
payloads are sent as raw request data, which is required for QBL documents.

XML requests use a separate mode. With `xml_action=`, the client sends an XML body to the
authenticated realm instead of the REST `base_url`.
The supported actions are `API_SetKeyField` and `API_SetFieldProperties`.
The endpoint identifies the table as `/db/{table_id}`.
The client adds the user token, escapes XML values, and uses the `QUICKBASE-ACTION` header.
An optional `app_token` supplies an application token.
The normal timeout, retry, logging, and backup behavior still applies.
XML errors omit response body previews to protect user tokens and application tokens.
Use the [XML wrappers](api-reference.md#xml-field-updates) for supported field and table operations.

For a mutating direct request, pass `app_id_for_backup` only when the operation should
participate in automatic backup orchestration:

```python
response = client.request(
    method="POST",
    endpoint="/tables/b23456789?appId=b12345678",
    payload={"description": "Managed table."},
    app_id_for_backup="b12345678",
)
```

For an operation that changes multiple apps, pass `app_ids_for_backup` with every affected app ID.
All pre-change backups complete before the mutation. Post-change backups follow a successful response.
If a post-change backup fails, the client still attempts the remaining backups.
It then raises `QuickbaseBackupError` with the failed application IDs in its context.
The mutation has already succeeded at this point.
`SolutionsManager.update_solution` uses this argument for QBL updates.

`solution_id_for_backup` overrides the global Solution ID for schema backups of one request.
The backup state preserves this target for the post-change export.
`SolutionsManager.update_solution` supplies its target Solution ID automatically.
`preview_solution_changes` sends no backup context, so its read-only `PUT` does not create backups.
