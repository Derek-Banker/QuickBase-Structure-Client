from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class FakeResponse:
    def __init__(
        self,
        json_data: Any | None = None,
        *,
        status_code: int = 200,
        text: str = "",
        headers: dict[str, str] | None = None,
    ):
        self._json_data = {} if json_data is None else json_data
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.reason = None

    def json(self) -> Any:
        return self._json_data


class RecordingClient:
    def __init__(self, responses: list[FakeResponse] | None = None):
        self.calls: list[dict[str, Any]] = []
        self.responses = responses or [FakeResponse()]
        self.auto_backup = False

    def request(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]
