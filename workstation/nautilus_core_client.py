from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "http://127.0.0.1:8792"
TIMEOUT_SECONDS = 2.0


def _request(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = BASE_URL + path
    data = None
    headers = {"Accept": "application/json"}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload, default=str).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(2_000_000)
        decoded = json.loads(raw.decode("utf-8"))
        return decoded if isinstance(decoded, dict) else {"success": False}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {
            "success": False,
            "service": "JARVIS_NAUTILUS_QUANT_CORE",
            "message": str(exc)[:300],
            "live_execution": False,
        }


def status() -> dict[str, Any]:
    return _request("/status")


def metrics() -> dict[str, Any]:
    return _request("/metrics")


def publish_market_event(payload: dict[str, Any]) -> dict[str, Any]:
    safe = dict(payload or {})
    safe.pop("api_key", None)
    safe.pop("api_secret", None)
    safe.pop("access_token", None)
    return _request("/event", safe)


def backtest_selftest() -> dict[str, Any]:
    return _request("/backtest-selftest", {})
