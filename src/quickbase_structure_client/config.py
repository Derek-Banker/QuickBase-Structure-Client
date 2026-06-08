"""Default configuration values for Quickbase API requests."""

from typing import Final

BASE_URL: Final[str] = "https://api.quickbase.com/v1"

DEFAULT_REQUEST_TIMEOUT: Final[tuple[float, float]] = (3.0, 25.0)
DEFAULT_RETRY_COUNT: Final[int] = 2
DEFAULT_RETRYABLE_STATUS_CODES: Final[frozenset[int]] = frozenset({429, 502, 503, 504})
DEFAULT_RETRY_BACKOFF_FACTOR: Final[float] = 0.5
DEFAULT_RETRY_JITTER: Final[float] = 0.25
