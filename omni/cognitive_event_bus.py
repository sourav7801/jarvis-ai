"""Bounded typed cognitive event bus for JARVIS V9.3.

The cognitive bus is an internal coordination surface. It distributes verified
state-change notifications between local JARVIS subsystems but never grants
execution authority. Consequential external actions remain approval-gated and
live broker execution remains disabled.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import re
from threading import RLock
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "state" / "cognitive_events.json"
MAX_PERSISTED = 1000
_SENSITIVE_KEY_PARTS = (
    "authorization", "api_key", "apikey", "token", "secret", "password",
    "passwd", "cookie", "credential", "access_key", "refresh_key",
)
_SECRET_TEXT_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)([^\s,;]+)"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret|password|passwd)\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)


class CognitiveEventType(str, Enum):
    MARKET_BAR_COMPLETED = "MARKET_BAR_COMPLETED"
    MARKET_DATA_STALE = "MARKET_DATA_STALE"
    PROVIDER_READY = "PROVIDER_READY"
    PROVIDER_DEGRADED = "PROVIDER_DEGRADED"
    PROVIDER_DOWN = "PROVIDER_DOWN"
    BREAKOUT_CANDIDATE = "BREAKOUT_CANDIDATE"
    PAPER_POSITION_OPENED = "PAPER_POSITION_OPENED"
    PAPER_POSITION_CLOSED = "PAPER_POSITION_CLOSED"
    RISK_LIMIT_CHANGED = "RISK_LIMIT_CHANGED"
    SERVICE_READY = "SERVICE_READY"
    SERVICE_DEGRADED = "SERVICE_DEGRADED"
    SERVICE_DOWN = "SERVICE_DOWN"
    SERVICE_RECOVERED = "SERVICE_RECOVERED"
    MISSION_CREATED = "MISSION_CREATED"
    MISSION_COMPLETED = "MISSION_COMPLETED"
    MISSION_FAILED = "MISSION_FAILED"
    TASK_READY = "TASK_READY"
    TASK_RUNNING = "TASK_RUNNING"
    TASK_VERIFIED = "TASK_VERIFIED"
    TASK_FAILED = "TASK_FAILED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    FILE_CHANGED = "FILE_CHANGED"
    TEST_FAILED = "TEST_FAILED"
    TEST_PASSED = "TEST_PASSED"
    MODEL_ROUTE_COMPLETED = "MODEL_ROUTE_COMPLETED"
    MEMORY_WRITTEN = "MEMORY_WRITTEN"
    WORLD_STATE_UPDATED = "WORLD_STATE_UPDATED"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sensitive_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _redact_text(value: Any, limit: int) -> str:
    text = str(value or "")
    for pattern in _SECRET_TEXT_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(lambda match: match.group(1) + "[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text[:limit]


def _bounded(
    value: Any,
    *,
    max_depth: int = 4,
    max_items: int = 50,
    max_text: int = 2000,
    _depth: int = 0,
) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _redact_text(value, max_text)
    if _depth >= max_depth:
        if isinstance(value, (Mapping, list, tuple, set, frozenset)):
            return "[TRUNCATED]"
        return _redact_text(value, max_text)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                break
            clean_key = str(key)[:120]
            result[clean_key] = "[REDACTED]" if _sensitive_key(clean_key) else _bounded(
                item,
                max_depth=max_depth,
                max_items=max_items,
                max_text=max_text,
                _depth=_depth + 1,
            )
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            _bounded(
                item,
                max_depth=max_depth,
                max_items=max_items,
                max_text=max_text,
                _depth=_depth + 1,
            )
            for item in list(value)[:max_items]
        ]
    return _redact_text(value, max_text)


@dataclass(frozen=True)
class CognitiveEvent:
    event_id: str
    event_type: str
    timestamp: str
    source: str
    subject: str
    payload: Mapping[str, Any]
    provenance: Mapping[str, Any]
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        CognitiveEventType(self.event_type)
        if not self.event_id.strip() or not self.source.strip() or not self.subject.strip():
            raise ValueError("Cognitive events require id, source and subject.")
        if not isinstance(self.payload, Mapping) or not isinstance(self.provenance, Mapping):
            raise TypeError("Cognitive event payload and provenance must be mappings.")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


Subscriber = Callable[[CognitiveEvent], None]


class CognitiveEventBus:
    def __init__(
        self,
        path: Path | str | None = None,
        *,
        capacity: int = 1000,
        persist: bool = True,
    ) -> None:
        self.path = Path(path or DEFAULT_PATH)
        self.capacity = max(50, min(int(capacity), 10_000))
        self.persist = bool(persist)
        self._lock = RLock()
        self._events: deque[dict[str, Any]] = deque(maxlen=self.capacity)
        self._subscribers: dict[str, tuple[set[str] | None, Subscriber]] = {}
        self._published = 0
        self._subscriber_errors = 0
        self._load()

    def _load(self) -> None:
        if not self.persist:
            return
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError, TypeError):
            return
        if not isinstance(value, dict):
            return
        events = value.get("events") or []
        if not isinstance(events, list):
            return
        for item in events[-self.capacity :]:
            if isinstance(item, dict):
                self._events.append(item)
        self._published = int(value.get("published") or len(self._events))
        self._subscriber_errors = int(value.get("subscriber_errors") or 0)

    def _save(self) -> None:
        if not self.persist:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {
            "version": 1,
            "updated_at": _now(),
            "published": self._published,
            "subscriber_errors": self._subscriber_errors,
            "events": list(self._events)[-min(self.capacity, MAX_PERSISTED) :],
        }
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def subscribe(
        self,
        name: str,
        callback: Subscriber,
        event_types: Iterable[CognitiveEventType | str] | None = None,
    ) -> None:
        clean = str(name or "").strip()
        if not clean or not callable(callback):
            raise ValueError("Subscriber name and callback are required.")
        normalized = None
        if event_types is not None:
            normalized = {
                CognitiveEventType(
                    str(item.value if isinstance(item, CognitiveEventType) else item)
                ).value
                for item in event_types
            }
        with self._lock:
            self._subscribers[clean[:120]] = (normalized, callback)

    def unsubscribe(self, name: str) -> None:
        with self._lock:
            self._subscribers.pop(str(name), None)

    def publish(
        self,
        event_type: CognitiveEventType | str,
        *,
        source: str,
        subject: str,
        payload: Mapping[str, Any] | None = None,
        provenance: Mapping[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        kind = CognitiveEventType(
            str(event_type.value if isinstance(event_type, CognitiveEventType) else event_type)
        )
        event = CognitiveEvent(
            event_id="evt-" + uuid4().hex[:20],
            event_type=kind.value,
            timestamp=_now(),
            source=_redact_text(source, 160).strip(),
            subject=_redact_text(subject, 240).strip(),
            payload=_bounded(dict(payload or {})),
            provenance=_bounded(dict(provenance or {})),
            correlation_id=(_redact_text(correlation_id, 160).strip() if correlation_id else None),
        )
        with self._lock:
            self._events.append(event.as_dict())
            self._published += 1
            subscribers = list(self._subscribers.items())
            self._save()
        delivered = 0
        errors = 0
        for _name, (filter_types, callback) in subscribers:
            if filter_types is not None and event.event_type not in filter_types:
                continue
            try:
                callback(event)
                delivered += 1
            except Exception:
                errors += 1
        if errors:
            with self._lock:
                self._subscriber_errors += errors
                self._save()
        return {
            "success": True,
            "accepted": True,
            "event_id": event.event_id,
            "event_type": event.event_type,
            "delivered": delivered,
            "subscriber_errors": errors,
            "external_actions": "APPROVAL_GATED",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }

    def snapshot(self, *, limit: int = 100, event_type: str | None = None) -> dict[str, Any]:
        limit = max(1, min(int(limit), self.capacity))
        with self._lock:
            all_events = list(self._events)
            subscribers = sorted(self._subscribers)
            published = self._published
            subscriber_errors = self._subscriber_errors
        events = all_events
        if event_type:
            normalized = CognitiveEventType(str(event_type)).value
            events = [item for item in events if item.get("event_type") == normalized]
        return {
            "success": True,
            "version": "9.3",
            "capacity": self.capacity,
            "retained": len(all_events),
            "matched": len(events),
            "published": published,
            "subscriber_errors": subscriber_errors,
            "subscribers": subscribers,
            "events": events[-limit:],
            "persistent": self.persist,
            "redacts_sensitive_fields": True,
            "external_actions": "APPROVAL_GATED",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


COGNITIVE_EVENT_BUS = CognitiveEventBus()

__all__ = [
    "COGNITIVE_EVENT_BUS",
    "CognitiveEvent",
    "CognitiveEventBus",
    "CognitiveEventType",
]
