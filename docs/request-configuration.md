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

Successful responses have a status code below 400. Terminal failures are translated to package
exceptions:

| Condition | Exception |
|---|---|
| HTTP 401 or 403 | `QuickbaseAuthError` |
| HTTP 404 | `QuickbaseNotFoundError` |
| HTTP 429 | `QuickbaseRateLimitError` |
| Other HTTP errors | `QuickbaseHTTPError` |
| Exhausted timeout or connection retries | `QuickbaseTransportError` |

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
    endpoint="/apps/app-id",
)
```

Endpoints must begin with `/`. Dictionary and list payloads are sent as JSON. String and byte
payloads are sent as raw request data, which is required for QBL documents.

For a mutating direct request, pass `app_id_for_backup` only when the operation should
participate in automatic backup orchestration:

```python
response = client.request(
    method="POST",
    endpoint="/tables/table-id?appId=app-id",
    payload={"description": "Managed table."},
    app_id_for_backup="app-id",
)
```
