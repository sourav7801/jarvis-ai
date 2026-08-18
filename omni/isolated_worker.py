"""Child-process entry point for signed isolated agent requests."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import sys
from typing import Any

from .agent_registry import default_agent_specs
from .isolated_runner import sign_payload, verify_payload


MAX_ENVELOPE_CHARS = 100_000


def _respond(payload: dict[str, Any], key: str) -> None:
    envelope = {"payload": payload, "signature": sign_payload(payload, key)}
    sys.stdout.write(json.dumps(envelope, default=str, sort_keys=True))


def main() -> int:
    key = os.environ.get("OMNI_WORKER_SIGNING_KEY", "")
    raw = sys.stdin.read(MAX_ENVELOPE_CHARS + 1)
    if not key or len(raw) > MAX_ENVELOPE_CHARS:
        return 2
    try:
        envelope = json.loads(raw)
        payload = envelope["payload"]
        if not verify_payload(payload, envelope["signature"], key):
            return 3
        if payload.get("version") != 1:
            return 4
        allowed = {spec.name: spec for spec in default_agent_specs()}
        spec = allowed.get(str(payload.get("agent", "")).lower())
        if (
            spec is None
            or spec.module != payload.get("module")
            or spec.entrypoint != payload.get("entrypoint")
        ):
            return 5
        text = str(payload.get("text", ""))
        if not text or len(text) > spec.max_input_chars:
            return 6

        logs = io.StringIO()
        try:
            with contextlib.redirect_stdout(logs), contextlib.redirect_stderr(logs):
                module = importlib.import_module(spec.module)
                function = getattr(module, spec.entrypoint)
                data = function(text)
            if isinstance(data, dict):
                message = str(data.get("message") or data.get("response") or data)
            else:
                message = str(data)
            response = {
                "request_id": payload["request_id"],
                "status": "SUCCEEDED",
                "message": message[: spec.max_output_chars],
                "data": data,
            }
        except Exception as error:
            response = {
                "request_id": payload.get("request_id"),
                "status": "FAILED",
                "message": "Agent failed safely in isolated execution.",
                "error_type": type(error).__name__,
            }
        _respond(response, key)
        return 0
    except (json.JSONDecodeError, KeyError, TypeError):
        return 7


if __name__ == "__main__":
    raise SystemExit(main())

