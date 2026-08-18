"""Signed, bounded subprocess runner for explicitly isolated legacy agents."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .agent_registry import AgentSpec
from .runtime import audit_event
from .sandbox import SandboxPolicy, SubprocessSandbox


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKER_MODULE = "omni.isolated_worker"


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, default=str, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sign_payload(payload: dict[str, Any], key: str) -> str:
    return hmac.new(key.encode("utf-8"), _canonical(payload), hashlib.sha256).hexdigest()


def verify_payload(payload: dict[str, Any], signature: str, key: str) -> bool:
    return hmac.compare_digest(sign_payload(payload, key), str(signature))


@dataclass(frozen=True)
class WorkerLimits:
    timeout_seconds: int = 60
    max_input_chars: int = 20_000
    max_output_chars: int = 100_000

    def __post_init__(self) -> None:
        if self.timeout_seconds < 1 or self.timeout_seconds > 300:
            raise ValueError("Worker timeout must be between 1 and 300 seconds.")
        if self.max_input_chars < 1 or self.max_output_chars < 1:
            raise ValueError("Worker input/output limits must be positive.")


class IsolatedAgentRunner:
    def __init__(
        self,
        python_executable: str | None = None,
        limits: WorkerLimits | None = None,
        signing_key: str | None = None,
    ):
        self.python_executable = str(python_executable or sys.executable)
        self.limits = limits or WorkerLimits()
        self._signing_key = signing_key or secrets.token_urlsafe(48)

    def __call__(self, spec: AgentSpec, text: str):
        if len(text) > min(spec.max_input_chars, self.limits.max_input_chars):
            raise ValueError("Isolated-agent request exceeds input limit.")
        request_id = uuid4().hex
        payload = {
            "version": 1,
            "request_id": request_id,
            "agent": spec.name,
            "module": spec.module,
            "entrypoint": spec.entrypoint,
            "text": text,
        }
        envelope = {
            "payload": payload,
            "signature": sign_payload(payload, self._signing_key),
        }

        with tempfile.TemporaryDirectory(prefix="omni_worker_") as directory:
            workspace = Path(directory).resolve()
            sandbox = SubprocessSandbox(
                SandboxPolicy(
                    allowed_executables=frozenset(
                        {Path(self.python_executable).name}
                    ),
                    allowed_roots=(workspace,),
                    max_timeout_seconds=self.limits.timeout_seconds,
                    max_output_chars=self.limits.max_output_chars,
                )
            )
            result = sandbox.run(
                [self.python_executable, "-m", WORKER_MODULE],
                workspace,
                timeout_seconds=self.limits.timeout_seconds,
                input_text=json.dumps(envelope),
                environment={
                    "OMNI_WORKER_SIGNING_KEY": self._signing_key,
                    "PYTHONPATH": str(PROJECT_ROOT),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
            )

        if result.timed_out:
            raise TimeoutError("Isolated agent exceeded its execution timeout.")
        if result.returncode != 0:
            raise RuntimeError("Isolated agent process failed.")
        try:
            response_envelope = json.loads(result.stdout)
            response_payload = response_envelope["payload"]
            signature = response_envelope["signature"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise RuntimeError("Isolated agent returned an invalid envelope.") from error
        if not verify_payload(response_payload, signature, self._signing_key):
            raise RuntimeError("Isolated agent response signature is invalid.")
        if response_payload.get("request_id") != request_id:
            raise RuntimeError("Isolated agent response correlation mismatch.")

        audit_event(
            "isolated_worker",
            spec.name,
            response_payload.get("status", "UNKNOWN"),
            {"output_characters": len(str(response_payload.get("message", "")))},
            request_id,
        )
        if response_payload.get("status") != "SUCCEEDED":
            raise RuntimeError(
                f"Isolated agent failed: {response_payload.get('error_type', 'UNKNOWN')}"
            )
        return response_payload.get("data", response_payload.get("message", ""))

