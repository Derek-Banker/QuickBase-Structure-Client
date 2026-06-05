from __future__ import annotations

import logging
import random
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, Literal, Mapping

import requests

from quickbase_structure_client.config import (
    BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_BACKOFF_FACTOR,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_JITTER,
    DEFAULT_RETRYABLE_STATUS_CODES,
)
from quickbase_structure_client.exceptions import (
    QuickbaseAuthError,
    QuickbaseConfigurationError,
    QuickbaseError,
    QuickbaseHTTPError,
    QuickbaseNotFoundError,
    QuickbaseRateLimitError,
    QuickbaseTransportError,
    format_error_message,
)

if TYPE_CHECKING:
    from quickbase_structure_client.app import StructureApp
    from quickbase_structure_client.table import StructureTable

logger = logging.getLogger(__name__)

# DEFAULT USER AGENT CONFIG
DEFAULT_USER_AGENT: Dict[str, str] = {
    "Base": "QuickBase-Structure-Client",
    "Version": "0.1.0",
    "Suffix": "Auth",
    "Separator": "-",
}

SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-api-key",
}
MAX_ERROR_BODY_CHARS = 500

RequestTimeout = float | tuple[float, float]
RequestLogHook = Callable[[dict[str, Any]], None]
JsonPayload = Dict[str, Any] | list[Any]
USER_TOKEN_AUTH_PREFIX = "QB-USER-TOKEN"


def _normalize_timeout(timeout: RequestTimeout) -> RequestTimeout:
    if isinstance(timeout, bool):
        raise QuickbaseConfigurationError(
            format_error_message(
                "timeout must be a positive number or a (connect, read) tuple.",
                operation="RequestConfig.__post_init__",
                timeout=timeout,
            )
        )

    if isinstance(timeout, (int, float)):
        timeout_value = float(timeout)
        if timeout_value <= 0:
            raise QuickbaseConfigurationError(
                format_error_message(
                    "timeout must be greater than zero.",
                    operation="RequestConfig.__post_init__",
                    timeout=timeout,
                )
            )
        return timeout_value

    if isinstance(timeout, (tuple, list)) and len(timeout) == 2:
        try:
            connect_timeout = float(timeout[0])
            read_timeout = float(timeout[1])
        except (TypeError, ValueError) as exc:
            raise QuickbaseConfigurationError(
                format_error_message(
                    "timeout tuple values must be numeric.",
                    operation="RequestConfig.__post_init__",
                    timeout=timeout,
                    cause=exc,
                )
            ) from exc

        if connect_timeout <= 0 or read_timeout <= 0:
            raise QuickbaseConfigurationError(
                format_error_message(
                    "timeout tuple values must be greater than zero.",
                    operation="RequestConfig.__post_init__",
                    timeout=timeout,
                )
            )
        return (connect_timeout, read_timeout)

    raise QuickbaseConfigurationError(
        format_error_message(
            "timeout must be a positive number or a (connect, read) tuple.",
            operation="RequestConfig.__post_init__",
            timeout=timeout,
        )
    )


@dataclass(frozen=True)
class RequestConfig:
    """Configuration for QuickBase request timeout, retry, and logging behavior."""

    timeout: RequestTimeout = DEFAULT_REQUEST_TIMEOUT
    retry_count: int = DEFAULT_RETRY_COUNT
    retryable_status_codes: frozenset[int] = field(
        default_factory=lambda: DEFAULT_RETRYABLE_STATUS_CODES
    )
    backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR
    jitter: float = DEFAULT_RETRY_JITTER
    respect_retry_after: bool = True
    request_log_hook: RequestLogHook | None = None
    response_log_hook: RequestLogHook | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "timeout", _normalize_timeout(self.timeout))
        try:
            retryable_status_codes = frozenset(self.retryable_status_codes)
        except TypeError as exc:
            raise QuickbaseConfigurationError(
                format_error_message(
                    "retryable_status_codes must be an iterable of HTTP status codes.",
                    operation="RequestConfig.__post_init__",
                    retryable_status_codes=self.retryable_status_codes,
                    cause=exc,
                )
            ) from exc
        object.__setattr__(self, "retryable_status_codes", retryable_status_codes)

        if (
            isinstance(self.retry_count, bool)
            or not isinstance(self.retry_count, int)
            or self.retry_count < 0
        ):
            raise QuickbaseConfigurationError(
                format_error_message(
                    "retry_count must be a non-negative integer.",
                    operation="RequestConfig.__post_init__",
                    retry_count=self.retry_count,
                )
            )

        if (
            isinstance(self.backoff_factor, bool)
            or not isinstance(self.backoff_factor, (int, float))
            or self.backoff_factor < 0
        ):
            raise QuickbaseConfigurationError(
                format_error_message(
                    "backoff_factor must be non-negative.",
                    operation="RequestConfig.__post_init__",
                    backoff_factor=self.backoff_factor,
                )
            )
        object.__setattr__(self, "backoff_factor", float(self.backoff_factor))

        if (
            isinstance(self.jitter, bool)
            or not isinstance(self.jitter, (int, float))
            or self.jitter < 0
        ):
            raise QuickbaseConfigurationError(
                format_error_message(
                    "jitter must be non-negative.",
                    operation="RequestConfig.__post_init__",
                    jitter=self.jitter,
                )
            )
        object.__setattr__(self, "jitter", float(self.jitter))

        for hook_name, hook in (
            ("request_log_hook", self.request_log_hook),
            ("response_log_hook", self.response_log_hook),
        ):
            if hook is not None and not callable(hook):
                raise QuickbaseConfigurationError(
                    format_error_message(
                        f"{hook_name} must be callable when provided.",
                        operation="RequestConfig.__post_init__",
                        hook_name=hook_name,
                        hook_type=type(hook).__name__,
                    )
                )


def assemble_user_agent(cfg: Dict[str, str]) -> str:
    final = DEFAULT_USER_AGENT.copy()
    final.update(cfg or {})
    sep = final["Separator"]
    parts = [final["Base"], final["Version"]]
    if final.get("Suffix"):
        parts.append(final["Suffix"])
    return sep.join(parts)


def normalize_realm_hostname(realm: str) -> str:
    return realm.strip().removeprefix("https://").removeprefix("http://").strip("/")


def normalize_user_token(user_token: str) -> str:
    token = user_token.strip()
    if token.upper().startswith(USER_TOKEN_AUTH_PREFIX):
        token = token[len(USER_TOKEN_AUTH_PREFIX) :].strip()
    return token


class Auth:
    """Encapsulates realm + user token and user-agent settings."""

    def __init__(
        self,
        realm: str,
        user_token: str,
        *,
        user_agent: Dict[str, str] | None = None,
    ):
        self.realm = normalize_realm_hostname(realm)
        self.user_token = normalize_user_token(user_token)
        self._user_agent = assemble_user_agent(user_agent or {})

    @property
    def user_agent(self) -> str:
        return self._user_agent

    @user_agent.setter
    def user_agent(self, cfg: Dict[str, str]):
        self._user_agent = assemble_user_agent(cfg)

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "QB-Realm-Hostname": self.realm,
            "Authorization": f"{USER_TOKEN_AUTH_PREFIX} {self.user_token}",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }

    def session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(self.headers)
        return session


class QuickBaseStructureClient:
    """
    Client for managing Quickbase app structures, tables, fields, trustees, and solutions.
    """

    def __init__(
        self,
        auth: Auth,
        base_url: str = BASE_URL,
        *,
        request_config: RequestConfig | None = None,
        session: requests.Session | None = None,
        auto_backup: bool = True,
        backup_method: Literal["schema", "clone"] = "schema",
        backup_solution_id: str | None = None,
        backup_dir: str = "backups",
        backup_fallback_to_clone: bool = True,
    ):
        self.auth = auth
        self.base_url = base_url.rstrip("/")
        self.request_config = request_config or RequestConfig()
        self.session = session or requests.Session()
        self.session.headers.update(auth.headers)

        # Backup configurations
        self.auto_backup = auto_backup
        self.backup_method = backup_method
        self.backup_solution_id = backup_solution_id
        self.backup_dir = backup_dir
        self.backup_fallback_to_clone = backup_fallback_to_clone
        self._backup_suppression_depth = 0

        # Late import binding of sub-components
        from quickbase_structure_client.app import StructureApp
        from quickbase_structure_client.schema_exporter import SchemaExporter
        from quickbase_structure_client.solutions import SolutionsManager
        from quickbase_structure_client.tools.backup_manager import BackupManager
        from quickbase_structure_client.trustees import TrusteesManager

        self.app_manager = StructureApp(self)
        self.solutions = SolutionsManager(self)
        self.exporter = SchemaExporter(self)
        self.backup_manager = BackupManager(self)
        self.trustees = TrusteesManager(self)

    def app(self, id: str, name: str | None = None) -> StructureApp:
        """Get a reference to a specific application."""
        from quickbase_structure_client.app import StructureApp
        return StructureApp(self, id=id, name=name)

    def table(
        self,
        id: str,
        *,
        app_id: str | None = None,
        name: str | None = None,
    ) -> StructureTable:
        """Get a reference to a specific table."""
        from quickbase_structure_client.table import StructureTable

        return StructureTable(self, id=id, app_id=app_id, name=name)

    def create_app(self, name: str, description: str | None = None) -> StructureApp:
        """Create a new Quickbase application."""
        return self.app_manager.create(name=name, description=description)

    def update_app(
        self,
        app_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        variables: list[dict[str, Any]] | None = None,
        properties: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Update an existing Quickbase application."""
        return self.app(id=app_id).update(
            name=name,
            description=description,
            variables=variables,
            properties=properties,
        )

    def delete_app(self, app_id: str, *, confirm_name: str) -> None:
        """Delete a Quickbase application. Quickbase requires the app name as confirmation."""
        self.app(id=app_id, name=confirm_name).delete(confirm_name=confirm_name)

    def copy_app(
        self,
        app_id: str,
        *,
        target_name: str,
        description: str | None = None,
        exclude_files: bool = True,
        keep_data: bool = False,
        users_and_roles: bool = True,
        assign_user_token: bool = False,
    ) -> StructureApp:
        """Copy an existing Quickbase application."""
        return self.app(id=app_id).copy(
            target_name=target_name,
            description=description,
            exclude_files=exclude_files,
            keep_data=keep_data,
            users_and_roles=users_and_roles,
            assign_user_token=assign_user_token,
        )

    @contextmanager
    def suppress_auto_backup(self) -> Iterator[None]:
        """Temporarily suppress automatic backup hooks for internal backup calls."""
        self._backup_suppression_depth += 1
        try:
            yield
        finally:
            self._backup_suppression_depth -= 1

    @staticmethod
    def _sanitize_headers(headers: Mapping[str, Any]) -> Dict[str, str]:
        sanitized: Dict[str, str] = {}
        for key, value in headers.items():
            normalized_key = str(key)
            if normalized_key.lower() in SENSITIVE_HEADER_NAMES:
                sanitized[normalized_key] = "<redacted>"
            else:
                sanitized[normalized_key] = str(value)
        return sanitized

    @staticmethod
    def _summarize_payload(payload: JsonPayload | None) -> Dict[str, Any] | None:
        if payload is None:
            return None
        if isinstance(payload, list):
            return {"type": "list", "item_count": len(payload)}

        summary: Dict[str, Any] = {
            "type": type(payload).__name__,
            "keys": sorted(str(key) for key in payload.keys()),
        }
        trustees = payload.get("trustees")
        if isinstance(trustees, list):
            summary["trustee_count"] = len(trustees)
        summary_fields = payload.get("summaryFields")
        if isinstance(summary_fields, list):
            summary["summary_field_count"] = len(summary_fields)
        return summary

    def _emit_log_hook(
        self,
        hook: RequestLogHook | None,
        event: dict[str, Any],
        hook_name: str,
    ) -> None:
        if hook is None:
            return
        try:
            hook(event)
        except Exception:
            logger.warning(
                "%s raised while logging QuickBaseStructureClient activity.",
                hook_name,
                exc_info=True,
            )

    def _log_request(
        self,
        *,
        method: str,
        endpoint: str,
        url: str,
        payload: JsonPayload | None,
        headers: Mapping[str, Any] | None,
        attempt: int,
    ) -> None:
        combined_headers: Dict[str, Any] = dict(self.session.headers)
        if headers:
            combined_headers.update(headers)
        event = {
            "event": "request",
            "method": method,
            "endpoint": endpoint,
            "url": url,
            "attempt": attempt,
            "timeout": self.request_config.timeout,
            "headers": self._sanitize_headers(combined_headers),
            "payload_summary": self._summarize_payload(payload),
        }
        logger.debug("QuickBaseStructureClient.request: %s", event)
        self._emit_log_hook(
            self.request_config.request_log_hook,
            event,
            "request_log_hook",
        )

    def _log_response(
        self,
        *,
        response: requests.Response,
        method: str,
        endpoint: str,
        url: str,
        attempt: int,
        will_retry: bool,
        retry_delay: float | None = None,
    ) -> None:
        retry_after_header = None
        headers = getattr(response, "headers", {}) or {}
        if isinstance(headers, Mapping):
            retry_after_header = headers.get("Retry-After")

        event = {
            "event": "response",
            "method": method,
            "endpoint": endpoint,
            "url": url,
            "attempt": attempt,
            "status_code": response.status_code,
            "reason": getattr(response, "reason", None),
            "headers": self._sanitize_headers(headers) if isinstance(headers, Mapping) else {},
            "will_retry": will_retry,
        }
        if retry_after_header is not None:
            event["retry_after"] = retry_after_header
        if retry_delay is not None:
            event["retry_delay"] = retry_delay

        logger.debug("QuickBaseStructureClient.response: %s", event)
        self._emit_log_hook(
            self.request_config.response_log_hook,
            event,
            "response_log_hook",
        )

    @staticmethod
    def _response_body_preview(response: requests.Response) -> str | None:
        body = getattr(response, "text", None)
        if body is None:
            return None
        body_text = str(body)
        if len(body_text) <= MAX_ERROR_BODY_CHARS:
            return body_text
        return f"{body_text[:MAX_ERROR_BODY_CHARS]}..."

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return max(float(value), 0.0)
        except ValueError:
            pass
        try:
            retry_after_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None

        if retry_after_at.tzinfo is None:
            retry_after_at = retry_after_at.replace(tzinfo=timezone.utc)
        return max((retry_after_at - datetime.now(timezone.utc)).total_seconds(), 0.0)

    def _compute_retry_delay(
        self,
        *,
        attempt: int,
        response: requests.Response | None = None,
    ) -> float:
        if response is not None and self.request_config.respect_retry_after:
            headers = getattr(response, "headers", {}) or {}
            if isinstance(headers, Mapping):
                retry_after = self._parse_retry_after(headers.get("Retry-After"))
                if retry_after is not None:
                    return retry_after

        delay = self.request_config.backoff_factor * (2 ** (attempt - 1))
        if self.request_config.jitter:
            delay += random.random() * self.request_config.jitter
        return delay

    def _raise_http_error(
        self,
        *,
        response: requests.Response,
        endpoint: str,
        method: str,
        attempts: int,
    ) -> None:
        status_code = response.status_code
        response_body = self._response_body_preview(response)
        headers = getattr(response, "headers", {}) or {}
        retry_after = headers.get("Retry-After") if isinstance(headers, Mapping) else None

        error_cls: type[QuickbaseError] = QuickbaseHTTPError
        if status_code in {401, 403}:
            error_cls = QuickbaseAuthError
        elif status_code == 404:
            error_cls = QuickbaseNotFoundError
        elif status_code == 429:
            error_cls = QuickbaseRateLimitError

        http_error = requests.HTTPError(
            f"Quickbase returned HTTP {status_code} for {method} {endpoint}",
            response=response,
        )
        raise error_cls(
            format_error_message(
                "Quickbase request failed.",
                operation="QuickBaseStructureClient.request",
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                attempts=attempts,
                retry_count=self.request_config.retry_count,
                retry_after=retry_after,
                response_body=response_body,
                cause=http_error,
            )
        ) from http_error

    def request(
        self,
        *,
        method: Literal["GET", "POST", "DELETE", "PUT"],
        endpoint: str,
        payload: JsonPayload | None = None,
        headers: Mapping[str, str] | None = None,
        app_id_for_backup: str | None = None,
    ) -> requests.Response:
        """Sends a raw HTTP request and returns the requests.Response."""

        backup_state = None
        if (
            self._backup_suppression_depth == 0
            and app_id_for_backup is not None
            and method in {"POST", "PUT", "DELETE"}
        ):
            backup_state = self.backup_manager.trigger_pre_backup(app_id_for_backup)

        url = f"{self.base_url}{endpoint}"
        terminal_response = None

        for attempt in range(1, self.request_config.retry_count + 2):
            self._log_request(
                method=method,
                endpoint=endpoint,
                url=url,
                payload=payload,
                headers=headers,
                attempt=attempt,
            )
            try:
                response = self.session.request(
                    method,
                    url,
                    json=payload if payload is not None else None,
                    headers=dict(headers) if headers else None,
                    timeout=self.request_config.timeout,
                )
                will_retry = (
                    attempt <= self.request_config.retry_count
                    and response.status_code in self.request_config.retryable_status_codes
                )
                retry_delay = (
                    self._compute_retry_delay(attempt=attempt, response=response)
                    if will_retry
                    else None
                )
                self._log_response(
                    response=response,
                    method=method,
                    endpoint=endpoint,
                    url=url,
                    attempt=attempt,
                    will_retry=will_retry,
                    retry_delay=retry_delay,
                )
                if response.status_code < 400:
                    terminal_response = response
                    break

                if will_retry:
                    time.sleep(retry_delay or 0.0)
                    continue

                self._raise_http_error(
                    response=response,
                    endpoint=endpoint,
                    method=method,
                    attempts=attempt,
                )
            except requests.Timeout as exc:
                if attempt <= self.request_config.retry_count:
                    time.sleep(self._compute_retry_delay(attempt=attempt))
                    continue
                raise QuickbaseTransportError(
                    format_error_message(
                        "Quickbase request timed out.",
                        operation="QuickBaseStructureClient.request",
                        endpoint=endpoint,
                        method=method,
                        timeout=self.request_config.timeout,
                        attempts=attempt,
                    )
                ) from exc
            except (requests.ConnectionError, requests.RequestException) as exc:
                if attempt <= self.request_config.retry_count:
                    time.sleep(self._compute_retry_delay(attempt=attempt))
                    continue
                raise QuickbaseTransportError(
                    format_error_message(
                        "Quickbase transport/connection error.",
                        operation="QuickBaseStructureClient.request",
                        endpoint=endpoint,
                        method=method,
                        attempts=attempt,
                    )
                ) from exc

        if terminal_response is None:
            raise QuickbaseTransportError(
                format_error_message(
                    "Quickbase request exhausted retries without a terminal response.",
                    operation="QuickBaseStructureClient.request",
                    endpoint=endpoint,
                    method=method,
                    retry_count=self.request_config.retry_count,
                )
            )

        # Intercept mutation to trigger post-backup
        if backup_state:
            self.backup_manager.trigger_post_backup(backup_state)

        return terminal_response
