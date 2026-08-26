"""Durable approval queue for consequential Company OS actions.

The queue prepares exact, reviewable payloads but deliberately contains no
connector or execution implementation.  Approval is bound to the payload hash;
editing a payload therefore requires a new approval.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4


SECRET_KEYS = {
    "access_token", "api_key", "api_secret", "app_secret", "client_secret",
    "password", "private_key", "refresh_token", "secret", "token",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _assert_secret_free(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).strip().lower()
            if normalized in SECRET_KEYS or normalized.endswith("_token") or normalized.endswith("_secret"):
                raise ValueError(f"Secret-bearing field is prohibited in action packets: {path}.{key}")
            _assert_secret_free(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_secret_free(item, f"{path}[{index}]")


class CompanyActionQueue:
    """Prepare, approve and revoke exact external-action envelopes."""

    def __init__(self, state_path: Path):
        self.state_path = Path(state_path)
        self._lock = RLock()
        self._state: dict[str, Any] = {"version": 1, "actions": []}
        try:
            loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("actions"), list):
                self._state = loaded
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._state, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.state_path)

    def prepare(
        self,
        *,
        plan_id: str,
        department: str,
        action_type: str,
        connector: str,
        destination: str,
        payload: dict[str, Any],
        expires_hours: int = 168,
    ) -> dict[str, Any]:
        if not all(str(value).strip() for value in (plan_id, department, action_type, connector, destination)):
            raise ValueError("Action packets require plan, department, type, connector and destination.")
        if not isinstance(payload, dict) or not payload:
            raise ValueError("Action payload must be a non-empty object.")
        _assert_secret_free(payload)
        created = _now()
        packet = {
            "id": uuid4().hex,
            "plan_id": str(plan_id),
            "department": str(department),
            "action_type": str(action_type),
            "connector": str(connector),
            "destination": str(destination),
            "payload": payload,
            "payload_hash": _payload_hash(payload),
            "created_at": created.isoformat(),
            "expires_at": (created + timedelta(hours=max(1, min(int(expires_hours), 720)))).isoformat(),
            "status": "DRAFT_REVIEW_REQUIRED",
            "approved_by": None,
            "approved_at": None,
            "executed": False,
        }
        with self._lock:
            self._state["actions"].append(packet)
            self._save()
        return dict(packet)

    def _find(self, action_id: str) -> dict[str, Any]:
        for item in self._state["actions"]:
            if item.get("id") == action_id:
                return item
        raise KeyError(f"Unknown company action: {action_id}")

    def approve(self, action_id: str, expected_payload_hash: str, approver: str) -> dict[str, Any]:
        with self._lock:
            item = self._find(action_id)
            if item["status"] != "DRAFT_REVIEW_REQUIRED":
                raise ValueError(f"Action cannot be approved from {item['status']}.")
            if item["destination"] == "UNCONFIGURED":
                raise ValueError("A configured destination is required before approval.")
            if _now() >= datetime.fromisoformat(item["expires_at"]):
                item["status"] = "EXPIRED"
                self._save()
                raise ValueError("Action packet has expired.")
            actual = _payload_hash(item["payload"])
            if actual != item["payload_hash"] or actual != expected_payload_hash:
                raise ValueError("Payload hash mismatch; review a newly prepared action.")
            if not str(approver).strip():
                raise ValueError("Approver identity is required.")
            item.update(status="APPROVED_NOT_EXECUTED", approved_by=str(approver).strip(), approved_at=_now().isoformat())
            self._save()
            return dict(item)

    def revoke(self, action_id: str, reason: str) -> dict[str, Any]:
        if not str(reason).strip():
            raise ValueError("A revocation reason is required.")
        with self._lock:
            item = self._find(action_id)
            if item.get("executed"):
                raise ValueError("An executed action cannot be revoked by the preparation queue.")
            item.update(status="REVOKED", revoked_at=_now().isoformat(), revocation_reason=str(reason).strip())
            self._save()
            return dict(item)

    def execution_envelope(self, action_id: str, *, connector_connected: bool, sandbox: bool) -> dict[str, Any]:
        """Return a bounded envelope; this method never performs the action."""
        with self._lock:
            item = self._find(action_id)
            if item["status"] != "APPROVED_NOT_EXECUTED":
                raise ValueError("Exact action approval is required.")
            if not connector_connected or not sandbox:
                raise ValueError("A connected sandbox connector is required.")
            if _payload_hash(item["payload"]) != item["payload_hash"]:
                raise ValueError("Approved payload was modified.")
            return {
                "action_id": item["id"], "connector": item["connector"],
                "destination": item["destination"], "payload": item["payload"],
                "payload_hash": item["payload_hash"], "sandbox_only": True,
                "external_action_executed": False,
            }

    def snapshot(self, plan_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            actions = [dict(item) for item in self._state["actions"] if plan_id is None or item.get("plan_id") == plan_id]
        counts: dict[str, int] = {}
        for item in actions:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        return {"version": 1, "actions": actions, "counts": counts, "external_actions_executed": False}

