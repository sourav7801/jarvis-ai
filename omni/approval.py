"""Short-lived, single-use approval grants for governed actions."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .audit import AuditStore


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApprovalGrant:
    id: str
    token: str
    action: str
    capability: str
    expires_at: str


class ApprovalService:
    def __init__(self, store: AuditStore, max_ttl_seconds: int = 300):
        self.store = store
        self.max_ttl_seconds = min(max(int(max_ttl_seconds), 1), 900)

    def issue(
        self, action: str, capability: str, ttl_seconds: int = 60
    ) -> ApprovalGrant:
        action = str(action).strip()
        capability = str(capability).strip()
        if not action or not capability:
            raise ValueError("Approval action and capability are required.")
        ttl = min(max(int(ttl_seconds), 1), self.max_ttl_seconds)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl)
        token = secrets.token_urlsafe(32)
        approval_id = uuid4().hex
        self.store.save_approval(
            approval_id,
            _token_hash(token),
            action,
            capability,
            _timestamp(now),
            _timestamp(expires),
        )
        self.store.record_event(
            "approval",
            action,
            "ISSUED",
            {"capability": capability, "ttl_seconds": ttl},
            approval_id,
        )
        return ApprovalGrant(
            approval_id, token, action, capability, _timestamp(expires)
        )

    def consume(self, token: str, action: str, capability: str) -> bool:
        if not token:
            return False
        consumed_at = _timestamp(datetime.now(timezone.utc))
        accepted = self.store.consume_approval(
            _token_hash(token), action, capability, consumed_at
        )
        self.store.record_event(
            "approval",
            action,
            "CONSUMED" if accepted else "REJECTED",
            {"capability": capability},
        )
        return accepted

